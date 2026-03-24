import sys 
import serial
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget, QHBoxLayout, QGroupBox, QFormLayout, QLabel, QGraphicsRectItem
from PyQt5.QtCore import QTimer
import numpy as np
import threading
import time

# ---------- Configuration ----------
SERIAL_PORT = 'COM13'
BAUD_RATE = 115200
PLATFORM_WIDTH = 47.0
PLATFORM_LENGTH = 47.0
TRACE_HISTORY_SECONDS = 5  # Show only last 5 seconds of trace
OFFSET_SAMPLE_COUNT = 50
MIN_TOTAL_FORCE = 10

# ---------- Global Variables ----------
data_lock = threading.Lock()
cop_x, cop_y = 0, 0
fl, fr, rl, rr = 0, 0, 0, 0
total_force = 0
trace_buffer = []  # List of (x, y, timestamp)
recording = False  # Toggle for CSV recording
csv_file = None    # File handle for CSV
loadcell_offsets = None
offset_buffer = { 'FL': [], 'FR': [], 'RL': [], 'RR': [] }
offset_ready = False

# ---------- CoP Calculation ----------
def compute_center_of_pressure(fl, fr, rl, rr):
	total = fl + fr + rl + rr
	if abs(total) < MIN_TOTAL_FORCE:
		return 0, 0
	x = ((fr + rr) - (fl + rl)) * (PLATFORM_WIDTH / 2) / total
	y = ((fl + fr) - (rl + rr)) * (PLATFORM_LENGTH / 2) / total
	return x, y

# ---------- Serial Reading Thread ----------
def read_serial():
	global cop_x, cop_y, trace_buffer, recording, csv_file, fl, fr, rl, rr, total_force, offset_ready, loadcell_offsets
	try:
		ser = serial.Serial(SERIAL_PORT, BAUD_RATE)
		print(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud.")
	except Exception as e:
		print(f"Failed to connect to {SERIAL_PORT}: {e}")
		return

	while True:
		try:
			line = ser.readline().decode(errors='ignore').strip()
			if not line:
				continue
			try:
				parts = [float(p) for p in line.split()]
			except ValueError:
				continue  # Silently skip non-numeric lines
			if len(parts) != 14:
				continue
			# Extract raw readings
			raw_rl = parts[10]
			raw_fr = parts[11]
			raw_fl = parts[12]
			raw_rr = parts[13]
			# Collect offset samples
			if not offset_ready:
				offset_buffer['RL'].append(raw_rl)
				offset_buffer['FR'].append(raw_fr)
				offset_buffer['FL'].append(raw_fl)
				offset_buffer['RR'].append(raw_rr)
				if len(offset_buffer['FL']) >= OFFSET_SAMPLE_COUNT:
					loadcell_offsets = {
						'RL': sum(offset_buffer['RL']) / len(offset_buffer['RL']),
						'FR': sum(offset_buffer['FR']) / len(offset_buffer['FR']),
						'FL': sum(offset_buffer['FL']) / len(offset_buffer['FL']),
						'RR': sum(offset_buffer['RR']) / len(offset_buffer['RR'])
					}
					offset_ready = True
					print("Offsets established:", loadcell_offsets)
				continue
			# Subtract offsets
			rl_val = raw_rl - loadcell_offsets['RL']
			fr_val = raw_fr - loadcell_offsets['FR']
			fl_val = raw_fl - loadcell_offsets['FL']
			rr_val = raw_rr - loadcell_offsets['RR']
			x, y = compute_center_of_pressure(fl_val, fr_val, rl_val, rr_val)
			total = fl_val + fr_val + rl_val + rr_val
			print(f"FL: {fl_val:.1f}, FR: {fr_val:.1f}, RL: {rl_val:.1f}, RR: {rr_val:.1f} => CoP: ({x:.3f}, {y:.3f})")
			current_time = time.time()
			with data_lock:
				cop_x, cop_y = x, y
				fl, fr, rl, rr = fl_val, fr_val, rl_val, rr_val
				total_force = total
				trace_buffer.append((x, y, current_time))
				# Remove old points older than TRACE_HISTORY_SECONDS
				while trace_buffer and current_time - trace_buffer[0][2] > TRACE_HISTORY_SECONDS:
					trace_buffer.pop(0)
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
main_layout = QHBoxLayout()
main_window.setLayout(main_layout)

# Left: Plot
plot_layout = QVBoxLayout()
win = pg.GraphicsLayoutWidget(title="Stable-o-gram (Center of Pressure)")
plot_layout.addWidget(win)

plot = win.addPlot()
plot.setAspectLocked(True)
plot.setXRange(-25, 25)
plot.setYRange(-25, 25)
plot.showGrid(x=True, y=True)

# Add square outline for the platform
platform_rect = QGraphicsRectItem(-23.5, -23.5, 47, 47)
platform_rect.setPen(pg.mkPen('w', width=2))
plot.addItem(platform_rect)

# Make axis numbers larger
axis_font = pg.QtGui.QFont()
axis_font.setPointSize(12)  # Change to your preferred size
plot.getAxis("bottom").setTickFont(axis_font)
plot.getAxis("left").setTickFont(axis_font)

# Add axis labels
plot.setLabel('left', 'Y Position (cm)', **{'font-size': '20pt'})
plot.setLabel('bottom', 'X Position (cm)', **{'font-size': '20pt'})

# CoP dot
dot = plot.plot([0], [0], pen=None, symbol='o', symbolSize=10, symbolBrush='r')

# Tracer plot (thicker line)
tracer = plot.plot([], [], pen=pg.mkPen('g', width=4))  # Increased width
main_layout.addLayout(plot_layout, 3)

# Right: Metrics
metrics_layout = QVBoxLayout()
metrics_box = QGroupBox('Sensor Readings')
form_layout = QFormLayout()
label_fl = QLabel('0')
label_fr = QLabel('0')
label_rl = QLabel('0')
label_rr = QLabel('0')
label_total = QLabel('0')
label_cop = QLabel('(0,0)')
form_layout.addRow('FL:', label_fl)
form_layout.addRow('FR:', label_fr)
form_layout.addRow('RL:', label_rl)
form_layout.addRow('RR:', label_rr)
form_layout.addRow('Total:', label_total)
form_layout.addRow('CoP (cm):', label_cop)
metrics_box.setLayout(form_layout)
metrics_layout.addWidget(metrics_box)

# ---------- Start/Stop Button ----------
record_button = QPushButton("Start Recording")
metrics_layout.addWidget(record_button)

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
			csv_file.write("x,y\n")  # Write header if needed
			recording = True
		except Exception as e:
			print(f"Failed to open CSV for writing: {e}")

record_button.clicked.connect(toggle_recording)

metrics_layout.addStretch(1)
main_layout.addLayout(metrics_layout, 1)

# ---------- Export Function ----------
def save_trace_buffer_to_csv():
	with data_lock:
		if not trace_buffer:
			print("Trace buffer is empty. Nothing to save.")
			return
		try:
			with open("TraceBuffer.csv", "w") as f:
				f.write("x,y\n")
				for x, y, _ in trace_buffer:
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

# ---------- Update Function ----------
def update():
	with data_lock:
		dot.setData([cop_x], [cop_y])
		if trace_buffer:
			x_vals, y_vals = zip(*[(x, y) for x, y, t in trace_buffer])
			tracer.setData(x_vals, y_vals)
		label_fl.setText(f"{fl:.1f}")
		label_fr.setText(f"{fr:.1f}")
		label_rl.setText(f"{rl:.1f}")
		label_rr.setText(f"{rr:.1f}")
		label_total.setText(f"{total_force:.1f}")
		label_cop.setText(f"({cop_x:.2f}, {cop_y:.2f})")

# Timer to update ~20 FPS to reduce lag
timer = QTimer()
timer.timeout.connect(update)
timer.start(50)

# ---------- Run App ----------
main_window.resize(1200, 700)
main_window.show()
sys.exit(app.exec())
