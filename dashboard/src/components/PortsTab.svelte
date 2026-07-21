<script>
  /**
   * PortsTab – port list + manual override / live readout panel.
   *
   * Left column: compact clickable list of all port slots.
   * Right panel: context-sensitive controls (outputs) or readings (inputs).
   */
  import { ports, robotState, selectedPortId } from '../lib/stores.js';
  import { send } from '../lib/ws.js';

  // ── Port directory ────────────────────────────────────────────────────────────
  const SINGLE = Array.from({ length: 8 }, (_, i) => ({ id: i,     label: `S${i}`, dual: false }));
  const DUAL   = Array.from({ length: 8 }, (_, i) => ({ id: i + 8, label: `D${i}`, dual: true  }));
  const I2C_PORT = { id: 16, label: 'I²C', dual: true };
  const ALL_PORTS = [...SINGLE, ...DUAL, I2C_PORT];

  let selectedId = null;

  $: selectedData = selectedId !== null ? $ports[selectedId] : null;
  $: selectedPort = selectedId !== null ? ALL_PORTS.find((p) => p.id === selectedId) : null;

  // Auto-select a port when navigating here from the overview port grid.
  let _lastHandled = null;
  $: if ($selectedPortId !== null && $selectedPortId !== _lastHandled) {
    _lastHandled = $selectedPortId;
    selectPort($selectedPortId);
    selectedPortId.set(null);
  }

  // ── Config finalization status ────────────────────────────────────────────────
  $: configFinalized = $robotState?.config_finalized ?? false;

  // ── Port type definitions for the configure picker ────────────────────────────
  // dualOnly: only shown for dual-pin ports
  // singleOnly: only shown for single-pin ports
  const TYPE_DEFS = [
    { id: 'motor_sm',           label: 'Motor',       sub: 'Sign-Magnitude',    group: 'Motor',  dualOnly: true,  singleOnly: false, d7Only: false },
    { id: 'motor_servo_signal', label: 'Motor',       sub: 'Servo Signal',      group: 'Motor',  dualOnly: false, singleOnly: true,  d7Only: false },
    { id: 'motor_lap',          label: 'Motor',       sub: 'Locked Anti-Phase', group: 'Motor',  dualOnly: false, singleOnly: true,  d7Only: false },
    { id: 'servo',              label: 'Servo',       sub: null,                group: 'Servo',  dualOnly: false, singleOnly: true,  d7Only: false },
    { id: 'encoder',            label: 'Encoder',     sub: null,                group: 'Sensor', dualOnly: true,  singleOnly: false, d7Only: false },
    { id: 'ultrasonic',         label: 'Ultrasonic',  sub: null,                group: 'Sensor', dualOnly: true,  singleOnly: false, d7Only: false },
    { id: 'gpio_in',            label: 'Digital In',  sub: null,                group: 'GPIO',   dualOnly: false, singleOnly: false, d7Only: false },
    { id: 'gpio_out',           label: 'Digital Out', sub: null,                group: 'GPIO',   dualOnly: false, singleOnly: false, d7Only: false },
    { id: 'uart',               label: 'UART Serial', sub: 'D6 or D7 only',     group: 'Bus',    dualOnly: true,  singleOnly: false, d7Only: true  },
    { id: 'tfluna',             label: 'TF-Luna',     sub: 'D6 or D7 only',     group: 'Sensor', dualOnly: true,  singleOnly: false, d7Only: true  },
    { id: 'tfmini',             label: 'TF-Mini',     sub: 'D6 or D7 only',     group: 'Sensor', dualOnly: true,  singleOnly: false, d7Only: true  },
  ];

  $: availableTypes = TYPE_DEFS.filter((t) => {
    if (t.d7Only     && selectedId !== 14 && selectedId !== 15) return false;
    if (t.dualOnly   && !(selectedPort?.dual))  return false;
    if (t.singleOnly &&   selectedPort?.dual)   return false;
    return true;
  });

  // pendingType: the type the user has selected in the picker but not yet sent
  let pendingType = null;
  $: if (selectedId !== null) pendingType = null;  // clear when port changes

  // reconfiguring: true when the user wants to change an already-configured port
  let reconfiguring = false;
  $: if (selectedId !== null) reconfiguring = false;  // clear when port changes

  // reset confirmation state
  let confirmReset = false;

  // ── Control state (local; does not track live RP2040 state) ──────────────────
  let motorSpeed = 0;   // -100..+100 (%)
  let servoAngle = 150; // degrees within the port's configured range

  // ── Servo range helpers ───────────────────────────────────────────────────────
  function servoRangeOf(d) {
    return {
      minAngle: d?.min_angle    ?? 0,
      maxAngle: d?.max_angle    ?? 300,
      minPulse: d?.min_pulse_us ?? 500,
      maxPulse: d?.max_pulse_us ?? 2500,
    };
  }

  function pulseToAngle(pulse_us, r) {
    if (r.maxPulse === r.minPulse) return r.minAngle;
    return r.minAngle + (pulse_us - r.minPulse) / (r.maxPulse - r.minPulse) * (r.maxAngle - r.minAngle);
  }

  function servoPresets(r, unit = '°') {
    const fmt = (n) => Number.isInteger(n) ? String(n) : n.toFixed(0);
    const c = (r.minAngle + r.maxAngle) / 2;
    const cLabel = unit === '%' ? `${fmt(c)}% (stop)` : `${fmt(c)}° (center)`;
    return [
      [r.minAngle, `${fmt(r.minAngle)}${unit}`],
      [r.minAngle + (r.maxAngle - r.minAngle) * 0.25, `${fmt(r.minAngle + (r.maxAngle - r.minAngle) * 0.25)}${unit}`],
      [c, cLabel],
      [r.minAngle + (r.maxAngle - r.minAngle) * 0.75, `${fmt(r.minAngle + (r.maxAngle - r.minAngle) * 0.75)}${unit}`],
      [r.maxAngle, `${fmt(r.maxAngle)}${unit}`],
    ];
  }

  // Servo range config editing state
  let servoRangeEditing = false;
  let srMinAngle = 0, srMaxAngle = 300, srMinPulse = 500, srMaxPulse = 2500;
  let pcaRangeEditing = false;
  let pcaSrMinAngle = 0, pcaSrMaxAngle = 300, pcaSrMinPulse = 500, pcaSrMaxPulse = 2500;

  $: sr        = servoRangeOf(selectedData);
  $: pcaSr     = servoRangeOf(selectedPcaData);
  $: servoUnit = selectedData?.gobilda_mode === 'continuous' ? '%' : '°';

  function selectPort(id) {
    selectedId = id;
    selectedPcaChannel = null;
    pcaCalibrating = false;
    reconfiguring = false;
    gobildaSwitching = false;
    const d = $ports[id];
    if (!d) return;
    if (isMotor(d.type)) motorSpeed = +(d.value / 100).toFixed(1);
    if (d.type === 'servo') {
      const r = servoRangeOf(d);
      servoAngle = +pulseToAngle(d.pulse_us ?? 1500, r).toFixed(1);
      servoAngle = Math.max(r.minAngle, Math.min(r.maxAngle, servoAngle));
    }
  }

  // ── Type helpers ─────────────────────────────────────────────────────────────
  const isMotor = (t) => t === 'motor_sm' || t === 'motor_lap' || t === 'motor_servo_signal';

  function deviceLabel(type) {
    if (isMotor(type)) return 'Motor';
    const m = { encoder: 'Encoder', ultrasonic: 'Ultrasonic', vl53l0x: 'VL53L0X ToF',
                 servo: 'Servo', gpio_in: 'Digital In', gpio_out: 'Digital Out',
                 i2c: 'I²C', uart: 'UART', tfluna: 'TF-Luna', tfmini: 'TF-Mini' };
    return m[type] ?? 'Empty';
  }

  function liveValue(d) {
    if (!d) return null;
    if (isMotor(d.type)) return `${((d.value ?? 0) / 100).toFixed(0)}% pwr`;
    switch (d.type) {
      case 'encoder':    return `${(d.count ?? 0).toLocaleString()} cnt`;
      case 'ultrasonic': return d.valid ? `${(d.distance_mm / 10).toFixed(1)} cm` : 'OOB';
      case 'vl53l0x':   return d.valid ? `${(d.distance_mm / 10).toFixed(1)} cm` : 'OOB';
      case 'tfluna':
      case 'tfmini':    return d.valid ? `${(d.distance_cm ?? 0).toFixed(0)} cm` : 'OOB';
      case 'servo': {
        const r = servoRangeOf(d);
        const unit = d.gobilda_mode === 'continuous' ? '%' : '°';
        return `${pulseToAngle(d.pulse_us ?? 1500, r).toFixed(1)}${unit}`;
      }
      case 'gpio_in':
      case 'gpio_out':   return d.state ? 'HIGH' : 'LOW';
      default:           return null;
    }
  }

  function accentClass(type) {
    if (isMotor(type))       return 'text-blue-400 border-blue-500/40';
    if (type === 'gpio_in' || type === 'gpio_out') return 'text-green-400 border-green-500/40';
    const m = {
      encoder:    'text-violet-400 border-violet-500/40',
      ultrasonic: 'text-cyan-400 border-cyan-500/40',
      vl53l0x:   'text-teal-400 border-teal-500/40',
      tfluna:    'text-sky-400 border-sky-500/40',
      tfmini:    'text-sky-400 border-sky-500/40',
      servo:      'text-amber-400 border-amber-500/40',
      i2c:        'text-orange-400 border-orange-500/40',
    };
    return m[type] ?? 'text-slate-600 border-slate-700/30';
  }

  function dotColor(type) {
    if (isMotor(type))       return 'bg-blue-400';
    if (type === 'gpio_in' || type === 'gpio_out') return 'bg-green-400';
    const m = { encoder: 'bg-violet-400', ultrasonic: 'bg-cyan-400', tfluna: 'bg-sky-400', tfmini: 'bg-sky-400',
                 vl53l0x: 'bg-teal-400', servo: 'bg-amber-400', i2c: 'bg-orange-400' };
    return m[type] ?? 'bg-slate-700';
  }

  // ── Motor commands ────────────────────────────────────────────────────────────
  function sendMotor(pct) {
    motorSpeed = Math.max(-100, Math.min(100, pct));
    send({ cmd: 'set_motor', port: selectedId, value_pct: motorSpeed });
  }

  function onMotorSlider(e) {
    sendMotor(Number(e.target.value));
  }

  // ── Servo commands ────────────────────────────────────────────────────────────
  function sendServo(deg) {
    const lo = Math.min(sr.minAngle, sr.maxAngle), hi = Math.max(sr.minAngle, sr.maxAngle);
    servoAngle = Math.max(lo, Math.min(hi, deg));
    send({ cmd: 'set_servo', port: selectedId, angle_deg: servoAngle });
  }

  function onServoSlider(e) {
    sendServo(Number(e.target.value));
  }

  function openServoRange() {
    srMinAngle = sr.minAngle; srMaxAngle = sr.maxAngle;
    srMinPulse = sr.minPulse; srMaxPulse = sr.maxPulse;
    servoRangeEditing = true;
  }

  function applyServoRange() {
    send({ cmd: 'set_servo_range', port: selectedId,
           min_angle: srMinAngle, max_angle: srMaxAngle,
           min_pulse_us: srMinPulse, max_pulse_us: srMaxPulse });
    servoAngle = (srMinAngle + srMaxAngle) / 2;
    servoRangeEditing = false;
  }

  // ── GoBilda mode switch ────────────────────────────────────────────────────────
  let gobildaSwitching = false;

  function sendGobildaMode(mode) {
    gobildaSwitching = true;
    send({ cmd: 'gobilda_set_mode', port: selectedId, mode });
    setTimeout(() => {
      gobildaSwitching = false;
      servoAngle = mode === 'continuous' ? 0 : 150;
      if (mode === 'continuous') {
        // Send an explicit stop so the servo doesn't run at the last positional pulse.
        // angle_deg 0 maps to 1500 µs (center of 900–2100 µs range) = stopped.
        send({ cmd: 'set_servo', port: selectedId, angle_deg: 0 });
      }
    }, 700);
  }

  // ── GPIO commands ─────────────────────────────────────────────────────────────
  function sendGpio(state) {
    send({ cmd: 'set_gpio', port: selectedId, state });
  }

  // ── Encoder commands ──────────────────────────────────────────────────────────
  function resetEncoder() {
    send({ cmd: 'reset_encoder', port: selectedId });
  }

  // ── Port configure / reset ────────────────────────────────────────────────────
  function configurePort() {
    if (!pendingType || selectedId === null) return;
    send({ cmd: 'configure_port', port: selectedId, type: pendingType });
    pendingType = null;
  }

  /**
   * Change the type of an already-configured port.
   * Because the firmware has no per-port reset, we must reset all ports,
   * then re-apply the saved configs for every OTHER port, then apply the new
   * type for this port. The daemon processes commands in order, so no delay
   * is needed — each message is fully handled before the next is read.
   */
  function doReconfigure() {
    if (!pendingType || selectedId === null) return;

    // Save configs for all ports except the one being changed
    const savedConfigs = ALL_PORTS
      .filter((p) => p.id !== selectedId && $ports[p.id]?.type)
      .map((p) => ({ port: p.id, type: $ports[p.id].type }));

    send({ cmd: 'reset_ports' });
    for (const { port, type } of savedConfigs) {
      send({ cmd: 'configure_port', port, type });
    }
    send({ cmd: 'configure_port', port: selectedId, type: pendingType });

    reconfiguring = false;
    pendingType = null;
    confirmReset = false;
  }

  function doResetPorts() {
    send({ cmd: 'reset_ports' });
    confirmReset = false;
  }

  // ── Global ────────────────────────────────────────────────────────────────────
  function stopAll() {
    send({ cmd: 'stop_all' });
    motorSpeed = 0;
  }

  // ── PCA9685 expansion channels ────────────────────────────────────────────────
  const PCA_CHANNELS = Array.from({ length: 16 }, (_, i) => ({ id: i, label: `P${i}` }));

  let selectedPcaChannel = null;
  let pcaCalibrating = false;
  let pcaCalibratePort = 0;     // which S-port (0–7) is wired to PCA channel 0
  let pcaCalibRunning = false;
  let pcaPendingType = null;
  let pcaMotorSpeed = 0;
  let pcaServoAngle = 150;

  $: pcaState = $robotState?.pca9685 ?? { present: false, channels: {} };
  $: selectedPcaData = selectedPcaChannel !== null
    ? (pcaState.channels?.[String(selectedPcaChannel)] ?? null)
    : null;

  // Detect calibration completion: daemon clears last_calibration before starting,
  // then sets it to the result dict when done. Watching for non-null is reliable.
  $: if (pcaCalibRunning && pcaState.last_calibration != null) {
    pcaCalibRunning = false;
  }

  function selectPcaChannel(ch) {
    selectedId = null;
    selectedPcaChannel = ch;
    pcaCalibrating = false;
    pcaPendingType = null;
    const d = pcaState.channels?.[String(ch)];
    if (d?.type && isMotor(d.type)) pcaMotorSpeed = 0;
    if (d?.type === 'servo') {
      const r = servoRangeOf(d);
      pcaServoAngle = +pulseToAngle(d.pulse_us ?? 1500, r).toFixed(1);
      pcaServoAngle = Math.max(r.minAngle, Math.min(r.maxAngle, pcaServoAngle));
    }
  }

  function openCalibration() {
    selectedId = null;
    selectedPcaChannel = null;
    pcaCalibrating = true;
  }

  function runCalibration() {
    pcaCalibRunning = true;
    send({ cmd: 'pca_calibrate', pico_port: pcaCalibratePort });
  }

  function configurePcaChannel() {
    if (!pcaPendingType || selectedPcaChannel === null) return;
    send({ cmd: 'pca_configure', channel: selectedPcaChannel, type: pcaPendingType });
    pcaPendingType = null;
  }

  function sendPcaMotor(pct) {
    pcaMotorSpeed = Math.max(-100, Math.min(100, pct));
    send({ cmd: 'pca_set_motor', channel: selectedPcaChannel, value_pct: pcaMotorSpeed });
  }

  function sendPcaServo(deg) {
    const lo = Math.min(pcaSr.minAngle, pcaSr.maxAngle), hi = Math.max(pcaSr.minAngle, pcaSr.maxAngle);
    pcaServoAngle = Math.max(lo, Math.min(hi, deg));
    send({ cmd: 'pca_set_servo', channel: selectedPcaChannel, angle_deg: pcaServoAngle });
  }

  function openPcaRange() {
    pcaSrMinAngle = pcaSr.minAngle; pcaSrMaxAngle = pcaSr.maxAngle;
    pcaSrMinPulse = pcaSr.minPulse; pcaSrMaxPulse = pcaSr.maxPulse;
    pcaRangeEditing = true;
  }

  function applyPcaRange() {
    send({ cmd: 'set_pca_servo_range', channel: selectedPcaChannel,
           min_angle: pcaSrMinAngle, max_angle: pcaSrMaxAngle,
           min_pulse_us: pcaSrMinPulse, max_pulse_us: pcaSrMaxPulse });
    pcaServoAngle = (pcaSrMinAngle + pcaSrMaxAngle) / 2;
    pcaRangeEditing = false;
  }
</script>

<div class="flex h-full overflow-hidden">

  <!-- ── Port list (left column) ── -->
  <div class="w-52 flex-shrink-0 flex flex-col border-r border-[#2e3340] bg-[#1a1d26] overflow-hidden">
    <div class="px-3 py-2 border-b border-[#2e3340] flex-shrink-0">
      <span class="text-[10px] font-bold uppercase tracking-widest text-slate-500">Ports</span>
    </div>

    <div class="flex-1 overflow-y-auto min-h-0">
      <!-- Dual-pin section -->
      <div class="px-2 pt-2 pb-1">
        <div class="text-[9px] text-slate-700 uppercase tracking-widest px-1 mb-1">Dual-pin D0–D7</div>
        {#each DUAL as p}
          {@const d = $ports[p.id]}
          <button
            class="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition-colors mb-px
                   {selectedId === p.id
                     ? 'bg-[#252932] ring-1 ring-[#3e4455]'
                     : 'hover:bg-[#1e2129]'}"
            on:click={() => selectPort(p.id)}
          >
            <!-- Port label badge -->
            <span class="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded flex-shrink-0
                         bg-slate-700/60 text-slate-400">{p.label}</span>

            {#if d}
              <!-- Color dot -->
              <span class="w-1.5 h-1.5 rounded-full flex-shrink-0 {dotColor(d.type)}"></span>
              <span class="text-[11px] text-slate-300 truncate">{deviceLabel(d.type)}</span>
              {#if liveValue(d)}
                <span class="text-[10px] font-mono text-slate-500 ml-auto flex-shrink-0">
                  {liveValue(d)}
                </span>
              {/if}
            {:else}
              <span class="text-[11px] text-slate-700 italic">empty</span>
            {/if}
          </button>
        {/each}
      </div>

      <!-- Divider -->
      <div class="border-t border-[#2e3340] mx-2 my-1"></div>

      <!-- Single-pin section -->
      <div class="px-2 pb-2">
        <div class="text-[9px] text-slate-700 uppercase tracking-widest px-1 mb-1">Single-pin S0–S7</div>
        {#each SINGLE as p}
          {@const d = $ports[p.id]}
          <button
            class="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition-colors mb-px
                   {selectedId === p.id
                     ? 'bg-[#252932] ring-1 ring-[#3e4455]'
                     : 'hover:bg-[#1e2129]'}"
            on:click={() => selectPort(p.id)}
          >
            <span class="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded flex-shrink-0
                         bg-slate-800/60 text-slate-500">{p.label}</span>

            {#if d}
              <span class="w-1.5 h-1.5 rounded-full flex-shrink-0 {dotColor(d.type)}"></span>
              <span class="text-[11px] text-slate-300 truncate">{deviceLabel(d.type)}</span>
              {#if liveValue(d)}
                <span class="text-[10px] font-mono text-slate-500 ml-auto flex-shrink-0">
                  {liveValue(d)}
                </span>
              {/if}
            {:else}
              <span class="text-[11px] text-slate-700 italic">empty</span>
            {/if}
          </button>
        {/each}
      </div>

      <!-- I²C port (port 16) — shown when a sensor is detected -->
      <!-- PCA9685 expansion channels (P0–P15) — shown when expander is detected -->
      {#if !pcaState.present}
        <div class="border-t border-[#2e3340] mx-2 my-1"></div>
        <div class="px-3 py-1.5 flex items-center gap-1.5">
          <span class="text-[9px] text-slate-700 uppercase tracking-widest">PCA9685</span>
          <span class="ml-auto text-[8px] text-slate-700 italic">not detected</span>
        </div>
      {:else}
      {/if}
      {#if pcaState.present}
        <div class="border-t border-[#2e3340] mx-2 my-1"></div>
        <div class="px-2 pb-1">
          <div class="flex items-center px-1 mb-1">
            <div class="text-[9px] text-slate-700 uppercase tracking-widest">PCA9685  P0–P15</div>
            {#if pcaState.calibrated}
              <span class="ml-auto text-[8px] text-green-600 font-semibold">calibrated</span>
            {:else}
              <button
                class="ml-auto text-[8px] text-amber-600 hover:text-amber-400 transition-colors cursor-pointer"
                on:click={openCalibration}
              >calibrate…</button>
            {/if}
          </div>
          {#each PCA_CHANNELS as ch}
            {@const chData = pcaState.channels?.[String(ch.id)]}
            <button
              class="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition-colors mb-px
                     {selectedPcaChannel === ch.id
                       ? 'bg-[#252932] ring-1 ring-[#3e4455]'
                       : 'hover:bg-[#1e2129]'}"
              on:click={() => selectPcaChannel(ch.id)}
            >
              <span class="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded flex-shrink-0
                           bg-purple-900/40 text-purple-400">{ch.label}</span>
              {#if chData?.type}
                <span class="w-1.5 h-1.5 rounded-full flex-shrink-0 {isMotor(chData.type) ? 'bg-blue-400' : 'bg-amber-400'}"></span>
                <span class="text-[11px] text-slate-300 truncate">{isMotor(chData.type) ? 'Motor' : 'Servo'}</span>
              {:else}
                <span class="text-[11px] text-slate-700 italic">empty</span>
              {/if}
            </button>
          {/each}
          {#if !pcaState.calibrated}
            <button
              class="w-full mt-1 px-2 py-1 rounded text-[9px] text-amber-700 border border-amber-900/40
                     hover:bg-amber-900/20 hover:text-amber-500 transition-colors text-center"
              on:click={openCalibration}
            >⚠ Oscillator uncalibrated — click to calibrate</button>
          {/if}
        </div>
      {/if}

      {#if $ports[16]}
        <div class="border-t border-[#2e3340] mx-2 my-1"></div>
        <div class="px-2 pb-2">
          <div class="text-[9px] text-slate-700 uppercase tracking-widest px-1 mb-1">I²C</div>
          <button
            class="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition-colors mb-px
                   {selectedId === 16
                     ? 'bg-[#252932] ring-1 ring-[#3e4455]'
                     : 'hover:bg-[#1e2129]'}"
            on:click={() => selectPort(16)}
          >
            <span class="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded flex-shrink-0
                         bg-slate-700/60 text-slate-400">I²C</span>
            <span class="w-1.5 h-1.5 rounded-full flex-shrink-0 {dotColor($ports[16].type)}"></span>
            <span class="text-[11px] text-slate-300 truncate">{deviceLabel($ports[16].type)}</span>
            {#if liveValue($ports[16])}
              <span class="text-[10px] font-mono text-slate-500 ml-auto flex-shrink-0">
                {liveValue($ports[16])}
              </span>
            {/if}
          </button>
        </div>
      {/if}
    </div>
  </div>

  <!-- ── Detail / control panel (right) ── -->
  <div class="flex-1 min-w-0 flex flex-col overflow-hidden bg-[#161920]">

    {#if pcaCalibrating}
      <!-- ── PCA9685 Calibration Wizard ── -->
      <div class="flex-1 overflow-y-auto p-6">
        <div class="max-w-md space-y-6">
          <div>
            <div class="flex items-center gap-3 mb-1">
              <span class="text-sm font-bold text-purple-300">PCA9685 Oscillator Calibration</span>
              <button
                class="ml-auto text-xs text-slate-500 hover:text-slate-300 transition-colors"
                on:click={() => pcaCalibrating = false}
              >✕ Close</button>
            </div>
            <p class="text-xs text-slate-500 leading-relaxed">
              Wires PCA channel 0 to a Pico S-port. The Pico measures the actual pulse width
              and adjusts the PCA prescale so 1500 µs commands are accurate.
            </p>
          </div>

          <div class="bg-[#1e2129] border border-[#2e3340] rounded-lg p-4 space-y-3">
            <p class="text-[11px] text-slate-400 font-semibold">Step 1 — Physical wiring</p>
            <p class="text-xs text-slate-500">
              Connect a wire from the <strong class="text-purple-300">PCA9685 channel 0 output</strong>
              to a Pico <strong class="text-slate-300">single-pin S-port</strong> (signal line only — no power).
            </p>
          </div>

          <div class="space-y-2">
            <p class="text-[11px] text-slate-400 font-semibold">Step 2 — Select the S-port you wired to</p>
            <div class="flex flex-wrap gap-1.5">
              {#each [0,1,2,3,4,5,6,7] as sp}
                <button
                  class="px-3 py-1.5 rounded text-xs font-mono border transition-all
                         {pcaCalibratePort === sp
                           ? 'bg-purple-600/20 border-purple-500/60 text-purple-300'
                           : 'bg-[#1e2129] border-[#2e3340] text-slate-400 hover:border-slate-500'}"
                  on:click={() => pcaCalibratePort = sp}
                >S{sp}</button>
              {/each}
            </div>
          </div>

          <div>
            <button
              disabled={pcaCalibRunning}
              class="px-5 py-2.5 rounded-lg text-sm font-semibold transition-all
                     {pcaCalibRunning
                       ? 'bg-slate-700 border border-[#2e3340] text-slate-500 cursor-wait'
                       : 'bg-purple-600/30 border border-purple-500/50 text-purple-300 hover:bg-purple-600/50 cursor-pointer'}"
              on:click={runCalibration}
            >
              {#if pcaCalibRunning}
                <span class="flex items-center gap-2">
                  <span class="animate-spin inline-block w-3 h-3 border-2 border-purple-400/30 border-t-purple-400 rounded-full"></span>
                  Measuring pulse on S{pcaCalibratePort}…
                </span>
              {:else}
                Run Calibration via S{pcaCalibratePort}
              {/if}
            </button>
          </div>

          {#if pcaState.last_calibration}
            {@const r = pcaState.last_calibration}
            <div class="rounded-lg border p-4 {r.ok
              ? 'bg-green-900/10 border-green-700/30'
              : 'bg-red-900/10 border-red-700/30'}">
              {#if r.ok}
                <p class="text-sm font-semibold text-green-400 mb-2">✓ Calibration successful</p>
                <div class="space-y-1 text-xs font-mono text-slate-400">
                  <div>Measured pulse: <span class="text-slate-200">{r.measured_us} µs</span></div>
                  <div>Actual oscillator: <span class="text-slate-200">{r.osc_freq.toLocaleString()} Hz</span>
                    <span class="text-slate-600">
                      ({r.osc_freq > 25_000_000 ? '+' : ''}{((r.osc_freq/25_000_000-1)*100).toFixed(2)}% vs nominal)
                    </span>
                  </div>
                  <div>Prescale: <span class="text-slate-200">{r.prescale}</span></div>
                </div>
              {:else}
                <p class="text-sm font-semibold text-red-400 mb-1">✗ Calibration failed</p>
                <p class="text-xs text-red-300/70">{r.error}</p>
              {/if}
            </div>
          {/if}
        </div>
      </div>

    {:else if selectedId === null && selectedPcaChannel === null}
      <!-- No port selected -->
      <div class="flex flex-col items-center justify-center h-full gap-3 text-slate-700">
        <svg class="w-10 h-10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <rect x="3" y="7" width="4" height="10" rx="1"/>
          <rect x="10" y="7" width="4" height="10" rx="1"/>
          <rect x="17" y="7" width="4" height="10" rx="1"/>
        </svg>
        <span class="text-sm">Select a port from the list</span>
      </div>

    {:else if selectedPcaChannel !== null}
      <!-- ── PCA9685 channel detail ── -->
      <div class="flex items-center gap-3 px-5 py-3 border-b border-[#2e3340] flex-shrink-0 bg-[#1a1d26]">
        <span class="text-[11px] font-bold font-mono px-2 py-1 rounded bg-purple-900/40 text-purple-300">
          P{selectedPcaChannel}
        </span>
        {#if selectedPcaData}
          <span class="text-sm font-semibold {isMotor(selectedPcaData.type) ? 'text-blue-400' : 'text-amber-400'}">
            {isMotor(selectedPcaData.type) ? 'Motor' : 'Servo'}
          </span>
          <span class="text-xs text-slate-600">PCA9685 channel {selectedPcaChannel}</span>
        {:else}
          <span class="text-sm text-slate-600 italic">not configured</span>
        {/if}
        <div class="ml-auto">
          <button
            class="px-3 py-1 rounded text-xs font-semibold bg-red-600/20 text-red-400
                   border border-red-600/30 hover:bg-red-600/40 transition-colors"
            on:click={() => { send({ cmd: 'pca_set_motor', channel: selectedPcaChannel, value_pct: 0 }); pcaMotorSpeed = 0; }}
          >Stop</button>
        </div>
      </div>

      <div class="flex-1 overflow-y-auto p-6">
        {#if !selectedPcaData}
          <!-- Unconfigured PCA channel -->
          <div class="max-w-sm space-y-5">
            <div>
              <p class="text-sm font-semibold text-slate-300 mb-1">Choose a device type</p>
              <p class="text-xs text-slate-600">PCA9685 only supports 50 Hz outputs (servo / RC ESC).</p>
            </div>
            <div class="flex gap-2">
              {#each [['motor_servo_signal', 'Motor', 'RC ESC / servo signal'], ['servo', 'Servo', 'Standard servo']] as [id, label, sub]}
                <button
                  class="flex flex-col items-start px-3 py-2 rounded-lg border transition-all text-left
                         {pcaPendingType === id
                           ? 'bg-blue-600/20 border-blue-500/60 text-blue-300'
                           : 'bg-[#1e2129] border-[#2e3340] text-slate-400 hover:border-slate-500 hover:text-slate-300'}"
                  on:click={() => pcaPendingType = id}
                >
                  <span class="text-xs font-semibold leading-tight">{label}</span>
                  <span class="text-[10px] {pcaPendingType === id ? 'text-blue-400/70' : 'text-slate-600'} leading-tight mt-0.5">{sub}</span>
                </button>
              {/each}
            </div>
            <button
              disabled={!pcaPendingType}
              class="px-5 py-2 rounded-lg text-sm font-semibold transition-all
                     {pcaPendingType
                       ? 'bg-blue-600/30 border border-blue-500/50 text-blue-300 hover:bg-blue-600/50 cursor-pointer'
                       : 'bg-[#1e2129] border border-[#2e3340] text-slate-700 cursor-not-allowed'}"
              on:click={configurePcaChannel}
            >
              {pcaPendingType ? `Configure P${selectedPcaChannel} as ${pcaPendingType === 'servo' ? 'Servo' : 'Motor'}` : 'Select a type above'}
            </button>
          </div>

        {:else if isMotor(selectedPcaData.type)}
          <!-- PCA motor control -->
          <div class="max-w-lg space-y-6">
            <div class="flex items-baseline gap-3">
              <span class="text-4xl font-bold tabular-nums text-blue-400">{pcaMotorSpeed.toFixed(1)}%</span>
              <span class="text-sm text-slate-500">power</span>
            </div>
            <div class="space-y-2">
              <div class="flex justify-between text-xs text-slate-500">
                <span>−100%</span>
                <span class="font-semibold text-slate-300 tabular-nums">{pcaMotorSpeed.toFixed(1)}%</span>
                <span>+100%</span>
              </div>
              <input
                type="range" min="-100" max="100" step="0.5"
                value={pcaMotorSpeed}
                class="w-full h-2 rounded-full appearance-none cursor-pointer
                       bg-gradient-to-r from-red-600/40 via-slate-600 to-blue-600/40 accent-blue-500"
                on:input={(e) => sendPcaMotor(Number(e.target.value))}
              />
              <div class="relative h-0">
                <div class="absolute top-0 left-1/2 w-px h-2 bg-slate-600 -translate-y-2"></div>
              </div>
            </div>
            <div class="flex gap-2">
              {#each [[-100,'−100%'],[-75,'−75%'],[-50,'−50%'],[-25,'−25%']] as [v, label]}
                <button class="px-3 py-1.5 rounded text-xs font-mono bg-[#1e2129] border border-[#2e3340]
                               text-red-400 hover:bg-red-900/20 hover:border-red-600/40 transition-colors"
                  on:click={() => sendPcaMotor(v)}>{label}</button>
              {/each}
              <button class="px-4 py-1.5 rounded text-xs font-bold bg-slate-700 border border-slate-600
                             text-slate-200 hover:bg-slate-600 transition-colors"
                on:click={() => sendPcaMotor(0)}>STOP</button>
              {#each [[25,'+25%'],[50,'+50%'],[75,'+75%'],[100,'+100%']] as [v, label]}
                <button class="px-3 py-1.5 rounded text-xs font-mono bg-[#1e2129] border border-[#2e3340]
                               text-blue-400 hover:bg-blue-900/20 hover:border-blue-600/40 transition-colors"
                  on:click={() => sendPcaMotor(v)}>{label}</button>
              {/each}
            </div>
            <p class="text-[11px] text-slate-600">RC ESC protocol: 1500 µs = stop, 1100 µs = full reverse, 1900 µs = full forward.</p>
          </div>

        {:else if selectedPcaData.type === 'servo'}
          <!-- PCA servo control -->
          <div class="max-w-lg space-y-6">
            <div class="flex items-baseline gap-3">
              <span class="text-4xl font-bold tabular-nums text-amber-400">{pcaServoAngle.toFixed(1)}°</span>
              <span class="text-sm text-slate-500">angle</span>
            </div>
            <div class="space-y-2">
              <div class="flex justify-between text-xs text-slate-500">
                <span>{pcaSr.minAngle}°</span>
                <span class="font-semibold text-slate-300 tabular-nums">{pcaServoAngle.toFixed(1)}°</span>
                <span>{pcaSr.maxAngle}°</span>
              </div>
              <input
                type="range" min={Math.min(pcaSr.minAngle, pcaSr.maxAngle)} max={Math.max(pcaSr.minAngle, pcaSr.maxAngle)} step="0.5"
                value={pcaServoAngle}
                class="w-full h-2 rounded-full appearance-none cursor-pointer
                       bg-gradient-to-r from-amber-800/40 via-amber-600/20 to-amber-800/40 accent-amber-400"
                on:input={(e) => sendPcaServo(Number(e.target.value))}
              />
            </div>
            <div class="flex gap-2 flex-wrap">
              {#each servoPresets(pcaSr) as [v, label]}
                <button class="px-3 py-1.5 rounded text-xs font-mono bg-[#1e2129] border border-[#2e3340]
                               text-amber-400 hover:bg-amber-900/20 hover:border-amber-600/40 transition-colors"
                  on:click={() => sendPcaServo(v)}>{label}</button>
              {/each}
            </div>
            {#if pcaRangeEditing}
              <div class="border border-amber-500/30 rounded-lg p-4 space-y-3 bg-amber-900/10">
                <p class="text-xs font-semibold text-amber-400">Set servo range</p>
                <div class="grid grid-cols-2 gap-3">
                  <label class="space-y-1">
                    <span class="text-[10px] text-slate-500 uppercase tracking-wider">Min angle (°)</span>
                    <input type="number" bind:value={pcaSrMinAngle} step="1"
                      class="w-full bg-[#1e2129] border border-[#2e3340] rounded px-2 py-1
                             text-xs text-slate-200 focus:outline-none focus:border-amber-500/60"/>
                  </label>
                  <label class="space-y-1">
                    <span class="text-[10px] text-slate-500 uppercase tracking-wider">Max angle (°)</span>
                    <input type="number" bind:value={pcaSrMaxAngle} step="1"
                      class="w-full bg-[#1e2129] border border-[#2e3340] rounded px-2 py-1
                             text-xs text-slate-200 focus:outline-none focus:border-amber-500/60"/>
                  </label>
                  <label class="space-y-1">
                    <span class="text-[10px] text-slate-500 uppercase tracking-wider">Min pulse (µs)</span>
                    <input type="number" bind:value={pcaSrMinPulse} step="1"
                      class="w-full bg-[#1e2129] border border-[#2e3340] rounded px-2 py-1
                             text-xs text-slate-200 focus:outline-none focus:border-amber-500/60"/>
                  </label>
                  <label class="space-y-1">
                    <span class="text-[10px] text-slate-500 uppercase tracking-wider">Max pulse (µs)</span>
                    <input type="number" bind:value={pcaSrMaxPulse} step="1"
                      class="w-full bg-[#1e2129] border border-[#2e3340] rounded px-2 py-1
                             text-xs text-slate-200 focus:outline-none focus:border-amber-500/60"/>
                  </label>
                </div>
                <div class="flex gap-2">
                  <button class="px-3 py-1.5 rounded text-xs font-semibold bg-amber-600/30
                                 border border-amber-500/50 text-amber-300 hover:bg-amber-600/50 transition-colors"
                    on:click={applyPcaRange}>Apply</button>
                  <button class="px-3 py-1.5 rounded text-xs text-slate-500 border border-[#2e3340]
                                 hover:text-slate-300 transition-colors"
                    on:click={() => pcaRangeEditing = false}>Cancel</button>
                </div>
              </div>
            {:else}
              <button class="text-[10px] text-slate-600 hover:text-amber-500 transition-colors"
                on:click={openPcaRange}>
                ⚙ Range: {pcaSr.minAngle}° – {pcaSr.maxAngle}° ({pcaSr.minPulse}–{pcaSr.maxPulse} µs)
              </button>
            {/if}
          </div>
        {/if}
      </div>

    {:else}
      <!-- Port header -->
      <div class="flex items-center gap-3 px-5 py-3 border-b border-[#2e3340] flex-shrink-0 bg-[#1a1d26]">
        <span class="text-[11px] font-bold font-mono px-2 py-1 rounded
                     {selectedPort?.dual ? 'bg-slate-700/60 text-slate-300' : 'bg-slate-800/60 text-slate-400'}">
          {selectedPort?.label}
        </span>
        {#if selectedData}
          <span class="text-sm font-semibold {accentClass(selectedData.type).split(' ')[0]}">
            {deviceLabel(selectedData.type)}
          </span>
          {#if isMotor(selectedData.type)}
            <span class="text-xs text-slate-600">
              {selectedData.type === 'motor_sm' ? 'sign-magnitude'
               : selectedData.type === 'motor_lap' ? 'locked antiphase'
               : 'servo signal'}
            </span>
          {/if}
        {:else}
          <span class="text-sm text-slate-600 italic">not configured</span>
        {/if}

        <!-- Reset / Stop All — always accessible -->
        <div class="ml-auto flex items-center gap-2">
          {#if confirmReset}
            <span class="text-xs text-amber-400">Reset all ports?</span>
            <button
              class="px-3 py-1 rounded text-xs font-semibold bg-amber-600/20 text-amber-400
                     border border-amber-600/40 hover:bg-amber-600/40 transition-colors"
              on:click={doResetPorts}
            >Confirm</button>
            <button
              class="px-3 py-1 rounded text-xs text-slate-500 border border-[#2e3340]
                     hover:text-slate-300 transition-colors"
              on:click={() => confirmReset = false}
            >Cancel</button>
          {:else}
            <button
              class="px-3 py-1 rounded text-xs font-semibold bg-slate-700/40 text-slate-400
                     border border-[#2e3340] hover:bg-slate-600/40 hover:text-slate-300 transition-colors"
              on:click={() => confirmReset = true}
            >Reset All Ports</button>
            <button
              class="px-3 py-1 rounded text-xs font-semibold bg-red-600/20 text-red-400
                     border border-red-600/30 hover:bg-red-600/40 transition-colors"
              on:click={stopAll}
            >Stop All Motors</button>
          {/if}
        </div>
      </div>

      <!-- Control body -->
      <div class="flex-1 overflow-y-auto p-6">

        {#if !selectedData}
          <!-- Unconfigured — show type picker or locked message -->
          {#if configFinalized}
            <div class="flex flex-col items-center justify-center h-full gap-3 text-slate-600">
              <svg class="w-8 h-8 text-slate-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
                <rect x="5" y="11" width="14" height="10" rx="2"/>
                <path d="M8 11V7a4 4 0 0 1 8 0v4"/>
              </svg>
              <p class="text-sm text-center">Configuration is locked by student code.</p>
              <p class="text-xs text-slate-700 text-center">Click <strong class="text-slate-500">Reset All Ports</strong> in the header to start fresh.</p>
            </div>
          {:else}
            <div class="max-w-md space-y-5">
              <div>
                <p class="text-sm font-semibold text-slate-300 mb-1">Choose a device type</p>
                <p class="text-xs text-slate-600">
                  {selectedPort?.dual ? 'Dual-pin port' : 'Single-pin port'} —
                  {selectedPort?.dual ? 'all types available' : 'single-pin types only'}
                </p>
              </div>

              <!-- Type cards grouped by category -->
              {#each ['Motor', 'Servo', 'Sensor', 'GPIO', 'Bus'] as group}
                {@const groupTypes = availableTypes.filter((t) => t.group === group)}
                {#if groupTypes.length > 0}
                  <div>
                    <div class="text-[9px] font-bold uppercase tracking-widest text-slate-600 mb-1.5">{group}</div>
                    <div class="flex flex-wrap gap-1.5">
                      {#each groupTypes as t}
                        <button
                          class="flex flex-col items-start px-3 py-2 rounded-lg border transition-all text-left
                                 {pendingType === t.id
                                   ? 'bg-blue-600/20 border-blue-500/60 text-blue-300'
                                   : 'bg-[#1e2129] border-[#2e3340] text-slate-400 hover:border-slate-500 hover:text-slate-300'}"
                          on:click={() => pendingType = t.id}
                        >
                          <span class="text-xs font-semibold leading-tight">{t.label}</span>
                          {#if t.sub}
                            <span class="text-[10px] {pendingType === t.id ? 'text-blue-400/70' : 'text-slate-600'} leading-tight mt-0.5">{t.sub}</span>
                          {/if}
                        </button>
                      {/each}
                    </div>
                  </div>
                {/if}
              {/each}

              <!-- Configure button -->
              <div class="pt-1">
                <button
                  disabled={!pendingType}
                  class="px-5 py-2 rounded-lg text-sm font-semibold transition-all
                         {pendingType
                           ? 'bg-blue-600/30 border border-blue-500/50 text-blue-300 hover:bg-blue-600/50 cursor-pointer'
                           : 'bg-[#1e2129] border border-[#2e3340] text-slate-700 cursor-not-allowed'}"
                  on:click={configurePort}
                >
                  {pendingType
                    ? `Configure ${selectedPort?.label} as ${TYPE_DEFS.find(t => t.id === pendingType)?.label}${TYPE_DEFS.find(t => t.id === pendingType)?.sub ? ' (' + TYPE_DEFS.find(t => t.id === pendingType)?.sub + ')' : ''}`
                    : 'Select a type above'}
                </button>
              </div>
            </div>
          {/if}

        {:else if reconfiguring}
          <!-- ── Reconfigure: pick a new type (triggers full reset + re-apply) ── -->
          <div class="max-w-md space-y-5">
            <div>
              <p class="text-sm font-semibold text-slate-300 mb-1">Choose a new device type</p>
              <p class="text-xs text-slate-500">
                Changing the type of <strong>{selectedPort?.label}</strong> requires resetting all
                ports. Other configured ports will be re-applied automatically.
              </p>
            </div>

            {#each ['Motor', 'Servo', 'Sensor', 'GPIO', 'Bus'] as group}
              {@const groupTypes = availableTypes.filter((t) => t.group === group)}
              {#if groupTypes.length > 0}
                <div>
                  <div class="text-[9px] font-bold uppercase tracking-widest text-slate-600 mb-1.5">{group}</div>
                  <div class="flex flex-wrap gap-1.5">
                    {#each groupTypes as t}
                      <button
                        class="flex flex-col items-start px-3 py-2 rounded-lg border transition-all text-left
                               {pendingType === t.id
                                 ? 'bg-blue-600/20 border-blue-500/60 text-blue-300'
                                 : 'bg-[#1e2129] border-[#2e3340] text-slate-400 hover:border-slate-500 hover:text-slate-300'}"
                        on:click={() => pendingType = t.id}
                      >
                        <span class="text-xs font-semibold leading-tight">{t.label}</span>
                        {#if t.sub}
                          <span class="text-[10px] {pendingType === t.id ? 'text-blue-400/70' : 'text-slate-600'} leading-tight mt-0.5">{t.sub}</span>
                        {/if}
                      </button>
                    {/each}
                  </div>
                </div>
              {/if}
            {/each}

            <div class="flex gap-2 pt-1">
              <button
                disabled={!pendingType}
                class="px-5 py-2 rounded-lg text-sm font-semibold transition-all
                       {pendingType
                         ? 'bg-blue-600/30 border border-blue-500/50 text-blue-300 hover:bg-blue-600/50 cursor-pointer'
                         : 'bg-[#1e2129] border border-[#2e3340] text-slate-700 cursor-not-allowed'}"
                on:click={doReconfigure}
              >
                {pendingType
                  ? `Apply — reset & reconfigure as ${TYPE_DEFS.find(t => t.id === pendingType)?.label}${TYPE_DEFS.find(t => t.id === pendingType)?.sub ? ' (' + TYPE_DEFS.find(t => t.id === pendingType)?.sub + ')' : ''}`
                  : 'Select a type above'}
              </button>
              <button
                class="px-4 py-2 rounded-lg text-sm text-slate-500 border border-[#2e3340]
                       hover:text-slate-300 hover:border-slate-500 transition-colors"
                on:click={() => { reconfiguring = false; pendingType = null; }}
              >Cancel</button>
            </div>
          </div>

        {:else if isMotor(selectedData.type)}
          <!-- ── Motor control ── -->
          <div class="max-w-lg space-y-6">

            <!-- Live readout -->
            <div class="flex items-baseline gap-3">
              <span class="text-4xl font-bold tabular-nums text-blue-400">
                {((selectedData.value ?? 0) / 100).toFixed(1)}%
              </span>
              <span class="text-sm text-slate-500">power (from RP2040)</span>
            </div>

            <!-- Power slider -->
            <div class="space-y-2">
              <div class="flex justify-between text-xs text-slate-500">
                <span>−100%</span>
                <span class="font-semibold text-slate-300 tabular-nums">{motorSpeed.toFixed(1)}%</span>
                <span>+100%</span>
              </div>
              <input
                type="range" min="-100" max="100" step="0.5"
                value={motorSpeed}
                class="w-full h-2 rounded-full appearance-none cursor-pointer
                       bg-gradient-to-r from-red-600/40 via-slate-600 to-blue-600/40
                       accent-blue-500"
                on:input={onMotorSlider}
              />
              <!-- Zero marker line -->
              <div class="relative h-0">
                <div class="absolute top-0 left-1/2 w-px h-2 bg-slate-600 -translate-y-2"></div>
              </div>
            </div>

            <!-- Quick presets -->
            <div class="flex gap-2">
              {#each [[-100, '−100%'], [-75, '−75%'], [-50, '−50%'], [-25, '−25%']] as [v, label]}
                <button
                  class="px-3 py-1.5 rounded text-xs font-mono bg-[#1e2129] border border-[#2e3340]
                         text-red-400 hover:bg-red-900/20 hover:border-red-600/40 transition-colors"
                  on:click={() => sendMotor(v)}>{label}</button>
              {/each}

              <button
                class="px-4 py-1.5 rounded text-xs font-bold bg-slate-700 border border-slate-600
                       text-slate-200 hover:bg-slate-600 transition-colors"
                on:click={() => sendMotor(0)}>STOP</button>

              {#each [[25, '+25%'], [50, '+50%'], [75, '+75%'], [100, '+100%']] as [v, label]}
                <button
                  class="px-3 py-1.5 rounded text-xs font-mono bg-[#1e2129] border border-[#2e3340]
                         text-blue-400 hover:bg-blue-900/20 hover:border-blue-600/40 transition-colors"
                  on:click={() => sendMotor(v)}>{label}</button>
              {/each}
            </div>

            <p class="text-[11px] text-slate-600">
              Manual commands are temporary — running student code will override them.
            </p>
          </div>

        {:else if selectedData.type === 'servo'}
          <!-- ── Servo control ── -->
          <div class="max-w-lg space-y-6">

            <!-- Live readout -->
            <div class="flex items-baseline gap-3">
              <span class="text-4xl font-bold tabular-nums text-amber-400">
                {pulseToAngle(selectedData.pulse_us ?? 1500, sr).toFixed(1)}{servoUnit}
              </span>
              <span class="text-sm text-slate-500">actual (from RP2040)</span>
            </div>

            <!-- Angle slider -->
            <div class="space-y-2">
              <div class="flex justify-between text-xs text-slate-500">
                <span>{sr.minAngle}{servoUnit}</span>
                <span class="font-semibold text-slate-300 tabular-nums">{servoAngle.toFixed(1)}{servoUnit}</span>
                <span>{sr.maxAngle}{servoUnit}</span>
              </div>
              <input
                type="range" min={Math.min(sr.minAngle, sr.maxAngle)} max={Math.max(sr.minAngle, sr.maxAngle)} step="0.5"
                value={servoAngle}
                class="w-full h-2 rounded-full appearance-none cursor-pointer
                       bg-gradient-to-r from-amber-800/40 via-amber-600/20 to-amber-800/40
                       accent-amber-400"
                on:input={onServoSlider}
              />
            </div>

            <!-- Quick presets -->
            <div class="flex gap-2 flex-wrap">
              {#each servoPresets(sr, servoUnit) as [v, label]}
                <button
                  class="px-3 py-1.5 rounded text-xs font-mono bg-[#1e2129] border border-[#2e3340]
                         text-amber-400 hover:bg-amber-900/20 hover:border-amber-600/40 transition-colors"
                  on:click={() => sendServo(v)}>{label}</button>
              {/each}
            </div>

            <!-- Range configuration -->
            {#if servoRangeEditing}
              <div class="border border-amber-500/30 rounded-lg p-4 space-y-3 bg-amber-900/10">
                <p class="text-xs font-semibold text-amber-400">Set servo range</p>
                <div class="grid grid-cols-2 gap-3">
                  <label class="space-y-1">
                    <span class="text-[10px] text-slate-500 uppercase tracking-wider">Min angle (°)</span>
                    <input type="number" bind:value={srMinAngle} step="1"
                      class="w-full bg-[#1e2129] border border-[#2e3340] rounded px-2 py-1
                             text-xs text-slate-200 focus:outline-none focus:border-amber-500/60"/>
                  </label>
                  <label class="space-y-1">
                    <span class="text-[10px] text-slate-500 uppercase tracking-wider">Max angle (°)</span>
                    <input type="number" bind:value={srMaxAngle} step="1"
                      class="w-full bg-[#1e2129] border border-[#2e3340] rounded px-2 py-1
                             text-xs text-slate-200 focus:outline-none focus:border-amber-500/60"/>
                  </label>
                  <label class="space-y-1">
                    <span class="text-[10px] text-slate-500 uppercase tracking-wider">Min pulse (µs)</span>
                    <input type="number" bind:value={srMinPulse} step="1"
                      class="w-full bg-[#1e2129] border border-[#2e3340] rounded px-2 py-1
                             text-xs text-slate-200 focus:outline-none focus:border-amber-500/60"/>
                  </label>
                  <label class="space-y-1">
                    <span class="text-[10px] text-slate-500 uppercase tracking-wider">Max pulse (µs)</span>
                    <input type="number" bind:value={srMaxPulse} step="1"
                      class="w-full bg-[#1e2129] border border-[#2e3340] rounded px-2 py-1
                             text-xs text-slate-200 focus:outline-none focus:border-amber-500/60"/>
                  </label>
                </div>
                <div class="flex gap-2">
                  <button class="px-3 py-1.5 rounded text-xs font-semibold bg-amber-600/30
                                 border border-amber-500/50 text-amber-300 hover:bg-amber-600/50 transition-colors"
                    on:click={applyServoRange}>Apply</button>
                  <button class="px-3 py-1.5 rounded text-xs text-slate-500 border border-[#2e3340]
                                 hover:text-slate-300 transition-colors"
                    on:click={() => servoRangeEditing = false}>Cancel</button>
                </div>
              </div>
            {:else}
              <button class="text-[10px] text-slate-600 hover:text-amber-500 transition-colors"
                on:click={openServoRange}>
                ⚙ Range: {sr.minAngle}{servoUnit} – {sr.maxAngle}{servoUnit} ({sr.minPulse}–{sr.maxPulse} µs)
              </button>
            {/if}

            <!-- GoBilda dual-mode switch (S-port servos only) -->
            {#if selectedId !== null && selectedId < 8}
              <div class="border border-slate-700/40 rounded-lg p-3 space-y-2 bg-[#1a1d26]">
                <div class="flex items-center gap-2">
                  <span class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">GoBilda Mode</span>
                  <span class="text-[10px] text-slate-700">· gray dual-mode servos only</span>
                  {#if selectedData?.gobilda_mode}
                    <span class="ml-auto text-[10px] font-mono
                                 {selectedData.gobilda_mode === 'continuous' ? 'text-blue-400' : 'text-amber-400'}">
                      {selectedData.gobilda_mode}
                    </span>
                  {/if}
                </div>
                {#if gobildaSwitching}
                  <div class="flex items-center gap-2 text-xs text-amber-400">
                    <span class="animate-spin inline-block w-3 h-3 border-2 border-amber-400/30 border-t-amber-400 rounded-full"></span>
                    Switching mode… (~500 ms)
                  </div>
                {:else}
                  <div class="flex gap-2">
                    <button
                      class="px-3 py-1.5 rounded text-xs font-semibold transition-all border
                             {selectedData?.gobilda_mode === 'positional'
                               ? 'bg-amber-600/20 border-amber-500/50 text-amber-300'
                               : 'bg-[#161920] border-[#2e3340] text-slate-500 hover:border-slate-500 hover:text-slate-300'}"
                      on:click={() => sendGobildaMode('positional')}
                    >Positional</button>
                    <button
                      class="px-3 py-1.5 rounded text-xs font-semibold transition-all border
                             {selectedData?.gobilda_mode === 'continuous'
                               ? 'bg-blue-600/20 border-blue-500/50 text-blue-300'
                               : 'bg-[#161920] border-[#2e3340] text-slate-500 hover:border-slate-500 hover:text-slate-300'}"
                      on:click={() => sendGobildaMode('continuous')}
                    >Continuous</button>
                  </div>
                {/if}
              </div>
            {/if}

            <p class="text-[11px] text-slate-600">
              Servos hold their last position — they are not affected by Stop All.
            </p>
          </div>

        {:else if selectedData.type === 'gpio_out'}
          <!-- ── Digital output control ── -->
          <div class="max-w-xs space-y-6">

            <!-- Live readout -->
            <div class="flex items-center gap-4">
              <div class="text-4xl font-bold {selectedData.state ? 'text-green-400' : 'text-slate-500'}">
                {selectedData.state ? 'HIGH' : 'LOW'}
              </div>
              <div class="w-4 h-4 rounded-full {selectedData.state ? 'bg-green-400 shadow-[0_0_8px_#4ade80]' : 'bg-slate-700'}"></div>
            </div>

            <!-- Toggle buttons -->
            <div class="flex gap-3">
              <button
                class="flex-1 py-3 rounded-lg text-sm font-bold transition-all
                       {!selectedData.state
                         ? 'bg-green-600/20 border-2 border-green-500 text-green-400'
                         : 'bg-[#1e2129] border border-[#2e3340] text-slate-500 hover:border-slate-500'}"
                on:click={() => sendGpio(false)}
              >LOW</button>
              <button
                class="flex-1 py-3 rounded-lg text-sm font-bold transition-all
                       {selectedData.state
                         ? 'bg-green-600/20 border-2 border-green-500 text-green-400'
                         : 'bg-[#1e2129] border border-[#2e3340] text-slate-500 hover:border-slate-500'}"
                on:click={() => sendGpio(true)}
              >HIGH</button>
            </div>
          </div>

        {:else if selectedData.type === 'gpio_in'}
          <!-- ── Digital input readout ── -->
          <div class="space-y-4">
            <div class="flex items-center gap-4">
              <div class="text-5xl font-bold {selectedData.state ? 'text-green-400' : 'text-slate-500'}">
                {selectedData.state ? 'HIGH' : 'LOW'}
              </div>
              <div class="w-5 h-5 rounded-full transition-all
                          {selectedData.state ? 'bg-green-400 shadow-[0_0_10px_#4ade80]' : 'bg-slate-700'}">
              </div>
            </div>
            <p class="text-xs text-slate-600">Read-only — digital inputs cannot be overridden.</p>
          </div>

        {:else if selectedData.type === 'encoder'}
          <!-- ── Encoder readout + reset ── -->
          <div class="space-y-6 max-w-sm">
            <div class="grid grid-cols-2 gap-4">
              <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-4">
                <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-1">Count</div>
                <div class="text-3xl font-bold tabular-nums text-violet-400">
                  {(selectedData.count ?? 0).toLocaleString()}
                </div>
                <div class="text-xs text-slate-600 mt-0.5">ticks</div>
              </div>
              <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-4">
                <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-1">Velocity</div>
                <div class="text-3xl font-bold tabular-nums text-violet-400">
                  {((selectedData.velocity ?? 0) / 10).toFixed(1)}
                </div>
                <div class="text-xs text-slate-600 mt-0.5">ticks/s</div>
              </div>
            </div>

            <button
              class="px-4 py-2 rounded bg-violet-600/20 border border-violet-500/40
                     text-violet-400 text-sm font-semibold hover:bg-violet-600/30 transition-colors"
              on:click={resetEncoder}
            >
              Reset Count to Zero
            </button>
          </div>

        {:else if selectedData.type === 'ultrasonic'}
          <!-- ── Ultrasonic readout ── -->
          <div class="space-y-4 max-w-xs">
            <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-5">
              <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Distance</div>
              {#if selectedData.valid}
                <div class="text-5xl font-bold tabular-nums text-cyan-400">
                  {(selectedData.distance_mm / 10).toFixed(1)}
                </div>
                <div class="text-sm text-slate-500 mt-1">centimeters</div>
              {:else}
                <div class="text-3xl font-bold text-red-400">Out of range</div>
                <div class="text-xs text-slate-600 mt-1">Nothing detected within 2–400 cm</div>
              {/if}
            </div>
            <p class="text-xs text-slate-600">Read-only — ultrasonic sensors are inputs only.</p>
          </div>

        {:else if selectedData.type === 'vl53l0x'}
          <!-- ── VL53L0X ToF readout ── -->
          <div class="space-y-4 max-w-xs">
            <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-5">
              <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Distance</div>
              {#if selectedData.valid}
                <div class="text-5xl font-bold tabular-nums text-teal-400">
                  {(selectedData.distance_mm / 10).toFixed(1)}
                </div>
                <div class="text-sm text-slate-500 mt-1">centimeters</div>
                <div class="text-xs text-slate-600 mt-2">{selectedData.distance_mm} mm</div>
              {:else}
                <div class="text-3xl font-bold text-red-400">Out of range</div>
                <div class="text-xs text-slate-600 mt-1">Nothing detected within 2–200 cm</div>
              {/if}
            </div>
            <p class="text-xs text-slate-600">
              VL53L0X auto-detected on I²C (GP4 SDA / GP5 SCL). Read-only.
            </p>
          </div>

        {:else if selectedData.type === 'tfluna' || selectedData.type === 'tfmini'}
          <!-- ── TF-Luna / TF-Mini readout ── -->
          <div class="space-y-3 max-w-xs">
            <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-5">
              <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Distance</div>
              {#if selectedData.valid}
                <div class="text-5xl font-bold tabular-nums text-sky-400">
                  {(selectedData.distance_cm ?? 0).toFixed(0)}
                </div>
                <div class="text-sm text-slate-500 mt-1">centimeters</div>
              {:else}
                <div class="text-3xl font-bold text-red-400">Out of range</div>
                <div class="text-xs text-slate-600 mt-1">
                  {selectedData.type === 'tfluna' ? 'Range: 0.2–800 cm' : 'Range: 0.3–1200 cm'}
                </div>
              {/if}
            </div>

            <div class="grid grid-cols-2 gap-2">
              <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-3">
                <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-1">Strength</div>
                <div class="text-lg font-bold tabular-nums {(selectedData.strength ?? 0) >= 100 ? 'text-emerald-400' : 'text-red-400'}">
                  {selectedData.strength ?? '—'}
                </div>
                <div class="text-[10px] text-slate-600">≥100 = reliable</div>
              </div>

              {#if selectedData.type === 'tfluna'}
                <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-3">
                  <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-1">Chip Temp</div>
                  <div class="text-lg font-bold tabular-nums text-slate-300">
                    {selectedData.temperature != null ? selectedData.temperature.toFixed(1) + ' °C' : '—'}
                  </div>
                  <div class="text-[10px] text-slate-600">sensor die temp</div>
                </div>
              {/if}
            </div>

            <p class="text-xs text-slate-600">Read-only — configure this port in student code with <span class="font-mono">robot.{selectedData.type}()</span>.</p>
          </div>

        {:else}
          <!-- Fallback for uart / i2c / other -->
          <div class="flex flex-col gap-2 text-slate-600">
            <span class="text-sm">No controls available for this port type.</span>
          </div>
        {/if}

        <!-- Change Type footer — not shown for the dedicated I²C port (auto-detected) -->
        {#if selectedData && !configFinalized && !reconfiguring && selectedId !== 16}
          <div class="mt-6 pt-4 border-t border-[#2e3340]">
            <p class="text-[11px] text-slate-600 mb-2">Need a different device type for this port?</p>
            <button
              class="px-3 py-1.5 rounded text-xs font-semibold bg-[#1e2129] border border-[#2e3340]
                     text-slate-400 hover:border-slate-500 hover:text-slate-300 transition-colors"
              on:click={() => reconfiguring = true}
            >Change Type…</button>
          </div>
        {/if}

      </div>
    {/if}

  </div>
</div>

<style>
  input[type='range']::-webkit-slider-thumb {
    appearance: none;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #60a5fa;
    cursor: pointer;
    box-shadow: 0 0 4px rgba(96, 165, 250, 0.5);
  }
  input[type='range'].accent-amber-400::-webkit-slider-thumb {
    background: #fbbf24;
    box-shadow: 0 0 4px rgba(251, 191, 36, 0.5);
  }
</style>
