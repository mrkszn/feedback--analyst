// Topics — positive / negative tabs + BarChart + mentions list.
// Maps to GET /admin/topics.

function TopicsScreen() {
  const c = voiceColors;
  const [tab, setTab] = React.useState('positive');
  const data = tab === 'positive' ? topicsPos : topicsNeg;
  const accent = tab === 'positive' ? c.success : c.danger;

  return (
    <div style={{ paddingBottom: 80 }}>
      {/* Tabs */}
      <div style={{ padding: '14px 16px 0' }}>
        <div style={{ display: 'inline-flex', background: c.surface2, padding: 2, borderRadius: 10, width: '100%' }}>
          {[
            { id: 'positive', label: 'Positive' },
            { id: 'negative', label: 'Negative' },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              flex: 1, height: 32, border: 0, borderRadius: 8, cursor: 'pointer',
              background: tab === t.id ? c.surface : 'transparent',
              color: tab === t.id ? c.text1 : c.text3,
              boxShadow: tab === t.id ? '0 1px 0 rgba(15,23,42,0.06)' : 'none',
              font: '500 14px/18px Geist, sans-serif',
            }}>{t.label}</button>
          ))}
        </div>
      </div>

      {/* Bar chart card */}
      <div style={{ margin: '14px 16px 0', background: c.surface, border: `1px solid ${c.border}`, borderRadius: 12, padding: 14 }}>
        <div style={{ font: '600 11px/14px Geist, sans-serif', letterSpacing: '0.08em',
                       textTransform: 'uppercase', color: c.text3, marginBottom: 12 }}>
          Top 5 · {tab}
        </div>
        {data.map((t, i) => (
          <div key={t.name} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '8px 0', borderBottom: i < data.length - 1 ? `1px solid ${c.border}` : 0,
          }}>
            <span style={{ width: 18, font: '500 12px/16px "Geist Mono", monospace', color: c.text3 }}>#{i + 1}</span>
            <span style={{ flex: 1, font: '500 14px/18px Geist, sans-serif', color: c.text1 }}>{t.name}</span>
            <div style={{ width: 100, height: 8, background: c.surface2, borderRadius: 999, overflow: 'hidden' }}>
              <div style={{ width: `${t.share * 100}%`, height: '100%', background: accent, borderRadius: 999 }}/>
            </div>
            <span style={{ width: 32, textAlign: 'right', font: '500 13px/16px "Geist Mono", monospace', color: c.text1 }}>{t.count}</span>
          </div>
        ))}
      </div>

      {/* Mentions */}
      <SectionHead>Recent mentions</SectionHead>
      <div style={{ margin: '0 16px', background: c.surface, border: `1px solid ${c.border}`, borderRadius: 12, overflow: 'hidden' }}>
        {feedbackItems.filter(f => tab === 'positive' ? f.sentiment === 'pos' : f.sentiment === 'neg').slice(0, 4).map(it => (
          <FeedbackRow key={it.id} item={it}/>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { TopicsScreen });
