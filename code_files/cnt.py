# continuous_raw_reader.py
# Continuously prints raw values from your force platform serial port
# Run this after flashing the correct streaming firmware

import serial
import time
from datetime import datetime

# Configuration
PORT = 'COM13'
BAUD_RATE = 115200
TIMEOUT = 1.0  # seconds

def main():
    print("=== Continuous Raw Serial Reader ===")
    print(f"Port: {PORT} | Baud: {BAUD_RATE}")
    print("Will print every incoming line non-stop.")
    print("Press Ctrl+C to stop.")
    print("===================================\n")

    ser = None

    try:
        # Open serial connection
        ser = serial.Serial(PORT, BAUD_RATE, timeout=TIMEOUT)
        print(f"[{get_time()}] Connected to {PORT} successfully!")

        # Give the device a moment to stabilize
        time.sleep(1)

        while True:
            # Read one line
            line = ser.readline().decode('utf-8', errors='replace').strip()
            
            if line:  # Only print if there's content
                timestamp = get_time()
                print(f"[{timestamp}] {line}")

            # Tiny sleep to avoid CPU overload (adjust if needed)
            time.sleep(0.001)  # ~1000 Hz loop, but actual rate depends on device

    except serial.SerialException as e:
        print(f"\nError: Could not connect or connection lost: {e}")
        print("Make sure the device is plugged in and no other program is using COM13.")
    
    except KeyboardInterrupt:
        print("\nStopped by user (Ctrl+C).")
    
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    
    finally:
        if ser and ser.is_open:
            ser.close()
            print(f"[{get_time()}] Serial port closed cleanly.")

def get_time():
    """Return current time in HH:MM:SS format"""
    return datetime.now().strftime("%H:%M:%S")

if __name__ == "__main__":
    main()