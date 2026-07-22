"use strict";

const assert = require("node:assert/strict");
const core = require("../web/codex-recorder-core.js");

const devices = [
  { kind: "audioinput", deviceId: "usb", label: "USB microphone" },
  { kind: "audioinput", deviceId: "default", label: "Default Bluetooth microphone" },
  { kind: "audiooutput", deviceId: "default", label: "Default Bluetooth audio" },
  { kind: "audioinput", deviceId: "laptop", label: "Built-in Audio" },
];

assert.deepEqual(core.findDefaultAudioDevices(devices), {
  input: devices[1],
  output: devices[2],
});
assert.deepEqual(core.findDefaultAudioDevices([devices[0]]), {
  input: devices[0],
  output: null,
});
assert.equal(core.hasRequiredDevices(core.findDefaultAudioDevices(devices)), true);
assert.equal(core.hasRequiredDevices(core.findDefaultAudioDevices([devices[0]])), false);
assert.deepEqual(core.controlsForState("unchecked", false), {
  checkDisabled: false,
  startDisabled: true,
  stopDisabled: true,
});
assert.deepEqual(core.controlsForState("ready", true), {
  checkDisabled: false,
  startDisabled: false,
  stopDisabled: true,
});
assert.deepEqual(core.controlsForState("recording", true), {
  checkDisabled: true,
  startDisabled: true,
  stopDisabled: false,
});
assert.deepEqual(core.controlsForState("processing", true), {
  checkDisabled: true,
  startDisabled: true,
  stopDisabled: true,
});
assert.equal(core.formatTimer(7), "00:07 / 00:30");
assert.equal(core.formatTimer(30), "00:30 / 00:30");

console.log("CODEX_RECORDER_CORE_TESTS_OK");
