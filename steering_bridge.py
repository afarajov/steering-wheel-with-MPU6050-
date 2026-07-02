#!/usr/bin/env python3
"""
Steering Wheel Bridge - Pseudo-Analog (WASD)
--------------------------------------------
Reads the ESP32-C3 steering-wheel serial stream and translates it into
WASD key presses for browser racing games.

Steering is PSEUDO-ANALOG: instead of holding the steer key fully, the key
is pulsed on/off within a short window, and the fraction of time it's held
("duty cycle") scales with how far you've turned the wheel. Small angle =
brief taps (gentle turn); large angle = nearly solid (hard turn). The game
averages these into a proportional turn rate, so you get fine steering
instead of all-or-nothing.

Pedals (accel/brake) are simple held keys.

Serial line format from the firmware:
    ANGLE,ACCEL,BRAKE      e.g.  -23.5,1,0

Requirements:
    pip3 install pyserial pynput

macOS note:
    Grant Accessibility permission to your terminal app:
    System Settings -> Privacy & Security -> Accessibility -> enable Terminal.

Usage:
    python3 steering_bridge.py
"""

import sys
import time

try:
    import serial
except ImportError:
    sys.exit("Missing dependency: run  pip3 install pyserial")

try:
    from pynput.keyboard import Controller
except ImportError:
    sys.exit("Missing dependency: run  pip3 install pynput")


# ---------------- Configuration ----------------
SERIAL_PORT = "/dev/cu.usbmodem1401"   # change if your port differs
BAUD_RATE   = 115200

# Key mapping (WASD)
KEY_LEFT  = 'a'
KEY_RIGHT = 'd'
KEY_ACCEL = 'w'
KEY_BRAKE = 's'

# Steering feel
DEAD_ZONE        = 7.0    # within +-7 deg of center = no steering at all
MAX_STEER_ANGLE  = 55.0   # angle (deg) that maps to full steering (duty 100%)
PWM_PERIOD       = 0.07   # seconds per pulse cycle (smaller = finer, busier)
FULL_LOCK_DUTY   = 0.92   # above this duty, just hold the key solid

# Safety: if no data arrives for this long, release all keys
DATA_TIMEOUT_S   = 0.5
# -----------------------------------------------


keyboard = Controller()

# Track which keys we are currently holding so we only press/release on change
held = {"left": False, "right": False, "up": False, "down": False}


def set_key(name, key, should_hold):
    """Press or release a key only when its state changes."""
    if should_hold and not held[name]:
        keyboard.press(key)
        held[name] = True
    elif not should_hold and held[name]:
        keyboard.release(key)
        held[name] = False


def release_all():
    set_key("left",  KEY_LEFT,  False)
    set_key("right", KEY_RIGHT, False)
    set_key("up",    KEY_ACCEL, False)
    set_key("down",  KEY_BRAKE, False)


def parse_line(line):
    """Parse 'ANGLE,ACCEL,BRAKE' -> (angle, accel, brake) or None."""
    parts = line.strip().split(",")
    if len(parts) != 3:
        return None
    try:
        angle = float(parts[0])
        accel = int(parts[1])
        brake = int(parts[2])
    except ValueError:
        return None
    return angle, accel, brake


def steering_duty(angle):
    """Map |angle| to a 0..1 duty cycle, respecting the dead zone."""
    a = abs(angle)
    if a <= DEAD_ZONE:
        return 0.0
    d = (a - DEAD_ZONE) / (MAX_STEER_ANGLE - DEAD_ZONE)
    if d < 0.0:
        d = 0.0
    elif d > 1.0:
        d = 1.0
    return d


def main():
    print("Steering Wheel Bridge - Pseudo-Analog (WASD)")
    print("============================================")
    print(f"Connecting to {SERIAL_PORT} at {BAUD_RATE} baud...")

    try:
        # Small timeout so the loop spins fast enough for smooth pulsing
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.005)
    except serial.SerialException as e:
        sys.exit(f"Could not open serial port: {e}\n"
                 f"Check the port name and that the Arduino Serial Monitor is CLOSED.")

    time.sleep(2)  # let the board reset/settle
    ser.reset_input_buffer()
    print("Connected. Steering active. Press Ctrl+C to stop.\n")

    # Current state (updated whenever a serial line arrives)
    angle = 0.0
    accel = 0
    brake = 0

    last_data_time = time.time()
    last_status = 0.0

    try:
        while True:
            # --- Pull the latest serial line, if any ---
            line = ser.readline().decode("utf-8", errors="ignore")
            if line:
                parsed = parse_line(line)
                if parsed is not None:
                    angle, accel, brake = parsed
                    last_data_time = time.time()

            now = time.time()

            # --- Safety: stale data -> neutralize everything ---
            if now - last_data_time > DATA_TIMEOUT_S:
                angle, accel, brake = 0.0, 0, 0

            # --- Pseudo-analog steering via duty-cycle pulsing ---
            duty = steering_duty(angle)
            direction = None
            if duty > 0.0:
                direction = "left" if angle < 0 else "right"

            if direction is None:
                left_hold = right_hold = False
            elif duty >= FULL_LOCK_DUTY:
                # Strong turn: just hold the key solid
                left_hold  = (direction == "left")
                right_hold = (direction == "right")
            else:
                # Pulse: key is "on" for the first `duty` fraction of each cycle
                phase = (now % PWM_PERIOD) / PWM_PERIOD   # 0..1
                on = phase < duty
                left_hold  = on and direction == "left"
                right_hold = on and direction == "right"

            set_key("left",  KEY_LEFT,  left_hold)
            set_key("right", KEY_RIGHT, right_hold)

            # --- Pedals (simple held keys) ---
            set_key("up",   KEY_ACCEL, accel == 1)
            set_key("down", KEY_BRAKE, brake == 1)

            # --- Throttled status line (every ~100 ms) ---
            if now - last_status > 0.1:
                last_status = now
                dirch = "<" if direction == "left" else (">" if direction == "right" else "-")
                status = (f"\rangle={angle:7.1f}  steer {dirch} duty={duty*100:5.1f}%  "
                          f"{'ACCEL' if accel else '     '} "
                          f"{'BRAKE' if brake else '     '}")
                sys.stdout.write(status)
                sys.stdout.flush()

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        release_all()
        ser.close()
        print("All keys released. Serial closed. Bye!")


if __name__ == "__main__":
    main()