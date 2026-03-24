# rk.py  -- Cleaned & Fixed Version with Overlay and Port Selection
import sys
import os
import time
import threading
import math
import numpy as np
import pandas as pd
import serial
import pyqtgraph as pg
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, 
    QGroupBox, QFormLayout, QMessageBox, QLineEdit, QComboBox
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont
from pyqtgraph import GraphicsLayoutWidget
from PyQt5.QtWidgets import QGraphicsRectItem
import serial.tools.list_ports

# ---------------- Configuration ----------------
CSV_STORE_DIR = r"C:\Users\Plaksha.PLAKSHA111\OneDrive - Plaksha University\Desktop\yts\Stable\EquiliSense\EquiliSense\ronak\csv_store"
os.makedirs(CSV_STORE_DIR, exist_ok=True)

BAUD_RATE = 115200

PLATFORM_SIZE_CM = 47.0
PLOT_RANGE_CM = 50.0
OFFSET_SAMPLE_COUNT = 50
MIN_TOTAL_FORCE = 10
TRACE_HISTORY_SECONDS = 15
POSITION_NAMES = ('FL', 'FR', 'RL', 'RR')

EXPERIMENT_FILES = {
    'eyes_open': 'eyes_open.csv',
    'eyes_closed': 'eyes_closed.csv',
    'one_leg_right': 'one_leg_right.csv',
    'one_leg_left': 'one_leg_left.csv',
    'cognitive': 'cognitive.csv',
}

# ---------------- Helpers ----------------
def get_session_dir(session_name):
    session_dir = os.path.join(CSV_STORE_DIR, session_name)
    os.makedirs(session_dir, exist_ok=True)
    return session_dir

def remove_outliers_df(df: pd.DataFrame, thresh: float = 3.5, max_remove: int = 2):
    if df is None or df.empty or 'x' not in df.columns or 'y' not in df.columns:
        return df
    try:
        s = df[['x', 'y']].astype(float).copy()
        mx, my = s['x'].median(), s['y'].median()
        mad_x = (s['x'] - mx).abs().median()
        mad_y = (s['y'] - my).abs().median()
        if mad_x == 0 or mad_y == 0:
            return df
        zx = 0.6745 * (s['x'] - mx) / mad_x
        zy = 0.6745 * (s['y'] - my) / mad_y
        robust_score = pd.concat([zx.abs(), zy.abs()], axis=1).max(axis=1)
        candidates = robust_score[robust_score > thresh]
        if candidates.empty:
            return df
        to_drop = candidates.sort_values(ascending=False).index[:max_remove]
        return df.drop(index=to_drop)
    except:
        return df

def get_ellipse_params(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 3:
        return 0.0, 0.0, 0.0, 0.0
    pts = np.column_stack([x, y])
    cov = np.cov(pts.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = eigvals.argsort()[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]
    width = 2.0 * math.sqrt(max(eigvals[0], 0))
    height = 2.0 * math.sqrt(max(eigvals[1], 0))
    angle = math.degrees(math.atan2(eigvecs[1, 0], eigvecs[0, 0]))
    area = math.pi * (width/2) * (height/2)
    return width, height, angle, area

def compute_center_of_pressure(fl, fr, rl, rr):
    total = fl + fr + rl + rr
    if abs(total) < MIN_TOTAL_FORCE:
        return 0.0, 0.0
    x = ((fr + rr) - (fl + rl)) * (PLATFORM_SIZE_CM / 2) / total
    y = ((fl + fr) - (rl + rr)) * (PLATFORM_SIZE_CM / 2) / total
    return x, y

# ---------------- Main Window ----------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('EquiliSense - Unified Interface')
        self._build_ui()
        self._init_runtime()

    def _build_ui(self):
        root = QHBoxLayout(self)

        # ================== LEFT: PLOT ==================
        self.graphics = GraphicsLayoutWidget()
        self.plot = self.graphics.addPlot()
        self.plot.setAspectLocked(True)
        self.plot.showGrid(x=True, y=True)
        self.plot.setXRange(-PLOT_RANGE_CM/2, PLOT_RANGE_CM/2)
        self.plot.setYRange(-PLOT_RANGE_CM/2, PLOT_RANGE_CM/2)
        self.plot.setLabel('bottom', 'X (cm)')
        self.plot.setLabel('left', 'Y (cm)')

        platform = QGraphicsRectItem(-PLATFORM_SIZE_CM/2, -PLATFORM_SIZE_CM/2, PLATFORM_SIZE_CM, PLATFORM_SIZE_CM)
        platform.setPen(pg.mkPen('w', width=2))
        self.plot.addItem(platform)

        self.dot = self.plot.plot([0], [0], pen=None, symbol='o', symbolSize=12, symbolBrush='r')
        self.tracer = self.plot.plot([], [], pen=pg.mkPen('lime', width=2))

        root.addWidget(self.graphics, 3)

        # ================== RIGHT: CONTROLS ==================
        right = QVBoxLayout()

        # Serial Settings
        serial_group = QGroupBox('Serial Settings')
        s_form = QFormLayout()
        self.port_combo = QComboBox()
        self._refresh_ports()
        s_form.addRow('Port:', self.port_combo)
        self.connect_btn = QPushButton('Connect')
        self.connect_btn.clicked.connect(self._connect_serial)
        s_form.addRow(self.connect_btn)
        serial_group.setLayout(s_form)
        right.addWidget(serial_group)

        # Session Settings
        g1 = QGroupBox("Session Settings")
        form = QFormLayout()
        self.session_input = QLineEdit()
        self.session_input.setPlaceholderText("Enter session name")
        self.session_dropdown = QComboBox()
        self._refresh_session_dropdown()
        self.session_dropdown.currentIndexChanged.connect(self._on_session_selected)

        self.experiment_combo = QComboBox()
        self.experiment_combo.addItems(EXPERIMENT_FILES.keys())
        
        self.timer_combo = QComboBox()
        self.timer_combo.addItems(['5','10','20','30','60','120'])

        form.addRow("Session:", self.session_input)
        form.addRow("Load Session:", self.session_dropdown)
        form.addRow("Experiment:", self.experiment_combo)
        form.addRow("Duration (s):", self.timer_combo)
        g1.setLayout(form)
        right.addWidget(g1)

        # Buttons
        self.record_btn = QPushButton('Start Recording')
        self.record_btn.clicked.connect(self._toggle_recording)
        self.overlay_btn = QPushButton('Show Overlay + Ellipses')
        self.overlay_btn.clicked.connect(self._do_overlay)
        self.clear_trace_btn = QPushButton('Clear Trace')
        self.clear_trace_btn.clicked.connect(self._clear_trace)

        right.addWidget(self.record_btn)
        right.addWidget(self.overlay_btn)
        right.addWidget(self.clear_trace_btn)
        right.addWidget(QPushButton('Clear Overlays', clicked=lambda: self._clear_overlays(keep_live=True)))

        # Live Metrics
        g2 = QGroupBox("Live Metrics")
        mf = QFormLayout()
        self.lbl_fl = QLabel('0.0')
        self.lbl_fr = QLabel('0.0')
        self.lbl_rl = QLabel('0.0')
        self.lbl_rr = QLabel('0.0')
        self.lbl_total = QLabel('0.0')
        self.lbl_cop = QLabel('(0.00, 0.00)')
        self.lbl_status = QLabel('Select port and connect...')

        mf.addRow('FL:', self.lbl_fl)
        mf.addRow('FR:', self.lbl_fr)
        mf.addRow('RL:', self.lbl_rl)
        mf.addRow('RR:', self.lbl_rr)
        mf.addRow('Total:', self.lbl_total)
        mf.addRow('CoP:', self.lbl_cop)
        mf.addRow('Status:', self.lbl_status)
        g2.setLayout(mf)
        right.addWidget(g2)

        # Overlay Areas
        self.area_group = QGroupBox('Overlay Areas (per CSV)')
        self.area_layout = QVBoxLayout()
        self.area_group.setLayout(self.area_layout)
        self.area_layout.addWidget(QLabel('Overlay: not computed'))
        right.addWidget(self.area_group)

        # Overlay Info
        self.overlay_info = QLabel('Overlay: not computed')
        self.overlay_info.setWordWrap(True)
        right.addWidget(self.overlay_info)

        right.addStretch()
        root.addLayout(right, 1)

        # Timer
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self._update)
        self.ui_timer.start(50)

    def _init_runtime(self):
        self.data_lock = threading.Lock()
        self.cop_x = self.cop_y = 0.0
        self.trace = []
        self.recording = False
        self.csv_file = None
        self.running = True
        self.ser = None
        self.loadcell_offsets = None
        self.forces = {pos: 0.0 for pos in POSITION_NAMES}
        self.traces = []
        self.legend = None
        self.status = "Select port and connect..."
        self.first_line = True

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo.clear()
        self.port_combo.addItems(ports if ports else ['No ports found'])
        if 'COM13' in ports:
            self.port_combo.setCurrentText('COM13')
        print(f"Available ports: {ports}")

    def _connect_serial(self):
        port = self.port_combo.currentText()
        if port == 'No ports found':
            self.status = "No ports available"
            return
        if self.ser:
            try:
                self.ser.close()
            except:
                pass
            self.ser = None
        self.loadcell_offsets = None
        self.first_line = True
        self.status = f"Connecting to {port}..."
        threading.Thread(target=self._serial_loop, args=(port,), daemon=True).start()

    def _refresh_session_dropdown(self):
        sessions = [d for d in os.listdir(CSV_STORE_DIR) if os.path.isdir(os.path.join(CSV_STORE_DIR, d))]
        self.session_dropdown.clear()
        self.session_dropdown.addItems([''] + sorted(sessions))

    def _on_session_selected(self, idx):
        txt = self.session_dropdown.currentText()
        if txt:
            self.session_input.setText(txt)

    # ================== RECORDING ==================
    def _toggle_recording(self):
        if self.recording:
            self._stop_recording()
            return

        sess = self.session_input.text().strip()
        if not sess:
            QMessageBox.warning(self, "Error", "Please enter a session name")
            return

        exp = self.experiment_combo.currentText()
        path = os.path.join(get_session_dir(sess), EXPERIMENT_FILES[exp])
        
        try:
            self.csv_file = open(path, 'a')
            if os.path.getsize(path) == 0:
                self.csv_file.write('x,y\n')
            self.recording = True
            self.record_btn.setText('Stop Recording')
            duration = int(self.timer_combo.currentText())
            QTimer.singleShot(duration * 1000, self._on_record_timeout)
            print(f"Recording started → {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _stop_recording(self):
        self.recording = False
        self.record_btn.setText('Start Recording')
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
        print("Recording stopped.")

    def _on_record_timeout(self):
        self._stop_recording()
        QMessageBox.information(self, "Done", "Recording finished!")

    # ================== SERIAL THREAD ==================
    def _serial_loop(self, port):
        try:
            self.ser = serial.Serial(port, BAUD_RATE, timeout=1)
            self.status = f"Connected to {port}"
            print(self.status)
        except Exception as e:
            self.status = f"Failed to connect: {e}"
            print(self.status)
            return

        offset_acc = {pos: 0.0 for pos in POSITION_NAMES}
        count = 0

        while self.running and self.ser.is_open:
            try:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()

                if self.first_line and line:
                    print(f"Sample serial data: {line}")
                    self.first_line = False

                if not line or 'Calibrating' in line or 'Done' in line or 'Counts' in line or '=' in line:
                    time.sleep(0.001)
                    continue

                parts = line.split()
                if len(parts) < 4:
                    continue

                vals = [float(p) for p in parts[-4:]]
                raw_rl, raw_fr, raw_fl, raw_rr = vals

                # Calibration Phase
                if self.loadcell_offsets is None:
                    offset_acc['RL'] += raw_rl
                    offset_acc['FR'] += raw_fr
                    offset_acc['FL'] += raw_fl
                    offset_acc['RR'] += raw_rr
                    count += 1
                    self.status = f"Calibrating... {count}/{OFFSET_SAMPLE_COUNT}"

                    if count >= OFFSET_SAMPLE_COUNT:
                        self.loadcell_offsets = {k: v/count for k, v in offset_acc.items()}
                        self.status = "Ready - Live Data Streaming"
                        print("Offsets:", self.loadcell_offsets)
                    continue

                # Normal Operation
                fl = raw_fl - self.loadcell_offsets['FL']
                fr = raw_fr - self.loadcell_offsets['FR']
                rl = raw_rl - self.loadcell_offsets['RL']
                rr = raw_rr - self.loadcell_offsets['RR']

                x, y = compute_center_of_pressure(fl, fr, rl, rr)

                with self.data_lock:
                    self.forces.update({'FL':fl, 'FR':fr, 'RL':rl, 'RR':rr})
                    self.cop_x, self.cop_y = x, y
                    self.trace.append((x, y, time.time()))

                    # Keep only recent trace
                    cutoff = time.time() - TRACE_HISTORY_SECONDS
                    self.trace = [p for p in self.trace if p[2] >= cutoff]

                    if self.recording and self.csv_file:
                        self.csv_file.write(f"{x:.4f},{y:.4f}\n")

            except ValueError:
                self.status = "Invalid data format"
                time.sleep(0.1)
            except Exception as e:
                self.status = f"Error: {e}"
                time.sleep(0.1)

    # ================== PLOT & UI UPDATE ==================
    def _update(self):
        with self.data_lock:
            self.dot.setData([self.cop_x], [self.cop_y])

            if self.trace:
                xs = [p[0] for p in self.trace]
                ys = [p[1] for p in self.trace]
                self.tracer.setData(xs, ys)

            self.lbl_fl.setText(f"{self.forces['FL']:.1f}")
            self.lbl_fr.setText(f"{self.forces['FR']:.1f}")
            self.lbl_rl.setText(f"{self.forces['RL']:.1f}")
            self.lbl_rr.setText(f"{self.forces['RR']:.1f}")
            self.lbl_total.setText(f"{sum(self.forces.values()):.1f}")
            self.lbl_cop.setText(f"({self.cop_x:.2f}, {self.cop_y:.2f})")

        self.lbl_status.setText(self.status)

    def _clear_trace(self):
        with self.data_lock:
            self.trace.clear()
        self.tracer.setData([], [])
        print("Trace cleared")

    # ================== OVERLAY LOGIC ==================
    def _do_overlay(self):
        session_names = [self.session_input.text().strip()]
        dropdown_name = self.session_dropdown.currentText()
        if dropdown_name and dropdown_name not in session_names:
            session_names.append(dropdown_name)

        DARK_COLORS = [
            '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4', '#46f0f0',
            '#f032e6', '#bcf60c', '#fabebe', '#008080', '#e6beff', '#9a6324', '#fffac8',
            '#800000', '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080'
        ]

        self.plot.clear()
        self.plot.setAspectLocked(True)
        self.plot.showGrid(x=True, y=True)
        self.plot.setXRange(-PLOT_RANGE_CM/2, PLOT_RANGE_CM/2)
        self.plot.setYRange(-PLOT_RANGE_CM/2, PLOT_RANGE_CM/2)
        self.plot.setLabel('bottom', 'X (cm)')
        self.plot.setLabel('left', 'Y (cm)')

        platform = QGraphicsRectItem(-PLATFORM_SIZE_CM/2, -PLATFORM_SIZE_CM/2, PLATFORM_SIZE_CM, PLATFORM_SIZE_CM)
        platform.setPen(pg.mkPen('w', width=2))
        self.plot.addItem(platform)

        summary_lines = []
        color_idx = 0
        self.legend = self.plot.addLegend(offset=(30, 30))
        self.traces = []

        for session_name in session_names:
            session_dir = get_session_dir(session_name)
            for key, fname in EXPERIMENT_FILES.items():
                path = os.path.join(session_dir, fname)
                if not os.path.exists(path):
                    continue
                try:
                    df = pd.read_csv(path)
                    if 'x' not in df.columns or 'y' not in df.columns:
                        continue
                    df = remove_outliers_df(df)
                    x = df['x'].to_numpy(dtype=float)
                    y = df['y'].to_numpy(dtype=float)
                    color = DARK_COLORS[color_idx % len(DARK_COLORS)]
                    curve = self.plot.plot(x, y, pen=pg.mkPen(color=color, width=2))
                    self.legend.addItem(curve, f"{session_name}-{key}")
                    width, height, angle, area = get_ellipse_params(x, y)
                    summary_lines.append(f"{session_name}-{key}: area = {area:.2f} cm^2")
                    mx = np.mean(x)
                    my = np.mean(y)
                    semi_w = width / 2
                    semi_h = height / 2
                    rad = math.radians(angle)
                    theta = np.linspace(0, 2 * math.pi, 100)
                    xx = mx + semi_w * np.cos(theta) * np.cos(rad) - semi_h * np.sin(theta) * np.sin(rad)
                    yy = my + semi_w * np.cos(theta) * np.sin(rad) + semi_h * np.sin(theta) * np.cos(rad)
                    ellipse_curve = self.plot.plot(xx, yy, pen=pg.mkPen(color=color, width=1, style=Qt.DashLine))
                    self.traces.append({'curve': curve, 'ellipse': ellipse_curve, 'name': f"{session_name}-{key}", 'area': area, 'color': color})
                    color_idx += 1
                except Exception as e:
                    summary_lines.append(f"{session_name}-{key}: error {e}")

        self.overlay_info.setText("\n".join(summary_lines) if summary_lines else "Overlay: not computed")

        for i in reversed(range(self.area_layout.count())):
            w = self.area_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        if self.traces:
            for rec in self.traces:
                lbl = QLabel(f"{rec['name']}: {rec['area']:.2f} cm²")
                lbl.setStyleSheet(f"color: {rec['color']};")
                self.area_layout.addWidget(lbl)
        else:
            self.area_layout.addWidget(QLabel('Overlay: not computed'))

        self.dot = self.plot.plot([self.cop_x], [self.cop_y], pen=None, symbol='o', symbolSize=12, symbolBrush='r')
        self.tracer = self.plot.plot([], [], pen=pg.mkPen('lime', width=2))

    def _clear_overlays(self, keep_live=False):
        for rec in self.traces:
            self.plot.removeItem(rec['curve'])
            if rec['ellipse']:
                self.plot.removeItem(rec['ellipse'])
        self.traces = []
        if self.legend:
            self.plot.removeItem(self.legend)
            self.legend = None
        for i in reversed(range(self.area_layout.count())):
            w = self.area_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        self.area_layout.addWidget(QLabel('Overlay: not computed'))
        self.overlay_info.setText('Overlay: not computed')
        if not keep_live:
            self.plot.clear()
            platform = QGraphicsRectItem(-PLATFORM_SIZE_CM/2, -PLATFORM_SIZE_CM/2, PLATFORM_SIZE_CM, PLATFORM_SIZE_CM)
            platform.setPen(pg.mkPen('w', width=2))
            self.plot.addItem(platform)
            self.dot = self.plot.plot([self.cop_x], [self.cop_y], pen=None, symbol='o', symbolSize=12, symbolBrush='r')
            self.tracer = self.plot.plot([], [], pen=pg.mkPen('lime', width=2))

    def closeEvent(self, event):
        self.running = False
        if self.csv_file:
            self.csv_file.close()
        if self.ser and self.ser.is_open:
            self.ser.close()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1250, 850)
    win.show()
    sys.exit(app.exec_())