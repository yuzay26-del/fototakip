/* FotoTakip istemcisi. Derleme adımı yok; tarayıcı bu dosyayı doğrudan çalıştırır. */
(() => {
'use strict';

/* ---------- yardımcılar ---------- */
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const pad = n => String(n).padStart(2, '0');
const dayStr = t => `${t.getFullYear()}-${pad(t.getMonth() + 1)}-${pad(t.getDate())}`;
const todayStr = () => dayStr(new Date());
const MONTHS = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
const fmtDate = s => { const [y, m, d] = s.split('-').map(Number); return `${d} ${MONTHS[m - 1].slice(0, 3)}`; };
const fmtTime = iso => { const t = new Date(iso); if (isNaN(t)) return '—'; return `${t.getDate()} ${MONTHS[t.getMonth()].slice(0, 3)} ${pad(t.getHours())}:${pad(t.getMinutes())}`; };
const fmtGps = p => p && p.lat != null ? `${p.lat.toFixed(5)}° · ${p.lng.toFixed(5)}°` : 'Konum yok';
const GPS_SRC = { exif: 'EXIF', device: 'Cihaz', project: 'Proje adresi', none: '' };
const daysBetween = (a, b) => Math.round((new Date(b + 'T00:00') - new Date(a + 'T00:00')) / 864e5);
const store = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch {} } };

const STATUSES = [
  { id: 'open', name: 'Açık', short: 'Açık' }, { id: 'progress', name: 'Devam ediyor', short: 'Devam' },
  { id: 'review', name: 'Onay bekliyor', short: 'Onay' }, { id: 'done', name: 'Tamamlandı', short: 'Bitti' }
];
const ST_ICON = {
  open: '<svg viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="4.5" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
  progress: '<svg viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="4.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M6 1.5A4.5 4.5 0 0 1 6 10.5Z" fill="currentColor"/></svg>',
  review: '<svg viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="4.5" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="6" cy="6" r="1.6" fill="currentColor"/></svg>',
  done: '<svg viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="5" fill="currentColor"/><path d="M3.6 6.2l1.6 1.6 3.2-3.4" stroke="var(--surface)" stroke-width="1.5" fill="none"/></svg>'
};
const TYPES = { before: 'Önce', progress: 'Süreç', after: 'Sonra', issue: 'Sorun' };
const TYPE_IC = { before: 'image', progress: 'clock', after: 'check', issue: 'alert' };
/* Simge seti: 24x24, çizgi. Yeni simge eklerken yalnızca yol (path) verisi yazılır. */
const P = {
  board: '<rect x="3" y="4" width="5" height="16" rx="1.5"/><rect x="10" y="4" width="5" height="10" rx="1.5"/><rect x="17" y="4" width="4" height="13" rx="1.5"/>',
  gallery: '<rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/><rect x="13" y="13" width="8" height="8" rx="1.5"/>',
  camera: '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
  map: '<path d="M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11z"/><circle cx="12" cy="10" r="2.2"/>',
  pin: '<path d="M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11z"/><circle cx="12" cy="10" r="2.2"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c1-3.5 3.5-5 6.5-5s5.5 1.5 6.5 5"/><circle cx="17" cy="9" r="2.8"/><path d="M16 14.2c2.6 0 4.6 1.3 5.5 4.3"/>',
  shield: '<path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
  crown: '<path d="M3 8l4.5 4L12 5l4.5 7L21 8l-2 11H5z"/>',
  flag: '<path d="M5 21V4h11l-2 4 2 4H5"/>',
  wrench: '<path d="M15 4a5 5 0 0 0-4.6 6.9L4 17.3V20h2.7l6.4-6.4A5 5 0 0 0 20 9l-3 3-3-1-1-3z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  list: '<path d="M9 6h12M9 12h12M9 18h12M4 6h.01M4 12h.01M4 18h.01"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  building: '<rect x="4" y="3" width="12" height="18" rx="1"/><path d="M16 9h4v12h-4M8 7h4M8 11h4M8 15h4"/>',
  phone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
  plug: '<path d="M9 2v6M15 2v6M6 8h12v4a6 6 0 0 1-12 0zM12 18v4"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9L7 7M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
  logout: '<path d="M10 4H5v16h5M15 8l4 4-4 4M19 12H9"/>',
  palette: '<path d="M12 3a9 9 0 1 0 0 18c1.5 0 2-1 2-2s-1-1.5-1-2.5 1-2 2.5-2H18a3 3 0 0 0 3-3c0-4.6-4-8.5-9-8.5z"/><circle cx="7.5" cy="11" r="1.2"/><circle cx="10" cy="7" r="1.2"/><circle cx="15" cy="7.5" r="1.2"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  cloudoff: '<path d="M3 3l18 18M7 18h10a4 4 0 0 0 1.7-7.6A6 6 0 0 0 8.4 7.6M5 10.5A4 4 0 0 0 7 18"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
  download: '<path d="M12 4v12M7 11l5 5 5-5M4 20h16"/>',
  report: '<path d="M6 3h9l4 4v14H6z"/><path d="M15 3v4h4M9 12h7M9 16h5"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  chevron: '<path d="M9 6l6 6-6 6"/>',
  chevl: '<path d="M15 6l-6 6 6 6"/>',
  pen: '<path d="M4 20l4-1L19 8l-3-3L5 16z"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  chat: '<path d="M4 5h16v11H9l-5 4z"/>',
  checklist: '<path d="M10 6h10M10 12h10M10 18h10M3.5 6l1.5 1.5L7.5 5M3.5 12l1.5 1.5 2.5-2.5M3.5 18l1.5 1.5 2.5-2.5"/>',
  sign: '<path d="M3 17c3 0 4-8 6-8s0 8 3 8 3-4 5-4 2 3 4 3M3 21h18"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v4M12 17.5v.01"/>',
  target: '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2.5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
  nav: '<path d="M3 11l18-8-8 18-2-8z"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.8"/><path d="M21 16l-5-5-9 9"/>',
  sparkle: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>',
  swap: '<path d="M7 7h13M16 3l4 4-4 4M17 17H4M8 13l-4 4 4 4"/>',
  archive: '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v11h14V9M10 13h4"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l3 3M15 8l2 2"/>',
  bolt: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  drop: '<path d="M12 3s7 7.5 7 12a7 7 0 0 1-14 0c0-4.5 7-12 7-12z"/>',
  snow: '<path d="M12 2v20M3.3 7l17.4 10M3.3 17L20.7 7M9 4l3 2 3-2M9 20l3-2 3 2"/>',
  brush: '<path d="M14 4l6 6-7 7-6-6zM7 11l-3 3c-1 1-1 4-1 6 2 0 5 0 6-1l3-3"/>',
  brick: '<rect x="3" y="5" width="18" height="14" rx="1"/><path d="M3 10h18M3 15h18M9 5v5M15 10v5M9 15v4"/>',
  wifi: '<path d="M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0M12 19.5v.01"/>',
  flame: '<path d="M12 3c1 4 5 5 5 10a5 5 0 0 1-10 0c0-3 2-4 2-7 2 1 3 3 3 3"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6L19 19M5 19l1.4-1.4M17.6 6.4L19 5"/>',
  cctv: '<path d="M3 7l14 4-2 4L3 11zM15 13l2 4h4M6 12v5H3"/>',
  leaf: '<path d="M5 19c0-9 6-14 15-14 0 9-5 15-14 15M5 19l7-7"/>'
};
const ic = (n, c = '') => `<svg class="i ${c}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[n] || P.wrench}</svg>`;
const IC = { camera: ic('camera'), target: ic('target'), plus: ic('plus') };
const SKILL_ICONS = ['bolt', 'drop', 'snow', 'brush', 'brick', 'wifi', 'wrench', 'flame', 'sun', 'key', 'cctv', 'leaf'];
const SKILL_COLORS = ['#D97706', '#0284C7', '#0891B2', '#C026D3', '#B45309', '#4F46E5', '#16A34A', '#DC2626', '#64748B'];
const ROLE = { owner: 'Sahip', manager: 'Yönetici', lead: 'Ekip lideri', field: 'Teknisyen' };
const ROLE_IC = { owner: 'crown', manager: 'shield', lead: 'flag', field: 'wrench' };
const STYLES = [
  { id: 'auto', name: 'Otomatik', b: 'linear-gradient(135deg,#F3F5F8 50%,#0F1318 50%)', s: '#9AA7B4', k: '#5D6876', a: '#0B6E99' },
  { id: 'sade', name: 'Sade', b: '#F3F5F8', s: '#FFFFFF', k: '#14181F', a: '#0B6E99' },
  { id: 'gece', name: 'Gece', b: '#0F1318', s: '#1F262E', k: '#E8EDF2', a: '#4CB8E6' },
  { id: 'saha', name: 'Saha', b: '#FFFFFF', s: '#F1F1F1', k: '#000000', a: '#FFD400' },
  { id: 'okyanus', name: 'Okyanus', b: '#E7EFF6', s: '#FFFFFF', k: '#0E2235', a: '#2160E0' },
  { id: 'orman', name: 'Orman', b: '#ECF0EA', s: '#FBFCFA', k: '#17241C', a: '#1F6B4A' }
];
const HUES = ['#0B6E99', '#1E7F4F', '#B76E00', '#6A4CC2', '#C23B22', '#0891B2', '#9D174D', '#4D7C0F'];
const hue = id => HUES[[...String(id)].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7) % HUES.length];
const initials = s => (String(s || '?').trim().split(/\s+/).filter(Boolean).map(w => w[0]).join('').slice(0, 2) || '?').toLocaleUpperCase('tr');

/* ---------- durum ---------- */
const now0 = new Date();
const S = {
  me: null, users: [], projects: [], allProjects: [], skills: [], tasks: [], photos: {}, settings: { auto_rule: true }, needsSetup: false, loaded: false,
  view: 'board', boardMode: 'kanban', mcol: 'progress', project: 'all', q: '', searchIds: null,
  open: null, active: null, annot: false, draftPin: null, galType: 'all', mapPick: null, repProj: null,
  cal: { y: now0.getFullYear(), m: now0.getMonth() }, theme: store.get('ft-style') || 'auto',
  cam: { target: 'new', project: null, type: 'before' }, pending: [], addType: 'progress',
  mapLayers: { photos: true, openOnly: false }, mapQ: '', mapMode: null, mapDetail: false, pickPoint: null, pickAddr: undefined, panelMin: false, here: null,
  admTab: 'customers', admQ: '', admArch: false, modal: null,
  queueCount: 0, forceOffline: store.get('ft-force-offline') === '1', online: navigator.onLine, flushing: false
};

const user = id => S.users.find(u => u.id === id);
const nameOf = id => id === 'sys' ? 'Sistem' : user(id)?.name ?? '—';
const proj = id => S.allProjects.find(p => p.id === id);
const task = id => S.tasks.find(t => t.id === id);
const skill = id => S.skills.find(s => s.id === id);
const thumb = pid => `/files/${pid}?s=t`;
const full = pid => `/files/${pid}`;
const can = k => !!S.me?.perms?.[k];
const isMgr = () => can('admin');
const isLead = () => S.me?.role === 'lead';
const canDispatch = () => isMgr() || isLead();          // atama, onay, yetenek belirleme
const canCust = () => can('customers');
const isPool = t => !t.assignee_id;
const mine = t => canDispatch() || t.assignee_id === S.me.id;  // işi değiştirebilir mi
const canManageUser = u => u.id !== S.me.id && (S.me.role === 'owner' || (S.me.role === 'manager' && ['lead', 'field'].includes(u.role)));
const assignable = () => S.users.filter(u => u.active !== false && (isMgr() || u.id === S.me.id || u.lead_id === S.me.id));
const stName = id => STATUSES.find(s => s.id === id).name;
const stPill = id => `<span class="st ${id}">${ST_ICON[id]}${stName(id)}</span>`;
const skillChip = (id, cls = '') => { const k = skill(id); return k ? `<span class="skill ${cls}" style="--c:${k.color}" title="${esc(k.name)}" role="img" aria-label="${esc(k.name)}">${ic(k.icon)}</span>` : ''; };
const roleBadge = r => `<span class="role ${r}">${ic(ROLE_IC[r], 'xs')}${ROLE[r]}</span>`;
const empty = (i, text, extra = '') => `<div class="empty">${ic(i)}<b>${text}</b>${extra}</div>`;
const coverPid = t => t.photos.length ? t.photos[t.photos.length - 1].pid : null;
const firstOf = (t, type) => t.photos.find(p => p.type === type);
const lastOf = (t, type) => [...t.photos].reverse().find(p => p.type === type);
const annCount = t => t.photos.reduce((n, p) => n + (S.photos[p.pid]?.annotations.length ?? 0), 0);
const isLate = t => t.status !== 'done' && t.due < todayStr();
const dueLabel = t => {
  if (t.status === 'done') return fmtDate(t.due);
  const d = daysBetween(todayStr(), t.due);
  if (d === 0) return 'Bugün';
  if (d < 0) return `${-d} gün gecikti`;
  if (d === 1) return 'Yarın';
  return fmtDate(t.due);
};
const dueCls = t => t.status === 'done' ? '' : isLate(t) ? 'late' : t.due === todayStr() ? 'today' : '';
const av = id => { const u = user(id); return u ? `<span class="avatar" title="${esc(u.name)}">${esc(u.short)}</span>` : '<span class="avatar none" title="Atanmamış">?</span>'; };
const offline = () => S.forceOffline || !navigator.onLine;
const visibleTasks = () => S.tasks.filter(t => (S.project === 'all' || t.project_id === S.project) && (!S.searchIds || S.searchIds.has(t.id)));

/* ---------- ağ ---------- */
class ApiErr extends Error { constructor(msg, status, code) { super(msg); this.status = status; this.code = code; } }
class NetErr extends Error {}
async function api(method, path, body) {
  const init = { method, headers: {}, credentials: 'same-origin' };
  if (body instanceof Blob) { init.body = body; init.headers['Content-Type'] = body.type || 'application/octet-stream'; }
  else if (body !== undefined) { init.body = JSON.stringify(body); init.headers['Content-Type'] = 'application/json'; }
  let r;
  try { r = await fetch(path, init); } catch (e) { throw new NetErr('Sunucuya ulaşılamıyor'); }
  let data = null;
  try { data = await r.json(); } catch {}
  if (!r.ok) throw new ApiErr(data?.error?.message || `Sunucu hatası (${r.status})`, r.status, data?.error?.code);
  return data;
}
function fail(e) {
  if (e instanceof NetErr) toast('Sunucuya ulaşılamıyor. Telefonda FotoTakip açık mı, bağlantın var mı?');
  else if (e?.status === 401) { showLogin(); }
  else toast(esc(e?.message || String(e)));
}
async function run(fn, ok) {
  try {
    const r = await fn();
    const msg = typeof ok === 'function' ? ok(r) : ok;
    if (msg) toast(msg);
    await reload();
    return r;
  } catch (e) {
    fail(e);
    if (!(e instanceof NetErr)) reload().catch(() => {});
    return null;
  }
}

async function reload() {
  const d = await api('GET', '/api/bootstrap');
  Object.assign(S, { me: d.me, users: d.users, allProjects: d.projects, projects: d.projects.filter(p => !p.archived), skills: d.skills || [],
    tasks: d.tasks, photos: d.photos, settings: d.settings, loaded: true });
  if (d.me.theme && d.me.theme !== S.theme) { S.theme = d.me.theme; store.set('ft-style', S.theme); applyTheme(); }
  if (!S.cam.project || !proj(S.cam.project)) S.cam.project = S.projects[0]?.id ?? null;
  if (!S.mapPick || !proj(S.mapPick)) S.mapPick = S.projects[0]?.id ?? null;
  if (!S.repProj || !proj(S.repProj)) S.repProj = S.projects[0]?.id ?? null;
  if (S.open && !task(S.open)) S.open = null;
  render();
}
let reloadTimer = null;
const reloadSoon = () => { clearTimeout(reloadTimer); reloadTimer = setTimeout(() => reload().catch(() => {}), 350); };

/* ---------- çevrimdışı kuyruk (IndexedDB) ---------- */
const Q = {
  _db: null,
  open() {
    return this._db ??= new Promise((res, rej) => {
      const r = indexedDB.open('fototakip', 1);
      r.onupgradeneeded = () => r.result.createObjectStore('queue', { keyPath: 'id', autoIncrement: true });
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error);
    });
  },
  async op(mode, fn) {
    const db = await this.open();
    return new Promise((res, rej) => {
      const tx = db.transaction('queue', mode);
      const req = fn(tx.objectStore('queue'));
      tx.oncomplete = () => res(req?.result);
      tx.onerror = () => rej(tx.error);
    });
  },
  add(item) { return this.op('readwrite', s => s.add(item)); },
  all() { return this.op('readonly', s => s.getAll()); },
  del(id) { return this.op('readwrite', s => s.delete(id)); },
  count() { return this.op('readonly', s => s.count()); }
};
async function refreshQueueCount() { try { S.queueCount = await Q.count(); } catch { S.queueCount = 0; } renderHeader(); renderDock(); }

/* Bir grup fotoğrafı sırayla yükler. İlk fotoğraf gerekirse işi oluşturur. */
async function uploadGroup(files, params) {
  let taskId = params.task_id || null;
  const results = [];
  for (let i = 0; i < files.length; i++) {
    const qp = new URLSearchParams({ type: params.type });
    if (taskId) qp.set('task_id', taskId);
    else { qp.set('new_task', '1'); qp.set('project_id', params.project_id); if (params.title) qp.set('title', params.title); }
    if (params.lat != null) { qp.set('lat', params.lat); qp.set('lng', params.lng); if (params.acc != null) qp.set('acc', params.acc); }
    try {
      const r = await api('POST', '/api/photos?' + qp, files[i]);
      taskId = r.task_id;
      results.push(r);
    } catch (e) {
      if (e instanceof NetErr) { e.rest = files.slice(i); e.taskId = taskId; e.results = results; }
      throw e;
    }
  }
  return results;
}
async function enqueue(files, params) {
  await Q.add({ files, params, at: new Date().toISOString() });
  await refreshQueueCount();
}
async function flushQueue() {
  if (S.flushing || offline() || !S.me) return;
  let items;
  try { items = await Q.all(); } catch { return; }
  if (!items.length) return;
  S.flushing = true;
  let sent = 0;
  try {
    for (const it of items) {
      try {
        await uploadGroup(it.files, it.params);
        await Q.del(it.id); sent++;
      } catch (e) {
        if (e instanceof NetErr) {
          if (e.results?.length) { await Q.del(it.id); await Q.add({ ...it, id: undefined, files: e.rest, params: { ...it.params, task_id: e.taskId } }); }
          break;
        }
        if (e.status === 401) { showLogin(); break; }
        await Q.del(it.id);
        toast(`Kuyruktaki bir fotoğraf yüklenemedi: ${esc(e.message)}`);
      }
    }
  } finally { S.flushing = false; }
  await refreshQueueCount();
  if (sent) { toast(`Kuyruktan <b>${sent} gönderim</b> yüklendi`); reload().catch(() => {}); }
}

/* ---------- konum ---------- */
let lastPos = null;
function deviceGps() {
  if (!window.isSecureContext || !navigator.geolocation) return Promise.resolve(null);
  if (lastPos && Date.now() - lastPos.t < 120000) return Promise.resolve(lastPos);
  return new Promise(res => {
    const done = v => { if (v) lastPos = v; res(v); };
    const timer = setTimeout(() => done(null), 8000);
    navigator.geolocation.getCurrentPosition(
      p => { clearTimeout(timer); done({ lat: +p.coords.latitude.toFixed(6), lng: +p.coords.longitude.toFixed(6), acc: Math.round(p.coords.accuracy), t: Date.now() }); },
      () => { clearTimeout(timer); done(null); },
      { enableHighAccuracy: true, timeout: 7500, maximumAge: 60000 });
  });
}

/* ---------- bildirimler ---------- */
function toast(html) {
  const el = document.createElement('div');
  el.className = 'toast'; el.innerHTML = html;
  const box = $('#toasts'); box.append(el);
  while (box.children.length > 3) box.firstElementChild.remove();
  setTimeout(() => el.remove(), 4200);
}

/* ---------- giriş ---------- */
function showSetup(msg = '') {
  S.me = null; S.loaded = false;
  $('#app').hidden = true; $('#sheet').hidden = true;
  const box = $('#login'); box.hidden = false;
  box.innerHTML = `<form id="setup-form" autocomplete="off">
    <h1><span class="mark">${ic('camera')}</span>FotoTakip</h1>
    <p class="hint"><b>İlk kurulum.</b> Kurulum kodu Termux ekranında yazıyor (ya da: <code>cat ~/fototakip-data/kurulum-kodu.txt</code>).</p>
    <label class="field"><span>Kurulum kodu</span><input id="su-code" class="input" autocapitalize="characters" placeholder="ABCD-1234" required></label>
    <label class="field"><span>Adın</span><input id="su-name" class="input" autocomplete="name" required maxlength="80"></label>
    <label class="field"><span>Kullanıcı adı</span><input id="su-user" class="input" autocomplete="username" autocapitalize="none" pattern="[a-z0-9._\\-]{3,32}" placeholder="küçük harf, rakam, nokta, tire" required></label>
    <label class="field"><span>Parola</span><input id="su-pass" class="input" type="password" autocomplete="new-password" minlength="8" required></label>
    <label class="field"><span>Parola (tekrar)</span><input id="su-pass2" class="input" type="password" autocomplete="new-password" minlength="8" required></label>
    <p class="err" id="lg-err">${esc(msg)}</p>
    <button class="btn primary" type="submit">${ic('check', 's')}Hesabı oluştur</button>
  </form>`;
  $('#su-code').focus();
}
async function doSetup() {
  const err = $('#lg-err');
  if ($('#su-pass').value !== $('#su-pass2').value) { err.textContent = 'Parolalar aynı değil.'; return; }
  try {
    await api('POST', '/api/setup', { code: $('#su-code').value, name: $('#su-name').value.trim(), username: $('#su-user').value.trim().toLowerCase(), password: $('#su-pass').value });
    S.needsSetup = false;
    Object.assign(S, { view: 'board', open: null, project: 'all', q: '', searchIds: null, mcol: 'progress', pending: [] });
    $('#login').hidden = true; $('#app').hidden = false;
    await reload();
    startEvents();
    toast('Hoş geldin. İlk müşterini ve ekibini <b>Yönetim</b> bölümünden ekle.');
  } catch (e) {
    if (e?.code === 'already_setup') { S.needsSetup = false; showLogin(e.message); return; }
    err.textContent = e instanceof NetErr ? 'Sunucuya ulaşılamıyor.' : e.message;
  }
}
function showLogin(msg = '') {
  if (S.needsSetup) return showSetup(msg);
  S.me = null; S.loaded = false;
  $('#app').hidden = true; $('#sheet').hidden = true;
  const box = $('#login'); box.hidden = false;
  box.innerHTML = `<form id="login-form" autocomplete="on">
    <h1><span class="mark">${ic('camera')}</span>FotoTakip</h1>
    <label class="field"><span>Kullanıcı adı</span><input id="lg-user" class="input" name="username" autocomplete="username" autocapitalize="none" required></label>
    <label class="field"><span>Parola</span><input id="lg-pass" class="input" type="password" name="password" autocomplete="current-password" required></label>
    <p class="err" id="lg-err">${esc(msg)}</p>
    <button class="btn primary" type="submit">${ic('arrow', 's')}Giriş yap</button>
  </form>`;
  $('#lg-user').focus();
}
async function doLogin(username, password) {
  try {
    await api('POST', '/api/login', { username, password });
    Object.assign(S, { view: 'board', open: null, project: 'all', q: '', searchIds: null, mcol: 'progress', pending: [] });
    $('#login').hidden = true; $('#app').hidden = false;
    await reload();
    startEvents();
    flushQueue();
  } catch (e) {
    const el = $('#lg-err');
    if (el) el.textContent = e instanceof NetErr ? 'Sunucuya ulaşılamıyor.' : e.message;
  }
}

/* ---------- canlı güncelleme ---------- */
let es = null;
function startEvents() {
  if (es || !window.EventSource) return;
  es = new EventSource('/api/events');
  es.onmessage = ev => {
    try { const d = JSON.parse(ev.data); if (d.by !== S.me?.id) reloadSoon(); } catch {}
  };
  es.onerror = () => { /* tarayıcı kendisi yeniden bağlanır */ };
}

/* ---------- başlık ve menü ---------- */
const VIEW_T = { board: 'İşler', gallery: 'Galeri', camera: 'Kamera', map: 'Harita', admin: 'Yönetim', profile: 'Profil', report: 'Rapor' };
function renderHeader() {
  if (!S.me) return;
  const showProj = ['board', 'gallery'].includes(S.view) && S.projects.length > 1;
  $('#hdr').innerHTML = `<h1><span class="mark brand-s">${ic('camera')}</span><span>${VIEW_T[S.view] || 'FotoTakip'}</span></h1>
    ${showProj ? `<label class="vh" for="hdr-proj">Müşteri</label><select id="hdr-proj" class="select hdr-sel" data-change="hdrProj">
      <option value="all"${S.project === 'all' ? ' selected' : ''}>Tüm müşteriler</option>
      ${S.projects.map(p => `<option value="${p.id}"${S.project === p.id ? ' selected' : ''}>${esc(p.client || p.name)}</option>`).join('')}</select>` : ''}
    ${offline() ? `<span class="ib warn" role="img" aria-label="Çevrimdışı" title="Çevrimdışı">${ic('cloudoff')}</span>` : ''}
    ${S.queueCount ? `<button class="ib warn" data-act="flush" aria-label="${S.queueCount} gönderim kuyrukta, şimdi yükle" title="Şimdi yükle">${ic('upload')}<span class="dotb">${S.queueCount}</span></button>` : ''}
    <button class="ib top-me" data-act="go" data-view="profile" aria-label="Profil" title="${esc(S.me.name)}"><span class="me">${esc(S.me.short)}</span></button>`;
}
function renderDock() {
  if (!S.me) return;
  const fifth = canDispatch() ? ['admin', 'Yönetim', 'shield'] : ['profile', 'Profil', 'user'];
  const items = [['board', 'İşler', 'board'], ['gallery', 'Galeri', 'gallery'], ['camera', 'Kamera', 'camera'], ['map', 'Harita', 'map'], fifth];
  const cur = v => (S.view === v || (v === 'profile' && S.view === 'report')) ? ' aria-current="page"' : '';
  $('#dock').innerHTML = `<div class="nav-brand"><span class="mark">${ic('camera')}</span><span class="hide-m">FotoTakip</span></div>`
    + items.map(([v, l, i]) => `<button class="nav ${v === 'camera' ? 'cam' : ''}" data-act="go" data-view="${v}"${cur(v)}><span class="pillbg">${ic(i)}</span><span>${l}</span>${v === 'camera' && S.queueCount ? `<span class="dotb">${S.queueCount}</span>` : ''}</button>`).join('')
    + `<button class="nav-me" data-act="go" data-view="profile" aria-label="Profil"${S.view === 'profile' ? ' aria-current="page"' : ''}><span class="me">${esc(S.me.short)}</span><span class="hide-m">${esc(S.me.name)}</span></button>`;
}

/* ---------- işler ---------- */
function viewBoard() {
  const ts = visibleTasks();
  const modes = [['kanban', 'board', 'Pano'], ['list', 'list', 'Liste'], ['calendar', 'calendar', 'Takvim']];
  const head = `<div class="bar">
    <div class="search">${ic('search', 's')}<label class="vh" for="q">İşlerde ara</label><input id="q" class="input" type="search" placeholder="Ara" value="${esc(S.q)}" data-input="search" autocomplete="off"></div>
    <div class="seg" role="group" aria-label="Görünüm">${modes.map(([m, i, l]) => `<button data-act="mode" data-mode="${m}" aria-pressed="${S.boardMode === m}" aria-label="${l}" title="${l}">${ic(i, 's')}</button>`).join('')}</div>
    ${canDispatch() && S.projects.length ? `<button class="btn primary icon" data-act="newTask" aria-label="Yeni iş" title="Yeni iş">${ic('plus')}</button>` : ''}
  </div>`;
  if (!S.projects.length && canCust()) return head + empty('building', 'Henüz müşteri yok', `<button class="btn primary" data-act="admNew" data-kind="customer">${ic('plus', 's')}Müşteri ekle</button>`);
  if (!S.tasks.length) return head + empty('board', canDispatch() ? 'Henüz iş yok' : 'Sana atanmış iş yok',
    canDispatch() ? `<button class="btn primary" data-act="newTask">${ic('plus', 's')}İş aç</button>` : '');
  if (S.boardMode === 'list') return head + viewList(ts);
  if (S.boardMode === 'calendar') return head + viewCalendar(ts);
  const cols = STATUSES.map(s => {
    const items = ts.filter(t => t.status === s.id);
    return `<section class="col ${S.mcol === s.id ? 'active' : ''}" data-status="${s.id}" aria-label="${s.name}">
      <div class="col-head">${stPill(s.id)}<span class="count">${items.length}</span></div>
      ${items.length ? items.map(card).join('') : `<div class="empty"><span class="st ${s.id}">${ST_ICON[s.id]}</span></div>`}
    </section>`;
  }).join('');
  return head + `
    <div class="seg coltabs" role="group" aria-label="Durum">${STATUSES.map(s => `<button data-act="mcol" data-col="${s.id}" aria-pressed="${S.mcol === s.id}"><span class="st ${s.id}">${ST_ICON[s.id]}</span>${s.short}<b class="num">${ts.filter(t => t.status === s.id).length}</b></button>`).join('')}</div>
    <div class="board">${cols}</div>`;
}
function canAdvance(t) {
  if (t.status === 'done') return false;
  if (canDispatch()) return !isPool(t) || isMgr();
  return t.assignee_id === S.me.id && t.status !== 'review';
}
function card(t) {
  const pid = coverPid(t), anns = annCount(t), p = proj(t.project_id), pool = isPool(t);
  const done = t.checklist.filter(c => c.done).length;
  return `<article class="card ${t.status}" draggable="${canAdvance(t)}" data-act="open" data-id="${t.id}" tabindex="0" aria-label="${esc(t.no_label)} ${esc(t.title)}, ${stName(t.status)}">
    <div class="cover">${pid ? `<img src="${thumb(pid)}" alt="" loading="lazy">` : ic('image', 'l')}
      <div class="ov tl">${t.rejected_reason ? `<span class="glass danger">${ic('swap', 'xs')}Geri</span>` : ''}${t.priority === 'high' ? `<span class="glass hot">${ic('alert', 'xs')}Acil</span>` : ''}${pool ? `<span class="glass">${ic('users', 'xs')}Havuz</span>` : ''}</div>
      <div class="ov br"><span class="glass" title="Fotoğraf">${ic('camera', 'xs')}${t.photos.length}</span>${anns ? `<span class="glass" title="İşaret">${ic('pen', 'xs')}${anns}</span>` : ''}${t.checklist.length ? `<span class="glass" title="Kontrol listesi">${ic('check', 'xs')}${done}/${t.checklist.length}</span>` : ''}${t.signature ? `<span class="glass" title="İmzalı">${ic('sign', 'xs')}</span>` : ''}</div>
    </div>
    ${pool && canDispatch() ? `<button class="claim" data-act="claim" data-id="${t.id}" aria-label="Üstlen" title="Üstlen">${ic('plus', 's')}</button>` : canAdvance(t) ? `<button class="adv" data-act="advance" data-id="${t.id}" aria-label="Sonraki duruma taşı" title="Sonraki duruma taşı">${ic('arrow', 's')}</button>` : ''}
    <div class="card-body">
      <h3 class="${t.untitled ? 'untitled' : ''}">${esc(t.title)}</h3>
      <div class="meta">${skillChip(t.skill_id)}<span class="cust">${ic('pin', 'xs')}<span>${esc(p?.client || p?.short || '')}</span></span><span class="due ${dueCls(t)}">${dueLabel(t)}</span>${av(t.assignee_id)}</div>
    </div></article>`;
}
function viewList(ts) {
  const rows = [...ts].sort((a, b) => (a.status === 'done') - (b.status === 'done') || a.due.localeCompare(b.due));
  if (!rows.length) return empty('search', 'Eşleşen iş yok');
  return `<div class="list">${rows.map(t => `<button class="lrow" data-act="open" data-id="${t.id}">
      ${coverPid(t) ? `<img src="${thumb(coverPid(t))}" alt="" loading="lazy">` : `<span class="ph">${ic('image', 's')}</span>`}
      <span style="min-width:0"><b class="${t.untitled ? 'muted' : ''}">${esc(t.title)}</b><span class="meta">${skillChip(t.skill_id)}<span class="no">${esc(t.no_label)}</span><span class="cust">${esc(proj(t.project_id)?.client || proj(t.project_id)?.short || '')}</span></span></span>
      <span class="end">${stPill(t.status)}<span class="due ${dueCls(t)}">${dueLabel(t)}</span></span></button>`).join('')}</div>`;
}
function viewCalendar(ts) {
  const { y, m } = S.cal;
  const first = new Date(y, m, 1);
  const start = new Date(y, m, 1 - (first.getDay() + 6) % 7);
  const days = Array.from({ length: 42 }, (_, i) => { const d = new Date(start); d.setDate(start.getDate() + i); return d; });
  const shown = days[35].getMonth() !== m ? days.slice(0, 35) : days;
  return `<div class="panel stack">
    <div class="bar"><b class="grow" style="font-size:20px">${MONTHS[m]} ${y}</b>
      <button class="btn icon" data-act="cal" data-d="-1" aria-label="Önceki ay">${ic('chevl', 's')}</button><button class="btn" data-act="cal" data-d="0">Bugün</button><button class="btn icon" data-act="cal" data-d="1" aria-label="Sonraki ay">${ic('chevron', 's')}</button></div>
    <div class="cal">${['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'].map(d => `<div class="dn">${d}</div>`).join('')}
    ${shown.map(d => { const ds = dayStr(d); const evs = ts.filter(t => t.due === ds);
      return `<div class="day ${d.getMonth() !== m ? 'out' : ''} ${ds === todayStr() ? 'today' : ''}"><span class="dnum">${d.getDate()}</span>
        ${evs.map(t => `<button class="ev ${t.status} ${isLate(t) ? 'late' : ''}" data-act="open" data-id="${t.id}" title="${esc(t.title)}" aria-label="${esc(t.title)}">${esc(t.title)}</button>`).join('')}</div>`; }).join('')}
    </div></div>`;
}

/* ---------- galeri ---------- */
function viewGallery() {
  const links = [];
  visibleTasks().forEach(t => t.photos.forEach(p => { const ph = S.photos[p.pid]; if (ph) links.push({ t, p, ph }); }));
  links.sort((a, b) => String(b.ph.taken_at).localeCompare(String(a.ph.taken_at)));
  const shown = links.filter(l => S.galType === 'all' || l.p.type === S.galType);
  const types = [['all', 'Tümü'], ...Object.entries(TYPES)];
  return `<div class="chips" role="group" aria-label="Fotoğraf türü">${types.map(([k, l]) => `<button class="chip" data-act="gal" data-type="${k}" aria-pressed="${S.galType === k}">${ic(k === 'all' ? 'gallery' : TYPE_IC[k], 'xs')}${l} <b>${k === 'all' ? links.length : links.filter(x => x.p.type === k).length}</b></button>`).join('')}</div>
    ${shown.length ? `<div class="masonry">${shown.map(({ t, p, ph }) => `<button class="tile" data-act="open" data-id="${t.id}" data-photo="${ph.id}" aria-label="${esc(TYPES[p.type])}: ${esc(t.title)}">
      <img src="${thumb(ph.id)}" alt="" loading="lazy"><span class="glass tg ${p.type}">${ic(TYPE_IC[p.type], 'xs')}${TYPES[p.type]}</span><span class="cap">${esc(t.title)}</span></button>`).join('')}</div>`
      : empty('gallery', 'Fotoğraf yok', `<button class="btn primary" data-act="go" data-view="camera">${ic('camera', 's')}Fotoğraf çek</button>`)}`;
}

/* ---------- kamera ---------- */
async function warmCamGps() {
  if (!window.isSecureContext || !navigator.geolocation) return;
  S.cam.locating = true; renderMain();
  const pos = await deviceGps();
  S.cam.locating = false;
  if (S.view !== 'camera') return;
  if (pos) {
    S.here = pos;
    const n = nearestProject(pos);
    S.cam.near = n ? { id: n.p.id, d: n.d } : null;
    if (n && n.d <= NEAR_METERS && !S.cam.userPicked) S.cam.project = n.p.id;
  }
  render();
}
function camNearLine() {
  if (!window.isSecureContext) return '';
  if (S.cam.locating) return `<p class="near muted">${ic('target', 'xs')}Konum alınıyor</p>`;
  const n = S.cam.near; if (!n) return '';
  const p = proj(n.id); if (!p) return '';
  const nm = esc(p.client || p.short);
  if (n.d <= NEAR_METERS) return S.cam.project === p.id
    ? `<p class="near ok">${ic('pin', 'xs')}<b>${nm}</b> ${fmtDist(n.d)}</p>`
    : `<p class="near">${ic('pin', 'xs')}${nm} ${fmtDist(n.d)} <button class="linkbtn" data-act="camPickNear">Seç</button></p>`;
  return `<p class="near warn">${ic('pin', 'xs')}Yakında müşteri yok${canCust() ? ` <button class="linkbtn" data-act="camNewHere">Buraya ekle</button>` : ''}</p>`;
}
function viewCamera() {
  const f = S.cam;
  const targets = S.tasks.filter(t => t.status !== 'done' && mine(t));
  if (f.target !== 'new' && !targets.some(t => t.id === f.target)) f.target = 'new';
  if (!S.projects.length) return empty('camera', canCust() ? 'Önce bir müşteri ekle' : 'Sana atanmış iş yok',
    canCust() ? `<button class="btn primary" data-act="admNew" data-kind="customer">${ic('plus', 's')}Müşteri ekle</button>` : '');
  const n = S.pending.length;
  const label = f.target === 'new' ? (n > 1 ? `${n} fotoğrafla iş aç` : 'İş aç') : (n > 1 ? `${n} fotoğrafı ekle` : 'İşe ekle');
  return `<div class="cam">
    <div class="stack">
      <label class="shutter" for="cam-file"><span class="lens">${ic('camera')}</span>Fotoğraf çek</label>
      <input id="cam-file" class="vh" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" multiple data-change="camFile">
      <label class="btn" for="cam-gal">${ic('image', 's')}Galeriden seç</label>
      <input id="cam-gal" class="vh" type="file" accept="image/jpeg,image/png,image/webp" multiple data-change="camFile">
      ${n ? `<div class="pending">${S.pending.map((p, i) => `<figure><img src="${p.url}" alt="Seçilen fotoğraf ${i + 1}"><button data-act="unpend" data-i="${i}" aria-label="Kaldır">${ic('x', 's')}</button></figure>`).join('')}</div>` : ''}
    </div>
    <div class="panel stack">
      <div class="types" role="radiogroup" aria-label="Fotoğraf türü">${Object.entries(TYPES).map(([k, l]) => `<label class="tg ${k}"><input type="radio" name="cam-type" id="cam-type-${k}" value="${k}" data-change="camType" ${f.type === k ? 'checked' : ''}><span>${ic(TYPE_IC[k])}${l}</span></label>`).join('')}</div>
      <label class="field"><span>${ic('board', 'xs')}Nereye</span><select id="cam-target" class="select" data-change="camTarget">
        <option value="new"${f.target === 'new' ? ' selected' : ''}>Yeni iş</option>
        ${targets.map(t => `<option value="${t.id}"${f.target === t.id ? ' selected' : ''}>${esc(t.no_label)} ${esc(t.title)}</option>`).join('')}</select></label>
      ${f.target === 'new' ? `<label class="field"><span>${ic('building', 'xs')}Müşteri</span><select id="cam-project" class="select" data-change="camProject">${S.projects.map(p => `<option value="${p.id}"${f.project === p.id ? ' selected' : ''}>${esc(p.client || p.name)}</option>`).join('')}</select></label>${camNearLine()}
        <label class="field"><span>${ic('pen', 'xs')}Başlık</span><input id="cam-title" class="input" placeholder="İsteğe bağlı" autocomplete="off" data-keep></label>` : ''}
      <button class="btn primary" data-act="camSubmit" ${n ? '' : 'disabled'}>${ic('upload', 's')}${label}</button>
      ${offline() ? `<div class="note">${ic('cloudoff', 's')}<span>Çevrimdışı: fotoğraflar kuyruğa alınır.</span></div>` : ''}
    </div>
  </div>`;
}

/* ---------- harita ---------- */
const TYPE_COLOR = { before: '#5B6876', progress: '#A86600', after: '#1F7A48', issue: '#B8381F' };
const SRC_LABEL = { photo: 'Fotoğraftan', geocode: 'Adres servisinden', manual: 'Elle girildi', map: 'Haritadan', device: 'Cihaz konumu', none: '' };
const NEAR_METERS = 300;
const M = { map: null, el: null, customers: null, photos: null, me: null, meAcc: null, temp: null, watch: null, follow: false, didFit: false, lastPanelPos: null };
const distM = (a, b, c, d) => { const R = 6371000, r = x => x * Math.PI / 180; const dp = r(c - a), dl = r(d - b); const h = Math.sin(dp / 2) ** 2 + Math.cos(r(a)) * Math.cos(r(c)) * Math.sin(dl / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); };
const fmtDist = m => m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1).replace('.', ',')} km`;
const located = () => S.projects.filter(p => p.lat != null);  // arşivlenenler hariç
const openTasksOf = p => S.tasks.filter(t => t.project_id === p.id && t.status !== 'done');
const nearestProject = pos => {
  let best = null;
  for (const p of located()) { const d = distM(pos.lat, pos.lng, p.lat, p.lng); if (!best || d < best.d) best = { p, d }; }
  return best;
};
const dirUrl = p => `https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lng}`;

function renderMapView() {
  document.body.classList.add('mapmode');
  if (!window.L) { $('#main').innerHTML = '<div class="wrap"><div class="empty">Harita kütüphanesi yüklenemedi. Sayfayı yenile.</div></div>'; return; }
  if (!M.el || !document.body.contains(M.el)) {
    $('#main').innerHTML = `<div class="mapview" id="mapview">
      <div id="leaf" class="leaf" aria-label="Müşteri haritası"></div>
      <div class="map-top"><div class="search">${ic('search', 's')}<label class="vh" for="map-q">Müşteri ara</label><input id="map-q" class="input" type="search" placeholder="Müşteri ara" autocomplete="off" data-input="mapSearch" data-keep></div>
        <div id="map-chips" class="chips"></div></div>
      <div class="map-fabs"><button class="fab" id="fab-me" data-act="locateMe" aria-label="Konumuma git" title="Konumuma git">${IC.target}</button>
        ${canCust() ? `<button class="fab" data-act="pickNew" aria-label="Haritadan müşteri ekle" title="Haritadan müşteri ekle">${IC.plus}</button>` : ''}</div>
      <section id="map-panel" class="map-panel" aria-live="polite"></section>
    </div>`;
    initLeaflet();
  }
  renderMapChips();
  renderMapPanel();
  updateMapLayers();
}
function destroyMap() {
  document.body.classList.remove('mapmode');
  if (M.watch != null) { navigator.geolocation.clearWatch(M.watch); M.watch = null; }
  if (M.map) { M.map.remove(); }
  Object.assign(M, { map: null, el: null, customers: null, photos: null, me: null, meAcc: null, temp: null, follow: false, didFit: false });
}
function initLeaflet() {
  M.el = $('#leaf');
  const map = L.map(M.el, { zoomControl: false, attributionControl: true, tap: true }).setView([41.0082, 28.9784], 11);
  L.control.zoom({ position: 'topright' }).addTo(map);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, referrerPolicy: 'strict-origin-when-cross-origin',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> katkıda bulunanlar'
  }).addTo(map);
  M.customers = L.layerGroup().addTo(map);
  M.photos = L.layerGroup();
  if (S.mapLayers.photos) M.photos.addTo(map);
  map.on('click', e => onMapClick(e.latlng));
  map.on('dragstart', () => { M.follow = false; $('#fab-me')?.classList.remove('on'); });
  M.map = map;
  setTimeout(() => map.invalidateSize(), 0);
  // izin önceden verilmişse konumu hemen göster
  if (navigator.permissions?.query && window.isSecureContext) {
    navigator.permissions.query({ name: 'geolocation' }).then(r => { if (r.state === 'granted') startWatch(false); }).catch(() => {});
  }
}
function customerIcon(p) {
  const open = openTasksOf(p);
  const late = open.some(isLate);
  const sel = S.mapDetail && p.id === S.mapPick;
  return L.divIcon({
    className: 'cpin-wrap', iconSize: [0, 0], iconAnchor: [0, 0],
    html: `<div class="cpin ${late ? 'late' : ''} ${sel ? 'sel' : ''} ${open.length ? '' : 'idle'}"><b>${open.length}</b></div><span class="cpin-label">${esc(p.client || p.short)}</span>`
  });
}
function updateMapLayers() {
  if (!M.map) return;
  const q = (S.mapQ || '').trim().toLocaleLowerCase('tr');
  const match = p => !q || [p.client, p.name, p.short, p.address].some(x => (x || '').toLocaleLowerCase('tr').includes(q));
  M.customers.clearLayers();
  const shown = located().filter(p => match(p) && (!S.mapLayers.openOnly || openTasksOf(p).length));
  shown.forEach(p => {
    const m = L.marker([p.lat, p.lng], { icon: customerIcon(p), keyboard: true, title: p.client || p.name, riseOnHover: true, zIndexOffset: p.id === S.mapPick ? 1000 : 0 });
    m.on('click', ev => { L.DomEvent.stopPropagation(ev); S.mapPick = p.id; S.mapMode = null; removeTemp(); updateMapLayers(); renderMapPanel(); });
    m.addTo(M.customers);
  });
  M.photos.clearLayers();
  if (S.mapLayers.photos) {
    S.tasks.forEach(t => t.photos.forEach(x => {
      const ph = S.photos[x.pid];
      if (!ph || ph.lat == null || !(ph.gps_source === 'exif' || ph.gps_source === 'device')) return;
      const c = L.circleMarker([ph.lat, ph.lng], { radius: 6, color: '#FFFFFF', weight: 2, fillColor: TYPE_COLOR[x.type], fillOpacity: .95 });
      c.bindTooltip(`${esc(TYPES[x.type])} · ${esc(t.title)}`, { direction: 'top', offset: [0, -6] });
      c.on('click', ev => { L.DomEvent.stopPropagation(ev); S.open = t.id; S.active = ph.id; renderSheet(); });
      c.addTo(M.photos);
    }));
  }
  if (!M.didFit) {
    M.didFit = true;
    const pts = shown.map(p => [p.lat, p.lng]);
    const wide = innerWidth >= 900;
    const pad = wide ? { paddingTopLeft: [410, 120], paddingBottomRight: [60, 40] } : { paddingTopLeft: [40, 130], paddingBottomRight: [40, 40] };
    if (pts.length) M.map.fitBounds(pts.length === 1 ? [pts[0], pts[0]] : pts, { ...pad, maxZoom: 15 });
  }
}
function renderMapChips() {
  const box = $('#map-chips'); if (!box) return;
  const chip = (k, l) => `<button class="chip map-chip" data-act="mapLayer" data-k="${k}" aria-pressed="${!!S.mapLayers[k]}">${l}</button>`;
  box.innerHTML = chip('photos', `${ic('camera', 'xs')}Fotoğraflar`) + chip('openOnly', `${ic('board', 'xs')}Açık işler`) + (offline() ? `<span class="pill warn">${ic('cloudoff', 'xs')}Çevrimdışı</span>` : '');
}
function panelHead(title, sub) { return `<div class="mp-head"><div style="min-width:0"><b class="mp-title">${title}</b>${sub ? `<div class="addr">${sub}</div>` : ''}</div><button class="ib x" data-act="panelToggle" aria-label="${S.panelMin ? 'Paneli aç' : 'Paneli küçült'}">${ic(S.panelMin ? 'plus' : 'x', 's')}</button></div>`; }
function renderMapPanel() {
  const box = $('#map-panel'); if (!box) return;
  box.classList.toggle('min', !!S.panelMin);
  const here = S.here;
  if (S.mapMode === 'new' || S.mapMode === 'move') { box.innerHTML = panelPick(); return; }
  const p = proj(S.mapPick);
  if (p && S.mapDetail) { box.innerHTML = panelCustomer(p, here); return; }
  // liste: yakınımdakiler ya da açık işe göre
  const q = (S.mapQ || '').trim().toLocaleLowerCase('tr');
  let list = S.projects.filter(x => !q || [x.client, x.name, x.short, x.address].some(v => (v || '').toLocaleLowerCase('tr').includes(q)));
  list = list.map(x => ({ p: x, d: here && x.lat != null ? distM(here.lat, here.lng, x.lat, x.lng) : null, open: openTasksOf(x).length }));
  list.sort((a, b) => here ? ((a.d ?? 9e9) - (b.d ?? 9e9)) : (b.open - a.open));
  const noLoc = S.projects.filter(x => x.lat == null).length;
  box.innerHTML = panelHead(here ? 'Yakınımdakiler' : 'Müşteriler', here ? `±${Math.round(here.acc ?? 0)} m` : '')
    + `<div class="mp-body">${list.length ? list.map(({ p: x, d, open }) => `<button class="mini" data-act="mapSelect" data-id="${x.id}">
        <span class="cdot ${open ? '' : 'idle'}">${open}</span>
        <span style="min-width:0"><b>${esc(x.client || x.name)}</b><span class="addr" style="display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(x.address || 'Adres yok')}</span></span>
        <span class="muted num">${d != null ? fmtDist(d) : x.lat == null ? ic('pin', 'xs') : ''}</span></button>`).join('') : empty('search', 'Eşleşen müşteri yok')}
      ${noLoc ? `<p class="muted row" style="font-size:13px;margin:6px 2px 0">${ic('pin', 'xs')}${noLoc} müşterinin konumu yok</p>` : ''}</div>`;
}
function panelCustomer(p, here) {
  const open = openTasksOf(p);
  const done = S.tasks.filter(t => t.project_id === p.id && t.status === 'done').length;
  const d = here && p.lat != null ? distM(here.lat, here.lng, p.lat, p.lng) : null;
  return panelHead(esc(p.client || p.name), esc(p.name)) + `<div class="mp-body">
    <div class="mp-addr">${p.address ? esc(p.address) : '<span class="muted">Adres yok</span>'}${p.address_source && SRC_LABEL[p.address_source] ? ` <span class="gps-src">${SRC_LABEL[p.address_source]}</span>` : ''}</div>
    ${p.suggested_address ? `<div class="note"><b>Fotoğraflardan farklı bir adres bulundu:</b> ${esc(p.suggested_address)}
      ${canCust() ? `<div class="row" style="margin-top:6px"><button class="btn primary" data-act="applySug" data-id="${p.id}">Bu adresi kullan</button><button class="btn" data-act="dismissSug" data-id="${p.id}">Yoksay</button></div>` : ''}</div>` : ''}
    ${p.contact ? `<div class="addr row">${ic('user', 'xs')}${esc(p.contact)}</div>` : ''}
    <div class="row muted num" style="font-size:12.5px">${p.lat != null ? `${p.lat.toFixed(5)}°, ${p.lng.toFixed(5)}° · ${SRC_LABEL[p.location_source] || ''}` : 'Konum yok'}${d != null ? ` · sana ${fmtDist(d)}` : ''}</div>
    <div class="row">
      ${p.lat != null ? `<a class="btn primary" href="${dirUrl(p)}" target="_blank" rel="noopener">${ic('nav', 's')}Yol tarifi</a>` : ''}
      ${p.phone ? `<a class="btn icon" href="tel:${esc(p.phone.replace(/[^\d+]/g, ''))}" aria-label="Ara" title="Ara">${ic('phone', 's')}</a>` : ''}
      <button class="btn icon" data-act="mapBack" aria-label="Listeye dön" title="Listeye dön">${ic('list', 's')}</button>
      ${canCust() ? `<button class="btn icon" data-act="pickMove" data-id="${p.id}" aria-label="${p.lat != null ? 'Konumu düzelt' : 'Konum ekle'}" title="${p.lat != null ? 'Konumu düzelt' : 'Konum ekle'}">${ic('target', 's')}</button>` : ''}
    </div>
    <div class="sec-h" style="margin:8px 0 0"><h4>${ic('board', 's')}Açık işler ${open.length}</h4><span class="muted row">${ic('check', 'xs')}${done}</span></div>
    ${open.length ? open.map(t => `<button class="mini" data-act="open" data-id="${t.id}">${coverPid(t) ? `<img src="${thumb(coverPid(t))}" alt="">` : '<span></span>'}<span style="min-width:0"><b>${esc(t.title)}</b><span class="due ${dueCls(t)}">${dueLabel(t)}</span></span>${stPill(t.status)}</button>`).join('') : empty('check', 'Açık iş yok')}
  </div>`;
}
function panelPick() {
  const isNew = S.mapMode === 'new';
  const p = isNew ? null : proj(S.mapPick);
  const pk = S.pickPoint;
  const title = isNew ? 'Yeni müşteri' : `Konum: ${esc(p?.client || p?.name || '')}`;
  if (!pk) return panelHead(title, 'Haritada müşterinin yerine dokun ya da bulunduğun yeri kullan')
    + `<div class="mp-body"><div class="row">${window.isSecureContext ? '<button class="btn primary" data-act="pickHere">Bulunduğum yeri kullan</button>' : ''}<button class="btn" data-act="pickCancel">Vazgeç</button></div></div>`;
  const addr = S.pickAddr;
  const addrLine = addr === undefined ? '<span class="muted">Adres aranıyor…</span>' : addr ? esc(addr) : '<span class="muted">Adres bulunamadı, elle yaz.</span>';
  if (!isNew) return panelHead(title, `${pk.lat.toFixed(5)}°, ${pk.lng.toFixed(5)}°`) + `<div class="mp-body">
    <div class="mp-addr">${addrLine}</div>
    <label class="row" style="font-size:13px;gap:6px"><input type="checkbox" id="mv-addr" ${addr ? 'checked' : 'disabled'}> Adresi de bununla değiştir</label>
    <div class="row"><button class="btn primary" data-act="pickSaveMove">Konumu kaydet</button><button class="btn" data-act="pickCancel">Vazgeç</button></div></div>`;
  return panelHead(title, `${pk.lat.toFixed(5)}°, ${pk.lng.toFixed(5)}°`) + `<div class="mp-body">
    <form class="stack" data-form="mapCustomer">
      <input id="mc-client" class="input" placeholder="Müşteri adı" required data-keep>
      <input id="mc-name" class="input" placeholder="Saha adı (örn. Kuzguncuk · Ev)" data-keep>
      <input id="mc-contact" class="input" type="tel" placeholder="Telefon" data-keep>
      <input id="mc-address" class="input" placeholder="Adres" value="${esc(addr || '')}" data-addr="${esc(addr || '')}">
      <div class="row"><button class="btn primary" type="submit">Müşteriyi ekle</button><button class="btn" type="button" data-act="pickCancel">Vazgeç</button></div>
    </form></div>`;
}
function removeTemp() { if (M.temp) { M.temp.remove(); M.temp = null; } }
async function setPickPoint(latlng) {
  S.pickPoint = { lat: +latlng.lat.toFixed(6), lng: +latlng.lng.toFixed(6) };
  S.pickAddr = undefined;
  removeTemp();
  M.temp = L.marker([S.pickPoint.lat, S.pickPoint.lng], { draggable: true, icon: L.divIcon({ className: 'cpin-wrap', iconSize: [0, 0], html: '<div class="cpin new"><b>+</b></div>' }) }).addTo(M.map);
  M.temp.on('dragend', e => setPickPoint(e.target.getLatLng()));
  S.panelMin = false; renderMapPanel();
  if (innerWidth < 900) $('#map-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });  // telefonda form harita altında
  const want = S.pickPoint;
  try { const r = await api('GET', `/api/geocode?lat=${want.lat}&lng=${want.lng}`); if (S.pickPoint === want) S.pickAddr = r.address; }
  catch (e) { if (S.pickPoint === want) S.pickAddr = null; }
  if (S.pickPoint === want) renderMapPanel();
}
function onMapClick(latlng) {
  if (S.mapMode === 'new' || S.mapMode === 'move') { setPickPoint(latlng); return; }
  if (S.mapDetail) { S.mapDetail = false; S.mapPick = null; updateMapLayers(); renderMapPanel(); }
}
function showMe(pos, fly) {
  if (!M.map) return;
  const ll = [pos.lat, pos.lng];
  if (!M.me) {
    M.meAcc = L.circle(ll, { radius: pos.acc || 30, color: '#1A73E8', weight: 1, fillColor: '#1A73E8', fillOpacity: .12, interactive: false }).addTo(M.map);
    M.me = L.circleMarker(ll, { radius: 8, color: '#FFFFFF', weight: 3, fillColor: '#1A73E8', fillOpacity: 1 }).addTo(M.map);
    M.me.bindTooltip('Buradasın', { direction: 'top', offset: [0, -8] });
  } else { M.me.setLatLng(ll); M.meAcc.setLatLng(ll).setRadius(pos.acc || 30); }
  if (fly || M.follow) M.map.flyTo(ll, Math.max(M.map.getZoom(), 16), { duration: .6 });
}
function startWatch(fly) {
  if (!window.isSecureContext || !navigator.geolocation) { toast('Konum için güvenli bağlantı gerekli: bu telefonda <b>http://localhost:8080</b> ya da tünel adresi.'); return; }
  M.follow = !!fly; $('#fab-me')?.classList.toggle('on', M.follow);
  if (S.here && fly) showMe(S.here, true);
  if (M.watch != null) return;
  M.watch = navigator.geolocation.watchPosition(p => {
    const pos = { lat: +p.coords.latitude.toFixed(6), lng: +p.coords.longitude.toFixed(6), acc: Math.round(p.coords.accuracy), t: Date.now() };
    const first = !S.here;
    S.here = pos; lastPos = pos;
    showMe(pos, first && fly);
    const moved = !M.lastPanelPos || distM(M.lastPanelPos.lat, M.lastPanelPos.lng, pos.lat, pos.lng) > 15;
    if (moved) { M.lastPanelPos = pos; renderMapPanel(); }
  }, err => {
    if (err.code === 1) {
      toast('Konum izni verilmedi. Tarayıcı ayarlarından bu site için konuma izin ver.');
      navigator.geolocation.clearWatch(M.watch); M.watch = null;
    } else if (!S.here) toast('Konum henüz alınamadı. GPS açık mı, gökyüzünü görüyor musun?');
  }, { enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 });
}

/* ---------- rapor ---------- */
function viewReport() {
  const p = proj(S.repProj);
  if (!p) return empty('report', 'Rapor için müşteri yok');
  const ts = S.tasks.filter(t => t.project_id === p.id);
  const fin = ts.filter(t => t.status === 'done' || t.status === 'review');
  const withPair = fin.filter(t => firstOf(t, 'before') && lastOf(t, 'after'));
  const missing = fin.filter(t => !(firstOf(t, 'before') && lastOf(t, 'after')));
  return `<div class="bar no-print"><label class="vh" for="rep-proj">Müşteri</label><select id="rep-proj" class="select grow" style="flex:1 1 200px" data-change="repProj">${S.projects.map(x => `<option value="${x.id}"${x.id === p.id ? ' selected' : ''}>${esc(x.client || x.name)}</option>`).join('')}</select>
    <button class="btn primary" data-act="print">${ic('download', 's')}PDF</button></div>
  <article class="report">
    <div class="rep-head"><div><h3>${esc(p.client || p.name)}</h3><div class="muted">${esc(p.address)}</div></div>
      <dl class="kv"><dt>Rapor tarihi</dt><dd class="num">${fmtDate(todayStr())} ${new Date().getFullYear()}</dd><dt>Hazırlayan</dt><dd>${esc(S.me.name)}</dd></dl></div>
    <div class="stats"><div><b>${ts.length}</b><span>iş</span></div><div><b>${ts.filter(t => t.status === 'done').length}</b><span>tamamlandı</span></div><div><b>${ts.filter(t => t.status === 'review').length}</b><span>onayda</span></div><div><b>${ts.filter(isLate).length}</b><span>gecikmede</span></div></div>
    ${withPair.length ? withPair.map(t => { const b = S.photos[firstOf(t, 'before').pid], a = S.photos[lastOf(t, 'after').pid];
      return `<section class="pair"><div class="bar"><b class="grow">${esc(t.no_label)} ${esc(t.title)}</b>${stPill(t.status)}</div>
        <div class="pair-imgs"><figure><img src="${full(b.id)}" alt="Önce"><span class="glass tg before">Önce</span><figcaption class="num">${fmtTime(b.taken_at)}</figcaption></figure>
        <figure><img src="${full(a.id)}" alt="Sonra"><span class="glass tg after">Sonra</span><figcaption class="num">${fmtTime(a.taken_at)}</figcaption></figure></div>
        ${t.checklist.length ? `<div class="muted" style="font-size:13px">${t.checklist.map(c => `${c.done ? '✓' : '○'} ${esc(c.text)}`).join('  ')}</div>` : ''}
        ${t.signature ? `<div class="row"><img src="/files/signature/${t.id}?v=${encodeURIComponent(t.signature.at)}" alt="Müşteri imzası" style="max-height:70px;background:#fff;border-radius:6px"><span class="muted" style="font-size:13px">${esc(t.signature.signer)}, ${fmtTime(t.signature.at)}</span></div>` : ''}</section>`; }).join('')
      : empty('image', 'Önce/sonra fotoğrafı tamamlanmış iş yok')}
    ${missing.length ? `<div class="note">${ic('alert', 's')}<span>Önce/sonra çifti eksik: ${missing.map(t => esc(t.no_label)).join(', ')}</span></div>` : ''}
  </article>`;
}

/* ---------- profil ---------- */
function viewProfile() {
  const secure = window.isSecureContext;
  const sw = s => `<button class="sw" data-act="theme" data-theme="${s.id}" aria-pressed="${S.theme === s.id}" style="--b:${s.b};--s:${s.s};--k:${s.k};--a:${s.a}"><span class="ph"><i></i><i></i><i></i><i class="a"></i></span>${s.name}</button>`;
  return `<section class="panel me-head"><span class="avatar big">${esc(S.me.short)}</span><div class="grow" style="min-width:0"><h2>${esc(S.me.name)}</h2><div class="row muted">${roleBadge(S.me.role)}<span>@${esc(S.me.username)}</span></div></div></section>
  <section class="panel"><div class="sec-h"><h4>${ic('palette', 's')}Görünüm</h4></div><div class="styles" role="group" aria-label="Stil">${STYLES.map(sw).join('')}</div></section>
  <section class="panel menu">
    ${canDispatch() ? `<button class="mi" data-act="go" data-view="admin">${ic('shield')}<span><b>Yönetim</b></span>${ic('chevron', 's')}</button>` : ''}
    <button class="mi" data-act="go" data-view="report">${ic('report')}<span><b>Teslim raporu</b></span>${ic('chevron', 's')}</button>
    <button class="mi" data-act="modal" data-kind="pw">${ic('key')}<span><b>Parola</b></span>${ic('chevron', 's')}</button>
    <button class="mi" data-act="flush" ${S.queueCount ? '' : 'disabled'}>${ic('upload')}<span><b>Yükleme kuyruğu</b><small>${S.queueCount ? `${S.queueCount} bekliyor` : 'Boş'}</small></span>${S.queueCount ? ic('chevron', 's') : ''}</button>
    <div class="mi">${ic('cloudoff')}<span><b>Çevrimdışı dene</b></span><label class="switch"><input type="checkbox" id="sw-off" data-change="forceOffline" ${S.forceOffline ? 'checked' : ''} aria-label="Çevrimdışı test modu"><span></span></label></div>
    <div class="mi">${ic(secure ? 'lock' : 'alert')}<span><b>Bağlantı</b><small>${esc(location.host)}</small></span><span class="pill ${secure ? 'ok' : 'bad'}">${secure ? 'Güvenli' : 'HTTP'}</span></div>
    <button class="mi bad" data-act="logout">${ic('logout')}<span><b>Çıkış yap</b></span></button>
  </section>`;
}

/* ---------- yönetim paneli ---------- */
function viewAdmin() {
  if (!canDispatch()) return viewProfile();
  const activeN = S.allProjects.filter(p => !p.archived).length;
  const tabs = [['customers', 'Müşteriler', 'building', activeN], ['team', isMgr() ? 'Ekip' : 'Ekibim', 'users', S.users.length]];
  if (isMgr()) tabs.push(['skills', 'Yetenekler', 'wrench', S.skills.length], ['system', 'Sistem', 'gear', null]);
  if (!tabs.some(t => t[0] === S.admTab)) S.admTab = 'customers';
  return `<div class="tabs" role="tablist" aria-label="Yönetim">${tabs.map(([k, l, i, n]) => `<button role="tab" data-act="admTab" data-tab="${k}" aria-selected="${S.admTab === k}">${ic(i, 's')}${l}${n != null ? `<span class="n">${n}</span>` : ''}</button>`).join('')}</div>`
    + { customers: admCustomers, team: admTeam, skills: admSkills, system: admSystem }[S.admTab]();
}
function admCustomers() {
  const q = S.admQ.trim().toLocaleLowerCase('tr');
  const list = S.allProjects.filter(p => (S.admArch ? p.archived : !p.archived)
    && (!q || [p.client, p.name, p.address, p.phone, p.contact].some(v => (v || '').toLocaleLowerCase('tr').includes(q))));
  const archN = S.allProjects.filter(p => p.archived).length;
  return `<div class="bar"><div class="search">${ic('search', 's')}<label class="vh" for="adm-q">Müşteri ara</label><input id="adm-q" class="input" type="search" placeholder="Ara" value="${esc(S.admQ)}" data-input="admQ" autocomplete="off"></div>
    ${archN ? `<button class="chip" data-act="admArch" aria-pressed="${!!S.admArch}">${ic('archive', 'xs')}Arşiv <b>${archN}</b></button>` : ''}
    ${canCust() ? `<button class="btn primary icon" data-act="admNew" data-kind="customer" aria-label="Müşteri ekle" title="Müşteri ekle">${ic('plus')}</button>` : ''}</div>
    ${list.length ? `<div class="grid-cards">${list.map(custCard).join('')}</div>` : empty('building', q ? 'Eşleşen müşteri yok' : 'Müşteri yok')}`;
}
function custCard(p) {
  const ts = S.tasks.filter(t => t.project_id === p.id);
  const open = ts.filter(t => t.status !== 'done').length, late = ts.filter(isLate).length;
  return `<div class="ucard" data-act="admEdit" data-kind="customer" data-id="${p.id}" role="button" tabindex="0" aria-label="${esc(p.client || p.name)}">
    <span class="cface" style="--c:${hue(p.id)}">${esc(initials(p.client || p.name))}</span>
    <span style="min-width:0"><b>${esc(p.client || p.name)}</b><span class="sub">${ic('pin', 'xs')}<span>${esc(p.address || p.name)}</span></span>
      <span class="kpis"><span title="Açık iş">${ic('board', 'xs')}${open}</span>${late ? `<span class="late" title="Geciken iş">${ic('clock', 'xs')}${late}</span>` : ''}<span title="Tamamlanan iş">${ic('check', 'xs')}${ts.length - open}</span></span></span>
    ${p.phone ? `<a class="ib" href="tel:${esc(p.phone.replace(/[^\d+]/g, ''))}" aria-label="Ara: ${esc(p.phone)}" title="${esc(p.phone)}">${ic('phone', 's')}</a>` : `<span class="muted">${ic('chevron', 's')}</span>`}
  </div>`;
}
function userCard(u) {
  const mineOpen = S.tasks.filter(t => t.assignee_id === u.id && t.status !== 'done');
  const late = mineOpen.filter(isLate).length;
  const edit = canManageUser(u);
  return `<div class="ucard ${u.active === false ? 'off' : ''}" ${edit ? `data-act="admEdit" data-kind="user" data-id="${u.id}" role="button" tabindex="0"` : ''} aria-label="${esc(u.name)}">
    <span class="avatar" style="width:46px;height:46px;font-size:15px">${esc(u.short)}</span>
    <span style="min-width:0"><b>${esc(u.name)}</b><span class="sub">${roleBadge(u.role)}${u.active === false ? '<span class="pill bad">Pasif</span>' : ''}</span>
      ${(u.skills || []).length ? `<span class="skills">${u.skills.map(s => skillChip(s)).join('')}</span>` : ''}</span>
    <span class="kpis" style="flex-direction:column;align-items:flex-end;gap:2px"><span title="Açık iş">${ic('board', 'xs')}${mineOpen.length}</span>${late ? `<span class="late" title="Geciken iş">${ic('clock', 'xs')}${late}</span>` : ''}
      ${u.phone && !edit ? `<a class="ib" href="tel:${esc(u.phone.replace(/[^\d+]/g, ''))}" aria-label="Ara: ${esc(u.name)}">${ic('phone', 's')}</a>` : ''}</span>
  </div>`;
}
function admTeam() {
  const us = S.users;
  const top = us.filter(u => u.role === 'owner' || u.role === 'manager');
  const leads = us.filter(u => u.role === 'lead');
  const free = us.filter(u => u.role === 'field' && !leads.some(l => l.id === u.lead_id));
  const count = r => us.filter(u => u.role === r).length;
  const grid = list => `<div class="grid-cards">${list.map(userCard).join('')}</div>`;
  return `<div class="bar"><div class="kpis grow">${['owner', 'manager', 'lead', 'field'].filter(count).map(r => `<span title="${ROLE[r]}">${ic(ROLE_IC[r], 's')}${count(r)}</span>`).join('')}</div>
    ${S.me.perms.roles.length ? `<button class="btn primary icon" data-act="admNew" data-kind="user" aria-label="Kişi ekle" title="Kişi ekle">${ic('plus')}</button>` : ''}</div>
  <div class="team">
    ${top.length && isMgr() ? `<h4>${ic('shield', 's')}Yönetim</h4>${grid(top)}` : ''}
    ${leads.map(l => `<h4>${ic('flag', 's')}${esc(l.name)}</h4><div class="members">${grid([l, ...us.filter(u => u.lead_id === l.id)])}</div>`).join('')}
    ${free.length ? `<h4>${ic('wrench', 's')}Ekipsiz</h4>${grid(free)}` : ''}
  </div>`;
}
function admSkills() {
  return `<div class="bar"><span class="grow"></span><button class="btn primary icon" data-act="admNew" data-kind="skill" aria-label="Yetenek ekle" title="Yetenek ekle">${ic('plus')}</button></div>
  ${S.skills.length ? `<div class="grid-cards">${S.skills.map(k => {
    const n = S.users.filter(u => (u.skills || []).includes(k.id)).length;
    const tn = S.tasks.filter(t => t.skill_id === k.id && t.status !== 'done').length;
    return `<div class="ucard" data-act="admEdit" data-kind="skill" data-id="${k.id}" role="button" tabindex="0" aria-label="${esc(k.name)}">${skillChip(k.id, 'lg')}
      <span style="min-width:0"><b>${esc(k.name)}</b><span class="kpis"><span title="Kişi">${ic('users', 'xs')}${n}</span><span title="Açık iş">${ic('board', 'xs')}${tn}</span></span></span><span class="muted">${ic('chevron', 's')}</span></div>`; }).join('')}</div>`
    : empty('wrench', 'Yetenek yok')}`;
}
function admSystem() {
  return `<section class="panel menu">
    <div class="mi">${ic('sparkle')}<span><b>Otomatik onaya taşı</b><small>Önce ve sonra fotoğrafı, kanıtlar tamamsa</small></span><label class="switch"><input type="checkbox" id="sw-auto" data-change="autoRule" ${S.settings.auto_rule ? 'checked' : ''} aria-label="Otomatik onaya taşı"><span></span></label></div>
    ${can('owner') ? `<a class="mi" href="/api/backup">${ic('download')}<span><b>Yedek indir</b><small>Veritabanı ve fotoğraflar</small></span>${ic('chevron', 's')}</a>` : ''}
  </section>
  ${can('owner') ? viewIntegrations() : ''}`;
}

/* ---------- formlar (alttan açılan pencere) ---------- */
function renderModal() {
  const box = $('#modal'), m = S.modal;
  if (!m) { box.hidden = true; box.innerHTML = ''; return; }
  const body = { customer: modalCustomer, user: modalUser, skill: modalSkill, pw: modalPw }[m.kind](m);
  box.hidden = false;
  box.innerHTML = `<div class="modal-wrap" data-act="modalBg"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="m-title">${body}</div></div>`;
  if (!m.id) box.querySelector('input:not([type=hidden]):not([type=checkbox]):not([type=radio])')?.focus({ preventScroll: true });
}
const mHead = (icon, title) => `<div class="sheet-top"><h3 id="m-title">${icon}<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${title}</span></h3><button type="button" class="ib" data-act="modalClose" aria-label="Kapat">${ic('x')}</button></div>`;
const fld = (id, label, icon, attrs = '', val = '') => `<label class="field"><span>${ic(icon, 'xs')}${label}</span><input id="${id}" class="input" value="${esc(val)}" ${attrs}></label>`;
function modalCustomer(m) {
  const p = m.id ? proj(m.id) : {};
  const ts = m.id ? S.tasks.filter(t => t.project_id === p.id) : [];
  return mHead(`<span class="cface" style="--c:${hue(p.id || 'yeni')};width:34px;height:34px;font-size:13px;border-radius:10px">${esc(initials(p.client || p.name || '+'))}</span>`, m.id ? esc(p.client || p.name) : 'Yeni müşteri')
    + `<form data-form="customer" data-id="${p.id || ''}">
      ${m.id && (p.phone || p.lat != null || p.email) ? `<div class="row">${p.phone ? `<a class="btn" href="tel:${esc(p.phone.replace(/[^\d+]/g, ''))}">${ic('phone', 's')}Ara</a>` : ''}${p.email ? `<a class="btn" href="mailto:${esc(p.email)}">${ic('mail', 's')}E-posta</a>` : ''}${p.lat != null ? `<a class="btn" href="${dirUrl(p)}" target="_blank" rel="noopener">${ic('nav', 's')}Yol tarifi</a>` : ''}</div>` : ''}
      <div class="fgrid">
        ${fld('mc-client', 'Müşteri', 'building', 'required maxlength="120" autocomplete="organization"', p.client || p.name || '')}
        ${fld('mc-name', 'Saha / yer adı', 'pin', 'maxlength="120" placeholder="İsteğe bağlı"', p.name && p.name !== p.client ? p.name : '')}
        ${fld('mc-phone', 'Telefon', 'phone', 'type="tel" maxlength="40" autocomplete="tel"', p.phone || '')}
        ${fld('mc-email', 'E-posta', 'mail', 'type="email" maxlength="120" autocomplete="email"', p.email || '')}
        ${fld('mc-contact', 'Yetkili', 'user', 'maxlength="120"', p.contact || '')}
        <div class="field full"><span>${ic('pin', 'xs')}Adres</span><div class="row" style="flex-wrap:nowrap"><input id="mc-address" class="input" maxlength="200" value="${esc(p.address || '')}">${window.isSecureContext ? `<button type="button" class="btn icon" data-act="custHere" aria-label="Bulunduğum yer" title="Bulunduğum yer">${ic('target', 's')}</button>` : ''}</div></div>
        <input type="hidden" id="mc-lat" value="${p.lat ?? ''}"><input type="hidden" id="mc-lng" value="${p.lng ?? ''}">
        <label class="field full"><span>${ic('chat', 'xs')}Not</span><textarea id="mc-notes" class="input" maxlength="1000" placeholder="Kapı kodu, çalışma saatleri…">${esc(p.notes || '')}</textarea></label>
      </div>
      ${m.id ? `<div class="kpis"><span>${ic('board', 'xs')}${ts.filter(t => t.status !== 'done').length} açık</span><span>${ic('check', 'xs')}${ts.filter(t => t.status === 'done').length} tamamlandı</span>${p.lat != null ? `<span>${ic('pin', 'xs')}Konum var</span>` : ''}</div>` : ''}
      <div class="actions">
        ${m.id && canCust() ? `<button type="button" class="btn" data-act="custArchive" data-id="${p.id}">${ic('archive', 's')}${p.archived ? 'Arşivden çıkar' : 'Arşivle'}</button>` : ''}
        ${m.id && isMgr() && !ts.length ? `<button type="button" class="btn bad icon" data-act="custDelete" data-id="${p.id}" aria-label="Sil" title="Sil">${ic('trash', 's')}</button>` : ''}
        ${canCust() ? `<button class="btn primary" type="submit">${ic('check', 's')}Kaydet</button>` : ''}
      </div></form>`;
}
function modalUser(m) {
  const roles = S.me.perms.roles;
  const u = m.id ? user(m.id) : { role: roles.includes('field') ? 'field' : roles[0], skills: [], active: true };
  const roleOpts = [...new Set([...(m.id ? [u.role] : []), ...roles])];
  const leads = S.users.filter(x => x.role === 'lead' && x.id !== u.id);
  return mHead(`<span class="avatar">${esc(u.short || '+')}</span>`, m.id ? esc(u.name) : 'Yeni kişi')
    + `<form data-form="user" data-id="${u.id || ''}">
      <div class="fgrid">
        ${fld('mu-name', 'Ad soyad', 'user', 'required maxlength="80" autocomplete="name"', u.name || '')}
        ${fld('mu-phone', 'Telefon', 'phone', 'type="tel" maxlength="40"', u.phone || '')}
        ${m.id ? '' : fld('mu-user', 'Kullanıcı adı', 'key', 'required autocapitalize="none" pattern="[a-z0-9._\\-]{3,32}" placeholder="kucuk.harf"')}
        ${fld('mu-pass', m.id ? 'Yeni parola' : 'Parola', 'lock', `type="password" minlength="8" autocomplete="new-password" ${m.id ? 'placeholder="Değiştirmeyeceksen boş bırak"' : 'required'}`)}
      </div>
      <div class="field"><span>${ic('shield', 'xs')}Rol</span><div class="skill-pick" role="radiogroup">${roleOpts.map(r => `<label><input type="radio" name="mu-role" value="${r}" data-change="muRole" ${u.role === r ? 'checked' : ''}><span style="--c:var(--accent)">${roleBadge(r)}</span></label>`).join('')}</div></div>
      <label class="field" id="mu-lead-f" ${u.role === 'field' ? '' : 'hidden'}><span>${ic('flag', 'xs')}Ekip lideri</span><select id="mu-lead" class="select"><option value="">Ekipsiz</option>${leads.map(l => `<option value="${l.id}"${u.lead_id === l.id ? ' selected' : ''}>${esc(l.name)}</option>`).join('')}</select></label>
      <div class="field"><span>${ic('wrench', 'xs')}Yetenekler</span><div class="skill-pick">${S.skills.map(k => `<label><input type="checkbox" name="mu-skill" value="${k.id}" ${(u.skills || []).includes(k.id) ? 'checked' : ''}><span style="--c:${k.color}">${skillChip(k.id)}${esc(k.name)}</span></label>`).join('')}</div></div>
      ${m.id ? `<div class="menu">
        <div class="mi">${ic('user')}<span><b>Hesap açık</b></span><label class="switch"><input type="checkbox" id="mu-active" ${u.active !== false ? 'checked' : ''} aria-label="Hesap açık"><span></span></label></div>
        <button type="button" class="mi" data-act="muRevoke" data-id="${u.id}">${ic('logout')}<span><b>Tüm oturumları kapat</b>${u.last_seen ? `<small>Son giriş ${fmtTime(u.last_seen)}</small>` : ''}</span></button></div>` : ''}
      <div class="actions"><button class="btn primary" type="submit">${ic('check', 's')}${m.id ? 'Kaydet' : 'Kişiyi ekle'}</button></div>
    </form>`;
}
function modalSkill(m) {
  const k = m.id ? skill(m.id) : { icon: 'wrench', color: SKILL_COLORS[S.skills.length % SKILL_COLORS.length] };
  return mHead(m.id ? skillChip(k.id) : ic('wrench'), m.id ? esc(k.name) : 'Yeni yetenek')
    + `<form data-form="skill" data-id="${k.id || ''}">
      ${fld('ms-name', 'Ad', 'pen', 'required maxlength="40"', k.name || '')}
      <div class="field"><span>Simge</span><div class="icon-pick" role="radiogroup" aria-label="Simge">${SKILL_ICONS.map(i => `<label><input type="radio" name="ms-icon" value="${i}" ${k.icon === i ? 'checked' : ''} aria-label="${i}"><span>${ic(i)}</span></label>`).join('')}</div></div>
      <div class="field"><span>Renk</span><div class="color-pick" role="radiogroup" aria-label="Renk">${SKILL_COLORS.map(c => `<label><input type="radio" name="ms-color" value="${c}" ${k.color === c ? 'checked' : ''} aria-label="${c}"><span style="--c:${c}"></span></label>`).join('')}</div></div>
      <div class="actions">${m.id ? `<button type="button" class="btn bad icon" data-act="skillDelete" data-id="${k.id}" aria-label="Sil" title="Sil">${ic('trash', 's')}</button>` : ''}<button class="btn primary" type="submit">${ic('check', 's')}Kaydet</button></div>
    </form>`;
}
function modalPw() {
  return mHead(ic('key'), 'Parola') + `<form data-form="password">
    ${fld('pw-old', 'Mevcut parola', 'lock', 'type="password" autocomplete="current-password" required')}
    ${fld('pw-new', 'Yeni parola', 'key', 'type="password" autocomplete="new-password" minlength="8" required placeholder="En az 8 karakter"')}
    <div class="actions"><button class="btn primary" type="submit">${ic('check', 's')}Değiştir</button></div></form>`;
}

/* ---------- entegrasyonlar: dışarıdan erişim, DNS, AI ---------- */
const TUN_STATUS = { stopped: ['Kapalı', ''], starting: ['Başlıyor…', 'warn'], running: ['Açık', 'ok'], error: ['Hata', 'bad'] };
let integTimer = null;
async function loadIntegrations() {
  try { S.integ = await api('GET', '/api/admin/integrations'); } catch (e) { fail(e); return; }
  const here = () => S.view === 'admin' && S.admTab === 'system';
  if (here()) renderIntegrations();
  clearTimeout(integTimer);
  if (here() && S.integ.tunnel.run_status === 'starting') integTimer = setTimeout(loadIntegrations, 1500);
}
function renderIntegrations() { const box = $('#integ'); if (box) { const kept = keepInputs(); box.outerHTML = viewIntegrations(); restoreInputs(kept); } }
function viewIntegrations() {
  const I = S.integ;
  if (!I) return '<section class="panel" id="integ"><div class="muted">Yükleniyor…</div></section>';
  const T = I.tunnel, [stName2, stCls] = TUN_STATUS[T.run_status] || TUN_STATUS.stopped;
  const mode = S.integMode || T.mode;
  const demoUsers = I.demo_password_users.map(u => S.users.find(x => x.username === u)).filter(Boolean);
  const radio = (v, l, d) => `<label class="opt"><input type="radio" name="tun-mode" value="${v}" data-change="tunMode" ${mode === v ? 'checked' : ''}><span><b>${l}</b><small>${d}</small></span></label>`;
  return `<section class="panel integ" id="integ">
    <div class="sec-h"><h4>${ic('plug', 's')}Bağlantılar</h4></div>
    <div class="integ-grid">
    <div class="stack" style="gap:10px">
      <div class="sec-h" style="margin:0"><h4>${ic('nav', 's')}Dışarıdan erişim</h4><span class="pill ${stCls}">${stName2}</span></div>
      ${T.run_url ? `<div class="url-box"><a href="${esc(T.run_url)}" target="_blank" rel="noopener" class="mono">${esc(T.run_url)}</a><button class="btn" data-act="copyUrl">Kopyala</button></div>` : ''}
      ${T.run_error ? `<div class="note" style="border-color:var(--danger)"><b>Sorun:</b> ${esc(T.run_error)}</div>` : ''}
      ${demoUsers.length ? `<div class="note" style="border-color:var(--danger)"><b>İnternete açmadan önce:</b> şu hesapların parolası hâlâ demo1234. Yeni parola ver:
        ${demoUsers.map(u => `<form class="row" data-form="resetPw" data-uid="${u.id}" style="margin-top:6px"><span style="min-width:70px">@${esc(u.username)}</span><input id="rp-${u.id}" class="input" type="password" minlength="8" placeholder="En az 8 karakter" data-keep autocomplete="new-password" style="flex:1 1 140px" required><button class="btn" type="submit">Değiştir</button></form>`).join('')}</div>` : ''}
      <div class="opts">
        ${radio('off', 'Kapalı', 'Yalnızca bu telefon ve aynı Wi-Fi.')}
        ${radio('quick', 'Hızlı tünel', 'Ücretsiz, hesap gerekmez. Adres her başlatmada değişir.')}
        ${radio('named', 'Kendi alan adım', 'Ücretsiz Cloudflare hesabı + Cloudflare\'deki alan adın. Adres sabit.')}
      </div>
      ${mode === 'named' ? `<label class="field"><span>Alan adı</span><input id="tn-host" class="input" placeholder="is.alanadin.com" value="${esc(T.hostname)}" data-keep autocapitalize="none"></label>
        <label class="field"><span>Tünel token'ı ${T.token_set ? `<span class="muted">(kayıtlı ${esc(T.token_hint)})</span>` : ''}</span><input id="tn-token" class="input" type="password" data-keep placeholder="${T.token_set ? 'Değiştirmek için yeni token yapıştır' : 'Cloudflare Zero Trust › Tunnels › token'}" autocomplete="off"></label>
        <details class="howto"><summary>Token ve alan adı nasıl alınır?</summary><ol>
          <li>Ücretsiz Cloudflare hesabı aç; alan adını Cloudflare'e ekle (alan adı ücretli olabilir, Cloudflare hesabı ücretsiz).</li>
          <li>Zero Trust › Networks › Tunnels › Create a tunnel › Cloudflared.</li>
          <li>Gösterilen komuttaki <code>--token</code> sonrasındaki uzun değeri kopyala, buraya yapıştır.</li>
          <li>Public Hostname: alan adını (ör. is.alanadin.com) <code>http://127.0.0.1:${I.local_port}</code> adresine yönlendir.</li></ol></details>` : ''}
      <div class="set-row"><div><b>Açılışta başlat</b><p>FotoTakip açılınca tünel de açılır.</p></div><label class="switch"><input type="checkbox" id="tn-auto" ${T.autostart ? 'checked' : ''} aria-label="Açılışta başlat"><span></span></label></div>
      <div class="row"><button class="btn" data-act="tunSave">Kaydet</button>
        ${T.run_status === 'running' || T.run_status === 'starting' ? '<button class="btn bad" data-act="tunStop">Tüneli kapat</button>' : '<button class="btn primary" data-act="tunStart">Tüneli başlat</button>'}</div>
      ${tunnelBlockers(mode, demoUsers, T).length && T.run_status !== 'running' ? `<ul class="blockers" id="tun-blockers">${tunnelBlockers(mode, demoUsers, T).map(r => `<li>${r}</li>`).join('')}</ul>` : ''}
      ${!T.run_cloudflared ? '<p class="muted" style="font-size:12.5px;margin:0">cloudflared kurulu değil. Termux\'ta: <code>pkg install cloudflared</code></p>' : ''}
      ${T.run_log.length ? `<details class="howto"><summary>Son kayıtlar</summary><pre class="log-pre">${esc(T.run_log.join('\n'))}</pre></details>` : ''}
      <p class="muted" style="font-size:12.5px;margin:0">Bağlantı telefondan dışarıya açılır; modemde port açmak gerekmez, mobil veride de çalışır. Trafik Cloudflare üzerinden şifreli geçer.</p>
    </div>
    <div class="stack" style="gap:10px">
      <div class="sec-h" style="margin:0"><h4>${ic('wifi', 's')}DNS</h4><span class="muted num">${esc(I.dns.servers.join(', ') || 'sistem')}</span></div>
      ${I.dns.available ? `<p class="muted" style="font-size:12.5px;margin:0">Termux içindeki programların (cloudflared, adres bulma) kullandığı DNS. Tünel "lookup" hatası verirse birini seç.</p>
        <div class="chips">${Object.entries(I.dns.presets).map(([k, v]) => `<button class="chip" data-act="dnsSet" data-k="${k}" aria-pressed="${I.dns.preset === k}">${esc(v.name)}</button>`).join('')}</div>`
        : '<p class="muted" style="font-size:12.5px;margin:0">DNS ayarı yalnızca Termux\'ta çalışırken değiştirilebilir.</p>'}
      <div class="sec-h" style="margin:14px 0 0"><h4>${ic('sparkle', 's')}AI fotoğraf incelemesi</h4><span class="pill ${I.ai.enabled && I.ai.key_set ? 'ok' : ''}">${I.ai.enabled ? (I.ai.key_set ? 'Açık' : 'Anahtar yok') : 'Kapalı'}</span></div>
      <p class="muted" style="font-size:12.5px;margin:0">Fotoğraf için gözlem notu üretir, karar vermez. Fotoğraf konumsuz olarak OpenAI'ye gönderilir; kullanım OpenAI hesabından ücretlendirilir.</p>
      <div class="set-row"><div><b>Açık</b></div><label class="switch"><input type="checkbox" id="ai-on" ${I.ai.enabled ? 'checked' : ''} aria-label="AI inceleme"><span></span></label></div>
      <label class="field"><span>Model</span><input id="ai-model" class="input" value="${esc(I.ai.model)}" autocapitalize="none"></label>
      <label class="field"><span>OpenAI API anahtarı ${I.ai.key_set ? `<span class="muted">(kayıtlı ${esc(I.ai.key_hint)})</span>` : ''}</span><input id="ai-key" class="input" type="password" data-keep placeholder="${I.ai.key_set ? 'Değiştirmek için yeni anahtar' : 'sk-…'}" autocomplete="off"></label>
      <div class="row"><button class="btn" data-act="aiSave">Kaydet</button>${I.ai.key_set ? '<button class="btn bad" data-act="aiClear">Anahtarı sil</button>' : ''}</div>
    </div>
    </div>
  </section>`;
}

/* Tünelin neden başlamayacağını önceden söyler; düğme hiçbir zaman sessizce kapalı kalmaz. */
function tunnelBlockers(mode, demoUsers, T) {
  const r = [];
  if (mode === 'off') r.push('Önce yukarıdan <b>Hızlı tünel</b> ya da <b>Kendi alan adım</b> seç.');
  if (mode === 'named' && !T.token_set && !$('#tn-token')?.value) r.push('Kendi alan adın için Cloudflare <b>tünel token\'ı</b> gerekli.');
  if (demoUsers.length) r.push(`Şu hesapların parolası hâlâ demo1234: <b>${demoUsers.map(u => '@' + esc(u.username)).join(', ')}</b>. Yukarıdan yeni parola ver.`);
  if (!T.run_cloudflared) r.push('<b>cloudflared</b> bulunamadı. Termux\'ta <code>pkg install cloudflared</code> çalıştır, sonra FotoTakip\'i yeniden başlat.');
  return r;
}

/* ---------- AI gözlem paneli ---------- */
const AI_LEVEL = { critical: ['Kritik', 'bad'], attention: ['Dikkat', 'warn'], info: ['Bilgi', ''], uncertain: ['Belirsiz', ''] };
const AI_QUALITY = { good: 'iyi', limited: 'sınırlı', poor: 'zayıf' };
function aiBlock(ph) {
  const r = ph.ai;
  if (S.aiBusy === ph.id) return `<section class="ai-box row muted">${ic('sparkle', 's')}AI inceliyor…</section>`;
  if (!r) {
    if (ph.mime === 'image/svg+xml') return '';
    return `<section class="ai-box bar"><span class="grow row muted">${ic('sparkle', 's')}AI gözlemi yok</span><button class="btn" data-act="aiRun">${ic('sparkle', 's')}İncele</button></section>`;
  }
  return `<section class="ai-box"><div class="sec-h"><h4>${ic('sparkle', 's')}AI gözlemi</h4><span class="pill">Kalite: ${AI_QUALITY[r.photo_quality] || r.photo_quality}</span>${isMgr() ? `<button class="ib" data-act="aiRun" data-force="1" aria-label="Yeniden incele" title="Yeniden incele">${ic('swap', 's')}</button>` : ''}</div>
    <p style="margin:0 0 8px">${esc(r.summary)}</p>
    ${r.observations.length ? `<ul class="ai-obs">${r.observations.map(o => `<li><span class="pill ${AI_LEVEL[o.level][1]}">${AI_LEVEL[o.level][0]}</span><span><b>${esc(o.title)}</b>${o.detail ? ` <span class="muted">${esc(o.detail)}</span>` : ''}</span></li>`).join('')}</ul>` : ''}
    ${r.limitations?.length ? `<div class="muted" style="font-size:13px;margin-top:6px">Sınırlar: ${r.limitations.map(esc).join('; ')}</div>` : ''}
    <div class="muted" style="font-size:12.5px;margin-top:6px">Karar değildir; son söz inceleyen kişide. ${esc(r.model || '')}, ${fmtTime(r.at)}</div></section>`;
}

/* ---------- iş ayrıntısı ---------- */
function suggestions(t) {
  if (!canDispatch() || t.status === 'done') return '';
  const load = id => S.tasks.filter(x => x.assignee_id === id && x.status !== 'done').length;
  let cands = assignable().filter(u => u.role === 'field' || u.role === 'lead');
  if (t.skill_id) cands = cands.filter(u => (u.skills || []).includes(t.skill_id));
  cands.sort((a, b) => load(a.id) - load(b.id) || a.name.localeCompare(b.name, 'tr')).splice(6);
  if (!cands.length) return t.skill_id ? `<div class="note">${ic('alert', 's')}<span>Bu yetenekte kimse yok.</span></div>` : '';
  return `<div class="field"><span>${ic('sparkle', 'xs')}Uygun kişiler${t.skill_id ? ` ${skillChip(t.skill_id)}` : ''}</span><div class="suggest">${cands.map(u =>
    `<button class="sug" data-act="assignTo" data-uid="${u.id}" aria-pressed="${t.assignee_id === u.id}" aria-label="${esc(u.name)}, ${load(u.id)} açık iş">${av(u.id)}<span>${esc(u.name.split(' ')[0])}</span><small>${ic('board', 'xs')} ${load(u.id)}</small></button>`).join('')}</div></div>`;
}
function renderSheet() {
  const box = $('#sheet');
  const t = S.open && task(S.open);
  if (!t || !S.me) { box.hidden = true; box.innerHTML = ''; document.body.style.overflow = ''; return; }
  if (!S.active || !t.photos.some(p => p.pid === S.active)) S.active = t.photos[0]?.pid ?? null;
  const ph = S.photos[S.active];
  const link = t.photos.find(p => p.pid === S.active);
  const before = firstOf(t, 'before'), after = lastOf(t, 'after');
  const p = proj(t.project_id);
  const pool = isPool(t);
  const canEdit = mine(t);
  const disp = canDispatch();
  const anns = ph ? ph.annotations : [];
  const prevScroll = box.querySelector('.sheet')?.scrollTop ?? 0;
  const people = assignable();
  if (t.assignee_id && !people.some(u => u.id === t.assignee_id) && user(t.assignee_id)) people.push(user(t.assignee_id));
  box.hidden = false;
  document.body.style.overflow = 'hidden';
  box.innerHTML = `<div class="sheet-wrap" data-act="closeBg"><div class="sheet" role="dialog" aria-modal="true" aria-label="${esc(t.no_label)} ${esc(t.title)}">
    <div class="sheet-top"><span class="no">${esc(t.no_label)}</span><label class="vh" for="t-title">Başlık</label>
      <input id="t-title" class="title-in" value="${esc(t.untitled ? '' : t.title)}" placeholder="${t.untitled ? 'Başlık yaz' : ''}" data-change="title" ${canEdit ? '' : 'disabled'}>
      <button class="ib" data-act="close" aria-label="Kapat">${ic('x')}</button></div>
    <div class="sheet-body">
      ${pool && disp ? `<div class="note bar"><span class="grow row">${ic('users', 's')}Havuzda, kimseye atanmamış</span><button class="btn primary" data-act="claim" data-id="${t.id}">Üstlen</button></div>` : ''}
      ${t.rejected_reason ? `<div class="note bad">${ic('swap', 's')}<span><b>Geri gönderildi:</b> ${esc(t.rejected_reason)}</span></div>` : ''}
      <div class="where">${ic('building', 's')}<b style="color:var(--ink)">${esc(p?.client || p?.name || '')}</b>${p?.address ? `<span>${esc(p.address)}</span>` : ''}
        ${p?.phone ? `<a href="tel:${esc(p.phone.replace(/[^\d+]/g, ''))}">${ic('phone', 'xs')}Ara</a>` : ''}${p?.lat != null ? `<a href="${dirUrl(p)}" target="_blank" rel="noopener">${ic('nav', 'xs')}Yol tarifi</a>` : ''}</div>
      ${p?.notes ? `<div class="note">${ic('chat', 's')}<span>${esc(p.notes)}</span></div>` : ''}
      <div class="facts">
        <label class="field"><span>${ST_ICON[t.status]}Durum</span><select id="t-status" class="select" data-change="status" ${canEdit ? '' : 'disabled'}>${STATUSES.map(s => `<option value="${s.id}"${t.status === s.id ? ' selected' : ''}${!disp && s.id === 'done' ? ' disabled' : ''}>${s.name}</option>`).join('')}</select></label>
        <label class="field"><span>${ic('user', 'xs')}Atanan</span><select id="t-assignee" class="select" data-change="assignee" ${disp ? '' : 'disabled'}><option value="">Havuz</option>${people.map(u => `<option value="${u.id}"${t.assignee_id === u.id ? ' selected' : ''}>${esc(u.name)}</option>`).join('')}</select></label>
        <label class="field"><span>${ic('wrench', 'xs')}Yetenek</span><select id="t-skill" class="select" data-change="skill" ${disp ? '' : 'disabled'}><option value="">Belirtilmedi</option>${S.skills.map(k => `<option value="${k.id}"${t.skill_id === k.id ? ' selected' : ''}>${esc(k.name)}</option>`).join('')}</select></label>
        <label class="field"><span>${ic('calendar', 'xs')}Son tarih</span><input id="t-due" type="date" class="input" value="${t.due}" data-change="due" ${canEdit ? '' : 'disabled'}></label>
        <label class="field"><span>${ic('alert', 'xs')}Öncelik</span><select id="t-prio" class="select" data-change="priority" ${canEdit ? '' : 'disabled'}><option value="normal"${t.priority === 'normal' ? ' selected' : ''}>Normal</option><option value="high"${t.priority === 'high' ? ' selected' : ''}>Acil</option></select></label>
      </div>
      ${suggestions(t)}

      <section class="viewer">
        ${ph ? `<div class="stage"><div class="shot ${S.annot ? 'annot' : ''}" data-act="shot">
          <img src="${full(ph.id)}" alt="${esc(TYPES[link.type])} fotoğrafı" draggable="false">
          ${anns.map((a, i) => `<span class="mk" style="left:${a.x}%;top:${a.y}%" title="${esc(a.text)}">${i + 1}</span>`).join('')}
          ${S.draftPin ? `<span class="mk new" style="left:${S.draftPin.x}%;top:${S.draftPin.y}%">${anns.length + 1}</span>` : ''}
        </div></div>
        <div class="vbar"><div class="info"><span class="glass tg ${link.type}">${ic(TYPE_IC[link.type], 'xs')}${TYPES[link.type]}</span><span>${ic('clock', 'xs')}${fmtTime(ph.taken_at)}</span>${ph.lat != null ? `<span title="${esc(fmtGps(ph))}">${ic('pin', 'xs')}${GPS_SRC[ph.gps_source]}${ph.gps_accuracy ? ` ±${Math.round(ph.gps_accuracy)} m` : ''}</span>` : ''}${photoDistChip(ph, p)}</div>
          ${canEdit ? `<div class="row"><button class="btn icon ${S.annot ? 'primary' : ''}" data-act="annot" aria-pressed="${S.annot}" aria-label="İşaretle" title="İşaretle">${ic(S.annot ? 'check' : 'pen', 's')}</button><button class="btn icon bad" data-act="unlink" aria-label="Fotoğrafı işten kaldır" title="Kaldır">${ic('trash', 's')}</button></div>` : ''}</div>
        ${ph.address ? `<div class="addr row">${ic('pin', 'xs')}${esc(ph.address)}</div>` : ''}
        ${S.annot && !S.draftPin ? `<div class="note">${ic('pen', 's')}<span>Fotoğrafta noktaya dokun</span></div>` : ''}
        ${S.draftPin ? `<div class="ann-form"><label class="vh" for="ann-text">İşaret notu</label><input id="ann-text" class="input" placeholder="İşaret ${anns.length + 1}" autocomplete="off" data-keep><button class="btn primary icon" data-act="annSave" aria-label="Kaydet">${ic('check', 's')}</button><button class="btn icon" data-act="annCancel" aria-label="Vazgeç">${ic('x', 's')}</button></div>` : ''}
        ${anns.length ? `<ol class="anns">${anns.map((a, i) => `<li><span class="n">${i + 1}</span><span>${esc(a.text)} <span class="muted">${esc(nameOf(a.by))}</span>${isMgr() || a.by === S.me.id ? ` <button class="linkbtn" data-act="annDel" data-aid="${a.id}" aria-label="İşareti sil">${ic('trash', 'xs')}</button>` : ''}</span></li>`).join('')}</ol>` : ''}` : empty('camera', 'Fotoğraf yok')}
        ${ph && S.settings.ai_enabled ? aiBlock(ph) : ''}
        <div class="thumbs">
          ${t.photos.map(x => `<button data-act="thumb" data-pid="${x.pid}" aria-current="${x.pid === S.active}" aria-label="${TYPES[x.type]} fotoğrafı"><img src="${thumb(x.pid)}" alt=""><span class="glass tg ${x.type}">${ic(TYPE_IC[x.type], 'xs')}</span></button>`).join('')}
          ${canEdit ? `<label class="add-photo" for="add-file" aria-label="Fotoğraf ekle">${ic('plus')}</label>` : ''}
        </div>
        ${canEdit ? `<input id="add-file" class="vh" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" multiple data-change="addFile">
        <div class="types" role="radiogroup" aria-label="Eklenecek fotoğraf türü">${Object.entries(TYPES).map(([k, l]) => `<label class="tg ${k}"><input type="radio" name="add-type" value="${k}" data-change="addType" ${S.addType === k ? 'checked' : ''}><span>${ic(TYPE_IC[k], 's')}${l}</span></label>`).join('')}</div>` : ''}
      </section>

      ${before && after ? `<section class="panel"><div class="sec-h"><h4>${ic('swap', 's')}Önce / sonra</h4><span class="muted num">${Math.max(0, daysBetween(dayStr(new Date(S.photos[before.pid]?.taken_at)), dayStr(new Date(S.photos[after.pid]?.taken_at))))} gün</span></div>
        <div class="compare" id="cmp-box"><img src="${full(before.pid)}" alt="Önce"><div class="after" id="cmp-after" style="clip-path:inset(0 0 0 50%)"><img src="${full(after.pid)}" alt="Sonra"></div>
          <span class="cbar" id="cmp-bar" style="left:50%"></span><span class="knob" id="cmp-knob" style="left:50%">${ic('swap', 's')}</span><span class="lbl glass" style="left:10px">Önce</span><span class="lbl glass tg after" style="right:10px">Sonra</span>
          <label class="vh" for="cmp">Karşılaştırma kaydırıcısı</label><input type="range" id="cmp" min="0" max="100" value="50" data-input="cmp"></div></section>` : ''}

      ${t.status === 'review' ? (disp ? `<section class="approve"><b class="row">${ic('shield', 's')}Onay bekliyor</b>
        <div class="bar"><button class="btn good" data-act="approve">${ic('check', 's')}Onayla</button><label class="vh" for="rej">Geri gönderme nedeni</label><input id="rej" class="input grow" style="flex:1 1 180px" placeholder="Geri gönderme nedeni" autocomplete="off" data-keep><button class="btn bad" data-act="reject">${ic('swap', 's')}Geri gönder</button></div></section>`
        : `<div class="note">${ic('clock', 's')}<span>Onay bekleniyor</span></div>`) : ''}

      <div class="two">
        <section class="panel"><div class="sec-h"><h4>${ic('checklist', 's')}Kontrol listesi</h4><span class="no">${t.checklist.filter(c => c.done).length}/${t.checklist.length}</span></div>
          ${t.checklist.length ? `<ul class="check">${t.checklist.map(c => `<li><input type="checkbox" id="ck-${c.id}" data-change="check" data-cid="${c.id}" ${c.done ? 'checked' : ''} ${canEdit ? '' : 'disabled'}><label for="ck-${c.id}">${esc(c.text)}${c.require_proof ? ` <span class="req" title="Fotoğraf kanıtı zorunlu">${ic('camera', 'xs')}</span>` : ''}</label>
            <span class="row" style="gap:4px">${c.proof ? `<img class="proof" src="${thumb(c.proof)}" alt="Kanıt fotoğrafı" data-act="thumb" data-pid="${c.proof}">` : `${c.done && c.require_proof ? `<span class="pill bad">${ic('camera', 'xs')}Yok</span>` : ''}${ph && canEdit ? `<button class="linkbtn" data-act="proof" data-cid="${c.id}" aria-label="Seçili fotoğrafı kanıt yap" title="Seçili fotoğrafı kanıt yap">${ic('image', 's')}</button>` : ''}`}${canEdit ? `<button class="linkbtn" data-act="ckDel" data-cid="${c.id}" aria-label="Maddeyi sil">${ic('x', 's')}</button>` : ''}</span></li>`).join('')}</ul>` : ''}
          ${canEdit ? `<div class="compose" style="margin-top:10px"><label class="vh" for="ck-new">Yeni madde</label><input id="ck-new" class="input" placeholder="Madde ekle" autocomplete="off" data-keep><button class="btn icon" data-act="ckAdd" aria-label="Ekle">${ic('plus', 's')}</button></div>
          <label class="row muted" style="font-size:13.5px;margin-top:8px;gap:8px;min-height:32px"><input type="checkbox" id="ck-req" style="width:20px;height:20px">${ic('camera', 'xs')}Fotoğraf kanıtı zorunlu</label>` : ''}
        </section>
        <section class="panel"><div class="sec-h"><h4>${ic('chat', 's')}Yorumlar</h4><span class="no">${t.comments.length}</span></div>
          <div class="comments">${t.comments.map(c => `<div class="cmt">${av(c.by)}<div><b>${esc(nameOf(c.by))}</b><time>${fmtTime(c.at)}</time><p>${esc(c.text)}</p></div></div>`).join('')}</div>
          ${canEdit ? `<div class="compose" style="margin-top:10px"><label class="vh" for="c-text">Yorum</label><input id="c-text" class="input" placeholder="Yorum yaz" autocomplete="off" data-keep><button class="btn primary icon" data-act="comment" aria-label="Gönder">${ic('arrow', 's')}</button></div>` : ''}
        </section>
      </div>

      <section class="panel sig"><div class="sec-h"><h4>${ic('sign', 's')}Müşteri imzası</h4>${t.signature ? `<span class="muted">${esc(t.signature.signer)}, ${fmtTime(t.signature.at)}</span>` : ''}</div>
        ${t.signature ? `<img src="/files/signature/${t.id}?v=${encodeURIComponent(t.signature.at)}" alt="Müşteri imzası">` : ''}
        ${canEdit ? `<canvas id="sig-pad" width="800" height="240" aria-label="İmza alanı"></canvas>
        <div class="bar"><label class="vh" for="sig-name">İmzalayan</label><input id="sig-name" class="input grow" style="flex:1 1 180px" placeholder="İmzalayanın adı" value="${esc(t.signature?.signer ?? '')}" data-keep>
          <button class="btn icon" data-act="sigClear" aria-label="Temizle" title="Temizle">${ic('x', 's')}</button><button class="btn primary" data-act="sigSave">${ic('check', 's')}Kaydet</button></div>` : ''}
      </section>

      <section class="panel"><div class="sec-h"><h4>${ic('clock', 's')}Geçmiş</h4>${isMgr() ? `<button class="btn bad icon" data-act="delTask" aria-label="İşi sil" title="İşi sil">${ic('trash', 's')}</button>` : ''}</div>
        <ul class="log">${[...t.activity].reverse().map(a => `<li><span class="num">${fmtTime(a.at)}</span><span><b style="font-weight:650">${esc(nameOf(a.by))}</b> ${esc(a.text)}</span></li>`).join('')}</ul></section>
    </div></div></div>`;
  const sh = box.querySelector('.sheet'); if (sh) sh.scrollTop = prevScroll;
  setupSignature();
}

function photoDistChip(ph, p) {
  if (!ph || ph.lat == null || !(ph.gps_source === 'exif' || ph.gps_source === 'device') || !p || p.lat == null) return '';
  const d = distM(ph.lat, ph.lng, p.lat, p.lng);
  return `<span class="gps-src ${d > 500 ? 'far' : ''}" title="Fotoğrafın çekildiği yer ile müşteri konumu arası">müşteriye ${fmtDist(d)}</span>`;
}

/* imza alanı */
let sigDirty = false;
function setupSignature() {
  const c = $('#sig-pad'); if (!c) return;
  sigDirty = false;
  const ctx = c.getContext('2d');
  ctx.lineWidth = 3.2; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = '#111';
  let drawing = false;
  const pos = e => { const r = c.getBoundingClientRect(); return [(e.clientX - r.left) * c.width / r.width, (e.clientY - r.top) * c.height / r.height]; };
  c.addEventListener('pointerdown', e => { drawing = true; c.setPointerCapture(e.pointerId); ctx.beginPath(); ctx.moveTo(...pos(e)); });
  c.addEventListener('pointermove', e => { if (!drawing) return; ctx.lineTo(...pos(e)); ctx.stroke(); sigDirty = true; });
  const end = () => { drawing = false; };
  c.addEventListener('pointerup', end); c.addEventListener('pointercancel', end);
}

/* ---------- çizim ---------- */
function keepInputs() {
  const vals = {};
  document.querySelectorAll('[data-keep][id]').forEach(el => { if (el.value) vals[el.id] = el.value; });
  const a = document.activeElement;
  const focus = a && a.id && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA') ? { id: a.id, s: a.selectionStart, e: a.selectionEnd } : null;
  return { vals, focus };
}
function restoreInputs({ vals, focus }) {
  for (const [id, v] of Object.entries(vals)) { const el = document.getElementById(id); if (el && el.hasAttribute('data-keep') && !el.value) el.value = v; }
  if (focus) { const el = document.getElementById(focus.id); if (el) { el.focus({ preventScroll: true }); try { el.setSelectionRange(focus.s, focus.e); } catch {} } }
}
function renderMain() {
  if (S.view === 'map') { renderMapView(); return; }
  if (M.el) destroyMap();
  const v = { board: viewBoard, gallery: viewGallery, camera: viewCamera, report: viewReport, profile: viewProfile, admin: viewAdmin }[S.view] || viewBoard;
  $('#main').innerHTML = `<div class="wrap">${v()}</div>`;
}
function measureChrome() {
  const r = document.documentElement.style, dock = $('.dock');
  r.setProperty('--hdr-h', ($('.top')?.offsetHeight || 57) + 'px');
  // tablet ve masaüstünde menü yanda: alttan yer kaplamaz
  r.setProperty('--dock-h', (dock && dock.offsetWidth < innerWidth / 2 ? 0 : (dock?.offsetHeight || 72)) + 'px');
}
function render() {
  if (!S.me) return;
  const kept = keepInputs();
  renderHeader(); renderDock(); measureChrome(); renderMain();
  if (!(S.open && sigDirty && document.getElementById('sig-pad'))) renderSheet();
  restoreInputs(kept);
}
function applyTheme() {
  const root = document.documentElement;
  if (!S.theme || S.theme === 'auto') delete root.dataset.style; else root.dataset.style = S.theme;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = getComputedStyle(root).getPropertyValue('--bg').trim() || '#F3F5F8';
}

/* ---------- eylemler ---------- */
async function moveTask(id, to) {
  const t = task(id); if (!t || t.status === to) return;
  if (!canDispatch() && to === 'done') { toast('<b>Tamamlandı</b> durumuna ekip lideri ya da yönetici taşır. İşi <b>Onay</b>’a taşı.'); return; }
  const prev = t.status; t.status = to; render();
  const ok = await run(() => api('PATCH', `/api/tasks/${id}`, { status: to, version: t.version }), `${esc(t.no_label)} → <b>${stName(to)}</b>`);
  if (ok === null && task(id)?.status === to) { task(id).status = prev; render(); }
}
function step(id, dir) {
  const t = task(id); const i = STATUSES.findIndex(s => s.id === t.status) + dir;
  if (i >= 0 && i < STATUSES.length) moveTask(id, STATUSES[i].id);
}
const patchTask = (body, msg) => { const t = task(S.open); return run(() => api('PATCH', `/api/tasks/${t.id}`, { ...body, version: t.version }), msg); };

async function submitPhotos(files, params, { openAfter = true } = {}) {
  if (offline()) { await enqueue(files, params); toast(`Çevrimdışı: <b>${files.length} fotoğraf</b> kuyruğa alındı`); return null; }
  try {
    const res = await uploadGroup(files, params);
    const last = res[res.length - 1];
    const dup = res.filter(r => r.duplicate).length;
    toast(params.task_id ? `${res.length - dup} fotoğraf <b>${esc(last.no_label)}</b>’e eklendi${dup ? ` · ${dup} tanesi zaten ekliydi` : ''}` : `<b>${esc(last.no_label)}</b> oluşturuldu`);
    const auto = res.map(r => r.automation?.message).filter(Boolean).pop();
    if (auto) toast(esc(auto));
    const warn = res.map(r => r.warning).filter(Boolean).pop();
    if (warn) toast(`<b>Konum uyarısı:</b> ${esc(warn)}`);
    await reload();
    if (openAfter && !params.task_id) { S.open = last.task_id; S.active = null; renderSheet(); }
    return last;
  } catch (e) {
    if (e instanceof NetErr) {
      await enqueue(e.rest, { ...params, task_id: e.taskId || params.task_id });
      toast(`Bağlantı koptu: <b>${e.rest.length} fotoğraf</b> kuyruğa alındı`);
      if (e.results?.length) reload().catch(() => {});
      return null;
    }
    fail(e); return null;
  }
}

let swallowClick = false;
const acts = {
  logout: async () => {
    try { await api('POST', '/api/logout'); } catch {}
    try { if (window.caches) { const ks = await caches.keys(); await Promise.all(ks.map(k => caches.open(k).then(c => c.delete('/api/bootstrap')))); } } catch {}
    es?.close(); es = null; showLogin();
  },
  go: a => { S.view = a.dataset.view; S.open = null; if (S.view !== 'map') { S.mapMode = null; S.pickPoint = null; } render(); window.scrollTo(0, 0); if (S.view === 'camera') warmCamGps(); if (S.view === 'admin' && S.admTab === 'system' && can('owner')) loadIntegrations(); },
  admTab: a => { S.admTab = a.dataset.tab; render(); if (S.admTab === 'system' && can('owner')) loadIntegrations(); },
  admArch: () => { S.admArch = !S.admArch; render(); },
  admNew: a => { S.modal = { kind: a.dataset.kind }; renderModal(); },
  admEdit: a => { S.modal = { kind: a.dataset.kind, id: a.dataset.id }; renderModal(); },
  modal: a => { S.modal = { kind: a.dataset.kind }; renderModal(); },
  modalClose: () => { S.modal = null; renderModal(); },
  modalBg: (a, e) => { if (e.target === a) acts.modalClose(); },
  custHere: async () => {
    const g = await deviceGps(); if (!g) { toast('Konum alınamadı. Konum iznini kontrol et.'); return; }
    $('#mc-lat').value = g.lat; $('#mc-lng').value = g.lng; toast('Konum eklendi');
    const addr = $('#mc-address');
    if (addr && !addr.value) { try { const r = await api('GET', `/api/geocode?lat=${g.lat}&lng=${g.lng}`); if (!addr.value) addr.value = r.address; } catch {} }
  },
  custArchive: async a => { const p = proj(a.dataset.id); const r = await run(() => api('PATCH', `/api/projects/${p.id}`, { archived: !p.archived }), p.archived ? 'Arşivden çıkarıldı' : 'Arşivlendi'); if (r) acts.modalClose(); },
  custDelete: async a => { if (!confirm('Müşteri kalıcı olarak silinsin mi?')) return; const r = await run(() => api('DELETE', `/api/projects/${a.dataset.id}`), 'Müşteri silindi'); if (r) acts.modalClose(); },
  skillDelete: async a => { if (!confirm('Yetenek silinsin mi? Kişilerden ve işlerden de kalkar.')) return; const r = await run(() => api('DELETE', `/api/skills/${a.dataset.id}`), 'Yetenek silindi'); if (r) acts.modalClose(); },
  muRevoke: a => run(() => api('PATCH', `/api/users/${a.dataset.id}`, { revoke_sessions: true }), 'Oturumlar kapatıldı'),
  assignTo: a => { const t = task(S.open); if (t.assignee_id !== a.dataset.uid) patchTask({ assignee_id: a.dataset.uid }, `${esc(nameOf(a.dataset.uid))} atandı`); },
  mode: a => { S.boardMode = a.dataset.mode; render(); },
  mcol: a => { S.mcol = a.dataset.col; render(); },
  open: a => { S.open = a.dataset.id; S.active = a.dataset.photo ?? null; S.annot = false; S.draftPin = null; renderSheet(); },
  advance: a => step(a.dataset.id, 1),
  claim: a => run(() => api('POST', `/api/tasks/${a.dataset.id}/claim`), 'İş sana atandı'),
  close: () => { S.open = null; S.annot = false; S.draftPin = null; sigDirty = false; renderSheet(); },
  closeBg: (a, e) => { if (e.target === a) acts.close(); },
  thumb: a => { S.active = a.dataset.pid; S.draftPin = null; renderSheet(); },
  annot: () => { S.annot = !S.annot; S.draftPin = null; renderSheet(); },
  shot: (a, e) => {
    if (!S.annot) return;
    const r = a.getBoundingClientRect();
    S.draftPin = { x: Math.min(100, Math.max(0, +((e.clientX - r.left) / r.width * 100).toFixed(1))), y: Math.min(100, Math.max(0, +((e.clientY - r.top) / r.height * 100).toFixed(1))) };
    renderSheet(); $('#ann-text')?.focus();
  },
  annSave: async () => {
    const el = $('#ann-text'); const v = el.value.trim(); if (!v) { toast('İşaret için kısa bir not yaz.'); return; }
    const pin = S.draftPin; S.draftPin = null; el.value = '';
    await run(() => api('POST', `/api/photos/${S.active}/annotations`, { task_id: S.open, x: pin.x, y: pin.y, text: v }));
  },
  annCancel: () => { S.draftPin = null; renderSheet(); },
  annDel: a => run(() => api('DELETE', `/api/annotations/${a.dataset.aid}`), 'İşaret silindi'),
  unlink: () => { if (confirm('Bu fotoğraf işten kaldırılsın mı?')) run(() => api('DELETE', `/api/tasks/${S.open}/photos/${S.active}`), 'Fotoğraf kaldırıldı'); },
  comment: async () => {
    const el = $('#c-text'); const v = el.value.trim(); if (!v) return;
    el.value = ''; await run(() => api('POST', `/api/tasks/${S.open}/comments`, { text: v })); $('#c-text')?.focus();
  },
  ckAdd: async () => {
    const el = $('#ck-new'); const v = el.value.trim(); if (!v) return;
    const req = $('#ck-req')?.checked; el.value = '';
    await run(() => api('POST', `/api/tasks/${S.open}/checklist`, { text: v, require_proof: !!req }));
  },
  ckDel: a => run(() => api('DELETE', `/api/checklist/${a.dataset.cid}`)),
  proof: a => run(() => api('PATCH', `/api/checklist/${a.dataset.cid}`, { proof_photo_id: S.active, done: true }), r => r?.automation?.moved ? 'Kanıt bağlandı · iş <b>Onay bekliyor</b>’a taşındı' : 'Kanıt bağlandı'),
  approve: () => run(() => api('POST', `/api/tasks/${S.open}/review`, { decision: 'approve' }), 'İş onaylandı'),
  reject: () => {
    const v = $('#rej').value.trim();
    if (!v) { toast('Geri gönderme nedeni yaz. Teknisyen neyi düzelteceğini bilmeli.'); $('#rej').focus(); return; }
    $('#rej').value = '';
    run(() => api('POST', `/api/tasks/${S.open}/review`, { decision: 'reject', reason: v }), 'İş geri gönderildi');
  },
  sigClear: () => { const c = $('#sig-pad'); c.getContext('2d').clearRect(0, 0, c.width, c.height); sigDirty = false; },
  sigSave: () => {
    const name = $('#sig-name').value.trim();
    if (!sigDirty) { toast('Önce imza alanına imza atılmalı.'); return; }
    if (!name) { toast('İmzalayanın adını yaz.'); $('#sig-name').focus(); return; }
    $('#sig-pad').toBlob(async blob => {
      const tid = S.open;
      sigDirty = false;
      await run(() => api('POST', `/api/tasks/${tid}/signature?signer=${encodeURIComponent(name)}`, blob), 'İmza kaydedildi');
    }, 'image/png');
  },
  delTask: () => { const t = task(S.open); if (confirm(`${t.no_label} kalıcı olarak silinsin mi?`)) { S.open = null; run(() => api('DELETE', `/api/tasks/${t.id}`), 'İş silindi'); } },
  newTask: async () => {
    const pid = S.project !== 'all' ? S.project : S.projects[0]?.id;
    if (!pid) { acts.admNew({ dataset: { kind: 'customer' } }); return; }
    const r = await run(() => api('POST', '/api/tasks', { project_id: pid, title: '' }));
    if (r) { S.open = r.id; S.active = null; renderSheet(); setTimeout(() => $('#t-title')?.focus(), 50); }
  },
  unpend: a => { const [p] = S.pending.splice(+a.dataset.i, 1); URL.revokeObjectURL(p.url); renderMain(); },
  camSubmit: async a => {
    if (!S.pending.length) return;
    a.disabled = true;
    const gps = await deviceGps();
    const params = { type: S.cam.type, title: $('#cam-title')?.value.trim() || '', lat: gps?.lat ?? null, lng: gps?.lng ?? null, acc: gps?.acc ?? null };
    if (S.cam.target === 'new') params.project_id = S.cam.project; else params.task_id = S.cam.target;
    const files = S.pending.map(p => p.blob);
    S.pending.forEach(p => URL.revokeObjectURL(p.url)); S.pending = [];
    const camTitle = $('#cam-title'); if (camTitle) camTitle.value = '';
    await submitPhotos(files, params);
    renderMain();
  },
  flush: () => flushQueue(),
  aiRun: async a => {
    const pid = S.active, tid = S.open; S.aiBusy = pid; renderSheet();
    try {
      const r = await api('POST', `/api/photos/${pid}/ai-review`, { task_id: tid, force: !!a.dataset.force });
      if (S.photos[pid]) S.photos[pid].ai = r;
      const crit = r.observations.filter(o => o.level === 'critical').length;
      toast(crit ? `AI gözlemi hazır · <b>${crit} kritik not</b>` : 'AI gözlemi hazır');
    } catch (e) { fail(e); }
    S.aiBusy = null; await reload().catch(() => {}); renderSheet();
  },
  tunSave: () => {
    const body = { tunnel: { mode: S.integMode || S.integ.tunnel.mode, autostart: $('#tn-auto').checked } };
    if ($('#tn-host')) body.tunnel.hostname = $('#tn-host').value;
    if ($('#tn-token')?.value) body.tunnel.tunnel_token = $('#tn-token').value;
    return saveInteg(body, 'Tünel ayarı kaydedildi');
  },
  tunStart: async () => {
    const I = S.integ, mode = S.integMode || I.tunnel.mode;
    const demoUsers = I.demo_password_users.map(u => S.users.find(x => x.username === u)).filter(Boolean);
    const blockers = tunnelBlockers(mode, demoUsers, I.tunnel);
    if (blockers.length) {
      toast('Tünel başlatılamadı: ' + blockers[0]);
      const el = $('#tun-blockers'); if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash'); }
      return;
    }
    await acts.tunSave(); try { S.integ = await api('POST', '/api/admin/tunnel/start'); toast('Tünel başlatılıyor…'); } catch (e) { fail(e); } loadIntegrations(); },
  tunStop: async () => { try { S.integ = await api('POST', '/api/admin/tunnel/stop'); toast('Tünel kapatıldı'); } catch (e) { fail(e); } renderIntegrations(); },
  copyUrl: async () => { const u = S.integ?.tunnel.run_url; try { await navigator.clipboard.writeText(u); toast('Adres kopyalandı'); } catch { toast(esc(u)); } },
  dnsSet: a => saveInteg({ dns: a.dataset.k }, 'DNS ayarlandı. Tüneli yeniden başlat.'),
  aiSave: () => {
    const body = { ai: { enabled: $('#ai-on').checked, model: $('#ai-model').value } };
    if ($('#ai-key').value) body.ai.openai_key = $('#ai-key').value;
    return saveInteg(body, 'AI ayarı kaydedildi');
  },
  aiClear: () => saveInteg({ ai: { openai_key: '' } }, 'Anahtar silindi'),
  gal: a => { S.galType = a.dataset.type; render(); },
  mapSelect: a => {
    const p = proj(a.dataset.id); if (!p) return;
    S.mapPick = p.id; S.mapDetail = true; S.mapMode = null; S.panelMin = false; removeTemp(); updateMapLayers(); renderMapPanel();
    if (p.lat != null && M.map) M.map.flyTo([p.lat, p.lng], Math.max(M.map.getZoom(), 16), { duration: .6 });
    if (innerWidth < 900 && p.lat != null) window.scrollTo({ top: 0, behavior: 'smooth' });  // telefonda listeden seçince haritaya dön
  },
  mapBack: () => { S.mapDetail = false; S.mapPick = null; updateMapLayers(); renderMapPanel(); },
  mapLayer: a => {
    const k = a.dataset.k; S.mapLayers[k] = !S.mapLayers[k];
    if (k === 'photos' && M.map) { if (S.mapLayers.photos) M.photos.addTo(M.map); else M.photos.remove(); }
    updateMapLayers(); renderMapChips(); renderMapPanel();
  },
  panelToggle: () => { S.panelMin = !S.panelMin; renderMapPanel(); },
  locateMe: () => startWatch(true),
  pickNew: () => { S.mapMode = 'new'; S.mapDetail = false; S.pickPoint = null; S.panelMin = false; removeTemp(); renderMapPanel(); toast('Haritada müşterinin yerine dokun.'); },
  pickMove: a => { S.mapPick = a.dataset.id; S.mapMode = 'move'; S.pickPoint = null; removeTemp(); renderMapPanel(); toast('Haritada müşterinin doğru yerine dokun.'); },
  pickHere: async () => { const g = S.here || await deviceGps(); if (!g) { toast('Konum alınamadı. Konum iznini kontrol et.'); return; } showMe(g, true); setPickPoint(g); },
  pickCancel: () => { S.mapMode = null; S.pickPoint = null; removeTemp(); renderMapPanel(); },
  pickSaveMove: async () => {
    const p = proj(S.mapPick), pk = S.pickPoint; if (!p || !pk) return;
    const body = { lat: pk.lat, lng: pk.lng, location_source: 'map' };
    if ($('#mv-addr')?.checked && S.pickAddr) body.address = S.pickAddr;
    const r = await run(() => api('PATCH', `/api/projects/${p.id}`, body), 'Konum kaydedildi');
    if (r) { S.mapMode = null; S.mapDetail = true; S.pickPoint = null; removeTemp(); M.didFit = true; updateMapLayers(); renderMapPanel(); }
  },
  applySug: a => run(() => api('PATCH', `/api/projects/${a.dataset.id}`, { apply_suggestion: true }), 'Adres güncellendi'),
  dismissSug: a => run(() => api('PATCH', `/api/projects/${a.dataset.id}`, { dismiss_suggestion: true })),
  camPickNear: () => { if (S.cam.near) { S.cam.project = S.cam.near.id; S.cam.userPicked = true; render(); } },
  camNewHere: () => { const g = S.here; S.view = 'map'; S.mapMode = 'new'; S.mapDetail = false; render(); if (g) { showMe(g, true); setPickPoint(g); } },
  cal: a => { const d = +a.dataset.d; if (d === 0) { const n = new Date(); S.cal = { y: n.getFullYear(), m: n.getMonth() }; } else { const n = new Date(S.cal.y, S.cal.m + d, 1); S.cal = { y: n.getFullYear(), m: n.getMonth() }; } render(); },
  theme: a => { S.theme = a.dataset.theme; store.set('ft-style', S.theme); applyTheme(); render(); api('PATCH', '/api/me', { theme: S.theme }).catch(() => {}); },
  print: () => window.print(),
};
async function saveInteg(body, msg) {
  try { S.integ = await api('PATCH', '/api/admin/integrations', body); S.integMode = null; toast(msg); if (body.ai) reload().catch(() => {}); }
  catch (e) { fail(e); }
  renderIntegrations();
}
const changes = {
  tunMode: el => { S.integMode = el.value; renderIntegrations(); },
  hdrProj: el => { S.project = el.value; render(); },
  camFile: el => { for (const f of el.files) S.pending.push({ blob: f, url: URL.createObjectURL(f) }); el.value = ''; renderMain(); },
  camTarget: el => { S.cam.target = el.value; renderMain(); },
  camProject: el => { S.cam.project = el.value; S.cam.userPicked = true; renderMain(); },
  camType: el => { S.cam.type = el.value; renderMain(); },
  title: el => { const t = task(S.open); const v = el.value.trim(); if (!v || v === t.title) return; patchTask({ title: v }); },
  status: el => { const t = task(S.open); moveTask(t.id, el.value); },
  assignee: el => patchTask({ assignee_id: el.value || null }, 'Atama güncellendi'),
  skill: el => patchTask({ skill_id: el.value || null }, 'Yetenek güncellendi'),
  muRole: el => { const f = $('#mu-lead-f'); if (f) f.hidden = el.value !== 'field'; },
  due: el => { if (el.value) patchTask({ due: el.value }); },
  priority: el => patchTask({ priority: el.value }),
  addType: el => { S.addType = el.value; },
  addFile: el => { const files = [...el.files]; el.value = ''; if (files.length) deviceGps().then(g => submitPhotos(files, { type: S.addType, task_id: S.open, lat: g?.lat ?? null, lng: g?.lng ?? null, acc: g?.acc ?? null })).then(r => { if (r?.photo_id && S.open === r.task_id) { S.active = r.photo_id; renderSheet(); } }); },
  check: el => run(() => api('PATCH', `/api/checklist/${el.dataset.cid}`, { done: el.checked }), r => r?.automation?.moved ? 'Tüm kanıtlar tamam · iş <b>Onay bekliyor</b>’a taşındı' : null),
  forceOffline: el => { S.forceOffline = el.checked; store.set('ft-force-offline', el.checked ? '1' : '0'); toast(el.checked ? 'Çevrimdışı test modu açık' : 'Çevrimdışı test modu kapalı'); render(); if (!el.checked) flushQueue(); },
  autoRule: el => run(() => api('PATCH', '/api/settings', { auto_rule: el.checked }), el.checked ? 'Otomasyon açık' : 'Otomasyon kapalı'),
  repProj: el => { S.repProj = el.value; render(); }
};
const forms = {
  resetPw: async f => { const pw = document.getElementById('rp-' + f.dataset.uid).value; try { await api('POST', `/api/admin/users/${f.dataset.uid}/password`, { password: pw }); toast('Parola değiştirildi'); } catch (e) { fail(e); } loadIntegrations(); },
  mapCustomer: async () => {
    const v = id => document.getElementById(id).value.trim();
    const pk = S.pickPoint; if (!pk) return;
    const client = v('mc-client'); if (!client) return;
    const addrEl = $('#mc-address');
    const fromGeo = addrEl.value.trim() && addrEl.value.trim() === addrEl.dataset.addr;
    const r = await run(() => api('POST', '/api/projects', { name: v('mc-name') || client, short: (v('mc-name') || client).split('·')[0].trim(), client, phone: v('mc-contact'),
      address: addrEl.value.trim(), address_source: fromGeo ? 'geocode' : 'manual', lat: pk.lat, lng: pk.lng, location_source: S.here && distM(S.here.lat, S.here.lng, pk.lat, pk.lng) < 5 ? 'device' : 'map' }), 'Müşteri eklendi');
    if (r) { S.mapMode = null; S.pickPoint = null; removeTemp(); S.mapPick = r.id; S.mapDetail = true; ['mc-client', 'mc-name', 'mc-contact'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; }); updateMapLayers(); renderMapPanel(); }
  },
  password: async () => { const r = await run(() => api('PATCH', '/api/me/password', { old: $('#pw-old').value, new: $('#pw-new').value }), 'Parola değiştirildi'); if (r) acts.modalClose(); },
  customer: async f => {
    const v = id => document.getElementById(id).value.trim();
    const client = v('mc-client'), place = v('mc-name');
    const body = { client, name: place || client, short: (place || client).split('·')[0].trim().slice(0, 40), phone: v('mc-phone'), email: v('mc-email'),
      contact: v('mc-contact'), notes: v('mc-notes') };
    const p = f.dataset.id ? proj(f.dataset.id) : null;
    if (!p || v('mc-address') !== (p.address || '')) body.address = v('mc-address');
    if (v('mc-lat') && (!p || +v('mc-lat') !== p.lat)) Object.assign(body, { lat: v('mc-lat'), lng: v('mc-lng'), location_source: 'device' });
    const r = await run(() => p ? api('PATCH', `/api/projects/${p.id}`, body) : api('POST', '/api/projects', body), p ? 'Müşteri kaydedildi' : 'Müşteri eklendi');
    if (r) acts.modalClose();
  },
  user: async f => {
    const v = id => document.getElementById(id)?.value.trim() ?? '';
    const role = document.querySelector('input[name="mu-role"]:checked')?.value;
    const skills = [...document.querySelectorAll('input[name="mu-skill"]:checked')].map(x => x.value);
    const body = { name: v('mu-name'), phone: v('mu-phone'), role, lead_id: role === 'field' ? v('mu-lead') || null : null, skills };
    const pw = document.getElementById('mu-pass').value;
    let r;
    if (f.dataset.id) {
      body.active = $('#mu-active').checked;
      r = await run(async () => { await api('PATCH', `/api/users/${f.dataset.id}`, body); if (pw) await api('POST', `/api/admin/users/${f.dataset.id}/password`, { password: pw }); return true; }, 'Kişi kaydedildi');
    } else r = await run(() => api('POST', '/api/users', { ...body, username: v('mu-user').toLowerCase(), password: pw }), 'Kişi eklendi');
    if (r) acts.modalClose();
  },
  skill: async f => {
    const body = { name: $('#ms-name').value.trim(), icon: document.querySelector('input[name="ms-icon"]:checked')?.value, color: document.querySelector('input[name="ms-color"]:checked')?.value };
    const r = await run(() => f.dataset.id ? api('PATCH', `/api/skills/${f.dataset.id}`, body) : api('POST', '/api/skills', body), 'Yetenek kaydedildi');
    if (r) acts.modalClose();
  }
};

/* ---------- olay dinleyiciler ---------- */
document.addEventListener('click', e => {
  if (swallowClick) { swallowClick = false; e.preventDefault(); return; }
  if (e.target.closest('a[href^="tel:"], a[href^="mailto:"]')) return;  // kart içindeki arama bağlantısı kartı açmasın
  const a = e.target.closest('[data-act]'); if (!a || a.tagName === 'LABEL') return;
  acts[a.dataset.act]?.(a, e);
});
document.addEventListener('change', e => { const k = e.target.dataset?.change; if (k) changes[k]?.(e.target); });
document.addEventListener('submit', e => {
  e.preventDefault();
  if (e.target.id === 'login-form') { doLogin($('#lg-user').value.trim(), $('#lg-pass').value); return; }
  if (e.target.id === 'setup-form') { doSetup(); return; }
  forms[e.target.dataset.form]?.(e.target);
});
let searchTimer = null;
document.addEventListener('input', e => {
  const k = e.target.dataset?.input;
  if (k === 'cmp') { const v = e.target.value; $('#cmp-after').style.clipPath = `inset(0 0 0 ${v}%)`; $('#cmp-bar').style.left = v + '%'; $('#cmp-knob').style.left = v + '%'; }
  if (k === 'mapSearch') { S.mapQ = e.target.value; S.mapDetail = false; updateMapLayers(); renderMapPanel(); return; }
  if (k === 'admQ') { S.admQ = e.target.value; render(); return; }
  if (k === 'search') {
    S.q = e.target.value; clearTimeout(searchTimer);
    searchTimer = setTimeout(async () => {
      if (S.q.trim().length < 2) { S.searchIds = null; render(); return; }
      try { const r = await api('GET', '/api/search?q=' + encodeURIComponent(S.q.trim())); S.searchIds = new Set(r.ids); render(); } catch (err) { fail(err); }
    }, 300);
  }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && S.modal) { acts.modalClose(); return; }
  if (e.key === 'Escape' && S.open) { acts.close(); return; }
  if (e.key !== 'Enter') return;
  const el = e.target;
  if (el.id === 'c-text') { e.preventDefault(); acts.comment(); }
  else if (el.id === 'ann-text') { e.preventDefault(); acts.annSave(); }
  else if (el.id === 'ck-new') { e.preventDefault(); acts.ckAdd(); }
  else if (el.id === 't-title') { el.blur(); }
  else if (el.matches?.('.card, .pin, .ucard[role="button"]')) { e.preventDefault(); el.click(); }
});
/* fare ile sürükle-bırak */
document.addEventListener('dragstart', e => { const c = e.target.closest?.('.card'); if (!c) return; e.dataTransfer.setData('text/plain', c.dataset.id); e.dataTransfer.effectAllowed = 'move'; requestAnimationFrame(() => c.classList.add('dragging')); });
document.addEventListener('dragover', e => { const col = e.target.closest?.('.col'); if (!col) return; e.preventDefault(); document.querySelectorAll('.col.over').forEach(x => x !== col && x.classList.remove('over')); col.classList.add('over'); });
document.addEventListener('drop', e => { const col = e.target.closest?.('.col'); if (!col) return; e.preventDefault(); moveTask(e.dataTransfer.getData('text/plain'), col.dataset.status); });
document.addEventListener('dragend', () => document.querySelectorAll('.dragging, .over').forEach(x => x.classList.remove('dragging', 'over')));
/* dokunmatik kaydırma */
let sw = null;
document.addEventListener('pointerdown', e => {
  if (e.pointerType === 'mouse') return;
  const c = e.target.closest('.card'); if (!c || e.target.closest('.adv, .claim')) return;
  const t = task(c.dataset.id); if (!t || !canAdvance(t) && !(isMgr() && t.status === 'done')) return;
  sw = { id: c.dataset.id, x: e.clientX, y: e.clientY, el: c };
});
document.addEventListener('pointermove', e => { if (!sw) return; const dx = e.clientX - sw.x; if (Math.abs(e.clientY - sw.y) < 40) sw.el.style.transform = `translateX(${dx}px) rotate(${dx / 40}deg)`; });
document.addEventListener('pointerup', e => {
  if (!sw) return; const dx = e.clientX - sw.x, dy = e.clientY - sw.y; sw.el.style.transform = '';
  const id = sw.id; sw = null;
  if (Math.abs(dx) > 80 && Math.abs(dy) < 40) { swallowClick = true; setTimeout(() => { swallowClick = false; }, 400); step(id, dx > 0 ? 1 : -1); }
});
document.addEventListener('pointercancel', () => { if (sw) { sw.el.style.transform = ''; sw = null; } });
window.addEventListener('resize', () => { measureChrome(); M.map?.invalidateSize(); });
window.addEventListener('online', () => { renderHeader(); flushQueue(); reload().catch(() => {}); });
window.addEventListener('offline', () => { renderHeader(); renderMain(); });
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && S.me) { reload().catch(() => {}); flushQueue(); } });
setInterval(flushQueue, 20000);

/* ---------- açılış ---------- */
async function boot() {
  applyTheme();
  if ('serviceWorker' in navigator && window.isSecureContext) navigator.serviceWorker.register('/sw.js').catch(() => {});
  try { const h = await api('GET', '/api/health'); S.needsSetup = !!h.needs_setup; } catch {}
  try {
    await reload();
    $('#app').hidden = false; $('#login').hidden = true;
    startEvents(); refreshQueueCount(); flushQueue();
  } catch (e) {
    if (e?.status === 401) showLogin();
    else if (e instanceof NetErr) { showLogin('Sunucuya ulaşılamıyor. FotoTakip telefonda çalışıyor mu?'); }
    else showLogin(e.message);
  }
}
boot();
})();
