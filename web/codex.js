"use strict";

const MAX_RECORDING_SECONDS = 30;
const MAX_AUDIO_BYTES = 8 * 1024 * 1024;
const {
  findZoneVibeDevices,
  hasRequiredDevices,
  controlsForState,
  formatTimer,
} = globalThis.AgentSpeakCodexRecorder;

const elements = {
  gatewayStatus: document.querySelector("#gateway-status"),
  checkDevices: document.querySelector("#device-check-button"),
  start: document.querySelector("#start-recording-button"),
  stop: document.querySelector("#stop-recording-button"),
  inputLabel: document.querySelector("#input-device-label"),
  outputLabel: document.querySelector("#output-device-label"),
  deviceStatus: document.querySelector("#device-status"),
  timer: document.querySelector("#recording-timer"),
  recordingStatus: document.querySelector("#recording-status"),
  rawTranscript: document.querySelector("#raw-transcript"),
  correctedText: document.querySelector("#corrected-text"),
  clipboardStatus: document.querySelector("#clipboard-status"),
  copy: document.querySelector("#copy-text-button"),
  error: document.querySelector("#action-error"),
};

const state = {
  phase: "unchecked",
  devices: { input: null, output: null },
  stream: null,
  recorder: null,
  chunks: [],
  autoStopTimer: null,
  timerInterval: null,
  startedAt: 0,
  discardRecording: false,
};

function renderControls() {
  const controls = controlsForState(state.phase, hasRequiredDevices(state.devices));
  elements.checkDevices.disabled = controls.checkDisabled;
  elements.start.disabled = controls.startDisabled;
  elements.stop.disabled = controls.stopDisabled;
}

function setPhase(phase) {
  state.phase = phase;
  renderControls();
}

function clearError() {
  elements.error.hidden = true;
  elements.error.textContent = "";
}

function showError(message) {
  elements.error.textContent = message;
  elements.error.hidden = false;
}

function stopTracks(stream) {
  if (!stream) return;
  stream.getTracks().forEach((track) => track.stop());
}

function clearRecordingTimers() {
  clearTimeout(state.autoStopTimer);
  clearInterval(state.timerInterval);
  state.autoStopTimer = null;
  state.timerInterval = null;
}

function assertCaptureSupport() {
  if (!navigator.mediaDevices?.getUserMedia || !navigator.mediaDevices?.enumerateDevices) {
    throw new Error("此瀏覽器不支援音訊裝置檢查，請使用最新版 Chromium 或 Chrome。");
  }
  if (typeof MediaRecorder !== "function") {
    throw new Error("此瀏覽器不支援錄音，請使用最新版 Chromium 或 Chrome。");
  }
}

async function checkGateway() {
  try {
    const response = await fetch("/api/v1/health");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const health = await response.json();
    if (health.status !== "ok") throw new Error("health status is not ok");
    elements.gatewayStatus.textContent = "Gateway 已連線";
  } catch (error) {
    elements.gatewayStatus.textContent = "Gateway 無法連線";
    showError("無法連線本機 Gateway，請確認服務已啟動後重新載入。");
  }
}

async function checkDevices() {
  clearError();
  setPhase("checking");
  elements.deviceStatus.textContent = "正在請求麥克風權限並檢查裝置…";
  let permissionStream = null;
  try {
    assertCaptureSupport();
    permissionStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const devices = await navigator.mediaDevices.enumerateDevices();
    state.devices = findZoneVibeDevices(devices);
    elements.inputLabel.textContent = state.devices.input?.label || "找不到 Zone Vibe 100 麥克風";
    elements.outputLabel.textContent = state.devices.output?.label || "找不到 Zone Vibe 100 喇叭";
    if (!hasRequiredDevices(state.devices)) {
      const missing = [
        !state.devices.input ? "麥克風" : "",
        !state.devices.output ? "喇叭" : "",
      ].filter(Boolean).join("與");
      throw new Error(`找不到 Zone Vibe 100 ${missing}，請確認藍牙設定後重新檢查。`);
    }
    elements.deviceStatus.textContent = "麥克風與喇叭皆可由瀏覽器看見；檢查沒有錄音或播放聲音。";
    elements.recordingStatus.textContent = "裝置已確認，可以開始錄音。";
    setPhase("ready");
  } catch (error) {
    state.devices = { input: null, output: null };
    setPhase("error");
    const message = error?.name === "NotAllowedError"
      ? "麥克風權限被拒絕，請允許此本機頁面使用麥克風後重新檢查。"
      : String(error?.message || error);
    elements.deviceStatus.textContent = "裝置檢查未完成。";
    showError(message);
  } finally {
    stopTracks(permissionStream);
  }
}

function updateTimer() {
  const elapsed = Math.floor((Date.now() - state.startedAt) / 1000);
  elements.timer.textContent = formatTimer(elapsed);
}

function validateAudioSize(blob) {
  if (!blob || blob.size === 0) throw new Error("沒有收到錄音資料，請重新錄製。");
  if (blob.size > MAX_AUDIO_BYTES) throw new Error("音訊超過 8 MiB 上限，請縮短錄音後重試。");
}

async function decodeToMono(blob) {
  const AudioContextType = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextType) throw new Error("此瀏覽器不支援音訊轉換。");
  const context = new AudioContextType();
  try {
    const decoded = await context.decodeAudioData(await blob.arrayBuffer());
    const samples = new Float32Array(decoded.length);
    for (let channel = 0; channel < decoded.numberOfChannels; channel += 1) {
      const source = decoded.getChannelData(channel);
      for (let index = 0; index < decoded.length; index += 1) {
        samples[index] += source[index] / decoded.numberOfChannels;
      }
    }
    return { samples, sampleRate: decoded.sampleRate };
  } finally {
    await context.close();
  }
}

function writeAscii(view, offset, value) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(44 + index * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
  return new Blob([view.buffer], { type: "audio/wav" });
}

async function readJson(response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.error?.message || `HTTP ${response.status}`);
    error.code = body.error?.code || "request_failed";
    throw error;
  }
  return body;
}

function requireText(value, message) {
  const text = String(value || "").trim();
  if (!text) throw new Error(message);
  return text;
}

async function copyCorrectedText({ automatic = false } = {}) {
  const text = requireText(elements.correctedText.textContent, "沒有可複製的校正文字。");
  try {
    if (!navigator.clipboard?.writeText) throw new Error("Clipboard API unavailable");
    await navigator.clipboard.writeText(text);
    elements.clipboardStatus.textContent = "校正文字已複製；請回到 Codex CLI 貼上並按 Enter。";
    elements.copy.hidden = true;
  } catch (error) {
    elements.copy.hidden = false;
    if (automatic) {
      elements.clipboardStatus.textContent = "瀏覽器未允許自動複製，請按下方按鈕。";
      return;
    }
    elements.clipboardStatus.textContent = "複製失敗；請允許剪貼簿權限後重試。";
    showError(`無法複製校正文字：${String(error?.message || error)}`);
  }
}

async function processRecording() {
  if (state.discardRecording) {
    state.discardRecording = false;
    state.chunks = [];
    state.recorder = null;
    return;
  }
  clearError();
  elements.copy.hidden = true;
  try {
    const source = new Blob(state.chunks, { type: state.recorder?.mimeType || "audio/webm" });
    validateAudioSize(source);
    elements.recordingStatus.textContent = "正在轉換為 16-bit PCM WAV…";
    const decoded = await decodeToMono(source);
    const wav = encodeWav(decoded.samples, decoded.sampleRate);
    validateAudioSize(wav);

    elements.recordingStatus.textContent = "正在辨識語音…";
    const asrResponse = await fetch("/api/v1/audio/asr", {
      method: "POST",
      headers: { "Content-Type": "audio/wav" },
      body: wav,
    });
    const asr = await readJson(asrResponse);
    const transcript = requireText(asr.text, "ASR 沒有回傳文字，請說得更清楚後重試。");
    elements.rawTranscript.textContent = transcript;

    elements.recordingStatus.textContent = "正在校正文字…";
    const correctionResponse = await fetch("/api/v1/text/correct", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: transcript }),
    });
    const correction = await readJson(correctionResponse);
    const corrected = requireText(correction.text, "文字校正沒有回傳內容，請重試。");
    elements.correctedText.textContent = corrected;
    elements.recordingStatus.textContent = "辨識與校正完成。";
    await copyCorrectedText({ automatic: true });
  } catch (error) {
    elements.recordingStatus.textContent = "這次錄音未完成處理。";
    showError(`處理失敗：${String(error?.message || error)}`);
  } finally {
    state.chunks = [];
    state.recorder = null;
    setPhase(hasRequiredDevices(state.devices) ? "ready" : "unchecked");
  }
}

async function startRecording() {
  if (!hasRequiredDevices(state.devices)) {
    showError("請先確認 Zone Vibe 100 麥克風與喇叭。");
    setPhase("unchecked");
    return;
  }
  clearError();
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({
      audio: { deviceId: { exact: state.devices.input.deviceId } },
    });
    state.recorder = new MediaRecorder(state.stream);
    state.chunks = [];
    state.discardRecording = false;
    state.recorder.addEventListener("dataavailable", (event) => {
      if (event.data && event.data.size) state.chunks.push(event.data);
    });
    state.recorder.addEventListener("stop", processRecording, { once: true });
    state.recorder.start();
    state.startedAt = Date.now();
    elements.timer.textContent = formatTimer(0);
    elements.recordingStatus.textContent = "錄音中；可隨時按下結束錄音。";
    setPhase("recording");
    state.timerInterval = setInterval(updateTimer, 250);
    state.autoStopTimer = setTimeout(stopRecording, MAX_RECORDING_SECONDS * 1000);
  } catch (error) {
    stopTracks(state.stream);
    state.stream = null;
    state.recorder = null;
    setPhase("error");
    showError(`無法開始錄音：${String(error?.message || error)}`);
  }
}

function stopRecording() {
  if (!state.recorder || state.recorder.state === "inactive") return;
  clearRecordingTimers();
  elements.timer.textContent = formatTimer(Math.floor((Date.now() - state.startedAt) / 1000));
  elements.recordingStatus.textContent = "正在處理錄音…";
  setPhase("processing");
  state.recorder.stop();
  stopTracks(state.stream);
  state.stream = null;
}

function invalidateDevices() {
  state.devices = { input: null, output: null };
  elements.inputLabel.textContent = "需要重新確認";
  elements.outputLabel.textContent = "需要重新確認";
  elements.deviceStatus.textContent = "音訊裝置已變更，請重新檢查。";
  elements.recordingStatus.textContent = "等待裝置重新確認。";
  if (state.recorder && state.recorder.state !== "inactive") {
    state.discardRecording = true;
    clearRecordingTimers();
    state.recorder.stop();
    stopTracks(state.stream);
    state.stream = null;
  }
  setPhase("unchecked");
}

elements.checkDevices.addEventListener("click", checkDevices);
elements.start.addEventListener("click", startRecording);
elements.stop.addEventListener("click", stopRecording);
elements.copy.addEventListener("click", () => copyCorrectedText());
if (navigator.mediaDevices?.addEventListener) {
  navigator.mediaDevices.addEventListener("devicechange", invalidateDevices);
}

renderControls();
checkGateway();
