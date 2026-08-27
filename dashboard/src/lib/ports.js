// ── Port directory ────────────────────────────────────────────────────────────
export const SINGLE = Array.from({ length: 8 }, (_, i) => ({ id: i,     label: `S${i}`, dual: false }));
export const DUAL   = Array.from({ length: 8 }, (_, i) => ({ id: i + 8, label: `D${i}`, dual: true  }));
export const I2C_PORT = { id: 16, label: 'I²C', dual: true };
export const IMU_PORT = { id: 17, label: 'IMU', dual: true };
export const ALL_PORTS = [...SINGLE, ...DUAL, I2C_PORT, IMU_PORT];

// D6/D7 configured for a UART-based protocol list under the bus sidebar
// (right) instead of the physical port sidebar (left).
export const UART_TYPES = new Set(['uart', 'tfluna', 'tfmini']);
export const isUartCapable = (id) => id === 14 || id === 15; // D6, D7

// ── Port type definitions for the configure picker ────────────────────────────
// dualOnly: only shown for dual-pin ports
// singleOnly: only shown for single-pin ports
export const TYPE_DEFS = [
  { id: 'motor_sm',           label: 'Motor',       sub: 'Sign-Magnitude',    group: 'Motor',  dualOnly: true,  singleOnly: false, d7Only: false },
  { id: 'motor_servo_signal', label: 'Motor',       sub: 'Servo Signal',      group: 'Motor',  dualOnly: false, singleOnly: true,  d7Only: false },
  { id: 'servo',              label: 'Servo',       sub: null,                group: 'Servo',  dualOnly: false, singleOnly: true,  d7Only: false },
  { id: 'encoder',            label: 'Encoder',     sub: null,                group: 'Sensor', dualOnly: true,  singleOnly: false, d7Only: false },
  { id: 'ultrasonic',         label: 'Ultrasonic',  sub: null,                group: 'Sensor', dualOnly: true,  singleOnly: false, d7Only: false },
  { id: 'gpio_in',            label: 'Digital In',  sub: null,                group: 'GPIO',   dualOnly: false, singleOnly: false, d7Only: false },
  { id: 'gpio_out',           label: 'Digital Out', sub: null,                group: 'GPIO',   dualOnly: false, singleOnly: false, d7Only: false },
  { id: 'uart',               label: 'UART Serial', sub: 'D6 or D7 only',     group: 'Bus',    dualOnly: true,  singleOnly: false, d7Only: true  },
  { id: 'tfluna',             label: 'TF-Luna',     sub: 'D6 or D7 only',     group: 'Sensor', dualOnly: true,  singleOnly: false, d7Only: true  },
  { id: 'tfmini',             label: 'TF-Mini',     sub: 'D6 or D7 only',     group: 'Sensor', dualOnly: true,  singleOnly: false, d7Only: true  },
];

// ── Type helpers ─────────────────────────────────────────────────────────────
// motor_lap (locked anti-phase) is no longer offered in the type picker, but
// existing ports/state may still carry it — kept recognized here so they
// still display correctly.
// motor_sm_pair is PCA9685-only: two channels bound as one sign-magnitude
// motor (see pca_pair_channels in daemon/api.py). Its "direction" role
// channel is rendered specially wherever it's shown (see PortsTab.svelte's
// PCA sidebar and MiniPortCard.svelte) rather than through these generic
// helpers, since it isn't a live-value readout.
export const isMotor = (t) => t === 'motor_sm' || t === 'motor_lap' || t === 'motor_servo_signal' || t === 'motor_sm_pair';

export function deviceLabel(type) {
  if (isMotor(type)) return 'Motor';
  const m = { encoder: 'Encoder', ultrasonic: 'Ultrasonic', vl53l0x: 'VL53L0X ToF',
               ir_distance: 'IR Sensor',
               bno085: 'BNO085 IMU', bno055: 'BNO055 IMU', mpu6050: 'MPU-6050 IMU',
               servo: 'Servo', gpio_in: 'Digital In', gpio_out: 'Digital Out',
               i2c: 'I²C', uart: 'UART', tfluna: 'TF-Luna', tfmini: 'TF-Mini' };
  return m[type] ?? 'Empty';
}

// ── Servo range helpers ───────────────────────────────────────────────────────
export function servoRangeOf(d) {
  return {
    minAngle: d?.min_angle    ?? 0,
    maxAngle: d?.max_angle    ?? 300,
    minPulse: d?.min_pulse_us ?? 500,
    maxPulse: d?.max_pulse_us ?? 2500,
  };
}

export function pulseToAngle(pulse_us, r) {
  if (r.maxPulse === r.minPulse) return r.minAngle;
  return r.minAngle + (pulse_us - r.minPulse) / (r.maxPulse - r.minPulse) * (r.maxAngle - r.minAngle);
}

export function servoPresets(r, unit = '°') {
  const fmt = (n) => Number.isInteger(n) ? String(n) : n.toFixed(0);
  const c = (r.minAngle + r.maxAngle) / 2;
  return [
    [r.minAngle, `${fmt(r.minAngle)}${unit}`],
    [r.minAngle + (r.maxAngle - r.minAngle) * 0.25, `${fmt(r.minAngle + (r.maxAngle - r.minAngle) * 0.25)}${unit}`],
    [c, `${fmt(c)}${unit}`],
    [r.minAngle + (r.maxAngle - r.minAngle) * 0.75, `${fmt(r.minAngle + (r.maxAngle - r.minAngle) * 0.75)}${unit}`],
    [r.maxAngle, `${fmt(r.maxAngle)}${unit}`],
  ];
}

export function liveValue(d) {
  if (!d) return null;
  if (isMotor(d.type)) return `${((d.value ?? 0) / 100).toFixed(0)}% pwr`;
  switch (d.type) {
    case 'encoder':    return `${(d.count ?? 0).toLocaleString()} cnt`;
    case 'ultrasonic':   return d.valid ? `${(d.distance_mm / 10).toFixed(1)} cm` : 'OOB';
    case 'vl53l0x':     return d.valid ? `${(d.distance_mm / 10).toFixed(1)} cm` : 'OOB';
    case 'ir_distance':  return d.valid ? `${(d.distance_mm / 10).toFixed(1)} cm` : 'OOB';
    case 'tfluna':
    case 'tfmini':    return d.valid ? `${(d.distance_cm ?? 0).toFixed(0)} cm` : 'OOB';
    case 'servo': {
      const r = servoRangeOf(d);
      const unit = d.gobilda_mode === 'continuous' ? '%' : '°';
      return `${pulseToAngle(d.pulse_us ?? 1500, r).toFixed(1)}${unit}`;
    }
    case 'bno085':
    case 'bno055': {
      const q = d.quaternion;
      if (!q) return null;
      const yaw = Math.atan2(2*(q.w*q.z + q.x*q.y), 1 - 2*(q.y*q.y + q.z*q.z));
      return `${((yaw * 180 / Math.PI + 360) % 360).toFixed(1)}°`;
    }
    case 'mpu6050': {
      const a = d.acceleration;
      if (!a) return null;
      const mag = Math.sqrt(a.x*a.x + a.y*a.y + a.z*a.z) * 9.80665;
      return `${mag.toFixed(2)} m/s²`;
    }
    case 'gpio_in':
    case 'gpio_out':   return d.state ? 'HIGH' : 'LOW';
    default:           return null;
  }
}

export function accentClass(type) {
  if (isMotor(type))       return 'text-blue-400 border-blue-500/40';
  if (type === 'gpio_in' || type === 'gpio_out') return 'text-green-400 border-green-500/40';
  const m = {
    encoder:    'text-violet-400 border-violet-500/40',
    ultrasonic:  'text-cyan-400 border-cyan-500/40',
    vl53l0x:    'text-teal-400 border-teal-500/40',
    ir_distance: 'text-rose-400 border-rose-500/40',
    bno085:     'text-indigo-400 border-indigo-500/40',
    bno055:     'text-indigo-400 border-indigo-500/40',
    mpu6050:    'text-purple-400 border-purple-500/40',
    tfluna:     'text-sky-400 border-sky-500/40',
    tfmini:     'text-sky-400 border-sky-500/40',
    servo:      'text-amber-400 border-amber-500/40',
    i2c:        'text-orange-400 border-orange-500/40',
  };
  return m[type] ?? 'text-slate-600 border-slate-700/30';
}

export function dotColor(type) {
  if (isMotor(type))       return 'bg-blue-400';
  if (type === 'gpio_in' || type === 'gpio_out') return 'bg-green-400';
  const m = { encoder: 'bg-violet-400', ultrasonic: 'bg-cyan-400', ir_distance: 'bg-rose-400',
               tfluna: 'bg-sky-400', tfmini: 'bg-sky-400',
               vl53l0x: 'bg-teal-400', servo: 'bg-amber-400', i2c: 'bg-orange-400',
               bno085: 'bg-indigo-400', bno055: 'bg-indigo-400', mpu6050: 'bg-purple-400' };
  return m[type] ?? 'bg-slate-700';
}
