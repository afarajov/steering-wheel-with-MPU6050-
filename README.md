# 🏎️ IMU Racing Wheel Controller

> A custom steering wheel controller for browser-based racing games — built from
> an ESP32-C3 and an MPU6050 IMU, with a pseudo-analog steering scheme that
> translates physical wheel rotation into smooth, proportional keyboard input.

## About

Standard racing games expect either a real steering wheel peripheral or raw
keyboard input (A/D for left/right) — nothing in between. I wanted wheel-like
control without buying dedicated hardware, so I built one: an MPU6050 measures
the physical rotation of a handheld wheel, an ESP32-C3 streams that angle over
serial, and a Python bridge on the host machine converts it into keyboard
input the game already understands.

The interesting part wasn't reading the sensor — it was making a *digital*
key-press feel *analog*. A held key is either on or off; there's no "turn the
wheel 20%" signal you can send to a browser game. To solve this, the bridge
pulses the steering key on and off at high frequency, with the fraction of
time it's "on" (duty cycle) proportional to how far the wheel is turned. The
game reads this as a smooth, proportional turn rate instead of an abrupt
on/off snap.

## What it does

- **Reads wheel angle** via an MPU6050 IMU over I2C (custom SDA/SCL pin mapping
  on the ESP32-C3 Super Mini)
- **Reads pedal input** — [accelerator/brake via buttons — analog] 
- **Streams `ANGLE,ACCEL,BRAKE`** over serial at 115200 baud
- **Converts angle → pseudo-analog steering** using duty-cycle pulsing, with a
  configurable dead zone, response curve, and full-lock threshold
- **Live preset switching** — swap steering feel (gentle / sensitive / linear /
  eased) on the fly with a hotkey, no restart needed
- **Safety timeout** — if the serial connection drops or data goes stale, all
  keys are released automatically so the wheel can't get "stuck" turning

## Why I built it (and what I learned)

I built this to play browser racing games with a real wheel-like feel without
buying a $100+ peripheral. The firmware itself was a fairly standard I2C sensor
read, but tuning the steering *feel* turned into the real engineering problem.

The key discovery: different games interpret a held key differently. Some
apply an instant full turn the moment the key goes down; others have their
own internal easing or spring-back. That means there's no single "correct"
response curve — the right curve depends on the game, not just the hardware.
Once I noticed this by testing across a few games, I built a preset system so
I could switch tuning profiles live instead of editing config values and
restarting every time.

## Tech stack

- **Firmware:** Arduino (C++) on ESP32-C3 Super Mini, Adafruit MPU6050 library, I2C
- **Bridge:** Python 3, `pyserial` for the serial link, `pynput` for synthetic keyboard input

## Built with AI assistance — what I actually understand

I used Claude to help write and tune parts of this project, particularly the
preset-switching system and the response-curve math. To be transparent about
where my understanding is solid vs. assisted:

- **I understand fully:** the duty-cycle pulsing concept, the serial protocol
  between firmware and bridge, the dead-zone/response-curve logic, and why the
  safety timeout is necessary
- **AI-assisted:** the live hotkey preset-switching implementation, and fine
  numerical tuning of the response curve constants (`RESPONSE_EXP`, `MIN_DUTY`)
  through iterative testing

## Hardware

- ESP32-C3 Super Mini
- MPU6050 (accelerometer + gyroscope)
- Two buttons used as acceleration and brakes (brakes -> GPIO4 ; accel -> GPIO3)
- I2C wiring: SDA → GPIO20, SCL → GPIO10 (remapped from default pins)

## Running it

**Firmware:**
Flash `SteeringWheel_Firmware.ino` to the ESP32-C3 via Arduino IDE
(board: ESP32-C3 Dev Module or Super Mini, whichever matches your board).

**Bridge (host machine):**
```bash
pip3 install pyserial pynput
python3 steering_bridge.py
```

> macOS: grant Accessibility (and Input Monitoring, for hotkeys) permissions
> to your terminal app under System Settings → Privacy & Security.

Press `1`–`4` while the bridge is running to switch steering-feel presets live.

## Status

A working personal project, tuned for a few specific browser racing games.
Not a general-purpose product — steering feel may need retuning for other games.

---
*Part of my journey learning applied software & embedded/AI engineering.*
