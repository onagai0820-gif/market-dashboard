'use strict';

const HIGHLIGHTS = ['^GSPC', '^N225', '^IXIC', '^VIX', 'USDJPY=X', '^TNX'];
const NEWS_PAGE = 20;

const state = {
  markets: null,
  news: null,
  quotes: new Map(),
  newsLang: 'all',
  newsShown: NEWS_PAGE,
  detail: null,
  detailRange: 365,
};

/* -------------------------------------------------------------- utilities */

const fmt = (value, digits) =>
  value === null || value === undefined || Number.isNaN(value)
    ? '—'
    : value.toLocaleString('ja-JP', {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });

function decimalsFor(value) {
  const magnitude = Math.abs(value ?? 0);
  if (magnitude >= 1000) return 2;
  if (magnitude >= 10) return 2;
  if (magnitude >= 1) return 3;
  return 4;
}

const price = (value) => fmt(value, decimalsFor(value));

function direction(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return 'flat';
  if (value > 0) return 'up';
  if (value < 0) return 'down';
  return 'flat';
}

const ARROW = { up: '▲', down: '▼', flat: '—' };

function deltaHTML(change, changePct, opts = {}) {
  const dir = direction(changePct ?? change);
  const arrow = `<span class="arrow" aria-hidden="true">${ARROW[dir]}</span>`;
  const sign = dir === 'up' ? '+' : '';
  const label = dir === 'up' ? '上昇' : dir === 'down' ? '下落' : '変化なし';
  const pct =
    changePct === null || changePct === undefined
      ? '—'
      : `${sign}${fmt(changePct, 2)}%`;
  if (opts.pctOnly) {
    return `<span class="pill ${dir}"><span class="sr-only">${label}</span>${arrow}${pct}</span>`;
  }
  // 前日比は値そのものではなく現在値の桁数に合わせる（7785 に対する +0.5 を +0.5000 と書かない）。
  const abs =
    change === null || change === undefined
      ? '—'
      : `${sign}${fmt(change, decimalsFor(opts.scale ?? change))}`;
  return `<span class="delta ${dir}"><span class="sr-only">${label}</span>${arrow}${abs} (${pct})</span>`;
}

const escapeHTML = (text) =>
  String(text ?? '').replace(/[&<>"']/g, (ch) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch])
  );

/* --------------------------------------------------------------- history */

// history は転送量を抑えるため {t: [...], c: [...]} の並列配列で持つ。
function historyPoints(history, limit) {
  if (!history?.c?.length) return [];
  const start = limit ? Math.max(0, history.c.length - limit) : 0;
  const points = [];
  for (let i = start; i < history.c.length; i += 1) {
    points.push({ t: history.t[i], c: history.c[i] });
  }
  return points;
}

/* ------------------------------------------------------------- sparklines */

function sparkline(history, dir) {
  const points = (history?.c || []).slice(-30);
  if (points.length < 2) return '';
  const w = 84;
  const h = 26;
  const pad = 3;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const x = (i) => (i / (points.length - 1)) * w;
  const y = (v) => h - pad - ((v - min) / span) * (h - pad * 2);
  const line = points.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const area = `${line} L${w} ${h} L0 ${h} Z`;
  return `<svg class="spark ${dir}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
    <path class="area" d="${area}"/><path class="line" d="${line}"/></svg>`;
}

/* ------------------------------------------------------------------ cards */

function statTile(quote) {
  const dir = direction(quote.change_pct);
  return `<button type="button" class="stat-tile" data-symbol="${escapeHTML(quote.symbol)}">
    <span class="stat-label">${escapeHTML(quote.name)}</span>
    <span class="stat-value">${price(quote.price)}</span>
    <span class="stat-foot">${deltaHTML(quote.change, quote.change_pct, { scale: quote.price })}
      ${sparkline(quote.history, dir)}</span>
  </button>`;
}

function quoteRow(quote) {
  const dir = direction(quote.change_pct);
  const stale = quote.stale ? '<span class="stale-flag">更新待ち</span>' : '';
  return `<tr data-symbol="${escapeHTML(quote.symbol)}" tabindex="0">
    <td><span class="name-cell">
      <span class="name-main">${escapeHTML(quote.name)}${stale}</span>
      <span class="name-sub">${escapeHTML(quote.subtitle || quote.symbol)}</span>
    </span></td>
    <td class="price-cell">${price(quote.price)}</td>
    <td>${deltaHTML(quote.change, quote.change_pct, { scale: quote.price })}</td>
    <td>${deltaHTML(null, quote.change_pct, { pctOnly: true })}</td>
    <td class="spark-cell">${sparkline(quote.history, dir)}</td>
  </tr>`;
}

function renderMarkets() {
  const data = state.markets;
  const nav = document.getElementById('section-nav');
  const host = document.getElementById('market-sections');

  const highlightQuotes = HIGHLIGHTS.map((s) => state.quotes.get(s)).filter(Boolean);
  document.getElementById('highlights').innerHTML = highlightQuotes.map(statTile).join('');

  host.innerHTML = data.groups
    .map(
      (group) => `<section class="market-section" id="${group.id}" aria-labelledby="h-${group.id}">
      <div class="section-head"><div>
        <h2 id="h-${group.id}">${escapeHTML(group.name)}</h2>
        <p class="section-note">${escapeHTML(group.note)}</p>
      </div></div>
      <div class="table-card"><div class="table-scroll"><table class="quotes">
        <thead><tr>
          <th scope="col">銘柄・指数</th><th scope="col">現在値</th>
          <th scope="col">前日比</th><th scope="col">騰落率</th>
          <th scope="col">30日推移</th>
        </tr></thead>
        <tbody>${group.items.map(quoteRow).join('')}</tbody>
      </table></div></div>
    </section>`
    )
    .join('');

  nav.innerHTML =
    data.groups
      .map((g) => `<a href="#${g.id}">${escapeHTML(g.name)}</a>`)
      .join('') + '<a href="#news">ニュース</a>';

  const updated = new Date(data.updated_at);
  document.getElementById('updated').innerHTML =
    `最終更新<span>${updated.toLocaleString('ja-JP', {
      month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
    })} JST</span>`;
}

/* ------------------------------------------------------------------- news */

function relativeTime(iso) {
  if (!iso) return '';
  const diffMin = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (diffMin < 1) return 'たった今';
  if (diffMin < 60) return `${diffMin}分前`;
  const hours = Math.round(diffMin / 60);
  if (hours < 24) return `${hours}時間前`;
  return `${Math.round(hours / 24)}日前`;
}

function renderNews() {
  const list = document.getElementById('news-list');
  const more = document.getElementById('news-more');
  const articles = (state.news?.articles || []).filter(
    (a) => state.newsLang === 'all' || a.lang === state.newsLang
  );

  if (!articles.length) {
    list.innerHTML = '<li><p class="empty-state">記事を取得できませんでした。</p></li>';
    more.hidden = true;
    return;
  }

  list.innerHTML = articles
    .slice(0, state.newsShown)
    .map(
      (a) => `<li><a href="${escapeHTML(a.url)}" target="_blank" rel="noopener noreferrer">
      <div class="news-meta">
        <span class="news-source">${escapeHTML(a.source)}</span>
        <span>${escapeHTML(relativeTime(a.published))}</span>
      </div>
      <div class="news-title">${escapeHTML(a.title)}</div>
      ${a.summary ? `<div class="news-summary">${escapeHTML(a.summary)}</div>` : ''}
    </a></li>`
    )
    .join('');

  more.hidden = articles.length <= state.newsShown;
}

/* ----------------------------------------------------------- detail chart */

const CHART = { w: 560, h: 220, padL: 52, padR: 12, padT: 12, padB: 26 };

function lineChart(points, dir) {
  if (points.length < 2) {
    return { html: '<p class="empty-state">チャートを表示できません。</p>', coords: [] };
  }

  const { w, h, padL, padR, padT, padB } = CHART;
  const values = points.map((d) => d.c);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const headroom = (max - min) * 0.08 || Math.abs(max) * 0.02 || 1;
  const lo = min - headroom;
  const hi = max + headroom;

  const x = (i) => padL + (i / (points.length - 1)) * (w - padL - padR);
  const y = (v) => padT + (1 - (v - lo) / (hi - lo)) * (h - padT - padB);
  const coords = points.map((d, i) => ({ x: x(i), y: y(d.c), t: d.t, c: d.c }));

  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => lo + (hi - lo) * f);
  const grid = ticks
    .map(
      (v) =>
        `<line x1="${padL}" x2="${w - padR}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/>`
    )
    .join('');
  const yLabels = ticks
    .map(
      (v) =>
        `<text x="${padL - 8}" y="${(y(v) + 3.5).toFixed(1)}" text-anchor="end">${fmt(
          v,
          decimalsFor(v) - 1 < 0 ? 0 : Math.min(2, decimalsFor(v))
        )}</text>`
    )
    .join('');

  const stepCount = Math.min(5, points.length);
  const xLabels = Array.from({ length: stepCount }, (_, k) => {
    const i = Math.round((k / (stepCount - 1)) * (points.length - 1));
    const date = new Date(points[i].t * 1000);
    const anchor = k === 0 ? 'start' : k === stepCount - 1 ? 'end' : 'middle';
    return `<text x="${x(i).toFixed(1)}" y="${h - 8}" text-anchor="${anchor}">${date.toLocaleDateString(
      'ja-JP', { month: 'numeric', day: 'numeric' })}</text>`;
  }).join('');

  const line = coords.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const last = coords[coords.length - 1];
  const area = `${line} L${last.x.toFixed(1)} ${h - padB} L${padL} ${h - padB} Z`;
  const stroke = dir === 'down' ? 'var(--down)' : dir === 'up' ? 'var(--up)' : 'var(--muted)';
  const fill = dir === 'down' ? 'var(--down-soft)' : dir === 'up' ? 'var(--up-soft)' : 'transparent';

  const html = `<div class="chart-wrap">
    <svg viewBox="0 0 ${w} ${h}" role="img" aria-label="期間中の終値推移">
      <g class="chart-grid">${grid}</g>
      <g class="chart-axis">${yLabels}${xLabels}</g>
      <path class="chart-area" d="${area}" fill="${fill}"/>
      <path class="chart-line" d="${line}" stroke="${stroke}"/>
      <g class="chart-cursor" hidden>
        <line y1="${padT}" y2="${h - padB}"/>
        <circle r="4.5" fill="${stroke}"/>
      </g>
      <rect class="chart-hit" x="${padL}" y="${padT}" width="${w - padL - padR}" height="${h - padT - padB}"/>
    </svg>
    <div class="chart-tooltip" hidden></div>
  </div>`;

  return { html, coords };
}

function attachCrosshair(container, coords) {
  const svg = container.querySelector('svg');
  const hit = container.querySelector('.chart-hit');
  if (!svg || !hit || coords.length < 2) return;

  const cursor = container.querySelector('.chart-cursor');
  const cursorLine = cursor.querySelector('line');
  const cursorDot = cursor.querySelector('circle');
  const tooltip = container.querySelector('.chart-tooltip');
  const { w, h, padL, padR } = CHART;

  const move = (event) => {
    const rect = svg.getBoundingClientRect();
    const clientX = event.touches ? event.touches[0].clientX : event.clientX;
    const svgX = ((clientX - rect.left) / rect.width) * w;
    const ratio = (svgX - padL) / (w - padL - padR);
    const i = Math.max(0, Math.min(coords.length - 1, Math.round(ratio * (coords.length - 1))));
    const point = coords[i];

    cursor.hidden = false;
    cursorLine.setAttribute('x1', point.x);
    cursorLine.setAttribute('x2', point.x);
    cursorDot.setAttribute('cx', point.x);
    cursorDot.setAttribute('cy', point.y);

    tooltip.hidden = false;
    tooltip.style.left = `${(point.x / w) * rect.width}px`;
    tooltip.style.top = `${(point.y / h) * rect.height}px`;
    tooltip.innerHTML = `<span class="tt-date">${new Date(point.t * 1000).toLocaleDateString(
      'ja-JP', { year: 'numeric', month: 'numeric', day: 'numeric' })}</span>
      <span class="tt-value">${price(point.c)}</span>`;
  };

  const leave = () => {
    cursor.hidden = true;
    tooltip.hidden = true;
  };

  hit.addEventListener('mousemove', move);
  hit.addEventListener('mouseleave', leave);
  hit.addEventListener('touchmove', move, { passive: true });
  hit.addEventListener('touchend', leave);
}

function renderDetail() {
  const quote = state.detail;
  if (!quote) return;

  document.getElementById('detail-name').textContent = quote.name;
  document.getElementById('detail-sub').textContent =
    [quote.symbol, quote.exchange, quote.currency].filter(Boolean).join(' · ');
  document.getElementById('detail-price').textContent = price(quote.price);
  document.getElementById('detail-delta').innerHTML = deltaHTML(quote.change, quote.change_pct, { scale: quote.price });

  const history = historyPoints(quote.history, state.detailRange);
  const dir = direction(history.length > 1 ? history[history.length - 1].c - history[0].c : 0);
  const chart = document.getElementById('detail-chart');
  const { html, coords } = lineChart(history, dir);
  chart.innerHTML = html;
  attachCrosshair(chart, coords);

  const first = history[0]?.c;
  const last = history[history.length - 1]?.c;
  const periodPct = first ? ((last - first) / first) * 100 : null;
  const label = { 30: '1ヶ月', 90: '3ヶ月', 180: '6ヶ月', 365: '1年' }[state.detailRange];
  document.getElementById('detail-caption').textContent =
    `${label}の終値推移（${history.length}営業日）`;

  const rows = [
    ['前日終値', price(quote.prev_close)],
    ['当日高値', price(quote.day_high)],
    ['当日安値', price(quote.day_low)],
    ['52週高値', price(quote.w52_high)],
    ['52週安値', price(quote.w52_low)],
    [`${label}騰落率`, periodPct === null ? '—' : `${periodPct > 0 ? '+' : ''}${fmt(periodPct, 2)}%`],
  ];
  document.getElementById('detail-stats').innerHTML = rows
    .map(([term, value]) => `<div><dt>${term}</dt><dd>${value}</dd></div>`)
    .join('');
}

function openDetail(symbol) {
  const quote = state.quotes.get(symbol);
  if (!quote) return;
  state.detail = quote;
  state.detailRange = 365;
  document.querySelectorAll('#range-picker button').forEach((btn) =>
    btn.classList.toggle('is-active', Number(btn.dataset.range) === 365)
  );
  document.getElementById('detail').hidden = false;
  document.body.style.overflow = 'hidden';
  renderDetail();
  document.getElementById('detail-close').focus();
}

function closeDetail() {
  document.getElementById('detail').hidden = true;
  document.body.style.overflow = '';
  state.detail = null;
}

/* ------------------------------------------------------------------ theme */

// CSS の既定が黒基調なので、ライトを選んだときだけ data-theme を立てる。
function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === 'light') root.setAttribute('data-theme', 'light');
  else root.removeAttribute('data-theme');
  localStorage.setItem('theme', theme);
  const toggle = document.getElementById('theme-toggle');
  document.getElementById('theme-icon').textContent = theme === 'light' ? '☀' : '☾';
  toggle.setAttribute('aria-label', theme === 'light' ? 'ダークテーマに切り替え' : 'ライトテーマに切り替え');
}

/* ------------------------------------------------------------------- init */

function bindEvents() {
  document.body.addEventListener('click', (event) => {
    const target = event.target.closest('[data-symbol]');
    if (target) openDetail(target.dataset.symbol);
  });

  document.body.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const row = event.target.closest('tr[data-symbol]');
    if (row) {
      event.preventDefault();
      openDetail(row.dataset.symbol);
    }
  });

  document.getElementById('detail-close').addEventListener('click', closeDetail);
  document.getElementById('detail').addEventListener('click', (event) => {
    if (event.target.id === 'detail') closeDetail();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !document.getElementById('detail').hidden) closeDetail();
  });

  document.getElementById('range-picker').addEventListener('click', (event) => {
    const btn = event.target.closest('button');
    if (!btn) return;
    state.detailRange = Number(btn.dataset.range);
    document.querySelectorAll('#range-picker button').forEach((b) =>
      b.classList.toggle('is-active', b === btn)
    );
    renderDetail();
  });

  document.querySelector('.news .segmented').addEventListener('click', (event) => {
    const btn = event.target.closest('button');
    if (!btn) return;
    state.newsLang = btn.dataset.lang;
    state.newsShown = NEWS_PAGE;
    document.querySelectorAll('.news .segmented button').forEach((b) =>
      b.classList.toggle('is-active', b === btn)
    );
    renderNews();
  });

  document.getElementById('news-more').addEventListener('click', () => {
    state.newsShown += NEWS_PAGE;
    renderNews();
  });

  document.getElementById('theme-toggle').addEventListener('click', () => {
    applyTheme(localStorage.getItem('theme') === 'light' ? 'dark' : 'light');
  });
}

async function load() {
  const bust = `?v=${Math.floor(Date.now() / 60000)}`;
  const [markets, news] = await Promise.all([
    fetch(`data/markets.json${bust}`).then((r) => r.json()),
    fetch(`data/news.json${bust}`).then((r) => r.json()).catch(() => null),
  ]);

  state.markets = markets;
  state.news = news;
  markets.groups.forEach((group) =>
    group.items.forEach((item) => state.quotes.set(item.symbol, item))
  );

  renderMarkets();
  renderNews();
}

applyTheme(localStorage.getItem('theme') || 'dark');
bindEvents();
load().catch((err) => {
  console.error(err);
  document.getElementById('updated').textContent = 'データを取得できませんでした';
});
