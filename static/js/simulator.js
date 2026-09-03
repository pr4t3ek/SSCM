/* What-If Simulator: debounced live recompute against POST /api/simulate.
 * Every slider change updates its numeric readout instantly (no network
 * call) then, after a short debounce, calls /api/simulate and re-renders
 * KPIs + charts in place via Plotly.react (no flicker).
 */
(function () {
  const DEBOUNCE_MS = 300;
  let debounceTimer = null;

  function riskBucket(shortageProbPct) {
    if (shortageProbPct < 10) return { label: 'Low', cls: 'green' };
    if (shortageProbPct < 30) return { label: 'Medium', cls: 'amber' };
    return { label: 'High', cls: 'red' };
  }

  function currentOverrides() {
    return {
      demand_growth_pct: +document.getElementById('s-demand-growth').value / 100,
      wagon_availability_pct: +document.getElementById('s-wagon-avail').value / 100,
      B_manual_override: +document.getElementById('s-base-fleet').value,
      spot_cost_per_rake_per_trip: +document.getElementById('s-spot-cost').value,
      min_service_level_pct: +document.getElementById('s-service-target').value / 100,
      demurrage_cost_per_rake_per_day: +document.getElementById('s-demurrage').value,
      demurrage_free_idle_rakes_per_day: +document.getElementById('s-demurrage-free').value,
      demurrage_penalty_cost_per_rake_per_day: +document.getElementById('s-demurrage-penalty').value,
    };
  }

  async function runSimulation() {
    const overrides = currentOverrides();
    const res = await fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(overrides),
    });
    const d = await res.json();
    renderResult(d, overrides);
  }

  function renderResult(d, overrides) {
    const manual = d.manual_breakdown;
    const req = d.required_summary;
    const risk = riskBucket((1 - manual.service_level_pct) * 100);

    const kpis = [
      { label: 'Required Rakes', value: req.avg.toFixed(1) + '/day' },
      { label: 'Base Fleet Rakes', value: manual.B.toFixed(1) + '/day' },
      { label: 'Spot Rakes', value: manual.avg_spot_rakes_per_day.toFixed(1) + '/day' },
      { label: 'Total Cost', value: Charts.fmtRupee(manual.total_cost) },
      { label: 'Service Level', value: (manual.service_level_pct * 100).toFixed(1) + '%', cls: manual.service_level_pct >= overrides.min_service_level_pct ? 'green' : 'amber' },
      { label: 'Risk Score', value: ((1 - manual.service_level_pct) * 100).toFixed(0) + '% &middot; ' + risk.label, cls: risk.cls },
    ];
    document.getElementById('sim-kpi-row').innerHTML = kpis.map(k =>
      `<div class="kpi-card ${k.cls || ''}"><div class="label">${k.label}</div><div class="value">${k.value}</div></div>`
    ).join('');

    const c = d.cost_curve;

    Charts.bar('sim-chart-stack', [
      { x: ['Required', 'Available'], y: [req.avg, null], name: 'Required Capacity', color: Charts.COLORS.inkMuted },
      { x: ['Required', 'Available'], y: [null, manual.B], name: 'Base Fleet', color: Charts.COLORS.series[0] },
      { x: ['Required', 'Available'], y: [null, manual.avg_spot_rakes_per_day], name: 'Spot Requirement', color: Charts.COLORS.series[1] },
    ], { stacked: true });

    Charts.line('sim-chart-cost-curve', [
      { x: c.B, y: c.total_cost, name: 'Total Cost', color: Charts.COLORS.series[0] },
    ], {
      layout: {
        showlegend: false,
        xaxis: { title: 'Base Fleet Capacity (rakes/day)' },
        yaxis: { title: 'Total Cost (Rs)' },
        shapes: [
          { type: 'line', x0: d.cost_optimal_B, x1: d.cost_optimal_B, y0: 0, y1: Math.max(...c.total_cost), line: { color: Charts.COLORS.good, width: 1.5, dash: 'dot' } },
          { type: 'line', x0: manual.B, x1: manual.B, y0: 0, y1: Math.max(...c.total_cost), line: { color: Charts.COLORS.critical, width: 1.5, dash: 'dot' } },
        ],
        annotations: [
          { x: d.cost_optimal_B, y: Math.max(...c.total_cost), text: 'Optimal', showarrow: false, font: { size: 10.5, color: Charts.COLORS.good } },
          { x: manual.B, y: 0, yshift: -14, text: 'Your setting', showarrow: false, font: { size: 10.5, color: Charts.COLORS.critical } },
        ],
      }
    });

    Charts.line('sim-chart-tradeoff', [
      { x: c.service_level_pct.map(v => v * 100), y: c.total_cost, name: 'Cost vs Service', color: Charts.COLORS.series[2] },
    ], {
      layout: {
        showlegend: false,
        xaxis: { title: 'Service Level %', ticksuffix: '%' },
        yaxis: { title: 'Total Cost (Rs)' },
      }
    });

    document.querySelectorAll('.sim-model-label').forEach(el => el.textContent = d.label);
  }

  function wireSlider(sliderId, valId, fmt) {
    const el = document.getElementById(sliderId);
    const val = document.getElementById(valId);
    el.addEventListener('input', () => {
      val.textContent = fmt(el.value);
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(runSimulation, DEBOUNCE_MS);
    });
  }

  function init() {
    wireSlider('s-demand-growth', 'v-demand-growth', v => (v >= 0 ? '+' : '') + v + '%');
    wireSlider('s-wagon-avail', 'v-wagon-avail', v => v + '%');
    wireSlider('s-base-fleet', 'v-base-fleet', v => (+v).toFixed(1) + ' rakes/day');
    wireSlider('s-spot-cost', 'v-spot-cost', v => Charts.fmtRupee(+v));
    wireSlider('s-service-target', 'v-service-target', v => v + '%');
    wireSlider('s-demurrage', 'v-demurrage', v => Charts.fmtRupee(+v));
    wireSlider('s-demurrage-free', 'v-demurrage-free', v => (+v).toFixed(1) + ' rakes/day');
    wireSlider('s-demurrage-penalty', 'v-demurrage-penalty', v => Charts.fmtRupee(+v));
    runSimulation();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
