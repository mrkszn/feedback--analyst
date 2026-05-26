// Dashboard — KPI overview + recent feedback + date range.
// Maps to GET /admin/overview.

function DashboardScreen({ onOpenItem }) {
  const c = voiceColors;
  const [range, setRange] = React.useState('7d');
  return (
    <div style={{ paddingBottom: 80 }}>
      {/* Date range */}
      <div style={{ padding: '16px 16px 0', display: 'flex', gap: 8, overflowX: 'auto' }}>
        {['Today', '7d', '30d', '90d'].map(r => (
          <Chip key={r} active={range === r} onClick={() => setRange(r)}>{r}</Chip>
        ))}
        <button style={{
          height: 30, padding: '0 10px', borderRadius: 999, border: `1px solid ${c.border}`,
          background: c.surface, color: c.text2, font: '500 13px/18px Geist, sans-serif',
          display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer',
        }}><Icon name="cal" size={14}/>Custom</button>
      </div>

      {/* KPI grid */}
      <div style={{ padding: '16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <KPICard label="Feedback · 7d"  value="1 248" delta="18.4%" deltaKind="up"
                 spark={<Spark points="0,16 8,14 16,15 24,11 32,12 40,8 48,9 60,4" color={c.success}/>}/>
        <KPICard label="Sentiment"      value="0.78"  delta="0.04" deltaKind="up"
                 spark={<Spark points="0,12 12,10 24,11 36,7 48,8 60,5" color={c.success}/>}/>
        <KPICard label="Sessions"       value="3 091" delta="±0.0%" deltaKind="flat"
                 spark={<Spark points="0,11 12,11 24,12 36,10 48,11 60,11" color="#94a3b8"/>}/>
        <KPICard label="Drop-off"       value="12.3%" delta="2.1%" deltaKind="dn"
                 spark={<Spark points="0,4 12,6 24,5 36,9 48,10 60,14" color={c.danger}/>}/>
      </div>

      {/* Top topics mini */}
      <SectionHead action={<button style={ghostLink(c)}>All <Icon name="chevRight" size={14}/></button>}>
        Top topics this week
      </SectionHead>
      <div style={{ margin: '0 16px', background: c.surface, border: `1px solid ${c.border}`, borderRadius: 12, padding: '4px 12px' }}>
        {topicsPos.slice(0, 4).map((t, i) => (
          <div key={t.name} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 0', borderBottom: i < 3 ? `1px solid ${c.border}` : 0
          }}>
            <span style={{ flex: 1, font: '500 14px/18px Geist, sans-serif', color: c.text1 }}>{t.name}</span>
            <div style={{ width: 100, height: 6, background: c.surface2, borderRadius: 999, overflow: 'hidden' }}>
              <div style={{ width: `${t.share * 100}%`, height: '100%', background: c.primary, borderRadius: 999 }}/>
            </div>
            <span style={{ width: 28, textAlign: 'right', font: '500 13px/16px "Geist Mono", monospace', color: c.text1 }}>{t.count}</span>
          </div>
        ))}
      </div>

      {/* Recent feedback */}
      <SectionHead action={<button style={ghostLink(c)}>All <Icon name="chevRight" size={14}/></button>}>
        Recent feedback
      </SectionHead>
      <div style={{ margin: '0 16px', background: c.surface, border: `1px solid ${c.border}`, borderRadius: 12, overflow: 'hidden' }}>
        {feedbackItems.slice(0, 4).map(it => (
          <FeedbackRow key={it.id} item={it} onClick={() => onOpenItem && onOpenItem(it)}/>
        ))}
      </div>
    </div>
  );
}

function ghostLink(c) {
  return {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    background: 'transparent', border: 0, padding: '2px 4px',
    color: c.text2, font: '500 12px/16px Geist, sans-serif', cursor: 'pointer',
  };
}

Object.assign(window, { DashboardScreen });
