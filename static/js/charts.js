/* Thin Plotly wrapper providing one shared theme so every chart on every
 * screen looks consistent without re-specifying styling each time.
 * Palette: fixed categorical slots (never reassigned by rank), reserved
 * status colors, single blue sequential ramp, blue<->red diverging pair.
 */
(function (global) {
  const COLORS = {
    ink: "#0b0b0b",
    inkSecondary: "#52514e",
    inkMuted: "#898781",
    grid: "#e1e0d9",
    baseline: "#c3c2b7",
    surface: "#fcfcfb",
    series: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
    good: "#0ca30c",
    warning: "#d98a00",
    serious: "#d9662f",
    critical: "#c23434",
    divergingCool: "#2a78d6",
    divergingWarm: "#e34948",
    divergingMid: "#f0efec",
  };

  const FONT = { family: "system-ui, -apple-system, Segoe UI, sans-serif", color: COLORS.inkSecondary, size: 12 };

  function baseLayout(overrides) {
    return Object.assign(
      {
        font: FONT,
        margin: { l: 52, r: 20, t: 10, b: 40 },
        paper_bgcolor: COLORS.surface,
        plot_bgcolor: COLORS.surface,
        xaxis: { gridcolor: COLORS.grid, zeroline: false, linecolor: COLORS.baseline, tickfont: { size: 11, color: COLORS.inkMuted } },
        yaxis: { gridcolor: COLORS.grid, zeroline: false, linecolor: COLORS.baseline, tickfont: { size: 11, color: COLORS.inkMuted } },
        legend: { orientation: "h", y: 1.12, x: 0, font: { size: 11.5 } },
        hovermode: "x unified",
        hoverlabel: { bgcolor: "#fff", bordercolor: COLORS.grid, font: { size: 11.5, color: COLORS.ink } },
      },
      overrides || {}
    );
  }

  const CONFIG = { displayModeBar: false, responsive: true };

  function render(containerId, traces, layout, config) {
    const el = document.getElementById(containerId);
    if (!el) return;
    Plotly.react(el, traces, layout, Object.assign({}, CONFIG, config || {}));
  }

  function line(containerId, series, opts) {
    opts = opts || {};
    const traces = series.map((s, i) => ({
      x: s.x,
      y: s.y,
      name: s.name,
      type: "scatter",
      mode: "lines",
      line: { width: 2, color: s.color || COLORS.series[i % COLORS.series.length], dash: s.dash || "solid" },
      fill: s.fill ? "tozeroy" : undefined,
      fillcolor: s.fill ? hexToRgba(s.color || COLORS.series[i % COLORS.series.length], 0.10) : undefined,
    }));
    render(containerId, traces, baseLayout(opts.layout), opts.config);
  }

  function bar(containerId, series, opts) {
    opts = opts || {};
    const traces = series.map((s, i) => ({
      x: s.x,
      y: s.y,
      name: s.name,
      type: "bar",
      marker: { color: s.color || COLORS.series[i % COLORS.series.length] },
    }));
    const layout = baseLayout(Object.assign({ barmode: opts.stacked ? "stack" : "group", bargap: 0.25 }, opts.layout));
    render(containerId, traces, layout, opts.config);
  }

  function scatter(containerId, points, opts) {
    opts = opts || {};
    const traces = [
      {
        x: points.x,
        y: points.y,
        mode: "markers",
        type: "scatter",
        marker: { size: 7, color: points.color || COLORS.series[0], opacity: 0.65, line: { width: 1, color: "#fff" } },
        name: points.name || "Shifts",
        hovertemplate: opts.hovertemplate,
      },
    ];
    if (opts.referenceLine) {
      const max = Math.max(...points.x, ...points.y) * 1.05;
      traces.push({
        x: [0, max],
        y: [0, max],
        mode: "lines",
        type: "scatter",
        line: { width: 1.5, color: COLORS.inkMuted, dash: "dash" },
        name: "Demand = Dispatch",
        hoverinfo: "skip",
      });
    }
    render(containerId, traces, baseLayout(Object.assign({ hovermode: "closest" }, opts.layout)), opts.config);
  }

  function heatmap(containerId, matrix, opts) {
    opts = opts || {};
    const trace = {
      z: matrix.z,
      x: matrix.x,
      y: matrix.y,
      type: "heatmap",
      colorscale: opts.diverging
        ? [[0, COLORS.divergingCool], [0.5, COLORS.divergingMid], [1, COLORS.divergingWarm]]
        : [[0, "#cde2fb"], [0.35, "#6da7ec"], [0.7, "#2a78d6"], [1, "#0d366b"]],
      colorbar: { thickness: 12, len: 0.9, tickfont: { size: 10, color: COLORS.inkMuted } },
      hovertemplate: opts.hovertemplate || "%{y} · %{x}<br>%{z:,.0f}<extra></extra>",
    };
    const callerLayout = opts.layout || {};
    const catAxis = { type: "category", gridcolor: COLORS.grid, tickfont: { size: 11, color: COLORS.inkMuted } };
    const layout = baseLayout(Object.assign(
      { hovermode: "closest", legend: undefined },
      callerLayout,
      {
        xaxis: Object.assign({}, catAxis, callerLayout.xaxis || {}, { type: "category" }),
        yaxis: Object.assign({}, catAxis, callerLayout.yaxis || {}, { type: "category" }),
      }
    ));
    render(containerId, [trace], layout, opts.config);
  }

  function box(containerId, groups, opts) {
    opts = opts || {};
    const traces = groups.map((g, i) => ({
      y: g.y,
      name: g.name,
      type: "box",
      marker: { color: g.color || COLORS.series[i % COLORS.series.length] },
      boxpoints: false,
    }));
    render(containerId, traces, baseLayout(Object.assign({ hovermode: "closest", showlegend: false }, opts.layout)), opts.config);
  }

  function donut(containerId, slices, opts) {
    opts = opts || {};
    const trace = {
      labels: slices.map((s) => s.label),
      values: slices.map((s) => s.value),
      type: "pie",
      hole: 0.62,
      marker: { colors: slices.map((s, i) => s.color || COLORS.series[i % COLORS.series.length]) },
      textinfo: "label+percent",
      textfont: { size: 11 },
    };
    render(containerId, [trace], baseLayout(Object.assign({ hovermode: "closest" }, opts.layout)), opts.config);
  }

  function stackedArea(containerId, series, opts) {
    opts = opts || {};
    const traces = series.map((s, i) => ({
      x: s.x,
      y: s.y,
      name: s.name,
      type: "scatter",
      mode: "lines",
      stackgroup: "one",
      line: { width: 1, color: s.color || COLORS.series[i % COLORS.series.length] },
      fillcolor: s.color || COLORS.series[i % COLORS.series.length],
    }));
    render(containerId, traces, baseLayout(opts.layout), opts.config);
  }

  function waterfall(containerId, steps, opts) {
    opts = opts || {};
    const trace = {
      type: "waterfall",
      x: steps.map((s) => s.label),
      y: steps.map((s) => s.value),
      measure: steps.map((s) => s.measure || "relative"),
      connector: { line: { color: COLORS.grid, width: 1 } },
      decreasing: { marker: { color: COLORS.good } },
      increasing: { marker: { color: COLORS.series[1] } },
      totals: { marker: { color: "#10182b" } },
      text: steps.map((s) => opts.fmt ? opts.fmt(s.value) : s.value),
      textposition: "outside",
      textfont: { size: 11 },
    };
    render(containerId, [trace], baseLayout(Object.assign({ hovermode: "closest", showlegend: false }, opts.layout)), opts.config);
  }

  function radar(containerId, series, categories, opts) {
    opts = opts || {};
    const closedCats = categories.concat([categories[0]]);
    const traces = series.map((s, i) => {
      const color = s.color || COLORS.series[i % COLORS.series.length];
      return {
        type: "scatterpolar",
        r: s.values.concat([s.values[0]]),
        theta: closedCats,
        name: s.name,
        fill: "toself",
        fillcolor: hexToRgba(color, s.emphasize ? 0.22 : 0.08),
        line: { color, width: s.emphasize ? 3 : 1.5 },
      };
    });
    const layout = baseLayout(Object.assign({
      hovermode: "closest",
      polar: {
        bgcolor: COLORS.surface,
        radialaxis: { visible: true, range: [0, 100], gridcolor: COLORS.grid, tickfont: { size: 9, color: COLORS.inkMuted } },
        angularaxis: { gridcolor: COLORS.grid, tickfont: { size: 11, color: COLORS.inkSecondary } },
      },
    }, opts.layout));
    render(containerId, traces, layout, opts.config);
  }

  function hexToRgba(hex, alpha) {
    const h = hex.replace("#", "");
    const bigint = parseInt(h, 16);
    const r = (bigint >> 16) & 255, g = (bigint >> 8) & 255, b = bigint & 255;
    return `rgba(${r},${g},${b},${alpha})`;
  }

  function fmtInt(n) {
    if (n === null || n === undefined || Number.isNaN(n)) return "--";
    return Math.round(n).toLocaleString("en-IN");
  }
  function fmtPct(n, digits) {
    if (n === null || n === undefined || Number.isNaN(n)) return "--";
    return n.toFixed(digits === undefined ? 1 : digits) + "%";
  }
  function fmtRupee(n) {
    if (n === null || n === undefined || Number.isNaN(n)) return "--";
    const abs = Math.abs(n);
    if (abs >= 1e7) return "₹" + (n / 1e7).toFixed(2) + " Cr";
    if (abs >= 1e5) return "₹" + (n / 1e5).toFixed(2) + " L";
    return "₹" + Math.round(n).toLocaleString("en-IN");
  }

  global.Charts = { COLORS, line, bar, scatter, heatmap, box, donut, stackedArea, waterfall, radar, render, baseLayout, fmtInt, fmtPct, fmtRupee };
})(window);
