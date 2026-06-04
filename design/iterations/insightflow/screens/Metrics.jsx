// Метрики — выбор метрики (number → линия, enum → столбцы).
// Маппинг: GET /admin/metrics?metric_key=…

function MetricsScreen() {
  const [metricKey, setMetricKey] = React.useState('rating');
  const [preset, setPreset]       = React.useState('30d');
  const [groupBy, setGroupBy]     = React.useState('day');
  const [pickerOpen, setOpen]     = React.useState(false);
  const data = metricsByKey[metricKey];
  const selectedLabel = METRIC_KEYS.find(m => m.value === metricKey)?.label ?? metricKey;

  return (
    <div style={{ paddingBottom: 86 }}>
      {/* Filter bar */}
      <div style={{ padding: '14px 16px 8px', display: 'flex', alignItems: 'center', gap: 8, overflowX: 'auto', position: 'relative' }}>
        {/* Picker */}
        <div style={{ position: 'relative', flexShrink: 0 }}>
          <button onClick={() => setOpen(o => !o)} aria-label="Выбрать метрику" style={{
            display: 'inline-flex', alignItems: 'center', gap: 6, height: 30, padding: '0 12px',
            borderRadius: 999, border: '1px solid var(--line)', background: 'var(--surface)',
            fontWeight: 500, fontSize: 13, color: 'var(--ink)', whiteSpace: 'nowrap', cursor: 'pointer',
            fontFamily: 'var(--font-sans)',
          }}>
            {selectedLabel}
            <Icon name="chev" size={14} color="var(--muted)"/>
          </button>
          {pickerOpen && (
            <>
              <div onClick={() => setOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 6 }}/>
              <div style={{ position: 'absolute', top: 38, left: 0, zIndex: 7, minWidth: 200,
                            background: 'var(--surface)', border: '1px solid var(--line)',
                            borderRadius: 'var(--r-input)', boxShadow: '0 10px 30px -10px rgba(11,11,18,.24)',
                            overflow: 'hidden' }}>
                {METRIC_KEYS.map(m => (
                  <button key={m.value} onClick={() => { setMetricKey(m.value); setOpen(false); }} style={{
                    display: 'block', width: '100%', textAlign: 'left', padding: '10px 14px', border: 0,
                    background: m.value === metricKey ? 'var(--primary-soft)' : 'transparent',
                    color: m.value === metricKey ? 'var(--primary-deep)' : 'var(--ink)',
                    fontSize: 14, cursor: 'pointer', fontFamily: 'var(--font-sans)',
                  }}>{m.label}</button>
                ))}
              </div>
            </>
          )}
        </div>

        {DATE_PRESETS.map(p => (
          <Chip key={p.value} active={preset === p.value} onClick={() => setPreset(p.value)}>{p.label}</Chip>
        ))}

        {data.expected_type === 'number' && (
          <div role="group" aria-label="Группировка" style={{
            marginLeft: 'auto', display: 'inline-flex', flexShrink: 0, background: 'var(--surface)',
            border: '1px solid var(--line)', borderRadius: 999, padding: 2,
          }}>
            {[['day','День'],['week','Неделя']].map(([v,lab]) => (
              <button key={v} onClick={() => setGroupBy(v)} aria-pressed={groupBy === v} style={{
                height: 26, padding: '0 10px', border: 0, borderRadius: 999, cursor: 'pointer',
                background: groupBy === v ? 'var(--primary)' : 'transparent',
                color: groupBy === v ? '#fff' : 'var(--muted)',
                fontWeight: 500, fontSize: 12, fontFamily: 'var(--font-sans)',
              }}>{lab}</button>
            ))}
          </div>
        )}
      </div>

      <MetricView data={data} label={selectedLabel}/>
    </div>
  );
}

function MetricView({ data, label }) {
  if (data.expected_type === 'unknown') {
    return <Empty msg={`Метрика «${label}» не найдена.`}/>;
  }
  if (data.expected_type === 'text') {
    return <Empty msg="Текстовая метрика — используйте «Топики» или «Клиенты» для анализа."/>;
  }
  if (data.expected_type === 'number') {
    if (!data.points || data.points.length === 0) return <Empty msg={`По метрике «${label}» данных за период нет.`}/>;
    return <NumberView data={data} label={label}/>;
  }
  // enum
  if (!data.distribution || data.distribution.length === 0) return <Empty msg={`По метрике «${label}» данных за период нет.`}/>;
  return <EnumView data={data} label={label}/>;
}

function NumberView({ data, label }) {
  const pts = data.points;
  const avgs = pts.map(p => p.avg ?? 0);
  const max = Math.max(...avgs), min = Math.min(...avgs);
  const W = 320, H = 130, pad = 14;
  const step = (W - pad*2) / (pts.length - 1);
  const ny = v => H - pad - ((v - min) / (max - min || 1)) * (H - pad*2);
  const points = pts.map((p,i) => `${pad + i*step},${ny(p.avg ?? 0).toFixed(1)}`).join(' ');
  const area   = `M ${pad},${H} L ${points.split(' ').join(' L ')} L ${pad + (pts.length-1)*step},${H} Z`;
  const overall = avgs.reduce((s,v) => s+v, 0) / avgs.length;
  const overallFmt = overall.toLocaleString('ru-RU', { maximumFractionDigits: 2 }).replace('.', ',');

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <Card style={{ margin: '0 16px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span className="serif-num" style={{ fontSize: 42, lineHeight: 1, color: 'var(--ink)' }}>{overallFmt}</span>
          <span style={{ fontWeight: 500, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--muted)', whiteSpace: 'nowrap' }}>
            ср. за период
          </span>
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--muted)', marginTop: 2 }}>Среднее по метрике «{label}»</div>
        <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ marginTop: 12, display: 'block' }}>
          <defs>
            <linearGradient id={`m-fill-${data.metric_key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--primary)" stopOpacity="0.22"/>
              <stop offset="1" stopColor="var(--primary)" stopOpacity="0"/>
            </linearGradient>
          </defs>
          {[0.25, 0.5, 0.75].map(p => (
            <line key={p} x1="0" x2={W} y1={H * p} y2={H * p} stroke="var(--line)" strokeWidth="1"/>
          ))}
          <path d={area} fill={`url(#m-fill-${data.metric_key})`}/>
          <polyline points={points} fill="none" stroke="var(--primary)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
          {pts.map((p, i) => (
            <circle key={i} cx={pad + i*step} cy={ny(p.avg ?? 0)} r="3.4" fill="var(--surface)" stroke="var(--primary)" strokeWidth="1.8"/>
          ))}
        </svg>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
          {pts.map(p => (
            <span key={p.bucket} style={{ fontWeight: 500, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted-2)' }}>{p.bucket}</span>
          ))}
        </div>
      </Card>

      <SectionHead index="01">Значения по дням</SectionHead>
      <Card pad={false} style={{ margin: '0 16px' }} data-testid="metric-table">
        <div style={{ display: 'flex', alignItems: 'center', padding: '10px 14px', background: 'var(--surface-2)',
                      fontWeight: 600, fontSize: 11, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--muted)' }}>
          <span style={{ flex: 1 }}>День</span>
          <span style={{ width: 70, textAlign: 'right' }}>Среднее</span>
          <span style={{ width: 60, textAlign: 'right' }}>Кол-во</span>
        </div>
        {pts.map((p, i, a) => (
          <div key={p.bucket} style={{ display: 'flex', alignItems: 'center', padding: 'var(--row-pad) 14px',
                                       borderTop: '1px solid var(--line)' }}>
            <span style={{ flex: 1, fontWeight: 500, fontSize: 14, color: 'var(--ink)' }}>{p.bucket}</span>
            <span style={{ width: 70, textAlign: 'right', fontWeight: 500, fontSize: 14, fontFamily: 'var(--font-mono)', color: 'var(--ink)' }}>{p.avg !== null ? p.avg.toFixed(2) : '—'}</span>
            <span style={{ width: 60, textAlign: 'right', fontWeight: 500, fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>{p.count}</span>
          </div>
        ))}
      </Card>
    </div>
  );
}

function EnumView({ data, label }) {
  const dist = [...data.distribution].sort((a,b) => b.count - a.count);
  const max = dist[0]?.count ?? 0;
  // simple Recharts-style vertical bars
  const W = 320, H = 160, padX = 28, padY = 14;
  const barW = (W - padX*2) / dist.length * 0.6;
  const gap  = (W - padX*2) / dist.length * 0.4;
  const slot = (W - padX*2) / dist.length;
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <Card style={{ margin: '0 16px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span className="serif-num" style={{ fontSize: 38, lineHeight: 1, color: 'var(--ink)' }}>{data.total.toLocaleString('ru-RU')}</span>
          <span style={{ fontWeight: 500, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>значений</span>
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--muted)', marginTop: 2 }}>Распределение по метрике «{label}»</div>
        <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ marginTop: 12, display: 'block' }}>
          {[0.25, 0.5, 0.75].map(p => (
            <line key={p} x1={padX} x2={W - padX} y1={padY + (H - padY*2) * p} y2={padY + (H - padY*2) * p} stroke="var(--line)" strokeWidth="1"/>
          ))}
          {dist.map((d, i) => {
            const h = max > 0 ? ((H - padY*2) * d.count) / max : 0;
            const x = padX + slot * i + (slot - barW) / 2;
            const y = H - padY - h;
            return (
              <g key={d.value}>
                <rect x={x} y={y} width={barW} height={h} rx="3" fill="var(--primary)"/>
                <text x={x + barW/2} y={H - 2} textAnchor="middle" style={{ fontSize: 9, fill: 'var(--muted-2)', fontFamily: 'var(--font-mono)' }}>
                  {ENUM_LABELS[d.value] ?? d.value}
                </text>
                <text x={x + barW/2} y={y - 4} textAnchor="middle" className="serif-num" style={{ fontSize: 13, fill: 'var(--ink)' }}>{d.count}</text>
              </g>
            );
          })}
        </svg>
      </Card>

      <div style={{ padding: '12px 16px 0', display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13, color: 'var(--muted)' }}>
        <span>Всего: <span className="serif-num" style={{ fontSize: 17, color: 'var(--ink)' }}>{data.total.toLocaleString('ru-RU')}</span></span>
        {data.unknown > 0 && <span>Не определено: <span className="serif-num" style={{ fontSize: 17, color: 'var(--ink)' }}>{data.unknown}</span></span>}
      </div>

      <SectionHead index="01">Категории</SectionHead>
      <Card pad={false} style={{ margin: '0 16px' }}>
        {dist.map((d, i, a) => (
          <div key={d.value} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 'var(--row-pad) 14px',
                                      borderBottom: i < a.length - 1 ? '1px solid var(--line)' : 0 }}>
            <span style={{ flex: 1, fontWeight: 500, fontSize: 14, color: 'var(--ink)' }}>{ENUM_LABELS[d.value] ?? d.value}</span>
            <div style={{ width: 92, height: 8, background: 'var(--surface-2)', borderRadius: 999, overflow: 'hidden' }}>
              <div style={{ width: `${(d.count / max) * 100}%`, height: '100%', background: 'var(--primary)', borderRadius: 999 }}/>
            </div>
            <span style={{ width: 38, textAlign: 'right', fontWeight: 500, fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--ink)' }}>{d.count}</span>
            <span style={{ width: 40, textAlign: 'right', fontWeight: 500, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--muted-2)' }}>{Math.round(d.pct * 100)}%</span>
          </div>
        ))}
      </Card>
    </div>
  );
}

function Empty({ msg }) {
  return (
    <div style={{ padding: '20px 16px 0' }}>
      <Card><span style={{ fontSize: 13, color: 'var(--muted)' }}>{msg}</span></Card>
    </div>
  );
}

Object.assign(window, { MetricsScreen });
