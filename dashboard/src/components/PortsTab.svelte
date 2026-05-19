<script>
  /**
   * PortsTab – port list + manual override / live readout panel.
   *
   * Left column: compact clickable list of all port slots.
   * Right panel: context-sensitive controls (outputs) or readings (inputs).
   */
  import { ports } from '../lib/stores.js';
  import { send } from '../lib/ws.js';

  // ── Port directory ────────────────────────────────────────────────────────────
  const SINGLE = Array.from({ length: 8 }, (_, i) => ({ id: i,     label: `S${i}`, dual: false }));
  const DUAL   = Array.from({ length: 8 }, (_, i) => ({ id: i + 8, label: `D${i}`, dual: true  }));
  const ALL_PORTS = [...SINGLE, ...DUAL];

  let selectedId = null;

  $: selectedData = selectedId !== null ? $ports[selectedId] : null;
  $: selectedPort = selectedId !== null ? ALL_PORTS.find((p) => p.id === selectedId) : null;

  // ── Control state (local; does not track live RP2040 state) ──────────────────
  let motorSpeed = 0;   // -100..+100 (%)
  let servoAngle = 150;  // degrees (default center of 300° range)

  function selectPort(id) {
    selectedId = id;
    const d = $ports[id];
    if (!d) return;
    if (isMotor(d.type)) motorSpeed = +(d.value / 100).toFixed(1);
    if (d.type === 'servo') servoAngle = +(((d.pulse_us ?? 1500) - 500) / 2000 * 300).toFixed(1);
  }

  // ── Type helpers ─────────────────────────────────────────────────────────────
  const isMotor = (t) => t === 'motor_sm' || t === 'motor_lap' || t === 'motor_servo_signal';

  function deviceLabel(type) {
    if (isMotor(type)) return 'Motor';
    const m = { encoder: 'Encoder', ultrasonic: 'Ultrasonic', servo: 'Servo',
                 gpio_in: 'Digital In', gpio_out: 'Digital Out', i2c: 'I²C', uart: 'UART' };
    return m[type] ?? 'Empty';
  }

  function liveValue(d) {
    if (!d) return null;
    if (isMotor(d.type)) return `${((d.value ?? 0) / 100).toFixed(0)}%`;
    switch (d.type) {
      case 'encoder':    return `${(d.count ?? 0).toLocaleString()} cnt`;
      case 'ultrasonic': return d.valid ? `${(d.distance_mm / 10).toFixed(1)} cm` : 'OOB';
      case 'servo':      return `${(((d.pulse_us ?? 1500) - 500) / 2000 * 300).toFixed(1)}°`;
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
      servo:      'text-amber-400 border-amber-500/40',
      i2c:        'text-orange-400 border-orange-500/40',
    };
    return m[type] ?? 'text-slate-600 border-slate-700/30';
  }

  function dotColor(type) {
    if (isMotor(type))       return 'bg-blue-400';
    if (type === 'gpio_in' || type === 'gpio_out') return 'bg-green-400';
    const m = { encoder: 'bg-violet-400', ultrasonic: 'bg-cyan-400',
                 servo: 'bg-amber-400',   i2c: 'bg-orange-400' };
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
    servoAngle = Math.max(0, Math.min(300, deg));
    send({ cmd: 'set_servo', port: selectedId, angle_deg: servoAngle });
  }

  function onServoSlider(e) {
    sendServo(Number(e.target.value));
  }

  // ── GPIO commands ─────────────────────────────────────────────────────────────
  function sendGpio(state) {
    send({ cmd: 'set_gpio', port: selectedId, state });
  }

  // ── Encoder commands ──────────────────────────────────────────────────────────
  function resetEncoder() {
    send({ cmd: 'reset_encoder', port: selectedId });
  }

  // ── Global ────────────────────────────────────────────────────────────────────
  function stopAll() {
    send({ cmd: 'stop_all' });
    motorSpeed = 0;
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
    </div>
  </div>

  <!-- ── Detail / control panel (right) ── -->
  <div class="flex-1 min-w-0 flex flex-col overflow-hidden bg-[#161920]">

    {#if selectedId === null}
      <!-- No port selected -->
      <div class="flex flex-col items-center justify-center h-full gap-3 text-slate-700">
        <svg class="w-10 h-10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <rect x="3" y="7" width="4" height="10" rx="1"/>
          <rect x="10" y="7" width="4" height="10" rx="1"/>
          <rect x="17" y="7" width="4" height="10" rx="1"/>
        </svg>
        <span class="text-sm">Select a port from the list</span>
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

        <!-- Stop All — always accessible -->
        <button
          class="ml-auto px-3 py-1 rounded text-xs font-semibold bg-red-600/20 text-red-400
                 border border-red-600/30 hover:bg-red-600/40 transition-colors"
          on:click={stopAll}
        >
          Stop All Motors
        </button>
      </div>

      <!-- Control body -->
      <div class="flex-1 overflow-y-auto p-6">

        {#if !selectedData}
          <!-- Unconfigured -->
          <div class="flex flex-col items-center justify-center h-full gap-2 text-slate-700">
            <span class="text-sm">Port not configured</span>
            <span class="text-xs">Configure it with robot.motor(), robot.servo(), etc. in your code.</span>
          </div>

        {:else if isMotor(selectedData.type)}
          <!-- ── Motor control ── -->
          <div class="max-w-lg space-y-6">

            <!-- Live readout -->
            <div class="flex items-baseline gap-3">
              <span class="text-4xl font-bold tabular-nums text-blue-400">
                {((selectedData.value ?? 0) / 100).toFixed(1)}%
              </span>
              <span class="text-sm text-slate-500">actual (from RP2040)</span>
            </div>

            <!-- Speed slider -->
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
            <div class="flex gap-2 flex-wrap">
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
                {(((selectedData.pulse_us ?? 1500) - 500) / 2000 * 300).toFixed(1)}°
              </span>
              <span class="text-sm text-slate-500">actual (from RP2040)</span>
            </div>

            <!-- Angle slider -->
            <div class="space-y-2">
              <div class="flex justify-between text-xs text-slate-500">
                <span>0°</span>
                <span class="font-semibold text-slate-300 tabular-nums">{servoAngle.toFixed(1)}°</span>
                <span>300°</span>
              </div>
              <input
                type="range" min="0" max="300" step="1"
                value={servoAngle}
                class="w-full h-2 rounded-full appearance-none cursor-pointer
                       bg-gradient-to-r from-amber-800/40 via-amber-600/20 to-amber-800/40
                       accent-amber-400"
                on:input={onServoSlider}
              />
            </div>

            <!-- Quick presets -->
            <div class="flex gap-2">
              {#each [[0, '0°'], [75, '75°'], [150, '150° (center)'], [225, '225°'], [300, '300°']] as [v, label]}
                <button
                  class="px-3 py-1.5 rounded text-xs font-mono bg-[#1e2129] border border-[#2e3340]
                         text-amber-400 hover:bg-amber-900/20 hover:border-amber-600/40 transition-colors"
                  on:click={() => sendServo(v)}>{label}</button>
              {/each}
            </div>

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

        {:else}
          <!-- Fallback for uart / i2c / other -->
          <div class="flex flex-col gap-2 text-slate-600">
            <span class="text-sm">No controls available for this port type.</span>
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
