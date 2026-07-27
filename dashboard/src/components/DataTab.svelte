<script>
  /**
   * DataTab – two configurable real-time graphs backed by a shared timeline.
   *
   * All series are aligned to a single shared timestamp array so that
   * both graphs display exactly the same time window and data is in sync.
   */
  import { onDestroy } from 'svelte';
  import { get } from 'svelte/store';
  import { robotState, plotValues } from '../lib/stores.js';
  import DataGraph from './DataGraph.svelte';

  // ── Group filters ─────────────────────────────────────────────────────────────

  const GROUPS = [
    { id: 'motors',   label: 'Motors'   },
    { id: 'servos',   label: 'Servos'   },
    { id: 'encoders', label: 'Encoders' },
    { id: 'sensors',  label: 'Sensors'  },
    { id: 'i2c',      label: 'I²C'      },
    { id: 'user',     label: 'User'     },
  ];

  let visibleGroups = new Set(GROUPS.map((g) => g.id));

  function getGroup(key) {
    if (key.startsWith('motor_'))                              return 'motors';
    if (key.startsWith('servo_'))                              return 'servos';
    if (key.startsWith('enc_'))                                return 'encoders';
    if (key.startsWith('vl53l0x_') || key.startsWith('imu_')) return 'i2c';
    if (key.startsWith('plot_'))                               return 'user';
    return 'sensors'; // ultrasonic, gpio, sharp, lidar
  }

  function toggleGroup(id) {
    if (visibleGroups.has(id)) visibleGroups.delete(id);
    else visibleGroups.add(id);
    visibleGroups = new Set(visibleGroups);
  }

  $: availableKeys = Object.keys(allSeries).filter((k) => visibleGroups.has(getGroup(k))).sort();

  // ── Config ───────────────────────────────────────────────────────────────────

  const WINDOW_OPTIONS = [
    { label: '5s',  value: 5   },
    { label: '10s', value: 10  },
    { label: '30s', value: 30  },
    { label: '1m',  value: 60  },
    { label: '2m',  value: 120 },
    { label: '5m',  value: 300 },
  ];

  /** Oldest data to keep — always the largest window option. */
  const MAX_WINDOW_S  = 300;
  const MAX_POINTS    = 60 * MAX_WINDOW_S; // 60 Hz × 5 min

  const PALETTE = [
    '#60a5fa', // blue
    '#a78bfa', // violet
    '#34d399', // emerald
    '#fb923c', // orange
    '#f472b6', // pink
    '#38bdf8', // sky
    '#facc15', // yellow
    '#4ade80', // green
    '#f87171', // red
    '#e879f9', // fuchsia
  ];

  // ── State ────────────────────────────────────────────────────────────────────

  let windowSec = 30;
  let nowSec    = 0;

  /**
   * Shared timeline — one entry per robotState tick.
   * Mutated in place; DataGraph reads it by reference each update.
   * @type {number[]}
   */
  let timeline = [];

  /**
   * allSeries: key → { key, label, unit, color, values: (number|null)[] }
   *
   * values[] is 1:1 aligned with timeline[].
   * null means "this series did not have a value at this tick" (renders as gap).
   */
  let allSeries = {};
  let colorCounter = 0;

  // ── Helpers ──────────────────────────────────────────────────────────────────

  function portLabel(id) {
    const n = Number(id);
    if (n < 8)  return `S${n}`;
    if (n < 16) return `D${n - 8}`;
    return 'I²C';
  }

  /**
   * Returns candidate series descriptors for the given port state.
   * Each descriptor has { key, label, unit, getValue() → number|null }.
   */
  function getCandidates(portId, portData) {
    const { type } = portData;
    const pl = portLabel(portId);
    const isMotor = type === 'motor_sm' || type === 'motor_lap' || type === 'motor_servo_signal';

    if (isMotor) {
      return [{
        key:      `motor_${portId}`,
        label:    `${pl} power`,
        unit:     '%',
        getValue: () => +((portData.value ?? 0) / 100).toFixed(2),
      }];
    }

    if (type === 'encoder') {
      return [
        {
          key:      `enc_vel_${portId}`,
          label:    `${pl} enc vel`,
          unit:     'ticks/s',
          getValue: () => +((portData.velocity ?? 0) / 10).toFixed(1),
        },
        {
          key:      `enc_cnt_${portId}`,
          label:    `${pl} enc count`,
          unit:     'ticks',
          getValue: () => portData.count ?? 0,
        },
      ];
    }

    if (type === 'ultrasonic') {
      return [{
        key:      `ultrasonic_${portId}`,
        label:    `${pl} distance`,
        unit:     'cm',
        getValue: () => portData.valid ? +((portData.distance_mm ?? 0) / 10).toFixed(1) : 0,
      }];
    }

    if (type === 'vl53l0x') {
      return [{
        key:      `vl53l0x_${portId}`,
        label:    'I²C ToF distance',
        unit:     'cm',
        // Return 0 when out of range so the graph shows a line drop rather
        // than a gap — 0 means "no target detected" (matches library behaviour).
        getValue: () => portData.valid ? +((portData.distance_mm ?? 0) / 10).toFixed(1) : 0,
      }];
    }

    if (type === 'servo') {
      return [{
        key:      `servo_${portId}`,
        label:    `${pl} servo`,
        unit:     '°',
        getValue: () => +(((portData.pulse_us ?? 1500) - 500) / 2000 * 300).toFixed(1),
      }];
    }

    if (type === 'gpio_in' || type === 'gpio_out') {
      return [{
        key:      `gpio_${portId}`,
        label:    `${pl} ${type === 'gpio_in' ? 'in' : 'out'}`,
        unit:     '',
        getValue: () => portData.state ? 1 : 0,
      }];
    }

    if (type === 'sharp_ir') {
      return [{
        key:      `sharp_${portId}`,
        label:    `${pl} IR dist`,
        unit:     'cm',
        getValue: () => portData.valid ? +((portData.distance_mm ?? 0) / 10).toFixed(1) : null,
      }];
    }

    if (type === 'tfluna' || type === 'tfmini') {
      return [{
        key:      `lidar_${portId}`,
        label:    `${pl} LiDAR`,
        unit:     'cm',
        getValue: () => portData.valid ? +(portData.distance_cm ?? 0) : null,
      }];
    }

    if (type === 'bno085' || type === 'bno055') {
      return [
        {
          key:      'imu_heading',
          label:    'IMU heading',
          unit:     '°',
          getValue: () => {
            const q = portData.quaternion;
            if (!q) return null;
            const yr = Math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z));
            return +(((yr * 180 / Math.PI) + 360) % 360).toFixed(1);
          },
        },
        {
          key: 'imu_qw', label: 'IMU Q.w', unit: '',
          getValue: () => portData.quaternion ? +portData.quaternion.w.toFixed(4) : null,
        },
        {
          key: 'imu_qx', label: 'IMU Q.x', unit: '',
          getValue: () => portData.quaternion ? +portData.quaternion.x.toFixed(4) : null,
        },
        {
          key: 'imu_qy', label: 'IMU Q.y', unit: '',
          getValue: () => portData.quaternion ? +portData.quaternion.y.toFixed(4) : null,
        },
        {
          key: 'imu_qz', label: 'IMU Q.z', unit: '',
          getValue: () => portData.quaternion ? +portData.quaternion.z.toFixed(4) : null,
        },
        {
          key: 'imu_lin_x', label: 'IMU accel X', unit: 'm/s²',
          getValue: () => portData.linear_acceleration ? +portData.linear_acceleration.x.toFixed(3) : null,
        },
        {
          key: 'imu_lin_y', label: 'IMU accel Y', unit: 'm/s²',
          getValue: () => portData.linear_acceleration ? +portData.linear_acceleration.y.toFixed(3) : null,
        },
        {
          key: 'imu_lin_z', label: 'IMU accel Z', unit: 'm/s²',
          getValue: () => portData.linear_acceleration ? +portData.linear_acceleration.z.toFixed(3) : null,
        },
        {
          key: 'imu_roll', label: 'IMU roll', unit: '°',
          getValue: () => {
            const q = portData.quaternion;
            if (!q) return null;
            return +(Math.atan2(2*(q.w*q.x + q.y*q.z), 1 - 2*(q.x*q.x + q.y*q.y)) * 180/Math.PI).toFixed(1);
          },
        },
        {
          key: 'imu_pitch', label: 'IMU pitch', unit: '°',
          getValue: () => {
            const q = portData.quaternion;
            if (!q) return null;
            const sinp = 2*(q.w*q.y - q.z*q.x);
            const pitch = Math.abs(sinp) >= 1 ? Math.sign(sinp) * 90 : Math.asin(sinp) * 180/Math.PI;
            return +pitch.toFixed(1);
          },
        },
      ];
    }

    if (type === 'mpu6050') {
      return [
        {
          key: 'imu_ax', label: 'IMU accel X', unit: 'm/s²',
          getValue: () => portData.acceleration ? +portData.acceleration.x.toFixed(3) : null,
        },
        {
          key: 'imu_ay', label: 'IMU accel Y', unit: 'm/s²',
          getValue: () => portData.acceleration ? +portData.acceleration.y.toFixed(3) : null,
        },
        {
          key: 'imu_az', label: 'IMU accel Z', unit: 'm/s²',
          getValue: () => portData.acceleration ? +portData.acceleration.z.toFixed(3) : null,
        },
        {
          key: 'imu_gx', label: 'IMU gyro X', unit: '°/s',
          getValue: () => portData.gyro ? +portData.gyro.x.toFixed(2) : null,
        },
        {
          key: 'imu_gy', label: 'IMU gyro Y', unit: '°/s',
          getValue: () => portData.gyro ? +portData.gyro.y.toFixed(2) : null,
        },
        {
          key: 'imu_gz', label: 'IMU gyro Z', unit: '°/s',
          getValue: () => portData.gyro ? +portData.gyro.z.toFixed(2) : null,
        },
      ];
    }

    return [];
  }

  // ── Data ingestion ────────────────────────────────────────────────────────────

  const unsubState = robotState.subscribe((state) => {
    if (!state?.ports) return;

    const ts = Date.now() / 1000;

    // 1. Append to shared timeline
    timeline.push(ts);

    // 2. Build candidate map for this tick
    const activeCandidates = {}; // key → { getValue }
    let newSeriesAdded = false;

    for (const [portId, portData] of Object.entries(state.ports)) {
      const { type } = portData;
      if (!type || type === 'unconfigured' || type === 'uart' || type === 'i2c') continue;

      for (const c of getCandidates(portId, portData)) {
        activeCandidates[c.key] = c;

        if (!allSeries[c.key]) {
          // New series: backfill all prior timeline entries with null
          allSeries[c.key] = {
            key:   c.key,
            label: c.label,
            unit:  c.unit,
            color: PALETTE[colorCounter++ % PALETTE.length],
            values: new Array(timeline.length - 1).fill(null),
          };
          newSeriesAdded = true;
        }
      }
    }

    // Also include any student robot.plot() series
    const plots = get(plotValues);
    for (const [label, { value }] of Object.entries(plots)) {
      const key = `plot_${label}`;
      const captured = value;  // capture for closure
      activeCandidates[key] = { key, getValue: () => captured };

      if (!allSeries[key]) {
        allSeries[key] = {
          key,
          label,
          unit:   '',
          color:  PALETTE[colorCounter++ % PALETTE.length],
          values: new Array(timeline.length - 1).fill(null),
        };
        newSeriesAdded = true;
      }
    }

    // 3. Append one value per known series (null if port absent this tick)
    for (const key of Object.keys(allSeries)) {
      const c = activeCandidates[key];
      allSeries[key].values.push(c ? c.getValue() : null);
    }

    // 4. Trim to max window (keeps all window options feasible)
    const cutoff = ts - MAX_WINDOW_S;
    while (timeline.length > 0 && timeline[0] < cutoff) {
      timeline.shift();
      for (const s of Object.values(allSeries)) s.values.shift();
    }
    if (timeline.length > MAX_POINTS) {
      const excess = timeline.length - MAX_POINTS;
      timeline.splice(0, excess);
      for (const s of Object.values(allSeries)) s.values.splice(0, excess);
    }

    // 5. Trigger Svelte reactivity
    //    - nowSec always changes → propagates to DataGraph → triggers data redraw
    //    - allSeries ref only changes when new series appear → updates checkbox list
    nowSec = ts;
    if (newSeriesAdded) allSeries = { ...allSeries };
  });

  onDestroy(() => unsubState());
</script>

<div class="flex flex-col h-full p-2 gap-2 overflow-hidden">

  <!-- ── Time window selector ── -->
  <div class="flex items-center gap-3 px-3 py-2 bg-[#1e2129] rounded-lg border border-[#2e3340] flex-shrink-0">
    <svg class="w-3.5 h-3.5 text-slate-500 flex-shrink-0" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3">
      <circle cx="8" cy="8" r="6.5"/>
      <polyline points="8,4.5 8,8 10.5,10"/>
    </svg>
    <span class="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mr-1">Window</span>

    {#each WINDOW_OPTIONS as opt}
      <button
        class="px-2.5 py-0.5 rounded text-xs font-mono transition-colors
               {windowSec === opt.value
                 ? 'bg-blue-600 text-white font-semibold'
                 : 'bg-[#161920] text-slate-500 border border-[#2e3340] hover:text-slate-300 hover:border-slate-500'}"
        on:click={() => (windowSec = opt.value)}
      >
        {opt.label}
      </button>
    {/each}

    <span class="ml-auto text-[10px] text-slate-700 font-mono">
      {Object.keys(allSeries).length} series available
    </span>
  </div>

  <!-- ── Group filter bar ── -->
  <div class="flex items-center gap-2 px-3 py-1.5 bg-[#1e2129] rounded-lg border border-[#2e3340] flex-shrink-0">
    <span class="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mr-1">Show</span>
    {#each GROUPS as g}
      <button
        class="px-2.5 py-0.5 rounded text-xs font-medium transition-colors
               {visibleGroups.has(g.id)
                 ? 'bg-slate-600 text-slate-200 hover:bg-slate-500'
                 : 'bg-[#161920] text-slate-600 border border-[#2e3340] hover:text-slate-400'}"
        on:click={() => toggleGroup(g.id)}
        title="{visibleGroups.has(g.id) ? 'Click to hide' : 'Click to show'} {g.label.toLowerCase()}"
      >
        {g.label}
      </button>
    {/each}
  </div>

  <!-- ── Graph 1 ── -->
  <div class="flex-1 min-h-0">
    <DataGraph {allSeries} {timeline} {windowSec} {nowSec} {availableKeys} graphLabel="Graph 1" />
  </div>

  <!-- ── Graph 2 ── -->
  <div class="flex-1 min-h-0">
    <DataGraph {allSeries} {timeline} {windowSec} {nowSec} {availableKeys} graphLabel="Graph 2" />
  </div>
</div>
