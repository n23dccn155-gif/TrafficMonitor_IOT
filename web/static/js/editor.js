/**
 * Road Convention Canvas Editor (Biên tập quy ước ngã tư).
 * Operates on frozen Frame 0s.
 * Draw a road outline, its center line and two stop lines; derive lanes and intersection.
 * Workflow: Pick tool -> Click N points -> Click "✓ Lưu Phần Này" -> Repeat -> Click "💾 Lưu Toàn Bộ & Giám Sát".
 */
class RoadConventionEditor {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas ? this.canvas.getContext("2d") : null;

    this.snapshotImage = null;
    this.currentTool = "road_A";
    this.referenceSize = [1912, 906];
    this.currentVideoFilename = "vd3.mp4";
    this.snapshotMs = 0;

    // Working geometry layers
    this.geometry = {
      roads: {
        A: {
          name: "Đường A",
          signal_group: "A",
          road_polygon: [],
          center_boundary: [],
          direction_regions: [
            { id: "A1", name: "A1 (Xuống)", polygon: [], allowed_direction: [0, 1] },
            { id: "A2", name: "A2 (Lên)", polygon: [], allowed_direction: [0, -1] },
          ],
          stop_lines: [
            { id: "stop_A1", direction_region_id: "A1", line: [] },
            { id: "stop_A2", direction_region_id: "A2", line: [] },
          ],
        },
        B: {
          name: "Đường B",
          signal_group: "B",
          road_polygon: [],
          center_boundary: [],
          direction_regions: [
            { id: "B1", name: "B1 (Sang phải)", polygon: [], allowed_direction: [1, 0] },
            { id: "B2", name: "B2 (Sang trái)", polygon: [], allowed_direction: [-1, 0] },
          ],
          stop_lines: [
            { id: "stop_B1", direction_region_id: "B1", line: [] },
            { id: "stop_B2", direction_region_id: "B2", line: [] },
          ],
        },
      },
      intersection_polygon: [],
    };

    this.activeDrawingPoints = [];
    if (this.canvas) {
      this._bindEvents();
    }
  }

  _bindEvents() {
    this.canvas.addEventListener("click", (e) => this._handleCanvasClick(e));
    window.addEventListener("resize", () => {
      this.resizeCanvas();
      this.render();
    });
  }

  setTool(tool) {
    this.currentTool = tool;
    this.activeDrawingPoints = [];
    this.updateGuide();
    this.render();
  }

  getToolName(tool) {
    const names = {
      road_A: "Toàn bộ Đường A (tự chia theo tim đường)",
      road_B: "Toàn bộ Đường B (tự chia theo tim đường)",
      stop_A1: "Vạch dừng A1 (chiều đi vào ngã tư)",
      stop_A2: "Vạch dừng A2 (chiều đi vào ngã tư)",
      boundary_A: "Vạch Tim Đường A",
      stop_B1: "Vạch dừng B1 (chiều đi vào ngã tư)",
      stop_B2: "Vạch dừng B2 (chiều đi vào ngã tư)",
      boundary_B: "Vạch Tim Đường B",
    };
    return names[tool] || tool;
  }

  updateGuide() {
    const el = document.getElementById("editorGuideText");
    if (!el) return;

    const toolName = this.getToolName(this.currentTool);
    const isPoly = ["road_A", "road_B"].includes(this.currentTool);
    const minReq = isPoly ? 3 : 2;

    let text = `👉 Đang vẽ: <strong>${toolName}</strong>. Hãy click chuột trên ảnh để chấm các điểm (không giới hạn số điểm).`;
    if (toolName.startsWith("Toàn bộ Đường")) {
      text += " Bao cả hai chiều đường; tim đường sẽ tự chia thành hai làn.";
    } else if (this.currentTool.startsWith("boundary_")) {
      text += " Chấm nhiều điểm theo tim đường nếu đường hơi cong; điểm đầu và cuối ở gần hai mép vùng đường.";
    } else if (this.currentTool.startsWith("stop_")) {
      text += " Vạch này nằm trên nửa đường của xe đi vào ngã tư; hai vạch của cùng đường ở hai bên tim.";
    }
    if (this.activeDrawingPoints.length > 0) {
      text += ` <span style="color:#d97706; font-weight:700;">[Đã chấm ${this.activeDrawingPoints.length} điểm]</span>.`;
      if (this.activeDrawingPoints.length >= minReq) {
        text += ` Bấm nút <strong style="color:#16a34a;">[✓ Lưu]</strong> để hoàn tất phần này.`;
      } else {
        text += ` Cần thêm ít nhất ${minReq - this.activeDrawingPoints.length} điểm nữa.`;
      }
    }
    el.innerHTML = text;
  }

  open(videoFilename, timestampMs = 0) {
    if (this.currentVideoFilename !== videoFilename) this.clearAll();
    this.currentVideoFilename = videoFilename;
    this.snapshotMs = timestampMs;
    this.snapshotImage = null;
    this.activeDrawingPoints = [];
    this.updateGuide();
    this.render();
    this.refreshSnapshot();
  }

  refreshSnapshot() {
    const guideEl = document.getElementById("editorGuideText");
    const source = this.currentVideoFilename;
    const requestId = this.snapshotRequestId = (this.snapshotRequestId || 0) + 1;
    if (guideEl) {
      guideEl.innerHTML = `<span style="color:#2563eb; font-weight:700;">📸 Đang lấy khung hình mới nhất từ ${this.currentVideoFilename}...</span>`;
    }

    const img = new Image();
    img.crossOrigin = "anonymous";
    const cacheBuster = Date.now() + "_" + Math.random().toString(36).substring(2, 7);

    img.onload = () => {
      if (requestId !== this.snapshotRequestId || source !== this.currentVideoFilename) return;
      this.snapshotImage = img;
      this.referenceSize = [img.naturalWidth || 1912, img.naturalHeight || 906];
      this.resizeCanvas();
      this.render();
      this.updateGuide();
    };

    img.onerror = () => {
      if (requestId !== this.snapshotRequestId || source !== this.currentVideoFilename) return;
      console.warn("Could not load snapshot for " + this.currentVideoFilename);
      if (guideEl) {
        guideEl.innerHTML = `<span style="color:#dc2626; font-weight:700;">⚠️ Chưa lấy được ảnh từ Camera/Video. Bấm [📸 Chụp lại ảnh] để thử lại.</span>`;
      }
    };

    img.src = `/api/videos/${encodeURIComponent(this.currentVideoFilename)}/snapshot/?at_ms=${this.snapshotMs}&_t=${cacheBuster}&fresh=1`;
  }

  resizeCanvas() {
    if (!this.canvas) return;
    const container = this.canvas.parentElement;
    if (container) {
      this.canvas.width = container.clientWidth || 800;
      this.canvas.height = container.clientHeight || 500;
      this.render();
    }
  }

  clearAll() {
    this.currentTool = "road_A";
    this.geometry = {
      roads: {
        A: {
          name: "Đường A",
          signal_group: "A",
          road_polygon: [],
          center_boundary: [],
          direction_regions: [
            { id: "A1", name: "A1 (Xuống)", polygon: [], allowed_direction: [0, 1] },
            { id: "A2", name: "A2 (Lên)", polygon: [], allowed_direction: [0, -1] },
          ],
          stop_lines: [
            { id: "stop_A1", direction_region_id: "A1", line: [] },
            { id: "stop_A2", direction_region_id: "A2", line: [] },
          ],
        },
        B: {
          name: "Đường B",
          signal_group: "B",
          road_polygon: [],
          center_boundary: [],
          direction_regions: [
            { id: "B1", name: "B1 (Sang phải)", polygon: [], allowed_direction: [1, 0] },
            { id: "B2", name: "B2 (Sang trái)", polygon: [], allowed_direction: [-1, 0] },
          ],
          stop_lines: [
            { id: "stop_B1", direction_region_id: "B1", line: [] },
            { id: "stop_B2", direction_region_id: "B2", line: [] },
          ],
        },
      },
      intersection_polygon: [],
    };
    this.activeDrawingPoints = [];
    document.querySelectorAll(".editor-toolbar-row1 .tool-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.getAttribute("data-tool") === "road_A");
    });
    this.updateToolButtonsState();
    this.updateGuide();
    this.render();
  }

  loadPreset(presetData) {
    if (!presetData) return;
    this.geometry = JSON.parse(JSON.stringify(presetData));
    this._recomputeDerivedGeometry();
    if (presetData.reference_size) {
      this.referenceSize = presetData.reference_size;
    }
    this.activeDrawingPoints = [];
    this.updateToolButtonsState();
    this.updateGuide();
    this.render();
  }

  _handleCanvasClick(e) {
    const rect = this.canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    // Convert from canvas display coordinates to reference image coordinates
    const refX = Math.round((clickX / this.canvas.width) * this.referenceSize[0]);
    const refY = Math.round((clickY / this.canvas.height) * this.referenceSize[1]);

    // Add point freely without auto-closing
    this.activeDrawingPoints.push([refX, refY]);

    this.updateGuide();
    this.render();
  }

  undoLastPoint() {
    if (this.activeDrawingPoints.length > 0) {
      this.activeDrawingPoints.pop();
      this.updateGuide();
      this.render();
    }
  }

  hasPart(tool) {
    const rA = this.geometry.roads.A;
    const rB = this.geometry.roads.B;
    switch (tool) {
      case "road_A": return rA.road_polygon?.length >= 3;
      case "road_B": return rB.road_polygon?.length >= 3;
      case "stop_A1": return rA.stop_lines[0]?.line?.length >= 2;
      case "stop_A2": return rA.stop_lines[1]?.line?.length >= 2;
      case "boundary_A": return rA.center_boundary?.length >= 2;
      case "stop_B1": return rB.stop_lines[0]?.line?.length >= 2;
      case "stop_B2": return rB.stop_lines[1]?.line?.length >= 2;
      case "boundary_B": return rB.center_boundary?.length >= 2;
      default: return false;
    }
  }

  updateToolButtonsState() {
    document.querySelectorAll(".editor-toolbar-row1 .tool-btn").forEach((btn) => {
      const toolAttr = btn.getAttribute("data-tool");
      if (toolAttr) {
        if (this.hasPart(toolAttr)) {
          btn.classList.add("saved-part");
        } else {
          btn.classList.remove("saved-part");
        }
      }
    });
  }

  clearCurrentToolPart() {
    const tool = this.currentTool;
    const rA = this.geometry.roads.A;
    const rB = this.geometry.roads.B;
    if (tool === "road_A") {
      rA.road_polygon = [];
      rA.direction_regions.forEach((region) => { region.polygon = []; });
    } else if (tool === "road_B") {
      rB.road_polygon = [];
      rB.direction_regions.forEach((region) => { region.polygon = []; });
    }
    else if (tool === "stop_A1") rA.stop_lines[0].line = [];
    else if (tool === "stop_A2" && rA.stop_lines[1]) rA.stop_lines[1].line = [];
    else if (tool === "boundary_A") rA.center_boundary = [];
    else if (tool === "stop_B1") rB.stop_lines[0].line = [];
    else if (tool === "stop_B2" && rB.stop_lines[1]) rB.stop_lines[1].line = [];
    else if (tool === "boundary_B") rB.center_boundary = [];

    this.activeDrawingPoints = [];
    this._recomputeDerivedGeometry();
    this.updateToolButtonsState();
    this.updateGuide();
    this.render();
  }

  commitCurrentPart() {
    const isPoly = ["road_A", "road_B"].includes(this.currentTool);
    const minReq = isPoly ? 3 : 2;

    if (this.activeDrawingPoints.length < minReq) {
      alert(`Phần này cần tối thiểu ${minReq} điểm để xác định. Bạn mới chấm ${this.activeDrawingPoints.length} điểm.`);
      return;
    }

    const pts = [...this.activeDrawingPoints];

    // Commit to the chosen tool
    if (this.currentTool === "road_A") {
      this.geometry.roads.A.road_polygon = pts;
    } else if (this.currentTool === "road_B") {
      this.geometry.roads.B.road_polygon = pts;
    } else if (this.currentTool === "stop_A1") {
      this.geometry.roads.A.stop_lines[0].line = pts;
    } else if (this.currentTool === "stop_A2") {
      if (!this.geometry.roads.A.stop_lines[1]) {
        this.geometry.roads.A.stop_lines.push({ id: "stop_A2", direction_region_id: "A2", line: [] });
      }
      this.geometry.roads.A.stop_lines[1].line = pts;
    } else if (this.currentTool === "boundary_A") {
      this.geometry.roads.A.center_boundary = pts;
    } else if (this.currentTool === "stop_B1") {
      this.geometry.roads.B.stop_lines[0].line = pts;
    } else if (this.currentTool === "stop_B2") {
      if (!this.geometry.roads.B.stop_lines[1]) {
        this.geometry.roads.B.stop_lines.push({ id: "stop_B2", direction_region_id: "B2", line: [] });
      }
      this.geometry.roads.B.stop_lines[1].line = pts;
    } else if (this.currentTool === "boundary_B") {
      this.geometry.roads.B.center_boundary = pts;
    }

    const savedName = this.getToolName(this.currentTool);
    this.activeDrawingPoints = [];
    this._recomputeDerivedGeometry();
    this.updateToolButtonsState();
    this.render();

    const guideEl = document.getElementById("editorGuideText");
    if (guideEl) {
      guideEl.innerHTML = `<span style="color:#16a34a; font-weight:700;">✓ Đã lưu thành công: ${savedName}!</span> Nút đã chuyển màu xanh. Hãy chọn tiếp phần khác để vẽ.`;
    }
  }

  _recomputeDerivedGeometry(strict = false) {
    const roads = this.geometry.roads;
    const result = SceneGeometry.deriveScene(roads, strict);
    for (const key of ["A", "B"]) {
      if (!(roads[key].road_polygon || []).length) continue;
      if (result.regions[key]) roads[key].direction_regions = result.regions[key];
      else roads[key].direction_regions.forEach((region) => { region.polygon = []; });
    }
    if ((roads.A.road_polygon || []).length || (roads.B.road_polygon || []).length) {
      this.geometry.intersection_polygon = result.intersectionPolygon;
    }
    this.derivedErrors = result.errors;
    return result;
  }

  render() {
    if (!this.canvas || !this.ctx) return;
    const { width, height } = this.canvas;
    this.ctx.clearRect(0, 0, width, height);

    // 1. Draw snapshot background
    if (this.snapshotImage) {
      this.ctx.drawImage(this.snapshotImage, 0, 0, width, height);
    } else {
      this.ctx.fillStyle = "#1e293b";
      this.ctx.fillRect(0, 0, width, height);
      this.ctx.fillStyle = "#94a3b8";
      this.ctx.font = "14px sans-serif";
      this.ctx.fillText("Đang tải khung hình đầu tiên của video...", 20, 30);
    }

    const toCanvas = (pt) => [
      (pt[0] / this.referenceSize[0]) * width,
      (pt[1] / this.referenceSize[1]) * height,
    ];

    // Helper to draw polygon
    const drawPoly = (pts, color, label) => {
      if (!pts || pts.length < 3) return;
      this.ctx.beginPath();
      this.ctx.strokeStyle = color;
      this.ctx.fillStyle = color.replace("1)", "0.15)");
      this.ctx.lineWidth = 2;
      pts.forEach((p, idx) => {
        const [cx, cy] = toCanvas(p);
        if (idx === 0) this.ctx.moveTo(cx, cy);
        else this.ctx.lineTo(cx, cy);
      });
      this.ctx.closePath();
      this.ctx.fill();
      this.ctx.stroke();

      if (label && pts.length > 0) {
        const [lx, ly] = toCanvas(pts[0]);
        this.ctx.fillStyle = color;
        this.ctx.font = "bold 12px sans-serif";
        this.ctx.fillText(label, lx + 4, ly + 16);
      }
    };

    // Helper to draw polyline (2 or more points)
    const drawLine = (line, color, label) => {
      if (!line || line.length < 2) return;
      this.ctx.beginPath();
      this.ctx.strokeStyle = color;
      this.ctx.lineWidth = 3;
      line.forEach((p, idx) => {
        const [x, y] = toCanvas(p);
        if (idx === 0) this.ctx.moveTo(x, y);
        else this.ctx.lineTo(x, y);
      });
      this.ctx.stroke();

      if (label && line.length >= 2) {
        const [x1, y1] = toCanvas(line[0]);
        const [x2, y2] = toCanvas(line[line.length - 1]);
        this.ctx.fillStyle = color;
        this.ctx.font = "bold 12px sans-serif";
        this.ctx.fillText(label, (x1 + x2) / 2, (y1 + y2) / 2 - 6);
      }
    };

    const rA = this.geometry.roads.A;
    const rB = this.geometry.roads.B;

    // Draw committed objects
    drawPoly(rA.road_polygon, "rgba(147, 51, 234, 1)", "Đường A");
    drawPoly(rB.road_polygon, "rgba(6, 182, 212, 1)", "Đường B");
    drawPoly(this.geometry.intersection_polygon, "rgba(236, 72, 153, 1)", "Ngã tư tự tạo");
    drawLine(rA.center_boundary, "rgba(245, 158, 11, 1)", "Tim Đường A");
    drawLine(rA.stop_lines[0]?.line, "rgba(239, 68, 68, 1)", "Stop A1");
    drawLine(rA.stop_lines[1]?.line, "rgba(239, 68, 68, 1)", "Stop A2");

    drawLine(rB.center_boundary, "rgba(245, 158, 11, 1)", "Tim Đường B");
    drawLine(rB.stop_lines[0]?.line, "rgba(239, 68, 68, 1)", "Stop B1");
    drawLine(rB.stop_lines[1]?.line, "rgba(239, 68, 68, 1)", "Stop B2");

    drawPoly(rA.direction_regions[0]?.polygon, "rgba(59, 130, 246, 1)", "Làn A1");
    drawPoly(rA.direction_regions[1]?.polygon, "rgba(99, 102, 241, 1)", "Làn A2");
    drawPoly(rB.direction_regions[0]?.polygon, "rgba(16, 185, 129, 1)", "Làn B1");
    drawPoly(rB.direction_regions[1]?.polygon, "rgba(20, 184, 166, 1)", "Làn B2");
    for (const road of [rA, rB]) {
      for (const region of road.direction_regions) {
        if (!region.polygon?.length || !region.allowed_direction) continue;
        const center = region.polygon.reduce((sum, point) =>
          [sum[0] + point[0], sum[1] + point[1]], [0, 0])
          .map((value) => value / region.polygon.length);
        const [x, y] = toCanvas(center);
        const dx = region.allowed_direction[0] * 28;
        const dy = region.allowed_direction[1] * 28;
        this.ctx.strokeStyle = "#ffffff";
        this.ctx.lineWidth = 3;
        this.ctx.beginPath();
        this.ctx.moveTo(x - dx / 2, y - dy / 2);
        this.ctx.lineTo(x + dx / 2, y + dy / 2);
        this.ctx.lineTo(x + dx / 2 - (dx - dy) * 0.28, y + dy / 2 - (dy + dx) * 0.28);
        this.ctx.moveTo(x + dx / 2, y + dy / 2);
        this.ctx.lineTo(x + dx / 2 - (dx + dy) * 0.28, y + dy / 2 - (dy - dx) * 0.28);
        this.ctx.stroke();
      }
    }

    // Draw currently active points being clicked in real-time
    if (this.activeDrawingPoints.length > 0) {
      const isPoly = ["road_A", "road_B"].includes(this.currentTool);

      this.ctx.strokeStyle = "#ffffff";
      this.ctx.fillStyle = isPoly ? "rgba(255, 255, 255, 0.2)" : "transparent";
      this.ctx.lineWidth = 2;
      this.ctx.setLineDash([5, 3]);

      this.ctx.beginPath();
      this.activeDrawingPoints.forEach((p, idx) => {
        const [cx, cy] = toCanvas(p);
        if (idx === 0) this.ctx.moveTo(cx, cy);
        else this.ctx.lineTo(cx, cy);
      });
      if (isPoly && this.activeDrawingPoints.length >= 3) {
        this.ctx.closePath();
      }
      this.ctx.stroke();
      if (isPoly && this.activeDrawingPoints.length >= 3) {
        this.ctx.fill();
      }
      this.ctx.setLineDash([]); // Reset dash

      // Draw point markers
      this.activeDrawingPoints.forEach((p, idx) => {
        const [cx, cy] = toCanvas(p);
        this.ctx.fillStyle = "#2563eb";
        this.ctx.strokeStyle = "#ffffff";
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.arc(cx, cy, 5, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.stroke();

        this.ctx.fillStyle = "#ffffff";
        this.ctx.font = "bold 10px sans-serif";
        this.ctx.fillText(String(idx + 1), cx + 7, cy - 4);
      });
    }
  }

  async saveConfig() {
    if (!this.snapshotImage) throw new Error("Chưa có khung hình camera/video để vẽ quy ước đường");
    if (this.activeDrawingPoints.length) {
      throw new Error("Bạn đang vẽ dở một phần. Bấm 'Lưu phần này' trước khi chạy.");
    }
    this._recomputeDerivedGeometry(true);
    const rA = this.geometry.roads.A;
    const rB = this.geometry.roads.B;
    const roads = [rA, rB];
    const hasRegions = roads.some((road) => road.direction_regions.some((region) => region.polygon.length >= 3));
    if (!hasRegions) {
      throw new Error("Cần vẽ và lưu ít nhất một vùng làn đường để nhận diện hướng xe.");
    }
    for (const road of roads) {
      for (const line of road.stop_lines) {
        if (line.line.length >= 2 && !road.direction_regions.some((region) =>
          region.id === line.direction_region_id && region.polygon.length >= 3)) {
          throw new Error(`Vạch ${line.id} cần vùng làn đường tương ứng để xác định chiều xe.`);
        }
      }
    }

    const payload = {
      scene_id: `scene_${this.currentVideoFilename}`,
      source_id: this.currentVideoFilename,
      reference_size: this.referenceSize,
      reference_frame_ms: this.snapshotMs,
      roads: this.geometry.roads,
      intersection_polygon: this.geometry.intersection_polygon,
    };

    const res = await fetch("/api/scene-configs/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || !data.scene_id) {
      throw new Error(data.error || "Không lưu được quy ước đường");
    }
    return data;
  }
}
