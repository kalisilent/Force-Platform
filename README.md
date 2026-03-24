
# Force Platform Development and Data Analysis

## Overview of This Semester’s Work

This semester focused on improving, validating, and extending the existing force platform system. The primary goal during this term was to build a more robust prototype, experimentally characterize the hardware, validate the electronics, and strengthen the data analysis and visualization through improved software and user interface design.

The work carried out this semester can broadly be divided into three phases: development of a new physical prototype, experimental validation of sensors and electronics, and extension of the software for real-time visualization and post-processing analysis.

---

## Development of a New Force Platform Prototype

At the beginning of the semester, a new force platform prototype was designed and assembled.This version of the platform used **S-type load cells**, which are stronger and more reliable than the sensors used earlier.

The platform was initially constructed on a **50 cm × 50 cm square plywood board (Ecorec MR 303)**. This material provided a stable, rigid, and durable base while still being easy to fabricate and modify during prototyping. The size ensured sufficient standing area for human subjects while maintaining symmetry for accurate force distribution measurements.

---

## Characterization of the HX711 ADC Module

A significant part of this semester was dedicated to experimentally verifying the performance of the **HX711 amplifier and ADC module**. Although the HX711 is marketed as a 24-bit ADC, practical performance can be limited by electrical noise, amplifier stability, and real-world sensor behavior.

To study this, a dedicated experiment was conducted using an HX711 module connected to a **potentiometer** and monitored simultaneously with a **multimeter**. By slowly varying the potentiometer and observing the digital output from the HX711, it was found that the effective resolution was lower than the theoretical 24 bits. The experimental observations suggested that the usable resolution was closer to **14–16 bits**, primarily due to noise and quantization effects. This experiment helped set realistic expectations for sensor precision and informed later decisions on filtering and data processing.

---

## Sensor, Amplifier, and Assembly Validation

Following the ADC experiment, systematic testing and characterization of individual system components were carried out. The load cells were tested under known loads to verify linearity and repeatability. The HX711 amplifiers were examined for stability and noise behavior during long-duration measurements.

During the full assembly process, common lab tools such as a drill machine, Arduino board, crocodile clips, and jumper wires were used to prototype and test the system. This hands-on approach allowed quick finish and debugging, leading to a fully functional integrated setup where sensors, amplifiers, and the microcontroller worked reliably together.

---

## Dead-Weight Experiments and Data Collection

Once the hardware setup was finalized, controlled experiments were conducted using calibrated dead weights. A total range of weights from **5 kg up to 100 kg** was used, increasing in steps of 5 kg. For each weight, the mass was placed at a fixed position on the platform, and the **Center of Pressure (CoP)** was recorded continuously for approximately **2–3 minutes**.

This process was repeated for each weight value to study the stability, drift, and noise characteristics of the CoP under static loading conditions. These experiments provided baseline data that was later used to validate the consistency of the platform.

---

## User Interface and Experiment Workflow

In the later part of the semester, the focus shifted toward improving the software interface and experiment workflow. A graphical user interface was developed to allow users to conduct experiments more intuitively. Through this interface, it became possible to start and stop experiments, observe **real-time sway traces**, and record data directly from the platform.

In addition to live visualization, the UI also allowed previously recorded experiments to be loaded and displayed on a **stabilogram**, making it easier to compare trials and visually analyze balance behavior across different conditions. This feature was particularly useful for making qualitative assumptions about stability, drift, and symmetry.

---

## New Functions Introduced in the Code

Several important data processing functions were introduced this semester to improve robustness and analysis quality.

One key addition was a function to remove outliers from CoP data using a **Median Absolute Deviation (MAD)** based method. This approach is well-suited for balance data, where occasional spikes can occur due to sensor noise or sudden disturbances.

```python
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
```

This function identifies extreme CoP points relative to the median position and removes only the strongest outliers, preserving the natural sway structure while eliminating physically unrealistic values.

Another important addition was a function to extract sway area from the CoP trajectory by fitting an ellipse using **Principal Component Analysis (PCA)**. This allows compact representation of sway behavior through parameters such as width, height, orientation, and area.

```python
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
    width = 2.0 * math.sqrt(max(eigvals[0], 0.0))
    height = 2.0 * math.sqrt(max(eigvals[1], 0.0))
    angle = math.degrees(math.atan2(eigvecs[1, 0], eigvecs[0, 0]))
    area = math.pi * (width/2.0) * (height/2.0)
    return width, height, angle, area
```

These parameters were later used to compare stability across different experimental conditions.

---

## Experimental Conditions and Data Analysis

To systematically analyze balance behavior, experiments were grouped into different conditions, each stored as a separate dataset. These conditions included standing with eyes open, eyes closed, standing on the right leg, and standing on the left leg.

```python
EXPERIMENT_FILES = {
    'eyes_open': 'eyes_open.csv',
    'eyes_closed': 'eyes_closed.csv',
    'one_leg_right': 'one_leg_right.csv',
    'one_leg_left': 'one_leg_left.csv',
}
```

For these datasets, extensive data analysis was carried out. Histogram-based analyses were used to study segment lengths and sway distributions. Overlay plots and peakness histograms were generated to visually compare balance characteristics across conditions. A 2×2 grid of histograms was used to clearly show differences in sway behavior between normal standing and more challenging postures.

---

## Summary of Semester Contributions

Overall, this semester strengthened the project both experimentally and analytically. The introduction of a new, more robust force platform prototype, systematic validation of the HX711 ADC, controlled dead-weight experiments, and the development of improved data processing and visualization tools significantly enhanced the reliability and usefulness of the system. 
---

