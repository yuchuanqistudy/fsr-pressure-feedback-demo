import csv
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

PORT = "/dev/cu.usbserial-310"
BAUD_RATE = 115200
ALPHA = 0.2
BASELINE = 0
CONTACT_ON = 50
CONTACT_OFF = 20
WINDOW_SECONDS = 10


def main():
    # 所有记录放在本程序旁边，不依赖终端当前所在目录。
    folder = Path(__file__).resolve().parent / "records"
    folder.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    csv_path = folder / f"fsr_{stamp}.csv"
    png_path = folder / f"fsr_{stamp}.png"
    times = deque(maxlen=1000)
    raw_values = deque(maxlen=1000)
    responses = deque(maxlen=1000)
    pending = bytearray()
    ema = None
    contact = False
    rows = 0

    fig, ax = plt.subplots(figsize=(10, 5))
    raw_line, = ax.plot([], [], color="gray", alpha=0.5, label="Raw")
    smooth_line, = ax.plot([], [], color="tab:orange", linewidth=2,
                           label=f"EMA (alpha={ALPHA})")
    ax.axhline(CONTACT_ON, color="tab:red", linestyle="--", label="ON: 50")
    ax.axhline(CONTACT_OFF, color="tab:green", linestyle=":", label="OFF: 20")
    ax.set(xlabel="PC receive time (s)", ylabel="ADC / response",
           ylim=(0, 1023), xlim=(0, WINDOW_SECONDS))
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    status = ax.text(0.98, 0.95, "NO CONTACT", transform=ax.transAxes,
                     ha="right", va="top", fontsize=13,
                     bbox=dict(facecolor="white", alpha=0.9))
    fig.tight_layout()

    try:
        with serial.Serial(PORT, BAUD_RATE, timeout=0) as arduino:
            time.sleep(2)
            arduino.reset_input_buffer()
            with csv_path.open("x", newline="", encoding="utf-8") as output:
                writer = csv.writer(output)
                writer.writerow([
                    "pc_receive_elapsed_s", "raw_adc", "ema_adc",
                    "response_adc", "contact", "baseline_adc", "alpha",
                    "contact_on_adc", "contact_off_adc", "fixed_resistor_ohm",
                ])
                start = time.monotonic()
                last_flush = start

                def update(_):
                    nonlocal ema, contact, rows, last_flush
                    try:
                        pending.extend(arduino.read(arduino.in_waiting))
                    except serial.SerialException as error:
                        print(f"串口断开：{error}")
                        plt.close(fig)
                        return raw_line, smooth_line, status

                    while b"\n" in pending:
                        raw, _, remainder = pending.partition(b"\n")
                        pending[:] = remainder
                        try:
                            value = int(raw.decode("ascii").strip())
                        except (UnicodeDecodeError, ValueError):
                            continue
                        if not 0 <= value <= 1023:
                            continue

                        ema = float(value) if ema is None else (
                            ALPHA * value + (1 - ALPHA) * ema
                        )
                        response = max(0.0, ema - BASELINE)
                        previous = contact
                        if not contact and response >= CONTACT_ON:
                            contact = True
                        elif contact and response <= CONTACT_OFF:
                            contact = False
                        elapsed = time.monotonic() - start
                        writer.writerow([
                            f"{elapsed:.6f}", value, f"{ema:.6f}",
                            f"{response:.6f}", int(contact), BASELINE,
                            ALPHA, CONTACT_ON, CONTACT_OFF, 1000,
                        ])
                        rows += 1
                        times.append(elapsed)
                        raw_values.append(value)
                        responses.append(response)
                        if previous != contact:
                            state = "接触" if contact else "未接触"
                            print(f"{elapsed:.2f} 秒 | {state} | 响应 {response:.1f}")

                    now = time.monotonic()
                    if now - last_flush >= 1:
                        output.flush()
                        last_flush = now
                    raw_line.set_data(list(times), list(raw_values))
                    smooth_line.set_data(list(times), list(responses))
                    elapsed = now - start
                    ax.set_xlim(max(0, elapsed - WINDOW_SECONDS),
                                max(WINDOW_SECONDS, elapsed))
                    state = "CONTACT" if contact else "NO CONTACT"
                    status.set_text(state)
                    status.set_color("tab:red" if contact else "tab:green")
                    if responses:
                        ax.set_title(f"FSR | Response: {responses[-1]:.1f} | Rows: {rows}")
                    return raw_line, smooth_line, status

                animation = FuncAnimation(fig, update, interval=40,
                                          cache_frame_data=False)
                print(f"记录文件：{csv_path}")
                print("关闭曲线窗口，结束记录并保存最后一个画面。")
                try:
                    plt.show()
                finally:
                    output.flush()
                    if rows:
                        fig.savefig(png_path, dpi=180)
                        print(f"已保存 {rows} 行：{csv_path}")
                        print(f"最后约 10 秒曲线：{png_path}")
    except serial.SerialException as error:
        print(f"串口错误：{error}")
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        plt.close(fig)


if __name__ == "__main__":
    main()
