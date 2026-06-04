// Главная — KPI обзора + позитивные/негативные топ-3 топика.
// Маппинг: GET /admin/overview.

function sentimentLabel(v) {
  if (v === null || v === undefined) return '—';
  if (v >  0.33) return 'позитив';
  if (v < -0.33) return 'негатив';
  return 'нейтрально';
}
function sentimentKind(v) {
  if (v === null || v === undefined) return 'flat';
  if (v >  0.33) return 'up';
  if (v < -0.33) return 'dn';
  return 'flat';
}
function positiveShare(o) {
  const pos = o.top_positive_topics.reduce((s,t) => s + t.count, 0);
  const neg = o.top_negative_topics.reduce((s,t) => s + t.count, 0);
  const total = pos + neg;
  if (total === 0) return '—';
  return `${Math.round((pos / total) * 100)}%`;
}
function topicsCount(o) {
  const s = new Set();
  for (const t of o.top_positive_topics) s.add(t.topic);
  for (const t of o.top_negative_topics) s.add(t.topic);
  return s.size;
}

function DashboardScreen() {
  const [preset, setPreset] = React.useState('7d');
  const o = overview;

  return (
    <div style={{ paddingBottom: 86 }}>
      {/* Date range */}
      <div style={{ padding: '14px 16px 8px', display: 'flex', gap: 8, overflowX: 'auto' }} role="tablist" aria-label="Период">
        {DATE_PRESETS.map(p => (
          <Chip key={p.value} active={preset === p.value} onClick={() => setPreset(p.value)}>{p.label}</Chip>
        ))}
      </div>

      {/* KPI grid 2x2 — exactly what /admin/overview gives */}
      <div style={{ padding: '8px 16px 0', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }} data-testid="kpi-grid">
        <KPICard label="Сессий"            value={o.sessions_count.toLocaleString('ru-RU')} delta="за период" deltaKind="flat"
                 spark={<Spark points="0,16 8,14 16,15 24,11 32,12 40,8 48,9 60,4"/>}/>
        <KPICard label="Средний sentiment" value={sentimentLabel(o.avg_sentiment)}
                 delta={o.avg_sentiment !== null ? o.avg_sentiment.toFixed(2) : '—'}
                 deltaKind={sentimentKind(o.avg_sentiment)}
                 spark={<Spark points="0,12 12,10 24,11 36,7 48,8 60,5" color="var(--accent)"/>}/>
        <KPICard label="Топиков"           value={topicsCount(o).toString()} delta="уникальных" deltaKind="flat"/>
        <KPICard label="Позитив"           value={positiveShare(o)} delta="доля" deltaKind="up"
                 spark={<Spark points="0,15 12,13 24,10 36,9 48,6 60,4"/>}/>
      </div>

      {/* Pos / Neg top-3 — the two grid cards from the repo */}
      <div style={{ padding: '14px 16px 0', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <TopTopicsCard title="Позитивные" tone="pos" topics={o.top_positive_topics.slice(0, 3)}/>
        <TopTopicsCard title="Негативные" tone="neg" topics={o.top_negative_topics.slice(0, 3)}/>
      </div>

      {/* Top-5 list (compact full-width) — visual richness without inventing features */}
      <SectionHead index="01">Топ-5 топиков · позитив</SectionHead>
      <Card pad={false} style={{ margin: '0 16px' }}>
        {o.top_positive_topics.slice(0, 5).map((t, i, a) => {
          const max = a[0].count;
          return (
            <div key={t.topic} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 'var(--row-pad) 14px',
                                        borderBottom: i < a.length - 1 ? '1px solid var(--line)' : 0 }}>
              <span className="serif-num" style={{ width: 22, fontSize: 15, color: 'var(--muted-2)' }}>{i + 1}</span>
              <span style={{ flex: 1, fontWeight: 500, fontSize: 14, color: 'var(--ink)' }}>{t.topic}</span>
              <div style={{ width: 90, height: 8, background: 'var(--surface-2)', borderRadius: 999, overflow: 'hidden' }}>
                <div style={{ width: `${(t.count / max) * 100}%`, height: '100%', background: 'var(--success)', borderRadius: 999 }}/>
              </div>
              <span style={{ width: 32, textAlign: 'right', fontWeight: 500, fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--ink)' }}>{t.count}</span>
            </div>
          );
        })}
      </Card>
    </div>
  );
}

function TopTopicsCard({ title, tone, topics }) {
  const cnt = tone === 'pos' ? 'var(--success)' : 'var(--danger)';
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--line)',
                  borderRadius: 'var(--r-card)', padding: 'var(--card-pad)',
                  display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontWeight: 600, fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{title}</span>
        <span style={{ width: 6, height: 6, borderRadius: 999, background: cnt }}/>
      </div>
      {topics.length === 0 ? (
        <span style={{ fontSize: 13, color: 'var(--muted)' }}>Нет данных</span>
      ) : (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 7 }}>
          {topics.map(t => (
            <li key={t.topic} style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span style={{ flex: 1, fontSize: 13, color: 'var(--ink)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.topic}</span>
              <span className="serif-num" style={{ fontSize: 17, color: cnt }}>{t.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

Object.assign(window, { DashboardScreen });
