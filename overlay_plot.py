import sys
import os
import pandas as pd
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget, QGraphicsRectItem
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# ---------- Configuration ----------
csv_folder = r"C:\Users\Plaksha.PLAKSHA111\OneDrive - Plaksha University\Desktop\yts\Stable\EquiliSense\EquiliSense\ronak\csv_store\Aditya"  # Folder where CSV files are located
file_prefix = "New"
file_suffix = "kg.csv"
min_num = 1
max_num = 100  # Adjust as needed for your number of files

# Generate file list by number, e.g., New1kg.csv, New2kg.csv, ...
file_list = [f"{file_prefix}{n}{file_suffix}" for n in range(min_num, max_num + 1)]

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

# ---------- Plot All Files ----------
for idx, file_name in enumerate(file_list):
    file_path = os.path.join(csv_folder, file_name)
    if not os.path.exists(file_path):
        continue
    try:
        data = pd.read_csv(file_path)
        if 'x' not in data.columns or 'y' not in data.columns:
            print(f"CSV missing 'x' and 'y' columns: {file_name}, skipping.")
            continue
        color = colors[idx % len(colors)]  # Use a unique color for each file
        pen = pg.mkPen(color=color, width=2)
        plot_widget.plot(data['x'], data['y'], pen=pen, name=file_name)
        print(f"Plotted {file_name}")
    except Exception as e:
        print(f"Error reading {file_name}: {e}")

# ---------- Run App ----------
window.setWindowTitle("CSV Y vs X Plotter (All Files)")
window.show()
sys.exit(app.exec())
