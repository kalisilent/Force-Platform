# EquiliSense / ronak

Unified tools for a real-time 4-loadcell force platform: live CoP viewer, recording, and multi-file overlay with ellipse metrics.

## Expected serial format
- Space/tab separated values. Example line:
  - `-1109 -0.002613 818 0.001927 -10385 -0.024470 -7215 -0.017000 -4.431 3.686`
- Indices 0,2,4,6 are the raw counts for the 4 load cells.
- CoP is computed in cm using platform size 47 x 47 cm.

## Install (PowerShell)
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install pyqtgraph PyQt5 pyserial pandas numpy
```

## Run the unified interface
```powershell
$env:FORCE_PLATFORM_PORT = 'COM13'   # set your COM port
python interface/main_interface.py
```
- Large 50 x 50 cm plot, 47 x 47 cm outline.
- Buttons: Start/Stop Recording, Show Overlay + Ellipses, Clear Trace.
- Recording writes `csv/New{n}kg.csv` (header: `x,y`).

## Overlay viewer (from unified interface)
- Click "Show Overlay + Ellipses" to load all `csv/New{n}kg.csv` files, plot them, and draw a 2-sigma covariance ellipse around each trace.
- Reported per-file metrics: major axis (a), minor axis (b), and area in cm^2.

## Verify
1. Connect Arduino and start unified interface.
2. Confirm console shows offsets after ~50 samples.
3. Press Start Recording, move on platform, then Stop Recording.
4. Confirm a new CSV appears under `csv/` with `x,y` values in cm.
5. Click Overlay to see traces and ellipse metrics.

## Sanity checks
```powershell
python sanity_checks.py
```
- Validates example serial line and an example CSV path.

## Notes
- Serial parsing: robust via `line.split()`; skips non-numeric lines.
- Load cell mapping: `{'FR':1,'FL':2,'RR':3,'RL':0}` mapped from indices [0,2,4,6].
- CoP: always in cm; plot is centered at (0,0).

## Optional
- Set environment variable `FORCE_PLATFORM_BAUD` to change baud (default 115200).
- Tune `OFFSET_SAMPLE_COUNT`, `FORCE_DEADBAND` in `interface/main_interface.py`.
