const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const SceneGeometry = require("../web/static/js/scene-geometry.js");

const roads = {
  A: {
    road_polygon: [[400, 0], [740, 0], [740, 720], [400, 720]],
    center_boundary: [[570, 0], [570, 720]],
    stop_lines: [
      { id: "stop_A1", line: [[444, 124], [566, 124]] },
      { id: "stop_A2", line: [[586, 339], [715, 339]] },
    ],
  },
  B: {
    road_polygon: [[100, 100], [1100, 100], [1100, 350], [100, 350]],
    center_boundary: [[100, 230], [1100, 230]],
    stop_lines: [
      { id: "stop_B1", line: [[721, 123], [728, 212]] },
      { id: "stop_B2", line: [[420, 254], [421, 344]] },
    ],
  },
};

const result = SceneGeometry.deriveScene(roads);
assert.equal(result.regions.A.length, 2);
assert.equal(result.regions.B.length, 2);
assert.deepEqual(result.regions.A[0].allowed_direction, [0, 1]);
assert.deepEqual(result.regions.A[1].allowed_direction, [0, -1]);
assert.deepEqual(result.regions.B[0].allowed_direction, [-1, 0]);
assert.deepEqual(result.regions.B[1].allowed_direction, [1, 0]);
assert.equal(
  SceneGeometry.area(result.regions.A[0].polygon) + SceneGeometry.area(result.regions.A[1].polygon),
  SceneGeometry.area(roads.A.road_polygon),
);
assert.ok(result.intersectionPolygon.length >= 4);
assert.ok(SceneGeometry.area(result.intersectionPolygon) > 10000);
assert.ok(Math.min(...result.intersectionPolygon.map((p) => p[0])) < 425);
assert.ok(Math.max(...result.intersectionPolygon.map((p) => p[0])) > 725);

const curved = {
  road_polygon: [[0, 0], [100, 0], [100, 100], [0, 100]],
  center_boundary: [[50, 10], [55, 40], [60, 60], [50, 90]],
  stop_lines: [
    { id: "stop_A1", line: [[10, 20], [40, 20]] },
    { id: "stop_A2", line: [[65, 80], [95, 80]] },
  ],
};
const curvedRegions = SceneGeometry.deriveRoad("A", curved, [55, 50]);
assert.ok(SceneGeometry.pointInPolygon([53, 50], curvedRegions[0].polygon));
assert.ok(SceneGeometry.pointInPolygon([58, 50], curvedRegions[1].polygon));
assert.equal(
  SceneGeometry.area(curvedRegions[0].polygon) + SceneGeometry.area(curvedRegions[1].polygon),
  SceneGeometry.area(curved.road_polygon),
);

const invalid = structuredClone(roads);
invalid.A.stop_lines[1].line = [[600, 339], [700, 339]];
invalid.A.stop_lines[0].line = [[600, 124], [700, 124]];
assert.throws(() => SceneGeometry.deriveScene(invalid), /hai bên tim đường/);
const parallelStops = structuredClone(roads);
parallelStops.B.stop_lines[0].line = [[721, 123], [820, 123]];
parallelStops.B.stop_lines[1].line = [[420, 344], [520, 344]];
assert.throws(() => SceneGeometry.deriveScene(parallelStops), /Không tạo được vùng ngã tư/);
const legacy = structuredClone(roads);
delete legacy.A.road_polygon;
delete legacy.B.road_polygon;
assert.deepEqual(SceneGeometry.deriveScene(legacy).regions, {});
global.SceneGeometry = SceneGeometry;
global.document = { getElementById: () => null, querySelectorAll: () => [] };
global.window = { addEventListener() {} };
vm.runInThisContext(fs.readFileSync(path.join(__dirname, "../web/static/js/editor.js"), "utf8"));
const editor = new RoadConventionEditor("missing");
editor.geometry.roads = structuredClone(roads);
editor._recomputeDerivedGeometry(true);
assert.equal(editor.geometry.roads.B.direction_regions[0].id, "B1");
assert.ok(editor.geometry.intersection_polygon.length >= 4);
console.log("automatic road split, directions and intersection geometry OK");
