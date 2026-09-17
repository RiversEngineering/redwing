# Redwing Python API — Quick Reference

Syntax cheat sheet. See `examples/` for full runnable programs.

## Setup pattern

```python
from redwing import Robot

robot = Robot()               # connect to the daemon (host="localhost" by default)

# 1. Configure every port/device here
left  = robot.D0.motor()
right = robot.D1.motor()

robot.start()                 # lock in config, enable motor/sensor commands

# 2. Control loop
while True:
    left.set_power(60)
    right.set_power(60)
    robot.sleep(0.02)
```

All device setup (`.motor()`, `.servo()`, `.encoder()`, etc.) must happen **before** `robot.start()`. Calling a setter/getter before `start()` raises `RuntimeError`.

Two equivalent ways to configure a port — use whichever reads better:

```python
motor = robot.D0.motor()          # port method (shown below)
motor = robot.motor(robot.D0)     # Robot factory method, same result
```

---

## Ports

| Ports | Pins | Notes |
|---|---|---|
| `S0`–`S7` | single-pin | 50 Hz servo-capable. `S5`–`S7` also ADC-capable (IR distance sensors) |
| `D0`–`D7` | dual-pin (A/B) | Motors (20 kHz), encoders, ultrasonic. `D6`/`D7` double as UART1/UART0 |
| `P0`–`P15` | PCA9685 I²C expander | 50 Hz only — motor (ESC) or servo output |
| I²C (SDA/SCL) | fixed GP4/GP5 | Reserved — auto-detects IMU / VL53L0X, no manual config |

Each port can only be configured for **one** device.

---

## Motor

```python
m = robot.D0.motor()                       # sign_magnitude (dual-pin default)
m = robot.S0.motor()                       # servo_signal (single-pin default, e.g. an ESC)
m = robot.D0.motor("locked_antiphase")     # or "sm" / "lap" / "servo" aliases

m.set_power(75)      # -100..100, open-loop PWM %
m.stop()
m.inverted = True     # flip direction without rewiring
m.power                # readback (last commanded, or actual output during PID)
```

### Closed-loop velocity (needs an encoder)

```python
enc = robot.D2.encoder()
m.attach_encoder(enc)
m.set_pid(kp, ki, kd, integral_max=None)   # integral_max caps ki * integral_max contribution

m.set_velocity(300)      # target ticks/sec
m.velocity                # target ticks/sec (readback)
m.actual_velocity         # measured ticks/sec (== enc.velocity)
```

### Closed-loop position (needs an encoder)

```python
m.go_to_position(500)                        # absolute target tick count
m.go_to_position(500, max_speed=30)          # cap speed at 30%
m.go_to_position(target, keep_integral=True) # for streamed/continuously-updated targets

m.move_by(200)                 # relative move, same kwargs as go_to_position
m.move_by(-100, max_speed=40)

m.set_position_options(
    deadband=5,          # ticks within target where output is zeroed, integral frozen
    output_floor=7,       # min % output outside deadband (overcome static friction)
    ramp_rate=300,         # max ticks/s the internal setpoint ramps toward target
    d_alpha=0.15,          # derivative low-pass filter (0-1, lower = more filtering)
    approach_factor=0.1,   # setpoint decelerates automatically near the target
)
```

### MotorGroup (two+ motors driven together)

```python
lm1, lm2 = robot.D0.motor(), robot.D2.motor()
lm2.inverted = True                      # e.g. rear motor mounted backwards
le = robot.S0.encoder()

left = robot.motor_group(lm1, lm2, encoder=le)
left.set_power(60)
left.stop()
left.encoder     # -> le
```

---

## Encoder

```python
enc = robot.D2.encoder()

enc.count          # total ticks since reset (int)
enc.velocity        # ticks/sec, positive = forward
enc.reset()
enc.inverted = True  # flip count direction without rewiring
```

---

## Servo

```python
arm = robot.S0.servo()                                          # default 0-300°, 500-2500us
arm = robot.S0.servo(max_deg=180, min_us=1000, max_us=2000)     # standard 180° hobby servo
arm = robot.S0.servo(min_deg=-90, max_deg=90, min_us=1000, max_us=2000)  # centered range

arm.set_angle(150)
arm.angle            # last commanded angle (readback)
arm.center()          # move to midpoint of configured range

arm.set_gobilda_mode("continuous")   # GoBilda dual-mode servo: "continuous" or "positional"
```
S5–S7 cannot be servos (shared PWM slices with D2/D3/D7 motors).

---

## Distance sensors

```python
# HC-SR04 ultrasonic — dual-pin port required
us = robot.D2.ultrasonic()
us.distance        # cm, -1 if out of range
us.distance_mm
us.in_range

# Sharp IR — S5, S6, or S7 only (ADC pins), 10-80cm, needs 10k/10k voltage divider
ir = robot.ir_distance(robot.S5)
ir.distance
ir.in_range

# VL53L0X ToF (I2C, auto-detected, no config call needed)
tof = robot.vl53l0x()
tof.connected
tof.valid
tof.distance        # cm

# TFMini / TFLuna UART ToF LiDAR — port 14 (D6) or 15 (D7, default)
tf = robot.tfmini()          # or robot.tfluna()
tf.valid
tf.distance          # cm (None until first frame)
tf.distance_m
tf.strength
tf.temperature        # TFLuna only, °C
```

---

## Digital I/O

```python
btn = robot.S1.digital_input()
btn.value            # True = HIGH
bool(btn)             # same

led = robot.S2.digital_output()
led.on(); led.off(); led.toggle()
led.value
```

---

## UART bus

```python
uart = robot.uart(port=15, baud=115200)   # D7 default (or robot.uart1(baud=...) for D6)

uart.write("AT\r\n")            # str -> UTF-8, or pass bytes directly
data = uart.read(n=-1)           # non-blocking, -1 = all buffered bytes
line = uart.readline(timeout=1.0)                 # None on timeout
chunk = uart.read_bytes_until(b"\x00", timeout=1.0)
```

---

## IMU (auto-detected: BNO085 > BNO055 > MPU-6050)

```python
imu = robot.imu()

imu.connected
imu.type              # "bno085" / "bno055" / "mpu6050"
imu.heading            # 0-360°, CCW positive, 0 at boot
imu.quaternion          # (w,x,y,z) — BNO085/BNO055 only
imu.acceleration         # (x,y,z) m/s², gravity-compensated on fusion sensors
imu.gyro                  # (x,y,z) °/s — MPU-6050 only

imu.set_mount_rotation(yaw=-90)     # correct for how the IMU is physically mounted
imu.reset_heading(0.0)               # re-zero gyro-integrated heading — MPU-6050 only
```
Robot frame: +X forward, +Y left, +Z up. MPU-6050 heading drifts over time (no magnetometer) — prefer BNO085/BNO055 for long runs.

---

## 360° LIDAR (USB, e.g. RPLIDAR)

```python
lidar = robot.lidar(offset_deg=0)   # offset = sensor's CW rotation vs. robot forward

lidar.scan()                          # [(angle_deg, distance_cm), ...] sorted by angle
lidar.nearest()                        # closest distance in any direction
lidar.nearest_in_range(0, 30)           # closest within ±30° of 0° (robot-forward)
lidar.nearest_with_angle()               # (angle_deg, distance_cm) of closest point
```

---

## Gamepad (virtual dashboard controller or physical USB/BT pad)

```python
gp = robot.gamepad     # no setup call needed, works immediately

gp.left_x, gp.left_y, gp.right_x, gp.right_y   # -1.0..1.0
gp.a, gp.b, gp.x, gp.y                          # True while held
gp.just_pressed_a                                # True once per press (edge)
gp.dpad_up / dpad_down / dpad_left / dpad_right   # + just_pressed_dpad_*
gp.lb, gp.rb                                       # bumpers, + just_pressed_lb/rb
gp.lt, gp.rt                                        # analog triggers 0.0-1.0, + just_pressed_lt/rt
gp.connected, gp.source                              # "virtual" / "physical" / "none"
```

---

## Camera

```python
cam = robot.camera

frame = cam.read()                     # numpy BGR array (OpenCV-compatible)
cam.show()                              # show raw feed on dashboard
cam.show(frame)                          # show a processed frame instead

mask = cam.color_mask(frame, "red")      # "red"/"green"/"blue"/"yellow"/"orange"
x, y, area = cam.find_largest_contour(mask)   # (None, None, 0) if nothing found
```
AprilTags aren't a Redwing wrapper — use OpenCV's ArUco module directly:
```python
import cv2
dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
detector   = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
corners, ids, _ = detector.detectMarkers(frame)
```

---

## PCA9685 expansion channels (P0–P15)

Mirrors the Port API; 50 Hz only, so motor outputs are RC-ESC style (servo signal).

```python
m = robot.P0.motor()          # RC ESC: 1500us=stop, 1100us=full reverse, 1900us=full forward
m.set_power(75)
m.inverted = True

s = robot.P1.servo(max_deg=180, min_us=1000, max_us=2000)
s.angle = 90
```

---

## Drive systems (odometry + dead-reckoning)

Coordinate frame: +X forward, +Y left, heading in degrees, **CCW positive**, 0 at `robot.start()`.

### Differential (2-wheel / tank)

```python
lm, rm = robot.D0.motor(), robot.D1.motor()
le, re = robot.D2.encoder(), robot.D3.encoder()

drive = robot.differential_drive(
    left_motor=lm, right_motor=rm,
    left_encoder=le, right_encoder=re,
    imu=robot.imu(),              # optional but recommended — cuts angular drift
    wheel_diameter_mm=60, track_width_mm=150, ticks_per_rev=1440,
    invert_left=False, invert_right=False,
)
# or pass left=/right= MotorGroup objects (encoder read from the group automatically)

robot.start()

drive.drive(forward=50, turn=0)      # continuous, non-blocking, -100..100
drive.forward(0.5)                    # blocking: 0.5 m, power=50 default
drive.backward(0.3)
drive.turn_left(90); drive.turn_right(90)   # blocking, degrees, power=40 default
drive.rotate(-45)                      # negative = CW
drive.stop()

drive.pose                              # (x_m, y_m, heading_deg)
drive.x; drive.y; drive.heading
drive.reset_pose(x=0, y=0, heading_deg=0)
drive.correct_pose(x, y, heading_deg=None)   # snap to external fix (e.g. AprilTag)
```
`strafe*()` raise `NotImplementedError` on differential drive.

### Mecanum (holonomic, 4-wheel)

```python
drive = robot.mecanum_drive(
    fl=(fl_motor, fl_enc), fr=(fr_motor, fr_enc),
    bl=(bl_motor, bl_enc), br=(br_motor, br_enc),
    imu=robot.imu(),
    wheel_diameter_mm=100, track_width_mm=300, wheelbase_mm=280, ticks_per_rev=1440,
)
robot.start()

drive.move(vx=50, vy=0, omega=0)     # continuous, non-blocking; vy>0=right, omega>0=CCW
drive.forward(0.5); drive.backward(0.3)
drive.strafe_left(0.3); drive.strafe_right(0.3)
drive.strafe(0.4, 45)                  # blocking, robot-relative angle: 0=fwd,90=right,180=back,270=left
drive.turn_left(90); drive.rotate(-90)
drive.stop()
drive.pose   # same pose API as DifferentialDrive
```

---

## Robot utilities

```python
robot.log("Distance:", sensor.distance, "cm")   # dashboard debug console
robot.plot("error", error_value)                  # named series on dashboard Data tab graph
robot.stop()                                       # stop all motors immediately
robot.sleep(0.02)                                   # like time.sleep, but syncs to fresh sensor data
robot.uptime                                         # seconds since daemon start

robot.map_point(x, y)              # push one world-frame point to dashboard Map tab
robot.map_points([(x1,y1), (x2,y2)])
robot.map_pose(x, y, heading_deg=0)
robot.clear_map()
```

---

## Nodes (advanced: concurrent/async programs)

```python
from redwing.nodes import Node, run_nodes

class ObstacleDetector(Node):
    async def run(self):
        while True:
            await self.publish("distance", sensor.distance)
            await self.sleep(0.05)

class DriveController(Node):
    async def run(self):
        while True:
            dist = await self.receive("distance")   # optional timeout=
            motor.set_power(0 if dist < 20 else 60)

run_nodes(ObstacleDetector(), DriveController())   # blocking; runs forever
```
