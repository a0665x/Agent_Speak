"use strict";

(function expose(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.AgentSpeakCodexRecorder = api;
}(typeof globalThis === "object" ? globalThis : this, function buildCore() {
  const TARGET = "zone vibe 100";

  function normalizeDeviceLabel(label) {
    return String(label || "").trim().toLowerCase().replace(/\s+/g, " ");
  }

  function findZoneVibeDevices(devices) {
    const list = Array.from(devices || []);
    const match = (kind) => list.find(
      (device) => device.kind === kind && normalizeDeviceLabel(device.label).includes(TARGET),
    ) || null;
    return { input: match("audioinput"), output: match("audiooutput") };
  }

  function hasRequiredDevices(pair) {
    return Boolean(pair && pair.input && pair.output);
  }

  function controlsForState(state, devicesReady) {
    return {
      checkDisabled: state === "checking" || state === "recording" || state === "processing",
      startDisabled: state !== "ready" || !devicesReady,
      stopDisabled: state !== "recording",
    };
  }

  function formatTimer(seconds) {
    const bounded = Math.max(0, Math.min(30, Math.floor(Number(seconds) || 0)));
    return `00:${String(bounded).padStart(2, "0")} / 00:30`;
  }

  return { normalizeDeviceLabel, findZoneVibeDevices, hasRequiredDevices, controlsForState, formatTimer };
}));
