"use strict";

const assert = require("node:assert/strict");
const core = require("../web/codex-recorder-core.js");

const devices = [
  { kind: "audioinput", deviceId: "mic-zone", label: "Logitech Zone Vibe 100 Hands-Free" },
  { kind: "audiooutput", deviceId: "speaker-zone", label: "Zone Vibe 100" },
  { kind: "audioinput", deviceId: "laptop", label: "Built-in Audio" },
];

assert.deepEqual(core.findZoneVibeDevices(devices), {
  input: devices[0],
  output: devices[1],
});
assert.deepEqual(core.findZoneVibeDevices(devices.slice(0, 1)), {
  input: devices[0],
  output: null,
});
assert.equal(core.hasRequiredDevices(core.findZoneVibeDevices(devices)), true);
assert.equal(core.hasRequiredDevices(core.findZoneVibeDevices(devices.slice(0, 1))), false);
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
