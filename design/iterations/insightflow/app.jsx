// InsightFlow Mini App — router + Tweaks panel.
// Tab labels and titles mirror the real Vite+React admin app
// (mrkszn/telegram-waiter-admin-miniapp). This file is a
// design reference paint (inline React+Babel), NOT production code.

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "brandColor": "#7c3aed",
  "headings": "serif",
  "density": "comfortable",
  "dark": false
}/*EDITMODE-END*/;

const BRAND_CLASS = { "#7c3aed": "", "#4f46e5": "brand-indigo", "#0e9aa8": "brand-teal" };

function MiniApp() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [tab, setTab] = React.useState('dashboard');

  // Apply theme to <html> so vars cascade to the phone frame too.
  React.useEffect(() => {
    const el = document.documentElement;
    const cls = [
      BRAND_CLASS[t.brandColor] || '',
      t.headings === 'serif' ? '' : 'headings-sans',
      t.density === 'comfortable' ? '' : 'density-compact',
    ].filter(Boolean).join(' ');
    el.className = cls;
    el.dataset.theme = t.dark ? 'dark' : 'light';
  }, [t.brandColor, t.headings, t.density, t.dark]);

  const titles = { dashboard: 'Главная', metrics: 'Метрики', topics: 'Топики', clients: 'Клиенты', ask: 'Чат' };
  const Screen = ({
    dashboard: DashboardScreen, metrics: MetricsScreen, topics: TopicsScreen,
    clients: ClientsScreen, ask: AskScreen,
  })[tab];

  return (
    <div style={{ background: 'var(--bg)', height: '100%', display: 'flex', flexDirection: 'column',
                  position: 'relative', overflow: 'hidden', fontFamily: 'var(--font-sans)', color: 'var(--ink)' }}>
      <Header
        title={titles[tab]}
        brand={tab === 'dashboard'}
        right={tab === 'dashboard' ? (
          <button style={{ width: 36, height: 36, borderRadius: 8, border: 0, background: 'transparent',
                           color: 'var(--ink)', cursor: 'pointer', position: 'relative',
                           display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="bell" size={20}/>
            <span style={{ position: 'absolute', top: 7, right: 8, width: 8, height: 8, borderRadius: 999,
                           background: 'var(--danger)', border: '2px solid var(--surface)' }}/>
          </button>
        ) : null}
      />

      <div style={{ flex: 1, overflow: 'auto', WebkitOverflowScrolling: 'touch' }}>
        <Screen/>
      </div>

      <BottomNav tab={tab} onTab={setTab}/>

      <TweaksPanel title="Tweaks">
        <TweakSection label="Бренд" />
        <TweakColor label="Акцент" value={t.brandColor}
                    options={["#7c3aed", "#4f46e5", "#0e9aa8"]}
                    onChange={(v) => setTweak('brandColor', v)} />
        <TweakSection label="Типографика" />
        <TweakRadio label="Заголовки" value={t.headings}
                    options={["serif", "sans"]}
                    onChange={(v) => setTweak('headings', v)} />
        <TweakRadio label="Плотность" value={t.density}
                    options={["comfortable", "compact"]}
                    onChange={(v) => setTweak('density', v)} />
        <TweakSection label="Тема" />
        <TweakToggle label="Тёмная" value={t.dark}
                     onChange={(v) => setTweak('dark', v)} />
      </TweaksPanel>
    </div>
  );
}

Object.assign(window, { MiniApp });
