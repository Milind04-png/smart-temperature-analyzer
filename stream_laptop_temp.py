"""
Real Laptop Hardware Temperature Streamer
-----------------------------------------
Reads live physical GPU temperature directly from your laptop hardware
using nvidia-smi and streams it into the Smart Temperature Analyzer dashboard!
"""

import subprocess
import time
import urllib.request
import json

BACKEND_URL = "http://localhost:5000/api/telemetry"

def get_gpu_temperature():
    cmd = ['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader,nounits']
    out = subprocess.check_output(cmd, text=True).strip()
    return float(out)

def stream_laptop_thermals():
    print("=" * 60)
    print("  Streaming REAL Laptop Hardware Temperature to Dashboard")
    print(f"  Target Backend: {BACKEND_URL}")
    print("=" * 60)
    step = 0

    while True:
        step += 1
        try:
            temp = get_gpu_temperature()
            payload = {"time": step * 500, "temperature": temp}
            req = urllib.request.Request(
                BACKEND_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=1.0) as res:
                print(f"[{step * 500:6d} ms] Physical Laptop GPU Temp: {temp:.1f} °C -> Streamed to Dashboard (200 OK)")
        except Exception as e:
            print(f"Streaming error: {e}")
        time.sleep(1.0)

if __name__ == "__main__":
    stream_laptop_thermals()
