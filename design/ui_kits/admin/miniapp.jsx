// Main router for the Voice / Admin Mini App.
// Drives 5 tabs + a detail sheet. App shell wraps everything.

function MiniApp() {
  const c = voiceColors;
  const [tab, setTab] = React.useState('dashboard');
  const [detail, setDetail] = React.useState(null);   // feedback item opened from any list

  const titles = {
    dashboard: 'Voice · Overview',
    metrics:   'Metrics',
    topics:    'Topics',
    clients:   'Clients',
    ask:       'Ask',
  };

  const Screen = ({
    dashboard: DashboardScreen,
    metrics:   MetricsScreen,
    topics:    TopicsScreen,
    clients:   ClientsScreen,
    ask:       AskScreen,
  })[tab];

  return (
    <div style={{
      background: c.bg, height: '100%', display: 'flex', flexDirection: 'column',
      position: 'relative', overflow: 'hidden',
      fontFamily: 'Geist, system-ui, sans-serif',
    }}>
      <Header
        title={titles[tab]}
        right={tab === 'dashboard' ? (
          <button style={{
            width: 36, height: 36, borderRadius: 8, border: 0, background: 'transparent',
            color: c.text1, cursor: 'pointer', position: 'relative',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Icon name="bell" size={20}/>
            <span style={{
              position: 'absolute', top: 7, right: 8, width: 8, height: 8,
              borderRadius: 999, background: c.danger, border: '2px solid white',
            }}/>
          </button>
        ) : null}
      />

      <div style={{ flex: 1, overflow: 'auto', WebkitOverflowScrolling: 'touch' }}>
        <Screen onOpenItem={setDetail}/>
      </div>

      <BottomNav tab={tab} onTab={(t) => { setDetail(null); setTab(t); }}/>

      {detail && <FeedbackDetail item={detail} onClose={() => setDetail(null)}/>}
    </div>
  );
}

function FeedbackDetail({ item, onClose }) {
  const c = voiceColors;
  return (
    <>
      <div onClick={onClose} style={{
        position: 'absolute', inset: 0, background: 'rgba(15,23,42,0.5)', zIndex: 10,
      }}/>
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0, zIndex: 11,
        background: c.surface, borderRadius: '16px 16px 0 0',
        padding: '8px 16px 24px', maxHeight: '80%', overflow: 'auto',
        animation: 'sheet-up 240ms cubic-bezier(0.2,0,0,1)',
        boxShadow: '0 -24px 48px -12px rgba(15,23,42,0.18)',
      }}>
        <div style={{ width: 36, height: 4, background: c.borderStrong, borderRadius: 999, margin: '6px auto 16px' }}/>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16 }}>
          <Avatar initials={item.initials}/>
          <div style={{ flex: 1 }}>
            <div style={{ font: '600 16px/20px Geist, sans-serif', color: c.text1 }}>{item.name}</div>
            <div style={{ font: '500 12px/16px "Geist Mono", monospace', color: c.text3 }}>#{item.id} · {item.date}</div>
          </div>
          <span style={{
            padding: '2px 8px', borderRadius: 4, font: '600 11px/16px Geist, sans-serif',
            background: item.sentiment === 'pos' ? '#ecfdf5' : item.sentiment === 'neg' ? '#fff1f2' : c.surface2,
            color: item.sentiment === 'pos' ? '#047857' : item.sentiment === 'neg' ? '#be123c' : c.text2,
            border: `1px solid ${item.sentiment === 'pos' ? '#a7f3d0' : item.sentiment === 'neg' ? '#fecdd3' : c.border}`,
          }}>{item.sentiment === 'pos' ? 'Positive' : item.sentiment === 'neg' ? 'Negative' : 'Neutral'}</span>
        </div>

        <div style={{
          padding: 12, background: c.surface2, borderRadius: 10,
          font: '400 15px/22px Geist, sans-serif', color: c.text1,
        }}>“{item.preview}”</div>

        <div style={{ display: 'flex', gap: 12, marginTop: 16, marginBottom: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ font: '500 11px/14px Geist, sans-serif', color: c.text3, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Topic</div>
            <div style={{ font: '500 14px/18px Geist, sans-serif', color: c.text1, marginTop: 4 }}>{item.topic}</div>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ font: '500 11px/14px Geist, sans-serif', color: c.text3, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Rating</div>
            <div style={{ font: '500 14px/18px Geist, sans-serif', color: c.text1, marginTop: 4 }}>{item.rating ? `${item.rating} / 5` : '—'}</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <button style={btnSecondaryR(c)}><Icon name="chat" size={16}/> Reply</button>
          <button style={btnPrimaryR(c)}>Open client</button>
        </div>
      </div>
    </>
  );
}

function btnPrimaryR(c) {
  return {
    flex: 1, height: 40, padding: '0 14px', borderRadius: 8,
    background: c.primaryHover, color: '#fff', border: 0,
    font: '500 14px/20px Geist, sans-serif', cursor: 'pointer',
  };
}
function btnSecondaryR(c) {
  return {
    flex: 1, height: 40, padding: '0 14px', borderRadius: 8,
    background: c.surface, color: c.text1, border: `1px solid ${c.border}`,
    font: '500 14px/20px Geist, sans-serif', cursor: 'pointer',
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
  };
}

Object.assign(window, { MiniApp });
