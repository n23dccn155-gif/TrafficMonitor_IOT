const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const select = { options: [], add(option) { this.options.push(option); } };
global.document = {
  addEventListener() {},
  getElementById(id) { return id === "trackingRunSelect" ? select : null; },
};
global.Option = class { constructor(text, value) { this.text = text; this.value = value; } };
let runs = [];
global.fetch = async () => ({ ok: true, json: async () => ({ runs }) });
vm.runInThisContext(fs.readFileSync(path.join(__dirname, "../web/static/js/app.js"), "utf8"));

async function main() {
  const application = new Application();
  application.currentVideo = "vd1.mp4";
  runs = [
    { run_id: "older_techgar", algorithm: "techgar", complete: true, processed_frames: 100, source_frames: 100 },
    { run_id: "newer_legacy", algorithm: "2", complete: true, processed_frames: 100, source_frames: 100 },
  ];
  await application.loadTrackingRuns();
  assert.equal(application.currentTrackingRunId, "older_techgar");
  assert.equal(select.options.length, 1);

  runs = [runs[1]];
  select.options = [];
  await application.loadTrackingRuns();
  assert.equal(application.currentTrackingRunId, null);
  assert.match(select.options[0].text, /Chưa có bản TechGAR đầy đủ/);
  console.log("MP4 defaults to a complete TechGAR run OK");
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
