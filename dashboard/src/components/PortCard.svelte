<script>
  /**
   * PortCard – displays the status of a single robot port.
   *
   * Props:
   *   portNum  {number}  1-8
   *   data     {object|null}  port data from daemon, or null if unconfigured
   */
  export let portId;         // numeric ID (0-17)
  export let portLabel;      // display label: "S0"–"S9" or "D0"–"D7"
  export let isDual = false; // true for D0–D7
  export let data = null;

  $: isDualPin = isDual;

  // ── Derived display values ───────────────────────────────────────────────

  $: label = deviceLabel(data?.type);
  $: valueText = formatValue(data);
  $: iconPath = deviceIcon(data?.type);
  $: accentColor = deviceColor(data?.type);

  const isMotor = (t) => t === 'motor_sm' || t === 'motor_lap' || t === 'motor_servo_signal';
  const isGpio  = (t) => t === 'gpio_in' || t === 'gpio_out';

  function deviceLabel(type) {
    if (isMotor(type)) return 'Motor';
    switch (type) {
      case 'encoder':      return 'Encoder';
      case 'ultrasonic':   return 'Ultrasonic';
      case 'vl53l0x':     return 'VL53L0X';
      case 'ir_distance':  return 'IR Sensor';
      case 'servo':        return 'Servo';
      case 'gpio_in':    return 'Digital In';
      case 'gpio_out':   return 'Digital Out';
      case 'i2c':        return 'I²C';
      default:           return type ?? 'Empty';
    }
  }

  function formatValue(d) {
    if (!d) return null;
    if (isMotor(d.type)) {
      // value is ±10000 representing ±100%
      const pct = Math.round((d.value / 10000) * 100);
      return `${pct > 0 ? '+' : ''}${pct}%`;
    }
    switch (d.type) {
      case 'encoder':
        return `${d.count?.toLocaleString() ?? 0} cnt`;
      case 'vl53l0x': {
        if (!d.valid) return 'OOB';
        return `${(d.distance_mm / 10).toFixed(1)} cm`;
      }
      case 'ultrasonic': {
        if (!d.valid) return 'OOB';
        const cm = (d.distance_mm / 10).toFixed(1);
        return `${cm} cm`;
      }
      case 'servo': {
        const minA = d.min_angle    ?? 0,   maxA = d.max_angle    ?? 300;
        const minP = d.min_pulse_us ?? 500, maxP = d.max_pulse_us ?? 2500;
        const pulse = d.pulse_us ?? 1500;
        const val = maxP === minP ? minA
          : minA + (pulse - minP) / (maxP - minP) * (maxA - minA);
        const unit = d.gobilda_mode === 'continuous' ? '%' : '°';
        return `${val.toFixed(1)}${unit}`;
      }
      case 'ir_distance': {
        if (!d.valid) return 'OOB';
        return `${(d.distance_mm / 10).toFixed(1)} cm`;
      }
      case 'gpio_in':
      case 'gpio_out':
        return d.state ? 'HIGH' : 'LOW';
      case 'i2c':
        return 'active';
      default:
        return '—';
    }
  }

  /** Returns an SVG path string for the device icon */
  function deviceIcon(type) {
    if (isMotor(type))
      return 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM2 12h2M20 12h2M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41';
    switch (type) {
      case 'encoder':
        return 'M12 2a10 10 0 1 0 10 10M12 2v4M12 2l3 3M12 2l-3 3';
      case 'ultrasonic':
        return 'M8 12a4 4 0 0 0 4 4M8 12a4 4 0 0 1 4-4M8 12H4M19 12a7 7 0 0 1-7 7M19 12a7 7 0 0 0-7-7';
      case 'vl53l0x':
        return 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5';
      case 'ir_distance':
        return 'M12 19V5M5 12l7-7 7 7M3 19h18';
      case 'servo':
        return 'M12 6v6l4 2M5.636 5.636a9 9 0 1 0 12.728 12.728';
      case 'gpio_in':
        return 'M3 12h4l3-9 4 18 3-9h4';
      case 'gpio_out':
        return 'M5 12h14M12 5l7 7-7 7';
      default:
        return 'M12 12h.01';
    }
  }

  function deviceColor(type) {
    if (isMotor(type))  return 'text-blue-400   border-blue-500/30   bg-blue-500/10';
    if (isGpio(type))   return 'text-green-400  border-green-500/30  bg-green-500/10';
    switch (type) {
      case 'encoder':    return 'text-violet-400 border-violet-500/30 bg-violet-500/10';
      case 'ultrasonic': return 'text-cyan-400   border-cyan-500/30   bg-cyan-500/10';
      case 'vl53l0x':     return 'text-teal-400   border-teal-500/30   bg-teal-500/10';
      case 'ir_distance': return 'text-rose-400   border-rose-500/30   bg-rose-500/10';
      case 'servo':       return 'text-amber-400  border-amber-500/30  bg-amber-500/10';
      case 'i2c':        return 'text-orange-400 border-orange-500/30 bg-orange-500/10';
      default:           return 'text-slate-600  border-slate-700/30  bg-slate-800/20';
    }
  }

  $: secondaryText = formatSecondary(data);

  function formatSecondary(d) {
    if (!d) return null;
    if (d.type === 'encoder')
      return `${((d.velocity ?? 0) / 10).toFixed(1)} ticks/s`;
    if (isMotor(d.type))
      return d.type === 'motor_sm' ? 'sign-mag' : d.type === 'motor_lap' ? 'locked AP' : 'servo sig';
    return null;
  }
</script>

<div
  class="relative flex flex-col rounded-lg border transition-all duration-200 overflow-hidden
         {data
           ? `${accentColor} bg-[#1e2129]`
           : 'text-slate-700 border-slate-800/50 bg-[#191c23]'}"
>
  <!-- Port number badge -->
  <div class="flex items-center gap-1.5 px-3 pt-2.5 pb-1">
    <span
      class="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded
             {isDualPin
               ? 'bg-slate-700/60 text-slate-400'
               : 'bg-slate-800/60 text-slate-600'}"
    >
      {portLabel}
    </span>
    {#if data}
      <!-- Device icon -->
      <div class="ml-auto">
        <svg class="w-4 h-4 opacity-70" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="1.5"
             stroke-linecap="round" stroke-linejoin="round">
          <path d={iconPath}/>
        </svg>
      </div>
    {/if}
  </div>

  <!-- Content -->
  <div class="flex flex-col px-3 pb-3 gap-0.5 flex-1">
    {#if data}
      <div class="text-[11px] font-semibold uppercase tracking-widest opacity-60 leading-none">
        {label}
      </div>
      <div class="text-xl font-bold tabular-nums leading-tight mt-1">
        {valueText ?? '—'}
      </div>
      {#if secondaryText}
        <div class="text-[10px] font-mono text-slate-500 leading-none mt-0.5">
          {secondaryText}
        </div>
      {/if}
      {#if data.type === 'encoder' && data.inverted}
        <div class="inline-flex items-center gap-0.5 mt-1 px-1.5 py-0.5 rounded text-[9px] font-bold font-mono uppercase tracking-wider bg-amber-500/20 text-amber-400 border border-amber-500/30 w-fit">
          ⇅ inverted
        </div>
      {/if}
      {#if (data.type === 'ultrasonic' || data.type === 'ir_distance') && !data.valid}
        <div class="text-[10px] text-red-400 mt-0.5">out of range</div>
      {/if}
    {:else}
      <div class="text-xs text-slate-700 italic mt-1">not configured</div>
    {/if}
  </div>

  <!-- Dual-pin indicator strip on left edge -->
  {#if isDualPin && data}
    <div class="absolute left-0 top-0 bottom-0 w-0.5 rounded-l-lg opacity-60
                {isMotor(data.type)          ? 'bg-blue-400'   :
                 data.type === 'encoder'     ? 'bg-violet-400' :
                 data.type === 'ultrasonic'  ? 'bg-cyan-400'   :
                 data.type === 'servo'       ? 'bg-amber-400'  :
                 isGpio(data.type)           ? 'bg-green-400'  : 'bg-slate-600'}">
    </div>
  {/if}
</div>
