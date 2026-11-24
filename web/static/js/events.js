/**
 * Violation Events Manager for TrafficMonitor IoT.
 * Displays the latest violation with enlarged vehicle crop image (with box & ID).
 * Populates an internal scrollable history list that seeks video on click.
 */

function violationRuleLabel(ruleType) {
  if (ruleType === "wrong_way") return "Ngược Chiều";
  if (ruleType === "lane_encroachment") return "Lấn Vạch";
  return "Vượt Đèn Đỏ";
}

if (typeof window !== "undefined") {
  window.violationRuleLabel = violationRuleLabel;
}
if (typeof global !== "undefined") {
  global.violationRuleLabel = violationRuleLabel;
}

class ViolationEventsManager {
  constructor(player) {
    this.player = player;
    this.events = [];
    this.activeEventId = null;
    this.requestId = 0;

    // DOM Elements
    this.totalCountEl = document.getElementById("totalViolationsCount");
    this.latestImg = document.getElementById("latestViolationImg");
    this.placeholderEl = document.getElementById("noViolationPlaceholder");
    this.ruleBadge = document.getElementById("latestRuleBadge");
    this.trackIdEl = document.getElementById("latestTrackId");
    this.timestampEl = document.getElementById("latestTimestamp");
    this.reasonEl = document.getElementById("latestReason");
    this.historyList = document.getElementById("violationHistoryList");

    if (this.latestImg) {
      this.latestImg.style.cursor = "zoom-in";
      this.latestImg.title = "Bấm để xem ảnh phóng to cực đại";
      this.latestImg.onclick = () => this.openLightbox();
    }
  }

  async loadEvents(ruleRunId = null) {
    const requestId = ++this.requestId;
    try {
      let url = "/api/events/";
      if (ruleRunId) url += `?run_id=${encodeURIComponent(ruleRunId)}`;
      const res = await fetch(url);
      const data = await res.json();
      if (requestId !== this.requestId) return;
      this.events = data.events || [];
      if (this.player) {
        this.player.violationEvents = this.events;
      }
      this.render();
    } catch (err) {
      console.error("Error loading events:", err);
    }
  }

  reset() {
    this.requestId++;
    this.events = [];
    if (this.player) {
      this.player.violationEvents = [];
    }
    this.activeEventId = null;
    this.render();
  }

  render() {
    if (this.totalCountEl) {
      this.totalCountEl.textContent = `${this.events.length} Vi phạm`;
    }

    if (this.events.length === 0) {
      if (this.latestImg) this.latestImg.style.display = "none";
      if (this.placeholderEl) this.placeholderEl.style.display = "block";
      if (this.ruleBadge) {
        this.ruleBadge.textContent = "CHỜ DỮ LIỆU";
        this.ruleBadge.className = "violation-badge badge-blue";
      }
      if (this.trackIdEl) this.trackIdEl.textContent = "--";
      if (this.timestampEl) this.timestampEl.textContent = "--:--";
      if (this.reasonEl) this.reasonEl.textContent = "Hệ thống đang quan sát luồng giao thông...";

      if (this.historyList) {
        this.historyList.innerHTML = `<div style="text-align:center; padding:1.5rem 0.5rem; color:var(--text-light); font-size:0.75rem;">Chưa có vi phạm nào trong danh sách.</div>`;
      }
      return;
    }

    // Show the first / most recent event in the Latest Violation card
    const latest = this.events[0];
    this.displayViolationInCard(latest);

    // Populate the scrollable history list
    if (this.historyList) {
      this.historyList.innerHTML = "";
      this.events.forEach((ev) => {
        const item = document.createElement("div");
        item.className = "history-item" + (ev.event_id === this.activeEventId ? " active" : "");

        let badgeClass = "badge-red";
        if (ev.rule_type === "wrong_way") {
          badgeClass = "badge-yellow";
        } else if (ev.rule_type === "lane_encroachment") {
          badgeClass = "badge-blue";
        }
        const ruleName = violationRuleLabel(ev.rule_type);

        item.innerHTML = `
          <div style="display:flex; align-items:center; gap:8px;">
            <span class="violation-badge ${badgeClass}" style="font-size:0.68rem; padding:1px 4px;">${ruleName}</span>
            <span style="font-weight:700;">#${ev.track_id}</span>
          </div>
          <span style="color:var(--text-muted); font-size:0.72rem;">${(ev.event_timestamp_ms / 1000).toFixed(1)}s</span>
        `;

        item.addEventListener("click", () => {
          this.activeEventId = ev.event_id;
          document.querySelectorAll(".history-item").forEach((el) => el.classList.remove("active"));
          item.classList.add("active");

          this.displayViolationInCard(ev);
          if (this.player && !this.player.liveMode) {
            this.player.seek(ev.event_timestamp_ms);
          }
        });

        this.historyList.appendChild(item);
      });
    }
  }

  displayViolationInCard(ev) {
    this.activeEventId = ev.event_id;

    if (this.latestImg) {
      // Prioritize enlarged crop image with vehicle box and ID
      const imgSrc = ev.crop_image_path || ev.full_image_path || "";
      if (imgSrc) {
        this.latestImg.src = imgSrc;
        this.latestImg.style.display = "block";
        if (this.placeholderEl) this.placeholderEl.style.display = "none";
      } else {
        this.latestImg.style.display = "none";
        if (this.placeholderEl) this.placeholderEl.style.display = "block";
      }
    }

    let badgeClass = "badge-red";
    if (ev.rule_type === "wrong_way") {
      badgeClass = "badge-yellow";
    } else if (ev.rule_type === "lane_encroachment") {
      badgeClass = "badge-blue";
    }
    const ruleName = violationRuleLabel(ev.rule_type).toUpperCase();

    if (this.ruleBadge) {
      this.ruleBadge.textContent = ruleName;
      this.ruleBadge.className = `violation-badge ${badgeClass}`;
    }

    if (this.trackIdEl) {
      this.trackIdEl.textContent = `#${ev.track_id} (${ev.vehicle_type || "Phương tiện"})`;
    }

    if (this.timestampEl) {
      this.timestampEl.textContent = `${(ev.event_timestamp_ms / 1000).toFixed(1)}s`;
    }

    if (this.reasonEl) {
      this.reasonEl.textContent = ev.reason || "Phát hiện vi phạm quy chuẩn giao thông ngã tư.";
    }
  }

  openLightbox() {
    const ev = this.events.find((e) => e.event_id === this.activeEventId) || this.events[0];
    if (!ev) return;
    const modal = document.getElementById("evidenceLightboxModal");
    const img = document.getElementById("lightboxImg");
    const title = document.getElementById("lightboxTitle");
    const details = document.getElementById("lightboxDetails");

    if (modal && img) {
      const imgSrc = ev.crop_image_path || ev.full_image_path || "";
      img.src = imgSrc;
      if (title) title.textContent = `Bằng Chứng: #${ev.track_id} - ${ev.rule_type.toUpperCase()} @ ${(ev.event_timestamp_ms / 1000).toFixed(1)}s`;
      if (details) details.innerHTML = `<strong>Lý do:</strong> ${ev.reason} &nbsp;|&nbsp; <strong>Loại xe:</strong> ${ev.vehicle_type || "Ô tô"} &nbsp;|&nbsp; <a href="${imgSrc}" download="${ev.event_id}.jpg" class="btn-primary" style="padding:2px 8px; font-size:0.75rem; text-decoration:none; display:inline-block; margin-left:8px;">📥 Tải Ảnh</a>`;
      modal.classList.add("active");
    }
  }

  closeLightbox(e) {
    if (e && e.target && e.target.closest && e.target.closest(".lightbox-content") && e.target.tagName !== "BUTTON") {
      return;
    }
    const modal = document.getElementById("evidenceLightboxModal");
    if (modal) modal.classList.remove("active");
  }
}
