"""
Synthetic Temperature Dataset Generator
----------------------------------------
Generates 1,000 temperature readings simulating a 24-hour diurnal cycle:
- Base diurnal curve: Sine wave
- Gaussian noise (sensor inaccuracy) via random.gauss()
- 1% extreme hardware glitch spikes
Uses ONLY standard library 'math' and 'random'.
"""

import csv
import math
import os
import random

def generate_diurnal_temperature_dataset(
    filename: str = "synthetic_temperature.csv",
    num_samples: int = 1000,
    base_temp: float = 22.0,
    amplitude: float = 8.0,
    noise_sigma: float = 0.75,
    outlier_fraction: float = 0.01,
    seed: int = 42
) -> str:
    """
    Generates synthetic temperature data and saves it to a CSV file.
    
    Parameters:
        filename: Target CSV filename.
        num_samples: Total number of measurements (default 1000).
        base_temp: Baseline ambient temperature (°C).
        amplitude: Diurnal peak-to-trough variation (°C).
        noise_sigma: Standard deviation of sensor Gaussian noise.
        outlier_fraction: Fraction of readings to corrupt with extreme glitch spikes.
        seed: Random seed for deterministic reproducibility.
    """
    random.seed(seed)
    
    # Pre-select exactly 1% of indices to be extreme glitch outliers
    num_outliers = int(num_samples * outlier_fraction)
    outlier_indices = set(random.sample(range(num_samples), num_outliers))

    records = []
    
    for t in range(num_samples):
        # 1. Base Diurnal Cycle: Sine wave over a 24-hour span (1000 samples)
        # Shift phase by -pi/2 so minimum occurs at night and peak at midday
        angle = (2.0 * math.pi * t / num_samples) - (math.pi / 2.0)
        diurnal_component = base_temp + amplitude * math.sin(angle)
        
        # 2. Sensor Inaccuracy: Additive Gaussian Noise
        sensor_noise = random.gauss(0.0, noise_sigma)
        temp = diurnal_component + sensor_noise
        
        # 3. Hardware Glitches: Replace 1% with extreme spikes (negative drops or severe overheating)
        if t in outlier_indices:
            if random.random() < 0.5:
                # Extreme high spike (e.g. 75°C to 110°C)
                temp = random.uniform(75.0, 110.0)
            else:
                # Extreme low spike (e.g. -30°C to -10°C)
                temp = random.uniform(-30.0, -10.0)

        records.append((t, round(temp, 3)))

    # Save to CSV with specified column headers
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Time", "Raw_Temperature"])
        writer.writerows(records)

    print(f"Generated {num_samples} readings ({len(outlier_indices)} outliers) -> '{filename}'")
    return filename

if __name__ == "__main__":
    filepath = os.path.join(os.path.dirname(__file__), "synthetic_temperature.csv")
    generate_diurnal_temperature_dataset(filename=filepath)
