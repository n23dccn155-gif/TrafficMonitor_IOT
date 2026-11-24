/**
 * Video Player with Responsive Canvas Overlay.
 * Synchronizes AI-detected vehicle bounding boxes and trajectories with video timecode.
 */
class VideoCanvasPlayer {
  constructor(videoElementId, canvasElementId, unprocessedBadgeId) {
    this.video = document.getElementById(videoElementId);
    this.canvas = document.getElementById(canvasElementId);
    this.ctx = this.canvas.getContext("2d");
    this.badge = document.getElementById(unprocessedBadgeId);

    this.currentRunId = null;
    this.trackFrames = new Map(); // timestamp_ms -> frameData
    this.maxBufferedMs = -1;
    this.minBufferedMs = Infinity;
    this.isFetchingWindow = false;
    this.windowRequestId = 0;
    this.processingSize = [1280, 720];
    this.scene = null;
    this.liveMode = false;
    this.liveFrame = null;
    this.liveMediaSize = null;
    this.violationEvents = [];

    this._bindEvents();
    this._startRenderLoop();
  }

  _bindEvents() {
    window.addEventListener("resize", () => this.resizeCanvas());
    this.video.addEventListener("loadedmetadata", () => this.resizeCanvas());
    this.video.addEventListener("timeupdate", () => this._checkBufferWindow());
    this.video.addEventListener("seeked", () => this._checkBufferWindow(true));
  }

  resizeCanvas() {
    if (!this.video || !this.canvas) return;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const width = Math.round(rect.width);
    const height = Math.round(rect.height);
    if (this.canvas.width === width && this.canvas.height === height) return;
    this.canvas.width = width;
    this.canvas.height = height;
    if (this.liveMode) this._renderOverlay();
  }

  setScene(scene) {
    this.scene = scene;
    if (this.liveMode) this._renderOverlay();
  }

  setLiveMode(enabled) {
    this.liveMode = enabled;
    this.liveFrame = null;
    this.liveMediaSize = null;
    if (enabled) this.setRun(null);
    this._renderOverlay();
  }

  setLiveMediaSize(width, height) {
    if (!width || !height) return;
    if (this.liveMediaSize?.[0] === width && this.liveMediaSize?.[1] === height) return;
    this.liveMediaSize = [width, height];
    if (this.liveMode) this._renderOverlay();
  }

  setLiveFrame(frame) {
    if (this.liveMode && !frame && !this.liveFrame) return;
    if (this.liveMode && frame && this.liveFrame && frame.frame_index != null &&
        frame.frame_index === this.liveFrame.frame_index &&
        frame.segment_id === this.liveFrame.segment_id) return;
    this.liveFrame = frame;
    if (frame?.processing_size) this.processingSize = frame.processing_size;
    if (this.liveMode) this._renderOverlay();
  }

  _mapPoint(point, sourceSize) {
    const [sourceW, sourceH] = sourceSize;
    const width = this.canvas.width;
    const height = this.canvas.height;
    if (!sourceW || !sourceH || !width || !height) return [0, 0];
    const liveImg = document.getElementById("liveMonitorImg");
    const mediaW = this.liveMode ? (this.liveMediaSize?.[0] || liveImg?.naturalWidth) : this.video.videoWidth;
    const mediaH = this.liveMode ? (this.liveMediaSize?.[1] || liveImg?.naturalHeight) : this.video.videoHeight;
    if (!mediaW || !mediaH) return [0, 0];
    const scale = Math.min(width / mediaW, height / mediaH);
    return [
      (width - mediaW * scale) / 2 + (point[0] / sourceW) * mediaW * scale,
      (height - mediaH * scale) / 2 + (point[1] / sourceH) * mediaH * scale,
    ];
  }

  _renderScene() {
    const scene = this.scene;
    if (!scene || !scene.reference_size) return;
    const size = scene.reference_size;
    const ctx = this.ctx;
    const draw = (points, color, closed) => {
      if (!Array.isArray(points) || points.length < (closed ? 3 : 2)) return;
      ctx.beginPath();
      points.forEach((point, i) => {
        const [x, y] = this._mapPoint(point, size);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      if (closed) ctx.closePath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      if (closed) {
        ctx.fillStyle = color.replace("0.5)", "0.10)");
        ctx.fill();
      }
      ctx.stroke();
    };
    draw(scene.intersection_polygon, "rgba(236, 72, 153, 0.5)", true);
    for (const road of Object.values(scene.roads || {})) {
      draw(road.center_boundary, "rgba(245, 158, 11, 0.5)", false);
      for (const stop of road.stop_lines || []) draw(stop.line, "rgba(239, 68, 68, 0.5)", false);
      for (const region of road.direction_regions || []) draw(region.polygon, "rgba(59, 130, 246, 0.5)", true);
    }
  }

  setRun(runId) {
    this.windowRequestId++;
    this.currentRunId = runId;
    this.isFetchingWindow = false;
    this.trackFrames.clear();
    this.minBufferedMs = Infinity;
    this.maxBufferedMs = -1;
    this.violationEvents = [];
    this._checkBufferWindow(true);
  }

  getCurrentTimestampMs() {
    return Math.floor((this.video.currentTime || 0) * 1000);
  }

  seek(timestampMs) {
    this.video.currentTime = timestampMs / 1000.0;
  }

  _violationFor(track, nowMs) {
    if (!track || !this.violationEvents || !this.violationEvents.length) {
      return null;
    }
    const matched = this.violationEvents.filter((ev) =>
      ev.track_id === track.track_id &&
      ev.review_status !== "dismissed" &&
      (nowMs == null || nowMs >= ev.event_timestamp_ms)
    );
    if (!matched.length) return null;
    return matched.reduce((latest, ev) =>
      !latest || (ev.event_timestamp_ms || 0) > (latest.event_timestamp_ms || 0) ? ev : latest
    , null);
  }

  async _checkBufferWindow(force = false) {
    if (!this.currentRunId || this.isFetchingWindow) return;
    const runId = this.currentRunId;
    const requestId = this.windowRequestId;
    const currentMs = this.getCurrentTimestampMs();

    // Fetch window if outside or near edge of buffer
    if (force || currentMs < this.minBufferedMs || currentMs > this.maxBufferedMs - 2000) {
      this.isFetchingWindow = true;
      const fromMs = Math.max(0, currentMs - 2000);
      const toMs = currentMs + 8000;
      try {
        const res = await fetch(`/api/tracking/runs/${encodeURIComponent(runId)}/tracks/?from_ms=${fromMs}&to_ms=${toMs}`);
        const data = await res.json();
        if (runId !== this.currentRunId || requestId !== this.windowRequestId) return;
        if (data.found && data.frames) {
          for (const f of data.frames) {
            this.trackFrames.set(f.video_timestamp_ms, f);
            if (f.processing_size) {
              this.processingSize = f.processing_size;
            }
          }
          this.minBufferedMs = Math.min(this.minBufferedMs, fromMs);
          this.maxBufferedMs = Math.max(this.maxBufferedMs, toMs);
        }
      } catch (err) {
        console.error("Error fetching tracks window:", err);
      } finally {
        if (requestId === this.windowRequestId) this.isFetchingWindow = false;
      }
    }
  }

  _startRenderLoop() {
    const render = () => {
      // Live overlays change only when a new inference result arrives.
      if (!this.liveMode) this._renderOverlay();
      requestAnimationFrame(render);
    };
    requestAnimationFrame(render);
  }

  _renderOverlay() {
    const { width, height } = this.canvas;
    this.ctx.clearRect(0, 0, width, height);
    this._renderScene();

    if (!this.currentRunId && !this.liveMode) {
      if (this.badge) this.badge.style.display = "none";
      return;
    }

    const currentMs = this.getCurrentTimestampMs();

    // Find closest frame within 100ms tolerance
    let closestFrame = this.liveMode ? this.liveFrame : null;
    let minDiff = 100;
    for (const [tMs, frame] of this.liveMode ? [] : this.trackFrames) {
      const diff = Math.abs(tMs - currentMs);
      if (diff < minDiff) {
        minDiff = diff;
        closestFrame = frame;
      }
    }

    if (!closestFrame) {
      if (this.badge) this.badge.style.display = "block";
      return;
    }

    if (this.badge) this.badge.style.display = "none";

    const nowMs = this.liveMode ? closestFrame?.video_timestamp_ms : currentMs;

    // Compute letterbox/pillarbox viewport mapping
    const liveImg = document.getElementById("liveMonitorImg");
    const vW = this.liveMode ? (this.liveMediaSize?.[0] || liveImg?.naturalWidth || 0) : (this.video.videoWidth || 0);
    const vH = this.liveMode ? (this.liveMediaSize?.[1] || liveImg?.naturalHeight || 0) : (this.video.videoHeight || 0);
    if (!vW || !vH) return;
    const cW = width;
    const cH = height;

    const scale = Math.min(cW / vW, cH / vH);
    const renderW = vW * scale;
    const renderH = vH * scale;
    const offsetX = (cW - renderW) / 2;
    const offsetY = (cH - renderH) / 2;

    const frameSize = closestFrame.processing_size || this.processingSize;
    const pW = frameSize[0] || vW;
    const pH = frameSize[1] || vH;

    const mapCoord = (x, y) => {
      const normX = x / pW;
      const normY = y / pH;
      return [offsetX + normX * renderW, offsetY + normY * renderH];
    };

    // Draw tracks
    for (const trk of closestFrame.tracks || []) {
      const [bx1, by1, bx2, by2] = trk.bbox_xyxy;
      const [x1, y1] = mapCoord(bx1, by1);
      const [x2, y2] = mapCoord(bx2, by2);
      const bw = x2 - x1;
      const bh = y2 - y1;

      const violation = this._violationFor(trk, nowMs);

      // Color and line width based on vehicle type or violation
      let color = "#3b82f6"; // blue
      let lineWidth = 2;
      let label = "";

      if (violation) {
        color = "#ef4444"; // red for violation
        lineWidth = 3;
        const ruleLabel = typeof violationRuleLabel === "function"
          ? violationRuleLabel(violation.rule_type)
          : (violation.rule_type === "wrong_way" ? "Ngược Chiều" : violation.rule_type === "lane_encroachment" ? "Lấn Vạch" : "Vượt Đèn Đỏ");
        label = `ID:${trk.track_id} ${trk.vehicle_type || "vehicle"} · ${ruleLabel}`;
      } else {
        if (trk.track_source === "techgar") color = "#a855f7"; // motion candidate
        else if (trk.vehicle_type === "motorcycle") color = "#06b6d4"; // cyan
        else if (trk.vehicle_type === "car") color = "#10b981"; // green
        else if (trk.vehicle_type === "bus") color = "#f59e0b"; // yellow

        label = trk.track_source === "techgar"
          ? `ID:${trk.track_id} ${trk.observation_kind === "detection" ? "vật thể chuyển động" : "đang giữ ID"}`
          : `ID:${trk.track_id} ${trk.vehicle_type}`;
      }

      // Draw bounding box
      this.ctx.strokeStyle = color;
      this.ctx.lineWidth = lineWidth;
      if (trk.observation_kind && trk.observation_kind !== "detection") this.ctx.setLineDash([5, 4]);
      this.ctx.strokeRect(x1, y1, bw, bh);
      this.ctx.setLineDash([]);

      // Draw label badge
      this.ctx.font = "bold 12px sans-serif";
      const textMetrics = this.ctx.measureText(label);
      this.ctx.fillStyle = color;
      this.ctx.fillRect(x1, Math.max(0, y1 - 18), textMetrics.width + 6, 18);
      this.ctx.fillStyle = "#ffffff";
      this.ctx.fillText(label, x1 + 3, Math.max(12, y1 - 4));

      // Draw ground contact point (red dot)
      if (trk.ground_point_xy) {
        const [gx, gy] = mapCoord(trk.ground_point_xy[0], trk.ground_point_xy[1]);
        this.ctx.beginPath();
        this.ctx.arc(gx, gy, 4, 0, 2 * Math.PI);
        this.ctx.fillStyle = "#ef4444";
        this.ctx.fill();
      }

      // Draw trajectory line
      if (trk.trajectory_xy && trk.trajectory_xy.length > 1) {
        this.ctx.beginPath();
        this.ctx.strokeStyle = color;
        this.ctx.lineWidth = 1.5;
        this.ctx.setLineDash([4, 2]);
        for (let i = 0; i < trk.trajectory_xy.length; i++) {
          const [tx, ty] = mapCoord(trk.trajectory_xy[i][0], trk.trajectory_xy[i][1]);
          if (i === 0) this.ctx.moveTo(tx, ty);
          else this.ctx.lineTo(tx, ty);
        }
        this.ctx.stroke();
        this.ctx.setLineDash([]);
      }
    }

  }
}
