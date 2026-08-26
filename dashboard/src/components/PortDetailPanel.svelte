<script>
  /**
   * PortDetailPanel – control/readout body for a single selected port.
   * Instantiated twice by PortsTab (once per split-view half) so the S/D
   * side and the I²C/UART/PCA side can each have an independent selection.
   */
  import { ports, robotState } from '../lib/stores.js';
  import { send } from '../lib/ws.js';
  import {
    ALL_PORTS, TYPE_DEFS, isMotor, deviceLabel, accentClass,
    servoRangeOf, pulseToAngle, servoPresets,
  } from '../lib/ports.js';

  export let portId = null;
  export let emptyMessage = 'Select a port from the list';

  $: selectedData = portId !== null ? $ports[portId] : null;
  $: selectedPort = portId !== null ? ALL_PORTS.find((p) => p.id === portId) : null;

  // ── Config finalization status ────────────────────────────────────────────────
  $: configFinalized = $robotState?.config_finalized ?? false;

  $: availableTypes = TYPE_DEFS.filter((t) => {
    if (t.d7Only     && portId !== 14 && portId !== 15) return false;
    if (t.adcOnly    && ![5, 6, 7].includes(portId))    return false;
    if (t.dualOnly   && !(selectedPort?.dual))  return false;
    if (t.singleOnly &&   selectedPort?.dual)   return false;
    return true;
  });

  // pendingType: the type the user has selected in the picker but not yet sent
  let pendingType = null;

  // reconfiguring: true when the user wants to change an already-configured port
  let reconfiguring = false;

  // ── IMU mount rotation ────────────────────────────────────────────────────────
  $: imuMount       = $robotState?.imu_mount ?? { yaw: 0, pitch: 0, roll: 0, code_set: false };
  $: imuMountLocked = imuMount.code_set;

  function sendMountAngle(field, val) {
    const v = parseFloat(val);
    if (!isNaN(v)) send({ cmd: 'set_imu_mount', [field]: v });
  }

  // ── Per-port invert overrides ─────────────────────────────────────────────────
  $: portInvert       = $robotState?.port_invert       ?? {};
  $: portInvertLocked = new Set($robotState?.port_invert_locked ?? []);

  function sendPortInvert(pid, inv) {
    send({ cmd: 'set_port_invert', port: pid, inverted: inv });
  }

  // ── Control state (local; does not track live RP2040 state) ──────────────────
  let motorSpeed = 0;   // -100..+100 (%)
  let servoAngle = 150; // degrees within the port's configured range

  $: sr        = servoRangeOf(selectedData);
  $: servoUnit = selectedData?.gobilda_mode === 'continuous' ? '%' : '°';

  // Servo range config editing state
  let servoRangeEditing = false;
  let srMinAngle = 0, srMaxAngle = 300, srMinPulse = 500, srMaxPulse = 2500;
  let gobildaSwitching = false;

  // Re-initialize local UI state whenever the selected port actually changes.
  let _prevPortId;
  $: if (portId !== _prevPortId) {
    _prevPortId = portId;
    pendingType = null;
    reconfiguring = false;
    gobildaSwitching = false;
    const d = portId !== null ? $ports[portId] : null;
    if (d) {
      if (isMotor(d.type)) motorSpeed = +(d.value / 100).toFixed(1);
      if (d.type === 'servo') {
        const r = servoRangeOf(d);
        servoAngle = +pulseToAngle(d.pulse_us ?? 1500, r).toFixed(1);
        servoAngle = Math.max(r.minAngle, Math.min(r.maxAngle, servoAngle));
      }
    }
  }

  // ── Motor commands ────────────────────────────────────────────────────────────
  function sendMotor(pct) {
    motorSpeed = Math.max(-100, Math.min(100, pct));
    send({ cmd: 'set_motor', port: portId, value_pct: motorSpeed });
  }

  function onMotorSlider(e) {
    sendMotor(Number(e.target.value));
  }

  // ── Servo commands ────────────────────────────────────────────────────────────
  function sendServo(deg) {
    const lo = Math.min(sr.minAngle, sr.maxAngle), hi = Math.max(sr.minAngle, sr.maxAngle);
    servoAngle = Math.max(lo, Math.min(hi, deg));
    send({ cmd: 'set_servo', port: portId, angle_deg: servoAngle });
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
    send({ cmd: 'set_servo_range', port: portId,
           min_angle: srMinAngle, max_angle: srMaxAngle,
           min_pulse_us: srMinPulse, max_pulse_us: srMaxPulse });
    servoAngle = (srMinAngle + srMaxAngle) / 2;
    servoRangeEditing = false;
  }

  // ── GoBilda mode switch ────────────────────────────────────────────────────────
  function sendGobildaMode(mode) {
    gobildaSwitching = true;
    send({ cmd: 'gobilda_set_mode', port: portId, mode });
    setTimeout(() => {
      gobildaSwitching = false;
      servoAngle = mode === 'continuous' ? 0 : 150;
      if (mode === 'continuous') {
        // Send an explicit stop so the servo doesn't run at the last positional pulse.
        // angle_deg 0 maps to 1500 µs (center of 900–2100 µs range) = stopped.
        send({ cmd: 'set_servo', port: portId, angle_deg: 0 });
      }
    }, 700);
  }

  // ── GPIO commands ─────────────────────────────────────────────────────────────
  function sendGpio(state) {
    send({ cmd: 'set_gpio', port: portId, state });
  }

  // ── Encoder commands ──────────────────────────────────────────────────────────
  function resetEncoder() {
    send({ cmd: 'reset_encoder', port: portId });
  }

  // ── Port configure ────────────────────────────────────────────────────────────
  function configurePort() {
    if (!pendingType || portId === null) return;
    send({ cmd: 'configure_port', port: portId, type: pendingType });
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
    if (!pendingType || portId === null) return;

    const savedConfigs = ALL_PORTS
      .filter((p) => p.id !== portId && $ports[p.id]?.type)
      .map((p) => ({ port: p.id, type: $ports[p.id].type }));

    send({ cmd: 'reset_ports' });
    for (const { port, type } of savedConfigs) {
      send({ cmd: 'configure_port', port, type });
    }
    send({ cmd: 'configure_port', port: portId, type: pendingType });

    reconfiguring = false;
    pendingType = null;
  }
</script>

{#if portId === null}
  <!-- No port selected -->
  <div class="flex flex-col items-center justify-center h-full gap-3 text-slate-700">
    <svg class="w-10 h-10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
      <rect x="3" y="7" width="4" height="10" rx="1"/>
      <rect x="10" y="7" width="4" height="10" rx="1"/>
      <rect x="17" y="7" width="4" height="10" rx="1"/>
    </svg>
    <span class="text-sm">{emptyMessage}</span>
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
  </div>

  <!-- Control body -->
  <div class="flex-1 overflow-y-auto p-6">

    {#if !selectedData && portId === 17}
      <!-- IMU port — auto-detected, never user-configurable -->
      <div class="flex flex-col items-center justify-center h-full gap-3 text-slate-600">
        <svg class="w-8 h-8 text-slate-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 6v6l4 2"/>
        </svg>
        <p class="text-sm text-center text-slate-500">No IMU detected</p>
        <p class="text-xs text-slate-700 text-center leading-relaxed max-w-xs">
          The firmware probes for BNO085, BNO055, and MPU-6050 at startup.<br>
          Check that the sensor is wired to <strong class="text-slate-500">GP4 (SDA)</strong> and <strong class="text-slate-500">GP5 (SCL)</strong> and power-cycle the robot.
        </p>
      </div>

    {:else if !selectedData}
      <!-- Unconfigured — show type picker or locked message -->
      {#if configFinalized}
        <div class="flex flex-col items-center justify-center h-full gap-3 text-slate-600">
          <svg class="w-8 h-8 text-slate-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
            <rect x="5" y="11" width="14" height="10" rx="2"/>
            <path d="M8 11V7a4 4 0 0 1 8 0v4"/>
          </svg>
          <p class="text-sm text-center">Configuration is locked by student code.</p>
          <p class="text-xs text-slate-700 text-center">Click <strong class="text-slate-500">Reset All Ports</strong> above to start fresh.</p>
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
        <div class="flex flex-wrap justify-center gap-1">
          {#each [[-100, '−100%'], [-75, '−75%'], [-50, '−50%'], [-25, '−25%']] as [v, label]}
            <button
              class="px-1.5 py-1 rounded text-[10px] font-mono bg-[#1e2129] border border-[#2e3340]
                     text-red-400 hover:bg-red-900/20 hover:border-red-600/40 transition-colors"
              on:click={() => sendMotor(v)}>{label}</button>
          {/each}

          <button
            class="px-2.5 py-1 rounded text-[10px] font-bold bg-slate-700 border border-slate-600
                   text-slate-200 hover:bg-slate-600 transition-colors"
            on:click={() => sendMotor(0)}>STOP</button>

          {#each [[25, '+25%'], [50, '+50%'], [75, '+75%'], [100, '+100%']] as [v, label]}
            <button
              class="px-1.5 py-1 rounded text-[10px] font-mono bg-[#1e2129] border border-[#2e3340]
                     text-blue-400 hover:bg-blue-900/20 hover:border-blue-600/40 transition-colors"
              on:click={() => sendMotor(v)}>{label}</button>
          {/each}
        </div>

        <p class="text-[11px] text-slate-600">
          Manual commands are temporary — running student code will override them.
        </p>

        <!-- Invert toggle -->
        <label class="flex items-center gap-2 cursor-pointer {portInvertLocked.has(String(portId)) ? 'opacity-60' : ''}">
          <input
            type="checkbox"
            checked={portInvert[String(portId)] ?? false}
            disabled={portInvertLocked.has(String(portId))}
            on:change={(e) => sendPortInvert(String(portId), e.target.checked)}
            class="w-4 h-4 accent-blue-500"
          />
          <span class="text-xs text-slate-400">Invert motor direction</span>
          {#if portInvertLocked.has(String(portId))}
            <span class="text-[9px] px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-400 border border-amber-700/40">Set by code</span>
          {/if}
        </label>
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
        <div class="flex gap-2 flex-wrap justify-center">
          {#each servoPresets(sr, servoUnit) as [v, label]}
            <button
              class="px-3 py-1.5 rounded text-xs font-mono bg-[#1e2129] border border-[#2e3340]
                     text-amber-400 hover:bg-amber-900/20 hover:border-amber-600/40 transition-colors"
              on:click={() => sendServo(v)}>{label}</button>
          {/each}
        </div>

        <!-- Range configuration -->
        <div class="space-y-2">
          <button
            class="w-full flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors
                   {servoRangeEditing
                     ? 'bg-amber-900/10 border-amber-500/30 text-amber-400'
                     : 'bg-[#1e2129] border-[#2e3340] text-slate-400 hover:border-amber-500/40 hover:text-amber-400'}"
            on:click={() => servoRangeEditing ? (servoRangeEditing = false) : openServoRange()}
          >
            <svg class="w-3 h-3 flex-shrink-0 transition-transform {servoRangeEditing ? 'rotate-90' : ''}"
                 viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M6 4l4 4-4 4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span class="text-xs font-semibold">Range</span>
            <span class="text-xs text-slate-500">{sr.minAngle}{servoUnit} – {sr.maxAngle}{servoUnit} · {sr.minPulse}–{sr.maxPulse} µs</span>
          </button>

          {#if servoRangeEditing}
          <div class="border border-amber-500/30 rounded-lg p-4 space-y-3 bg-amber-900/10">
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
          {/if}
        </div>

        <!-- GoBilda dual-mode switch (S-port servos only) -->
        {#if portId !== null && portId < 8}
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

        <!-- Invert toggle -->
        <label class="flex items-center gap-2 cursor-pointer {portInvertLocked.has(String(portId)) ? 'opacity-60' : ''}">
          <input
            type="checkbox"
            checked={portInvert[String(portId)] ?? false}
            disabled={portInvertLocked.has(String(portId))}
            on:change={(e) => sendPortInvert(String(portId), e.target.checked)}
            class="w-4 h-4 accent-violet-500"
          />
          <span class="text-xs text-slate-400">Invert count direction</span>
          {#if portInvertLocked.has(String(portId))}
            <span class="text-[9px] px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-400 border border-amber-700/40">Set by code</span>
          {/if}
        </label>
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

    {:else if selectedData.type === 'ir_distance'}
      <!-- ── Sharp IR distance readout ── -->
      <div class="space-y-4 max-w-xs">
        <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-5">
          <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Distance</div>
          {#if selectedData.valid}
            <div class="text-5xl font-bold tabular-nums text-rose-400">
              {(selectedData.distance_mm / 10).toFixed(1)}
            </div>
            <div class="text-sm text-slate-500 mt-1">centimeters</div>
            <div class="text-xs text-slate-600 mt-2">{selectedData.distance_mm} mm</div>
          {:else}
            <div class="text-3xl font-bold text-red-400">Out of range</div>
            <div class="text-xs text-slate-600 mt-1">Valid range: 10–80 cm</div>
          {/if}
        </div>
        <p class="text-xs text-slate-600">
          Sharp GP2Y0A21 IR sensor on S{portId}. Read-only. Connect signal directly to S-port pin.
        </p>
      </div>

    {:else if selectedData.type === 'bno085' || selectedData.type === 'bno055'}
      <!-- ── BNO085 / BNO055 IMU readout ── -->
      <div class="space-y-3 max-w-sm">
        {#if selectedData.quaternion}
          {@const q = selectedData.quaternion}
          {@const yawRad = Math.atan2(2*(q.w*q.z + q.x*q.y), 1 - 2*(q.y*q.y + q.z*q.z))}
          {@const heading = ((yawRad * 180 / Math.PI) + 360) % 360}
          <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-5">
            <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Heading (yaw)</div>
            <div class="text-5xl font-bold tabular-nums text-indigo-400">{heading.toFixed(1)}°</div>
            <div class="text-xs text-slate-600 mt-1">0° = startup orientation</div>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-3">
              <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Quaternion</div>
              {#each [['W', q.w], ['X', q.x], ['Y', q.y], ['Z', q.z]] as [label, val]}
                <div class="flex justify-between text-[11px]">
                  <span class="text-slate-500">{label}</span>
                  <span class="font-mono text-slate-300">{val.toFixed(4)}</span>
                </div>
              {/each}
            </div>
            {#if selectedData.linear_acceleration}
              {@const a = selectedData.linear_acceleration}
              <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-3">
                <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Linear Accel (m/s²)</div>
                {#each [['X', a.x], ['Y', a.y], ['Z', a.z]] as [label, val]}
                  <div class="flex justify-between text-[11px]">
                    <span class="text-slate-500">{label}</span>
                    <span class="font-mono text-slate-300">{val.toFixed(3)}</span>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {:else}
          <div class="text-sm text-slate-500">No data yet.</div>
        {/if}
        <!-- Mount rotation -->
        <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-3 space-y-2">
          <div class="flex items-center justify-between">
            <div class="text-[10px] uppercase tracking-widest text-slate-500">Mount Rotation</div>
            {#if imuMountLocked}
              <span class="text-[9px] px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-400 border border-amber-700/40">Set by code</span>
            {/if}
          </div>
          <div class="grid grid-cols-3 gap-2">
            {#each [['Yaw (Z)', 'yaw'], ['Pitch (Y)', 'pitch'], ['Roll (X)', 'roll']] as [label, field]}
              <div class="space-y-1">
                <div class="text-[9px] text-slate-600">{label}</div>
                <input
                  type="number" min="-180" max="180" step="1"
                  value={imuMount[field] ?? 0}
                  disabled={imuMountLocked}
                  on:change={(e) => sendMountAngle(field, e.target.value)}
                  class="w-full bg-[#151820] border rounded px-2 py-1 text-xs font-mono text-slate-300
                         {imuMountLocked
                           ? 'border-slate-700/40 text-slate-500 cursor-not-allowed'
                           : 'border-[#2e3340] focus:border-indigo-500 focus:outline-none'}"
                />
              </div>
            {/each}
          </div>
          <p class="text-[9px] text-slate-600">Degrees. +X forward, +Y left, +Z up. Locked once student code calls <span class="font-mono">set_mount_rotation()</span>.</p>
        </div>
        <p class="text-xs text-slate-600">
          {selectedData.type === 'bno085' ? 'BNO085' : 'BNO055'} auto-detected on I²C (GP4 SDA / GP5 SCL). Read-only.
        </p>
      </div>

    {:else if selectedData.type === 'mpu6050'}
      <!-- ── MPU-6050 readout ── -->
      <div class="space-y-3 max-w-sm">
        {#if selectedData.acceleration && selectedData.gyro}
          {@const a = selectedData.acceleration}
          {@const g = selectedData.gyro}
          {@const mag = Math.sqrt(a.x*a.x + a.y*a.y + a.z*a.z) * 9.80665}
          <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-5">
            <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Accel magnitude</div>
            <div class="text-5xl font-bold tabular-nums text-purple-400">{mag.toFixed(2)}</div>
            <div class="text-xs text-slate-600 mt-1">m/s² (includes gravity ~9.81)</div>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-3">
              <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Acceleration (g)</div>
              {#each [['X', a.x], ['Y', a.y], ['Z', a.z]] as [label, val]}
                <div class="flex justify-between text-[11px]">
                  <span class="text-slate-500">{label}</span>
                  <span class="font-mono text-slate-300">{val.toFixed(4)}</span>
                </div>
              {/each}
            </div>
            <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-3">
              <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Gyro (°/s)</div>
              {#each [['X', g.x], ['Y', g.y], ['Z', g.z]] as [label, val]}
                <div class="flex justify-between text-[11px]">
                  <span class="text-slate-500">{label}</span>
                  <span class="font-mono text-slate-300">{val.toFixed(2)}</span>
                </div>
              {/each}
            </div>
          </div>
        {:else}
          <div class="text-sm text-slate-500">No data yet.</div>
        {/if}
        <!-- Mount rotation -->
        <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-3 space-y-2">
          <div class="flex items-center justify-between">
            <div class="text-[10px] uppercase tracking-widest text-slate-500">Mount Rotation</div>
            {#if imuMountLocked}
              <span class="text-[9px] px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-400 border border-amber-700/40">Set by code</span>
            {/if}
          </div>
          <div class="grid grid-cols-3 gap-2">
            {#each [['Yaw (Z)', 'yaw'], ['Pitch (Y)', 'pitch'], ['Roll (X)', 'roll']] as [label, field]}
              <div class="space-y-1">
                <div class="text-[9px] text-slate-600">{label}</div>
                <input
                  type="number" min="-180" max="180" step="1"
                  value={imuMount[field] ?? 0}
                  disabled={imuMountLocked}
                  on:change={(e) => sendMountAngle(field, e.target.value)}
                  class="w-full bg-[#151820] border rounded px-2 py-1 text-xs font-mono text-slate-300
                         {imuMountLocked
                           ? 'border-slate-700/40 text-slate-500 cursor-not-allowed'
                           : 'border-[#2e3340] focus:border-indigo-500 focus:outline-none'}"
                />
              </div>
            {/each}
          </div>
          <p class="text-[9px] text-slate-600">Degrees. +X forward, +Y left, +Z up. Locked once student code calls <span class="font-mono">set_mount_rotation()</span>.</p>
        </div>
        <p class="text-xs text-slate-600">
          MPU-6050 auto-detected on I²C (GP4 SDA / GP5 SCL). Read-only.
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

    {:else if selectedData.type === 'i2c'}
      <!-- ── I²C bus scan ── -->
      <div class="space-y-4 max-w-xs">
        <div class="bg-[#1e2129] rounded-lg border border-[#2e3340] p-5">
          <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-3">I²C Bus Scan</div>
          {#if selectedData.scan && selectedData.scan.length > 0}
            <div class="text-xs text-slate-400 mb-2">{selectedData.scan.length} device{selectedData.scan.length !== 1 ? 's' : ''} found</div>
            <div class="flex flex-wrap gap-2">
              {#each selectedData.scan as addr}
                <span class="font-mono text-sm px-2 py-1 rounded bg-orange-500/10 border border-orange-500/30 text-orange-400">{addr}</span>
              {/each}
            </div>
          {:else if selectedData.scan}
            <div class="text-sm text-red-400">No devices responded</div>
            <div class="text-xs text-slate-600 mt-1">Check wiring and that the sensor is powered.</div>
          {:else}
            <div class="text-sm text-slate-600 italic">Scan data not available — reflash firmware.</div>
          {/if}
        </div>
        <p class="text-xs text-slate-600">
          Scan runs once at startup. Power-cycle the robot after connecting a sensor.
        </p>
      </div>

    {:else}
      <!-- Fallback for uart / other -->
      <div class="flex flex-col gap-2 text-slate-600">
        <span class="text-sm">No controls available for this port type.</span>
      </div>
    {/if}

    <!-- Change Type footer — not shown for dedicated ports (I²C/IMU — auto-detected) -->
    {#if selectedData && !configFinalized && !reconfiguring && portId !== 16 && portId !== 17}
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
