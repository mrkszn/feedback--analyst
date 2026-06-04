// Клиенты — семантический поиск (POST /admin/semantic) + профиль (GET /admin/clients/{id}).

function ClientsScreen() {
  const [query, setQuery]     = React.useState('');
  const [debounced, setDeb]   = React.useState('');
  const [hits, setHits]       = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [openId, setOpenId]   = React.useState(null);

  // 300ms debounce — mirrors useDebounce(300) in the repo
  React.useEffect(() => {
    const t = setTimeout(() => setDeb(query.trim()), 300);
    return () => clearTimeout(t);
  }, [query]);

  React.useEffect(() => {
    if (!debounced) { setHits([]); setLoading(false); return; }
    setLoading(true);
    const t = setTimeout(() => { setHits(searchSemantic(debounced)); setLoading(false); }, 350);
    return () => clearTimeout(t);
  }, [debounced]);

  const suggestions = ['жалобы на доставку', 'хвалят сервис', 'долгое ожидание', 'постоянные гости'];

  return (
    <div style={{ paddingBottom: 86, position: 'relative' }}>
      {/* Search */}
      <div style={{ padding: '14px 16px 8px' }}>
        <div style={{ position: 'relative' }}>
          <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)',
                          color: 'var(--muted)', pointerEvents: 'none' }}>
            <Icon name="search" size={16}/>
          </span>
          <input value={query} onChange={e => setQuery(e.target.value)} aria-label="Поиск клиентов"
                 placeholder="Опишите, кого ищете…"
                 style={{ width: '100%', height: 44, padding: '0 12px 0 36px',
                          borderRadius: 'var(--r-input)', border: '1px solid var(--line)',
                          background: 'var(--surface)', fontSize: 15, fontFamily: 'var(--font-sans)',
                          color: 'var(--ink)', outline: 'none' }}/>
          {query && (
            <button onClick={() => setQuery('')} style={{ position: 'absolute', right: 8, top: '50%',
              transform: 'translateY(-50%)', width: 28, height: 28, borderRadius: 8, border: 0,
              background: 'transparent', color: 'var(--muted)', cursor: 'pointer',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon name="close" size={14}/>
            </button>
          )}
        </div>
      </div>

      {/* Empty / suggestion state */}
      {!debounced && (
        <div style={{ padding: '4px 16px 0' }}>
          <div style={{ fontFamily: 'var(--font-head)', fontStyle: 'var(--head-style)',
                         fontSize: 22, lineHeight: 1.18, color: 'var(--ink)', marginBottom: 10 }}>
            Спросите голосом владельца.
          </div>
          <div style={{ fontSize: 13.5, color: 'var(--muted)', marginBottom: 12, lineHeight: 1.5 }}>
            Семантический поиск ищет клиентов по смыслу запроса, не по имени или id.
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
            {suggestions.map(s => (
              <button key={s} onClick={() => setQuery(s)} style={{
                fontSize: 13, padding: '6px 11px', borderRadius: 999, border: '1px solid var(--line)',
                background: 'var(--surface)', color: 'var(--ink-2)', cursor: 'pointer', fontFamily: 'var(--font-sans)',
                whiteSpace: 'nowrap',
              }}>{s}</button>
            ))}
          </div>
        </div>
      )}

      {/* Loading */}
      {debounced && loading && (
        <div style={{ padding: '8px 16px', color: 'var(--muted)', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 12, height: 12, borderRadius: 999, border: '2px solid var(--line)',
                          borderTopColor: 'var(--primary)', display: 'inline-block',
                          animation: 'spin 0.8s linear infinite' }}/>
          Поиск…
        </div>
      )}
      <style>{`@keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }`}</style>

      {/* Results */}
      {debounced && !loading && hits.length === 0 && (
        <div style={{ padding: '8px 16px', color: 'var(--muted)', fontSize: 13 }}>Ничего не найдено.</div>
      )}
      {debounced && !loading && hits.length > 0 && (
        <>
          <div style={{ padding: '4px 16px 8px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
            <span style={{ fontWeight: 600, fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              {hits.length} {hits.length === 1 ? 'результат' : 'результатов'}
            </span>
            <span style={{ fontWeight: 500, fontSize: 11.5, color: 'var(--muted-2)', fontStyle: 'italic', fontFamily: 'var(--font-head)' }}>по смыслу</span>
          </div>
          <div style={{ padding: '0 16px', display: 'flex', flexDirection: 'column', gap: 8 }} data-testid="hit-list">
            {hits.map(h => <HitCard key={h.session_id} hit={h} onOpen={() => h.client_id !== null && setOpenId(h.client_id)}/>)}
          </div>
        </>
      )}

      {openId !== null && <ProfileSheet telegramId={openId} onClose={() => setOpenId(null)}/>}
    </div>
  );
}

function HitCard({ hit, onOpen }) {
  const c = clientProfiles[hit.client_id];
  const name = c?.name || (hit.client_id !== null ? `Клиент ${hit.client_id}` : 'Аноним');
  const init = c?.name
    ? (c.name.split(/\s+/).slice(0,2).map(p => p[0] || '').join('') || '—').toUpperCase()
    : (hit.client_id ? String(hit.client_id).slice(0,2) : '—');
  const sentTint = hit.sentiment === 'positive' ? 'mint' : hit.sentiment === 'negative' ? 'rose' : 'slate';
  const sentBg   = hit.sentiment === 'positive' ? 'color-mix(in srgb, var(--mint) 18%, var(--surface))'
                  : hit.sentiment === 'negative' ? 'color-mix(in srgb, var(--rose) 18%, var(--surface))'
                  : 'var(--surface-2)';
  const sentFg   = hit.sentiment === 'positive' ? 'var(--success)' : hit.sentiment === 'negative' ? 'var(--danger)' : 'var(--muted)';
  const sentLab  = hit.sentiment === 'positive' ? 'позитив' : hit.sentiment === 'negative' ? 'негатив' : hit.sentiment === 'neutral' ? 'нейтрально' : '—';
  const date = hit.started_at ? new Date(hit.started_at).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' }) : '';

  return (
    <button onClick={onOpen} disabled={hit.client_id === null} style={{
      display: 'flex', gap: 12, alignItems: 'flex-start', padding: '12px 14px',
      background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-card)',
      textAlign: 'left', cursor: hit.client_id !== null ? 'pointer' : 'default',
      opacity: hit.client_id !== null ? 1 : 0.6, fontFamily: 'var(--font-sans)',
    }}>
      <Avatar initials={init} tint={sentTint} size={40}/>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
          <span style={{ flex: 1, minWidth: 0, fontWeight: 600, fontSize: 14, color: 'var(--ink)',
                          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{name}</span>
          <span style={{ fontSize: 11.5, color: 'var(--muted-2)', fontFamily: 'var(--font-mono)', flexShrink: 0, whiteSpace: 'nowrap' }}>{date}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', padding: '2px 8px', borderRadius: 6,
                          background: sentBg, color: sentFg, fontSize: 11, fontWeight: 600 }}>
            {sentLab}
          </span>
          <span className="serif-num" style={{ fontSize: 14, color: 'var(--primary)' }}>{hit.score.toFixed(2)}</span>
          <span style={{ fontSize: 11, color: 'var(--muted-2)', fontFamily: 'var(--font-mono)' }}>score</span>
        </div>
        <div style={{ fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.45 }}>
          {hit.summary_text.length > 110 ? hit.summary_text.slice(0, 110) + '…' : hit.summary_text}
        </div>
      </div>
    </button>
  );
}

function ProfileSheet({ telegramId, onClose }) {
  const [loading, setLoading] = React.useState(true);
  const [profile, setProfile] = React.useState(null);
  React.useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => { setProfile(clientProfiles[telegramId] || null); setLoading(false); }, 250);
    return () => clearTimeout(t);
  }, [telegramId]);

  const name = profile?.name || `Клиент ${telegramId}`;
  const init = profile?.name
    ? profile.name.split(/\s+/).slice(0,2).map(p => p[0]).join('').toUpperCase()
    : String(telegramId).slice(0,2);
  const last = profile?.last_session_at ? new Date(profile.last_session_at).toLocaleDateString('ru-RU', { day:'2-digit', month:'long' }) : '—';
  const sentColor = profile && profile.avg_sentiment !== null
    ? (profile.avg_sentiment > 0.33 ? 'var(--success)' : profile.avg_sentiment < -0.33 ? 'var(--danger)' : 'var(--warning)')
    : 'var(--ink)';

  return (
    <>
      <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'var(--scrim)', zIndex: 10 }}/>
      <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, zIndex: 11, background: 'var(--surface)',
                    borderRadius: 'var(--r-sheet) var(--r-sheet) 0 0', boxShadow: 'var(--shadow-sheet)',
                    padding: '8px 16px 24px', maxHeight: '88%', overflow: 'auto',
                    animation: 'sheet-up 240ms cubic-bezier(0.2,0,0,1)' }}>
        <div style={{ width: 36, height: 4, background: 'var(--line-strong)', borderRadius: 999, margin: '6px auto 16px' }}/>

        {loading ? (
          <div style={{ padding: '12px 0', color: 'var(--muted)', fontSize: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 14, height: 14, borderRadius: 999, border: '2px solid var(--line)',
                            borderTopColor: 'var(--primary)', animation: 'spin 0.8s linear infinite' }}/>
            Загрузка профиля…
          </div>
        ) : !profile ? (
          <div style={{ padding: '12px 0', color: 'var(--muted)', fontSize: 14 }}>Профиль не найден.</div>
        ) : (
          <>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 14 }}>
              <Avatar initials={init} tint={'violet'} size={46}/>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: 18, color: 'var(--ink)' }}>{name}</div>
                <div style={{ fontWeight: 500, fontSize: 12.5, fontFamily: 'var(--font-mono)', color: 'var(--muted-2)' }}>
                  telegram #{profile.telegram_id} · последняя сессия {last}
                </div>
              </div>
              <button onClick={onClose} style={{ width: 32, height: 32, borderRadius: 8, border: 0, background: 'transparent',
                                                  color: 'var(--muted)', cursor: 'pointer',
                                                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                <Icon name="close" size={18}/>
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
              <div style={{ padding: '11px 12px', background: 'var(--surface-2)', borderRadius: 'var(--r-input)' }}>
                <div style={{ fontWeight: 600, fontSize: 10.5, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Сессий</div>
                <div className="serif-num" style={{ fontSize: 26, color: 'var(--ink)', marginTop: 2 }}>{profile.sessions_count}</div>
              </div>
              <div style={{ padding: '11px 12px', background: 'var(--surface-2)', borderRadius: 'var(--r-input)' }}>
                <div style={{ fontWeight: 600, fontSize: 10.5, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Sentiment</div>
                <div className="serif-num" style={{ fontSize: 26, color: sentColor, marginTop: 2 }}>
                  {profile.avg_sentiment !== null ? (profile.avg_sentiment > 0 ? '+' : '') + profile.avg_sentiment.toFixed(2) : '—'}
                </div>
              </div>
            </div>

            {profile.top_topics?.length > 0 && (
              <>
                <div style={{ fontWeight: 600, fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>Топики</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 16 }}>
                  {profile.top_topics.slice(0, 6).map(t => (
                    <span key={t.topic} style={{
                      fontSize: 12, padding: '4px 10px', borderRadius: 999,
                      background: 'var(--surface-2)', color: 'var(--ink-2)',
                    }}>{t.topic} <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--muted-2)', marginLeft: 4 }}>{t.count}</span></span>
                  ))}
                </div>
              </>
            )}

            {profile.recent_cards?.length > 0 && (
              <>
                <div style={{ fontWeight: 600, fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>Последние карточки</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {profile.recent_cards.slice(0, 3).map((card, i) => (
                    <div key={i} style={{ background: 'var(--surface)', border: '1px solid var(--line)',
                                          borderRadius: 'var(--r-card)', padding: 12,
                                          fontFamily: 'var(--font-mono)', fontSize: 11.5, lineHeight: '17px',
                                          color: 'var(--ink-2)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      <pre style={{ margin: 0, fontFamily: 'inherit', fontSize: 'inherit' }}>{JSON.stringify(card, null, 2)}</pre>
                    </div>
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </>
  );
}

Object.assign(window, { ClientsScreen });
