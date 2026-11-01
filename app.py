"""
Interactive Computational Temperature Analyzer Dashboard
--------------------------------------------------------
Data Visualization built with Streamlit & Matplotlib.

Visualizes:
1. Raw noisy synthetic data (scatter points) & detected glitch outliers
2. Smoothed/filtered computational data (solid line via Exponential Smoothing)
3. Linear Least Squares predictive trendline projected 20 steps into the future (dashed line)
4. Instantaneous rate of change (Central Finite Difference) and Cumulative Thermal Exposure (Trapezoidal Rule)
"""

import os
import sys

# Ensure current script directory is in sys.path for local module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# Import computational algorithms implemented from scratch
from computational_engine import (
    read_temperature_csv,
    remove_outliers_zscore,
    apply_exponential_smoothing,
    calculate_derivative_central_difference,
    linear_least_squares_predict,
    trapezoidal_rule_integration
)
from generate_dataset import generate_diurnal_temperature_dataset

# -----------------------------------------------------------------------------
# Streamlit App Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Computational Temperature Analyzer",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for polished dashboard presentation
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #1f77b4;
    }
    .stMetric {
        background-color: rgba(28, 131, 225, 0.06);
        padding: 10px 15px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🌡️ Computational Temperature Analyzer")
st.caption("From-Scratch Numerical Filtering, Finite Difference & Least-Squares Prediction")

# Ensure synthetic dataset is generated
DATA_PATH = os.path.join(os.path.dirname(__file__), "synthetic_temperature.csv")
if not os.path.exists(DATA_PATH):
    generate_diurnal_temperature_dataset(filename=DATA_PATH)

# -----------------------------------------------------------------------------
# Sidebar Interactive Controls
# -----------------------------------------------------------------------------
st.sidebar.header("⚙️ Filter & Analysis Controls")

st.sidebar.subheader("1. Outlier Rejection (Z-Score)")
z_thresh = st.sidebar.slider("Z-Score Threshold", min_value=1.5, max_value=5.0, value=3.0, step=0.1)
z_window = st.sidebar.slider("Z-Score Rolling Window", min_value=10, max_value=60, value=30, step=5)

st.sidebar.subheader("2. Smoothing Filter (Exponential)")
alpha = st.sidebar.slider("Alpha (Smoothing Factor)", min_value=0.01, max_value=0.50, value=0.15, step=0.01)

st.sidebar.subheader("3. Trendline & Future Prediction")
reg_window = st.sidebar.slider("Regression Window (Samples)", min_value=20, max_value=100, value=50, step=5)
future_horizon = st.sidebar.slider("Prediction Horizon (Steps)", min_value=5, max_value=50, value=20, step=5)

if st.sidebar.button("🔄 Regenerate Random Dataset"):
    import random
    generate_diurnal_temperature_dataset(filename=DATA_PATH, seed=random.randint(1, 99999))
    st.sidebar.success("New synthetic diurnal dataset generated!")
    st.rerun()

# -----------------------------------------------------------------------------
# Computational Pipeline Execution (All from Scratch)
# -----------------------------------------------------------------------------
# 1. Read CSV
times, raw_temps = read_temperature_csv(DATA_PATH)

# 2. Z-Score Outlier Detection
clean_times, clean_temps, outliers = remove_outliers_zscore(
    times=times,
    temperatures=raw_temps,
    window_size=z_window,
    z_threshold=z_thresh
)

# 3. Exponential Smoothing
smoothed_temps = apply_exponential_smoothing(clean_temps, alpha=alpha)

# 4. Central Finite Difference Numerical Differentiation
derivatives = calculate_derivative_central_difference(clean_times, smoothed_temps)
current_rate_of_change = derivatives[-1] if derivatives else 0.0

# 5. Linear Least Squares Regression & Future Prediction
slope, intercept, reg_x, reg_y, pred_x, pred_y = linear_least_squares_predict(
    times=clean_times,
    temperatures=smoothed_temps,
    window_pts=reg_window,
    future_steps=future_horizon
)

# 6. Trapezoidal Rule Numerical Integration
total_thermal_exposure, cumulative_exposure = trapezoidal_rule_integration(
    times=clean_times,
    temperatures=smoothed_temps
)

# -----------------------------------------------------------------------------
# Dashboard Key Metrics Display
# -----------------------------------------------------------------------------
col1, col2, col3, col4, col5 = st.columns(5)

current_temp = smoothed_temps[-1] if smoothed_temps else 0.0
future_temp = pred_y[-1] if pred_y else 0.0

with col1:
    st.metric(
        label="Current Temperature",
        value=f"{current_temp:.2f} °C",
        delta=f"{current_rate_of_change:+.3f} °C/step"
    )

with col2:
    st.metric(
        label="Rate of Change (dT/dt)",
        value=f"{current_rate_of_change:+.4f} °C/step",
        help="Calculated via Central Finite Difference"
    )

with col3:
    st.metric(
        label="Cumulative Exposure",
        value=f"{total_thermal_exposure:,.1f} °C·steps",
        help="Computed via Numerical Trapezoidal Rule Integration"
    )

with col4:
    st.metric(
        label=f"Projected (+{future_horizon} steps)",
        value=f"{future_temp:.2f} °C",
        delta=f"{(future_temp - current_temp):+.2f} °C"
    )

with col5:
    st.metric(
        label="Outliers Discarded",
        value=f"{len(outliers)}",
        delta=f"{(len(outliers) / len(raw_temps) * 100):.1f}% of data",
        delta_color="inverse"
    )

st.markdown("---")

# -----------------------------------------------------------------------------
# Primary Visualization: Matplotlib Composite Plot
# -----------------------------------------------------------------------------
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
fig, ax = plt.subplots(figsize=(14, 6.5), dpi=120)

# 1. Raw noisy synthetic data (scatter points)
ax.scatter(
    times,
    raw_temps,
    color="#94a3b8",
    alpha=0.35,
    s=12,
    label="Raw Noisy Data (Scatter)",
    zorder=2
)

# Highlight discarded glitch outliers
if outliers:
    outlier_t = [pt[0] for pt in outliers]
    outlier_v = [pt[1] for pt in outliers]
    ax.scatter(
        outlier_t,
        outlier_v,
        color="#dc2626",
        marker="x",
        s=55,
        linewidths=1.8,
        label=f"Discarded Glitch Spikes (Z > {z_thresh})",
        zorder=5
    )

# 2. Smoothed/filtered computational data (solid line)
ax.plot(
    clean_times,
    smoothed_temps,
    color="#0284c7",
    linewidth=2.4,
    label=f"Filtered Signal (Exponential Smoothing, α={alpha:.2f})",
    zorder=3
)

# 3. Least Squares predictive trendline extending into the future (dashed line)
# Combine regression fit over last 50 points and projection
combined_trend_x = reg_x + pred_x
combined_trend_y = reg_y + pred_y

ax.plot(
    combined_trend_x,
    combined_trend_y,
    color="#ea580c",
    linestyle="--",
    linewidth=2.5,
    label=f"Least Squares Trend & {future_horizon}-Step Projection (slope = {slope:+.4f})",
    zorder=4
)

# Highlight future prediction endpoint
ax.scatter(
    [pred_x[-1]],
    [pred_y[-1]],
    color="#ea580c",
    s=75,
    edgecolors="white",
    linewidths=1.5,
    zorder=6
)
ax.annotate(
    f" Pred: {pred_y[-1]:.2f}°C",
    (pred_x[-1], pred_y[-1]),
    textcoords="offset points",
    xytext=(8, -4),
    fontweight="bold",
    color="#c2410c",
    fontsize=9
)

# Plot formatting
ax.set_title("Computational Temperature Analysis: Filtering & Least-Squares Forecast", fontsize=15, fontweight="bold", pad=12)
ax.set_xlabel("Time (Steps / Sample Index)", fontsize=11, fontweight="bold")
ax.set_ylabel("Temperature (°C)", fontsize=11, fontweight="bold")
ax.set_ylim(-35, 120)  # Bound to showcase extreme glitches clearly alongside the diurnal wave
ax.legend(loc="upper left", frameon=True, facecolor="white", framealpha=0.9, fontsize=9.5)
ax.grid(True, linestyle=":", alpha=0.6)

st.pyplot(fig)

# -----------------------------------------------------------------------------
# Secondary Detailed Analytical Views (Tabs)
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "📈 Rate of Change (dT/dt)",
    "📊 Cumulative Exposure (Integral)",
    "⚠️ Detected Outlier Registry"
])

with tab1:
    st.subheader("Instantaneous Temperature Derivative (Central Finite Difference)")
    fig_d, ax_d = plt.subplots(figsize=(14, 3.5), dpi=100)
    ax_d.plot(clean_times, derivatives, color="#059669", linewidth=1.5, label="dT/dt (Central Difference)")
    ax_d.axhline(0.0, color="#6b7280", linestyle="--", linewidth=1)
    ax_d.fill_between(clean_times, derivatives, 0, where=[d >= 0 for d in derivatives], color="#10b981", alpha=0.2, label="Warming Phase")
    ax_d.fill_between(clean_times, derivatives, 0, where=[d < 0 for d in derivatives], color="#3b82f6", alpha=0.2, label="Cooling Phase")
    ax_d.set_xlabel("Time (Steps)", fontsize=10)
    ax_d.set_ylabel("dT/dt (°C / step)", fontsize=10)
    ax_d.legend(loc="upper right", frameon=True, fontsize=8.5)
    ax_d.grid(True, linestyle=":", alpha=0.5)
    st.pyplot(fig_d)

with tab2:
    st.subheader("Cumulative Thermal Exposure Over Time (Trapezoidal Rule)")
    fig_i, ax_i = plt.subplots(figsize=(14, 3.5), dpi=100)
    ax_i.plot(clean_times, cumulative_exposure, color="#7c3aed", linewidth=2.0, label="Cumulative Thermal Integral")
    ax_i.set_xlabel("Time (Steps)", fontsize=10)
    ax_i.set_ylabel("Integral (°C · steps)", fontsize=10)
    ax_i.legend(loc="upper left", frameon=True, fontsize=8.5)
    ax_i.grid(True, linestyle=":", alpha=0.5)
    st.pyplot(fig_i)

with tab3:
    st.subheader(f"Discarded Hardware Glitch Spikes (Total: {len(outliers)})")
    if outliers:
        st.write("The following extreme data points were identified and stripped by the rolling Z-Score filter:")
        outlier_records = [
            {"Timestamp (Step)": int(t), "Glitch Temperature (°C)": round(v, 2), "Classification": "Extreme High Spike" if v > 50 else "Extreme Low Spike"}
            for t, v in outliers
        ]
        st.dataframe(outlier_records, use_container_width=True)
    else:
        st.info("No outliers detected with current Z-Score threshold settings.")
