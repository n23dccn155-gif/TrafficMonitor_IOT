const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const strokes = [];
const boxes = [];
const labels = [];
let clears = 0;
let points = [];
const ctx = {
  clearRect() { clears++; }, beginPath() { points = []; },
  moveTo(x, y) { points.push([x, y]); },
  lineTo(x, y) { points.push([x, y]); },
  closePath() {}, fill() {},
  stroke() { strokes.push({ points, color: this.strokeStyle }); },
  strokeRect(x, y, width, height) { boxes.push([x, y, width, height]); },
  fillRect() {}, fillText(value) { labels.push(value); }, arc() {}, setLineDash() {},
  measureText() { return { width: 20 }; },
};
const canvas = { width: 0, height: 0, getContext: () => ctx,
  parentElement: { getBoundingClientRect: () => ({ width: 800, height: 600 }) } };
const video = { videoWidth: 640, videoHeight: 480, currentTime: 0,
  addEventListener() {} };
const liveImg = { naturalWidth: 640, naturalHeight: 480 };
global.document = { getElementById(id) {
  return { mainVideo: video, overlayCanvas: canvas, liveMonitorImg: liveImg }[id];
} };
global.window = { addEventListener() {} };
global.requestAnimationFrame = () => {};
vm.runInThisContext(fs.readFileSync(path.join(__dirname, "../web/static/js/player.js"), "utf8"));

const player = new VideoCanvasPlayer("mainVideo", "overlayCanvas");
player.resizeCanvas();
player.setLiveMode(true);
player.setScene({
  reference_size: [1280, 960],
  roads: { A: { center_boundary: [[0, 0], [1280, 960]], stop_lines: [], direction_regions: [] } },
});
player._renderOverlay();
assert.deepEqual(strokes[0].points, [[0, 0], [800, 600]]);
assert.match(strokes[0].color, /0\.5\)/);
player.setLiveFrame({ processing_size: [320, 240], tracks: [{
  track_id: 1, vehicle_type: "car", bbox_xyxy: [32, 24, 64, 48],
}] });
assert.deepEqual(boxes.at(-1), [80, 60, 80, 60]);
const boxesBeforeMotion = boxes.length;
player.setLiveFrame({ processing_size: [320, 240], tracks: [{
  track_id: -2, track_source: "motion", vehicle_type: "motion_candidate",
  observation_kind: "detection", bbox_xyxy: [32, 24, 64, 48],
}] });
assert.equal(boxes.length, boxesBeforeMotion);
player.setLiveFrame({ processing_size: [320, 240], tracks: [], yolo_detections: [{
  vehicle_type: "car", class_confidence: 0.82, bbox_xyxy: [32, 24, 64, 48],
}] });
assert.deepEqual(boxes.at(-1), [80, 60, 80, 60]);
assert.ok(labels.some((label) => label.includes("YOLO car 82%")));
player.setLiveMediaSize(640, 480);
liveImg.naturalWidth = 0;
liveImg.naturalHeight = 0;
player.setLiveFrame({ frame_index: 7, segment_id: "seg0", processing_size: [320, 240], tracks: [] });
assert.deepEqual(strokes.at(-1).points, [[0, 0], [800, 600]]);
const clearsBefore = clears;
player.setLiveFrame({ frame_index: 7, segment_id: "seg0", processing_size: [320, 240], tracks: [] });
player.resizeCanvas();
assert.equal(clears, clearsBefore);
console.log("live overlay mapping, opacity and detection boxes OK");
