// Топики — топ-5 по тональности (POST /admin/topics).

function TopicsScreen() {
  const [preset, setPreset] = React.useState('30d');
  const [tone, setTone]     = React.useState('positive');
  const list = topicsByTone[tone] || [];
  const top5 = list.slice(0, 5);
  const max = top5[0]?.count ?? 0;
  const barBg = tone === 'positive' ? 'var(--success)' : 'var(--danger)';

  return (
    <div style={{ paddingBottom: 86 }}>
      {/* Date chips */}
      <div style={{ padding: '14px 16px 8px', display: 'flex', gap: 8, overflowX: 'auto' }}>
        {DATE_PRESETS.map(p => (
          <Chip key={p.value} active={preset === p.value} onClick={() => setPreset(p.value)}>{p.label}</Chip>
        ))}
      </div>

      {/* Tone pill toggle */}
      <div style={{ padding: '0 16px 8px' }}>
        <div role="tablist" aria-label="Тональность" style={{
          display: 'inline-flex', background: 'var(--surface)', border: '1px solid var(--line)',
          borderRadius: 999, padding: 3,
        }}>
          {[['positive','Позитивные'], ['negative','Негативные']].map(([v, lab]) => (
            <button key={v} role="tab" aria-selected={tone === v} onClick={() => setTone(v)} style={{
              height: 30, padding: '0 14px', border: 0, borderRadius: 999, cursor: 'pointer',
              background: tone === v ? 'var(--primary)' : 'transparent',
              color: tone === v ? '#fff' : 'var(--muted)',
              fontWeight: 500, fontSize: 13, fontFamily: 'var(--font-sans)',
            }}>{lab}</button>
          ))}
        </div>
      </div>

      {/* Top-5 bars card */}
      <Card style={{ margin: '6px 16px 0' }} aria-label="Топ-5 топиков">
        <div style={{ fontWeight: 600, fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase',
                       color: 'var(--muted)', marginBottom: 12 }}>
          Топ-5 · {tone === 'positive' ? 'позитив' : 'негатив'}
        </div>
        {top5.length === 0 ? (
          <span style={{ fontSize: 13, color: 'var(--muted)' }}>За период данных нет.</span>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 11 }} data-testid="topic-bars">
            {top5.map((t, i) => {
              const pct = max > 0 ? (t.count / max) * 100 : 0;
              return (
                <li key={t.topic} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span className="serif-num" style={{ width: 20, fontSize: 15, color: 'var(--muted-2)' }}>{i + 1}</span>
                  <span style={{ flex: '0 0 38%', fontSize: 13.5, color: 'var(--ink)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.topic}</span>
                  <div style={{ flex: 1, height: 8, background: 'var(--surface-2)', borderRadius: 999, overflow: 'hidden' }}>
                    <div style={{ width: `${pct}%`, height: '100%', background: barBg, borderRadius: 999 }}/>
                  </div>
                  <span style={{ width: 30, textAlign: 'right', fontWeight: 500, fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--ink)' }}>{t.count}</span>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      {/* Avg-sentiment row — small editorial value-add but uses real avg_sentiment field */}
      <Card pad={false} style={{ margin: '14px 16px 0' }}>
        <div style={{ padding: '10px 14px', background: 'var(--surface-2)',
                       fontWeight: 600, fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em',
                       display: 'flex' }}>
          <span style={{ flex: 1 }}>Топик</span>
          <span style={{ width: 70, textAlign: 'right' }}>Sentiment</span>
          <span style={{ width: 46, textAlign: 'right' }}>Кол-во</span>
        </div>
        {top5.map((t, i, a) => (
          <div key={t.topic} style={{ display: 'flex', alignItems: 'center', padding: 'var(--row-pad) 14px',
                                      borderTop: '1px solid var(--line)' }}>
            <span style={{ flex: 1, fontWeight: 500, fontSize: 14, color: 'var(--ink)' }}>{t.topic}</span>
            <span style={{ width: 70, textAlign: 'right', fontWeight: 500, fontSize: 13, fontFamily: 'var(--font-mono)',
                            color: t.avg_sentiment >= 0 ? 'var(--success)' : 'var(--danger)' }}>
              {t.avg_sentiment > 0 ? '+' : ''}{t.avg_sentiment.toFixed(2)}
            </span>
            <span style={{ width: 46, textAlign: 'right', fontWeight: 500, fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>{t.count}</span>
          </div>
        ))}
      </Card>

      {/* Mentions placeholder — honest about backend status */}
      <SectionHead index="01">Упоминания</SectionHead>
      <Card style={{ margin: '0 16px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
          <span style={{ width: 24, height: 24, borderRadius: 999, display: 'grid', placeItems: 'center',
                          background: 'var(--primary-soft)', color: 'var(--primary-deep)', flexShrink: 0 }}>
            <Icon name="clock" size={14}/>
          </span>
          <div>
            <div style={{ fontFamily: 'var(--font-head)', fontStyle: 'var(--head-style)', fontSize: 18, lineHeight: 1.2, color: 'var(--ink)' }}>
              Следующая итерация
            </div>
            <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 6, lineHeight: 1.5 }}>
              Подключение к семантическому поиску по топикам — в следующем релизе. Пока используйте «Клиенты» и «Чат».
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

Object.assign(window, { TopicsScreen });
