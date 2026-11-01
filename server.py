"""
Smart Temperature Analyzer - Enhanced Flask Backend & Telemetry Bridge
-----------------------------------------------------------------------
Full Wokwi & Real Hardware Integration:
- Ingests live telemetry packets from ESP32 / Wokwi via POST /api/telemetry.
- Serves real-time rolling calculations via GET /api/live.
- Provides 500-sample diurnal batch analysis via GET /api/data.
- SQLite Database logging (temperature_logs.db).
- Pure Python mathematics (zero Pandas, SciPy, or scikit-learn).
"""

import datetime
import math
import os
import random
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "temperature_logs.db")

# In-memory rolling live telemetry buffers
LIVE_RAW_BUFFER = []        # Raw incoming packets: [{"x": t_ms, "y": temp_c}]
LIVE_FILTERED_BUFFER = []   # Outlier-cleaned & smoothed packets
LIVE_OUTLIERS = []          # Detected glitch spikes
MAX_LIVE_BUFFER = 150       # Rolling capacity for smooth charting


# =============================================================================
# 1. SQLite Database Setup & Operations
# =============================================================================

def init_db():
    """Initializes SQLite database and creates/migrates the predictions table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            current_temp REAL NOT NULL,
            rate_of_change REAL NOT NULL,
            predicted_temp_in_20_steps REAL NOT NULL,
            source TEXT DEFAULT 'BATCH_SIMULATION'
        )
    """)
    # Check if 'source' column exists in existing database; add it if missing
    cursor.execute("PRAGMA table_info(predictions)")
    columns = [row[1] for row in cursor.fetchall()]
    if "source" not in columns:
        cursor.execute("ALTER TABLE predictions ADD COLUMN source TEXT DEFAULT 'BATCH_SIMULATION'")
    conn.commit()
    conn.close()

# Ensure database table is initialized/migrated
init_db()


def log_prediction(current_temp: float, rate_of_change: float, predicted_temp_20: float, source: str = "BATCH_SIMULATION") -> int:
    """Inserts a prediction snapshot into SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO predictions (timestamp, current_temp, rate_of_change, predicted_temp_in_20_steps, source)
        VALUES (?, ?, ?, ?, ?)
    """, (now_str, current_temp, rate_of_change, predicted_temp_20, source))
    conn.commit()
    inserted_id = cursor.lastrowid
    conn.close()
    return inserted_id


def get_recent_history(limit: int = 10) -> list[dict]:
    """Retrieves the last N records from SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, current_temp, rate_of_change, predicted_temp_in_20_steps, source
        FROM predictions
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# =============================================================================
# 2. Fundamental Computational Algorithms (From Scratch)
# =============================================================================

def generate_synthetic_temperature_data(num_points: int = 500) -> list[dict]:
    """Generates 500-sample diurnal sine wave + Gaussian noise + extreme spikes."""
    base_temp = 22.0
    amplitude = 7.5
    noise_sigma = 0.65
    outlier_count = int(num_points * 0.015)
    outlier_indices = set(random.sample(range(num_points), outlier_count))

    dataset = []
    for t in range(num_points):
        angle = (2.0 * math.pi * t / num_points) - (math.pi / 2.0)
        temp = base_temp + amplitude * math.sin(angle) + random.gauss(0.0, noise_sigma)

        if t in outlier_indices:
            temp = random.uniform(70.0, 95.0) if random.random() < 0.5 else random.uniform(-25.0, -10.0)

        dataset.append({"x": t, "y": round(temp, 2)})
    return dataset


def remove_outliers_zscore(
    raw_data: list[dict],
    z_threshold: float = 3.0,
    window_size: int = 25
) -> tuple[list[dict], list[dict]]:
    """Rolling Z-score outlier detection from scratch."""
    clean_data, outliers = [], []
    n = len(raw_data)
    min_noise_floor = 0.5

    for i in range(n):
        val = raw_data[i]["y"]
        t = raw_data[i]["x"]

        start = max(0, i - window_size // 2)
        end = min(n, i + window_size // 2 + 1)
        window = [raw_data[j]["y"] for j in range(start, end) if j != i]

        if len(window) < 3:
            clean_data.append({"x": t, "y": val})
            continue

        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        std_dev = math.sqrt(variance)
        effective_std = max(std_dev, min_noise_floor)

        z = abs(val - mean) / effective_std
        if z > z_threshold:
            outliers.append({"x": t, "y": val, "z": round(z, 2)})
        else:
            clean_data.append({"x": t, "y": val})

    return clean_data, outliers


def apply_moving_average_filter(data: list[dict], window_size: int = 7) -> list[dict]:
    """Moving Average filter built from scratch."""
    n = len(data)
    if n == 0:
        return []

    half_w = window_size // 2
    smoothed_data = []

    for i in range(n):
        start = max(0, i - half_w)
        end = min(n, i + half_w + 1)
        window_vals = [data[j]["y"] for j in range(start, end)]
        avg = sum(window_vals) / len(window_vals)
        smoothed_data.append({"x": data[i]["x"], "y": round(avg, 2)})

    return smoothed_data


def calculate_latest_rate_of_change(data: list[dict]) -> float:
    """Calculates instantaneous rate of change (dT/dt) at the latest point."""
    if len(data) < 2:
        return 0.0
    dt = data[-1]["x"] - data[-2]["x"]
    if dt == 0:
        return 0.0
    return round((data[-1]["y"] - data[-2]["y"]) / dt, 4)


def linear_least_squares_predict(
    data: list[dict],
    window_pts: int = 50,
    future_steps: int = 20
) -> list[dict]:
    """Linear Least Squares regression on the last 'window_pts' points to project future trend."""
    n_pts = min(window_pts, len(data))
    if n_pts < 2:
        return []

    sub = data[-n_pts:]
    N = float(n_pts)
    sum_x = sum(pt["x"] for pt in sub)
    sum_y = sum(pt["y"] for pt in sub)
    sum_xy = sum(pt["x"] * pt["y"] for pt in sub)
    sum_x2 = sum(pt["x"] ** 2 for pt in sub)

    denom = N * sum_x2 - (sum_x ** 2)
    if abs(denom) < 1e-12:
        slope = 0.0
        intercept = sum_y / N
    else:
        slope = (N * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / N

    last_x = data[-1]["x"]
    avg_dt = (sub[-1]["x"] - sub[0]["x"]) / (n_pts - 1) if n_pts > 1 else 1.0

    predictions = [{"x": last_x, "y": round(slope * last_x + intercept, 2)}]
    for step in range(1, future_steps + 1):
        future_x = last_x + (step * avg_dt)
        predictions.append({"x": round(future_x, 1), "y": round(slope * future_x + intercept, 2)})

    return predictions


# =============================================================================
# 3. Flask API Endpoints
# =============================================================================

@app.route("/")
def index():
    """Serves the dashboard index.html."""
    html_path = os.path.join(BASE_DIR, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@app.route("/api/telemetry", methods=["POST"])
def ingest_telemetry():
    """
    Ingests live telemetry packets from ESP32 / Wokwi simulation.
    Accepts JSON: {"time": <millis_or_step>, "temperature": <celsius>}
    """
    global LIVE_RAW_BUFFER, LIVE_FILTERED_BUFFER, LIVE_OUTLIERS

    content = request.get_json(silent=True) or {}
    t_val = content.get("time") or content.get("time_ms") or content.get("x")
    temp_val = content.get("temperature") or content.get("temp") or content.get("y")

    if t_val is None or temp_val is None:
        return jsonify({"status": "error", "message": "Missing 'time' or 'temperature' fields"}), 400

    try:
        t = float(t_val)
        val = float(temp_val)
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid numeric values"}), 400

    # Append to rolling live buffer
    LIVE_RAW_BUFFER.append({"x": t, "y": val})
    if len(LIVE_RAW_BUFFER) > MAX_LIVE_BUFFER:
        LIVE_RAW_BUFFER.pop(0)

    # Real-time filtering on rolling buffer
    clean_buf, outliers = remove_outliers_zscore(LIVE_RAW_BUFFER, z_threshold=3.0, window_size=20)
    LIVE_OUTLIERS = outliers
    LIVE_FILTERED_BUFFER = apply_moving_average_filter(clean_buf, window_size=5)

    # Compute live metrics
    rate_of_change = calculate_latest_rate_of_change(LIVE_FILTERED_BUFFER)
    latest_temp = LIVE_FILTERED_BUFFER[-1]["y"] if LIVE_FILTERED_BUFFER else val
    pred_data = linear_least_squares_predict(LIVE_FILTERED_BUFFER, window_pts=30, future_steps=15)
    pred_temp = pred_data[-1]["y"] if pred_data else latest_temp

    # Periodic SQLite logging (every 10 packets to avoid DB congestion)
    if len(LIVE_RAW_BUFFER) % 10 == 0:
        log_prediction(latest_temp, rate_of_change, pred_temp, source="WOKWI_LIVE_TELEMETRY")

    return jsonify({
        "status": "success",
        "buffer_size": len(LIVE_RAW_BUFFER),
        "latest_temp": latest_temp,
        "rate_of_change": rate_of_change,
        "predicted_temp": pred_temp
    })


@app.route("/api/live", methods=["GET"])
def get_live_telemetry():
    """Returns the current rolling live telemetry buffer, filtered signal, and prediction."""
    latest_temp = LIVE_FILTERED_BUFFER[-1]["y"] if LIVE_FILTERED_BUFFER else (LIVE_RAW_BUFFER[-1]["y"] if LIVE_RAW_BUFFER else 0.0)
    rate_of_change = calculate_latest_rate_of_change(LIVE_FILTERED_BUFFER)
    pred_data = linear_least_squares_predict(LIVE_FILTERED_BUFFER, window_pts=30, future_steps=15)
    pred_temp = pred_data[-1]["y"] if pred_data else latest_temp

    return jsonify({
        "status": "success",
        "live_count": len(LIVE_RAW_BUFFER),
        "latest_temp": latest_temp,
        "rate_of_change": rate_of_change,
        "predicted_temp_20": pred_temp,
        "outlier_count": len(LIVE_OUTLIERS),
        "raw_data": LIVE_RAW_BUFFER,
        "filtered_data": LIVE_FILTERED_BUFFER,
        "predicted_data": pred_data
    })


@app.route("/api/data", methods=["GET"])
def get_temperature_data():
    """Generates synthetic 500-sample diurnal dataset, runs all filters, logs to SQLite."""
    raw_data = generate_synthetic_temperature_data(500)
    clean_data, outliers = remove_outliers_zscore(raw_data, z_threshold=3.0)
    filtered_data = apply_moving_average_filter(clean_data, window_size=7)
    rate_of_change = calculate_latest_rate_of_change(filtered_data)
    latest_temp = filtered_data[-1]["y"] if filtered_data else 0.0
    predicted_data = linear_least_squares_predict(filtered_data, window_pts=50, future_steps=20)
    final_pred_temp = predicted_data[-1]["y"] if predicted_data else latest_temp

    log_id = log_prediction(latest_temp, rate_of_change, final_pred_temp, source="BATCH_SIMULATION")

    return jsonify({
        "status": "success",
        "log_id": log_id,
        "latest_temp": latest_temp,
        "rate_of_change": rate_of_change,
        "predicted_temp_20": final_pred_temp,
        "outlier_count": len(outliers),
        "raw_data": raw_data,
        "filtered_data": filtered_data,
        "predicted_data": predicted_data
    })


@app.route("/api/history", methods=["GET"])
def get_prediction_history():
    """Returns the last 10 simulation prediction logs from SQLite."""
    return jsonify({
        "status": "success",
        "history": get_recent_history(limit=10)
    })


@app.route("/api/clear", methods=["POST"])
def clear_live_buffer():
    """Flushes the live telemetry buffer."""
    global LIVE_RAW_BUFFER, LIVE_FILTERED_BUFFER, LIVE_OUTLIERS
    LIVE_RAW_BUFFER.clear()
    LIVE_FILTERED_BUFFER.clear()
    LIVE_OUTLIERS.clear()
    return jsonify({"status": "success", "message": "Live telemetry buffer reset"})


@app.route("/api/wokwi-project", methods=["GET"])
def get_wokwi_project():
    """Returns firmware and diagram files for 1-click Wokwi simulation."""
    sketch_path = os.path.join(BASE_DIR, "sketch.ino")
    diagram_path = os.path.join(BASE_DIR, "diagram.json")

    with open(sketch_path, "r", encoding="utf-8") as f:
        sketch_code = f.read()
    with open(diagram_path, "r", encoding="utf-8") as f:
        diagram_code = f.read()

    return jsonify({
        "sketch": sketch_code,
        "diagram": diagram_code,
        "wokwi_url": "https://wokwi.com/projects/new/esp32"
    })


# =============================================================================
# Main Entry Point
# =============================================================================
if __name__ == "__main__":
    init_db()
    print("SQLite database verified: 'temperature_logs.db'")
    print("Smart Temperature Analyzer running at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
