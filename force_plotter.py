import sys
import os
import pandas as pd
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

# ---------- Configuration ----------
csv_folder = r"C:\Users\Plaksha.PLAKSHA111\OneDrive - Plaksha University\Desktop\yts\Stable\EquiliSense\EquiliSense\ronak\csv"  # Set to folder where CSVs are located
file_prefix = "New"
file_suffix = "kg.csv"
min_num = 1
max_num = 100  # Adjust as needed for your number of files

# ---------- Generate file list ----------
file_list = [f"{file_prefix}{n}{file_suffix}" for n in range(min_num, max_num + 1)]
current_index = 0

# ---------- PyQt5 App ----------
app = QApplication([])
window = QWidget()
layout = QVBoxLayout()

# Plot widget
plot_widget = pg.PlotWidget(title="Y vs X Plot")
plot_widget.setLabel('left', 'Y Value')
plot_widget.setLabel('bottom', 'X Value')
plot_widget.showGrid(x=True, y=True)
layout.addWidget(plot_widget)

# Next button
next_button = QPushButton("Next File")
layout.addWidget(next_button)

window.setLayout(layout)

# ---------- Plot Function ----------
def plot_csv(index):
    if index < 0 or index >= len(file_list):
        print("Index out of range")
        return
    file_name = file_list[index]
    file_path = os.path.join(csv_folder, file_name)
    if not os.path.exists(file_path):
        print(f"File not found: {file_name}")
        return

    # Read CSV
    try:
        data = pd.read_csv(file_path)
        if 'x' not in data.columns or 'y' not in data.columns:
            print(f"CSV missing 'x' and 'y' columns: {file_name}")
            return

        # Clear previous plot
        plot_widget.clear()
        # Plot Y vs X
        plot_widget.plot(data['x'], data['y'], pen=pg.mkPen('b', width=2))
        plot_widget.setTitle(f"Plot for {file_name}")
        print(f"Plotted {file_name}")
    except Exception as e:
        print(f"Error reading {file_name}: {e}")

# ---------- Button Click Handler ----------
def next_file():
    global current_index
    current_index += 1
    if current_index >= len(file_list):
        current_index = 0  # Wrap around
    plot_csv(current_index)

next_button.clicked.connect(next_file)

# ---------- Initial Plot ----------
plot_csv(current_index)

# ---------- Run App ----------
window.setWindowTitle("CSV Y vs X Plotter")
window.show()
sys.exit(app.exec())
