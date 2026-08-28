<script>
  /**
   * PortsTab – port list + manual override / live readout panel.
   *
   * Left sidebar: S/D physical ports. Right sidebar: I²C, UART (D6/D7 in
   * UART mode), and PCA9685 expansion channels. The center is split into two
   * independent detail panels, one driven by each sidebar's selection.
   */
  import { ports, robotState, selectedPortId, selectedPcaChannelId } from '../lib/stores.js';
  import { send } from '../lib/ws.js';
  import PortDetailPanel from './PortDetailPanel.svelte';
  import {
    SINGLE, DUAL, UART_TYPES, isUartCapable,
    isMotor, deviceLabel, dotColor, liveValue, servoRangeOf, pulseToAngle, servoPresets,
  } from '../lib/ports.js';

  $: dualRight = DUAL.filter((p) => isUartCapable(p.id) && UART_TYPES.has($ports[p.id]?.type));

  // ── Independent left/right selections ─────────────────────────────────────────
  let leftSelectedId = null;   // S/D ports (excluding D6/D7 while in UART mode)
  let rightSelectedId = null;  // I²C (16), IMU (17), or D6/D7 while in UART mode
  let rightSelectedPcaChannel = null;
  let pcaCalibrating = false;

  function selectLeft(id) {
    leftSelectedId = id;
  }

  function selectRight(id) {
    rightSelectedId = id;
    rightSelectedPcaChannel = null;
    pcaCalibrating = false;
    pcaPairPicking = false;
  }

  // Auto-select a port when navigating here from the overview port grid.
  let _lastHandled = null;
  $: if ($selectedPortId !== null && $selectedPortId !== _lastHandled) {
    _lastHandled = $selectedPortId;
    const id = $selectedPortId;
    if (id === 16 || id === 17 || (isUartCapable(id) && UART_TYPES.has($ports[id]?.type))) {
      selectRight(id);
    } else {
      selectLeft(id);
    }
    selectedPortId.set(null);
  }

  // Auto-select a PCA9685 channel when navigating here from the overview grid.
  let _lastHandledPca = null;
  $: if ($selectedPcaChannelId !== null && $selectedPcaChannelId !== _lastHandledPca) {
    _lastHandledPca = $selectedPcaChannelId;
    selectPcaChannel($selectedPcaChannelId);
    selectedPcaChannelId.set(null);
  }

  // ── Global reset / stop ────────────────────────────────────────────────────────
  let confirmReset = false;

  function doResetPorts() {
    send({ cmd: 'reset_ports' });
    confirmReset = false;
  }

  let leftPanel, rightPanel;

  function stopAll() {
    send({ cmd: 'stop_all' });
    // The daemon stops continuous-mode servos with an explicit neutral pulse,
    // but that doesn't touch any of these components' local slider state —
    // reset them here so the sliders visibly reflect the stop.
    leftPanel?.resetContinuousServoDisplay?.();
    rightPanel?.resetContinuousServoDisplay?.();
    if (selectedPcaData?.type === 'servo' && selectedPcaData?.gobilda_mode === 'continuous') {
      pcaServoAngle = 0;
    }
  }

  // ── PCA9685 expansion channels ────────────────────────────────────────────────
  const PCA_CHANNELS = Array.from({ length: 16 }, (_, i) => ({ id: i, label: `P${i}` }));

  let pcaCalibratePort = 0;     // which S-port (0–7) is wired to PCA channel 0
  let pcaCalibRunning = false;
  let pcaMotorSpeed = 0;
  let pcaServoAngle = 150;
  let pcaRangeEditing = false;
  let pcaPairPicking = false;   // choosing the direction-channel partner for a new pair
  let pcaSrMinAngle = 0, pcaSrMaxAngle = 300, pcaSrMinPulse = 500, pcaSrMaxPulse = 2500;
  let pcaModePending = null;    // mode staged for confirmation ('servo'|'motor'), or null

  $: pcaState = $robotState?.pca9685 ?? { present: false, channels: {}, mode: 'servo' };
  $: selectedPcaData = rightSelectedPcaChannel !== null
    ? (pcaState.channels?.[String(rightSelectedPcaChannel)] ?? null)
    : null;
  $: pcaSr = servoRangeOf(selectedPcaData);
  $: pcaServoUnit = selectedPcaData?.gobilda_mode === 'continuous' ? '%' : '°';

  // Detect calibration completion: daemon clears last_calibration before starting,
  // then sets it to the result dict when done. Watching for non-null is reliable.
  $: if (pcaCalibRunning && pcaState.last_calibration != null) {
    pcaCalibRunning = false;
  }

  function selectPcaChannel(ch) {
    rightSelectedId = null;
    rightSelectedPcaChannel = ch;
    pcaCalibrating = false;
    pcaPairPicking = false;
    const d = pcaState.channels?.[String(ch)];
    if (d?.type && isMotor(d.type)) pcaMotorSpeed = 0;
    if (d?.type === 'servo') {
      const r = servoRangeOf(d);
      pcaServoAngle = +pulseToAngle(d.pulse_us ?? 1500, r).toFixed(1);
      pcaServoAngle = Math.max(r.minAngle, Math.min(r.maxAngle, pcaServoAngle));
    }
  }

  function resetPcaChannel() {
    if (rightSelectedPcaChannel === null) return;
    send({ cmd: 'pca_reset_channel', channel: rightSelectedPcaChannel });
  }

  function openCalibration() {
    rightSelectedId = null;
    rightSelectedPcaChannel = null;
    pcaCalibrating = true;
    pcaModePending = null;
  }

  function runCalibration() {
    pcaCalibRunning = true;
    send({ cmd: 'pca_calibrate', pico_port: pcaCalibratePort });
  }

  // Frequency is chip-wide on the PCA9685 (no per-channel rate), so a mode
  // switch resets every configured channel — stage it behind a confirm step
  // whenever there's something to lose, skip the extra click otherwise.
  function requestPcaMode(mode) {
    if (mode === pcaState.mode) return;
    const hasChannels = Object.keys(pcaState.channels ?? {}).length > 0;
    if (hasChannels) {
      pcaModePending = mode;
    } else {
      send({ cmd: 'pca_set_mode', mode });
    }
  }

  function confirmPcaMode() {
    send({ cmd: 'pca_set_mode', mode: pcaModePending });
    pcaModePending = null;
  }

  function cancelPcaMode() {
    pcaModePending = null;
  }

  function configurePcaChannel(type) {
    if (rightSelectedPcaChannel === null) return;
    send({ cmd: 'pca_configure', channel: rightSelectedPcaChannel, type });
  }

  // Binds this channel (as the magnitude/PWM line) to another unconfigured
  // channel (as the direction line) — see pca_pair_channels in daemon/api.py.
  function pairPcaChannel(partnerId) {
    if (rightSelectedPcaChannel === null) return;
    send({ cmd: 'pca_pair_channels', channel_a: rightSelectedPcaChannel, channel_b: partnerId });
    pcaPairPicking = false;
  }

  function sendPcaMotor(pct) {
    pcaMotorSpeed = Math.max(-100, Math.min(100, pct));
    const cmd = selectedPcaData?.type === 'motor_sm_pair' ? 'pca_set_pair_motor' : 'pca_set_motor';
    send({ cmd, channel: rightSelectedPcaChannel, value_pct: pcaMotorSpeed });
  }

  function sendPcaServo(deg) {
    const lo = Math.min(pcaSr.minAngle, pcaSr.maxAngle), hi = Math.max(pcaSr.minAngle, pcaSr.maxAngle);
    pcaServoAngle = Math.max(lo, Math.min(hi, deg));
    send({ cmd: 'pca_set_servo', channel: rightSelectedPcaChannel, angle_deg: pcaServoAngle });
  }

  // Unlike gobilda_set_mode on an S-port, there's no serial line from a PCA9685
  // channel back to the servo — this only updates the daemon's bookkeeping
  // (which units/range to use, and whether Stop All should neutral-pulse it).
  // No physical reprogram happens, so there's nothing to stage behind a
  // separate "Program" action — the toggle takes effect immediately.
  function sendPcaGobildaMode(mode) {
    send({ cmd: 'pca_set_gobilda_mode', channel: rightSelectedPcaChannel, mode });
    // Local display only, so the readout doesn't keep showing a stale
    // positional-degree value once the unit switches to % (or vice versa).
    pcaServoAngle = mode === 'continuous' ? 0 : 150;
  }

  function openPcaRange() {
    pcaSrMinAngle = pcaSr.minAngle; pcaSrMaxAngle = pcaSr.maxAngle;
    pcaSrMinPulse = pcaSr.minPulse; pcaSrMaxPulse = pcaSr.maxPulse;
    pcaRangeEditing = true;
  }

  function applyPcaRange() {
    // Continuous-mode servos only accept a 900–2100 µs pulse (1500 = stop);
    // clamp so the manual range editor can't push a positional-style pulse
    // into a channel that's currently wired up as continuous, or vice versa.
    const continuous = selectedPcaData?.gobilda_mode === 'continuous';
    const [loA, hiA] = continuous ? [-100, 100] : [0, 300];
    const [loP, hiP] = continuous ? [900, 2100] : [500, 2500];
    const minAngle = Math.max(loA, Math.min(hiA, pcaSrMinAngle));
    const maxAngle = Math.max(loA, Math.min(hiA, pcaSrMaxAngle));
    const minPulse = Math.max(loP, Math.min(hiP, pcaSrMinPulse));
    const maxPulse = Math.max(loP, Math.min(hiP, pcaSrMaxPulse));
    send({ cmd: 'set_pca_servo_range', channel: rightSelectedPcaChannel,
           min_angle: minAngle, max_angle: maxAngle,
           min_pulse_us: minPulse, max_pulse_us: maxPulse });
    pcaServoAngle = (minAngle + maxAngle) / 2;
    pcaRangeEditing = false;
  }
</script>

<div class="flex h-full overflow-hidden">

  <!-- ── Port list (left column) ── -->
  <div class="w-52 flex-shrink-0 flex flex-col border-r border-[#2e3340] bg-[#1a1d26] overflow-hidden">
    <div class="h-10 flex items-center px-3 border-b border-[#2e3340] flex-shrink-0">
      <span class="text-[10px] font-bold uppercase tracking-widest text-slate-500">Ports</span>
    </div>

    <div class="flex-1 overflow-y-auto min-h-0">
      <!-- Single-pin section -->
      <div class="px-2 pt-2 pb-1">
        <div class="text-[9px] text-slate-700 uppercase tracking-widest px-1 mb-1">Single-pin S0–S7</div>
        {#each SINGLE as p}
          {@const d = $ports[p.id]}
          <button
            class="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition-colors mb-px
                   {leftSelectedId === p.id
                     ? 'bg-[#252932] ring-1 ring-[#3e4455]'
                     : 'hover:bg-[#1e2129]'}"
            on:click={() => selectLeft(p.id)}
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

      <!-- Divider -->
      <div class="border-t border-[#2e3340] mx-2 my-1"></div>

      <!-- Dual-pin section -->
      <div class="px-2 pb-2">
        <div class="text-[9px] text-slate-700 uppercase tracking-widest px-1 mb-1">Dual-pin D0–D7</div>
        {#each DUAL as p}
          {@const d = $ports[p.id]}
          {@const isUartElsewhere = isUartCapable(p.id) && UART_TYPES.has(d?.type)}
          {#if isUartElsewhere}
            <div
              class="w-full flex items-center gap-2 px-2 py-1.5 rounded mb-px opacity-40 cursor-not-allowed"
              title="{p.label} is configured as {deviceLabel(d.type)} — see the I²C & UART panel"
            >
              <span class="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded flex-shrink-0
                           bg-slate-700/60 text-slate-400">{p.label}</span>
              <span class="text-[11px] text-slate-600 italic truncate">UART → right panel</span>
            </div>
          {:else}
            <button
              class="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition-colors mb-px
                     {leftSelectedId === p.id
                       ? 'bg-[#252932] ring-1 ring-[#3e4455]'
                       : 'hover:bg-[#1e2129]'}"
              on:click={() => selectLeft(p.id)}
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
          {/if}
        {/each}
      </div>
    </div>
  </div>

  <!-- ── Detail / control panel (center, split) ── -->
  <div class="flex-1 min-w-0 flex flex-col overflow-hidden bg-[#161920]">

    <!-- Shared toolbar -->
    <div class="h-10 flex items-center justify-center gap-2 px-3 border-b border-[#2e3340] flex-shrink-0 bg-[#1a1d26]">
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

    <!-- Split body -->
    <div class="flex-1 flex overflow-hidden">

      <!-- Left half — driven by the S/D sidebar -->
      <div class="flex-1 min-w-0 flex flex-col overflow-hidden border-r border-[#2e3340]">
        <PortDetailPanel bind:this={leftPanel} portId={leftSelectedId} emptyMessage="Select an S or D port" />
      </div>

      <!-- Right half — driven by the I²C / UART / PCA9685 sidebar -->
      <div class="flex-1 min-w-0 flex flex-col overflow-hidden">
        {#if pcaCalibrating}
          <!-- ── PCA9685 Calibration Wizard ── -->
          <div class="flex-1 overflow-y-auto p-6">
            <div class="max-w-md space-y-6">
              <div>
                <div class="flex items-center gap-3 mb-1">
                  <span class="text-sm font-bold text-purple-300">PCA9685 Settings</span>
                  <button
                    class="ml-auto text-xs text-slate-500 hover:text-slate-300 transition-colors"
                    on:click={() => pcaCalibrating = false}
                  >✕ Close</button>
                </div>
              </div>

              <div class="space-y-3">
                <div>
                  <p class="text-[11px] text-slate-400 font-semibold">PWM Mode</p>
                  <p class="text-xs text-slate-500 leading-relaxed">
                    All 16 channels share one PWM frequency — there's no per-channel rate on this
                    chip. <span class="text-slate-400">Servo mode</span> (50 Hz) is the RC servo/ESC
                    standard. <span class="text-slate-400">Motor mode</span> (~1 kHz) is for a plain
                    PWM+DIR driver (e.g. a paired sign-magnitude motor) — a student needing an RC
                    servo can still use an S-port instead.
                  </p>
                </div>
                <div class="flex items-center gap-2">
                  <button
                    class="px-3 py-1.5 rounded text-xs font-semibold transition-all border
                           {pcaState.mode !== 'motor'
                             ? 'bg-amber-600/20 border-amber-500/50 text-amber-300'
                             : 'bg-[#161920] border-[#2e3340] text-slate-500 hover:border-slate-500 hover:text-slate-300'}"
                    on:click={() => requestPcaMode('servo')}
                  >Servo Mode · 50 Hz</button>
                  <button
                    class="px-3 py-1.5 rounded text-xs font-semibold transition-all border
                           {pcaState.mode === 'motor'
                             ? 'bg-blue-600/20 border-blue-500/50 text-blue-300'
                             : 'bg-[#161920] border-[#2e3340] text-slate-500 hover:border-slate-500 hover:text-slate-300'}"
                    on:click={() => requestPcaMode('motor')}
                  >Motor Mode · ~1 kHz</button>
                </div>
                {#if pcaModePending}
                  <div class="border border-amber-500/30 rounded-lg p-3 bg-amber-900/10 space-y-2">
                    <p class="text-xs text-amber-300">
                      Switching to {pcaModePending === 'motor' ? 'Motor' : 'Servo'} mode resets every
                      configured PCA9685 channel (P0–P15) — frequency is chip-wide, so existing
                      channels' programming won't mean the same thing afterward.
                    </p>
                    <div class="flex gap-2">
                      <button
                        class="px-3 py-1.5 rounded text-xs font-semibold bg-amber-600/30 border
                               border-amber-500/50 text-amber-300 hover:bg-amber-600/50 transition-colors"
                        on:click={confirmPcaMode}
                      >Confirm</button>
                      <button
                        class="px-3 py-1.5 rounded text-xs text-slate-500 border border-[#2e3340]
                               hover:text-slate-300 transition-colors"
                        on:click={cancelPcaMode}
                      >Cancel</button>
                    </div>
                  </div>
                {/if}
              </div>

              <div>
                <p class="text-sm font-bold text-purple-300 mb-1">Oscillator Calibration</p>
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

        {:else if rightSelectedPcaChannel !== null}
          <!-- ── PCA9685 channel detail ── -->
          <div class="flex items-center gap-3 px-5 py-3 border-b border-[#2e3340] flex-shrink-0 bg-[#1a1d26]">
            <span class="text-[11px] font-bold font-mono px-2 py-1 rounded bg-purple-900/40 text-purple-300">
              P{rightSelectedPcaChannel}
            </span>
            {#if selectedPcaData}
              <span class="text-sm font-semibold {isMotor(selectedPcaData.type) ? 'text-blue-400' : 'text-amber-400'}">
                {isMotor(selectedPcaData.type) ? 'Motor' : 'Servo'}
              </span>
              {#if selectedPcaData.type === 'motor_sm_pair'}
                <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-900/30 text-blue-400">
                  PWM · DIR on P{selectedPcaData.partner}
                </span>
              {/if}
              <span class="text-xs text-slate-600">PCA9685 channel {rightSelectedPcaChannel}</span>
            {:else}
              <span class="text-sm text-slate-600 italic">not configured</span>
            {/if}
            <div class="ml-auto flex items-center gap-2">
              {#if selectedPcaData}
                <button
                  class="px-3 py-1 rounded text-xs font-semibold bg-[#1e2129] text-slate-400
                         border border-[#2e3340] hover:border-red-600/40 hover:text-red-400 transition-colors"
                  on:click={resetPcaChannel}
                >Reset Port</button>
              {/if}
              <button
                class="px-3 py-1 rounded text-xs font-semibold bg-red-600/20 text-red-400
                       border border-red-600/30 hover:bg-red-600/40 transition-colors"
                on:click={() => sendPcaMotor(0)}
              >Stop</button>
            </div>
          </div>

          <div class="flex-1 overflow-y-auto p-6">
            {#if !selectedPcaData}
              <!-- Unconfigured PCA channel -->
              <div class="max-w-sm space-y-5">
                {#if !pcaPairPicking}
                  <div>
                    <p class="text-sm font-semibold text-slate-300 mb-1">Choose a device type</p>
                    <p class="text-xs text-slate-600">
                      {pcaState.mode === 'motor'
                        ? 'Motor mode is on (~1 kHz) — RC servo/ESC signals need 50 Hz, so only the paired sign-magnitude motor is available. Switch to Servo mode for RC motor/servo signals.'
                        : 'PCA9685 only supports 50 Hz outputs (servo / RC ESC).'}
                    </p>
                  </div>
                  <div class="flex gap-2 flex-wrap">
                    {#if pcaState.mode !== 'motor'}
                      {#each [['motor_servo_signal', 'Motor', 'RC ESC / servo signal'], ['servo', 'Servo', 'Standard servo']] as [id, label, sub]}
                        <button
                          class="flex flex-col items-start px-3 py-2 rounded-lg border transition-all text-left
                                 bg-[#1e2129] border-[#2e3340] text-slate-400 hover:border-blue-500/60 hover:text-blue-300"
                          on:click={() => configurePcaChannel(id)}
                        >
                          <span class="text-xs font-semibold leading-tight">{label}</span>
                          <span class="text-[10px] text-slate-600 leading-tight mt-0.5">{sub}</span>
                        </button>
                      {/each}
                    {/if}
                    <button
                      class="flex flex-col items-start px-3 py-2 rounded-lg border transition-all text-left
                             bg-[#1e2129] border-[#2e3340] text-slate-400 hover:border-blue-500/60 hover:text-blue-300"
                      on:click={() => pcaPairPicking = true}
                    >
                      <span class="text-xs font-semibold leading-tight">Motor (Paired)</span>
                      <span class="text-[10px] text-slate-600 leading-tight mt-0.5">PWM channel + DIR channel</span>
                    </button>
                  </div>
                {:else}
                  <div>
                    <p class="text-sm font-semibold text-slate-300 mb-1">Pick the DIR channel</p>
                    <p class="text-xs text-slate-600">
                      P{rightSelectedPcaChannel} becomes the <span class="text-slate-400 font-semibold">PWM</span> channel
                      — a signal proportional to |speed| — wire it to your driver's PWM/magnitude input.
                      The channel you pick here becomes the <span class="text-slate-400 font-semibold">DIR</span> channel
                      — a fixed HIGH/LOW level, not a PWM signal — wire it to your driver's DIR input.
                    </p>
                  </div>
                  <div class="grid grid-cols-4 gap-1.5">
                    {#each PCA_CHANNELS as c}
                      {@const isSelf = c.id === rightSelectedPcaChannel}
                      {@const isOccupied = !isSelf && !!pcaState.channels?.[String(c.id)]}
                      {#if isSelf}
                        <div
                          class="px-2 py-1.5 rounded text-xs font-mono border border-blue-500/40
                                 bg-blue-900/20 text-blue-400 text-center cursor-not-allowed leading-tight"
                          title="P{c.id} is already selected as the PWM channel — pick a different one for DIR"
                        >
                          {c.label}
                          <span class="block text-[8px] text-blue-500/70">PWM · selected</span>
                        </div>
                      {:else if isOccupied}
                        <div
                          class="px-2 py-1.5 rounded text-xs font-mono border border-[#2e3340]
                                 bg-[#161920] text-slate-700 text-center cursor-not-allowed opacity-60"
                          title="P{c.id} is already configured — reset it first to use it here"
                        >{c.label}</div>
                      {:else}
                        <button
                          class="px-2 py-1.5 rounded text-xs font-mono bg-[#1e2129] border border-[#2e3340]
                                 text-slate-400 hover:border-blue-500/60 hover:text-blue-300 transition-colors"
                          on:click={() => pairPcaChannel(c.id)}
                        >{c.label}</button>
                      {/if}
                    {/each}
                  </div>
                  <button
                    class="text-xs text-slate-500 hover:text-slate-300 transition-colors"
                    on:click={() => pcaPairPicking = false}
                  >← Back</button>
                {/if}
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
                <div class="flex justify-center">
                  <div class="flex flex-col items-center gap-2 w-full max-w-[15rem]">
                    <button
                      class="w-full py-2.5 rounded text-sm font-bold bg-slate-700 border border-slate-600
                             text-slate-200 hover:bg-slate-600 transition-colors"
                      on:click={() => sendPcaMotor(0)}>STOP</button>

                    <div class="grid grid-cols-2 gap-x-3 gap-y-2 w-full">
                      {#each [25, 50, 75, 100] as mag}
                        <button
                          class="py-2.5 rounded text-sm font-mono bg-[#1e2129] border border-[#2e3340]
                                 text-red-400 hover:bg-red-900/20 hover:border-red-600/40 transition-colors"
                          on:click={() => sendPcaMotor(-mag)}>−{mag}%</button>
                        <button
                          class="py-2.5 rounded text-sm font-mono bg-[#1e2129] border border-[#2e3340]
                                 text-blue-400 hover:bg-blue-900/20 hover:border-blue-600/40 transition-colors"
                          on:click={() => sendPcaMotor(mag)}>+{mag}%</button>
                      {/each}
                    </div>
                  </div>
                </div>
                {#if selectedPcaData.type === 'motor_sm_pair'}
                  <div class="flex items-center gap-2 text-xs">
                    <span class="text-slate-500">DIR (P{selectedPcaData.partner}):</span>
                    <span class="font-mono font-semibold px-1.5 py-0.5 rounded
                                 {pcaMotorSpeed >= 0 ? 'text-blue-400 bg-blue-900/20' : 'text-red-400 bg-red-900/20'}">
                      {pcaMotorSpeed >= 0 ? 'HIGH (forward)' : 'LOW (reverse)'}
                    </span>
                  </div>
                  <p class="text-[11px] text-slate-600">
                    Sign-magnitude pair: P{rightSelectedPcaChannel} (PWM) outputs a 0–100% duty cycle
                    proportional to |speed| — not an RC servo pulse — for a plain PWM+DIR driver input
                    (e.g. Cytron MDD10A). P{selectedPcaData.partner} (DIR) outputs a fixed HIGH or LOW
                    level — not a pulse — via the PCA9685's full-on/full-off mode. Wire it to your
                    driver's DIR input.
                  </p>
                {:else}
                  <p class="text-[11px] text-slate-600">RC ESC protocol: 1500 µs = stop, 1100 µs = full reverse, 1900 µs = full forward.</p>
                {/if}
              </div>

            {:else if selectedPcaData.type === 'servo'}
              <!-- PCA servo control -->
              <div class="max-w-lg space-y-6">
                <div class="flex items-baseline gap-3">
                  <span class="text-4xl font-bold tabular-nums text-amber-400">{pcaServoAngle.toFixed(1)}{pcaServoUnit}</span>
                  <span class="text-sm text-slate-500">{pcaServoUnit === '%' ? 'power' : 'angle'}</span>
                </div>
                <div class="space-y-2">
                  <div class="flex justify-between text-xs text-slate-500">
                    <span>{pcaSr.minAngle}{pcaServoUnit}</span>
                    <span class="font-semibold text-slate-300 tabular-nums">{pcaServoAngle.toFixed(1)}{pcaServoUnit}</span>
                    <span>{pcaSr.maxAngle}{pcaServoUnit}</span>
                  </div>
                  <input
                    type="range" min={Math.min(pcaSr.minAngle, pcaSr.maxAngle)} max={Math.max(pcaSr.minAngle, pcaSr.maxAngle)} step="0.5"
                    value={pcaServoAngle}
                    class="w-full h-2 rounded-full appearance-none cursor-pointer
                           bg-gradient-to-r from-amber-800/40 via-amber-600/20 to-amber-800/40 accent-amber-400"
                    on:input={(e) => sendPcaServo(Number(e.target.value))}
                  />
                </div>
                <div class="flex gap-1.5 flex-wrap justify-center">
                  {#each servoPresets(pcaSr, pcaServoUnit) as [v, label]}
                    <button class="px-2 py-1 rounded text-xs font-mono bg-[#1e2129] border border-[#2e3340]
                                   text-amber-400 hover:bg-amber-900/20 hover:border-amber-600/40 transition-colors"
                      on:click={() => sendPcaServo(v)}>{label}</button>
                  {/each}
                </div>
                <div class="space-y-2">
                  <button
                    class="w-full flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors
                           {pcaRangeEditing
                             ? 'bg-amber-900/10 border-amber-500/30 text-amber-400'
                             : 'bg-[#1e2129] border-[#2e3340] text-slate-400 hover:border-amber-500/40 hover:text-amber-400'}"
                    on:click={() => pcaRangeEditing ? (pcaRangeEditing = false) : openPcaRange()}
                  >
                    <svg class="w-3 h-3 flex-shrink-0 transition-transform {pcaRangeEditing ? 'rotate-90' : ''}"
                         viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M6 4l4 4-4 4" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    <span class="text-xs font-semibold">Range</span>
                    <span class="text-xs text-slate-500">{pcaSr.minAngle}{pcaServoUnit} – {pcaSr.maxAngle}{pcaServoUnit} · {pcaSr.minPulse}–{pcaSr.maxPulse} µs</span>
                  </button>

                  {#if pcaRangeEditing}
                  <div class="border border-amber-500/30 rounded-lg p-4 space-y-3 bg-amber-900/10">
                    <p class="text-[10px] text-slate-500">
                      {selectedPcaData?.gobilda_mode === 'continuous'
                        ? 'Continuous mode — clamped to −100–100% / 900–2100 µs.'
                        : 'Positional mode — clamped to 0–300° / 500–2500 µs.'}
                    </p>
                    <div class="grid grid-cols-2 gap-3">
                      <label class="space-y-1">
                        <span class="text-[10px] text-slate-500 uppercase tracking-wider">Min angle ({pcaServoUnit})</span>
                        <input type="number" bind:value={pcaSrMinAngle} step="1"
                          min={selectedPcaData?.gobilda_mode === 'continuous' ? -100 : 0}
                          max={selectedPcaData?.gobilda_mode === 'continuous' ? 100 : 300}
                          class="w-full bg-[#1e2129] border border-[#2e3340] rounded px-2 py-1
                                 text-xs text-slate-200 focus:outline-none focus:border-amber-500/60"/>
                      </label>
                      <label class="space-y-1">
                        <span class="text-[10px] text-slate-500 uppercase tracking-wider">Max angle ({pcaServoUnit})</span>
                        <input type="number" bind:value={pcaSrMaxAngle} step="1"
                          min={selectedPcaData?.gobilda_mode === 'continuous' ? -100 : 0}
                          max={selectedPcaData?.gobilda_mode === 'continuous' ? 100 : 300}
                          class="w-full bg-[#1e2129] border border-[#2e3340] rounded px-2 py-1
                                 text-xs text-slate-200 focus:outline-none focus:border-amber-500/60"/>
                      </label>
                      <label class="space-y-1">
                        <span class="text-[10px] text-slate-500 uppercase tracking-wider">Min pulse (µs)</span>
                        <input type="number" bind:value={pcaSrMinPulse} step="1"
                          min={selectedPcaData?.gobilda_mode === 'continuous' ? 900 : 500}
                          max={selectedPcaData?.gobilda_mode === 'continuous' ? 2100 : 2500}
                          class="w-full bg-[#1e2129] border border-[#2e3340] rounded px-2 py-1
                                 text-xs text-slate-200 focus:outline-none focus:border-amber-500/60"/>
                      </label>
                      <label class="space-y-1">
                        <span class="text-[10px] text-slate-500 uppercase tracking-wider">Max pulse (µs)</span>
                        <input type="number" bind:value={pcaSrMaxPulse} step="1"
                          min={selectedPcaData?.gobilda_mode === 'continuous' ? 900 : 500}
                          max={selectedPcaData?.gobilda_mode === 'continuous' ? 2100 : 2500}
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
                  {/if}
                </div>

                <!-- Continuous-mode flag (software only — PCA9685 has no serial link -->
                <!-- back to the servo, so this doesn't reprogram it; the servo    -->
                <!-- must already be in continuous mode). Lets Stop All Motors and -->
                <!-- the throttle-style display know to treat this channel as one.-->
                <div class="border border-slate-700/40 rounded-lg p-3 space-y-2 bg-[#1a1d26]">
                  <div class="flex items-center gap-2">
                    <span class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">GoBilda Mode</span>
                    <span class="text-[10px] text-slate-700">· continuous servos wired to this channel only</span>
                    {#if selectedPcaData?.gobilda_mode}
                      <span class="ml-auto text-[10px] font-mono
                                   {selectedPcaData.gobilda_mode === 'continuous' ? 'text-blue-400' : 'text-amber-400'}">
                        {selectedPcaData.gobilda_mode}
                      </span>
                    {/if}
                  </div>
                  <div class="flex items-center gap-2">
                    <button
                      class="px-3 py-1.5 rounded text-xs font-semibold transition-all border
                             {(selectedPcaData?.gobilda_mode ?? 'positional') === 'positional'
                               ? 'bg-amber-600/20 border-amber-500/50 text-amber-300'
                               : 'bg-[#161920] border-[#2e3340] text-slate-500 hover:border-slate-500 hover:text-slate-300'}"
                      on:click={() => sendPcaGobildaMode('positional')}
                    >Positional</button>
                    <button
                      class="px-3 py-1.5 rounded text-xs font-semibold transition-all border
                             {selectedPcaData?.gobilda_mode === 'continuous'
                               ? 'bg-blue-600/20 border-blue-500/50 text-blue-300'
                               : 'bg-[#161920] border-[#2e3340] text-slate-500 hover:border-slate-500 hover:text-slate-300'}"
                      on:click={() => sendPcaGobildaMode('continuous')}
                    >Continuous</button>
                  </div>
                </div>
              </div>
            {/if}
          </div>

        {:else}
          <PortDetailPanel bind:this={rightPanel} portId={rightSelectedId} emptyMessage="Select an I²C, UART, or PCA9685 device" />
        {/if}
      </div>
    </div>
  </div>

  <!-- ── Bus / expansion device list (right column) — mirror image of the port list ── -->
  <div class="w-52 flex-shrink-0 flex flex-col border-l border-[#2e3340] bg-[#1a1d26] overflow-hidden">
    <div class="h-10 flex items-center justify-end px-3 border-b border-[#2e3340] flex-shrink-0">
      <span class="text-[10px] font-bold uppercase tracking-widest text-slate-500">I²C &amp; UART</span>
    </div>

    <div class="flex-1 overflow-y-auto min-h-0">
      <!-- I²C port (port 16) + IMU (port 17) — shown when an I²C sensor is detected -->
      {#if $ports[16]}
        <div class="px-2 pt-2 pb-2">
          <div class="text-[9px] text-slate-700 uppercase tracking-widest px-1 mb-1 text-right">I²C</div>
          <button
            class="w-full flex flex-row-reverse items-center gap-2 px-2 py-1.5 rounded text-right transition-colors mb-px
                   {rightSelectedId === 16
                     ? 'bg-[#252932] ring-1 ring-[#3e4455]'
                     : 'hover:bg-[#1e2129]'}"
            on:click={() => selectRight(16)}
          >
            <span class="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded flex-shrink-0
                         bg-slate-700/60 text-slate-400">I²C</span>
            <span class="w-1.5 h-1.5 rounded-full flex-shrink-0 {dotColor($ports[16].type)}"></span>
            <span class="text-[11px] text-slate-300 truncate">{deviceLabel($ports[16].type)}</span>
            {#if liveValue($ports[16])}
              <span class="text-[10px] font-mono text-slate-500 mr-auto flex-shrink-0">
                {liveValue($ports[16])}
              </span>
            {/if}
          </button>
          <button
            class="w-full flex flex-row-reverse items-center gap-2 px-2 py-1.5 rounded text-right transition-colors mb-px
                   {rightSelectedId === 17
                     ? 'bg-[#252932] ring-1 ring-[#3e4455]'
                     : 'hover:bg-[#1e2129]'}"
            on:click={() => selectRight(17)}
          >
            <span class="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded flex-shrink-0
                         bg-slate-700/60 text-slate-400">IMU</span>
            <span class="w-1.5 h-1.5 rounded-full flex-shrink-0 {dotColor($ports[17]?.type)}"></span>
            <span class="text-[11px] text-slate-300 truncate">{deviceLabel($ports[17]?.type)}</span>
            {#if liveValue($ports[17])}
              <span class="text-[10px] font-mono text-slate-500 mr-auto flex-shrink-0">
                {liveValue($ports[17])}
              </span>
            {/if}
          </button>
        </div>
        <div class="border-t border-[#2e3340] mx-2 my-1"></div>
      {/if}

      <!-- UART section — D6/D7 when configured for a UART-based protocol; hidden entirely when none are -->
      {#if dualRight.length > 0}
        <div class="px-2 pt-2 pb-1">
          <div class="text-[9px] text-slate-700 uppercase tracking-widest px-1 mb-1 text-right">UART D6–D7</div>
          {#each dualRight as p}
            {@const d = $ports[p.id]}
            <button
              class="w-full flex flex-row-reverse items-center gap-2 px-2 py-1.5 rounded text-right transition-colors mb-px
                     {rightSelectedId === p.id
                       ? 'bg-[#252932] ring-1 ring-[#3e4455]'
                       : 'hover:bg-[#1e2129]'}"
              on:click={() => selectRight(p.id)}
            >
              <span class="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded flex-shrink-0
                           bg-slate-700/60 text-slate-400">{p.label}</span>
              <span class="w-1.5 h-1.5 rounded-full flex-shrink-0 {dotColor(d.type)}"></span>
              <span class="text-[11px] text-slate-300 truncate">{deviceLabel(d.type)}</span>
              {#if liveValue(d)}
                <span class="text-[10px] font-mono text-slate-500 mr-auto flex-shrink-0">
                  {liveValue(d)}
                </span>
              {/if}
            </button>
          {/each}
        </div>
      {/if}

      <!-- PCA9685 expansion channels (P0–P15) -->
      {#if !pcaState.present}
        <div class="border-t border-[#2e3340] mx-2 my-1"></div>
        <div class="px-3 py-1.5 flex flex-row-reverse items-center gap-1.5">
          <span class="text-[9px] text-slate-700 uppercase tracking-widest">PCA9685</span>
          <span class="mr-auto text-[8px] text-slate-700 italic">not detected</span>
        </div>
      {:else}
        <div class="border-t border-[#2e3340] mx-2 my-1"></div>
        <div class="px-2 pb-1">
          <div class="flex flex-row-reverse items-center px-1 mb-1">
            <div class="text-[9px] text-slate-700 uppercase tracking-widest leading-tight text-right">
              <div>PCA9685</div>
              <div>P0–P15</div>
            </div>
            <div class="mr-auto flex items-center gap-4">
              <button
                class="text-[8px] leading-tight text-right transition-colors cursor-pointer hover:brightness-125
                       {pcaState.mode === 'motor' ? 'text-blue-500' : 'text-amber-600/80'}"
                title="Click to change PWM mode"
                on:click={openCalibration}
              >
                <div>{pcaState.mode === 'motor' ? 'motor' : 'servo'}</div>
                <div>mode</div>
              </button>
              {#if pcaState.calibrated}
                <span class="text-[8px] text-green-600 font-semibold">calibrated</span>
              {:else}
                <button
                  class="text-[8px] text-amber-600 hover:text-amber-400 transition-colors cursor-pointer"
                  on:click={openCalibration}
                >calibrate…</button>
              {/if}
            </div>
          </div>
          {#each PCA_CHANNELS as ch}
            {@const chData = pcaState.channels?.[String(ch.id)]}
            {@const isPairDir = chData?.type === 'motor_sm_pair' && chData?.role === 'direction'}
            {#if isPairDir}
              <div
                class="w-full flex flex-row-reverse items-center gap-2 px-2 py-1.5 rounded mb-px opacity-40 cursor-not-allowed"
                title="{ch.label} is the DIR (direction) channel of a sign-magnitude pair — see P{chData.partner}, the PWM channel"
              >
                <span class="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded flex-shrink-0
                             bg-purple-900/40 text-purple-400">{ch.label}</span>
                <span class="text-[11px] text-slate-600 italic truncate">DIR → P{chData.partner}</span>
              </div>
            {:else}
              <button
                class="w-full flex flex-row-reverse items-center gap-2 px-2 py-1.5 rounded text-right transition-colors mb-px
                       {rightSelectedPcaChannel === ch.id
                         ? 'bg-[#252932] ring-1 ring-[#3e4455]'
                         : 'hover:bg-[#1e2129]'}"
                on:click={() => selectPcaChannel(ch.id)}
              >
                <span class="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded flex-shrink-0
                             bg-purple-900/40 text-purple-400">{ch.label}</span>
                {#if chData?.type}
                  <span class="w-1.5 h-1.5 rounded-full flex-shrink-0 {isMotor(chData.type) ? 'bg-blue-400' : 'bg-amber-400'}"></span>
                  <span class="text-[11px] text-slate-300 truncate">
                    {chData.type === 'motor_sm_pair' ? 'Motor · PWM' : (isMotor(chData.type) ? 'Motor' : 'Servo')}
                  </span>
                {:else}
                  <span class="text-[11px] text-slate-700 italic">empty</span>
                {/if}
              </button>
            {/if}
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
    </div>
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
