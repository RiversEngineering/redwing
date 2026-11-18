/**
 * LIDAR geometry shared by the radar and the map.
 *
 * Everything uses the robot frame (ROS REP 103), matching redwing/devices/lidar.py:
 *   +x = forward, +y = left, angles counter-clockwise from forward.
 * The daemon already reports scan angles counter-clockwise from the sensor's
 * forward direction.
 */

/**
 * Convert a scan to robot-frame points, applying the mounting config.
 *
 * @param {Array<[number, number]>} scan  [angle_deg, distance_cm] pairs
 * @param {{offset?: number, x_offset?: number, y_offset?: number}} cfg
 *        offset: CCW rotation of the sensor (deg); x_offset: cm forward of
 *        centre; y_offset: cm left of centre
 * @returns {Array<[number, number]>} [x_cm, y_cm] pairs
 */
export function scanToRobot(scan, cfg = {}) {
  const offset = cfg.offset   ?? 0;
  const xOff   = cfg.x_offset ?? 0;
  const yOff   = cfg.y_offset ?? 0;
  return scan.map(([angle, dist]) => {
    const rad = (angle + offset) * Math.PI / 180;
    return [dist * Math.cos(rad) + xOff, dist * Math.sin(rad) + yOff];
  });
}
