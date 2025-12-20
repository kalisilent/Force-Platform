# rk.py  -- integrated UI + overlay using provided overlay code and helpers
import sys
import os
import time
import threading
import math
import random
import numpy as np
import pandas as pd
import serial
import pyqtgraph as pg
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QGroupBox, QFormLayout, QMessageBox,
    QLineEdit, QComboBox, QFileDialog, QScrollArea, QSizePolicy
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont
from pyqtgraph import GraphicsLayoutWidget
from PyQt5.QtWidgets import QGraphicsRectItem

# ---------------- Configuration ----------------
CSV_STORE_DIR = r"C:\Users\Plaksha.PLAKSHA111\OneDrive - Plaksha University\Desktop\yts\Stable\EquiliSense\EquiliSense\ronak\csv_store"
os.makedirs(CSV_STORE_DIR, exist_ok=True)

SERIAL_PORT = os.environ.get('FORCE_PLATFORM_PORT', 'COM13')
BAUD_RATE = int(os.environ.get('FORCE_PLATFORM_BAUD', '115200'))

PLATFORM_SIZE_CM = 47.0
PLOT_RANGE_CM = 50.0
OFFSET_SAMPLE_COUNT = 50
MIN_TOTAL_FORCE = 10
TRACE_HISTORY_SECONDS = 30
POSITION_NAMES = ('FL', 'FR', 'RL', 'RR')

EXPERIMENT_FILES = {
    'eyes_open': 'eyes_open.csv',
    'eyes_closed': 'eyes_closed.csv',
    'one_leg_right': 'one_leg_right.csv',
    'one_leg_left': 'one_leg_left.csv',
}

# ---------------- Helpers ----------------
def get_session_dir(session_name):
    session_dir = os.path.join(CSV_STORE_DIR, session_name)
    os.makedirs(session_dir, exist_ok=True)
    return session_dir

def remove_outliers_df(df: pd.DataFrame, thresh: float = 3.5, max_remove: int = 2) -> pd.DataFrame:
    """Remove up to max_remove strongest 2D outliers on 'x','y' using MAD-based method."""
    if df is None or df.empty or 'x' not in df.columns or 'y' not in df.columns:
        return df
    try:
        s = df[['x', 'y']].astype(float).copy()
        mx = s['x'].median()
        my = s['y'].median()
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
        to_drop_idx = candidates.sort_values(ascending=False).index[:max_remove]
        return df.drop(index=to_drop_idx)
    except Exception:
        return df

def get_ellipse_params(x, y):
    """Return width, height, angle (deg), area using PCA on covariance (fallback ellipse fit)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < 3:
        return 0.0, 0.0, 0.0, 0.0
    pts = np.column_stack([x, y])
    cov = np.cov(pts.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = eigvals.argsort()[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]
    # width/height are 2 * sqrt(eigval)
    width = 2.0 * math.sqrt(max(eigvals[0], 0.0))
    height = 2.0 * math.sqrt(max(eigvals[1], 0.0))
    angle = math.degrees(math.atan2(eigvecs[1, 0], eigvecs[0, 0]))
    area = math.pi * (width/2.0) * (height/2.0)
    return width, height, angle, area

def remove_outliers_xy(x: np.ndarray, y: np.ndarray, thresh: float = 3.5):
    """MAD-based filter for arrays."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < 5:
        return x, y
    mx = np.median(x)
    my = np.median(y)
    mad_x = np.median(np.abs(x - mx))
    mad_y = np.median(np.abs(y - my))
    if mad_x == 0 or mad_y == 0:
        return x, y
    zx = 0.6745 * (x - mx) / mad_x
    zy = 0.6745 * (y - my) / mad_y
    mask = (np.abs(zx) <= thresh) & (np.abs(zy) <= thresh)
    return x[mask], y[mask]

def compute_center_of_pressure(fl, fr, rl, rr):
    total = fl + fr + rl + rr
    if abs(total) < MIN_TOTAL_FORCE:
        return 0.0, 0.0
    x = ((fr + rr) - (fl + rl)) * (PLATFORM_SIZE_CM / 2) / total
    y = ((fl + fr) - (rl + rr)) * (PLATFORM_SIZE_CM / 2) / total
    return x, y

def random_unique_hex_colors(n):
    colors = set()
    while len(colors) < n:
        r = random.randint(30, 220)
        g = random.randint(30, 220)
        b = random.randint(30, 220)
        colors.add('#{:02x}{:02x}{:02x}'.format(r, g, b))
    return list(colors)

def get_all_csvs_in_dir(folder):
    return sorted([f for f in os.listdir(folder) if f.lower().endswith('.csv')])

# ---------------- Main Window ----------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('EquiliSense - Unified Interface')
        self._build_ui()
        self._init_runtime()
        self._start_serial_thread()

    def _build_ui(self):
        root = QHBoxLayout()
        self.setLayout(root)

        # Left: Plot
        left_box = QVBoxLayout()
        self.graphics = GraphicsLayoutWidget()
        left_box.addWidget(self.graphics)
        self.plot = self.graphics.addPlot()
        self.plot.setAspectLocked(True)
        self.plot.showGrid(x=True, y=True)
        self.plot.setXRange(-PLOT_RANGE_CM/2, PLOT_RANGE_CM/2)
        self.plot.setYRange(-PLOT_RANGE_CM/2, PLOT_RANGE_CM/2)
        self.plot.setLabel('bottom', 'X (cm)')
        self.plot.setLabel('left', 'Y (cm)')
        platform_rect = QGraphicsRectItem(-PLATFORM_SIZE_CM/2, -PLATFORM_SIZE_CM/2, PLATFORM_SIZE_CM, PLATFORM_SIZE_CM)
        platform_rect.setPen(pg.mkPen(color='w', width=2))
        self.plot.addItem(platform_rect)
        self.dot = self.plot.plot([0], [0], pen=None, symbol='o', symbolSize=10, symbolBrush='r')
        self.tracer = self.plot.plot([], [], pen=pg.mkPen('g', width=2))
        root.addLayout(left_box, 3)

        # Right: Controls
        right_box = QVBoxLayout()

        # Session and experiment controls
        session_group = QGroupBox('Session Settings')
        session_form = QFormLayout()
        self.session_input = QLineEdit()
        self.session_input.setPlaceholderText('Enter session name')
        self.session_dropdown = QComboBox()
        self._refresh_session_dropdown()
        self.session_dropdown.currentIndexChanged.connect(self._on_session_selected)
        session_form.addRow('Session:', self.session_input)
        session_form.addRow('Select Existing:', self.session_dropdown)
        self.experiment_combo = QComboBox()
        self.experiment_combo.addItems(list(EXPERIMENT_FILES.keys()) + ['cognitive'])
        session_form.addRow('Experiment:', self.experiment_combo)
        self.timer_combo = QComboBox()
        self.timer_combo.addItems(['5','10','20','30','60','120'])
        session_form.addRow('Duration (s):', self.timer_combo)
        session_group.setLayout(session_form)
        right_box.addWidget(session_group)

        # Person selector
        person_group = QGroupBox('Select Person (from csv_store)')
        p_layout = QVBoxLayout()
        self.person_dropdown = QComboBox()
        self._refresh_person_dropdown()
        self.person_dropdown.currentIndexChanged.connect(self._on_person_selected)
        p_layout.addWidget(self.person_dropdown)
        person_group.setLayout(p_layout)
        right_box.addWidget(person_group)

        # Recording & overlay controls
        self.record_btn = QPushButton('Start Recording')
        self.record_btn.clicked.connect(self._toggle_recording)
        right_box.addWidget(self.record_btn)

        self.overlay_btn = QPushButton('Show Overlay + Ellipses')
        self.overlay_btn.clicked.connect(self._do_overlay)
        right_box.addWidget(self.overlay_btn)

        self.clear_trace_btn = QPushButton('Clear Trace')
        self.clear_trace_btn.clicked.connect(self._clear_trace)
        right_box.addWidget(self.clear_trace_btn)

        self.clear_overlays_btn = QPushButton('Clear Overlays')
        self.clear_overlays_btn.clicked.connect(lambda: self._clear_overlays(keep_live=True))
        right_box.addWidget(self.clear_overlays_btn)

        # Live metrics box
        metrics_group = QGroupBox('Live Metrics')
        metrics_form = QFormLayout()
        self.lbl_fl = QLabel('0')
        self.lbl_fr = QLabel('0')
        self.lbl_rl = QLabel('0')
        self.lbl_rr = QLabel('0')
        self.lbl_total = QLabel('0')
        self.lbl_cop = QLabel('(0,0)')
        metrics_form.addRow('FL:', self.lbl_fl)
        metrics_form.addRow('FR:', self.lbl_fr)
        metrics_form.addRow('RL:', self.lbl_rl)
        metrics_form.addRow('RR:', self.lbl_rr)
        metrics_form.addRow('Total:', self.lbl_total)
        metrics_form.addRow('CoP (cm):', self.lbl_cop)
        metrics_group.setLayout(metrics_form)
        right_box.addWidget(metrics_group)

        # Area values display (static colored labels)
        self.area_group = QGroupBox('Overlay Areas (per CSV)')
        self.area_layout = QVBoxLayout()
        self.area_group.setLayout(self.area_layout)
        self.area_layout.addWidget(QLabel('Overlay: not computed'))
        right_box.addWidget(self.area_group)

        # overlay info label (multi-line summary)
        self.overlay_info = QLabel('Overlay: not computed')
        self.overlay_info.setWordWrap(True)
        right_box.addWidget(self.overlay_info)

        right_box.addStretch(1)
        root.addLayout(right_box, 1)

        axis_font = QFont()
        axis_font.setPointSize(10)
        self.plot.getAxis("bottom").setTickFont(axis_font)
        self.plot.getAxis("left").setTickFont(axis_font)

        # UI timer for updates
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self._update)
        self.ui_timer.start(50)

    def _init_runtime(self):
        self.data_lock = threading.Lock()
        self.cop_x = 0.0
        self.cop_y = 0.0
        self.trace = []
        self.recording = False
        self.csv_file = None
        self.running = True
        self.ser = None
        self.loadcell_offsets = None
        self.offset_sums = {pos: 0.0 for pos in POSITION_NAMES}
        self.offset_count = 0
        self.forces = {pos: 0.0 for pos in POSITION_NAMES}
        self.traces = []  # overlays stored here
        self.color_idx = 0
        self.record_timer = QTimer()
        self.record_timer.setSingleShot(True)
        self.record_timer.timeout.connect(self._on_record_timeout)

    # ---------------- Session helpers ----------------
    def _refresh_session_dropdown(self):
        if not os.path.exists(CSV_STORE_DIR):
            os.makedirs(CSV_STORE_DIR, exist_ok=True)
        sessions = [d for d in os.listdir(CSV_STORE_DIR) if os.path.isdir(os.path.join(CSV_STORE_DIR, d))]
        sessions.sort()
        self.session_dropdown.clear()
        self.session_dropdown.addItem('')
        self.session_dropdown.addItems(sessions)

    def _refresh_person_dropdown(self):
        if not os.path.exists(CSV_STORE_DIR):
            os.makedirs(CSV_STORE_DIR, exist_ok=True)
        people = [d for d in os.listdir(CSV_STORE_DIR) if os.path.isdir(os.path.join(CSV_STORE_DIR, d))]
        people.sort()
        self.person_dropdown.clear()
        if people:
            self.person_dropdown.addItems(people)
            self.person_dropdown.setCurrentIndex(0)
            self.session_input.setText(people[0])
        else:
            self.person_dropdown.addItem('')

    def _on_session_selected(self, idx):
        txt = self.session_dropdown.currentText()
        if txt:
            self.session_input.setText(txt)

    def _on_person_selected(self, idx):
        txt = self.person_dropdown.currentText()
        if txt:
            self.session_input.setText(txt)

    # ---------------- Recording ----------------
    def _toggle_recording(self):
        if self.recording:
            self._stop_recording()
            return
        sess = self.session_input.text().strip()
        if not sess:
            QMessageBox.warning(self, "No session", "Enter session name before recording.")
            return
        exp = self.experiment_combo.currentText()
        path = os.path.join(get_session_dir(sess), f"{exp}.csv")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        is_new = not os.path.exists(path)
        try:
            self.csv_file = open(path, 'a')
            if is_new:
                self.csv_file.write('x,y\n')
        except Exception as e:
            QMessageBox.critical(self, "File error", f"Cannot open file: {e}")
            return
        self.recording = True
        self.record_btn.setText('Stop Recording')
        try:
            secs = int(self.timer_combo.currentText())
        except Exception:
            secs = 10
        self.record_timer.start(secs * 1000)
        print(f"🔴 Recording started for {secs}s -> {path}")

    def _stop_recording(self):
        if not self.recording:
            return
        self.recording = False
        self.record_btn.setText('Start Recording')
        try:
            if self.csv_file:
                self.csv_file.close()
        except Exception:
            pass
        self.csv_file = None
        if self.record_timer.isActive():
            self.record_timer.stop()
        print("⏹️ Recording stopped.")

    def _on_record_timeout(self):
        self._stop_recording()
        QMessageBox.information(self, "Recording complete", "Recording finished (timer expired).")

    # ---------------- Serial thread ----------------
    def _start_serial_thread(self):
        t = threading.Thread(target=self._serial_loop, daemon=True)
        t.start()

    def _serial_loop(self):
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            print(f"✅ Connected to {SERIAL_PORT} at {BAUD_RATE}")
        except Exception as e:
            print("❌ Serial connection failed:", e)
            self.ser = None
            return

        offset_acc = {pos: 0.0 for pos in POSITION_NAMES}
        count = 0
        while self.ser and self.running:
            try:
                line = self.ser.readline().decode(errors='ignore').strip()
                if not line or '=' in line or 'Calibrating' in line or 'Done' in line or 'Counts' in line:
                    continue
                parts = line.split()
                if len(parts) < 8:
                    continue
                try:
                    vals = list(map(float, parts))
                except Exception:
                    continue
                raw_rl, raw_fr, raw_fl, raw_rr = vals[-4], vals[-3], vals[-2], vals[-1]
                if self.loadcell_offsets is None:
                    offset_acc['RL'] += raw_rl
                    offset_acc['FR'] += raw_fr
                    offset_acc['FL'] += raw_fl
                    offset_acc['RR'] += raw_rr
                    count += 1
                    if count >= OFFSET_SAMPLE_COUNT:
                        self.loadcell_offsets = {k: (offset_acc[k] / count) for k in offset_acc}
                        print("✅ Offsets established:", self.loadcell_offsets)
                    continue
                rl_val = raw_rl - self.loadcell_offsets['RL']
                fr_val = raw_fr - self.loadcell_offsets['FR']
                fl_val = raw_fl - self.loadcell_offsets['FL']
                rr_val = raw_rr - self.loadcell_offsets['RR']
                x, y = compute_center_of_pressure(fl_val, fr_val, rl_val, rr_val)
                with self.data_lock:
                    self.cop_x, self.cop_y = x, y
                    self.trace.append((x, y, time.time()))
                    cutoff = time.time() - TRACE_HISTORY_SECONDS
                    self.trace = [(xx, yy, t) for (xx, yy, t) in self.trace if t >= cutoff]
                    if self.recording and self.csv_file:
                        try:
                            self.csv_file.write(f"{x},{y}\n")
                        except Exception:
                            pass
                time.sleep(0.00)
            except Exception:
                time.sleep(0.00)
                continue

    # ---------------- Clear trace ----------------
    def _clear_trace(self):
        with self.data_lock:
            self.trace = []
            try:
                self.tracer.setData([], [])
            except Exception:
                pass
        print("🧹 Live trace cleared.")

    # ---------------- Overlay logic (user-provided code merged) ----------------
    def _do_overlay(self):
        # Overlay four experiment files for all selected sessions
        session_names = [self.session_input.text()]
        # Add all selected from dropdown if not empty and not duplicate
        dropdown_name = self.session_dropdown.currentText()
        if dropdown_name and dropdown_name not in session_names:
            session_names.append(dropdown_name)
        # Use a large set of dark colors for traces
        DARK_COLORS = [
            '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4', '#46f0f0',
            '#f032e6', '#bcf60c', '#fabebe', '#008080', '#e6beff', '#9a6324', '#fffac8',
            '#800000', '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080', "#3F1131",
            '#1a1a1a', '#2d2d2d', '#333366', '#660066', '#993333', '#003300', '#003366',
            '#4b0082', '#191970', '#483d8b', '#2f4f4f', '#008b8b', '#556b2f', '#8b0000',
            '#8b008b', '#b22222', '#228b22', '#6b8e23', '#191970', '#00008b', '#8b4513',
            '#2e0854', '#013220', '#36454f', '#232b2b', '#0b0b0b', '#22313f', '#1c2833',
            '#212f3c', '#17202a', '#283747', '#212f3c', '#1b2631', '#212f3c', '#1c1c1c',
            '#2c3e50', '#34495e', '#22313f', '#2c2c2c', '#222222', "#EBE2E2", '#333333',
        ]
        colors = DARK_COLORS
        # Clear plot but re-draw platform and keep ability to add live items later
        self.plot.clear()
        self.plot.setAspectLocked(True)
        self.plot.showGrid(x=True, y=True)
        self.plot.setXRange(-PLOT_RANGE_CM/2, PLOT_RANGE_CM/2)
        self.plot.setYRange(-PLOT_RANGE_CM/2, PLOT_RANGE_CM/2)
        self.plot.setLabel('bottom', 'X (cm)')
        self.plot.setLabel('left', 'Y (cm)')
        platform_rect = QGraphicsRectItem(-PLATFORM_SIZE_CM/2, -PLATFORM_SIZE_CM/2, PLATFORM_SIZE_CM, PLATFORM_SIZE_CM)
        platform_rect.setPen(pg.mkPen(color='w', width=2))
        self.plot.addItem(platform_rect)

        summary_lines = []
        color_idx = 0
        # Add legend
        legend = self.plot.addLegend(offset=(30, 30))
        # Clear previous stored traces list (we'll re-populate)
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
                    color = colors[color_idx % len(colors)]
                    # ---- FIX: removed name=... from plot() to prevent duplicate legend entries ----
                    curve = self.plot.plot(x, y, pen=pg.mkPen(color=color, width=2))
                    try:
                        legend.addItem(curve, f"{session_name}-{key}")
                    except Exception:
                        pass
                    # Compute ellipse parameters and area using get_ellipse_params
                    try:
                        width, height, angle, area = get_ellipse_params(x, y)
                        summary_lines.append(f"{session_name}-{key}: area = {area:.2f} cm^2")
                    except Exception as e:
                        summary_lines.append(f"{session_name}-{key}: area error {e}")
                    # store overlay objects so we can clear later
                    self.traces.append({'curve': curve, 'name': f"{session_name}-{key}", 'area': (area if 'area' in locals() else 0.0), 'color': color})
                    color_idx += 1
                except Exception as e:
                    summary_lines.append(f"{session_name}-{key}: error {e}")
                    continue

        # Update overlay info label
        self.overlay_info.setText("\n".join(summary_lines) if summary_lines else "Overlay: not computed")
        # Update static area_layout (clear and add color-labeled QLabels)
        for i in reversed(range(self.area_layout.count())):
            w = self.area_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        if self.traces:
            for rec in self.traces:
                lbl = QLabel(f"{rec['name']}: {rec.get('area',0.0):.2f} cm²")
                # color the label text same as curve color
                lbl.setStyleSheet(f"color: {rec['color']};")
                self.area_layout.addWidget(lbl)
        else:
            self.area_layout.addWidget(QLabel('Overlay: not computed'))

        # re-add live dot and tracer on top so live info remains visible
        self.dot = self.plot.plot([self.cop_x], [self.cop_y], pen=None, symbol='o', symbolSize=10, symbolBrush='r')
        self.tracer = self.plot.plot([], [], pen=pg.mkPen('g', width=2))

    def _clear_overlays(self, keep_live=False):
        # remove overlay items previously plotted
        for rec in getattr(self, 'traces', []):
            try:
                if rec.get('curve') is not None:
                    self.plot.removeItem(rec['curve'])
            except Exception:
                pass
        self.traces = []
        # clear area layout
        for i in reversed(range(self.area_layout.count())):
            w = self.area_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        self.area_layout.addWidget(QLabel('Overlay: not computed'))
        self.overlay_info.setText('Overlay: not computed')
        if not keep_live:
            # clear entire plot and redraw platform
            self.plot.clear()
            platform_rect = QGraphicsRectItem(-PLATFORM_SIZE_CM/2, -PLATFORM_SIZE_CM/2, PLATFORM_SIZE_CM, PLATFORM_SIZE_CM)
            platform_rect.setPen(pg.mkPen(color='w', width=2))
            self.plot.addItem(platform_rect)
            self.dot = self.plot.plot([self.cop_x], [self.cop_y], pen=None, symbol='o', symbolSize=10, symbolBrush='r')
            self.tracer = self.plot.plot([], [], pen=pg.mkPen('g', width=2))
        else:
            # keep platform for live trace
            platform_rect = QGraphicsRectItem(-PLATFORM_SIZE_CM/2, -PLATFORM_SIZE_CM/2, PLATFORM_SIZE_CM, PLATFORM_SIZE_CM)
            platform_rect.setPen(pg.mkPen(color='w', width=2))
            self.plot.addItem(platform_rect)

    # ---------------- Update UI ----------------
    def _update(self):
        with self.data_lock:
            try:
                self.dot.setData([self.cop_x], [self.cop_y])
            except Exception:
                pass
            if self.trace:
                xs = [p[0] for p in self.trace]
                ys = [p[1] for p in self.trace]
                try:
                    self.tracer.setData(xs, ys)
                except Exception:
                    pass
            self.lbl_fl.setText(f"{self.forces.get('FL', 0.0):.1f}")
            self.lbl_fr.setText(f"{self.forces.get('FR', 0.0):.1f}")
            self.lbl_rl.setText(f"{self.forces.get('RL', 0.0):.1f}")
            self.lbl_rr.setText(f"{self.forces.get('RR', 0.0):.1f}")
            total_force = sum(self.forces.values()) if self.forces else 0.0
            self.lbl_total.setText(f"{total_force:.1f}")
            self.lbl_cop.setText(f"({self.cop_x:.2f}, {self.cop_y:.2f})")

    def closeEvent(self, event):
        self.running = False
        try:
            if self.csv_file:
                self.csv_file.close()
        except Exception:
            pass
        try:
            if self.ser and getattr(self.ser, 'is_open', False):
                self.ser.close()
        except Exception:
            pass
        event.accept()

# ---------------- Run ----------------
def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
