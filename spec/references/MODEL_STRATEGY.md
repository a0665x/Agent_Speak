# Model Strategy

API contracts intentionally precede heavy model installation.

Evaluation order on Jetson AGX Orin:
- VAD: Silero VAD ONNX; energy VAD stays as fallback.
- ASR: faster-whisper/CTranslate2 when Jetson wheels are stable, or whisper.cpp CUDA as robust aarch64 fallback; benchmark Mandarin/Taiwanese samples.
- Speaker: ECAPA-TDNN/WeSpeaker ONNX; calibrate locally; never treat convenience matching as authentication.
- TTS: Piper or sherpa-onnx; verify Mandarin voice quality and licensing.
- Voice cloning: same TTS provider contract, explicit consent/provenance/disclosure before enabling.
- Correction/end detection: deterministic rules first; train a small classifier only after labeled data exists.

Production providers report model, version, device, readiness, and limitations through `/capabilities`, with latency/quality fixtures.
