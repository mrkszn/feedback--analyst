// InsightFlow — shared components (CSS-var driven so Tweaks can retheme live).

// --- Icon: thin Lucide-style strokes -------------------------
function Icon({ name, size = 20, color = 'currentColor', strokeWidth = 1.75 }) {
  const paths = {
    home:     <><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></>,
    chart:    <><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></>,
    search:   <><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></>,
    chat:     <><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></>,
    user:     <><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></>,
    back:     <><path d="m15 18-6-6 6-6"/></>,
    more:     <><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></>,
    plus:     <><path d="M12 5v14M5 12h14"/></>,
    check:    <><polyline points="20 6 9 17 4 12"/></>,
    close:    <><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>,
    filter:   <><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></>,
    bell:     <><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></>,
    arrow:    <><path d="M5 12h14M12 5l7 7-7 7"/></>,
    trendUp:  <><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></>,
    trendDn:  <><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></>,
    send:     <><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></>,
    cal:      <><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></>,
    chev:     <><path d="m6 9 6 6 6-6"/></>,
    chevRight:<><path d="m9 18 6-6-6-6"/></>,
    sparkle:  <><path d="M12 3l1.7 4.6L18 9.3l-4.3 1.7L12 15l-1.7-4L6 9.3l4.3-1.7z"/><path d="M19 14l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/></>,
    target:   <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.4"/></>,
    gift:     <><rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/><path d="M12 8S10 3 7.5 3 5 5.5 7 8M12 8s2-5 4.5-5S19 5.5 17 8"/></>,
    segments: <><circle cx="7" cy="7" r="3"/><circle cx="17" cy="7" r="3"/><circle cx="7" cy="17" r="3"/><circle cx="17" cy="17" r="3"/></>,
    bulb:     <><path d="M9 18h6M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1V17h6v-.2c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z"/></>,
    heart:    <><path d="M19 14c1.5-1.5 3-3.4 3-5.5A4.5 4.5 0 0 0 12 5 4.5 4.5 0 0 0 2 8.5c0 2.1 1.5 4 3 5.5l7 7z"/></>,
    clock:    <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      {paths[name] || null}
    </svg>
  );
}

// --- Brand mark: gradient tile + serif "i" -------------------
function BrandMark({ size = 28, radius = 8 }) {
  return (
    <span style={{
      width: size, height: size, borderRadius: radius, display: 'grid', placeItems: 'center',
      background: 'var(--grad-brand)', color: '#fff',
      fontFamily: 'var(--font-head)', fontStyle: 'italic',
      fontSize: size * 0.62, lineHeight: 1,
      boxShadow: '0 4px 12px -3px color-mix(in srgb, var(--primary) 55%, transparent)',
      flexShrink: 0,
    }}>i</span>
  );
}

// --- Header --------------------------------------------------
function Header({ title, onBack, right, brand }) {
  return (
    <div style={{
      height: 46, padding: '0 8px', display: 'flex', alignItems: 'center',
      background: 'var(--surface)', borderBottom: '1px solid var(--line)',
      position: 'sticky', top: 0, zIndex: 5,
    }}>
      {onBack ? (
        <button onClick={onBack} style={{
          width: 36, height: 36, borderRadius: 8, border: 0, background: 'transparent',
          display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--ink)', cursor: 'pointer'
        }}><Icon name="back" size={20}/></button>
      ) : <div style={{ width: 38, display: 'flex', justifyContent: 'center' }}>{brand ? <BrandMark size={26} radius={7}/> : null}</div>}
      <div style={{
        flex: 1, textAlign: 'center', fontWeight: 600, fontSize: 16, lineHeight: '22px',
        color: 'var(--ink)', letterSpacing: '-0.005em',
      }}>{title}</div>
      <div style={{ width: 38, display: 'flex', justifyContent: 'flex-end' }}>{right}</div>
    </div>
  );
}

// --- BottomNav ----------------------------------------------
function BottomNav({ tab, onTab }) {
  const items = [
    { id: 'dashboard', icon: 'home',     label: 'Главная' },
    { id: 'metrics',   icon: 'chart',    label: 'Метрики' },
    { id: 'topics',    icon: 'sparkle',  label: 'Топики' },
    { id: 'clients',   icon: 'user',     label: 'Клиенты' },
    { id: 'ask',       icon: 'chat',     label: 'Чат' },
  ];
  return (
    <div style={{
      position: 'absolute', left: 0, right: 0, bottom: 0,
      background: 'color-mix(in srgb, var(--surface) 88%, transparent)',
      backdropFilter: 'blur(14px)', WebkitBackdropFilter: 'blur(14px)',
      borderTop: '1px solid var(--line)',
      boxShadow: 'var(--shadow-2, 0 -4px 12px rgba(15,23,42,0.05))',
      paddingBottom: 'env(safe-area-inset-bottom, 0px)',
      display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', zIndex: 4,
    }}>
      {items.map(it => {
        const active = tab === it.id;
        return (
          <button key={it.id} onClick={() => onTab(it.id)} style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            gap: 4, padding: '9px 0 11px', border: 0, background: 'transparent', cursor: 'pointer',
            color: active ? 'var(--primary-hover)' : 'var(--muted-2)',
            fontWeight: 500, fontSize: 11, lineHeight: '14px', fontFamily: 'var(--font-sans)',
          }}>
            <Icon name={it.icon} size={22} strokeWidth={active ? 2.25 : 1.75}/>
            {it.label}
          </button>
        );
      })}
    </div>
  );
}

// --- KPICard (serif value) ----------------------------------
function KPICard({ label, value, suffix, delta, deltaKind = 'up', spark }) {
  const deltaColor = { up: 'var(--success)', dn: 'var(--danger)', flat: 'var(--warning)' }[deltaKind];
  const arrow = { up: '▲', dn: '▼', flat: '●' }[deltaKind];
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--line)',
      borderRadius: 'var(--r-card)', padding: 'var(--card-pad)',
    }}>
      <div style={{ fontWeight: 600, fontSize: 11, lineHeight: '14px', color: 'var(--muted)',
                    textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
      <div className="serif-num" style={{ fontSize: 'var(--kpi-size)', lineHeight: 1, color: 'var(--ink)', marginTop: 8 }}>
        {value}{suffix && <span style={{ fontSize: '0.5em', fontStyle: 'normal', fontFamily: 'var(--font-mono)', color: 'var(--muted)', marginLeft: 2 }}>{suffix}</span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 }}>
        <span style={{ fontWeight: 500, fontSize: 12, lineHeight: '16px', fontFamily: 'var(--font-mono)', color: deltaColor }}>{arrow} {delta}</span>
        {spark}
      </div>
    </div>
  );
}

// --- Spark line ---------------------------------------------
function Spark({ points, color = 'var(--success)' }) {
  return (
    <svg width="56" height="18" viewBox="0 0 60 22" fill="none">
      <polyline points={points} stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// --- Filter Chip --------------------------------------------
function Chip({ children, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      display: 'inline-flex', alignItems: 'center', height: 30, padding: '0 13px',
      borderRadius: 999, border: `1px solid ${active ? 'var(--ink)' : 'var(--line)'}`,
      background: active ? 'var(--ink)' : 'var(--surface)',
      color: active ? 'var(--surface)' : 'var(--ink)',
      fontWeight: 500, fontSize: 13, lineHeight: '18px', fontFamily: 'var(--font-sans)',
      cursor: 'pointer', whiteSpace: 'nowrap',
    }}>{children}</button>
  );
}

// --- Avatar bubble ------------------------------------------
function Avatar({ initials, tint = 'violet', size = 36 }) {
  const tints = {
    violet:  { bg: 'var(--primary-soft)', fg: 'var(--primary-deep)' },
    rose:    { bg: 'color-mix(in srgb, var(--rose) 18%, var(--surface))',  fg: 'var(--danger)' },
    slate:   { bg: 'var(--surface-2)',    fg: 'var(--muted)' },
    cyan:    { bg: 'color-mix(in srgb, var(--accent) 16%, var(--surface))', fg: 'color-mix(in srgb, var(--accent) 70%, #000)' },
    amber:   { bg: 'color-mix(in srgb, var(--amber) 20%, var(--surface))', fg: 'var(--warning)' },
    mint:    { bg: 'color-mix(in srgb, var(--mint) 20%, var(--surface))',  fg: 'var(--success)' },
  };
  const t = tints[tint] || tints.violet;
  return (
    <div style={{
      width: size, height: size, borderRadius: 999, background: t.bg, color: t.fg,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontWeight: 600, fontSize: size * 0.36, fontFamily: 'var(--font-sans)', flexShrink: 0,
    }}>{initials}</div>
  );
}

// --- FeedbackRow --------------------------------------------
function FeedbackRow({ item, onClick, last }) {
  const tint = item.sentiment === 'pos' ? 'violet' : item.sentiment === 'neg' ? 'rose' : 'slate';
  const dot = { pos: 'var(--success)', neg: 'var(--danger)', neu: 'var(--muted-2)' }[item.sentiment];
  return (
    <button onClick={onClick} style={{
      display: 'flex', gap: 12, alignItems: 'center', padding: 'var(--row-pad) 14px',
      background: 'transparent', border: 0,
      borderBottom: last ? 0 : '1px solid var(--line)', width: '100%', textAlign: 'left', cursor: 'pointer',
    }}>
      <Avatar initials={item.initials} tint={tint}/>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
          <span style={{ fontWeight: 600, fontSize: 14, lineHeight: '18px', color: 'var(--ink)' }}>{item.name}</span>
          <span style={{ fontWeight: 500, fontSize: 12, lineHeight: '16px', fontFamily: 'var(--font-mono)', color: 'var(--muted-2)' }}>#{item.id}</span>
        </div>
        <div style={{
          fontSize: 13, lineHeight: '18px', color: 'var(--muted)',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginTop: 2,
        }}>{item.preview}</div>
      </div>
      <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
        <span style={{ fontWeight: 500, fontSize: 12, lineHeight: '14px', fontFamily: 'var(--font-mono)', color: 'var(--muted-2)' }}>{item.time}</span>
        <span style={{ width: 6, height: 6, borderRadius: 999, background: dot }}/>
      </div>
    </button>
  );
}

// --- Section header (overline + serif index) ----------------
function SectionHead({ children, action, index }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: 'calc(var(--section-gap) + 2px) 16px 8px',
    }}>
      <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 8 }}>
        {index && <span className="serif-num" style={{ fontSize: 15, color: 'var(--primary)', opacity: .6 }}>{index}</span>}
        <span style={{
          fontWeight: 600, fontSize: 11, lineHeight: '14px', letterSpacing: '0.08em',
          textTransform: 'uppercase', color: 'var(--muted)', fontFamily: 'var(--font-sans)',
        }}>{children}</span>
      </span>
      {action}
    </div>
  );
}

// --- Card wrapper -------------------------------------------
function Card({ children, style, pad = true }) {
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--line)',
      borderRadius: 'var(--r-card)', overflow: 'hidden',
      padding: pad ? 'var(--card-pad)' : 0, ...style,
    }}>{children}</div>
  );
}

// --- Recommended action row ---------------------------------
function RecCard({ n, children, last }) {
  return (
    <div style={{
      display: 'flex', gap: 11, alignItems: 'flex-start', padding: 'var(--row-pad) 14px',
      borderBottom: last ? 0 : '1px solid var(--line)',
    }}>
      <span className="serif-num" style={{
        width: 26, height: 26, flexShrink: 0, display: 'grid', placeItems: 'center',
        borderRadius: 8, background: 'var(--primary-soft)', color: 'var(--primary-deep)',
        fontSize: 17,
      }}>{n}</span>
      <span style={{ flex: 1, fontSize: 13.5, lineHeight: '19px', color: 'var(--ink-2)' }}>{children}</span>
    </div>
  );
}

// --- Tag pill -----------------------------------------------
function Tag({ children }) {
  return (
    <span style={{
      fontSize: 11, lineHeight: '16px', padding: '3px 9px', borderRadius: 999,
      background: 'var(--surface)', border: '1px solid var(--line)', color: 'var(--ink-2)',
      fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap',
    }}>{children}</span>
  );
}

// --- ghost text link ----------------------------------------
function GhostLink({ children, onClick }) {
  return (
    <button onClick={onClick} style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      background: 'transparent', border: 0, padding: '2px 4px',
      color: 'var(--muted)', fontWeight: 500, fontSize: 12, lineHeight: '16px',
      fontFamily: 'var(--font-sans)', cursor: 'pointer',
    }}>{children}</button>
  );
}

Object.assign(window, {
  Icon, BrandMark, Header, BottomNav, KPICard, Spark, Chip, Avatar,
  FeedbackRow, SectionHead, Card, RecCard, Tag, GhostLink,
});
