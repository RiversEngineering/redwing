"""LIDAR device — 360° distance sensing via USB-connected RPLIDAR."""

import math


class Lidar:
    """A 360° LIDAR sensor connected to the Raspberry Pi via USB.

    Obtain via ``robot.lidar()``::

        lidar = robot.lidar()               # sensor forward = robot forward
        lidar = robot.lidar(offset_deg=90)  # sensor is rotated 90° left (CCW)

        while True:
            d = lidar.nearest()
            if d < 30:
                robot.stop()
            robot.sleep(0.1)

    The daemon continuously reads scans in the background.
    All Lidar methods return the most recent completed scan.

    Angles
    ------
    All angles follow the robot frame (ROS REP 103): **0° = forward,
    counter-clockwise is positive**, so 90° = left, 180° = behind and
    270° = right.  Angles returned by ``scan()``, ``nearest_in_range()``
    and ``nearest_with_angle()`` are corrected for the mounting below, so
    0° always means the robot's own forward direction.

    Mounting offset
    ---------------
    If the LIDAR is physically rotated on the robot, pass ``offset_deg``
    equal to the **counter-clockwise** rotation of the sensor's forward
    direction relative to the robot's forward direction.

    * Sensor points forward (cable at back): ``offset_deg=0`` (default)
    * Sensor rotated 90° left (CCW): ``offset_deg=90``
    * Sensor points backward: ``offset_deg=180``
    * Sensor rotated 90° right (CW): ``offset_deg=270`` (or ``-90``)

    If the sensor is not at the robot's centre, pass ``x_offset_cm``
    (+ = forward of centre) and ``y_offset_cm`` (+ = **left** of centre).
    """

    def __init__(self, conn, offset_deg: float = 0.0,
                 x_offset_cm: float = 0.0, y_offset_cm: float = 0.0):
        self._conn     = conn
        self._offset   = float(offset_deg) % 360.0
        self._x_offset = float(x_offset_cm)   # positive = LIDAR is forward of centre
        self._y_offset = float(y_offset_cm)   # positive = LIDAR is left of centre

    def scan(self) -> list[tuple[float, float]]:
        """Return the latest full 360° scan as a list of ``(angle_deg, distance_cm)`` tuples.

        Angles run 0–360°, counter-clockwise from robot forward (90° = left,
        270° = right), corrected for any mounting offset.  The list is
        sorted by angle.
        Returns an empty list if no scan is available yet.

        Example::

            for angle, dist in lidar.scan():
                if dist < 20:
                    robot.log(f"Obstacle at {angle:.0f}°, {dist:.1f} cm")
        """
        state = self._conn.get_all_state()
        raw   = state.get("lidar", [])
        if not raw:
            return []

        # The daemon already reports CCW angles (0° = sensor forward).
        # 1. Apply rotation offset so 0° = robot forward
        if self._offset != 0.0:
            raw = [((a + self._offset) % 360.0, d) for a, d in raw]

        # 2. Apply XY mounting offset so coordinates are relative to the robot centre
        #    (robot frame: +x forward, +y left).
        if self._x_offset != 0.0 or self._y_offset != 0.0:
            corrected = []
            for angle_deg, dist in raw:
                rad = math.radians(angle_deg)
                rx = dist * math.cos(rad) + self._x_offset
                ry = dist * math.sin(rad) + self._y_offset
                new_dist  = math.sqrt(rx * rx + ry * ry)
                new_angle = math.degrees(math.atan2(ry, rx)) % 360.0
                corrected.append((round(new_angle, 1), round(new_dist, 1)))
            return sorted(corrected, key=lambda p: p[0])

        return sorted(raw, key=lambda p: p[0])

    def nearest(self) -> float:
        """Distance in cm to the nearest detected obstacle in any direction.

        Returns ``float('inf')`` if no scan is available.

        Example::

            if lidar.nearest() < 20:
                robot.stop()
        """
        points = self.scan()
        if not points:
            return float("inf")
        return min(d for _, d in points)

    def nearest_in_range(self, center_deg: float, half_width_deg: float) -> float:
        """Distance in cm to the nearest obstacle within an angular window.

        All angles are in **robot-relative** coordinates (0° = robot forward,
        counter-clockwise positive), corrected for any mounting offset.

        Parameters
        ----------
        center_deg:
            Centre of the search window in degrees (0° = forward, 90° = left).
        half_width_deg:
            Half-width of the window.  For example ``half_width_deg=30``
            searches ±30° around *center_deg*.

        Returns ``float('inf')`` if no points fall in the window.

        Example::

            front = lidar.nearest_in_range(0, 30)    # ±30° ahead
            left  = lidar.nearest_in_range(90, 30)   # ±30° to the left
            right = lidar.nearest_in_range(270, 30)  # ±30° to the right
            back  = lidar.nearest_in_range(180, 30)  # ±30° behind
        """
        lo = (center_deg - half_width_deg) % 360
        hi = (center_deg + half_width_deg) % 360

        def in_window(angle: float) -> bool:
            if lo <= hi:
                return lo <= angle <= hi
            return angle >= lo or angle <= hi   # wraps around 0°

        points = [d for a, d in self.scan() if in_window(a)]
        return min(points) if points else float("inf")

    def nearest_with_angle(self) -> tuple[float, float]:
        """Return ``(angle_deg, distance_cm)`` for the nearest obstacle.

        The angle is in robot-relative coordinates (0° = forward, 90° = left).
        Returns ``(0.0, float('inf'))`` if no scan is available.

        Example::

            angle, dist = lidar.nearest_with_angle()
            robot.log(f"Closest obstacle is {dist:.1f} cm at {angle:.0f}°")
        """
        points = self.scan()
        if not points:
            return (0.0, float("inf"))
        return min(points, key=lambda p: p[1])
