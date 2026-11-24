const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const elements = new Map();
global.document = { getElementById(id) {
  if (!elements.has(id)) {
    const classes = new Set();
    elements.set(id, {
      value: id === "arduinoPort" ? "COM3" : id.endsWith("GreenSec") ? "15" : "3",
      textContent: "", style: {}, classes,
      classList: { add(name) { classes.add(name); }, remove(name) { classes.delete(name); } },
    });
  }
  return elements.get(id);
} };
global.app = { currentStep: 3, selectedSourceType: "live", onSignalPhaseChanged() {} };
global.setInterval = () => 1;
global.clearInterval = () => {};
const actions = [];
global.fetch = async (url, options) => {
  if (url === "/api/signal-timelines/") return { ok: true };
  if (!options) return { ok: true, json: async () => ({
    connected: false, ports: [{ port: "COM7", description: "USB Serial Device" }],
  }) };
  const payload = JSON.parse(options.body);
  actions.push(payload);
  const manual = payload.action === "connect" || payload.action === "manual";
  return { ok: true, json: async () => ({
    connected: true, port: "COM7", phase: manual ? "ALL_RED" : "A_GREEN",
    remaining_ms: manual ? 0 : 5000, mode: manual ? "manual" : "auto",
    a_green: 5, a_yellow: 2, b_green: 5, b_yellow: 2,
  }) };
};
vm.runInThisContext(fs.readFileSync(path.join(__dirname, "../web/static/js/signal.js"), "utf8"));

async function main() {
  const panel = new SignalPanel();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(document.getElementById("arduinoPort").value, "COM7");
  await panel.toggleHardware();
  assert.equal(actions[0].action, "connect");
  assert.deepEqual(actions[1], {
    action: "auto", a_green: 15, a_yellow: 3, b_green: 15, b_yellow: 3,
  });
  assert.equal(panel.currentPhase, "A_GREEN");
  assert.equal(panel.remainingSec, 5);
  assert.equal(panel.hardwareEnabled, true);
  panel.applyHardwareState({
    port: "COM7", phase: "ALL_RED", remaining_ms: 0, mode: "manual",
    a_green: 15, a_yellow: 3, b_green: 15, b_yellow: 3,
  });
  assert.equal(document.getElementById("bulbA_red").classes.has("active"), true);
  assert.equal(document.getElementById("bulbB_red").classes.has("active"), true);

  // Manual BOTH_YELLOW: with the board connected the clicks must reach the Uno.
  const base = actions.length;
  panel.onBulbClick("A", "yellow");
  assert.deepEqual(actions[base], { action: "manual", phase: "A_YELLOW" });
  panel.onBulbClick("B", "yellow");
  assert.deepEqual(actions[base + 1], { action: "manual", phase: "ALL_YELLOW" });

  // Same clicks in web-only mode light both yellow bulbs (and no red bulb).
  panel.hardwareEnabled = false;
  panel.currentPhase = "A_YELLOW";
  panel.onBulbClick("B", "yellow");
  assert.equal(panel.currentPhase, "ALL_YELLOW");
  assert.equal(document.getElementById("bulbA_yellow").classes.has("active"), true);
  assert.equal(document.getElementById("bulbB_yellow").classes.has("active"), true);
  assert.equal(document.getElementById("bulbA_red").classes.has("active"), false);
  assert.equal(document.getElementById("bulbB_red").classes.has("active"), false);
  assert.equal(document.getElementById("bulbA_green").classes.has("active"), false);
  assert.equal(document.getElementById("bulbB_green").classes.has("active"), false);
  // Clicking one yellow again drops back to that road alone.
  panel.onBulbClick("A", "yellow");
  assert.equal(panel.currentPhase, "B_YELLOW");
  // A green click leaves BOTH_YELLOW safely (never two greens).
  panel.setPhase("ALL_YELLOW");
  panel.onBulbClick("A", "green");
  assert.equal(panel.currentPhase, "A_GREEN");
  console.log("Arduino UI connect and automatic timing OK");
  console.log("manual ALL_YELLOW phase OK");
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
