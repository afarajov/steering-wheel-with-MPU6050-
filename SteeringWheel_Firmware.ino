/*
 * Steering Wheel Controller - Firmware
 * ESP32-C3 SuperMini + MPU6050
 *
 * Reads steering angle from the accelerometer (drift-free, gravity-based)
 * and two button states, then streams everything over USB serial.
 *
 * A Python bridge on the computer reads this stream and converts it into
 * arrow-key presses for browser racing games.
 *
 * Wiring:
 *   MPU6050 VCC -> 3.3V
 *   MPU6050 GND -> GND
 *   MPU6050 SDA -> GPIO20
 *   MPU6050 SCL -> GPIO10
 *   Accel button -> GPIO3  (other leg to GND)
 *   Brake button -> GPIO4  (other leg to GND)
 *
 * Serial format (one line per update, 50 Hz):
 *   ANGLE,ACCEL,BRAKE
 *   e.g.  -23.5,1,0
 *   ANGLE  = steering angle in degrees (negative = left, positive = right)
 *   ACCEL  = 1 if accelerator pressed, else 0
 *   BRAKE  = 1 if brake pressed, else 0
 */

#include <Wire.h>
#include <math.h>

// ---------- Pin configuration ----------
#define I2C_SDA     20
#define I2C_SCL     10
#define BTN_ACCEL   3
#define BTN_BRAKE   4

// ---------- MPU6050 registers ----------
#define MPU6050_ADDR  0x68
#define PWR_MGMT_1    0x6B
#define ACCEL_CONFIG  0x1C
#define ACCEL_XOUT_H  0x3B

// ---------- Tuning ----------
// Smoothing factor for the angle (0..1). Lower = smoother but laggier.
// 0.2 is a good balance for steering.
#define SMOOTH_ALPHA  0.2

// How often we send data (50 Hz = every 20 ms)
#define UPDATE_INTERVAL_MS  20

// Calibrated "center" angle. After flashing, hold the wheel level and read
// the raw angle from serial, then set this so centered reads ~0.
float centerOffset = 0.0;

// Smoothed angle state
float smoothedAngle = 0.0;

unsigned long lastUpdate = 0;

void setup() {
  Serial.begin(115200);
  delay(500);

  // Buttons use internal pull-ups: pressed = LOW
  pinMode(BTN_ACCEL, INPUT_PULLUP);
  pinMode(BTN_BRAKE, INPUT_PULLUP);

  // Start I2C and wake the MPU6050
  Wire.begin(I2C_SDA, I2C_SCL);
  delay(100);

  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(PWR_MGMT_1);
  Wire.write(0x00);            // clear sleep bit
  Wire.endTransmission();
  delay(100);

  // Accelerometer range +-2g for best angle resolution (16384 LSB/g)
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(ACCEL_CONFIG);
  Wire.write(0x00);
  Wire.endTransmission();
  delay(100);

  // Seed the smoothed angle so it doesn't ramp from zero on startup
  smoothedAngle = readRawAngle();
}

void loop() {
  if (millis() - lastUpdate < UPDATE_INTERVAL_MS) {
    return;
  }
  lastUpdate = millis();

  // --- Steering angle ---
  float raw = readRawAngle();
  // Exponential smoothing to kill jitter
  smoothedAngle = SMOOTH_ALPHA * raw + (1.0 - SMOOTH_ALPHA) * smoothedAngle;
  float angle = smoothedAngle - centerOffset;

  // --- Buttons (pull-up: pressed = LOW, so invert) ---
  int accel = (digitalRead(BTN_ACCEL) == LOW) ? 1 : 0;
  int brake = (digitalRead(BTN_BRAKE) == LOW) ? 1 : 0;

  // --- Send line: ANGLE,ACCEL,BRAKE ---
  Serial.print(angle, 1);
  Serial.print(",");
  Serial.print(accel);
  Serial.print(",");
  Serial.println(brake);
}

// Reads the two accelerometer axes that respond to wheel rotation and
// returns an absolute tilt angle in degrees.
//
// NOTE: depending on how your sensor is physically mounted, the axis pair
// that reacts to "steering" might differ. If turning the wheel doesn't
// change the angle as expected, swap which axes are used in atan2() below
// (try ax/az, ay/az, or ax/ay).
float readRawAngle() {
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(ACCEL_XOUT_H);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU6050_ADDR, 6, true);

  int16_t ax = (Wire.read() << 8) | Wire.read();
  int16_t ay = (Wire.read() << 8) | Wire.read();
  int16_t az = (Wire.read() << 8) | Wire.read();

  float fax = ax / 16384.0;
  float fay = ay / 16384.0;
  float faz = az / 16384.0;

  float angle = atan2(fay, sqrt(fax * fax + faz * faz)) * 180.0 / PI;

  // Past 90 degrees, ax goes negative. Reflect so the angle keeps
  // increasing toward +/-180 instead of folding back toward 0.
  if (fax < 0) {
    if (angle >= 0) angle =  180.0 - angle;
    else            angle = -180.0 - angle;
  }
  return angle;
}