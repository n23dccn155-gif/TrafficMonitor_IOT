"""Menu chính cho hệ thống TrafficMonitor IoT.

Quy trình chuẩn:
  1. Chọn loại nguồn: [1] Video file cục bộ hoặc [2] Link DroidCam live.
  2. Sau khi chọn nguồn, mới hiển thị phần nhập / dán đường dẫn (hoặc chọn nhanh vd1, vd2, vd3).
  3. Chọn thuật toán theo dõi; MOG2 chỉ theo dõi vùng chuyển động và không phân loại xe.
  4. Mở cửa sổ trực tiếp OpenCV (gốc bên trái, box/ID bên phải).
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent

# Tự động chuyển sang môi trường .venv của dự án nếu chạy từ python ngoài
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
if VENV_PYTHON.is_file():
    try:
        if Path(sys.executable).resolve() != VENV_PYTHON.resolve():
            sys.exit(subprocess.call([str(VENV_PYTHON)] + sys.argv))
    except Exception:
        pass

SRC_DIR = PROJECT_ROOT / "src" / "traffic_monitor"
sys.path.insert(0, str(SRC_DIR))

CONFIG_FILE = PROJECT_ROOT / "outputs" / "menu_config.json"
DEFAULT_DROIDCAM_URL = ""
RAW_VIDEOS = {
    "1": PROJECT_ROOT / "data" / "raw" / "vd3.mp4",
    "2": PROJECT_ROOT / "data" / "raw" / "vd2.mp4",
    "3": PROJECT_ROOT / "data" / "raw" / "vd1.mp4",
}


def load_config() -> dict:
    if CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_droidcam_url": DEFAULT_DROIDCAM_URL, "last_video_path": str(RAW_VIDEOS["1"])}


def save_config(cfg: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def select_source(cfg: dict) -> str | None:
    while True:
        print("\n=======================================================")
        print("         BƯỚC 1: CHỌN NGUỒN ĐẦU VÀO                    ")
        print("=======================================================")
        print("  1. Nguồn Video file (file video trên máy)")
        print("  2. Link DroidCam live (thử nghiệm; chưa có reconnect/frame-latest)")
        print("  0. Thoát chương trình")
        print("-------------------------------------------------------")

        source_type = input("Nhập lựa chọn (1, 2 hoặc 0): ").strip()

        if source_type == "0":
            return None

        # Trường hợp 1: Chọn Video File -> Mới hiển thị nhập đường dẫn
        elif source_type == "1":
            while True:
                print("\n--- Nhập đường dẫn Video ---")
                print("Gợi ý video có sẵn (nhập số hoặc dán đường dẫn file):")
                print(f"  [1] vd3.mp4 (Góc cao ngã tư xe máy — Mặc định)")
                print(f"  [2] vd2.mp4 (Mật độ xe máy đông)")
                print(f"  [3] vd1.mp4 (Cao tốc ô tô)")
                print("  [0] Quay lại chọn lại nguồn")
                default_path = cfg.get("last_video_path", str(RAW_VIDEOS["1"]))
                user_input = input(f"\nNhập [1, 2, 3] hoặc dán đường dẫn (Enter = vd3): ").strip()

                if user_input == "0":
                    break
                elif user_input in ("", "1"):
                    target = RAW_VIDEOS["1"]
                    if target.is_file():
                        cfg["last_video_path"] = str(target)
                        save_config(cfg)
                        return str(target)
                    print(f"  [Lỗi] Không tìm thấy file: {target}")
                elif user_input == "2":
                    target = RAW_VIDEOS["2"]
                    if target.is_file():
                        cfg["last_video_path"] = str(target)
                        save_config(cfg)
                        return str(target)
                    print(f"  [Lỗi] Không tìm thấy file: {target}")
                elif user_input == "3":
                    target = RAW_VIDEOS["3"]
                    if target.is_file():
                        cfg["last_video_path"] = str(target)
                        save_config(cfg)
                        return str(target)
                    print(f"  [Lỗi] Không tìm thấy file: {target}")
                else:
                    clean_path = user_input.strip('"').strip("'")
                    if Path(clean_path).is_file():
                        cfg["last_video_path"] = clean_path
                        save_config(cfg)
                        return clean_path
                    print(f"  [Lỗi] File không tồn tại: {clean_path}")

        # Trường hợp 2: Chọn DroidCam -> Mới hiển thị nhập link DroidCam
        elif source_type == "2":
            last_url = cfg.get("last_droidcam_url", DEFAULT_DROIDCAM_URL)
            print("\n--- Nhập link DroidCam Live ---")
            print(f"Link hiện tại: {last_url}")
            user_url = input("Nhấn Enter để dùng link trên, hoặc dán link DroidCam mới (0 để quay lại): ").strip()

            if user_url == "0":
                continue
            final_url = user_url if user_url else last_url
            if not final_url.startswith(("http://", "https://", "rtsp://")):
                print("[Lỗi] Hãy nhập URL http://, https:// hoặc rtsp:// từ DroidCam.")
                continue
            cfg["last_droidcam_url"] = final_url
            save_config(cfg)
            return final_url

        else:
            print("Lựa chọn không hợp lệ. Vui lòng nhập 1, 2 hoặc 0.")


def select_algorithm() -> str | None:
    while True:
        print("\n=======================================================")
        print("         BƯỚC 2: CHỌN THUẬT TOÁN QUAN SÁT & THEO DÕI ID")
        print("=======================================================")
        print("  1. YOLO11s chia 4 ô + ByteTrack (thử nghiệm, ưu tiên xe nhỏ)")
        print("     • Đổi lại: rất nặng CPU; vẫn có thể bỏ sót xe và đổi ID")
        print()
        print("  2. MOG2 trừ nền + Kalman (có sẵn trong repo)")
        print("     • Quan sát: vùng chuyển động; gán ID, không phân loại xe")
        print("     • Có thể mất xe dừng, xe bị che và tạo box sai")
        print()
        print("  3. Thuật toán 3: YOLOv8n + ByteTrack (Baseline)")
        print("     • Quan sát: Ô tô, Xe máy, Xe tải, Xe buýt ở độ rộng bạn chọn")
        print("     • Gán ID: ByteTrack tiêu chuẩn")
        print()
        print("  0. Quay lại bước chọn nguồn")
        print("-------------------------------------------------------")

        choice = input("Nhập lựa chọn thuật toán (1, 2, 3 hoặc 0): ").strip()
        if choice in ("0", "1", "2", "3"):
            return choice if choice != "0" else None
        print("Lựa chọn không hợp lệ, vui lòng nhập 1, 2, 3 hoặc 0.")


# Preset chất lượng: video file luôn được đọc tuần tự, không bỏ frame.
# Giảm độ phân giải giúp giảm lượng tính toán, nhưng cũng làm mất chi tiết xe nhỏ.
SPEED_PRESETS = {
    "1": {
        "name": "Chi tiết cao: 1280 px, YOLO11s chia 4 ô (rất chậm trên CPU)",
        "width": 1280, "tile_imgsz": 960, "cli_width": 1280,
    },
    "2": {
        "name": "Cân bằng: 960 px (vẫn xử lý đủ mọi frame)",
        "width": 960, "tile_imgsz": 640, "cli_width": 960,
    },
    "3": {
        "name": "Nhẹ: 640 px (vẫn xử lý đủ mọi frame; xe nhỏ dễ bị sót)",
        "width": 640, "tile_imgsz": 640, "cli_width": 640,
    },
}


def select_speed() -> dict:
    while True:
        print("\n=======================================================")
        print("         BƯỚC 3: CHỌN TỐC ĐỘ XỬ LÝ (CPU)")
        print("=======================================================")
        keys = sorted(SPEED_PRESETS.keys())
        for k in keys:
            print(f"  [{k}] {SPEED_PRESETS[k]['name']}")
        print("  [0] Quay lại bước chọn nguồn")
        print("-------------------------------------------------------")
        choice = input("Nhập lựa chọn tốc độ (1, 2, 3 hoặc 0): ").strip()
        if choice == "0":
            return None
        if choice in SPEED_PRESETS:
            return SPEED_PRESETS[choice]
        print("Lựa chọn không hợp lệ, vui lòng nhập 1, 2, 3 hoặc 0.")


def main():
    cfg = load_config()

    while True:
        source = select_source(cfg)
        if source is None:
            print("\nĐã thoát chương trình. Tạm biệt!")
            break

        algo = select_algorithm()
        if algo is None:
            continue

        speed = select_speed()
        if speed is None:
            continue

        save_mp4 = input("Lưu thêm MP4 debug? [y/N]: ").strip().lower() in ("y", "yes")

        run_id = f"run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}"
        output_dir = PROJECT_ROOT / "outputs" / "runs" / run_id
        output_dir.mkdir(parents=True, exist_ok=True)

        algo_names = {
            "1": "Thuật toán 1 (YOLO11s Tiling 2x2 + ByteTrack - Quan sát Ô tô & Xe máy nhỏ)",
            "2": "Thuật toán 2 (MOG2 trừ nền + Kalman, độc lập)",
            "3": "Thuật toán 3 (YOLOv8n Baseline + ByteTrack)",
        }

        print(f"\n=======================================================")
        print(f"  KHỞI ĐỘNG XỬ LÝ [{run_id}]")
        print(f"  • Nguồn: {source}")
        print(f"  • Thuật toán: {algo_names.get(algo)}")
        print(f"  • Tốc độ: {speed['name']}")
        print("  • Đầu ra: tracks.jsonl, summary.json" + (", annotated.mp4" if save_mp4 else ""))
        if source.startswith(("http://", "https://", "rtsp://")):
            print("  • Stream thử nghiệm: chưa có cơ chế bỏ frame cũ/nối lại; có thể tăng độ trễ")
        else:
            print("  • File video: đọc đủ mọi frame; cửa sổ có thể chậm hơn tốc độ video gốc")
        print(f"  • Thư mục lưu log: {output_dir}")
        print("=======================================================")

        venv_py = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        py_exe = str(venv_py) if venv_py.is_file() else sys.executable

        try:
            if algo == "1":
                # Chạy bằng tiến trình riêng như thuật toán 2/3: khi kết
                # thúc, hệ điều hành thu hồi toàn bộ RAM + thread torch,
                # máy không còn bị đơ/slow sau khi chạy xong thuật toán 1.
                script = str(SRC_DIR / "tiled_yolo11_camera.py")
                cmd = [
                    py_exe, script,
                    "--source", source,
                    "--output-dir", str(output_dir),
                    "--width", str(speed["width"]),
                    "--tile-imgsz", str(speed["tile_imgsz"]),
                    "--show",
                ]
                if save_mp4:
                    cmd.append("--save-video")
                subprocess.run(cmd, check=True)
            elif algo == "2":
                script = str(SRC_DIR / "motion_camera.py")
                cmd = [py_exe, script, "--source", source, "--output", str(output_dir), "--show", "--width", str(speed["cli_width"])]
                if save_mp4:
                    cmd.append("--save-video")
                subprocess.run(cmd, check=True)
            elif algo == "3":
                script = str(SRC_DIR / "yolo_camera.py")
                cmd = [py_exe, script, "--source", source, "--output", str(output_dir), "--show", "--width", str(speed["cli_width"])]
                if save_mp4:
                    cmd.append("--save-video")
                subprocess.run(cmd, check=True)

        except KeyboardInterrupt:
            print("\n[Hủy] Người dùng đã nhấn Ctrl+C.")
        except Exception as e:
            print(f"\n[Lỗi] Đã xảy ra lỗi: {e}")

        print("\nĐã quay về Menu chính.")


if __name__ == "__main__":
    main()
