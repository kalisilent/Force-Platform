import pandas as pd
import numpy as np
from scipy.signal import filtfilt
from scipy.stats import chi2
import glob
import os

# ────────────────────────────────────────────────
# SETTINGS - CHANGE ONLY THESE IF NEEDED
# ────────────────────────────────────────────────
TRIAL_TIME = 30.0                  # seconds (fixed for all trials)
KERNEL_SIZE = 5                    # 5, 7 or 9
SMOOTHED = True                    # recommended

FOLDER = r'C:\Users\Plaksha.PLAKSHA111\OneDrive - Plaksha University\Desktop\yts\Stable\EquiliSense\EquiliSense\ronak\csv_store\Deepan2_male_37'
CSV_PATTERN = os.path.join(FOLDER, '*.csv')  # all csv files in this folder

# ────────────────────────────────────────────────
# FUNCTIONS
# ────────────────────────────────────────────────





def compute_sway_metrics(x, y, duration, smoothed=True):
    
    x_f, y_f = x, y

    path_t = np.sqrt(np.diff(x_f)**2 + np.diff(y_f)**2).sum()
    path_ap = np.abs(np.diff(x_f)).sum()
    path_ml = np.abs(np.diff(y_f)).sum()

    v_t = path_t / duration
    v_ap = path_ap / duration
    v_ml = path_ml / duration


    return {
        'Path-T cm': path_t,
        'Path-AP cm': path_ap,
        'Path-ML cm': path_ml,
        'V-T cm/s': v_t,
        'V-AP cm/s': v_ap,
        'V-ML cm/s': v_ml,
    }


# ────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────
files = glob.glob(CSV_PATTERN)
if not files:
    print("No CSV files found in folder:")
    print(FOLDER)
    exit()

results = []

for filepath in files:
    filename = os.path.basename(filepath)
    if 'eyes_open' in filename.lower():
        condition = 'eyes_open'
    elif 'eyes_closed' in filename.lower():
        condition = 'eyes_closed'
    elif 'one_leg_left' in filename.lower():
        condition = 'one_leg_left'
    elif 'one_leg_right' in filename.lower():
        condition = 'one_leg_right'
    else:
        condition = filename.replace('.csv', '')

    try:
        df = pd.read_csv(filepath, header=0, usecols=['x', 'y'])
        df = df.dropna()
        x = df['x'].values
        y = df['y'].values

        N = len(x)
        if N < 500:
            print(f"Warning: {filename} has only {N} points → skipping")
            continue

        # Dynamic fs per file
        fs = N / TRIAL_TIME
        duration = TRIAL_TIME  # Fixed, but fs is now dynamic for display

        metrics = compute_sway_metrics(x, y, duration, SMOOTHED)
        metrics['Condition'] = condition
        metrics['File'] = filename
        metrics['Points'] = N
        metrics['fs (Hz)'] = fs
        results.append(metrics)

        print(f"Processed: {condition}  ({N} points, fs={fs:.1f} Hz)")

    except Exception as e:
        print(f"Error reading {filename}: {e}")

# ────────────────────────────────────────────────
# SHOW TABLE
# ────────────────────────────────────────────────
if results:
    df_results = pd.DataFrame(results)
    cols = ['Condition', 'Path-T cm', 'Path-AP cm', 'Path-ML cm',
            'V-T cm/s', 'V-AP cm/s', 'V-ML cm/s', 'Points', 'fs (Hz)']
    df_results = df_results[cols]

    print(f"\nDeepan2_male_37 – 30-second trials (smoothed={SMOOTHED})\n")

    # Terminal table
    print(df_results.round(3).to_string(index=False))

    # Save
    output_file = os.path.join(FOLDER, 'Deepan2_male_37_all_conditions.csv')
    df_results.to_csv(output_file, index=False)
    print(f"\nSaved full table to: {output_file}")
else:
    print("No valid files processed.")


# ────────────────────────────────────────────────
    # SIMPLE EXPLANATIONS OF EACH MEASURE (Units: cm for paths/vels, cm² for area)
    # ────────────────────────────────────────────────
    
    # Total distance the center of pressure (CoP) traveled during 30 seconds
    # → like how much "ink" was used to draw the wiggly line
    # Higher number = more overall movement / less stable
    
    # Distance traveled only forward-backward (anterior-posterior = AP)
    # → how much the person swayed front-to-back
    # Useful to see if instability is more in the ankle direction
    
    # Distance traveled only side-to-side (medial-lateral = ML)
    # → how much the person swayed left-to-right
    # Usually bigger in single-leg standing or when hips are working more
    
    # Average speed of the CoP movement (total distance ÷ 30 seconds)
    # → how fast the CoP was moving on average
    # Higher speed usually means poorer control / more corrections
    
    # Average front-back speed (AP direction only)
    # → how quickly the person was rocking forward and backward
    
    # Average side-to-side speed (ML direction only)
    # → how quickly the person was shifting weight left-right