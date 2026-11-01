"""
Live Serial Telemetry Processor & Computational Filter
------------------------------------------------------
Reads a continuous stream of CSV time/temperature packets ("<time_ms>,<temp_c>")
from an ESP32 / Arduino serial interface.

Implements from scratch (zero Pandas, zero SciPy):
1. Rolling Z-Score Outlier Detector (anomalous spike rejection)
2. Moving Average Filter (noise smoothing)
"""

import math
import sys
import time

try:
    import serial
except ImportError:
    serial = None


# =============================================================================
# 1. Computational Filtering Algorithms (From Scratch)
# =============================================================================

def compute_mean(data_window: list[float]) -> float:
    """Computes the arithmetic mean of a numeric sequence."""
    if not data_window:
        return 0.0
    return sum(data_window) / len(data_window)


def compute_std_dev(data_window: list[float], mean: float) -> float:
    """Computes the population standard deviation of a numeric sequence."""
    if len(data_window) < 2:
        return 0.0
    variance = sum((x - mean) ** 2 for x in data_window) / len(data_window)
    return math.sqrt(variance)


def is_zscore_outlier(
    candidate: float,
    history: list[float],
    window_size: int = 10,
    z_threshold: float = 3.0,
    min_samples: int = 5,
    min_noise_floor: float = 0.5
) -> tuple[bool, float]:
    """
    Evaluates whether candidate value is an outlier based on rolling Z-score.
    
    Formula:
        z = (x - mean) / max(std_dev, min_noise_floor)

    The 'min_noise_floor' parameter prevents false positives caused by
    quantization noise when sensor variance is near zero (DHT22 precision is ~0.5°C).
        
    Returns:
        (is_outlier, z_score)
    """
    # Use the most recent 'window_size' valid data points as reference baseline
    reference = history[-window_size:] if len(history) >= window_size else history[:]

    # Allow initial baseline buildup before discarding points
    if len(reference) < min_samples:
        return False, 0.0

    mean = compute_mean(reference)
    std_dev = compute_std_dev(reference, mean)

    # Prevent near-zero division & avoid rejecting normal sub-degree thermal drift
    effective_std = max(std_dev, min_noise_floor)
    z_score = (candidate - mean) / effective_std
    is_spike = abs(z_score) > z_threshold

    return is_spike, z_score


def apply_moving_average(data_history: list[float], window_size: int = 5) -> float:
    """
    Computes the simple moving average (SMA) over the last 'window_size' samples.
    
    Formula:
        SMA = (1 / k) * sum(x_i) for i in [t-k+1, t]
    """
    if not data_history:
        return 0.0
    
    # Grab the latest valid values up to window_size
    window = data_history[-window_size:]
    return sum(window) / len(window)


# =============================================================================
# 2. Telemetry Processing Pipeline
# =============================================================================

class SerialTelemetryProcessor:
    def __init__(
        self,
        port: str = "COM3",
        baudrate: int = 115200,
        z_threshold: float = 2.5,
        z_window_size: int = 10,
        ma_window_size: int = 5
    ):
        self.port = port
        self.baudrate = baudrate
        self.z_threshold = z_threshold
        self.z_window_size = z_window_size
        self.ma_window_size = ma_window_size

        # Data storage lists required by specification
        self.time_array: list[int] = []            # All raw timestamps received (ms)
        self.raw_data: list[float] = []            # All raw temperature values received (°C)
        self.filtered_data: list[float] = []        # Outlier-scrubbed & smoothed temperatures (°C)
        
        # Validated points baseline for outlier and MA evaluation
        self._accepted_temperatures: list[float] = []

    def process_sample(self, raw_time_ms: int, raw_temp_c: float) -> None:
        """Processes a single incoming telemetry packet."""
        # Store raw inputs
        self.time_array.append(raw_time_ms)
        self.raw_data.append(raw_temp_c)

        # 1. Z-Score Outlier Detection
        is_spike, z_val = is_zscore_outlier(
            candidate=raw_temp_c,
            history=self._accepted_temperatures,
            window_size=self.z_window_size,
            z_threshold=self.z_threshold
        )

        if is_spike:
            print(f"[{raw_time_ms:6d} ms] REJECTED SPIKE: {raw_temp_c:6.2f} °C (z = {z_val:+5.2f})")
            return

        # Record accepted candidate into valid baseline
        self._accepted_temperatures.append(raw_temp_c)

        # 2. Moving Average Smoothing
        smoothed_val = apply_moving_average(
            data_history=self._accepted_temperatures,
            window_size=self.ma_window_size
        )
        self.filtered_data.append(round(smoothed_val, 2))

        print(
            f"[{raw_time_ms:6d} ms] Raw: {raw_temp_c:5.1f} °C | "
            f"Filtered (SMA-{self.ma_window_size}): {smoothed_val:5.2f} °C (z = {z_val:+5.2f})"
        )

    def run_live_serial(self) -> None:
        """Opens the serial port and processes data in a real-time event loop."""
        if serial is None:
            print("ERROR: 'pyserial' is not installed. Install via: pip install pyserial")
            return

        print(f"Opening Serial port {self.port} at {self.baudrate} baud...")
        try:
            with serial.Serial(self.port, self.baudrate, timeout=1.0) as ser:
                # Flush initial stale bytes from serial buffer
                ser.reset_input_buffer()
                print("Listening for incoming telemetry... (Press Ctrl+C to stop)\n")

                while True:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue

                    # Expected input format: "<timestamp_ms>,<temperature_c>"
                    parts = line.split(",")
                    if len(parts) != 2:
                        continue

                    try:
                        timestamp_ms = int(parts[0].strip())
                        temp_c = float(parts[1].strip())
                        self.process_sample(timestamp_ms, temp_c)
                    except ValueError:
                        # Skip malformed lines (e.g. initialization text or "NAN")
                        continue

        except serial.SerialException as err:
            print(f"Serial Error: {err}")
        except KeyboardInterrupt:
            print("\nStream halted by user.")
            self._print_summary()

    def _print_summary(self) -> None:
        """Prints high-level stats of the collected arrays."""
        print("-" * 50)
        print("Telemetry Session Summary:")
        print(f"  Total raw packets received : {len(self.raw_data)}")
        print(f"  Accepted & filtered samples: {len(self.filtered_data)}")
        print(f"  Discarded anomalous spikes : {len(self.raw_data) - len(self.filtered_data)}")
        print("-" * 50)


# =============================================================================
# Standalone Execution / Demo
# =============================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Live Serial Telemetry Processor with Custom Filtering")
    parser.add_argument("--port", type=str, default="COM3", help="Serial port (e.g., COM3, /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--simulate", action="store_true", help="Run with simulated telemetry feed containing artificial spikes")
    args = parser.parse_args()

    processor = SerialTelemetryProcessor(
        port=args.port,
        baudrate=args.baud,
        z_threshold=2.5,     # Discard spikes beyond 2.5 standard deviations
        z_window_size=10,    # 10-sample rolling window for Z-score baseline
        ma_window_size=5     # 5-sample moving average window
    )

    if args.simulate:
        print("=== Running in Pure Software Simulation Mode ===")
        # Synthetic telemetry feed with normal noise and intentional anomalous spikes
        synthetic_stream = [
            (500,  24.4), (1000, 24.5), (1500, 24.6), (2000, 24.5), (2500, 24.5),
            (3000, 24.7), (3500, 24.6), (4000, 24.8), (4500, 24.6), (5000, 24.7),
            (5500, 89.9), # <--- ANOMALOUS SPIKE (e.g. sensor CRC error / bitflip)
            (6000, 24.8), (6500, 24.9), (7000, -15.0), # <--- ANOMALOUS SPIKE (negative drop)
            (7500, 24.9), (8000, 25.0), (8500, 25.1), (9000, 25.0)
        ]
        for t_ms, temp in synthetic_stream:
            processor.process_sample(t_ms, temp)
            time.sleep(0.05)
        processor._print_summary()
    else:
        processor.run_live_serial()
