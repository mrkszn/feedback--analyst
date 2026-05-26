// Mock data — domain-neutral. Voice template, "delivery service" sample fill.
const feedbackItems = [
  { id: 1287, name: 'Maria K.',  initials: 'МК', time: '3 min',  sentiment: 'pos',
    preview: 'Очень быстрая доставка, всё пришло аккуратно. Спасибо!',
    rating: 5, topic: 'Delivery speed', date: '14:02' },
  { id: 1286, name: 'Anton T.',  initials: 'АТ', time: '12 min', sentiment: 'neg',
    preview: 'Курьер опоздал на 40 минут, заказ остыл — пришлось разогревать.',
    rating: 2, topic: 'Delivery speed', date: '13:53' },
  { id: 1285, name: 'Lena S.',   initials: 'ЛС', time: '31 min', sentiment: 'neu',
    preview: 'Заказ оформлен, пока без обратной связи.',
    rating: 0, topic: '—', date: '13:34' },
  { id: 1284, name: 'Pavel R.',  initials: 'ПР', time: '1 h',    sentiment: 'pos',
    preview: 'Удобный интерфейс, в три клика разобрался.',
    rating: 5, topic: 'UX', date: '13:02' },
  { id: 1283, name: 'Olga D.',   initials: 'ОД', time: '2 h',    sentiment: 'neg',
    preview: 'Не нашла, как отменить подписку. Поддержка не отвечает.',
    rating: 2, topic: 'Support', date: '12:14' },
  { id: 1282, name: 'Igor V.',   initials: 'ИВ', time: '3 h',    sentiment: 'pos',
    preview: 'Цены адекватные, заказываю не первый раз.',
    rating: 4, topic: 'Pricing', date: '11:08' },
  { id: 1281, name: 'Anna M.',   initials: 'АМ', time: '4 h',    sentiment: 'neu',
    preview: 'Всё нормально, без претензий.',
    rating: 3, topic: '—', date: '10:55' },
  { id: 1280, name: 'Sergey N.', initials: 'СН', time: '5 h',    sentiment: 'pos',
    preview: 'Поддержка помогла буквально за минуту в чате.',
    rating: 5, topic: 'Support', date: '09:22' },
];

const topicsPos = [
  { name: 'Delivery speed', count: 86, share: 0.92 },
  { name: 'UX',             count: 64, share: 0.68 },
  { name: 'Pricing',        count: 52, share: 0.55 },
  { name: 'Support',        count: 38, share: 0.41 },
  { name: 'Packaging',      count: 21, share: 0.22 },
];
const topicsNeg = [
  { name: 'Delivery speed', count: 41, share: 0.95 },
  { name: 'Support',        count: 28, share: 0.65 },
  { name: 'Cancellation',   count: 19, share: 0.44 },
  { name: 'Mobile bugs',    count: 12, share: 0.28 },
  { name: 'Pricing',        count:  8, share: 0.19 },
];

const metricSeries = [
  { d: 'Mon', v: 0.62 }, { d: 'Tue', v: 0.66 }, { d: 'Wed', v: 0.71 },
  { d: 'Thu', v: 0.69 }, { d: 'Fri', v: 0.74 }, { d: 'Sat', v: 0.78 }, { d: 'Sun', v: 0.78 },
];

const clientsList = [
  { id: 1287, name: 'Maria K.',  initials: 'МК', tint: 'violet',  sessions: 12, sentiment: 0.86 },
  { id: 1286, name: 'Anton T.',  initials: 'АТ', tint: 'rose',    sessions:  8, sentiment: 0.32 },
  { id: 1285, name: 'Lena S.',   initials: 'ЛС', tint: 'slate',   sessions:  3, sentiment: 0.51 },
  { id: 1284, name: 'Pavel R.',  initials: 'ПР', tint: 'indigo',  sessions: 19, sentiment: 0.92 },
  { id: 1283, name: 'Olga D.',   initials: 'ОД', tint: 'rose',    sessions:  6, sentiment: 0.28 },
  { id: 1282, name: 'Igor V.',   initials: 'ИВ', tint: 'emerald', sessions: 24, sentiment: 0.81 },
  { id: 1281, name: 'Anna M.',   initials: 'АМ', tint: 'slate',   sessions:  4, sentiment: 0.59 },
  { id: 1280, name: 'Sergey N.', initials: 'СН', tint: 'violet',  sessions: 11, sentiment: 0.88 },
];

Object.assign(window, { feedbackItems, topicsPos, topicsNeg, metricSeries, clientsList });
