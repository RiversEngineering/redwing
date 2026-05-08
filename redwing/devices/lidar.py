"""LIDAR device — 360° distance sensing via USB-connected RPLIDAR."""

import math


class Lidar:
    """A 360° LIDAR sensor connected to the Raspberry Pi via USB.

    Obtain via ``robot.lidar()``::

        lidar = robot.lidar()

        while True:
            d = lidar.nearest()
            if d < 30:
                robot.stop()
            robot.sleep(0.1)

    The daemon continuously reads scans in the background.
    All Lidar methods return the most recent completed scan.
    """

    def __init__(self, conn):
        self._conn = conn

    def scan(self) -> list[tuple[float, float]]:
        """Return the latest full 360° scan as a list of ``(angle_deg, distance_cm)`` tuples.

        Angles run 0–360° (0° = front).  The list is sorted by angle.
        Returns an empty list if no scan is available yet.

        Example::

            for angle, dist in lidar.scan():
                if dist < 20:
                    robot.log(f"Obstacle at {angle:.0f}°, {dist:.1f} cm")
        """
        state = self._conn.get_all_state()
        points = state.get("lidar", [])
        return sorted(points, key=lambda p: p[0])

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

        Parameters
        ----------
        center_deg:
            Centre of the search window in degrees (0° = front).
        half_width_deg:
            Half-width of the window.  For example ``half_width_deg=30``
            searches ±30° around *center_deg*.

        Returns ``float('inf')`` if no points fall in the window.

        Example::

            front = lidar.nearest_in_range(0, 30)   # ±30° ahead
            left  = lidar.nearest_in_range(270, 30) # ±30° to the left
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

        Returns ``(0.0, float('inf'))`` if no scan is available.
        """
        points = self.scan()
        if not points:
            return (0.0, float("inf"))
        return min(points, key=lambda p: p[1])
