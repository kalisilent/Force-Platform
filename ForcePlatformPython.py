import sys 
import serial
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget
from PyQt5.QtCore import QTimer
import numpy as np
import threading
import os
import datetime

# ---------- Configuration ----------
SERIAL_PORT = 'COM13'
BAUD_RATE = 115200
PLATFORM_WIDTH = 0.47
PLATFORM_LENGTH = 0.47
TRACER_BUFFER_SIZE = 100  # Number of previous points to show

# ---------- Global Variables ----------
data_lock = threading.Lock()
cop_x, cop_y = 0, 0
trace_buffer = []
recording = False  # Toggle for CSV recording
csv_file = None    # File handle for CSV

# CSV directory
CSV_DIR = os.path.join(os.path.dirname(__file__), 'csv')
os.makedirs(CSV_DIR, exist_ok=True)

# ---------- CoP Calculation ----------
def compute_center_of_pressure(fl, fr, rl, rr):
    total = fl + fr + rl + rr
    if abs(total) < 1000:
        return 0, 0
    width_cm = PLATFORM_WIDTH * 100
    length_cm = PLATFORM_LENGTH * 100
    x = ((fr + rr) - (fl + rl)) * (width_cm / 2) / total
    y = ((fl + fr) - (rl + rr)) * (length_cm / 2) / total
    return x, y

# ---------- Serial Reading Thread ----------
def read_serial():
    global cop_x, cop_y, trace_buffer, recording, csv_file
    OFFSET_SAMPLE_COUNT = 50
    FORCE_DEADBAND = 5
    MIN_TOTAL_FORCE = 10
    RAW_INDEX_BY_POSITION = {
        'FR': 1,  # load cell 2
        'FL': 2,  # load cell 3
        'RR': 3,  # load cell 4
        'RL': 0,  # load cell 1
    }
    POSITION_NAMES = ('FL', 'FR', 'RL', 'RR')
    loadcell_offsets = {pos: 0.0 for pos in POSITION_NAMES}
    offset_sums = {pos: 0.0 for pos in POSITION_NAMES}
    offset_count = 0
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE)
        print(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud.")
    except Exception as e:
        print(f"Failed to connect to {SERIAL_PORT}: {e}")
        return
    while True:
        try:
            line = ser.readline().decode().strip()
            try:
                parts = list(map(float, line.split()))
            except ValueError:
                continue
            if len(parts) < 8:
                continue
            raw_counts = [parts[0], parts[2], parts[4], parts[6]]
            mapped_raw = {pos: raw_counts[RAW_INDEX_BY_POSITION[pos]] for pos in POSITION_NAMES}
            if offset_count < OFFSET_SAMPLE_COUNT:
                for pos in POSITION_NAMES:
                    offset_sums[pos] += mapped_raw[pos]
                offset_count += 1
                if offset_count == OFFSET_SAMPLE_COUNT:
                    for pos in POSITION_NAMES:
                        loadcell_offsets[pos] = offset_sums[pos] / OFFSET_SAMPLE_COUNT
                    print("Load cell offsets established:",
                          " ".join(f"{pos} {loadcell_offsets[pos]:.2f}" for pos in POSITION_NAMES))
                continue
            forces = {pos: mapped_raw[pos] - loadcell_offsets[pos] for pos in POSITION_NAMES}
            for pos in POSITION_NAMES:
                if abs(forces[pos]) < FORCE_DEADBAND:
                    forces[pos] = 0.0
            fl = forces['FL']
            fr = forces['FR']
            rl = forces['RL']
            rr = forces['RR']
            x, y = compute_center_of_pressure(fl, fr, rl, rr)
            print(f"FL:{fl:.1f} FR:{fr:.1f} RL:{rl:.1f} RR:{rr:.1f} => CoP (cm): ({x:.2f}, {y:.2f})")
            with data_lock:
                cop_x, cop_y = x, y
                trace_buffer.append((x, y))
                if recording and csv_file:
                    csv_file.write(f"{x},{y}\n")
                    csv_file.flush()
        except Exception as e:
            print(f"Serial Read Error: {e}")
            continue

# ---------- Start Serial Thread ----------
threading.Thread(target=read_serial, daemon=True).start()

# ---------- PyQtGraph Real-Time Plot ----------
app = QApplication([])
main_window = QWidget()
layout = QVBoxLayout()
win = pg.GraphicsLayoutWidget(title="Stable-o-gram (Center of Pressure)")
layout.addWidget(win)

plot = win.addPlot()
plot.setAspectLocked(True)
plot.setXRange(-PLATFORM_WIDTH / 2, PLATFORM_WIDTH / 2)
plot.setYRange(-PLATFORM_LENGTH / 2, PLATFORM_LENGTH / 2)
plot.showGrid(x=True, y=True)

# Make axis numbers larger
axis_font = pg.QtGui.QFont()
axis_font.setPointSize(12)  # Change to your preferred size
plot.getAxis("bottom").setTickFont(axis_font)
plot.getAxis("left").setTickFont(axis_font)

# Add axis labels
plot.setLabel('left', 'Y Position (m)', **{'font-size': '20pt'})
plot.setLabel('bottom', 'X Position (m)', **{'font-size': '20pt'})

# CoP dot
dot = plot.plot([0], [0], pen=None, symbol='o', symbolSize=10, symbolBrush='r')

# Tracer plot (thicker line)
tracer = plot.plot([], [], pen=pg.mkPen('g', width=4))  # Increased width

# ---------- Start/Stop Button ----------
record_button = QPushButton("Start Recording")
layout.addWidget(record_button)

def toggle_recording():
    global recording, csv_file
    if recording:
        print("Stopping recording.")
        record_button.setText("Start Recording")
        if csv_file:
            csv_file.close()
            csv_file = None
        recording = False
    else:
        print("Starting recording.")
        record_button.setText("Stop Recording")
        try:
            # Find the next available integer filename in the csv folder
            existing = [f for f in os.listdir(CSV_DIR) if f.startswith('New') and f.endswith('kg.csv')]
            nums = [int(f[3:-6]) for f in existing if f[3:-6].isdigit()]
            next_num = max(nums) + 1 if nums else 1
            csv_path = os.path.join(CSV_DIR, f"New{next_num}kg.csv")
            csv_file = open(csv_path, "w")
            csv_file.write("x,y\n")  # Write header
            recording = True
        except Exception as e:
            print(f"Failed to open CSV for writing: {e}")

record_button.clicked.connect(toggle_recording)

# ---------- Export Function ----------
def save_trace_buffer_to_csv():
    with data_lock:
        if not trace_buffer:
            print("Trace buffer is empty. Nothing to save.")
            return
        try:
            with open(os.path.join(CSV_DIR, "TraceBuffer.csv"), "w") as f:
                f.write("x,y\n")
                for x, y in trace_buffer:
                    f.write(f"{x},{y}\n")
            print("Trace buffer saved to TraceBuffer.csv")
        except Exception as e:
            print(f"Error saving CSV: {e}")

# Hook into close event
def on_close_event(event):
    print("Application closing...")
    if recording and csv_file:
        csv_file.close()
    save_trace_buffer_to_csv()
    event.accept()  # Let the window close

main_window.closeEvent = on_close_event
main_window.setLayout(layout)

# ---------- Update Function ----------
def update():
    with data_lock:
        dot.setData([cop_x], [cop_y])
        if trace_buffer:
            x_vals, y_vals = zip(*trace_buffer)
            tracer.setData(x_vals, y_vals)

# Timer to update ~80 FPS
timer = QTimer()
timer.timeout.connect(update)
timer.start(12)

# ---------- Run App ----------
main_window.show()
sys.exit(app.exec())
