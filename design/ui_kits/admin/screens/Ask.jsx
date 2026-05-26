// Ask — chat widget with the data agent.
// Maps to POST /admin/ask.

function AskScreen() {
  const c = voiceColors;
  const seed = [
    { from: 'bot', text: 'Я могу ответить на вопрос о ваших отзывах, метриках или клиентах. Спросите что-нибудь.', ts: '14:01' },
  ];
  const [messages, setMessages] = React.useState(seed);
  const [input, setInput] = React.useState('');
  const [thinking, setThinking] = React.useState(false);
  const scrollRef = React.useRef(null);

  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, thinking]);

  function send(text) {
    if (!text.trim()) return;
    const now = new Date();
    const ts = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
    setMessages(m => [...m, { from: 'user', text, ts }]);
    setInput('');
    setThinking(true);
    setTimeout(() => {
      setThinking(false);
      setMessages(m => [...m, mockReply(text, ts)]);
    }, 900);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div ref={scrollRef} style={{ flex: 1, overflow: 'auto', padding: '14px 14px 14px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {messages.map((m, i) => (
            <Bubble key={i} m={m} c={c}/>
          ))}
          {thinking && (
            <div style={{
              alignSelf: 'flex-start', padding: '10px 12px', background: c.surface,
              border: `1px solid ${c.border}`, borderRadius: '14px 14px 14px 4px',
              display: 'inline-flex', gap: 4, alignItems: 'center',
            }}>
              {[0,1,2].map(i => (
                <span key={i} style={{
                  width: 6, height: 6, borderRadius: 999, background: c.warning,
                  animation: `bob 1.2s ${i*0.15}s infinite ease-in-out`,
                }}/>
              ))}
            </div>
          )}
        </div>

        {messages.length === 1 && !thinking && (
          <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ font: '500 11px/14px Geist, sans-serif', color: c.text3,
                          textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>
              Suggested
            </div>
            {[
              'Сколько негативных отзывов на этой неделе?',
              'Топ-3 темы по росту',
              'Покажи клиентов с sentiment ниже 0.3',
            ].map(s => (
              <button key={s} onClick={() => send(s)} style={{
                textAlign: 'left', padding: '10px 12px', borderRadius: 10,
                background: c.surface, border: `1px solid ${c.border}`, color: c.text1,
                font: '400 14px/20px Geist, sans-serif', cursor: 'pointer',
              }}>{s}</button>
            ))}
          </div>
        )}
      </div>

      {/* Composer — sits above the 56-px bottom-nav (plus its 6/12-px padding
          and the iOS safe-area inset). Keep the offset in sync with
          BottomNav in components.jsx. */}
      <div style={{
        padding: '8px 12px 12px', borderTop: `1px solid ${c.border}`,
        background: c.surface, display: 'flex', gap: 8, alignItems: 'center',
        marginBottom: 'calc(64px + env(safe-area-inset-bottom, 0px))',
      }}>
        <div style={{
          flex: 1, display: 'flex', alignItems: 'center', gap: 8,
          background: c.surface2, border: `1px solid ${c.border}`, borderRadius: 10,
          padding: '0 12px', height: 40,
        }}>
          <input value={input} onChange={e => setInput(e.target.value)}
                 onKeyDown={e => e.key === 'Enter' && send(input)}
                 placeholder="Спросите что-нибудь о ваших отзывах…"
                 style={{
                   flex: 1, border: 0, outline: 0, background: 'transparent',
                   font: '400 15px/20px Geist, sans-serif', color: c.text1, minWidth: 0,
                 }}/>
        </div>
        <button onClick={() => send(input)} disabled={!input.trim()} style={{
          width: 40, height: 40, borderRadius: 10, border: 0, cursor: input.trim() ? 'pointer' : 'default',
          background: input.trim() ? c.primaryHover : c.surface2,
          color: input.trim() ? '#fff' : c.text3,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        }}><Icon name="send" size={16}/></button>
      </div>
      <style>{`@keyframes bob { 0%,60%,100% { transform: translateY(0); opacity: 0.4; } 30% { transform: translateY(-3px); opacity: 1; } }`}</style>
    </div>
  );
}

function Bubble({ m, c }) {
  const isUser = m.from === 'user';
  return (
    <div style={{
      alignSelf: isUser ? 'flex-end' : 'flex-start',
      maxWidth: '82%',
      background: isUser ? c.primaryHover : c.surface,
      color: isUser ? '#fff' : c.text1,
      border: isUser ? 'none' : `1px solid ${c.border}`,
      padding: '10px 12px',
      borderRadius: isUser ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
      font: '400 14px/20px Geist, sans-serif',
    }}>
      {m.chart}
      <div>{m.text}</div>
      <div style={{
        font: '500 11px/14px "Geist Mono", monospace', marginTop: 4,
        color: isUser ? 'rgba(255,255,255,0.7)' : c.text3,
      }}>{m.ts}</div>
    </div>
  );
}

function mockReply(q, ts) {
  const c = voiceColors;
  if (q.toLowerCase().includes('негатив')) {
    return {
      from: 'bot', ts,
      text: 'За последние 7 дней: 23 негативных отзыва из 248 (9.3%). Главная тема — «доставка опаздывает».',
      chart: (
        <div style={{ marginBottom: 8, padding: 8, background: 'rgba(15,23,42,0.03)', borderRadius: 8 }}>
          {topicsNeg.slice(0,3).map(t => (
            <div key={t.name} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <span style={{ width: 96, font: '500 11px/14px Geist, sans-serif', color: c.text2 }}>{t.name}</span>
              <div style={{ flex: 1, height: 5, background: '#fff', borderRadius: 999, overflow: 'hidden' }}>
                <div style={{ width: `${t.share*100}%`, height: '100%', background: c.danger }}/>
              </div>
              <span style={{ width: 22, textAlign: 'right', font: '500 11px/14px "Geist Mono", monospace', color: c.text1 }}>{t.count}</span>
            </div>
          ))}
        </div>
      )
    };
  }
  if (q.toLowerCase().includes('топ')) {
    return { from: 'bot', ts, text: 'Темы с наибольшим ростом: «доставка» (+24%), «UX» (+12%), «цены» (+9%).' };
  }
  return { from: 'bot', ts, text: 'Понял вопрос. Сейчас соберу ответ — это займёт пару секунд.' };
}

Object.assign(window, { AskScreen });
