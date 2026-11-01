"""
ESP32 + DHT22 Hardware Simulator & Telemetry Bridge
---------------------------------------------------
Simulates the exact firmware execution of the ESP32 in Wokwi:
- Runs an accurate 500ms sampling interval.
- Synthesizes AM2302 sensor physics (diurnal thermal wave + sensor noise).
- Injects 2% hardware glitch spikes (testing from-scratch Z-score rejection).
- Pushes JSON packets live to the Flask backend (POST http://localhost:5000/api/telemetry).
"""

import math
import random
import sys
import time
import urllib.request
import json

BACKEND_URL = "http://localhost:5000/api/telemetry"
INTERVAL_SECONDS = 0.5  # 500ms sampling rate matching ESP32 firmware

def run_hardware_bridge():
    print("=" * 65)
    print("  ESP32 DHT22 Virtual Hardware Simulator & Telemetry Bridge")
    print(f"  Target Backend Endpoint: {BACKEND_URL}")
    print(f"  Sampling Interval: {int(INTERVAL_SECONDS * 1000)} ms")
    print("=" * 65)
    print("Press Ctrl+C to stop simulation.\n")

    step = 0
    base_temp = 23.5

    while True:
        step += 1
        current_time_ms = step * 500

        # Thermodynamic model: slow drift + noise
        drift = math.sin(step * 0.02) * 4.0
        thermal_noise = (random.random() - 0.5) * 0.4
        temp = base_temp + drift + thermal_noise

        # 2% probability of extreme hardware glitch (outlier spike)
        is_glitch = False
        if random.random() < 0.02:
            is_glitch = True
            temp = random.choice([89.5, 94.2, -18.5, -22.0])

        payload = {
            "time": current_time_ms,
            "temperature": round(temp, 2)
        }

        try:
            req = urllib.request.Request(
                BACKEND_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=1.0) as res:
                res_data = json.loads(res.read().decode("utf-8"))
                buf_size = res_data.get("buffer_size", 0)
                rate = res_data.get("rate_of_change", 0.0)
                pred = res_data.get("predicted_temp", 0.0)

                glitch_tag = " [GLITCH SPIKE INJECTED]" if is_glitch else ""
                print(
                    f"[{current_time_ms:6d} ms] T: {temp:5.2f} °C{glitch_tag:<25} | "
                    f"Backend Status: {res.status} OK (Buf: {buf_size:2d}, dT/dt: {rate:+.3f}, Pred+20: {pred:5.2f}°C)"
                )
        except Exception as err:
            print(f"[{current_time_ms:6d} ms] Connection warning: {err} (Retrying...)")

        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        run_hardware_bridge()
    except KeyboardInterrupt:
        print("\nHardware simulation bridge stopped.")
