// Admin / Voice — shared components.
// All Geist-based, slate + violet, no shadows on cards.

const colors = {
  bg: '#f8fafc',
  surface: '#ffffff',
  surface2: '#f1f5f9',
  border: '#e2e8f0',
  borderStrong: '#cbd5e1',
  text1: '#0f172a',
  text2: '#475569',
  text3: '#64748b',
  primary: '#7c3aed',
  primaryHover: '#6d28d9',
  primarySoft: '#ede9fe',
  primaryOn: '#ffffff',
  success: '#059669',
  successSoft: '#ecfdf5',
  danger: '#e11d48',
  dangerSoft: '#fff1f2',
  warning: '#f59e0b',
  warningSoft: '#fffbeb',
  info: '#0ea5e9',
};

// --- Icon: thin Lucide-style stroke icons inline --------------
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
    smile:    <><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></>,
    frown:    <><circle cx="12" cy="12" r="10"/><path d="M16 16s-1.5-2-4-2-4 2-4 2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      {paths[name] || null}
    </svg>
  );
}

// --- Header with optional Telegram back ----------------------
function Header({ title, onBack, right }) {
  return (
    <div style={{
      height: 44, padding: '0 8px', display: 'flex', alignItems: 'center',
      background: colors.surface, borderBottom: `1px solid ${colors.border}`,
      position: 'sticky', top: 0, zIndex: 5,
    }}>
      {onBack ? (
        <button onClick={onBack} style={{
          width: 36, height: 36, borderRadius: 8, border: 0, background: 'transparent',
          display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.text1, cursor: 'pointer'
        }}><Icon name="back" size={20}/></button>
      ) : <div style={{ width: 36 }}/>}
      <div style={{
        flex: 1, textAlign: 'center', font: '600 16px/22px Geist, sans-serif',
        color: colors.text1, letterSpacing: '-0.005em'
      }}>{title}</div>
      <div style={{ width: 36, display: 'flex', justifyContent: 'flex-end' }}>{right}</div>
    </div>
  );
}

// --- BottomNav ----------------------------------------------
function BottomNav({ tab, onTab }) {
  const items = [
    { id: 'dashboard', icon: 'home',   label: 'Overview' },
    { id: 'metrics',   icon: 'chart',  label: 'Metrics' },
    { id: 'topics',    icon: 'sparkle',label: 'Topics' },
    { id: 'clients',   icon: 'search', label: 'Clients' },
    { id: 'ask',       icon: 'chat',   label: 'Ask' },
  ];
  return (
    <div style={{
      position: 'absolute', left: 0, right: 0, bottom: 0,
      background: 'rgba(255,255,255,0.92)',
      backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
      borderTop: `1px solid ${colors.border}`,
      boxShadow: '0 -4px 12px rgba(15,23,42,0.04)',
      paddingBottom: 'env(safe-area-inset-bottom, 0px)',
      display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', zIndex: 4,
    }}>
      {items.map(it => {
        const active = tab === it.id;
        return (
          <button key={it.id} onClick={() => onTab(it.id)} style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            gap: 4, padding: '10px 0 12px', border: 0, background: 'transparent', cursor: 'pointer',
            color: active ? colors.primaryHover : colors.text3,
            font: '500 11px/14px Geist, sans-serif',
          }}>
            <Icon name={it.icon} size={22} strokeWidth={active ? 2.25 : 1.75}/>
            {it.label}
          </button>
        );
      })}
    </div>
  );
}

// --- KPICard -------------------------------------------------
function KPICard({ label, value, delta, deltaKind = 'up', spark }) {
  const deltaColor = { up: colors.success, dn: colors.danger, flat: '#b45309' }[deltaKind];
  const arrow = { up: '▲', dn: '▼', flat: '●' }[deltaKind];
  return (
    <div style={{
      background: colors.surface, border: `1px solid ${colors.border}`,
      borderRadius: 12, padding: 14,
    }}>
      <div style={{ font: '500 11px/14px Geist, sans-serif', color: colors.text3,
                    textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
      <div style={{ font: '600 24px/28px "Geist Mono", monospace', color: colors.text1,
                    letterSpacing: '-0.01em', marginTop: 8, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 6 }}>
        <span style={{ font: '500 12px/16px "Geist Mono", monospace', color: deltaColor }}>{arrow} {delta}</span>
        {spark}
      </div>
    </div>
  );
}

// --- Spark line ---------------------------------------------
function Spark({ points, color = colors.success }) {
  return (
    <svg width="56" height="18" viewBox="0 0 60 22" fill="none">
      <polyline points={points} stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// --- Filter Chip --------------------------------------------
function Chip({ children, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      display: 'inline-flex', alignItems: 'center', height: 30, padding: '0 12px',
      borderRadius: 999, border: `1px solid ${active ? colors.text1 : colors.border}`,
      background: active ? colors.text1 : colors.surface,
      color: active ? '#fff' : colors.text1,
      font: '500 13px/18px Geist, sans-serif', cursor: 'pointer',
      whiteSpace: 'nowrap',
    }}>{children}</button>
  );
}

// --- Avatar bubble ------------------------------------------
function Avatar({ initials, tint = 'violet' }) {
  const tints = {
    violet: { bg: '#ede9fe', fg: '#5b21b6' },
    rose:   { bg: '#fff1f2', fg: '#be123c' },
    slate:  { bg: colors.surface2, fg: colors.text2 },
    indigo: { bg: '#e0e7ff', fg: '#3730a3' },
    emerald:{ bg: '#ecfdf5', fg: '#047857' },
  };
  const t = tints[tint] || tints.violet;
  return (
    <div style={{
      width: 36, height: 36, borderRadius: 999, background: t.bg, color: t.fg,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      font: '600 13px/16px Geist, sans-serif', flexShrink: 0,
    }}>{initials}</div>
  );
}

// --- FeedbackRow --------------------------------------------
function FeedbackRow({ item, onClick }) {
  const tint = item.sentiment === 'pos' ? 'violet' : item.sentiment === 'neg' ? 'rose' : 'slate';
  const dot = { pos: colors.success, neg: colors.danger, neu: '#94a3b8' }[item.sentiment];
  return (
    <button onClick={onClick} style={{
      display: 'flex', gap: 12, alignItems: 'center', padding: '12px 14px',
      borderBottom: `1px solid ${colors.border}`, background: 'transparent',
      border: 0, borderBottom: `1px solid ${colors.border}`, width: '100%', textAlign: 'left', cursor: 'pointer',
    }}>
      <Avatar initials={item.initials} tint={tint}/>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
          <span style={{ font: '600 14px/18px Geist, sans-serif', color: colors.text1 }}>{item.name}</span>
          <span style={{ font: '500 12px/16px "Geist Mono", monospace', color: colors.text3 }}>#{item.id}</span>
        </div>
        <div style={{
          font: '400 13px/18px Geist, sans-serif', color: colors.text2,
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginTop: 2,
        }}>{item.preview}</div>
      </div>
      <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
        <span style={{ font: '500 12px/14px "Geist Mono", monospace', color: colors.text3 }}>{item.time}</span>
        <span style={{ width: 6, height: 6, borderRadius: 999, background: dot }}/>
      </div>
    </button>
  );
}

// --- Section header (overline) ------------------------------
function SectionHead({ children, action }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '20px 16px 8px',
    }}>
      <span style={{
        font: '600 11px/14px Geist, sans-serif', letterSpacing: '0.08em',
        textTransform: 'uppercase', color: colors.text3,
      }}>{children}</span>
      {action}
    </div>
  );
}

Object.assign(window, {
  voiceColors: colors, Icon, Header, BottomNav, KPICard, Spark,
  Chip, Avatar, FeedbackRow, SectionHead,
});
