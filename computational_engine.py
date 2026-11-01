"""
Computational Temperature Analysis Engine
------------------------------------------
Implements from scratch (zero Pandas, zero NumPy, zero SciPy):
1. CSV reading & ingestion
2. Rolling Z-Score outlier detection
3. Exponential Smoothing filter
4. Central Finite Difference numerical differentiation (dT/dt)
5. Linear Least Squares regression & future projection (20 steps)
6. Trapezoidal Rule numerical integration (cumulative thermal exposure)
"""

import csv
import math


# =============================================================================
# 1. CSV Data Ingestion
# =============================================================================

def read_temperature_csv(filepath: str) -> tuple[list[float], list[float]]:
    """
    Reads CSV file containing 'Time' and 'Raw_Temperature' columns from scratch.
    
    Returns:
        (time_array, raw_temperatures)
    """
    times = []
    temperatures = []
    with open(filepath, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # Skip header row: ["Time", "Raw_Temperature"]
        for row in reader:
            if not row or len(row) < 2:
                continue
            try:
                t = float(row[0].strip())
                val = float(row[1].strip())
                times.append(t)
                temperatures.append(val)
            except ValueError:
                continue
    return times, temperatures


# =============================================================================
# 2. Computational Filtering Algorithms (From Scratch)
# =============================================================================

def remove_outliers_zscore(
    times: list[float],
    temperatures: list[float],
    window_size: int = 30,
    z_threshold: float = 3.0,
    min_noise_floor: float = 0.5
) -> tuple[list[float], list[float], list[tuple[float, float]]]:
    """
    Applies sliding-window Z-Score outlier rejection to identify and remove anomalous spikes.
    
    Returns:
        (clean_times, clean_temperatures, discarded_outliers)
    """
    clean_times = []
    clean_temps = []
    outliers = []
    n = len(temperatures)

    for i in range(n):
        val = temperatures[i]
        t = times[i]

        # Define symmetric sliding window boundaries
        start = max(0, i - window_size // 2)
        end = min(n, i + window_size // 2 + 1)
        
        # Reference neighborhood excluding candidate point to prevent self-masking
        window = [temperatures[j] for j in range(start, end) if j != i]

        if len(window) < 3:
            clean_times.append(t)
            clean_temps.append(val)
            continue

        # Compute mean
        mean = sum(window) / len(window)

        # Compute standard deviation
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        std_dev = math.sqrt(variance)

        # Apply noise floor to avoid false positives when local variation is minute
        effective_std = max(std_dev, min_noise_floor)
        z_score = abs(val - mean) / effective_std

        if z_score > z_threshold:
            outliers.append((t, val))
        else:
            clean_times.append(t)
            clean_temps.append(val)

    return clean_times, clean_temps, outliers


def apply_exponential_smoothing(
    temperatures: list[float],
    alpha: float = 0.15
) -> list[float]:
    """
    Applies Single Exponential Smoothing filter entirely from scratch:
        S_0 = Y_0
        S_t = alpha * Y_t + (1 - alpha) * S_{t-1}
        
    Parameters:
        temperatures: Cleaned data list.
        alpha: Smoothing factor (0 < alpha <= 1). Lower values = smoother curve.
        
    Returns:
        A new list containing smoothed temperature values.
    """
    if not temperatures:
        return []

    smoothed = [temperatures[0]]
    for t in range(1, len(temperatures)):
        s_prev = smoothed[-1]
        y_curr = temperatures[t]
        s_curr = alpha * y_curr + (1.0 - alpha) * s_prev
        smoothed.append(s_curr)

    return smoothed


# =============================================================================
# 3. Numerical Analysis Algorithms (From Scratch)
# =============================================================================

def calculate_derivative_central_difference(
    times: list[float],
    temperatures: list[float]
) -> list[float]:
    """
    Calculates the first derivative (dT/dt) using the Central Finite Difference method:
        - Internal points:  dT/dt_i = (T_{i+1} - T_{i-1}) / (t_{i+1} - t_{i-1})
        - Left boundary:    dT/dt_0 = (T_1 - T_0) / (t_1 - t_0)         [Forward]
        - Right boundary:   dT/dt_{N-1} = (T_{N-1} - T_{N-2}) / (t_{N-1} - t_{N-2}) [Backward]
        
    Returns:
        List of instantaneous derivatives (rates of temperature change).
    """
    n = len(temperatures)
    if n < 2:
        return [0.0] * n

    derivatives = [0.0] * n

    # Forward difference at initial boundary
    dt_0 = times[1] - times[0]
    derivatives[0] = (temperatures[1] - temperatures[0]) / dt_0 if dt_0 != 0 else 0.0

    # Central difference for interior points
    for i in range(1, n - 1):
        dt = times[i + 1] - times[i - 1]
        derivatives[i] = (temperatures[i + 1] - temperatures[i - 1]) / dt if dt != 0 else 0.0

    # Backward difference at final boundary
    dt_end = times[-1] - times[-2]
    derivatives[-1] = (temperatures[-1] - temperatures[-2]) / dt_end if dt_end != 0 else 0.0

    return derivatives


def linear_least_squares_predict(
    times: list[float],
    temperatures: list[float],
    window_pts: int = 50,
    future_steps: int = 20
) -> tuple[float, float, list[float], list[float], list[float], list[float]]:
    """
    Calculates Linear Least Squares regression on the last 'window_pts' data points:
        slope (m) = [N * sum(x*y) - sum(x)*sum(y)] / [N * sum(x^2) - (sum(x))^2]
        intercept (c) = [sum(y) - m * sum(x)] / N
        
    Projects 'future_steps' steps ahead into the future.
    
    Returns:
        (slope, intercept, reg_times, reg_fit, future_times, future_preds)
    """
    n_pts = min(window_pts, len(temperatures))
    x_sub = times[-n_pts:]
    y_sub = temperatures[-n_pts:]

    N = float(n_pts)
    sum_x = sum(x_sub)
    sum_y = sum(y_sub)
    sum_xy = sum(x * y for x, y in zip(x_sub, y_sub))
    sum_x2 = sum(x ** 2 for x in x_sub)

    denom = N * sum_x2 - (sum_x ** 2)
    if abs(denom) < 1e-12:
        slope = 0.0
        intercept = sum_y / N
    else:
        slope = (N * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / N

    # Trendline over regression window
    reg_fit = [slope * x + intercept for x in x_sub]

    # Predict future steps
    dt_avg = (x_sub[-1] - x_sub[0]) / (n_pts - 1) if n_pts > 1 else 1.0
    future_times = [x_sub[-1] + (k + 1) * dt_avg for k in range(future_steps)]
    future_preds = [slope * tf + intercept for tf in future_times]

    return slope, intercept, x_sub, reg_fit, future_times, future_preds


def trapezoidal_rule_integration(
    times: list[float],
    temperatures: list[float]
) -> tuple[float, list[float]]:
    """
    Calculates the numerical integral (area under curve) using the Trapezoidal Rule:
        Integral = sum_{i=0}^{N-2} 0.5 * (T_i + T_{i+1}) * (t_{i+1} - t_i)
        
    Represents cumulative thermal exposure (°C * time units).
    
    Returns:
        (total_integral, cumulative_exposure_curve)
    """
    n = len(temperatures)
    if n < 2:
        return 0.0, [0.0] * n

    total_exposure = 0.0
    cumulative_curve = [0.0]

    for i in range(n - 1):
        dt = times[i + 1] - times[i]
        trapezoid_area = 0.5 * (temperatures[i] + temperatures[i + 1]) * dt
        total_exposure += trapezoid_area
        cumulative_curve.append(total_exposure)

    return total_exposure, cumulative_curve
