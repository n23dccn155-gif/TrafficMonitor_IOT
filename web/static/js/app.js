/**
 * Main Application Orchestrator for TrafficMonitor IoT.
 * Implements the 3-step linear flow:
 * Step 1: Chọn Nguồn (Central Modal)
 * Step 2: Vẽ Quy Ước Đường (Frozen Frame 0s on Viewport Canvas)
 * Step 3: Giám Sát Tự Động (Video Player + Real-time Overlay + Latest Violation + Scrollable History)
 */

class Application {
  constructor() {
    this.currentStep = 1;
    this.selectedSourceType = "mp4"; // "mp4" or "live"
    this.currentVideo = "vd3.mp4";
    this.currentTrackingRunId = null;
    this.currentSceneId = null;
    this.currentRuleRunId = null;
    this.isSaving = false;

    // Components
    this.player = null;
    this.signalPanel = null;
    this.editor = null;
    this.eventsManager = null;
  }

  async init() {
    // Initialize components
    this.player = new VideoCanvasPlayer("mainVideo", "overlayCanvas");
    this.signalPanel = new SignalPanel();
    this.editor = new RoadConventionEditor("editorCanvas");
    this.eventsManager = new ViolationEventsManager(this.player);

    // Recorded footage has no synchronized signal data; show only its playback time.
    if (this.player.video) {
      this.player.video.addEventListener("timeupdate", () => {
        const cur = (this.player.video.currentTime || 0).toFixed(1);
        const dur = (this.player.video.duration || 0).toFixed(1);
        const display = document.getElementById("timecodeDisplay");
        if (display) display.textContent = `${cur}s / ${dur}s`;
      });
    }

    // Populate video dropdown
    await this.loadVideoList();

    // Start at Step 1: Source Selection
    this.setStep(1);
  }

  setStep(step) {
    this.currentStep = step;

    // Stepper navigation highlights
    const s1 = document.getElementById("stepNav1");
    const s2 = document.getElementById("stepNav2");
    const s3 = document.getElementById("stepNav3");

    [s1, s2, s3].forEach((el) => el && el.classList.remove("active", "completed"));
    if (step === 1) {
      this.signalPanel?.stopTimedCycle();
      this.stopLivePolling();
      this.stopLivePreview();
      s1.classList.add("active");
    } else if (step === 2) {
      this.signalPanel?.stopTimedCycle();
      this.stopLivePolling();
      this.stopLivePreview();
      s1.classList.add("completed");
      s2.classList.add("active");
    } else if (step === 3) {
      if (this.signalPanel?.mode === "timed") this.signalPanel.startTimedCycle();
      s1.classList.add("completed");
      s2.classList.add("completed");
      s3.classList.add("active");
    }

    // Containers visibility
    const modal = document.getElementById("sourceModalOverlay");
    const editorEl = document.getElementById("editorContainer");
    const monitorEl = document.getElementById("monitorContainer");

    if (step === 1) {
      if (modal) modal.style.display = "flex";
      if (editorEl) editorEl.style.display = "none";
      if (monitorEl) monitorEl.style.display = "none";
      if (this.player && this.player.video) this.player.video.pause();
    } else if (step === 2) {
      if (modal) modal.style.display = "none";
      if (editorEl) editorEl.style.display = "flex";
      if (monitorEl) monitorEl.style.display = "none";
      if (this.player && this.player.video) this.player.video.pause();

      setTimeout(() => {
        if (this.editor) this.editor.resizeCanvas();
      }, 50);

      // Open editor on Frame 0s
      this.editor.open(this.currentVideo, 0);
    } else if (step === 3) {
      if (modal) modal.style.display = "none";
      if (editorEl) editorEl.style.display = "none";
      if (monitorEl) monitorEl.style.display = "flex";

      setTimeout(() => {
        if (this.player) this.player.resizeCanvas();
      }, 50);

      const statusBadge = document.getElementById("monitoringStatusBadge");
      const rulesButton = document.getElementById("rulesRunButton");
      const trackingControl = document.getElementById("trackingControl");
      const signalContextNote = document.getElementById("signalContextNote");
      if (rulesButton) rulesButton.style.display = this.selectedSourceType === "live" ? "none" : "inline-flex";
      if (trackingControl) trackingControl.style.display = this.selectedSourceType === "live" ? "none" : "inline-flex";
      if (signalContextNote) signalContextNote.textContent = this.selectedSourceType === "mp4"
        ? "Video mẫu không có dữ liệu pha đèn: bảng đèn chạy độc lập, không dùng để chấm vượt đèn đỏ."
        : "Camera trực tiếp: pha đèn được dùng để xét vượt đèn đỏ.";

      if (this.selectedSourceType === "live") {
        // Live Camera Mode (DroidCam)
        if (statusBadge) {
          statusBadge.textContent = "Đang Giám Sát Trực Tiếp (DroidCam)";
          statusBadge.className = "violation-badge badge-green";
        }
        if (this.player && this.player.video) {
          this.player.video.style.display = "none";
        }
        let liveImg = document.getElementById("liveMonitorImg");
        if (!liveImg) {
          liveImg = document.createElement("img");
          liveImg.id = "liveMonitorImg";
          liveImg.style.width = "100%";
          liveImg.style.height = "100%";
          liveImg.style.objectFit = "contain";
          const wrapper = document.querySelector(".monitor-viewport-wrapper");
          if (wrapper) wrapper.prepend(liveImg);
        }
        liveImg.style.display = "block";
        this.player.setLiveMode(true);
        this.startLivePreview(liveImg);
        this.startLivePolling();
      } else {
        // MP4 Video Mode
        if (statusBadge) {
          statusBadge.textContent = "Đang Giám Sát Tự Động (Video)";
          statusBadge.className = "violation-badge badge-blue";
        }
        const liveImg = document.getElementById("liveMonitorImg");
        if (liveImg) liveImg.style.display = "none";
        this.stopLivePreview();
        this.player.setLiveMode(false);

        if (this.player && this.player.video) {
          this.player.video.style.display = "block";
          this.player.video.src = `/api/videos/${encodeURIComponent(this.currentVideo)}/stream/`;
          this.player.video.play().catch(() => {});
          this.player.setRun(this.currentTrackingRunId);
        }
      }

      this.eventsManager.reset();
    }
  }

  // --- STEP 1: SOURCE SELECTION ---
  selectSourceMode(mode) {
    this.selectedSourceType = mode;
    const mp4Grp = document.getElementById("optionMp4Group");
    const liveGrp = document.getElementById("optionLiveGroup");
    const rMp4 = document.getElementById("radioMp4");
    const rLive = document.getElementById("radioLive");

    if (mode === "mp4") {
      if (mp4Grp) mp4Grp.classList.add("selected");
      if (liveGrp) liveGrp.classList.remove("selected");
      if (rMp4) rMp4.checked = true;
    } else {
      if (mp4Grp) mp4Grp.classList.remove("selected");
      if (liveGrp) liveGrp.classList.add("selected");
      if (rLive) rLive.checked = true;
    }
  }

  async loadVideoList() {
    try {
      const res = await fetch("/api/videos/");
      const data = await res.json();
      const sel = document.getElementById("videoSelect");
      if (!sel) return;
      sel.innerHTML = "";
      (data.videos || []).forEach((v) => {
        const opt = document.createElement("option");
        opt.value = v.filename;
        opt.textContent = `${v.filename} (${(v.duration_ms / 1000).toFixed(1)}s, ${v.width}x${v.height})`;
        if (v.filename === this.currentVideo) opt.selected = true;
        sel.appendChild(opt);
      });
    } catch (e) {
      console.warn("Could not load video list:", e);
    }
  }

  async loadTrackingRuns() {
    const source = this.currentVideo;
    const res = await fetch(`/api/tracking/runs/?source=${encodeURIComponent(source)}`);
    if (!res.ok) throw new Error("Không đọc được danh sách bản nhận diện");
    const data = await res.json();
    if (source !== this.currentVideo) return;
    const runs = data.runs || [];
    this.availableRuns = runs;
    this.currentTrackingRunId = runs.find((run) => run.complete && run.algorithm === "3")?.run_id || null;
    const select = document.getElementById("trackingRunSelect");
    if (select) {
      select.innerHTML = "";
      if (!this.currentTrackingRunId) select.add(new Option("Chưa có bản YOLOv8n đầy đủ", ""));
      for (const run of runs) {
        const coverage = run.source_frames
          ? ` / ${run.source_frames} khung hình` : " khung hình";
        const label = run.complete ? "đầy đủ" : "chưa đủ";
        const algorithm = { "3": "YOLOv8n", "2": "MOG2 (không phân loại xe)", "1": "YOLO11s" }[run.algorithm] || "thuật toán chưa rõ";
        select.add(new Option(`${algorithm} · ${run.run_id} (${run.processed_frames}${coverage}, ${label})`, run.run_id));
      }
      select.value = this.currentTrackingRunId || "";
    }
    return runs;
  }

  async ensureTrackingRun() {
    if (this.currentTrackingRunId) return;
    const source = this.currentVideo;
    const badge = document.getElementById("monitoringStatusBadge");
    if (badge) badge.textContent = "Đang nhận diện video bằng YOLO; có thể mất vài phút...";
    const response = await fetch("/api/tracking/jobs/", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, algorithm: "3", width: 1280 }),
    });
    const job = await response.json();
    if (!response.ok) throw new Error(job.error || "Không tạo được tác vụ nhận diện");
    while (this.currentStep === 3 && this.selectedSourceType === "mp4" && this.currentVideo === source) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      const statusResponse = await fetch(`/api/tracking/jobs/${encodeURIComponent(job.job_id)}/`);
      if (!statusResponse.ok) throw new Error("Không đọc được trạng thái nhận diện");
      const status = await statusResponse.json();
      if (status.status === "FAILED") throw new Error(status.error_text || "Nhận diện video thất bại");
      if (status.status === "DONE") {
        await this.loadTrackingRuns();
        if (!this.currentTrackingRunId) throw new Error("Tác vụ hoàn thành nhưng thiếu dữ liệu tracking");
        this.player.setRun(this.currentTrackingRunId);
        return;
      }
    }
  }

  onVideoDropdownChange(val) {
    this.currentVideo = val;
    this.currentTrackingRunId = null;
  }

  async handleFileUpload(input) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/videos/upload/", { method: "POST", body: formData });
      const data = await res.json();
      if (data.status === "success") {
        alert("Đã tải lên video: " + data.filename);
        await this.loadVideoList();
        this.currentVideo = data.filename;
        const sel = document.getElementById("videoSelect");
        if (sel) sel.value = data.filename;
      } else {
        alert("Lỗi tải video: " + (data.error || "Không thành công"));
      }
    } catch (e) {
      alert("Lỗi tải file: " + e.message);
    }
  }

  async connectLiveCamera(silent = false) {
    const url = (document.getElementById("cameraUrlInput").value || "").trim();
    try {
      const res = await fetch("/api/live/connect/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Không kết nối được camera");
      if (!silent) {
        alert(`Kết nối camera: ${data.status} (Chế độ: ${data.mode})`);
      }
      return data;
    } catch (e) {
      if (!silent) alert("Lỗi kết nối camera: " + e.message);
      return null;
    }
  }

  testMockStream() {
    document.getElementById("cameraUrlInput").value = "mock://droidcam";
    this.connectLiveCamera();
  }

  async confirmSourceAndProceed() {
    if (this.selectedSourceType === "mp4") {
      const sel = document.getElementById("videoSelect");
      if (sel && sel.value) this.currentVideo = sel.value;
      try {
        await this.loadTrackingRuns();
        this.setStep(2);
      } catch (error) {
        alert(`Không chuẩn bị được video: ${error.message}`);
      }
    } else {
      this.currentVideo = "live";
      const btn = document.querySelector("#sourceModalOverlay .btn-primary");
      const origText = btn ? btn.textContent : "";
      if (btn) {
        btn.disabled = true;
        btn.textContent = "⏳ Đang kết nối camera & lấy khung hình...";
      }
      try {
        const connection = await this.connectLiveCamera(true);
        if (!connection || connection.status !== "connected") {
          alert("Camera chưa có khung hình. Kiểm tra URL và kết nối mạng rồi thử lại.");
          return;
        }
        // Wait 400ms for camera handshake and first frame
        await new Promise((r) => setTimeout(r, 400));
        this.setStep(2);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.textContent = origText || "➡️ Xác Nhận Nguồn & Vẽ Quy Ước Đường";
        }
      }
    }
  }

  resetToSourceSelection() {
    this.stopLivePolling();
    if (this.selectedSourceType === "live") {
      fetch("/api/live/processing/", { method: "DELETE" }).catch(() => {});
    }
    this.stopLivePreview();
    this.setStep(1);
  }

  startLivePreview(liveImg) {
    this.stopLivePreview();
    const token = this.livePreviewToken;
    let firstFrame = true;
    const next = () => {
      if (token !== this.livePreviewToken || this.currentStep !== 3 || this.selectedSourceType !== "live") return;
      const frame = new Image();
      this.liveProbe = frame;
      frame.onload = () => {
        if (token !== this.livePreviewToken) return;
        this.player.setLiveMediaSize(frame.naturalWidth, frame.naturalHeight);
        liveImg.src = frame.src;
        liveImg.style.visibility = "visible";
        if (firstFrame) {
          this.player.resizeCanvas();
          firstFrame = false;
        }
        this.liveInterval = setTimeout(next, 250);
      };
      frame.onerror = () => {
        if (token !== this.livePreviewToken) return;
        // Keep the last good image visible during a transient camera error.
        this.liveInterval = setTimeout(next, 500);
      };
      frame.src = `/api/live/preview/?t=${Date.now()}`;
    };
    next();
  }

  stopLivePreview() {
    this.livePreviewToken = (this.livePreviewToken || 0) + 1;
    if (this.liveInterval) clearTimeout(this.liveInterval);
    this.liveInterval = null;
    if (this.liveProbe) {
      this.liveProbe.onload = null;
      this.liveProbe.onerror = null;
      this.liveProbe = null;
    }
    const liveImg = document.getElementById("liveMonitorImg");
    if (liveImg) {
      liveImg.onload = null;
      liveImg.onerror = null;
    }
  }

  // --- STEP 2: ROAD CONVENTION EDITOR ---
  async loadSamplePreset() {
    try {
      const res = await fetch(`/api/scene-configs/?source_id=${encodeURIComponent(this.currentVideo)}`);
      const data = await res.json();
      if (data.scene_configs && data.scene_configs.length > 0) {
        this.editor.loadPreset(data.scene_configs[0]);
      }
    } catch (e) {
      console.warn("Could not load sample preset:", e);
    }
  }

  async saveRoadConventionsAndStartMonitoring() {
    if (this.isSaving) return;
    this.isSaving = true;
    try {
      const data = await this.editor.saveConfig();
      this.currentSceneId = data.scene_id;
      this.currentRuleRunId = null;
      this.player.setScene(data);
      this.setStep(3);
      if (this.selectedSourceType === "live") {
        await this.startLiveProcessing();
      } else {
        await this.ensureTrackingRun();
        if (this.currentStep === 3 && this.currentTrackingRunId) await this.triggerRerunRules();
      }
    } catch (e) {
      const badge = document.getElementById("monitoringStatusBadge");
      if (this.currentStep === 3 && badge) badge.textContent = `Lỗi xử lý: ${e.message}`;
      else alert("Lỗi khi lưu quy ước đường: " + e.message);
    } finally {
      this.isSaving = false;
    }
  }

  async startLiveProcessing() {
    const badge = document.getElementById("monitoringStatusBadge");
    if (badge) badge.textContent = "Đang khởi động nhận diện...";
    try {
      const res = await fetch("/api/live/processing/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scene_config_id: this.currentSceneId,
          phase: this.signalPanel?.currentPhase || "UNKNOWN",
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Không khởi động được nhận diện");
      this.currentRuleRunId = data.run_id;
      this.eventsManager.loadEvents(this.currentRuleRunId);
    } catch (e) {
      if (badge) badge.textContent = `Lỗi xử lý: ${e.message}`;
    }
  }

  startLivePolling() {
    this.stopLivePolling();
    let polling = false;
    let lastEventsFetch = 0;
    const poll = async () => {
      if (this.currentStep !== 3 || this.selectedSourceType !== "live" || polling) return;
      polling = true;
      try {
        const [res, cameraRes] = await Promise.all([
          fetch("/api/live/processing/"), fetch("/api/live/status/"),
        ]);
        if (!res.ok || !cameraRes.ok) throw new Error("Cannot read camera status");
        const [data, cameraStatus] = await Promise.all([res.json(), cameraRes.json()]);
        const badge = document.getElementById("monitoringStatusBadge");
        if (!cameraStatus.connected || cameraStatus.frame_age_ms > 2000) {
          if (badge) badge.textContent = "Mất khung hình camera — đang kết nối lại";
          this.player.setLiveFrame(null);
          return;
        }
        if (data.run_id === this.currentRuleRunId) {
          this.player.setLiveFrame(data.result_age_ms > 5000 ? null : data.frame);
          if (badge && data.status === "RUNNING") {
            const stats = data.frame?.detection_stats || {};
            const tracked = stats.yolo_tracks || 0;
            const detected = stats.yolo_detections || 0;
            if (data.detector_warning) {
              badge.textContent = "Lỗi YOLO: " + data.detector_warning;
            } else if (!data.model_ready) {
              badge.textContent = "Đang tải mô hình YOLOv8...";
            } else if (data.result_age_ms > 5000) {
              badge.textContent = "Nhận diện đang chậm — kiểm tra tải CPU";
            } else if (!tracked && !detected && stats.rejected_boxes > 0) {
              badge.textContent = "YOLO nhận nhầm vùng quá lớn — hãy chỉnh góc camera";
            } else if (!tracked && !detected) {
              badge.textContent = "Camera có hình · YOLO chưa nhận ra ô tô hoặc xe máy";
            } else {
              badge.textContent = "Camera trực tiếp · " + tracked + " xe YOLO có ID, " + detected + " xe YOLO chưa có ID";
            }
          }
          if (badge && data.status === "FAILED") badge.textContent = `Lỗi xử lý: ${data.error}`;
          if (badge && data.status === "STARTING") badge.textContent = "Đang khởi động nhận diện...";
          if (data.status === "RUNNING" && Date.now() - lastEventsFetch >= 5000) {
            lastEventsFetch = Date.now();
            this.eventsManager.loadEvents(this.currentRuleRunId);
          }
        }
      } catch (e) {
        console.warn("Không lấy được trạng thái xử lý live:", e);
      } finally {
        polling = false;
      }
    };
    poll();
    this.livePollInterval = setInterval(poll, 1000);
  }

  stopLivePolling() {
    if (this.livePollInterval) clearInterval(this.livePollInterval);
    this.livePollInterval = null;
    this.player?.setLiveFrame(null);
  }

  onSignalPhaseChanged(phase) {
    if (this.currentStep !== 3 || this.selectedSourceType !== "live") return;
    fetch("/api/live/phase/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phase }),
    }).then((response) => {
      if (!response.ok) console.warn("Máy chủ chưa nhận được pha đèn:", response.status);
    }).catch((e) => console.warn("Không cập nhật được tín hiệu đèn:", e));
  }

  // --- STEP 3: MONITORING & RULE EXECUTION ---
  async triggerRerunRules() {
    if (this.selectedSourceType === "live") return;
    const badge = document.getElementById("monitoringStatusBadge");
    if (!this.currentTrackingRunId) {
      if (badge) badge.textContent = "Chưa có bản nhận diện cho video này";
      return;
    }
    try {
      if (badge) badge.textContent = "Đang quét vi phạm...";
      const res = await fetch("/api/rules/run/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tracking_run_id: this.currentTrackingRunId,
          source_id: this.currentVideo,
          scene_config_id: this.currentSceneId,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        this.currentRuleRunId = data.rule_run_id;
        await this.eventsManager.loadEvents(this.currentRuleRunId);
        if (badge) badge.textContent = `Đã quét xong · ${data.events_count} vi phạm (không chấm vượt đèn đỏ)`;
      } else {
        throw new Error(data.error || "Quét vi phạm thất bại");
      }
    } catch (e) {
      console.error("Error running rules:", e);
      if (badge) badge.textContent = `Lỗi quét vi phạm: ${e.message}`;
    }
  }

  onTrackingRunChange(runId) {
    this.currentTrackingRunId = runId || null;
    this.currentRuleRunId = null;
    this.eventsManager.reset();
    const run = this.availableRuns?.find((item) => item.run_id === runId);
    const badge = document.getElementById("monitoringStatusBadge");
    if (badge && run?.algorithm === "2") badge.textContent = "MOG2 chỉ bám vật chuyển động; nhãn xe là unknown. Chọn YOLOv8n để phân loại xe.";
    if (this.player) {
      this.player.setRun(this.currentTrackingRunId);
    }
  }
}

// Global Application Instance
let app = null;
let player = null;
let signalPanel = null;
let editor = null;
let eventsManager = null;

document.addEventListener("DOMContentLoaded", () => {
  app = new Application();
  app.init().then(() => {
    player = app.player;
    signalPanel = app.signalPanel;
    editor = app.editor;
    eventsManager = app.eventsManager;
  });
});
