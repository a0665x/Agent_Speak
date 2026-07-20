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

async function processRecording() {
  if (state.discardRecording) {
    state.discardRecording = false;
    state.chunks = [];
    return;
  }
  elements.recordingStatus.textContent = "錄音已結束，準備處理音訊。";
  setPhase(hasRequiredDevices(state.devices) ? "ready" : "unchecked");
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
if (navigator.mediaDevices?.addEventListener) {
  navigator.mediaDevices.addEventListener("devicechange", invalidateDevices);
}

renderControls();
checkGateway();
