// Mock data — shaped exactly like the FastAPI admin backend
// (apps/backend/app/schemas/admin.py). Atelier Brun (HoReCa) sample fill.

// --- OverviewResponse ----------------------------------------
const overview = {
  sessions_count: 1248,
  avg_sentiment: 0.42,
  top_positive_topics: [
    { topic: 'Сервис',        count: 86, avg_sentiment:  0.82 },
    { topic: 'Качество еды',  count: 71, avg_sentiment:  0.74 },
    { topic: 'Атмосфера',     count: 58, avg_sentiment:  0.62 },
    { topic: 'Сезонное меню', count: 39, avg_sentiment:  0.58 },
    { topic: 'Столик у окна', count: 24, avg_sentiment:  0.71 },
  ],
  top_negative_topics: [
    { topic: 'Время ожидания', count: 41, avg_sentiment: -0.62 },
    { topic: 'Доставка',       count: 33, avg_sentiment: -0.54 },
    { topic: 'Десерты',        count: 23, avg_sentiment: -0.41 },
    { topic: 'Шум в зале',     count: 14, avg_sentiment: -0.38 },
    { topic: 'Парковка',       count:  9, avg_sentiment: -0.46 },
  ],
};

// --- Date presets --------------------------------------------
const DATE_PRESETS = [
  { value: '24h', label: '24 ч' },
  { value: '7d',  label: '7 дней' },
  { value: '30d', label: '30 дней' },
  { value: '90d', label: '90 дней' },
];

// --- MetricsResponse per metric_key --------------------------
const METRIC_KEYS = [
  { value: 'rating',            label: 'Оценка' },
  { value: 'satisfaction',      label: 'Удовлетворённость' },
  { value: 'service_quality',   label: 'Качество сервиса' },
  { value: 'wait_time_minutes', label: 'Время ожидания' },
  { value: 'would_return',      label: 'Готовность вернуться' },
];

const DAYS_RU = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];

const metricsByKey = {
  rating: {
    metric_key: 'rating', expected_type: 'number',
    points: [
      { bucket: 'Пн', count: 28, avg: 4.2 }, { bucket: 'Вт', count: 32, avg: 4.4 },
      { bucket: 'Ср', count: 41, avg: 4.5 }, { bucket: 'Чт', count: 36, avg: 4.3 },
      { bucket: 'Пт', count: 58, avg: 3.9 }, { bucket: 'Сб', count: 64, avg: 4.7 },
      { bucket: 'Вс', count: 49, avg: 4.6 },
    ],
    distribution: null, total: 308, unknown: null, enum_values: null,
  },
  satisfaction: {
    metric_key: 'satisfaction', expected_type: 'number',
    points: [
      { bucket: 'Пн', count: 26, avg: 0.62 }, { bucket: 'Вт', count: 30, avg: 0.66 },
      { bucket: 'Ср', count: 38, avg: 0.71 }, { bucket: 'Чт', count: 33, avg: 0.69 },
      { bucket: 'Пт', count: 54, avg: 0.58 }, { bucket: 'Сб', count: 60, avg: 0.80 },
      { bucket: 'Вс', count: 47, avg: 0.82 },
    ],
    distribution: null, total: 288, unknown: null, enum_values: null,
  },
  service_quality: {
    metric_key: 'service_quality', expected_type: 'enum',
    points: null,
    distribution: [
      { value: 'excellent', count: 124, pct: 0.51 },
      { value: 'good',      count:  78, pct: 0.32 },
      { value: 'fair',      count:  29, pct: 0.12 },
      { value: 'poor',      count:  12, pct: 0.05 },
    ],
    total: 243, unknown: 8, enum_values: ['excellent','good','fair','poor'],
  },
  wait_time_minutes: {
    metric_key: 'wait_time_minutes', expected_type: 'number',
    points: [
      { bucket: 'Пн', count: 22, avg: 14 }, { bucket: 'Вт', count: 25, avg: 16 },
      { bucket: 'Ср', count: 31, avg: 18 }, { bucket: 'Чт', count: 28, avg: 19 },
      { bucket: 'Пт', count: 46, avg: 27 }, { bucket: 'Сб', count: 52, avg: 22 },
      { bucket: 'Вс', count: 38, avg: 20 },
    ],
    distribution: null, total: 242, unknown: null, enum_values: null,
  },
  would_return: {
    metric_key: 'would_return', expected_type: 'enum',
    points: null,
    distribution: [
      { value: 'yes',   count: 198, pct: 0.78 },
      { value: 'maybe', count:  36, pct: 0.14 },
      { value: 'no',    count:  20, pct: 0.08 },
    ],
    total: 254, unknown: 14, enum_values: ['yes','maybe','no'],
  },
};

const ENUM_LABELS = {
  excellent: 'отлично', good: 'хорошо', fair: 'средне', poor: 'плохо',
  yes: 'да', no: 'нет', maybe: 'возможно',
};

// --- TopicsResponse per tone ---------------------------------
const topicsByTone = {
  positive: [
    { topic: 'Сервис',        count: 86, avg_sentiment:  0.82 },
    { topic: 'Качество еды',  count: 71, avg_sentiment:  0.74 },
    { topic: 'Атмосфера',     count: 58, avg_sentiment:  0.62 },
    { topic: 'Сезонное меню', count: 39, avg_sentiment:  0.58 },
    { topic: 'Столик у окна', count: 24, avg_sentiment:  0.71 },
  ],
  negative: [
    { topic: 'Время ожидания', count: 41, avg_sentiment: -0.62 },
    { topic: 'Доставка',       count: 33, avg_sentiment: -0.54 },
    { topic: 'Десерты',        count: 23, avg_sentiment: -0.41 },
    { topic: 'Шум в зале',     count: 14, avg_sentiment: -0.38 },
    { topic: 'Парковка',       count:  9, avg_sentiment: -0.46 },
  ],
};

// --- Semantic search ----------------------------------------
// One source of truth — clients (telegram_id keyed) + their sessions.
const clientProfiles = {
  1042: {
    telegram_id: 1042, name: 'Анна Бергер',
    sessions_count: 17, last_session_at: '2026-06-01T14:02:00Z',
    avg_sentiment: 0.82,
    top_topics: [
      { topic: 'Сервис',        count: 9,  avg_sentiment:  0.86 },
      { topic: 'Атмосфера',     count: 6,  avg_sentiment:  0.78 },
      { topic: 'Столик у окна', count: 4,  avg_sentiment:  0.82 },
      { topic: 'Сезонное меню', count: 3,  avg_sentiment:  0.71 },
    ],
    recent_cards: [
      { topic: 'Сервис',    sentiment: 'positive', summary: 'Официант помнит предпочтения — приятно', rating: 5 },
      { topic: 'Атмосфера', sentiment: 'positive', summary: 'Любит столик у окна, тихо и уютно', rating: 5 },
      { topic: 'Десерты',   sentiment: 'neutral',  summary: 'Замечает долгое ожидание десерта в пятницу', rating: 3 },
    ],
  },
  1286: {
    telegram_id: 1286, name: 'Дмитрий Ковач',
    sessions_count: 8, last_session_at: '2026-05-23T13:48:00Z',
    avg_sentiment: -0.34,
    top_topics: [
      { topic: 'Время ожидания', count: 4, avg_sentiment: -0.74 },
      { topic: 'Десерты',        count: 3, avg_sentiment: -0.51 },
      { topic: 'Сервис',         count: 1, avg_sentiment:  0.22 },
    ],
    recent_cards: [
      { topic: 'Время ожидания', sentiment: 'negative', summary: 'Десерт ждали 25 минут в пятницу вечером', rating: 2 },
      { topic: 'Время ожидания', sentiment: 'negative', summary: 'Кухня не справлялась, повторно', rating: 2 },
    ],
  },
  1284: {
    telegram_id: 1284, name: 'Павел Рот',
    sessions_count: 19, last_session_at: '2026-06-04T13:05:00Z',
    avg_sentiment: 0.91,
    top_topics: [
      { topic: 'Доставка',     count: 11, avg_sentiment: 0.92 },
      { topic: 'Качество еды', count:  6, avg_sentiment: 0.84 },
    ],
    recent_cards: [
      { topic: 'Доставка',     sentiment: 'positive', summary: 'Приехала тёплой и вовремя — приятно удивлён', rating: 5 },
      { topic: 'Качество еды', sentiment: 'positive', summary: 'Острое всё как просил', rating: 5 },
    ],
  },
  1283: {
    telegram_id: 1283, name: 'Ольга Дрозд',
    sessions_count: 6, last_session_at: '2026-05-28T12:10:00Z',
    avg_sentiment: -0.28,
    top_topics: [
      { topic: 'Доставка', count: 4, avg_sentiment: -0.81 },
      { topic: 'Сервис',   count: 1, avg_sentiment:  0.12 },
    ],
    recent_cards: [
      { topic: 'Доставка', sentiment: 'negative', summary: 'Курьер опоздал на полчаса, паста остыла', rating: 2 },
      { topic: 'Доставка', sentiment: 'negative', summary: 'Второй раз за месяц задержка', rating: 2 },
    ],
  },
  1282: {
    telegram_id: 1282, name: 'Игорь Вебер',
    sessions_count: 24, last_session_at: '2026-06-04T11:08:00Z',
    avg_sentiment: 0.88,
    top_topics: [
      { topic: 'Сезонное меню', count: 8, avg_sentiment: 0.92 },
      { topic: 'Атмосфера',     count: 6, avg_sentiment: 0.78 },
      { topic: 'Сервис',        count: 4, avg_sentiment: 0.71 },
    ],
    recent_cards: [
      { topic: 'Сезонное меню', sentiment: 'positive', summary: 'Новое меню — отдельный восторг', rating: 5 },
      { topic: 'Атмосфера',     sentiment: 'positive', summary: 'Приходит с компанией, любит зал', rating: 5 },
    ],
  },
  1280: {
    telegram_id: 1280, name: 'Давид Хартманн',
    sessions_count: 11, last_session_at: '2026-06-04T09:22:00Z',
    avg_sentiment: 0.90,
    top_topics: [
      { topic: 'Сервис',       count: 7, avg_sentiment: 0.92 },
      { topic: 'Качество еды', count: 3, avg_sentiment: 0.78 },
    ],
    recent_cards: [
      { topic: 'Сервис', sentiment: 'positive', summary: 'Официант вспомнил, что не ест рыбу — мелочь, а приятно', rating: 5 },
    ],
  },
  1081: {
    telegram_id: 1081, name: null,        // anonymous — backend allows null name
    sessions_count: 4, last_session_at: '2026-05-29T10:55:00Z',
    avg_sentiment: 0.18,
    top_topics: [
      { topic: 'Атмосфера', count: 2, avg_sentiment:  0.41 },
      { topic: 'Шум в зале', count: 2, avg_sentiment: -0.32 },
    ],
    recent_cards: [
      { topic: 'Шум в зале', sentiment: 'negative', summary: 'Музыку сделали громковато к вечеру', rating: 3 },
    ],
  },
};

// Pool of semantic hits — each ties a session_id to a client_id.
const semanticHits = [
  { session_id: 's-1287', client_id: 1042, score: 0.94, summary_text: 'Гостья хвалит сервис, помнят её предпочтения, столик у окна — лучшее место в зале', sentiment: 'positive', started_at: '2026-06-04T14:02:00Z' },
  { session_id: 's-1286', client_id: 1286, score: 0.91, summary_text: 'Гость возмущён ожиданием десерта 25 минут в пятницу вечером, кухня не справляется', sentiment: 'negative', started_at: '2026-06-04T13:48:00Z' },
  { session_id: 's-1285', client_id: 1081, score: 0.78, summary_text: 'Атмосфера приятная, но к вечеру музыка слишком громкая, в зале прохладно',                    sentiment: 'neutral',  started_at: '2026-06-04T13:26:00Z' },
  { session_id: 's-1284', client_id: 1284, score: 0.96, summary_text: 'Доставка приехала тёплой и вовремя, повторный клиент очень доволен качеством',             sentiment: 'positive', started_at: '2026-06-04T13:05:00Z' },
  { session_id: 's-1283', client_id: 1283, score: 0.93, summary_text: 'Курьер опоздал на полчаса, паста остыла, жалоба повторяется второй раз за месяц',           sentiment: 'negative', started_at: '2026-06-04T12:10:00Z' },
  { session_id: 's-1282', client_id: 1282, score: 0.88, summary_text: 'Новое сезонное меню — восторг, обещает вернуться с друзьями на выходных',                  sentiment: 'positive', started_at: '2026-06-04T11:08:00Z' },
  { session_id: 's-1281', client_id: 1081, score: 0.71, summary_text: 'Музыку сделали громковато к вечеру, мешает разговаривать',                                  sentiment: 'negative', started_at: '2026-06-04T10:55:00Z' },
  { session_id: 's-1280', client_id: 1280, score: 0.95, summary_text: 'Официант запомнил, что гость не ест рыбу — мелкое внимание, но очень приятно',             sentiment: 'positive', started_at: '2026-06-04T09:22:00Z' },
  { session_id: 's-1279', client_id: 1042, score: 0.83, summary_text: 'Постоянная гостья, любит сезонное меню и тихий вечер',                                      sentiment: 'positive', started_at: '2026-06-02T20:10:00Z' },
  { session_id: 's-1278', client_id: 1286, score: 0.79, summary_text: 'Жалоба на скорость подачи десерта, гость спрашивает можно ли заказать сразу с горячим',     sentiment: 'negative', started_at: '2026-05-30T19:48:00Z' },
];

function searchSemantic(query) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  // Keyword-based ranking against summary + sentiment + topic hints.
  const tokens = q.split(/\s+/);
  const scored = semanticHits.map(h => {
    const text = h.summary_text.toLowerCase();
    let s = 0;
    for (const tok of tokens) if (text.includes(tok)) s += 1;
    // sentiment intent
    if (/жалоб|плох|медлен|долг|опозд|остыл/.test(q) && h.sentiment === 'negative') s += 0.8;
    if (/хвал|похвал|нрави|восторг|спасибо|отлич/.test(q) && h.sentiment === 'positive') s += 0.8;
    if (/доставк/.test(q) && /доставк/.test(text)) s += 0.5;
    if (/скорост|ожидан|жди/.test(q) && /ожидан|опозд|долг|25 минут|остыл/.test(text)) s += 0.5;
    return { ...h, _s: s };
  }).filter(x => x._s > 0).sort((a,b) => b._s - a._s).slice(0, 10);
  return scored.map(({ _s, ...rest }) => rest);
}

// --- Ask replies (mock /admin/ask) ---------------------------
function askReply(question, history) {
  const q = question.toLowerCase();
  if (/жалоб|негатив|плохо/.test(q)) {
    return {
      answer_text: 'Топ-3 жалобы за 7 дней: «время ожидания» (41), «доставка» (33), «десерты» (23). Основной всплеск — пятница 19:00–21:00, кондитерская станция.',
      tools_used: ['topics.list', 'metrics.wait_time_minutes'],
      chart_text:
        'Время ожидания  ████████████████████  41\n' +
        'Доставка        ████████████████      33\n' +
        'Десерты         ███████████           23',
    };
  }
  if (/свод|обзор|30/.test(q)) {
    return {
      answer_text: 'За 30 дней: 1 248 сессий, средний sentiment +0.42. Позитив доминирует по «сервису» и «качеству еды»; негатив сконцентрирован вокруг «времени ожидания» и «доставки».',
      tools_used: ['overview'],
      chart_text: null,
    };
  }
  if (/хвал|похвал|нрав|позитив|спасибо/.test(q)) {
    return {
      answer_text: 'Что хвалят чаще всего: «сервис» (86), «качество еды» (71), «атмосфера» (58). Внимание к деталям (постоянные гости, столик у окна) — повторяющийся мотив.',
      tools_used: ['topics.list?sentiment=positive'],
      chart_text:
        'Сервис         ████████████████████  86\n' +
        'Качество еды   █████████████████     71\n' +
        'Атмосфера      ██████████████        58',
    };
  }
  if (/скорост|ожидан|долг/.test(q)) {
    return {
      answer_text: 'Жалобы на скорость концентрируются в пятницу 19:00–21:00. Среднее ожидание десерта вырастает с 14 до 27 минут. Затронуты 41 сессия.',
      tools_used: ['metrics.wait_time_minutes', 'topics.list?topic=Время%20ожидания'],
      chart_text:
        'Пн  ██████        14\n' +
        'Вт  ████████      16\n' +
        'Ср  █████████     18\n' +
        'Чт  ██████████    19\n' +
        'Пт  ██████████████  27\n' +
        'Сб  ████████████  22\n' +
        'Вс  ██████████    20',
    };
  }
  if (/клиент|sentiment|анна|павел/.test(q)) {
    return {
      answer_text: 'Топ-3 положительных клиента: Павел Рот (0.91), Давид Хартманн (0.90), Игорь Вебер (0.88). Двое в зоне риска: Дмитрий Ковач (−0.34) и Ольга Дрозд (−0.28).',
      tools_used: ['clients.top'],
      chart_text: null,
    };
  }
  return { answer_text: 'Понял вопрос. По данным Atelier Brun я могу выдать сводку, топ-3 жалобы или похвалы, либо найти клиентов и сессии. Сформулируйте чуть конкретнее.', tools_used: [], chart_text: null };
}

Object.assign(window, {
  overview, DATE_PRESETS, METRIC_KEYS, DAYS_RU,
  metricsByKey, ENUM_LABELS, topicsByTone,
  clientProfiles, semanticHits, searchSemantic,
  askReply,
});
