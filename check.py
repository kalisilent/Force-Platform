import sys 
import serial
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget
from PyQt5.QtCore import QTimer
import numpy as np
import threading

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

# ---------- CoP Calculation ----------
def compute_center_of_pressure(fl, fr, rl, rr):
    total = fl + fr + rl + rr
    if abs(total) < 1000:
        return 0, 0
    x = ((fr + rr) - (fl + rl)) * (PLATFORM_WIDTH / 2) / total
    y = ((fl + fr) - (rl + rr)) * (PLATFORM_LENGTH / 2) / total
    return x, y

# ---------- Serial Reading Thread ----------
def read_serial():
    global cop_x, cop_y, trace_buffer, recording, csv_file
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE)
        print(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud.")
    except Exception as e:
        print(f"Failed to connect to {SERIAL_PORT}: {e}")
        return

    while True:
        try:
            line = ser.readline().decode().strip()
            parts = list(map(float, line.split(',')))
            if len(parts) != 5:
                continue
            _, fl, rl, rr, fr = parts         
            x, y = compute_center_of_pressure(fl, fr, rl, rr)
            print(f"FL: {fl:.1f}, FR: {fr:.1f}, RL: {rl:.1f}, RR: {rr:.1f} => CoP: ({x:.3f}, {y:.3f})")
            with data_lock:
                cop_x, cop_y = x, y
                trace_buffer.append((x, y))
                if recording and csv_file:  # Only write if recording is ON
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
            csv_file = open("Debug.csv", "a")
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
            with open("TraceBuffer.csv", "w") as f:
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
