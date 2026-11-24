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
// Manual transitions use setTimeout + Date.now; fake both and fire timers by hand.
let now = 0;
Date.now = () => now;
let timers = [];
global.setTimeout = (fn, ms) => { timers.push({ fn, ms }); return timers.length; };
global.clearTimeout = () => { timers = []; };
const fireTimer = () => { const t = timers.shift(); now += t.ms; t.fn(); return t.ms; };
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

  // Timed cycle: 6 phases, ALL_RED 3 s after each direction.
  const seen = [];
  for (let i = 0; i < 6; i++) {
    panel._advanceToNextPhase();
    seen.push([panel.currentPhase, panel.remainingSec]);
  }
  assert.deepEqual(seen, [
    ["A_YELLOW", 3], ["ALL_RED", 3], ["B_GREEN", 15], ["B_YELLOW", 3], ["ALL_RED", 3], ["A_GREEN", 15],
  ]);

  // Red countdown includes yellow + ALL_RED; in ALL_RED the next road counts down first.
  panel.setPhase("A_GREEN", 10);
  assert.equal(document.getElementById("bulbB_red_count").textContent, "16");
  panel._advanceToNextPhase(); // A_YELLOW 3
  assert.equal(document.getElementById("bulbB_red_count").textContent, "6");
  panel._advanceToNextPhase(); // ALL_RED 3, B goes next
  assert.equal(document.getElementById("bulbB_red_count").textContent, "3");
  assert.equal(document.getElementById("bulbA_red_count").textContent, String(3 + 15 + 3 + 3));

  // Video sync lands on the ALL_RED gaps (15+3 .. 21 s and 39 .. 42 s).
  panel.syncToVideoTime(19);
  assert.equal(panel.currentPhase, "ALL_RED");
  panel.syncToVideoTime(22);
  assert.equal(panel.currentPhase, "B_GREEN");
  panel.syncToVideoTime(40);
  assert.equal(panel.currentPhase, "ALL_RED");
  // Seeking straight into the second ALL_RED: A goes next, so A counts down first.
  assert.equal(document.getElementById("bulbA_red_count").textContent, "2");
  assert.equal(document.getElementById("bulbB_red_count").textContent, String(2 + 15 + 3 + 3));
  panel._advanceToNextPhase();
  assert.equal(panel.currentPhase, "A_GREEN");

  // Saved timeline: every green is preceded by a 3 s ALL_RED.
  assert.equal(await panel.saveTimelineToBackend(), true);
  const changes = savedTimeline.changes;
  assert.deepEqual(changes.slice(0, 7).map((c) => c.phase),
    ["A_GREEN", "A_YELLOW", "ALL_RED", "B_GREEN", "B_YELLOW", "ALL_RED", "A_GREEN"]);
  changes.forEach((c, i) => {
    if (i > 0 && c.phase.endsWith("_GREEN")) {
      assert.equal(changes[i - 1].phase, "ALL_RED");
      assert.equal(c.at_video_ms - changes[i - 1].at_video_ms, 3000);
    }
  });
  savedTimeline = undefined;

  // Manual (web only): A green -> click B green runs A yellow -> ALL_RED 3 s -> B green.
  panel.setMode("manual");
  panel.setPhase("A_GREEN");
  panel.onBulbClick("B", "green");
  assert.equal(panel.currentPhase, "A_YELLOW");
  assert.equal(fireTimer(), 3000);
  assert.equal(panel.currentPhase, "ALL_RED");
  // A click during the clearance only retargets it; ALL_RED is not cut short.
  panel.onBulbClick("A", "green");
  assert.equal(panel.currentPhase, "ALL_RED");
  assert.equal(fireTimer(), 3000);
  assert.equal(panel.currentPhase, "A_GREEN");
  assert.equal(timers.length, 0);

  // ALL_RED button from green goes through yellow first.
  panel.requestPhase("ALL_RED");
  assert.equal(panel.currentPhase, "A_YELLOW");
  fireTimer();
  assert.equal(panel.currentPhase, "ALL_RED");

  // ALL_RED reached as the target still holds 3 s before a green click takes effect.
  assert.equal(timers.length, 0);
  now += 1000;
  panel.onBulbClick("B", "green");
  assert.equal(panel.currentPhase, "ALL_RED");
  assert.equal(fireTimer(), 2000);
  assert.equal(panel.currentPhase, "B_GREEN");

  // A second click during the yellow lets the yellow finish (no early ALL_RED).
  panel.onBulbClick("A", "green");
  assert.equal(panel.currentPhase, "B_YELLOW");
  now += 1000;
  panel.onBulbClick("A", "green");
  assert.equal(panel.currentPhase, "B_YELLOW");
  assert.equal(fireTimer(), 2000);
  assert.equal(panel.currentPhase, "ALL_RED");
  // Retarget to ALL_RED during the clearance, then green: still the full 3 s from ALL_RED start.
  panel.requestPhase("ALL_RED");
  assert.equal(panel.currentPhase, "ALL_RED");
  panel.onBulbClick("B", "green");
  assert.equal(panel.currentPhase, "ALL_RED");
  assert.equal(fireTimer(), 3000);
  assert.equal(panel.currentPhase, "B_GREEN");

  // Timed cycle in ALL_RED -> switch to manual -> green click still waits for the clearance.
  panel.setMode("timed");
  panel.syncToVideoTime(19); // 1 s into the first ALL_RED
  assert.equal(panel.currentPhase, "ALL_RED");
  panel.setMode("manual");
  panel.onBulbClick("B", "green");
  assert.equal(panel.currentPhase, "ALL_RED");
  assert.equal(fireTimer(), 2000);
  assert.equal(panel.currentPhase, "B_GREEN");

  // "Áp dụng chu kỳ"/back to timed while B is green goes through B yellow, not straight to A.
  panel.setMode("timed");
  assert.equal(panel.currentPhase, "B_YELLOW");
  assert.equal(panel.remainingSec, 3);
  panel.setMode("manual");

  // Re-clicking the active manual tab mid-transition keeps the pending target.
  panel.onBulbClick("A", "green");
  assert.equal(panel.currentPhase, "B_YELLOW");
  panel.setMode("manual");
  assert.equal(timers.length, 1);
  fireTimer();
  fireTimer();
  assert.equal(panel.currentPhase, "A_GREEN");

  // Unknown state (e.g. after USB loss) -> green also clears first.
  panel.setPhase("UNKNOWN");
  panel.onBulbClick("A", "green");
  assert.equal(panel.currentPhase, "ALL_RED");
  fireTimer();
  assert.equal(panel.currentPhase, "A_GREEN");

  app.player.video.currentTime = 10;
  panel.setPhase("B_GREEN");
  app.player.video.currentTime = 30;
  assert.equal(panel.currentPhase, "B_GREEN");
  assert.equal(savedTimeline, undefined);
  console.log("signal cycle with 3 s ALL_RED and safe manual control OK");
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
