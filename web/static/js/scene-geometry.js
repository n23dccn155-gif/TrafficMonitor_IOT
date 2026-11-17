/* Geometry generated from road outlines, center lines and approach stop lines. */
const SceneGeometry = (() => {
  const EPS = 1e-6;
  const cross = (a, b, p) => (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);
  const area = (poly) => Math.abs(poly.reduce((sum, p, i) => {
    const q = poly[(i + 1) % poly.length];
    return sum + p[0] * q[1] - q[0] * p[1];
  }, 0)) / 2;
  const midpoint = (line) => {
    const first = line[0], last = line[line.length - 1];
    return [(first[0] + last[0]) / 2, (first[1] + last[1]) / 2];
  };
  const rounded = (poly) => poly.map((p) => p.map(Math.round));

  function rayBoundaryHit(origin, direction, polygon) {
    let nearest = null;
    for (let i = 0; i < polygon.length; i++) {
      const a = polygon[i], b = polygon[(i + 1) % polygon.length];
      const edge = [b[0] - a[0], b[1] - a[1]];
      const denominator = direction[0] * edge[1] - direction[1] * edge[0];
      if (Math.abs(denominator) < EPS) continue;
      const delta = [a[0] - origin[0], a[1] - origin[1]];
      const distance = (delta[0] * edge[1] - delta[1] * edge[0]) / denominator;
      const fraction = (delta[0] * direction[1] - delta[1] * direction[0]) / denominator;
      if (distance < -EPS || fraction < -EPS || fraction > 1 + EPS) continue;
      if (!nearest || distance < nearest.distance) {
        nearest = {
          edge: i, distance,
          point: [origin[0] + distance * direction[0], origin[1] + distance * direction[1]],
        };
      }
    }
    return nearest;
  }

  function polygonArc(polygon, start, end) {
    const arc = [start.point];
    let vertex = (start.edge + 1) % polygon.length;
    for (let count = 0; count < polygon.length; count++) {
      arc.push(polygon[vertex]);
      if (vertex === end.edge) {
        arc.push(end.point);
        return arc;
      }
      vertex = (vertex + 1) % polygon.length;
    }
    return [];
  }

  function splitPolygonAlongPolyline(polygon, line) {
    if (line.some((point) => !pointInPolygon(point, polygon))) return null;
    const startDirection = [line[0][0] - line[1][0], line[0][1] - line[1][1]];
    const last = line.length - 1;
    const endDirection = [line[last][0] - line[last - 1][0], line[last][1] - line[last - 1][1]];
    const start = rayBoundaryHit(line[0], startDirection, polygon);
    const end = rayBoundaryHit(line[last], endDirection, polygon);
    if (!start || !end || start.edge === end.edge ||
        Math.hypot(start.point[0] - end.point[0], start.point[1] - end.point[1]) < 2) return null;
    const path = [start.point, ...line, end.point];
    const first = polygonArc(polygon, start, end).concat(path.slice(1, -1).reverse());
    const second = polygonArc(polygon, end, start).concat(path.slice(1, -1));
    if (area(first) < 10 || area(second) < 10 ||
        Math.abs(area(first) + area(second) - area(polygon)) > area(polygon) * 0.02) return null;
    return [first, second];
  }

  function segmentIntersection(a, b, c, d) {
    const dx1 = b[0] - a[0], dy1 = b[1] - a[1];
    const dx2 = d[0] - c[0], dy2 = d[1] - c[1];
    const denom = dx1 * dy2 - dy1 * dx2;
    if (Math.abs(denom) < EPS) return null;
    const qx = c[0] - a[0], qy = c[1] - a[1];
    const t = (qx * dy2 - qy * dx2) / denom;
    const u = (qx * dy1 - qy * dx1) / denom;
    if (t < -EPS || t > 1 + EPS || u < -EPS || u > 1 + EPS) return null;
    return [a[0] + t * dx1, a[1] + t * dy1];
  }

  function extendedLineIntersection(first, second) {
    const a = first[0], b = first[first.length - 1];
    const c = second[0], d = second[second.length - 1];
    const dx1 = b[0] - a[0], dy1 = b[1] - a[1];
    const dx2 = d[0] - c[0], dy2 = d[1] - c[1];
    const denom = dx1 * dy2 - dy1 * dx2;
    if (Math.abs(denom) < EPS) return null;
    const t = ((c[0] - a[0]) * dy2 - (c[1] - a[1]) * dx2) / denom;
    return [a[0] + t * dx1, a[1] + t * dy1];
  }

  function centerlineIntersection(a, b) {
    for (let i = 0; i + 1 < a.length; i++) {
      for (let j = 0; j + 1 < b.length; j++) {
        const point = segmentIntersection(a[i], a[i + 1], b[j], b[j + 1]);
        if (point) return point;
      }
    }
    return null;
  }

  function convexHull(points) {
    const sorted = [...new Map(points.map((p) => [`${p[0]},${p[1]}`, p])).values()]
      .sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    if (sorted.length < 3) return [];
    const lower = [], upper = [];
    for (const p of sorted) {
      while (lower.length >= 2 && cross(lower.at(-2), lower.at(-1), p) <= 0) lower.pop();
      lower.push(p);
    }
    for (const p of [...sorted].reverse()) {
      while (upper.length >= 2 && cross(upper.at(-2), upper.at(-1), p) <= 0) upper.pop();
      upper.push(p);
    }
    return lower.slice(0, -1).concat(upper.slice(0, -1));
  }

  function pointInPolygon(point, poly) {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const a = poly[i], b = poly[j];
      if (Math.abs(cross(a, b, point)) < EPS &&
          point[0] >= Math.min(a[0], b[0]) - EPS && point[0] <= Math.max(a[0], b[0]) + EPS &&
          point[1] >= Math.min(a[1], b[1]) - EPS && point[1] <= Math.max(a[1], b[1]) + EPS) return true;
      if (((a[1] > point[1]) !== (b[1] > point[1])) &&
          point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
    }
    return inside;
  }

  function deriveRoad(key, road, center) {
    const polygon = road.road_polygon || [];
    const line = road.center_boundary || [];
    const stops = road.stop_lines || [];
    if (polygon.length < 3) throw new Error(`Đường ${key}: cần vẽ vùng đường ít nhất 3 điểm.`);
    if (line.length < 2) throw new Error(`Đường ${key}: cần vẽ tim đường.`);
    if (stops.length < 2 || stops.some((s) => !s.line || s.line.length < 2)) {
      throw new Error(`Đường ${key}: cần hai vạch dừng ở hai chiều.`);
    }
    const a = line[0], b = line[line.length - 1];
    const axisLength = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (axisLength < 2 || area(polygon) < 10) throw new Error(`Đường ${key}: vùng đường hoặc tim đường quá nhỏ.`);
    const halves = splitPolygonAlongPolyline(polygon, line);
    if (!halves) throw new Error(`Đường ${key}: tim đường phải đi trong vùng đường từ đầu đến cuối để chia hai làn.`);
    const m1 = midpoint(stops[0].line), m2 = midpoint(stops[1].line);
    const sideOf = (point) => {
      const inFirst = pointInPolygon(point, halves[0]);
      const inSecond = pointInPolygon(point, halves[1]);
      return inFirst === inSecond ? -1 : (inFirst ? 0 : 1);
    };
    const side1 = sideOf(m1), side2 = sideOf(m2);
    if (side1 < 0 || side2 < 0 || side1 === side2) {
      throw new Error(`Đường ${key}: hai vạch dừng phải nằm ở hai bên tim đường.`);
    }
    const firstPolygon = halves[side1], secondPolygon = halves[side2];
    const target = center || [(m1[0] + m2[0]) / 2, (m1[1] + m2[1]) / 2];
    const axis = [(b[0] - a[0]) / axisLength, (b[1] - a[1]) / axisLength];
    const toCenter = (m) => (target[0] - m[0]) * axis[0] + (target[1] - m[1]) * axis[1];
    const move1 = toCenter(m1), move2 = toCenter(m2);
    if (Math.abs(move1) < 2 || Math.abs(move2) < 2 || move1 * move2 >= 0) {
      throw new Error(`Đường ${key}: hai vạch dừng phải ở hai phía ngã tư để xác định chiều xe.`);
    }
    const direction = (value) => axis.map((component) => component * Math.sign(value) || 0);
    return [
      { id: `${key}1`, name: `Làn ${key}1`, polygon: rounded(firstPolygon), allowed_direction: direction(move1) },
      { id: `${key}2`, name: `Làn ${key}2`, polygon: rounded(secondPolygon), allowed_direction: direction(move2) },
    ];
  }

  function deriveScene(roads, strict = true) {
    const center = centerlineIntersection(roads.A.center_boundary || [], roads.B.center_boundary || []);
    const regions = {};
    const errors = [];
    for (const key of ["A", "B"]) {
      const road = roads[key];
      if (!(road.road_polygon || []).length) continue; // Existing saved scenes keep their old regions.
      try {
        regions[key] = deriveRoad(key, road, center);
      } catch (error) {
        errors.push(error.message);
      }
    }
    let intersectionPolygon = [];
    const hasAllStops = ["A", "B"].every((key) => (roads[key].stop_lines || []).length >= 2 &&
      roads[key].stop_lines.slice(0, 2).every((stop) => stop.line?.length >= 2));
    if (hasAllStops && roads.A.road_polygon?.length >= 3 && roads.B.road_polygon?.length >= 3) {
      const endpoints = ["A", "B"].flatMap((key) => roads[key].stop_lines.slice(0, 2)
        .flatMap((stop) => stop.line));
      const corners = roads.A.stop_lines.slice(0, 2).flatMap((aStop) =>
        roads.B.stop_lines.slice(0, 2).map((bStop) =>
          extendedLineIntersection(aStop.line, bStop.line)));
      if (corners.every(Boolean)) intersectionPolygon = rounded(convexHull(corners));
      if (!center || area(intersectionPolygon) < 10 ||
          area(intersectionPolygon) > 4 * area(convexHull(endpoints)) ||
          !pointInPolygon(center, intersectionPolygon)) {
        errors.push("Không tạo được vùng ngã tư: kiểm tra vị trí bốn vạch dừng và hai tim đường.");
        intersectionPolygon = [];
      }
    }
    if (strict && errors.length) throw new Error(errors[0]);
    return { regions, intersectionPolygon, errors };
  }

  return { deriveScene, deriveRoad, convexHull, centerlineIntersection, pointInPolygon, area };
})();
if (typeof module !== "undefined") module.exports = SceneGeometry;
