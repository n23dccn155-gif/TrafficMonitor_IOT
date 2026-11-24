/**
 * Traffic Signal Controller & Visual Panel.
 * Supports:
 * 1. Timed Mode (Tự động theo giây): Configurable A/B green & yellow durations with live countdown.
 * 2. Manual Mode (Chuyển thủ công): Direct clicking on bulbs with glowing white border highlight and safe interlocking.
 *    Clicking the yellow bulb on both roads (ALL_YELLOW) shows both directions yellow at once.
 */
class SignalPanel {
  constructor() {
    this.mode = "timed"; // "timed" or "manual"
    this.currentPhase = "A_GREEN";
    this.timelineId = "timeline_vd3_v1";
    this.videoFilename = "vd3.mp4";

    // Durations in seconds
    this.aGreenSec = 15;
    this.aYellowSec = 3;
    this.bGreenSec = 15;
    this.bYellowSec = 3;

    // Timer state
    this.cycleTimer = null;
    this.remainingSec = 15;
    this.manualChanges = [{ at_video_ms: 0, phase: "A_GREEN", seq: 1 }];
    this.hardwareEnabled = false;
    this.hardwarePoll = null;
    this.hardwareBusy = false;

    // DOM Elements
    this.tabTimed = document.getElementById("tabTimed");
    this.tabManual = document.getElementById("tabManual");
    this.timedInputsBox = document.getElementById("timedInputsBox");
    this.manualHintText = document.getElementById("manualHintText");
    this.phaseBadge = document.getElementById("currentPhaseBadge");

    this.bulbARed = document.getElementById("bulbA_red");
    this.bulbAYellow = document.getElementById("bulbA_yellow");
    this.bulbAGreen = document.getElementById("bulbA_green");
    this.bulbBRed = document.getElementById("bulbB_red");
    this.bulbBYellow = document.getElementById("bulbB_yellow");
    this.bulbBGreen = document.getElementById("bulbB_green");

    this.countARed = document.getElementById("bulbA_red_count");
    this.countAYellow = document.getElementById("bulbA_yellow_count");
    this.countAGreen = document.getElementById("bulbA_green_count");
    this.countBRed = document.getElementById("bulbB_red_count");
    this.countBYellow = document.getElementById("bulbB_yellow_count");
    this.countBGreen = document.getElementById("bulbB_green_count");

    // Initialize
    this.applyTimedConfig();
    this.checkExistingHardware();
  }

  setMode(mode) {
    this.mode = mode;
    const container = document.getElementById("trafficLightsContainer");
    const allRedButton = document.getElementById("manualAllRedButton");
    if (allRedButton) allRedButton.style.display = mode === "manual" ? "inline-flex" : "none";
    if (mode === "timed") {
      this.tabTimed.classList.add("active");
      this.tabManual.classList.remove("active");
      this.timedInputsBox.style.display = "flex";
      this.manualHintText.style.display = "none";
      if (container) container.classList.remove("mode-manual");
      this.startTimedCycle();
      if (this.hardwareEnabled) this.sendHardwareAuto().catch((e) => this.showHardwareStatus(`Lỗi Arduino: ${e.message}`));
    } else {
      this.tabTimed.classList.remove("active");
      this.tabManual.classList.add("active");
      this.timedInputsBox.style.display = "none";
      this.manualHintText.style.display = "block";
      if (container) container.classList.add("mode-manual");
      this.stopTimedCycle();
      this._clearAllCounts();
      if (this.hardwareEnabled) {
        this.hardwareRequest({ action: "manual", phase: this.currentPhase }).catch((e) => this.showHardwareStatus(`Lỗi Arduino: ${e.message}`));
      }
    }
  }

  applyTimedConfig() {
    const ag = parseInt(document.getElementById("inputAGreenSec").value) || 15;
    const ay = parseInt(document.getElementById("inputAYellowSec").value) || 3;
    const bg = parseInt(document.getElementById("inputBGreenSec").value) || 15;
    const by = parseInt(document.getElementById("inputBYellowSec").value) || 3;

    this.aGreenSec = Math.min(120, Math.max(3, ag));
    this.aYellowSec = Math.min(10, Math.max(1, ay));
    this.bGreenSec = Math.min(120, Math.max(3, bg));
    this.bYellowSec = Math.min(10, Math.max(1, by));

    if (this.hardwareEnabled) {
      this.stopTimedCycle();
      if (this.mode === "timed") this.sendHardwareAuto().catch((e) => this.showHardwareStatus(`Lỗi Arduino: ${e.message}`));
      return;
    }
    if (this.mode === "timed") {
      this.setPhase("A_GREEN", this.aGreenSec);
      this.startTimedCycle();
    }
  }

  syncToVideoTime(seconds) {
    if (this.hardwareEnabled) return;
    if (this.mode === "manual") {
      const atMs = Math.round(Math.max(0, seconds) * 1000);
      const change = [...this.manualChanges].sort((a, b) => a.at_video_ms - b.at_video_ms)
        .filter((item) => item.at_video_ms <= atMs).at(-1);
      if (change) {
        this.currentPhase = change.phase;
        this._renderBulbs();
      }
      return;
    }
    const phases = [
      ["A_GREEN", this.aGreenSec], ["A_YELLOW", this.aYellowSec],
      ["B_GREEN", this.bGreenSec], ["B_YELLOW", this.bYellowSec],
    ];
    const cycle = phases.reduce((sum, item) => sum + item[1], 0);
    let elapsed = Math.max(0, seconds) % cycle;
    for (const [phase, duration] of phases) {
      if (elapsed < duration) {
        this.currentPhase = phase;
        this.remainingSec = Math.ceil(duration - elapsed);
        this._renderBulbs();
        return;
      }
      elapsed -= duration;
    }
  }

  startTimedCycle() {
    this.stopTimedCycle();
    if (this.hardwareEnabled) return;
    this.cycleTimer = setInterval(() => {
      this.remainingSec--;
      if (this.remainingSec <= 0) {
        this._advanceToNextPhase();
      } else {
        this._renderBulbs();
      }
    }, 1000);
  }

  stopTimedCycle() {
    if (this.cycleTimer) {
      clearInterval(this.cycleTimer);
      this.cycleTimer = null;
    }
  }

  _advanceToNextPhase() {
    switch (this.currentPhase) {
      case "A_GREEN":
        this.setPhase("A_YELLOW", this.aYellowSec);
        break;
      case "A_YELLOW":
        this.setPhase("B_GREEN", this.bGreenSec);
        break;
      case "B_GREEN":
        this.setPhase("B_YELLOW", this.bYellowSec);
        break;
      case "B_YELLOW":
      default:
        this.setPhase("A_GREEN", this.aGreenSec);
        break;
    }
  }

  setPhase(phase, durationSec = null) {
    if (this.hardwareEnabled) {
      if (this.mode === "manual") {
        // Update locally right away so fast clicks chain (e.g. A yellow then B yellow
        // becomes ALL_YELLOW); the Uno reply overwrites this with the real state.
        this.currentPhase = phase;
        this._renderBulbs();
        this.hardwareRequest({ action: "manual", phase }).catch(() => {});
      }
      return;
    }
    this.currentPhase = phase;
    if (typeof app !== "undefined" && app) app.onSignalPhaseChanged(phase);
    if (durationSec !== null) {
      this.remainingSec = durationSec;
    }
    this._renderBulbs();
  }

  onBulbClick(road, color) {
    if (this.mode === "timed") {
      alert("Đang ở chế độ Tự Động. Vui lòng bấm vào tab '👆 Chuyển Đèn Thủ Công' để điều khiển trực tiếp bằng chuột.");
      return;
    }

    // Manual switching logic with strict safety: Never A and B green concurrently
    if (road === "A") {
      if (color === "green") {
        this.setPhase("A_GREEN");
      } else if (color === "yellow") {
        // Yellow on both roads: B already yellow => BOTH_YELLOW; again => back to B only.
        if (this.currentPhase === "ALL_YELLOW") this.setPhase("B_YELLOW");
        else this.setPhase(this.currentPhase === "B_YELLOW" ? "ALL_YELLOW" : "A_YELLOW");
      } else if (color === "red") {
        // Switching A to Red safely gives green to B
        this.setPhase("B_GREEN");
      }
    } else if (road === "B") {
      if (color === "green") {
        this.setPhase("B_GREEN");
      } else if (color === "yellow") {
        if (this.currentPhase === "ALL_YELLOW") this.setPhase("A_YELLOW");
        else this.setPhase(this.currentPhase === "A_YELLOW" ? "ALL_YELLOW" : "B_YELLOW");
      } else if (color === "red") {
        // Switching B to Red safely gives green to A
        this.setPhase("A_GREEN");
      }
    }
  }

  _clearAllCounts() {
    [this.countARed, this.countAYellow, this.countAGreen, this.countBRed, this.countBYellow, this.countBGreen].forEach(
      (el) => el && (el.textContent = "")
    );
  }

  _renderBulbs() {
    // Reset all bulbs
    [this.bulbARed, this.bulbAYellow, this.bulbAGreen, this.bulbBRed, this.bulbBYellow, this.bulbBGreen].forEach(
      (b) => b && b.classList.remove("active")
    );
    this._clearAllCounts();

    const isTimed = this.mode === "timed";
    const secStr = isTimed ? String(this.remainingSec) : "";

    switch (this.currentPhase) {
      case "A_GREEN":
        if (this.bulbAGreen) {
          this.bulbAGreen.classList.add("active");
          if (this.countAGreen) this.countAGreen.textContent = secStr;
        }
        if (this.bulbBRed) {
          this.bulbBRed.classList.add("active");
          if (this.countBRed) this.countBRed.textContent = isTimed ? String(this.remainingSec + this.aYellowSec + (this.hardwareEnabled ? 1 : 0)) : "";
        }
        break;

      case "A_YELLOW":
        if (this.bulbAYellow) {
          this.bulbAYellow.classList.add("active");
          if (this.countAYellow) this.countAYellow.textContent = secStr;
        }
        if (this.bulbBRed) {
          this.bulbBRed.classList.add("active");
          if (this.countBRed) this.countBRed.textContent = isTimed && this.hardwareEnabled ? String(this.remainingSec + 1) : secStr;
        }
        break;

      case "B_GREEN":
        if (this.bulbBGreen) {
          this.bulbBGreen.classList.add("active");
          if (this.countBGreen) this.countBGreen.textContent = secStr;
        }
        if (this.bulbARed) {
          this.bulbARed.classList.add("active");
          if (this.countARed) this.countARed.textContent = isTimed ? String(this.remainingSec + this.bYellowSec + (this.hardwareEnabled ? 1 : 0)) : "";
        }
        break;

      case "B_YELLOW":
        if (this.bulbBYellow) {
          this.bulbBYellow.classList.add("active");
          if (this.countBYellow) this.countBYellow.textContent = secStr;
        }
        if (this.bulbARed) {
          this.bulbARed.classList.add("active");
          if (this.countARed) this.countARed.textContent = isTimed && this.hardwareEnabled ? String(this.remainingSec + 1) : secStr;
        }
        break;
      case "ALL_YELLOW":
        if (this.bulbAYellow) this.bulbAYellow.classList.add("active");
        if (this.bulbBYellow) this.bulbBYellow.classList.add("active");
        if (isTimed && this.remainingSec > 0) {
          if (this.countAYellow) this.countAYellow.textContent = secStr;
          if (this.countBYellow) this.countBYellow.textContent = secStr;
        }
        break;

      case "ALL_RED":
        if (this.bulbARed) this.bulbARed.classList.add("active");
        if (this.bulbBRed) this.bulbBRed.classList.add("active");
        if (isTimed && this.remainingSec > 0) {
          if (this.countARed) this.countARed.textContent = secStr;
          if (this.countBRed) this.countBRed.textContent = secStr;
        }
        break;
    }

    if (this.phaseBadge) {
      this.phaseBadge.textContent = this.currentPhase;
      this.phaseBadge.className = "violation-badge " + (
        this.currentPhase === "UNKNOWN" ? "badge-blue" :
        this.currentPhase.includes("GREEN") ? "badge-green" :
        this.currentPhase.includes("YELLOW") ? "badge-yellow" : "badge-red"
      );
    }
  }

  async hardwareRequest(payload) {
    const response = await fetch("/api/arduino/signal/", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    if (result.connected && result.phase) this.applyHardwareState(result);
    return result;
  }

  async toggleHardware() {
    if (this.hardwareEnabled) {
      this.hardwareEnabled = false;
      clearInterval(this.hardwarePoll);
      this.hardwarePoll = null;
      try { await this.hardwareRequest({ action: "disconnect" }); } catch (e) { console.warn(e); }
      this.showHardwareStatus("Mô phỏng trên web");
      if (typeof app !== "undefined" && app?.selectedSourceType === "live") {
        this.currentPhase = "UNKNOWN";
        this._renderBulbs();
      } else this.applyTimedConfig();
      return;
    }
    const port = document.getElementById("arduinoPort")?.value?.trim()?.toUpperCase();
    const desiredMode = this.mode;
    const desiredTiming = {
      action: "auto", a_green: this.aGreenSec, a_yellow: this.aYellowSec,
      b_green: this.bGreenSec, b_yellow: this.bYellowSec,
    };
    try {
      this.showHardwareStatus("Đang kết nối...");
      await this.hardwareRequest({ action: "connect", port });
      this.hardwareEnabled = true;
      this.stopTimedCycle();
      document.getElementById("arduinoConnectButton").textContent = "Ngắt kết nối";
      if (desiredMode === "timed") await this.hardwareRequest(desiredTiming);
      else await this.hardwareRequest({ action: "manual", phase: this.currentPhase });
      this.hardwarePoll = setInterval(() => this.pollHardware(), 500);
    } catch (e) {
      this.hardwareEnabled = false;
      this.showHardwareStatus(`Lỗi Arduino: ${e.message}`);
    }
  }

  showHardwareStatus(message) {
    const el = document.getElementById("arduinoStatus");
    if (el) el.textContent = message;
    const button = document.getElementById("arduinoConnectButton");
    if (button && !this.hardwareEnabled) button.textContent = "Kết nối";
  }

  async sendHardwareAuto() {
    return this.hardwareRequest({
      action: "auto", a_green: this.aGreenSec, a_yellow: this.aYellowSec,
      b_green: this.bGreenSec, b_yellow: this.bYellowSec,
    });
  }

  async checkExistingHardware() {
    try {
      const response = await fetch("/api/arduino/signal/");
      const state = await response.json();
      if (!response.ok) return;
      if (!state.connected) {
        const usbPort = state.ports?.find((item) => /USB|Arduino/i.test(item.description));
        if (usbPort) document.getElementById("arduinoPort").value = usbPort.port;
        return;
      }
      this.hardwareEnabled = true;
      this.stopTimedCycle();
      document.getElementById("arduinoPort").value = state.port;
      document.getElementById("arduinoConnectButton").textContent = "Ngắt kết nối";
      this.applyHardwareState(state);
      this.hardwarePoll = setInterval(() => this.pollHardware(), 500);
    } catch (e) { console.warn("Arduino status unavailable", e); }
  }

  async pollHardware() {
    if (!this.hardwareEnabled || this.hardwareBusy) return;
    this.hardwareBusy = true;
    try {
      const response = await fetch("/api/arduino/signal/");
      const state = await response.json();
      if (!response.ok) throw new Error(state.error || `HTTP ${response.status}`);
      if (!state.connected) throw new Error("Đã mất kết nối USB");
      this.applyHardwareState(state);
    } catch (e) {
      clearInterval(this.hardwarePoll);
      this.hardwarePoll = null;
      this.hardwareEnabled = false;
      this.stopTimedCycle();
      this.currentPhase = "UNKNOWN";
      this._renderBulbs();
      this.showHardwareStatus(`Lỗi Arduino: ${e.message}`);
    } finally {
      this.hardwareBusy = false;
    }
  }

  applyHardwareState(state) {
    this.aGreenSec = state.a_green;
    this.aYellowSec = state.a_yellow;
    this.bGreenSec = state.b_green;
    this.bYellowSec = state.b_yellow;
    const reportedMode = state.mode === "auto" ? "timed" : "manual";
    if (reportedMode !== this.mode) {
      this.mode = reportedMode;
      this.tabTimed.classList[reportedMode === "timed" ? "add" : "remove"]("active");
      this.tabManual.classList[reportedMode === "manual" ? "add" : "remove"]("active");
      this.timedInputsBox.style.display = reportedMode === "timed" ? "flex" : "none";
      this.manualHintText.style.display = reportedMode === "manual" ? "block" : "none";
      const allRedButton = document.getElementById("manualAllRedButton");
      if (allRedButton) allRedButton.style.display = reportedMode === "manual" ? "inline-flex" : "none";
      const container = document.getElementById("trafficLightsContainer");
      if (container) container.classList[reportedMode === "manual" ? "add" : "remove"]("mode-manual");
    }
    const previous = this.currentPhase;
    this.currentPhase = state.phase;
    this.remainingSec = Math.ceil(state.remaining_ms / 1000);
    this.showHardwareStatus(`${state.port}: ${state.mode === "auto" ? "Tự động" : "Thủ công"}`);
    this._renderBulbs();
    if (previous !== state.phase && typeof app !== "undefined" && app) app.onSignalPhaseChanged(state.phase);
  }

  async saveTimelineToBackend() {
    try {
      let changes = this.mode === "manual" ? [...this.manualChanges] : [];
      let t = 0;
      let seq = 1;

      const durationMs = typeof app !== "undefined" && app?.player?.video?.duration
        ? Math.ceil(app.player.video.duration * 1000) : 300000;
      while (this.mode === "timed" && t < Math.max(300000, durationMs)) {
        changes.push({ at_video_ms: t, phase: "A_GREEN", seq: seq++ });
        t += this.aGreenSec * 1000;
        changes.push({ at_video_ms: t, phase: "A_YELLOW", seq: seq++ });
        t += this.aYellowSec * 1000;
        changes.push({ at_video_ms: t, phase: "B_GREEN", seq: seq++ });
        t += this.bGreenSec * 1000;
        changes.push({ at_video_ms: t, phase: "B_YELLOW", seq: seq++ });
        t += this.bYellowSec * 1000;
      }

      const response = await fetch("/api/signal-timelines/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_id: this.videoFilename,
          timeline_id: this.timelineId,
          mode: this.mode,
          changes: changes,
        }),
      });
      return response.ok;
    } catch (e) {
      console.warn("Could not sync timeline to backend:", e);
      return false;
    }
  }
}
