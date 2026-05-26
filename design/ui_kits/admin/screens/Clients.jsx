// Clients — search + list + sheet-modal deep-dive.
// Maps to GET /admin/clients/{id}.

function ClientsScreen() {
  const c = voiceColors;
  const [q, setQ] = React.useState('');
  const [selected, setSelected] = React.useState(null);
  const filtered = clientsList.filter(cl =>
    cl.name.toLowerCase().includes(q.toLowerCase()) || String(cl.id).includes(q)
  );

  return (
    <div style={{ paddingBottom: 80, position: 'relative' }}>
      {/* Search */}
      <div style={{ padding: '14px 16px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, height: 40, padding: '0 12px',
          borderRadius: 8, border: `1px solid ${c.border}`, background: c.surface,
        }}>
          <Icon name="search" size={16} color={c.text3}/>
          <input value={q} onChange={e => setQ(e.target.value)}
            placeholder="Search by name or #id"
            style={{
              flex: 1, border: 0, outline: 0, background: 'transparent',
              font: '400 15px/20px Geist, sans-serif', color: c.text1, minWidth: 0,
            }}/>
          {q && <button onClick={() => setQ('')} style={iconBtn(c)}><Icon name="close" size={14}/></button>}
        </div>
      </div>

      {/* Result count */}
      <div style={{ padding: '0 16px 8px', font: '500 12px/16px Geist, sans-serif', color: c.text3 }}>
        {filtered.length} clients
      </div>

      {/* List */}
      <div style={{ margin: '0 16px', background: c.surface, border: `1px solid ${c.border}`, borderRadius: 12, overflow: 'hidden' }}>
        {filtered.map((cl, i) => (
          <button key={cl.id} onClick={() => setSelected(cl)} style={{
            display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px',
            background: 'transparent', border: 0, borderBottom: i < filtered.length - 1 ? `1px solid ${c.border}` : 0,
            width: '100%', textAlign: 'left', cursor: 'pointer',
          }}>
            <Avatar initials={cl.initials} tint={cl.tint}/>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                <span style={{ font: '600 14px/18px Geist, sans-serif', color: c.text1 }}>{cl.name}</span>
                <span style={{ font: '500 12px/16px "Geist Mono", monospace', color: c.text3 }}>#{cl.id}</span>
              </div>
              <div style={{ font: '400 13px/18px Geist, sans-serif', color: c.text2, marginTop: 2 }}>
                {cl.sessions} sessions · sentiment {cl.sentiment.toFixed(2)}
              </div>
            </div>
            <Icon name="chevRight" size={18} color={c.text3}/>
          </button>
        ))}
      </div>

      {selected && (
        <ClientSheet client={selected} onClose={() => setSelected(null)}/>
      )}
    </div>
  );
}

function ClientSheet({ client, onClose }) {
  const c = voiceColors;
  return (
    <>
      <div onClick={onClose} style={{
        position: 'absolute', inset: 0, background: 'rgba(15,23,42,0.5)', zIndex: 10,
      }}/>
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0, zIndex: 11,
        background: c.surface, borderRadius: '16px 16px 0 0',
        boxShadow: '0 -24px 48px -12px rgba(15,23,42,0.18)',
        padding: '8px 16px 24px', maxHeight: '85%', overflow: 'auto',
        animation: 'sheet-up 240ms cubic-bezier(0.2,0,0,1)',
      }}>
        <div style={{ width: 36, height: 4, background: c.borderStrong, borderRadius: 999, margin: '6px auto 16px' }}/>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16 }}>
          <Avatar initials={client.initials} tint={client.tint}/>
          <div style={{ flex: 1 }}>
            <div style={{ font: '600 18px/24px Geist, sans-serif', color: c.text1, letterSpacing: '-0.005em' }}>{client.name}</div>
            <div style={{ font: '500 13px/16px "Geist Mono", monospace', color: c.text3 }}>client #{client.id}</div>
          </div>
          <button onClick={onClose} style={iconBtn(c)}><Icon name="close" size={18}/></button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 16 }}>
          {[
            { l: 'Sessions',  v: client.sessions },
            { l: 'Sentiment', v: client.sentiment.toFixed(2) },
            { l: 'Last seen', v: '2 d' },
          ].map(s => (
            <div key={s.l} style={{ padding: '10px 12px', background: c.surface2, borderRadius: 8 }}>
              <div style={{ font: '500 11px/14px Geist, sans-serif', color: c.text3, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{s.l}</div>
              <div style={{ font: '600 16px/20px "Geist Mono", monospace', color: c.text1, marginTop: 4 }}>{s.v}</div>
            </div>
          ))}
        </div>

        <div style={{ font: '600 11px/14px Geist, sans-serif', letterSpacing: '0.08em',
                       textTransform: 'uppercase', color: c.text3, margin: '4px 0 8px' }}>
          Feedback history
        </div>
        <div style={{ background: c.surface, border: `1px solid ${c.border}`, borderRadius: 10, overflow: 'hidden' }}>
          {feedbackItems.slice(0, 3).map((it, i, a) => (
            <div key={it.id} style={{
              display: 'flex', gap: 10, padding: '12px 12px',
              borderBottom: i < a.length - 1 ? `1px solid ${c.border}` : 0,
            }}>
              <span style={{
                width: 6, marginTop: 6, height: 6, borderRadius: 999,
                background: it.sentiment === 'pos' ? c.success : it.sentiment === 'neg' ? c.danger : '#94a3b8',
                flexShrink: 0,
              }}/>
              <div style={{ flex: 1 }}>
                <div style={{ font: '400 13px/18px Geist, sans-serif', color: c.text1 }}>{it.preview}</div>
                <div style={{ font: '500 11px/14px "Geist Mono", monospace', color: c.text3, marginTop: 4 }}>
                  {it.date} · {it.topic}
                </div>
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          <button style={btnSecondary(c)}><Icon name="chat" size={16}/> Message</button>
          <button style={btnPrimary(c)}>Open in Telegram</button>
        </div>
      </div>
      <style>{`@keyframes sheet-up { from { transform: translateY(100%); } to { transform: translateY(0); } }`}</style>
    </>
  );
}

function iconBtn(c) {
  return {
    width: 32, height: 32, borderRadius: 8, border: 0, background: 'transparent',
    color: c.text2, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  };
}
function btnPrimary(c) {
  return {
    flex: 1, height: 40, padding: '0 14px', borderRadius: 8,
    background: c.primaryHover, color: '#fff', border: `1px solid ${c.primaryHover}`,
    font: '500 14px/20px Geist, sans-serif', cursor: 'pointer',
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
  };
}
function btnSecondary(c) {
  return {
    flex: 1, height: 40, padding: '0 14px', borderRadius: 8,
    background: c.surface, color: c.text1, border: `1px solid ${c.border}`,
    font: '500 14px/20px Geist, sans-serif', cursor: 'pointer',
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
  };
}

Object.assign(window, { ClientsScreen, ClientSheet });
