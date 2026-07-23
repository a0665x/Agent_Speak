FROM node:22-bookworm-slim AS realtime-frontend-deps

WORKDIR /workspace/frontend/realtime
COPY frontend/realtime/package.json frontend/realtime/package-lock.json ./
RUN npm ci
COPY frontend/realtime ./

FROM realtime-frontend-deps AS frontend-test
CMD ["npm", "test"]

FROM realtime-frontend-deps AS realtime-frontend-build
RUN npm run build

FROM python:3.11-slim-bookworm AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/app/models/home \
    HF_HOME=/app/models/huggingface \
    XDG_CACHE_HOME=/app/models/cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends alsa-utils libgomp1 libsndfile1 nodejs ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml LICENSE ./
COPY src ./src
ARG AGENT_SPEAK_IMAGE_VARIANT=cpu
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -e '.[test]'

ENV LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib

FROM python-base AS model-downloader

COPY . .
RUN python -m pip install -e '.[models]'
ENTRYPOINT ["python", "scripts/bootstrap_models.py"]
CMD ["--verify"]

FROM python-base AS runtime

# Include runtime assets and the complete public repository contract after dependencies,
# so documentation/script edits do not invalidate the expensive inference dependency layer.
# .dockerignore excludes private state, models, credentials, caches, and local Agent data.
COPY . .
COPY --from=realtime-frontend-build /workspace/web/asr_realtime /app/web/asr_realtime
COPY --from=realtime-frontend-build /workspace/web/tts_clone_test /app/web/tts_clone_test
COPY docker/entrypoint.sh /usr/local/bin/agent-speak-entrypoint
RUN chmod 0755 /usr/local/bin/agent-speak-entrypoint

EXPOSE 8765
VOLUME ["/app/data", "/app/runtime", "/app/models"]

HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=6 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/v1/health', timeout=3).read()"]

ENTRYPOINT ["agent-speak-entrypoint"]
CMD ["python", "-m", "uvicorn", "agent_speak.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8765"]

FROM runtime AS asr-runtime

ARG AGENT_SPEAK_IMAGE_VARIANT=cpu
RUN if [ "$AGENT_SPEAK_IMAGE_VARIANT" = "nvidia" ]; then \
      python -m pip install -e '.[asr,gpu]'; \
    else \
      python -m pip install -e '.[asr]'; \
    fi

FROM python:3.12-slim-bookworm AS tts-runtime

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/app/models/home \
    HF_HOME=/app/models/huggingface \
    XDG_CACHE_HOME=/app/models/cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install "uv>=0.8,<1" \
    && uv pip install --system "vllm==0.24.0" --torch-backend=auto \
    && uv pip install --system \
      "vllm-omni @ git+https://github.com/vllm-project/vllm-omni.git@b9e9d236c3f78afd405119a5b686ebebeeb53984"

RUN uv pip install --system "voxcpm==2.0.3"

COPY scripts/patch_vllm_omni_voxcpm2.py /tmp/patch_vllm_omni_voxcpm2.py
RUN python /tmp/patch_vllm_omni_voxcpm2.py \
    && rm /tmp/patch_vllm_omni_voxcpm2.py

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

HEALTHCHECK --interval=10s --timeout=5s --start-period=300s --retries=30 \
  CMD ["curl", "-fsS", "http://127.0.0.1:8000/health"]
