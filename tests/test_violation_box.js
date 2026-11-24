const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

// Mock canvas and 2D rendering context
const strokes = [];
const boxes = [];
const filledRects = [];
const labels = [];
let lastStrokeColor = null;
let lastStrokeWidth = null;
let lastFillColor = null;
let points = [];

const ctx = {
  clearRect() {},
  beginPath() { points = []; },
  moveTo(x, y) { points.push([x, y]); },
  lineTo(x, y) { points.push([x, y]); },
  closePath() {},
  fill() {},
  stroke() {
    strokes.push({ points: [...points], color: this.strokeStyle, lineWidth: this.lineWidth });
  },
  strokeRect(x, y, width, height) {
    boxes.push({ x, y, width, height, color: this.strokeStyle, lineWidth: this.lineWidth });
  },
  fillRect(x, y, width, height) {
    filledRects.push({ x, y, width, height, color: this.fillStyle });
  },
  fillText(value) {
    labels.push({ text: value, fillStyle: this.fillStyle });
  },
  arc() {},
  setLineDash() {},
  measureText() { return { width: 50 }; },
  get strokeStyle() { return lastStrokeColor; },
  set strokeStyle(val) { lastStrokeColor = val; },
  get lineWidth() { return lastStrokeWidth; },
  set lineWidth(val) { lastStrokeWidth = val; },
  get fillStyle() { return lastFillColor; },
  set fillStyle(val) { lastFillColor = val; },
};

const canvas = {
  width: 0,
  height: 0,
  getContext: () => ctx,
  parentElement: { getBoundingClientRect: () => ({ width: 800, height: 600 }) },
};

const video = {
  videoWidth: 640,
  videoHeight: 480,
  currentTime: 0,
  addEventListener() {},
};

const liveImg = { naturalWidth: 640, naturalHeight: 480 };

const domElements = new Map();
global.document = {
  getElementById(id) {
    if (id === "mainVideo") return video;
    if (id === "overlayCanvas") return canvas;
    if (id === "liveMonitorImg") return liveImg;
    if (!domElements.has(id)) {
      const classes = new Set();
      domElements.set(id, {
        id,
        textContent: "",
        style: {},
        classes,
        classList: {
          add(name) { classes.add(name); },
          remove(name) { classes.delete(name); },
        },
      });
    }
    return domElements.get(id);
  },
  querySelectorAll() { return []; },
};

global.window = { addEventListener() {} };
global.requestAnimationFrame = () => {};

// Load events.js and player.js into VM context
vm.runInThisContext(fs.readFileSync(path.join(__dirname, "../web/static/js/events.js"), "utf8"));
vm.runInThisContext(fs.readFileSync(path.join(__dirname, "../web/static/js/player.js"), "utf8"));

async function main() {
  // 1. Assert violationRuleLabel translations
  assert.equal(violationRuleLabel("wrong_way"), "Ngược Chiều");
  assert.equal(violationRuleLabel("lane_encroachment"), "Lấn Vạch");
  assert.equal(violationRuleLabel("red_light"), "Vượt Đèn Đỏ");
  assert.equal(violationRuleLabel("unknown"), "Vượt Đèn Đỏ");

  const player = new VideoCanvasPlayer("mainVideo", "overlayCanvas");
  player.resizeCanvas();
  player.setLiveMode(true);
  player.setLiveMediaSize(640, 480);

  const eventsManager = new ViolationEventsManager(player);

  // 2. Normal vehicle without violation -> green box, 2px lineWidth, normal label
  boxes.length = 0;
  labels.length = 0;
  player.setLiveFrame({
    processing_size: [320, 240],
    video_timestamp_ms: 1000,
    tracks: [{ track_id: 10, vehicle_type: "car", bbox_xyxy: [32, 24, 64, 48] }],
  });

  const normalBox = boxes.at(-1);
  assert.equal(normalBox.color, "#10b981", "Normal car must have green box (#10b981)");
  assert.equal(normalBox.lineWidth, 2, "Normal car must have 2px lineWidth");
  assert.equal(labels.at(-1).text, "ID:10 car", "Normal car must display ID:10 car without violation suffix");

  // 3. Car with violation -> red box (#ef4444), lineWidth 3, red badge and error name
  eventsManager.events = [
    {
      event_id: "ev1",
      track_id: 12,
      vehicle_type: "car",
      rule_type: "red_light",
      event_timestamp_ms: 1000,
      review_status: "pending",
    },
  ];
  player.violationEvents = eventsManager.events;

  boxes.length = 0;
  labels.length = 0;
  strokes.length = 0;
  player.setLiveFrame({
    processing_size: [320, 240],
    video_timestamp_ms: 1200,
    tracks: [{
      track_id: 12,
      vehicle_type: "car",
      bbox_xyxy: [32, 24, 64, 48],
      trajectory_xy: [[32, 24], [64, 48]],
    }],
  });

  const violBox = boxes.at(-1);
  assert.equal(violBox.color, "#ef4444", "Violating car box must be red (#ef4444)");
  assert.equal(violBox.lineWidth, 3, "Violating car box must have lineWidth 3");
  assert.equal(labels.at(-1).text, "ID:12 car · Vượt Đèn Đỏ", "Badge label must contain violation text");
  assert.equal(strokes.at(-1).color, "#ef4444", "Trajectory line must be red for violating car");

  // 4. Before violation occurred (nowMs < event_timestamp_ms) -> remains green
  boxes.length = 0;
  labels.length = 0;
  player.setLiveFrame({
    processing_size: [320, 240],
    video_timestamp_ms: 800,
    tracks: [{ track_id: 12, vehicle_type: "car", bbox_xyxy: [32, 24, 64, 48] }],
  });

  const beforeBox = boxes.at(-1);
  assert.equal(beforeBox.color, "#10b981", "Before violation timestamp, box should remain green");
  assert.equal(beforeBox.lineWidth, 2);
  assert.equal(labels.at(-1).text, "ID:12 car");

  // 5. Dismissed event -> does not turn red
  eventsManager.events = [
    {
      event_id: "ev2",
      track_id: 15,
      vehicle_type: "car",
      rule_type: "wrong_way",
      event_timestamp_ms: 1000,
      review_status: "dismissed",
    },
  ];
  player.violationEvents = eventsManager.events;

  boxes.length = 0;
  labels.length = 0;
  player.setLiveFrame({
    processing_size: [320, 240],
    video_timestamp_ms: 1500,
    tracks: [{ track_id: 15, vehicle_type: "car", bbox_xyxy: [32, 24, 64, 48] }],
  });

  const dismissedBox = boxes.at(-1);
  assert.equal(dismissedBox.color, "#10b981", "Dismissed violation must not turn box red");
  assert.equal(dismissedBox.lineWidth, 2);
  assert.equal(labels.at(-1).text, "ID:15 car");

  // 6. Motion track is skipped from violation logic
  player.setLiveMode(false);
  player.currentRunId = "test_run";
  eventsManager.events = [
    {
      event_id: "ev3",
      track_id: 99,
      rule_type: "red_light",
      event_timestamp_ms: 1000,
      review_status: "pending",
    },
  ];
  player.violationEvents = eventsManager.events;
  boxes.length = 0;
  labels.length = 0;
  player.trackFrames.set(1200, {
    processing_size: [320, 240],
    tracks: [{
      track_id: 99,
      track_source: "techgar",
      vehicle_type: "vehicle",
      observation_kind: "detection",
      bbox_xyxy: [32, 24, 64, 48],
    }],
  });
  player.video.currentTime = 1.2;
  player._renderOverlay();
  const motionBox = boxes.at(-1);
  assert.equal(motionBox.color, "#ef4444", "TechGAR track shows its violation in red");

  // 7. Reset clears violationEvents
  eventsManager.reset();
  assert.deepEqual(player.violationEvents, [], "reset() must clear player.violationEvents");

  console.log("violation box red and label badge tests OK");
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
