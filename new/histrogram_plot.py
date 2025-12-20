
import sys
import os
import pandas as pd
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget, QGraphicsRectItem
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

# ---------- Configuration ----------

# Folder where CSV files are located
csv_folder = r"C:\Users\Plaksha.PLAKSHA111\OneDrive - Plaksha University\Desktop\yts\Stable\EquiliSense\EquiliSense\ronak\csv_store\Deepan"
# List of CSV files to overlay
file_list = [
    "eyes_closed.csv",
    "eyes_open.csv",
    "one_leg_left.csv",
    "one_leg_right.csv"
]

# Use a set of dark, visually distinct colors for plotting
DARK_COLORS = [
    '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4', '#46f0f0',
    '#f032e6', '#bcf60c', '#fabebe', '#008080', '#e6beff', '#9a6324', '#fffac8',
    '#800000', '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080', "#FF0000",
    '#1a1a1a', '#2d2d2d', '#333366', '#660066', '#993333', '#003300', '#003366',
    '#4b0082', '#191970', '#483d8b', '#2f4f4f', '#008b8b', '#556b2f', '#8b0000',
    '#8b008b', '#b22222', '#228b22', '#6b8e23', '#191970', '#00008b', '#8b4513',
    '#2e0854', '#013220', '#36454f', '#232b2b', "#b700ff", '#22313f', '#1c2833',
    '#212f3c', '#17202a', '#283747', '#212f3c', '#1b2631', '#212f3c', '#1c1c1c',
    '#2c3e50', '#34495e', '#22313f', '#2c2c2c', '#222222', "#4400FF", '#333333',
]
colors = DARK_COLORS
# ---------- PyQt5 App ----------
app = QApplication([])
window = QWidget()
layout = QVBoxLayout()

# Plot widget
plot_widget = pg.PlotWidget(title="Y vs X: All Files")
plot_widget.setLabel('left', 'Y Value')
plot_widget.setLabel('bottom', 'X Value')
plot_widget.showGrid(x=True, y=True)
plot_widget.addLegend()
layout.addWidget(plot_widget)

window.setLayout(layout)

# Set the plot scale to fixed 50x50 cm
plot_widget.setXRange(-25, 25)
plot_widget.setYRange(-25, 25)
plot_widget.setAspectLocked(True)

# Add square outline for 47x47 cm platform
platform_rect = QGraphicsRectItem(-23.5, -23.5, 47, 47)
platform_rect.setPen(pg.mkPen(color='w', width=2))
plot_widget.addItem(platform_rect)



# ---------- Overlay Plot and Peakness Histogram (2x2 subplots) ----------
peakness_list = []
titles = []
colors_used = []
for idx, file_name in enumerate(file_list):
    file_path = os.path.join(csv_folder, file_name)
    if not os.path.exists(file_path):
        peakness_list.append(None)
        titles.append(file_name)
        colors_used.append(colors[idx % len(colors)])
        continue
    try:
        data = pd.read_csv(file_path)
        if 'x' not in data.columns or 'y' not in data.columns:
            print(f"CSV missing 'x' and 'y' columns: {file_name}, skipping.")
            peakness_list.append(None)
            titles.append(file_name)
            colors_used.append(colors[idx % len(colors)])
            continue
        color = colors[idx % len(colors)]  # Use a unique color for each file
        pen = pg.mkPen(color=color, width=2)
        plot_widget.plot(data['x'], data['y'], pen=pen, name=file_name)
        print(f"Plotted {file_name}")

        # --- Compute peakness (change in angle between segments) ---
        x = data['x'].values
        y = data['y'].values
        peakness = []
        for i in range(1, len(x)-1):
            v1 = [x[i]-x[i-1], y[i]-y[i-1]]
            v2 = [x[i+1]-x[i], y[i+1]-y[i]]
            dot = v1[0]*v2[0] + v1[1]*v2[1]
            norm1 = (v1[0]**2 + v1[1]**2)**0.5
            norm2 = (v2[0]**2 + v2[1]**2)**0.5
            if norm1 == 0 or norm2 == 0:
                angle = 0
            else:
                cos_theta = max(min(dot/(norm1*norm2), 1), -1)
                angle = abs(np.arccos(cos_theta))
            peakness.append(angle)
        peakness_list.append(peakness)
        titles.append(file_name)
        colors_used.append(color)
    except Exception as e:
        print(f"Error reading {file_name}: {e}")
        peakness_list.append(None)
        titles.append(file_name)
        colors_used.append(colors[idx % len(colors)])


# --- Plot segment length vs. time in a 2x2 grid ---

segment_lengths = []
segment_times = []
for idx, file_name in enumerate(file_list):
    file_path = os.path.join(csv_folder, file_name)
    if not os.path.exists(file_path):
        segment_lengths.append(None)
        segment_times.append(None)
        continue
    try:
        data = pd.read_csv(file_path)
        if 'x' not in data.columns or 'y' not in data.columns:
            segment_lengths.append(None)
            segment_times.append(None)
            continue
        # Find time column
        time_col = None
        for col in ['t', 'time', 'timestamp', 'Time']:
            if col in data.columns:
                time_col = col
                break
        if time_col is None:
            # If no time column, use index as time
            # Each segment is between two points, so use len(data)-1
            duration = (len(data)-1) / 2  # seconds
            if len(data) > 1:
                times = np.linspace(0, duration, len(data)-1)
            else:
                times = np.array([])
        else:
            times = data[time_col].values[:-1]
            # If time column is not in seconds, scale to duration
            if len(times) > 0:
                duration = (len(times)) / 2
                times = np.linspace(0, duration, len(times))
        x = data['x'].values
        y = data['y'].values
        lengths = np.sqrt(np.diff(x)**2 + np.diff(y)**2)  # Already in cm
        # Remove at most two outliers (largest segment lengths)
        if len(lengths) > 2:
            # Get indices of the two largest values
            outlier_indices = np.argsort(lengths)[-2:]
            mask = np.ones(len(lengths), dtype=bool)
            mask[outlier_indices] = False
            cleaned_lengths = lengths[mask]
            cleaned_times = times[mask]
        else:
            cleaned_lengths = lengths
            cleaned_times = times
        segment_lengths.append(cleaned_lengths)
        segment_times.append(cleaned_times)
    except Exception as e:
        segment_lengths.append(None)
        segment_times.append(None)


# --- Histogram of segment lengths (2x2 grid) ---
bin_width = 0.05
# Find global max segment length for consistent x-axis scaling
valid_lengths = [l for l in segment_lengths if l is not None and len(l) > 0]
all_lengths = np.concatenate(valid_lengths) if len(valid_lengths) > 0 else np.array([0])
max_len = np.max(all_lengths) if len(all_lengths) > 0 else 1
bins = np.arange(0, max_len + bin_width, bin_width)
fig, axs = plt.subplots(2, 2, figsize=(12, 8))
for i in range(4):
    ax = axs[i//2, i%2]
    lengths = segment_lengths[i]
    if lengths is not None and len(lengths) > 0:
        ax.hist(lengths, bins=bins, color=colors[i % len(colors)], alpha=0.7, edgecolor='black')
        ax.set_title(f"Segment Length Distribution: {file_list[i]}", fontsize=12)
        ax.set_xlabel("Segment Length (cm)", fontsize=10)
        ax.set_ylabel("Count", fontsize=10)
        ax.set_xlim(0, max_len)
        ax.grid(True, linestyle='--', alpha=0.6)
    else:
        ax.text(0.5, 0.5, f"No data for {file_list[i]}", ha='center', va='center', fontsize=12)
        ax.set_title(f"Segment Length Distribution: {file_list[i]}", fontsize=12)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_xlim(0, max_len)
    ax.tick_params(axis='both', labelsize=9)
plt.tight_layout()
plt.show()

# ---------- Run App ----------
window.setWindowTitle("CSV Y vs X Plotter (All Files)")
window.show()
sys.exit(app.exec())
