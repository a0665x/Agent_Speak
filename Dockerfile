FROM python:3.11-slim-bookworm

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
    && if [ "$AGENT_SPEAK_IMAGE_VARIANT" = "nvidia" ]; then \
         python -m pip install -e '.[test,gpu]'; \
       else \
         python -m pip install -e '.[test]'; \
       fi

ENV LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib

# Include runtime assets and the complete public repository contract after dependencies,
# so documentation/script edits do not invalidate the expensive inference dependency layer.
# .dockerignore excludes private state, models, credentials, caches, and local Agent data.
COPY . .
COPY docker/entrypoint.sh /usr/local/bin/agent-speak-entrypoint
RUN chmod 0755 /usr/local/bin/agent-speak-entrypoint

EXPOSE 8765
VOLUME ["/app/data", "/app/runtime", "/app/models"]

HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=6 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/v1/health', timeout=3).read()"]

ENTRYPOINT ["agent-speak-entrypoint"]
CMD ["python", "-m", "uvicorn", "agent_speak.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8765"]
