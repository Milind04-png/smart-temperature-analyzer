"""
SMART TEMPERATURE DATA ANALYSER
-------------------------------
Course: Data Base Management System (DBMS)
Department: Computer Science & Engineering
Batch: 2025-2029 | Section: D G-3

Presented By:
- Vaneesha Singh (21818002725)
- Anisha Dubey (22018002725)
- Amritanshu Mishra (22218002725)
- Sumit Chourasia (22618002725)
- Milind Shukla (22718002725)

Implements exactly the required functions from Slide 17:
- lagrange(xs, ys, x)
- divided_differences(xs, ys)
- newton(xs, ys, x)
- nearest_four(xs, ys, x)
- trapezoid(xs, ys)
- simpson(xs, ys)
"""

import os
import matplotlib.pyplot as plt
from dbms_database import get_connection, init_dbms_database, seed_sample_readings


# =============================================================================
# Core Mathematical Algorithms (Slide 14 & 17)
# =============================================================================

def lagrange(xs: list[float], ys: list[float], x: float) -> float:
    """
    Lagrange Interpolation Polynomial:
        P(x) = sum_{i=0}^n y_i * L_i(x)
        L_i(x) = prod_{j != i} (x - x_j) / (x_i - x_j)
    """
    total = 0.0
    n = len(xs)
    for i in range(n):
        term = ys[i]
        for j in range(n):
            if j != i:
                term *= (x - xs[j]) / (xs[i] - xs[j])
        total += term
    return total


def divided_differences(xs: list[float], ys: list[float]) -> list[list[float]]:
    """
    Constructs the Newton Divided Difference Table:
        f[x_i..x_{i+k}] = (f[x_{i+1}..x_{i+k}] - f[x_i..x_{i+k-1}]) / (x_{i+k} - x_i)
    """
    n = len(xs)
    table = [[0.0] * n for _ in range(n)]
    for i in range(n):
        table[i][0] = ys[i]

    for j in range(1, n):
        for i in range(n - j):
            table[i][j] = (table[i + 1][j - 1] - table[i][j - 1]) / (xs[i + j] - xs[i])

    return table


def newton(xs: list[float], ys: list[float], x: float) -> float:
    """
    Evaluates the Newton Divided Difference Polynomial using Horner's nested form:
        P(x) = f[x_0] + f[x_0, x_1](x - x_0) + ...
    """
    table = divided_differences(xs, ys)
    n = len(xs)
    result = table[0][n - 1]
    for i in range(n - 2, -1, -1):
        result = result * (x - xs[i]) + table[0][i]
    return result


def nearest_four(xs: list[float], ys: list[float], x: float) -> tuple[list[float], list[float]]:
    """
    Selects the 4 nearest measured nodes around the gap x to prevent
    Runge's phenomenon associated with high-degree polynomials (Slide 8).
    """
    paired = sorted(zip(xs, ys), key=lambda pt: abs(pt[0] - x))
    chosen = sorted(paired[:4], key=lambda pt: pt[0])
    return [pt[0] for pt in chosen], [pt[1] for pt in chosen]


def trapezoid(xs: list[float], ys: list[float]) -> float:
    """
    Trapezoidal Rule for numerical integration (Slide 16):
        E approx sum_{i=0}^{n-1} (h/2) * (T_i + T_{i+1})
        For uniform spacing h: (h/2) * [T_0 + 2*sum(T_interior) + T_n]
    """
    n = len(ys)
    if n < 2:
        return 0.0
    h = xs[1] - xs[0]
    total = ys[0] + ys[-1] + 2.0 * sum(ys[1:-1])
    return (h / 2.0) * total


def simpson(xs: list[float], ys: list[float]) -> float:
    """
    Simpson's 1/3 Rule for numerical integration (Slide 16):
        E approx (h/3) * [T_0 + 4*sum(T_odd) + 2*sum(T_even) + T_n]
        Requires an even number of intervals n (odd number of points).
    """
    n = len(ys) - 1
    if n % 2 != 0:
        raise ValueError("Simpson 1/3 requires an even number of intervals.")
    h = xs[1] - xs[0]
    total = ys[0] + ys[-1]
    for i in range(1, n):
        total += (4.0 if i % 2 == 1 else 2.0) * ys[i]
    return (h / 3.0) * total


# =============================================================================
# Execution Pipeline & Presentation Output (Slide 21)
# =============================================================================

def run_analysis(plot_graphs: bool = True):
    # Ensure database is prepared
    init_dbms_database()
    seed_sample_readings()

    conn = get_connection()
    cursor = conn.cursor()

    # Step 1: Read readings from database (Slide 17 Step 1)
    cursor.execute("SELECT reading_id, time_hr, temp_c, is_missing FROM READING ORDER BY time_hr")
    rows = cursor.fetchall()

    measured_xs = []
    measured_ys = []
    missing_times = []

    for r in rows:
        if r["is_missing"] == 0:
            measured_xs.append(r["time_hr"])
            measured_ys.append(r["temp_c"])
        else:
            missing_times.append(r["time_hr"])

    # Step 2 & 3: Find gaps and estimate using nearest 4 nodes (Slide 17 Steps 2 & 3)
    completed_series = {}
    for r in rows:
        t = r["time_hr"]
        if r["is_missing"] == 0:
            completed_series[t] = r["temp_c"]
        else:
            nx, ny = nearest_four(measured_xs, measured_ys, t)
            lagrange_val = lagrange(nx, ny, t)
            newton_val = newton(nx, ny, t)
            abs_err = abs(lagrange_val - newton_val)
            completed_series[t] = lagrange_val

            # Store in ESTIMATE table (Slide 10)
            cursor.execute("""
                INSERT INTO ESTIMATE (reading_id, method, est_temp_c, abs_error)
                VALUES (?, 'Lagrange', ?, ?)
            """, (r["reading_id"], lagrange_val, abs_err))
            cursor.execute("""
                INSERT INTO ESTIMATE (reading_id, method, est_temp_c, abs_error)
                VALUES (?, 'Newton', ?, ?)
            """, (r["reading_id"], newton_val, abs_err))

    # Calculate 11:00 worked example values (Slide 15 & 21)
    nodes_11_x, nodes_11_y = nearest_four(measured_xs, measured_ys, 11.0)
    lag_11 = lagrange(nodes_11_x, nodes_11_y, 11.0)
    newt_11 = newton(nodes_11_x, nodes_11_y, 11.0)
    diff_table_11 = divided_differences(nodes_11_x, nodes_11_y)

    # Step 4: Validation Hold-out check (Slide 15 & 21: hide t=12, estimate from 8,10,14,16)
    val_nodes_x = [8.0, 10.0, 14.0, 16.0]
    val_nodes_y = [27.5, 31.2, 35.6, 33.1]
    val_estimate = lagrange(val_nodes_x, val_nodes_y, 12.0)
    actual_12 = 34.8
    val_error = abs(actual_12 - val_estimate)

    # Step 5: Numerical Integration (Slide 16 & 21)
    # 2 h data (7 readings, 6 intervals of h=2)
    trap_2h = trapezoid(measured_xs, measured_ys)
    simp_2h = simpson(measured_xs, measured_ys)

    # Hourly series (13 readings, 12 intervals of h=1)
    sorted_hourly_t = sorted(completed_series.keys())
    sorted_hourly_y = [completed_series[t] for t in sorted_hourly_t]
    simp_hourly = simpson(sorted_hourly_t, sorted_hourly_y)
    mean_temp = simp_hourly / 12.0

    # Store final exposure in EXPOSURE_REPORT table (Slide 10)
    cursor.execute("""
        INSERT INTO EXPOSURE_REPORT (sensor_id, start_hr, end_hr, exposure_cdeg_h)
        VALUES (1, 6.0, 18.0, ?)
    """, (simp_hourly,))
    conn.commit()
    conn.close()

    # =========================================================================
    # Terminal Output: EXACT MATCH TO SLIDE 21
    # =========================================================================
    print("=== SMART TEMPERATURE DATA ANALYSER ===\n")
    print(f"[1] Missing reading at t = 11 h (nodes: {[int(x) for x in nodes_11_x]})")
    print(f"    Lagrange            : {lag_11:.4f} C")
    print(f"    Newton divided diff : {newt_11:.4f} C\n")

    print("[2] Divided-difference table")
    for order in range(1, 4):
        vals = [f"{diff_table_11[i][order]:.5f}" for i in range(len(nodes_11_x) - order)]
        print(f"    order {order} : {vals}\n" if order == 3 else f"    order {order} : {vals}")

    print(f"[3] Validation (hide t = 12, estimate from 8,10,14,16)")
    print(f"    estimate {val_estimate:.3f} C | actual {actual_12:.3f} C | error {val_error:.3f} C\n")

    print("[5] Cumulative temperature exposure, 06:00 -> 18:00")
    print(f"    Trapezoidal (2 h data)  : {trap_2h:.2f} C.h")
    print(f"    Simpson 1/3 (2 h data)  : {simp_2h:.2f} C.h")
    print(f"    Simpson 1/3 (hourly)    : {simp_hourly:.2f} C.h")
    print(f"    Mean temperature        : {mean_temp:.2f} C")

    # =========================================================================
    # Step 6: Generate Matplotlib Plots Matching Slide 19
    # =========================================================================
    if plot_graphs:
        generate_slide_19_plots(sorted_hourly_t, sorted_hourly_y, measured_xs, measured_ys)

    return {
        "t_11_lagrange": lag_11,
        "t_11_newton": newt_11,
        "val_estimate": val_estimate,
        "val_actual": actual_12,
        "val_error": val_error,
        "trap_2h": trap_2h,
        "simp_2h": simp_2h,
        "simp_hourly": simp_hourly,
        "mean_temp": mean_temp,
        "hourly_t": sorted_hourly_t,
        "hourly_y": sorted_hourly_y
    }


def generate_slide_19_plots(hourly_t, hourly_y, measured_xs, measured_ys):
    """Generates the two exact charts shown in Slide 19."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5), dpi=120)

    # Chart 1: Reconstructed temperature (°C)
    time_labels = [f"{int(t):02d}:00" for t in hourly_t]
    ax1.plot(time_labels, hourly_y, marker="o", color="#0284c7", linewidth=2.2, markersize=6)
    ax1.set_title("Reconstructed temperature (°C)", fontsize=13, fontweight="bold", pad=10)
    ax1.set_ylabel("°C", fontsize=11)
    ax1.set_ylim(20, 38)
    ax1.set_yticks([20, 24, 28, 32, 36])
    ax1.tick_params(axis="x", rotation=45)
    ax1.grid(True, linestyle=":", alpha=0.6)

    # Chart 2: Cumulative exposure (°C·h)
    cum_exposure = [0.0]
    for i in range(1, len(measured_xs)):
        # Trapezoidal area on 2 h segments
        area = 0.5 * (measured_ys[i - 1] + measured_ys[i]) * (measured_xs[i] - measured_xs[i - 1])
        cum_exposure.append(cum_exposure[-1] + area)

    meas_labels = [f"{int(t):02d}:00" for t in measured_xs]
    ax2.plot(meas_labels, cum_exposure, marker="o", color="#dc2626", linewidth=2.2, markersize=6)
    for x_lbl, val in zip(meas_labels, cum_exposure):
        ax2.annotate(f"{val:.1f}", (x_lbl, val), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9, fontweight="bold")

    ax2.set_title("Cumulative exposure (°C·h)", fontsize=13, fontweight="bold", pad=10)
    ax2.set_ylabel("°C·h", fontsize=11)
    ax2.set_ylim(0, 450)
    ax2.set_yticks([0, 50, 100, 150, 200, 250, 300, 350, 400, 450])
    ax2.grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    output_img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reconstructed_results.png")
    plt.savefig(output_img_path)
    plt.close()
    print(f"\n[INFO] Slide 19 verification plots generated -> '{output_img_path}'")


if __name__ == "__main__":
    run_analysis(plot_graphs=True)
