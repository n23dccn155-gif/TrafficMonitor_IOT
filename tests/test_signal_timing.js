const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const elements = new Map();
global.document = { getElementById(id) {
  if (!elements.has(id)) elements.set(id, {
    value: id.endsWith("GreenSec") ? "15" : "3",
    style: {}, classList: { add() {}, remove() {} },
  });
  return elements.get(id);
} };
global.app = { currentStep: 3, selectedSourceType: "mp4",
  player: { video: { currentTime: 0, duration: 100 } }, onSignalPhaseChanged() {} };
global.setInterval = () => 1;
global.clearInterval = () => {};
let savedTimeline;
global.fetch = async (_url, options) => {
  if (!options) return { ok: true, json: async () => ({ connected: false }) };
  savedTimeline = JSON.parse(options.body);
  return { ok: true };
};
vm.runInThisContext(fs.readFileSync(path.join(__dirname, "../web/static/js/signal.js"), "utf8"));

async function main() {
  const panel = new SignalPanel();
  assert.equal(savedTimeline, undefined);
  assert.equal(panel.currentPhase, "A_GREEN");
  panel._advanceToNextPhase();
  assert.equal(panel.currentPhase, "A_YELLOW");
  panel._advanceToNextPhase();
  assert.equal(panel.currentPhase, "B_GREEN");
  panel._advanceToNextPhase();
  assert.equal(panel.currentPhase, "B_YELLOW");
  panel._advanceToNextPhase();
  assert.equal(panel.currentPhase, "A_GREEN");

  panel.setMode("manual");
  app.player.video.currentTime = 10;
  panel.setPhase("B_GREEN");
  app.player.video.currentTime = 30;
  assert.equal(panel.currentPhase, "B_GREEN");
  assert.equal(savedTimeline, undefined);
  console.log("independent signal cycle and manual control OK");
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
