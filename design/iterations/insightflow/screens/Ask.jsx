// Чат — диалог с агентом (POST /admin/ask). Ответ: { answer_text, tools_used, chart_text }.

const SUGGESTED = [
  'Топ-3 жалобы за неделю',
  'Сводка за 30 дней',
  'Что хвалят клиенты',
  'Найди жалобы на скорость',
];

const HISTORY_LIMIT = 6;

function AskScreen() {
  const [entries, setEntries] = React.useState([]);   // { role, content, chart_text, tools_used }
  const [thinking, setThinking] = React.useState(false);
  const [value, setValue] = React.useState('');
  const scrollRef = React.useRef(null);
  const taRef = React.useRef(null);

  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [entries.length, thinking]);

  function send(text) {
    const trimmed = (text || '').trim();
    if (!trimmed) return;
    const history = entries.filter(e => e.role !== 'thinking').slice(-HISTORY_LIMIT)
                           .map(e => ({ role: e.role === 'user' ? 'user' : 'assistant', content: e.content || '' }));
    const next = [...entries, { role: 'user', content: trimmed }];
    setEntries(next);
    setValue('');
    setThinking(true);
    setTimeout(() => {
      const res = askReply(trimmed, history);
      setEntries(e => [...e, { role: 'agent', content: res.answer_text, chart_text: res.chart_text, tools_used: res.tools_used }]);
      setThinking(false);
    }, 850);
  }

  function onKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send(value);
    }
  }

  // autosize textarea
  function autosize(el) {
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 96) + 'px';
  }
  React.useEffect(() => autosize(taRef.current), [value]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Empty state — suggested chips above the (empty) chat */}
      {entries.length === 0 && (
        <div style={{ padding: '16px 16px 4px' }}>
          <div style={{ fontFamily: 'var(--font-head)', fontStyle: 'var(--head-style)',
                         fontSize: 22, lineHeight: 1.18, color: 'var(--ink)' }}>
            Спросите про feedback.
          </div>
          <div style={{ fontSize: 13.5, color: 'var(--muted)', marginTop: 6, lineHeight: 1.5 }}>
            Я отвечаю по данным сессий Atelier Brun — метрики, топики, клиенты.
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginTop: 12 }} aria-label="Подсказки">
            {SUGGESTED.map(p => (
              <Chip key={p} onClick={() => send(p)}>{p}</Chip>
            ))}
          </div>
        </div>
      )}

      {/* Chat list */}
      <div ref={scrollRef} style={{ flex: 1, overflow: 'auto', padding: '14px 14px 4px' }} data-testid="chat-list">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {entries.map((m, i) => <Message key={i} m={m}/>)}
          {thinking && (
            <div style={{ alignSelf: 'flex-start', display: 'flex', alignItems: 'flex-end', gap: 8 }}>
              <BrandMark size={24} radius={6}/>
              <div style={{ padding: '10px 12px', background: 'var(--surface)', border: '1px solid var(--line)',
                             borderRadius: '14px 14px 14px 4px', display: 'inline-flex', gap: 4, alignItems: 'center' }}>
                {[0,1,2].map(i => (
                  <span key={i} style={{ width: 6, height: 6, borderRadius: 999, background: 'var(--amber)',
                                          animation: `bob 1.2s ${i*0.15}s infinite ease-in-out` }}/>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Composer */}
      <form onSubmit={e => { e.preventDefault(); send(value); }} style={{
        margin: '6px 12px calc(64px + env(safe-area-inset-bottom, 0px))',
        padding: 8, display: 'flex', gap: 8, alignItems: 'flex-end',
        background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-card)',
      }}>
        <textarea
          ref={taRef} value={value} onChange={e => setValue(e.target.value)} onKeyDown={onKey}
          rows={1} aria-label="Сообщение"
          placeholder="Спросите про feedback…"
          style={{ flex: 1, resize: 'none', border: 0, outline: 0, background: 'transparent',
                    padding: '7px 8px', fontSize: 15, lineHeight: '20px',
                    color: 'var(--ink)', fontFamily: 'var(--font-sans)', minHeight: 22, maxHeight: 96 }}
        />
        <button type="submit" aria-label="Отправить" disabled={!value.trim()} style={{
          width: 36, height: 36, borderRadius: 'var(--r-input)', border: 0, flexShrink: 0,
          background: value.trim() ? 'var(--primary)' : 'var(--surface-2)',
          color: value.trim() ? '#fff' : 'var(--muted-2)',
          cursor: value.trim() ? 'pointer' : 'default',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name="send" size={16}/>
        </button>
      </form>
    </div>
  );
}

function Message({ m }) {
  const isUser = m.role === 'user';
  if (isUser) {
    return (
      <div style={{ alignSelf: 'flex-end', maxWidth: '84%' }}>
        <div style={{ background: 'var(--primary-hover)', color: '#fff', padding: '10px 12px',
                       borderRadius: '14px 14px 4px 14px', fontSize: 14, lineHeight: '20px', whiteSpace: 'pre-wrap' }}>
          {m.content}
        </div>
      </div>
    );
  }
  return (
    <div style={{ alignSelf: 'flex-start', maxWidth: '88%', display: 'flex', gap: 8, alignItems: 'flex-end' }}>
      <BrandMark size={24} radius={6}/>
      <div style={{ background: 'var(--surface)', color: 'var(--ink)', border: '1px solid var(--line)',
                     padding: '10px 12px', borderRadius: '14px 14px 14px 4px',
                     fontSize: 14, lineHeight: '20px', maxWidth: '100%' }}>
        <div style={{ whiteSpace: 'pre-wrap' }}>{m.content}</div>
        {m.chart_text && (
          <pre style={{ margin: '10px 0 2px', padding: 10, background: 'var(--surface-2)',
                         borderRadius: 'var(--r-input)', fontFamily: 'var(--font-mono)',
                         fontSize: 11, lineHeight: '16px', color: 'var(--ink-2)',
                         overflowX: 'auto', whiteSpace: 'pre' }}>{m.chart_text}</pre>
        )}
        {m.tools_used?.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
            {m.tools_used.map(t => (
              <span key={t} style={{ fontSize: 10, padding: '2px 7px', borderRadius: 999,
                                      background: 'var(--primary-soft)', color: 'var(--primary-deep)',
                                      fontFamily: 'var(--font-mono)' }}>{t}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { AskScreen });
