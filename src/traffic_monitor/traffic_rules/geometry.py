"""Pure Python 2D geometry functions for traffic rule detection.
Zero external dependency.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple


def point_in_polygon(point: List[int] | Tuple[int, int], polygon: List[List[int]]) -> bool:
    """Ray casting algorithm to determine if a point is inside a polygon.
    Returns True if inside or on boundary, False otherwise.
    """
    if len(polygon) < 3:
        return False
    x, y = point[0], point[1]
    inside = False
    for i, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(i + 1) % len(polygon)]
        cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
        if (cross == 0 and min(x1, x2) <= x <= max(x1, x2)
                and min(y1, y2) <= y <= max(y1, y2)):
            return True
        if (y1 > y) != (y2 > y):
            x_intersection = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_intersection:
                inside = not inside
    return inside


def _ccw(A: Tuple[float, float], B: Tuple[float, float], C: Tuple[float, float]) -> bool:
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])


def line_segment_intersection(
    p1: List[int] | Tuple[float, float],
    p2: List[int] | Tuple[float, float],
    p3: List[int] | Tuple[float, float],
    p4: List[int] | Tuple[float, float],
) -> bool:
    """Check if segment (p1, p2) intersects segment (p3, p4)."""
    A = (float(p1[0]), float(p1[1]))
    B = (float(p2[0]), float(p2[1]))
    C = (float(p3[0]), float(p3[1]))
    D = (float(p4[0]), float(p4[1]))
    return _ccw(A, C, D) != _ccw(B, C, D) and _ccw(A, B, C) != _ccw(A, B, D)


def segment_intersection_fraction(
    p1: List[int] | Tuple[float, float],
    p2: List[int] | Tuple[float, float],
    q1: List[int] | Tuple[float, float],
    q2: List[int] | Tuple[float, float],
) -> Optional[float]:
    """Return where p1->p2 meets q1->q2, as a fraction of the first segment."""
    rx, ry = p2[0] - p1[0], p2[1] - p1[1]
    sx, sy = q2[0] - q1[0], q2[1] - q1[1]
    denominator = rx * sy - ry * sx
    if abs(denominator) < 1e-9 or (rx == 0 and ry == 0):
        return None
    dx, dy = q1[0] - p1[0], q1[1] - p1[1]
    t = (dx * sy - dy * sx) / denominator
    u = (dx * ry - dy * rx) / denominator
    if 0 <= t <= 1 and 0 <= u <= 1:
        return t
    return None


def point_to_segment_distance(
    p: List[int] | Tuple[float, float],
    a: List[int] | Tuple[float, float],
    b: List[int] | Tuple[float, float],
) -> float:
    """Perpendicular distance from point p to line segment (a, b)."""
    px, py = float(p[0]), float(p[1])
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])

    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)

    # Project point onto segment
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def vector_angle_degrees(v1: Tuple[float, float] | List[float], v2: Tuple[float, float] | List[float]) -> float:
    """Compute the angle in degrees [0, 180] between two 2D vectors."""
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    mag1 = math.hypot(v1[0], v1[1])
    mag2 = math.hypot(v2[0], v2[1])
    if mag1 < 1e-6 or mag2 < 1e-6:
        return 0.0
    cos_theta = max(-1.0, min(1.0, dot / (mag1 * mag2)))
    return math.degrees(math.acos(cos_theta))


def scale_point(
    pt: List[int] | Tuple[int, int],
    from_size: List[int] | Tuple[int, int],
    to_size: List[int] | Tuple[int, int],
) -> List[int]:
    """Scale a point from one resolution space to another."""
    if from_size[0] <= 0 or from_size[1] <= 0:
        return [int(pt[0]), int(pt[1])]
    scale_x = to_size[0] / from_size[0]
    scale_y = to_size[1] / from_size[1]
    return [int(pt[0] * scale_x), int(pt[1] * scale_y)]


def scale_bbox(
    bbox: List[int],
    from_size: List[int] | Tuple[int, int],
    to_size: List[int] | Tuple[int, int],
) -> List[int]:
    """Scale bounding box [x1, y1, x2, y2] to target size."""
    if from_size[0] <= 0 or from_size[1] <= 0:
        return list(bbox)
    scale_x = to_size[0] / from_size[0]
    scale_y = to_size[1] / from_size[1]
    return [
        int(bbox[0] * scale_x),
        int(bbox[1] * scale_y),
        int(bbox[2] * scale_x),
        int(bbox[3] * scale_y),
    ]
