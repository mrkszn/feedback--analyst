// Metrics — line chart + filter bar + data table.
// Maps to GET /admin/metrics.

function MetricsScreen() {
  const c = voiceColors;
  const [metric, setMetric] = React.useState('sentiment');
  const [bucket, setBucket] = React.useState('day');
  const series = metricSeries;
  const max = Math.max(...series.map(s => s.v));
  const min = Math.min(...series.map(s => s.v));
  // build polyline
  const W = 320, H = 120, pad = 10;
  const step = (W - pad * 2) / (series.length - 1);
  const ny = v => H - pad - ((v - min) / (max - min || 1)) * (H - pad * 2);
  const points = series.map((s, i) => `${pad + i * step},${ny(s.v).toFixed(1)}`).join(' ');
  const area = `M ${pad},${H} L ${points.split(' ').join(' L ')} L ${pad + (series.length - 1) * step},${H} Z`;

  return (
    <div style={{ paddingBottom: 80 }}>
      {/* Filter bar */}
      <div style={{ padding: '14px 16px 8px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <button style={selectStyle(c)}>
          <span style={{ color: c.text3, font: '500 12px/14px Geist, sans-serif' }}>METRIC</span>
          <span style={{ font: '500 14px/18px Geist, sans-serif', color: c.text1, flex: 1, textAlign: 'left' }}>
            {metric === 'sentiment' ? 'Sentiment score' : metric}
          </span>
          <Icon name="chev" size={16} color={c.text3}/>
        </button>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button style={selectStyle(c, { flex: 1 })}>
            <Icon name="cal" size={14} color={c.text3}/>
            <span style={{ font: '500 13px/16px Geist, sans-serif' }}>Last 7 days</span>
          </button>
          <div style={{ display: 'inline-flex', background: c.surface2, padding: 2, borderRadius: 8 }}>
            {['day', 'week'].map(b => (
              <button key={b} onClick={() => setBucket(b)} style={{
                height: 28, padding: '0 12px', border: 0, borderRadius: 6, cursor: 'pointer',
                background: bucket === b ? c.surface : 'transparent',
                color: bucket === b ? c.text1 : c.text3,
                boxShadow: bucket === b ? '0 1px 0 rgba(15,23,42,0.04)' : 'none',
                font: '500 13px/16px Geist, sans-serif',
              }}>{b}</button>
            ))}
          </div>
        </div>
      </div>

      {/* Chart card */}
      <div style={{ margin: '12px 16px 0', background: c.surface, border: `1px solid ${c.border}`, borderRadius: 12, padding: 14 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span style={{ font: '600 26px/30px "Geist Mono", monospace', color: c.text1 }}>0.78</span>
          <span style={{ font: '500 12px/16px "Geist Mono", monospace', color: c.success }}>▲ 0.04 wow</span>
        </div>
        <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ marginTop: 8 }}>
          <defs>
            <linearGradient id="m-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor={c.primary} stopOpacity="0.18"/>
              <stop offset="1" stopColor={c.primary} stopOpacity="0"/>
            </linearGradient>
          </defs>
          {[0.25, 0.5, 0.75].map(p => (
            <line key={p} x1="0" x2={W} y1={H * p + 8} y2={H * p + 8} stroke={c.border} strokeWidth="1"/>
          ))}
          <path d={area} fill="url(#m-fill)"/>
          <polyline points={points} fill="none" stroke={c.primary} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          {series.map((s, i) => (
            <circle key={i} cx={pad + i * step} cy={ny(s.v)} r="3" fill={c.surface} stroke={c.primary} strokeWidth="1.5"/>
          ))}
        </svg>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
          {series.map(s => (
            <span key={s.d} style={{ font: '500 11px/14px "Geist Mono", monospace', color: c.text3 }}>{s.d}</span>
          ))}
        </div>
      </div>

      <SectionHead>Daily values</SectionHead>
      <div style={{ margin: '0 16px', background: c.surface, border: `1px solid ${c.border}`, borderRadius: 12, overflow: 'hidden' }}>
        {series.slice().reverse().map((s, i) => (
          <div key={s.d} style={{ display: 'flex', alignItems: 'center', padding: '12px 14px',
                                  borderBottom: i < series.length - 1 ? `1px solid ${c.border}` : 0 }}>
            <span style={{ flex: 1, font: '500 14px/18px Geist, sans-serif', color: c.text1 }}>{s.d}</span>
            <span style={{ font: '500 14px/18px "Geist Mono", monospace', color: c.text1, width: 54, textAlign: 'right' }}>{s.v.toFixed(2)}</span>
            <span style={{ font: '500 12px/16px "Geist Mono", monospace', color: i === 0 ? c.success : c.text3, width: 60, textAlign: 'right' }}>
              {i === 0 ? '+0.04' : '—'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function selectStyle(c, extra = {}) {
  return {
    height: 40, padding: '0 12px', borderRadius: 8, border: `1px solid ${c.border}`,
    background: c.surface, cursor: 'pointer', display: 'inline-flex',
    alignItems: 'center', gap: 8, color: c.text1, ...extra,
  };
}

Object.assign(window, { MetricsScreen });
