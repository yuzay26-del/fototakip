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
  { id: 'open', name: 'Açık' }, { id: 'progress', name: 'Devam ediyor' }, { id: 'review', name: 'Onay bekliyor' }, { id: 'done', name: 'Tamamlandı' }
];
const ST_ICON = {
  open: '<svg viewBox="0 0 12 12"><circle cx="6" cy="6" r="4.5" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
  progress: '<svg viewBox="0 0 12 12"><circle cx="6" cy="6" r="4.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M6 1.5A4.5 4.5 0 0 1 6 10.5Z" fill="currentColor"/></svg>',
  review: '<svg viewBox="0 0 12 12"><circle cx="6" cy="6" r="4.5" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="6" cy="6" r="1.6" fill="currentColor"/></svg>',
  done: '<svg viewBox="0 0 12 12"><circle cx="6" cy="6" r="5" fill="currentColor"/><path d="M3.6 6.2l1.6 1.6 3.2-3.4" stroke="var(--surface)" stroke-width="1.5" fill="none"/></svg>'
};
const TYPES = { before: 'Önce', progress: 'Süreç', after: 'Sonra', issue: 'Sorun' };
const IC = {
  board: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="4" width="5" height="16" rx="1.5"/><rect x="10" y="4" width="5" height="10" rx="1.5"/><rect x="17" y="4" width="4" height="13" rx="1.5"/></svg>',
  gallery: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/><rect x="13" y="13" width="8" height="8" rx="1.5"/></svg>',
  camera: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M4 8h3l2-3h6l2 3h3v11H4z" stroke-linejoin="round"/><circle cx="12" cy="13" r="3.5"/></svg>',
  map: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11z"/><circle cx="12" cy="10" r="2.2"/></svg>',
  user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>',
  target: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2.5" fill="currentColor"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>',
  plus: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 5v14M5 12h14"/></svg>'
};

/* ---------- durum ---------- */
const now0 = new Date();
const S = {
  me: null, users: [], projects: [], tasks: [], photos: {}, settings: { auto_rule: true }, needsSetup: false, loaded: false,
  view: 'board', boardMode: 'kanban', mcol: 'progress', project: 'all', q: '', searchIds: null,
  open: null, active: null, annot: false, draftPin: null, galType: 'all', mapPick: null, repProj: null,
  cal: { y: now0.getFullYear(), m: now0.getMonth() }, theme: store.get('ft-theme') || 'system',
  cam: { target: 'new', project: null, type: 'before' }, pending: [], addType: 'progress',
  mapLayers: { photos: true, openOnly: false }, mapQ: '', mapMode: null, mapDetail: false, pickPoint: null, pickAddr: undefined, panelMin: false, here: null,
  queueCount: 0, forceOffline: store.get('ft-force-offline') === '1', online: navigator.onLine, flushing: false
};

const user = id => S.users.find(u => u.id === id);
const nameOf = id => id === 'sys' ? 'Sistem' : user(id)?.name ?? '—';
const proj = id => S.projects.find(p => p.id === id);
const task = id => S.tasks.find(t => t.id === id);
const thumb = pid => `/files/${pid}?s=t`;
const full = pid => `/files/${pid}`;
const isMgr = () => S.me?.role === 'manager';
const isPool = t => !t.assignee_id;
const mine = t => isMgr() || t.assignee_id === S.me.id;
const stName = id => STATUSES.find(s => s.id === id).name;
const stPill = id => `<span class="st ${id}">${ST_ICON[id]}${stName(id)}</span>`;
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
  Object.assign(S, { me: d.me, users: d.users, projects: d.projects, tasks: d.tasks, photos: d.photos, settings: d.settings, loaded: true });
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
    <h1><span class="brand-mark">${IC.camera.replace('<svg ', '<svg width="18" height="18" ')}</span>FotoTakip</h1>
    <p class="hint"><b>İlk kurulum.</b> Henüz hesap yok; yönetici hesabını oluştur. Kurulum kodu FotoTakip'i başlattığın Termux ekranında yazıyor
      (ya da Termux'ta: <code>cat ~/fototakip-data/kurulum-kodu.txt</code>).</p>
    <label class="field"><span>Kurulum kodu</span><input id="su-code" class="input" autocapitalize="characters" placeholder="ABCD-1234" required></label>
    <label class="field"><span>Adın</span><input id="su-name" class="input" autocomplete="name" required maxlength="80"></label>
    <label class="field"><span>Kullanıcı adı</span><input id="su-user" class="input" autocomplete="username" autocapitalize="none" pattern="[a-z0-9._\\-]{3,32}" placeholder="küçük harf, rakam, nokta, tire" required></label>
    <label class="field"><span>Parola</span><input id="su-pass" class="input" type="password" autocomplete="new-password" minlength="8" required></label>
    <label class="field"><span>Parola (tekrar)</span><input id="su-pass2" class="input" type="password" autocomplete="new-password" minlength="8" required></label>
    <p class="err" id="lg-err">${esc(msg)}</p>
    <button class="btn primary" type="submit">Yönetici hesabını oluştur</button>
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
    toast('Hoş geldin. Ekip arkadaşlarını Profil › Ekip bölümünden ekleyebilirsin.');
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
    <h1><span class="brand-mark">${IC.camera.replace('<svg ', '<svg width="18" height="18" ')}</span>FotoTakip</h1>
    <label class="field"><span>Kullanıcı adı</span><input id="lg-user" class="input" name="username" autocomplete="username" autocapitalize="none" required></label>
    <label class="field"><span>Parola</span><input id="lg-pass" class="input" type="password" name="password" autocomplete="current-password" required></label>
    <p class="err" id="lg-err">${esc(msg)}</p>
    <button class="btn primary" type="submit">Giriş yap</button>
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

/* ---------- başlık ve alt menü ---------- */
function renderHeader() {
  if (!S.me) return;
  const showProj = ['board', 'gallery'].includes(S.view);
  $('#hdr').innerHTML = `
    <div class="brand"><span class="brand-mark">${IC.camera.replace('<svg ', '<svg width="16" height="16" ')}</span>FotoTakip</div>
    <div class="top-right">
      ${showProj ? `<label class="vh" for="hdr-proj">Proje</label><select id="hdr-proj" class="select" data-change="hdrProj">
        <option value="all"${S.project === 'all' ? ' selected' : ''}>Tüm projeler</option>
        ${S.projects.map(p => `<option value="${p.id}"${S.project === p.id ? ' selected' : ''}>${esc(p.name)}</option>`).join('')}</select>` : ''}
      ${offline() ? `<span class="pill warn"><span class="dot"></span>Çevrimdışı</span>` : ''}
      ${S.queueCount ? `<button class="pill warn" data-act="flush" title="Şimdi yükle">${S.queueCount} kuyrukta</button>` : ''}
      <button class="pill" data-act="go" data-view="profile" title="Profil">${esc(S.me.short)} · ${isMgr() ? 'Yönetici' : 'Saha'}</button>
    </div>`;
}
function renderDock() {
  if (!S.me) return;
  const items = [['board', 'Pano'], ['gallery', 'Galeri'], ['camera', 'Kamera'], ['map', 'Harita'], ['profile', 'Profil']];
  $('#dock').innerHTML = items.map(([v, l]) => v === 'camera'
    ? `<button class="camkey" data-act="go" data-view="camera" ${S.view === v ? 'aria-current="page"' : ''}><span class="k">${IC.camera}</span>${l}${S.queueCount ? `<span class="badge">${S.queueCount}</span>` : ''}</button>`
    : `<button data-act="go" data-view="${v}" ${S.view === v || (v === 'profile' && S.view === 'report') ? 'aria-current="page"' : ''}>${IC[v === 'profile' ? 'user' : v]}${l}</button>`).join('');
}

/* ---------- pano ---------- */
function viewBoard() {
  const ts = visibleTasks();
  const modes = [['kanban', 'Pano'], ['list', 'Liste'], ['calendar', 'Takvim']];
  const head = `<div class="pane-head"><div><div class="eyebrow">${isMgr() ? 'Tüm ekip' : 'Benim işlerim ve havuz'} · ${ts.length} iş</div><h2>İş panosu</h2></div>
    <div class="row">
      <div class="search"><label class="vh" for="q">Ara</label><input id="q" class="input" type="search" placeholder="Ara: başlık, İE-no, yorum" value="${esc(S.q)}" data-input="search" autocomplete="off"></div>
      <div class="seg" role="group" aria-label="Görünüm">${modes.map(([m, l]) => `<button data-act="mode" data-mode="${m}" aria-pressed="${S.boardMode === m}">${l}</button>`).join('')}</div>
      ${isMgr() ? '<button class="btn" data-act="newTask">+ İş</button>' : ''}
    </div></div>`;
  if (!S.projects.length) return head + `<div class="empty">Henüz proje yok. ${isMgr() ? 'Profil sayfasından ilk projeyi ekle.' : 'Yöneticinin proje eklemesi gerekiyor.'}</div>`;
  if (S.boardMode === 'list') return head + viewList(ts);
  if (S.boardMode === 'calendar') return head + viewCalendar(ts);
  const cols = STATUSES.map(s => {
    const items = ts.filter(t => t.status === s.id);
    return `<section class="col ${S.mcol === s.id ? 'active' : ''}" data-status="${s.id}" aria-label="${s.name}">
      <div class="col-head">${stPill(s.id)}<span class="count">${items.length}</span></div>
      ${items.length ? items.map(card).join('') : `<div class="empty">Bu durumda iş yok${s.id !== 'done' ? '. Kartı buraya sürükle.' : '.'}</div>`}
    </section>`;
  }).join('');
  return head + `
    <div class="seg coltabs" role="group" aria-label="Durum">${STATUSES.map(s => `<button data-act="mcol" data-col="${s.id}" aria-pressed="${S.mcol === s.id}">${s.name} · ${ts.filter(t => t.status === s.id).length}</button>`).join('')}</div>
    <p class="swipe-hint">Kartı sağa kaydır: sonraki durum. Sola kaydır: önceki durum.</p>
    <div class="board">${cols}</div>`;
}
function canAdvance(t) {
  if (t.status === 'done' || isPool(t) && !isMgr()) return false;
  return isMgr() || (mine(t) && t.status !== 'review');
}
function card(t) {
  const pid = coverPid(t);
  const anns = annCount(t);
  const pool = isPool(t) && !isMgr();
  return `<article class="card" draggable="${!pool}" data-act="open" data-id="${t.id}" tabindex="0" aria-label="${esc(t.no_label)} ${esc(t.title)}">
    <div class="cover">${pid ? `<img src="${thumb(pid)}" alt="" loading="lazy">` : ''}${t.rejected_reason ? '<span class="flag">Geri gönderildi</span>' : pool ? '<span class="pool-tag">Havuz</span>' : ''}<span class="ph-count">${t.photos.length} foto</span></div>
    ${pool ? `<button class="claim" data-act="claim" data-id="${t.id}">Üstlen</button>` : canAdvance(t) ? `<button class="adv" data-act="advance" data-id="${t.id}" aria-label="Sonraki duruma taşı" title="Sonraki duruma taşı">→</button>` : ''}
    <div class="card-body">
      <div class="row"><span class="wo">${esc(t.no_label)}</span><span class="wo">· ${esc(proj(t.project_id)?.short)}</span>${t.priority === 'high' ? '<span class="prio">Acil</span>' : ''}</div>
      <h3 class="${t.untitled ? 'untitled' : ''}">${esc(t.title)}</h3>
      <div class="row meta"><span class="due ${dueCls(t)}">${dueLabel(t)}</span>${anns ? `<span>${anns} işaret</span>` : ''}${t.checklist.length ? `<span>${t.checklist.filter(c => c.done).length}/${t.checklist.length}</span>` : ''}${t.signature ? '<span>İmzalı</span>' : ''}${av(t.assignee_id)}</div>
    </div></article>`;
}
function viewList(ts) {
  const rows = [...ts].sort((a, b) => (a.status === 'done') - (b.status === 'done') || a.due.localeCompare(b.due));
  if (!rows.length) return '<div class="empty">Gösterilecek iş yok.</div>';
  return `<div class="table-wrap"><table><thead><tr><th></th><th>İş</th><th>Proje</th><th>Durum</th><th>Atanan</th><th>Son tarih</th></tr></thead><tbody>
    ${rows.map(t => `<tr data-act="open" data-id="${t.id}"><td>${coverPid(t) ? `<img class="thumb" src="${thumb(coverPid(t))}" alt="" loading="lazy">` : ''}</td>
      <td><div class="wo">${esc(t.no_label)}</div><b style="font-weight:600" class="${t.untitled ? 'muted' : ''}">${esc(t.title)}</b></td>
      <td>${esc(proj(t.project_id)?.short)}</td><td>${stPill(t.status)}</td><td>${t.assignee_id ? esc(nameOf(t.assignee_id)) : '<span class="muted">Havuz</span>'}</td>
      <td><span class="due ${dueCls(t)}">${dueLabel(t)}</span></td></tr>`).join('')}
  </tbody></table></div>`;
}
function viewCalendar(ts) {
  const { y, m } = S.cal;
  const first = new Date(y, m, 1);
  const start = new Date(y, m, 1 - (first.getDay() + 6) % 7);
  const days = Array.from({ length: 42 }, (_, i) => { const d = new Date(start); d.setDate(start.getDate() + i); return d; });
  const shown = days[35].getMonth() !== m ? days.slice(0, 35) : days;
  return `<div class="panel" style="display:grid;gap:12px">
    <div class="row" style="justify-content:space-between"><b style="font-family:var(--f-display);font-size:22px">${MONTHS[m]} ${y}</b>
      <div class="row"><button class="btn" data-act="cal" data-d="-1" aria-label="Önceki ay">‹</button><button class="btn" data-act="cal" data-d="0">Bugün</button><button class="btn" data-act="cal" data-d="1" aria-label="Sonraki ay">›</button></div></div>
    <div class="cal">${['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'].map(d => `<div class="dn">${d}</div>`).join('')}
    ${shown.map(d => { const ds = dayStr(d); const evs = ts.filter(t => t.due === ds);
      return `<div class="day ${d.getMonth() !== m ? 'out' : ''} ${ds === todayStr() ? 'today' : ''}"><span class="num">${d.getDate()}</span>
        ${evs.map(t => `<button class="ev ${t.status} ${isLate(t) ? 'late' : ''}" data-act="open" data-id="${t.id}" title="${esc(t.title)}">${esc(t.title)}</button>`).join('')}</div>`; }).join('')}
    </div>
    <p class="muted" style="margin:0;font-size:12.5px">Kırmızı çerçeve: son tarihi geçmiş ve tamamlanmamış iş.</p></div>`;
}

/* ---------- galeri ---------- */
function viewGallery() {
  const links = [];
  visibleTasks().forEach(t => t.photos.forEach(p => { const ph = S.photos[p.pid]; if (ph) links.push({ t, p, ph }); }));
  links.sort((a, b) => String(b.ph.taken_at).localeCompare(String(a.ph.taken_at)));
  const shown = links.filter(l => S.galType === 'all' || l.p.type === S.galType);
  const types = [['all', 'Tümü'], ...Object.entries(TYPES)];
  return `<div class="pane-head"><div><div class="eyebrow">${shown.length} fotoğraf · en yeni önce</div><h2>Galeri</h2></div>
    <div class="chips">${types.map(([k, l]) => `<button class="chip" data-act="gal" data-type="${k}" aria-pressed="${S.galType === k}">${l} ${k === 'all' ? links.length : links.filter(x => x.p.type === k).length}</button>`).join('')}</div></div>
    ${shown.length ? `<div class="masonry">${shown.map(({ t, p, ph }) => `<button class="tile" data-act="open" data-id="${t.id}" data-photo="${ph.id}">
      <img src="${thumb(ph.id)}" alt="${esc(TYPES[p.type])} fotoğrafı: ${esc(t.title)}" loading="lazy"><span class="tag ${p.type}">${TYPES[p.type]}</span>
      <span class="cap"><b>${esc(t.title)}</b><span class="mono muted">${fmtTime(ph.taken_at)} · ${ph.lat != null ? GPS_SRC[ph.gps_source] : 'konum yok'}${ph.annotations.length ? ` · ${ph.annotations.length} işaret` : ''}</span>${ph.address ? `<span class="muted" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(ph.address)}</span>` : ''}</span></button>`).join('')}</div>`
      : '<div class="empty">Bu filtrede fotoğraf yok. Kamera sekmesinden ilk fotoğrafı çek.</div>'}`;
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
  if (S.cam.locating) return '<p class="muted near">Konumun alınıyor…</p>';
  const n = S.cam.near; if (!n) return S.here === null ? '' : '<p class="muted near">Kayıtlı konumu olan müşteri yok.</p>';
  const p = proj(n.id); if (!p) return '';
  if (n.d <= NEAR_METERS) return S.cam.project === p.id
    ? `<p class="near ok">Konumuna göre seçildi: <b>${esc(p.client || p.short)}</b> · ${fmtDist(n.d)}</p>`
    : `<p class="near">Yakındaki müşteri: <b>${esc(p.client || p.short)}</b> · ${fmtDist(n.d)} <button class="linkbtn" data-act="camPickNear">Seç</button></p>`;
  return `<p class="near warn">Yakında kayıtlı müşteri yok (en yakın: ${esc(p.client || p.short)}, ${fmtDist(n.d)}).${isMgr() ? ' <button class="linkbtn" data-act="camNewHere">Bu konumda yeni müşteri ekle</button>' : ''}</p>`;
}
function viewCamera() {
  const f = S.cam;
  const targets = S.tasks.filter(t => t.status !== 'done' && mine(t));
  if (f.target !== 'new' && !targets.some(t => t.id === f.target)) f.target = 'new';
  const btnLabel = f.target === 'new' ? (S.pending.length > 1 ? `${S.pending.length} fotoğrafla iş oluştur` : 'İş oluştur') : (S.pending.length > 1 ? `${S.pending.length} fotoğrafı ekle` : 'İşe ekle');
  if (!S.projects.length) return '<div class="empty">Fotoğraf çekmeden önce bir proje gerekli.</div>';
  return `<div class="pane-head"><div><div class="eyebrow">Fotoğraftan işe iki dokunuş</div><h2>Kamera</h2></div></div>
  <div class="cam-grid">
    <div class="stack" style="gap:12px">
      <label class="shutter" for="cam-file"><span class="lens">${IC.camera.replace('<svg ', '<svg width="34" height="34" ')}</span><b>Fotoğraf çek veya seç</b><span class="muted" style="font-size:13px">Telefonda kamera açılır. Galeriden birden fazla fotoğraf da seçebilirsin.</span></label>
      <input id="cam-file" class="vh" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" multiple data-change="camFile">
      <label class="btn" for="cam-gal" style="justify-content:center">Galeriden seç</label>
      <input id="cam-gal" class="vh" type="file" accept="image/jpeg,image/png,image/webp" multiple data-change="camFile">
      ${S.pending.length ? `<div class="pending">${S.pending.map((p, i) => `<figure><img src="${p.url}" alt="Seçilen fotoğraf ${i + 1}"><button data-act="unpend" data-i="${i}" aria-label="Kaldır">×</button></figure>`).join('')}</div>` : ''}
    </div>
    <div class="panel stack" style="gap:14px">
      <label class="field"><span>Nereye</span><select id="cam-target" class="select" data-change="camTarget">
        <option value="new"${f.target === 'new' ? ' selected' : ''}>Yeni iş oluştur</option>
        ${targets.map(t => `<option value="${t.id}"${f.target === t.id ? ' selected' : ''}>${esc(t.no_label)} · ${esc(t.title)}</option>`).join('')}</select></label>
      ${f.target === 'new' ? `<label class="field"><span>Müşteri / saha</span><select id="cam-project" class="select" data-change="camProject">${S.projects.map(p => `<option value="${p.id}"${f.project === p.id ? ' selected' : ''}>${esc(p.client ? `${p.client} · ${p.short}` : p.name)}</option>`).join('')}</select></label>${camNearLine()}` : ''}
      <div class="field"><span>Fotoğraf türü</span><div class="types" role="radiogroup">${Object.entries(TYPES).map(([k, l]) => `<label><input type="radio" name="cam-type" id="cam-type-${k}" value="${k}" data-change="camType" ${f.type === k ? 'checked' : ''}><span>${l}</span></label>`).join('')}</div></div>
      ${f.target === 'new' ? `<label class="field"><span>Başlık (isteğe bağlı)</span><input id="cam-title" class="input" placeholder="Boş kalırsa: Başlıksız iş · saat" autocomplete="off" data-keep></label>` : ''}
      ${S.settings.auto_rule && f.type === 'after' && f.target !== 'new' ? '<div class="note"><b>Otomasyon açık:</b> önce fotoğrafı ve zorunlu kanıtlar tamamsa iş “Onay bekliyor”a geçer.</div>' : ''}
      <button class="btn primary" data-act="camSubmit" ${S.pending.length ? '' : 'disabled'}>${btnLabel}</button>
      ${offline() ? '<div class="note"><b>Çevrimdışısın.</b> Fotoğraflar telefonda kuyruğa alınır, bağlantı gelince sırayla yüklenir.</div>' : ''}
      ${!window.isSecureContext ? '<p class="muted" style="font-size:12px;margin:0">Bu bağlantı HTTPS değil: cihaz konumu alınamaz, konum yalnızca fotoğrafın EXIF bilgisinden veya proje adresinden gelir.</p>' : ''}
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
const located = () => S.projects.filter(p => p.lat != null);
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
      <div class="map-top"><label class="vh" for="map-q">Müşteri ara</label><input id="map-q" class="input map-search" type="search" placeholder="Müşteri, adres veya saha ara" autocomplete="off" data-input="mapSearch" data-keep>
        <div id="map-chips" class="chips"></div></div>
      <div class="map-fabs"><button class="fab" id="fab-me" data-act="locateMe" aria-label="Konumuma git" title="Konumuma git">${IC.target}</button>
        ${isMgr() ? `<button class="fab" data-act="pickNew" aria-label="Haritadan müşteri ekle" title="Haritadan müşteri ekle">${IC.plus}</button>` : ''}</div>
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
  box.innerHTML = chip('photos', 'Fotoğraflar') + chip('openOnly', 'Yalnız açık işler') + (offline() ? '<span class="pill warn">Çevrimdışı: yalnızca önceden bakılan bölge</span>' : '');
}
function panelHead(title, sub) { return `<div class="mp-head"><div style="min-width:0"><b class="mp-title">${title}</b>${sub ? `<div class="addr">${sub}</div>` : ''}</div><button class="x" data-act="panelToggle" aria-label="${S.panelMin ? 'Paneli aç' : 'Paneli küçült'}">${S.panelMin ? '▴' : '▾'}</button></div>`; }
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
  box.innerHTML = panelHead(here ? 'Yakınımdaki müşteriler' : 'Müşteriler', here ? `Konumun ±${Math.round(here.acc ?? 0)} m` : (window.isSecureContext ? 'Konumunu görmek için hedef düğmesine bas' : 'Konum için HTTPS gerekli'))
    + `<div class="mp-body">${list.length ? list.map(({ p: x, d, open }) => `<button class="mini" data-act="mapSelect" data-id="${x.id}">
        <span class="cdot ${open ? '' : 'idle'}">${open}</span>
        <span style="min-width:0"><b>${esc(x.client || x.name)}</b><span class="addr" style="display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(x.address || 'Adres yok')}</span></span>
        <span class="mono muted">${d != null ? fmtDist(d) : x.lat == null ? 'konum yok' : ''}</span></button>`).join('') : '<div class="empty">Eşleşen müşteri yok.</div>'}
      ${noLoc ? `<p class="muted" style="font-size:12.5px;margin:6px 2px 0">${noLoc} müşterinin konumu yok. İlk konumlu fotoğraf geldiğinde konumu otomatik eklenir.</p>` : ''}</div>`;
}
function panelCustomer(p, here) {
  const open = openTasksOf(p);
  const done = S.tasks.filter(t => t.project_id === p.id && t.status === 'done').length;
  const d = here && p.lat != null ? distM(here.lat, here.lng, p.lat, p.lng) : null;
  return panelHead(esc(p.client || p.name), esc(p.name)) + `<div class="mp-body">
    <div class="mp-addr">${p.address ? esc(p.address) : '<span class="muted">Adres yok</span>'}${p.address_source && SRC_LABEL[p.address_source] ? ` <span class="gps-src">${SRC_LABEL[p.address_source]}</span>` : ''}</div>
    ${p.suggested_address ? `<div class="note"><b>Fotoğraflardan farklı bir adres bulundu:</b> ${esc(p.suggested_address)}
      ${isMgr() ? `<div class="row" style="margin-top:6px"><button class="btn primary" data-act="applySug" data-id="${p.id}">Bu adresi kullan</button><button class="btn" data-act="dismissSug" data-id="${p.id}">Yoksay</button></div>` : ''}</div>` : ''}
    ${p.contact ? `<div class="addr">Yetkili: <span class="sel">${esc(p.contact)}</span></div>` : ''}
    <div class="row mono muted" style="font-size:12px">${p.lat != null ? `${p.lat.toFixed(5)}°, ${p.lng.toFixed(5)}° · ${SRC_LABEL[p.location_source] || ''}` : 'Konum yok'}${d != null ? ` · sana ${fmtDist(d)}` : ''}</div>
    <div class="row">
      ${p.lat != null ? `<a class="btn primary" href="${dirUrl(p)}" target="_blank" rel="noopener">Yol tarifi</a>` : ''}
      <button class="btn" data-act="mapBack">Listeye dön</button>
      ${isMgr() ? `<button class="btn" data-act="pickMove" data-id="${p.id}">${p.lat != null ? 'Konumu düzelt' : 'Konum ekle'}</button>` : ''}
    </div>
    <div class="sec-h" style="margin:8px 0 0"><h4>Açık işler · ${open.length}</h4><span class="muted" style="font-size:12px">${done} tamamlandı</span></div>
    ${open.length ? open.map(t => `<button class="mini" data-act="open" data-id="${t.id}">${coverPid(t) ? `<img src="${thumb(coverPid(t))}" alt="">` : '<span></span>'}<span style="min-width:0"><b>${esc(t.title)}</b><span class="wo">${esc(t.no_label)} · <span class="due ${dueCls(t)}">${dueLabel(t)}</span></span></span>${stPill(t.status)}</button>`).join('') : '<div class="empty">Açık iş yok.</div>'}
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
      <input id="mc-contact" class="input" placeholder="Telefon veya yetkili" data-keep>
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
  if (!window.isSecureContext || !navigator.geolocation) { toast('Konumunu görmek için güvenli bağlantı (HTTPS) gerekiyor. Bu telefonda <b>http://localhost:8080</b> adresinden aç ya da <b>fototakip-tunel</b> kullan.'); return; }
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
  if (!p) return '<div class="empty">Henüz proje yok.</div>';
  const ts = S.tasks.filter(t => t.project_id === p.id);
  const fin = ts.filter(t => t.status === 'done' || t.status === 'review');
  const withPair = fin.filter(t => firstOf(t, 'before') && lastOf(t, 'after'));
  const missing = fin.filter(t => !(firstOf(t, 'before') && lastOf(t, 'after')));
  return `<div class="pane-head no-print"><div><div class="eyebrow">Müşteriye teslim belgesi</div><h2>Rapor</h2></div>
    <div class="row"><label class="vh" for="rep-proj">Proje</label><select id="rep-proj" class="select" data-change="repProj">${S.projects.map(x => `<option value="${x.id}"${x.id === p.id ? ' selected' : ''}>${esc(x.name)}</option>`).join('')}</select>
    <button class="btn primary" data-act="print">Yazdır / PDF</button></div></div>
  <article class="report">
    <div class="rep-head"><div><div class="eyebrow">İş teslim raporu</div><h3>${esc(p.name)}</h3><div class="muted">${esc(p.address)}</div></div>
      <dl class="kv"><dt>Müşteri</dt><dd>${esc(p.client || '—')}</dd><dt>Rapor tarihi</dt><dd class="mono">${fmtDate(todayStr())} ${new Date().getFullYear()}</dd><dt>Hazırlayan</dt><dd>${esc(S.me.name)}</dd></dl></div>
    <div class="stats"><div><b>${ts.length}</b><span>toplam iş</span></div><div><b>${ts.filter(t => t.status === 'done').length}</b><span>tamamlandı</span></div><div><b>${ts.filter(t => t.status === 'review').length}</b><span>onay bekliyor</span></div><div><b>${ts.filter(isLate).length}</b><span>gecikmede</span></div></div>
    ${withPair.length ? withPair.map(t => { const b = S.photos[firstOf(t, 'before').pid], a = S.photos[lastOf(t, 'after').pid];
      return `<section class="pair"><div class="row" style="justify-content:space-between"><b>${esc(t.no_label)} · ${esc(t.title)}</b>${stPill(t.status)}</div>
        <div class="pair-imgs"><figure><img src="${full(b.id)}" alt="Önce"><span class="tag">Önce</span><figcaption class="mono">${fmtTime(b.taken_at)}</figcaption></figure>
        <figure><img src="${full(a.id)}" alt="Sonra"><span class="tag after">Sonra</span><figcaption class="mono">${fmtTime(a.taken_at)}</figcaption></figure></div>
        ${t.checklist.length ? `<div class="muted" style="font-size:12.5px">${t.checklist.map(c => `${c.done ? '✓' : '○'} ${esc(c.text)}`).join(' · ')}</div>` : ''}
        ${t.signature ? `<div class="row"><img src="/files/signature/${t.id}?v=${encodeURIComponent(t.signature.at)}" alt="Müşteri imzası" style="max-height:70px;background:#fff;border-radius:6px"><span class="muted" style="font-size:12.5px">İmzalayan: ${esc(t.signature.signer)} · ${fmtTime(t.signature.at)}</span></div>` : '<div class="muted" style="font-size:12.5px">Müşteri imzası yok</div>'}</section>`; }).join('')
      : '<div class="empty">Bu projede önce/sonra fotoğrafı tamamlanmış iş yok.</div>'}
    ${missing.length ? `<div class="note"><b>Kanıtı eksik:</b> ${missing.map(t => esc(t.no_label)).join(', ')} onaya gönderildi veya tamamlandı ama önce/sonra çifti yok.</div>` : ''}
  </article>
  <p class="muted no-print" style="font-size:12.5px">Rapordaki fotoğraflar sunucuda EXIF'siz kaydedildiği için konum bilgisi içermez.</p>`;
}

/* ---------- profil ---------- */
function viewProfile() {
  const themeBtn = (t, l) => `<button data-act="theme" data-theme="${t}" aria-pressed="${S.theme === t}">${l}</button>`;
  const secure = window.isSecureContext;
  return `<div class="pane-head"><div><div class="eyebrow">${isMgr() ? 'Yönetici' : 'Saha teknisyeni'} · @${esc(S.me.username)}</div><h2>${esc(S.me.name)}</h2></div>
    <button class="btn" data-act="logout">Çıkış yap</button></div>
  <div class="settings">
    <section class="panel">
      <div class="sec-h"><h4>Bağlantı</h4></div>
      <div class="set-row"><div><b>${esc(location.origin)}</b><p>${secure ? 'Güvenli bağlantı: kamera, konum ve çevrimdışı açılış çalışır.' : 'HTTPS değil: çevrimdışı açılış ve cihaz konumu kapalı. Diğer telefonlar için README’deki tünel adımını uygula.'}</p></div><span class="pill ${secure ? 'ok' : 'bad'}">${secure ? 'Güvenli' : 'HTTP'}</span></div>
      <div class="set-row"><div><b>Çevrimdışı test modu</b><p>İnternet varken de fotoğrafları kuyruğa alır. Sahayı denemek için.</p></div><label class="switch"><input type="checkbox" id="sw-off" data-change="forceOffline" ${S.forceOffline ? 'checked' : ''} aria-label="Çevrimdışı test modu"><span></span></label></div>
      <div class="set-row"><div><b>Yükleme kuyruğu</b><p>${S.queueCount ? `${S.queueCount} gönderim bekliyor.` : 'Kuyruk boş.'}</p></div><button class="btn" data-act="flush" ${S.queueCount ? '' : 'disabled'}>Şimdi yükle</button></div>
      <div class="sec-h" style="margin-top:14px"><h4>Görünüm</h4></div>
      <div class="seg" role="group" aria-label="Tema">${themeBtn('system', 'Sistem')}${themeBtn('light', 'Açık')}${themeBtn('dark', 'Koyu')}</div>
    </section>
    <section class="panel">
      <div class="sec-h"><h4>İşlemler</h4></div>
      <div class="set-row"><div><b>Rapor</b><p>Proje için önce/sonra teslim belgesi.</p></div><button class="btn" data-act="go" data-view="report">Raporu aç</button></div>
      ${isMgr() ? `<div class="set-row"><div><b>Otomasyon kuralı</b><p>“Sonra” fotoğrafı gelince, önce fotoğrafı ve zorunlu kanıtlar tamamsa işi onaya taşı.</p></div><label class="switch"><input type="checkbox" id="sw-auto" data-change="autoRule" ${S.settings.auto_rule ? 'checked' : ''} aria-label="Otomasyon kuralı"><span></span></label></div>
      <div class="set-row"><div><b>Yedek indir</b><p>Veritabanı ve tüm fotoğraflar tek zip dosyasında.</p></div><a class="btn" href="/api/backup">İndir</a></div>` : ''}
      <form class="stack" data-form="password" style="margin-top:10px"><div class="sec-h" style="margin:0"><h4>Parola değiştir</h4></div>
        <div class="form-grid"><input id="pw-old" class="input" type="password" placeholder="Mevcut parola" autocomplete="current-password" required><input id="pw-new" class="input" type="password" placeholder="Yeni parola (en az 6)" autocomplete="new-password" minlength="6" required></div>
        <button class="btn" type="submit">Parolayı değiştir</button></form>
    </section>
    ${isMgr() ? `<section class="panel users">
      <div class="sec-h"><h4>Ekip · ${S.users.length}</h4></div>
      <ul>${S.users.map(u => `<li>${av(u.id)}<span style="min-width:0"><b>${esc(u.name)}</b> <span class="muted">@${esc(u.username)}</span></span><span class="pill" style="margin-left:auto">${u.role === 'manager' ? 'Yönetici' : 'Saha'}</span></li>`).join('')}</ul>
      <form class="stack" data-form="user" style="margin-top:12px"><div class="form-grid">
        <input id="nu-name" class="input" placeholder="Ad Soyad" required data-keep><input id="nu-user" class="input" placeholder="kullanici.adi" autocapitalize="none" required data-keep>
        <input id="nu-pass" class="input" type="password" placeholder="Parola" minlength="6" required autocomplete="new-password">
        <select id="nu-role" class="select"><option value="field">Saha teknisyeni</option><option value="manager">Yönetici</option></select></div>
        <button class="btn" type="submit">Kişi ekle</button></form>
    </section>
    <section class="panel">
      <div class="sec-h"><h4>Yeni proje</h4></div>
      <form class="stack" data-form="project"><div class="form-grid">
        <input id="np-name" class="input" placeholder="Ad (örn. Kadıköy · Moda Apt.)" required data-keep><input id="np-short" class="input" placeholder="Kısa ad" data-keep>
        <input id="np-client" class="input" placeholder="Müşteri" data-keep><input id="np-contact" class="input" placeholder="Yetkili ve telefon" data-keep>
        <input id="np-address" class="input" placeholder="Adres" data-keep>
        <input id="np-lat" class="input" inputmode="decimal" placeholder="Enlem (41.0082)" data-keep><input id="np-lng" class="input" inputmode="decimal" placeholder="Boylam (28.9784)" data-keep></div>
        <div class="row"><button class="btn" type="submit">Projeyi ekle</button>${window.isSecureContext ? '<button class="btn" type="button" data-act="hereGps">Bulunduğum konumu kullan</button>' : ''}</div></form>
    </section>` : ''}
  </div>
  ${isMgr() ? viewIntegrations() : ''}`;
}

/* ---------- entegrasyonlar: dışarıdan erişim, DNS, AI ---------- */
const TUN_STATUS = { stopped: ['Kapalı', ''], starting: ['Başlıyor…', 'warn'], running: ['Açık', 'ok'], error: ['Hata', 'bad'] };
let integTimer = null;
async function loadIntegrations() {
  try { S.integ = await api('GET', '/api/admin/integrations'); } catch (e) { fail(e); return; }
  if (S.view === 'profile') renderIntegrations();
  clearTimeout(integTimer);
  if (S.view === 'profile' && S.integ.tunnel.run_status === 'starting') integTimer = setTimeout(loadIntegrations, 1500);
}
function renderIntegrations() { const box = $('#integ'); if (box) { const kept = keepInputs(); box.outerHTML = viewIntegrations(); restoreInputs(kept); } }
function viewIntegrations() {
  const I = S.integ;
  if (!I) return '<section class="panel" id="integ"><div class="muted">Entegrasyonlar yükleniyor…</div></section>';
  const T = I.tunnel, [stName2, stCls] = TUN_STATUS[T.run_status] || TUN_STATUS.stopped;
  const mode = S.integMode || T.mode;
  const demoUsers = I.demo_password_users.map(u => S.users.find(x => x.username === u)).filter(Boolean);
  const radio = (v, l, d) => `<label class="opt"><input type="radio" name="tun-mode" value="${v}" data-change="tunMode" ${mode === v ? 'checked' : ''}><span><b>${l}</b><small>${d}</small></span></label>`;
  return `<section class="panel integ" id="integ">
    <div class="pane-head" style="margin-bottom:6px"><div><div class="eyebrow">Yönetici</div><h2 style="font-size:24px">Entegrasyonlar</h2></div></div>
    <div class="integ-grid">
    <div class="stack" style="gap:10px">
      <div class="sec-h" style="margin:0"><h4>Dışarıdan erişim</h4><span class="pill ${stCls}">${stName2}</span></div>
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
      <div class="sec-h" style="margin:0"><h4>DNS sunucusu</h4><span class="mono muted">${esc(I.dns.servers.join(', ') || 'sistem')}</span></div>
      ${I.dns.available ? `<p class="muted" style="font-size:12.5px;margin:0">Termux içindeki programların (cloudflared, adres bulma) kullandığı DNS. Tünel "lookup" hatası verirse birini seç.</p>
        <div class="chips">${Object.entries(I.dns.presets).map(([k, v]) => `<button class="chip" data-act="dnsSet" data-k="${k}" aria-pressed="${I.dns.preset === k}">${esc(v.name)}</button>`).join('')}</div>`
        : '<p class="muted" style="font-size:12.5px;margin:0">DNS ayarı yalnızca Termux\'ta çalışırken değiştirilebilir.</p>'}
      <div class="sec-h" style="margin:14px 0 0"><h4>AI fotoğraf incelemesi</h4><span class="pill ${I.ai.enabled && I.ai.key_set ? 'ok' : ''}">${I.ai.enabled ? (I.ai.key_set ? 'Açık' : 'Anahtar yok') : 'Kapalı'}</span></div>
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
function aiBlock(ph, t, canEdit) {
  const r = ph.ai;
  if (S.aiBusy === ph.id) return '<section class="ai-box"><div class="muted">AI fotoğrafı inceliyor… (birkaç saniye sürebilir)</div></section>';
  if (!r) {
    if (ph.mime === 'image/svg+xml') return '<section class="ai-box"><span class="muted" style="font-size:12.5px">Örnek çizim fotoğraflar AI ile incelenemez.</span></section>';
    return `<section class="ai-box row" style="justify-content:space-between"><span class="muted" style="font-size:13px">Bu fotoğraf için AI gözlemi yok.</span><button class="btn" data-act="aiRun">AI gözlemi al</button></section>`;
  }
  return `<section class="ai-box"><div class="sec-h" style="margin:0 0 6px"><h4>AI gözlemi · fotoğraf kalitesi ${AI_QUALITY[r.photo_quality] || r.photo_quality}</h4>${isMgr() ? '<button class="linkbtn" data-act="aiRun" data-force="1">Yeniden incele</button>' : ''}</div>
    <p style="margin:0 0 8px">${esc(r.summary)}</p>
    ${r.observations.length ? `<ul class="ai-obs">${r.observations.map(o => `<li><span class="pill ${AI_LEVEL[o.level][1]}">${AI_LEVEL[o.level][0]}</span><span><b>${esc(o.title)}</b>${o.detail ? ` <span class="muted">${esc(o.detail)}</span>` : ''}</span></li>`).join('')}</ul>` : ''}
    ${r.limitations?.length ? `<div class="muted" style="font-size:12px;margin-top:6px">Sınırlar: ${r.limitations.map(esc).join(' · ')}</div>` : ''}
    <div class="muted" style="font-size:11.5px;margin-top:6px">Bu bir karar değil; son söz incelemeyi yapan kişide. ${esc(r.model || '')} · ${fmtTime(r.at)}</div></section>`;
}

/* ---------- iş ayrıntısı ---------- */
function renderSheet() {
  const box = $('#sheet');
  const t = S.open && task(S.open);
  if (!t || !S.me) { box.hidden = true; box.innerHTML = ''; document.body.style.overflow = ''; return; }
  if (!S.active || !t.photos.some(p => p.pid === S.active)) S.active = t.photos[0]?.pid ?? null;
  const ph = S.photos[S.active];
  const link = t.photos.find(p => p.pid === S.active);
  const before = firstOf(t, 'before'), after = lastOf(t, 'after');
  const p = proj(t.project_id);
  const pool = isPool(t) && !isMgr();
  const canEdit = mine(t);
  const anns = ph ? ph.annotations : [];
  const prevScroll = box.querySelector('.sheet')?.scrollTop ?? 0;
  box.hidden = false;
  document.body.style.overflow = 'hidden';
  box.innerHTML = `<div class="sheet-wrap" data-act="closeBg"><div class="sheet" role="dialog" aria-modal="true" aria-label="${esc(t.no_label)} ${esc(t.title)}">
    <div class="sheet-top"><span class="wo">${esc(t.no_label)}</span><label class="vh" for="t-title">Başlık</label>
      <input id="t-title" class="title-in" value="${esc(t.untitled ? '' : t.title)}" placeholder="${t.untitled ? 'Başlık yaz' : ''}" data-change="title" ${canEdit ? '' : 'disabled'}>
      <button class="x" data-act="close" aria-label="Kapat">×</button></div>
    <div class="sheet-body">
      ${pool ? `<div class="note row" style="justify-content:space-between"><span><b>Havuzdaki iş.</b> Kimseye atanmamış; üstlenirsen sana atanır.</span><button class="btn primary" data-act="claim" data-id="${t.id}">Üstlen</button></div>` : ''}
      ${t.untitled && canEdit ? '<div class="note"><b>Bu iş başlıksız açıldı.</b> Yukarıya ne yapılacağını yaz.</div>' : ''}
      ${t.rejected_reason ? `<div class="note" style="border-color:var(--danger)"><b>Geri gönderildi:</b> ${esc(t.rejected_reason)}</div>` : ''}
      <div class="meta-grid">
        <label class="field"><span>Durum</span><select id="t-status" class="select" data-change="status" ${canEdit ? '' : 'disabled'}>${STATUSES.map(s => `<option value="${s.id}"${t.status === s.id ? ' selected' : ''}${!isMgr() && s.id === 'done' ? ' disabled' : ''}>${s.name}</option>`).join('')}</select></label>
        <label class="field"><span>Atanan</span><select id="t-assignee" class="select" data-change="assignee" ${isMgr() ? '' : 'disabled'}><option value="">Havuz (atanmamış)</option>${S.users.map(u => `<option value="${u.id}"${t.assignee_id === u.id ? ' selected' : ''}>${esc(u.name)}</option>`).join('')}</select></label>
        <label class="field"><span>Son tarih</span><input id="t-due" type="date" class="input" value="${t.due}" data-change="due" ${canEdit ? '' : 'disabled'}></label>
        <label class="field"><span>Öncelik</span><select id="t-prio" class="select" data-change="priority" ${canEdit ? '' : 'disabled'}><option value="normal"${t.priority === 'normal' ? ' selected' : ''}>Normal</option><option value="high"${t.priority === 'high' ? ' selected' : ''}>Acil</option></select></label>
      </div>
      <div class="addr">${esc(p?.name)} · ${esc(p?.address)}${p?.contact ? ` · ${esc(p.contact)}` : ''}</div>

      <section class="viewer">
        ${ph ? `<div class="stage"><div class="shot ${S.annot ? 'annot' : ''}" data-act="shot">
          <img src="${full(ph.id)}" alt="${esc(TYPES[link.type])} fotoğrafı" draggable="false">
          ${anns.map((a, i) => `<span class="mk" style="left:${a.x}%;top:${a.y}%" title="${esc(a.text)}">${i + 1}</span>`).join('')}
          ${S.draftPin ? `<span class="mk new" style="left:${S.draftPin.x}%;top:${S.draftPin.y}%">${anns.length + 1}</span>` : ''}
        </div></div>
        <div class="viewer-bar"><div class="row"><span class="tag ${link.type}" style="position:static">${TYPES[link.type]}</span><span class="mono muted">${fmtTime(ph.taken_at)} · ${fmtGps(ph)}</span>${ph.lat != null ? `<span class="gps-src">${GPS_SRC[ph.gps_source]}${ph.gps_accuracy ? ` ±${Math.round(ph.gps_accuracy)} m` : ''}</span>` : ''}${photoDistChip(ph, p)}</div>
          <div class="row">${canEdit ? `<button class="btn ${S.annot ? 'primary' : ''}" data-act="annot" aria-pressed="${S.annot}">${S.annot ? 'İşaretlemeyi bitir' : 'İşaretle'}</button><button class="btn bad" data-act="unlink">Kaldır</button>` : ''}</div></div>
        ${ph.address ? `<div class="addr">Çekildiği yer: ${esc(ph.address)}</div>` : ''}
        ${S.annot && !S.draftPin ? '<div class="note">Fotoğrafta sorunlu noktaya dokun.</div>' : ''}
        ${S.draftPin ? `<div class="ann-form"><label class="vh" for="ann-text">İşaret notu</label><input id="ann-text" class="input" placeholder="İşaret ${anns.length + 1}: ne var burada?" autocomplete="off" data-keep><button class="btn primary" data-act="annSave">Kaydet</button><button class="btn" data-act="annCancel">Vazgeç</button></div>` : ''}
        ${anns.length ? `<ol class="anns">${anns.map((a, i) => `<li><span class="n">${i + 1}</span><span>${esc(a.text)} <span class="muted">· ${esc(nameOf(a.by))}</span>${isMgr() || a.by === S.me.id ? ` <button class="linkbtn" data-act="annDel" data-aid="${a.id}">sil</button>` : ''}</span></li>`).join('')}</ol>` : ''}` : '<div class="empty">Bu işte fotoğraf yok. Aşağıdan ekle.</div>'}
        ${ph && S.settings.ai_enabled ? aiBlock(ph, t, canEdit) : ''}
        <div class="thumbs">
          ${t.photos.map(x => `<button data-act="thumb" data-pid="${x.pid}" aria-current="${x.pid === S.active}" aria-label="${TYPES[x.type]} fotoğrafı"><img src="${thumb(x.pid)}" alt=""><span class="tag ${x.type}">${TYPES[x.type]}</span></button>`).join('')}
          ${canEdit ? '<label class="add-photo" for="add-file">+ Fotoğraf<br>ekle</label>' : ''}
        </div>
        ${canEdit ? `<input id="add-file" class="vh" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" multiple data-change="addFile">
        <div class="row"><label class="field" style="grid-auto-flow:column;align-items:center;gap:8px"><span>Eklenecek tür</span><select id="add-type" class="select" data-change="addType">${Object.entries(TYPES).map(([k, l]) => `<option value="${k}"${S.addType === k ? ' selected' : ''}>${l}</option>`).join('')}</select></label></div>` : ''}
      </section>

      ${before && after ? `<section class="panel"><div class="sec-h"><h4>Önce / sonra</h4><span class="mono muted">${Math.max(0, daysBetween(dayStr(new Date(S.photos[before.pid]?.taken_at)), dayStr(new Date(S.photos[after.pid]?.taken_at))))} gün arayla</span></div>
        <div class="compare" id="cmp-box"><img src="${full(before.pid)}" alt="Önce"><div class="after" id="cmp-after" style="clip-path:inset(0 0 0 50%)"><img src="${full(after.pid)}" alt="Sonra"></div>
          <span class="bar" id="cmp-bar" style="left:50%"></span><span class="knob" id="cmp-knob" style="left:50%">↔</span><span class="lbl" style="left:10px">ÖNCE</span><span class="lbl" style="right:10px">SONRA</span>
          <label class="vh" for="cmp">Karşılaştırma kaydırıcısı</label><input type="range" id="cmp" min="0" max="100" value="50" data-input="cmp"></div></section>` : ''}

      ${t.status === 'review' ? (isMgr() ? `<section class="approve"><b>Onayın bekleniyor</b><span class="muted" style="font-size:13px">Önce/sonra fotoğraflarını, kontrol listesini ve imzayı incele.</span>
        <div class="row"><button class="btn good" data-act="approve">Onayla ve tamamla</button><label class="vh" for="rej">Geri gönderme nedeni</label><input id="rej" class="input" placeholder="Geri gönderme nedeni" autocomplete="off" data-keep><button class="btn bad" data-act="reject">Geri gönder</button></div></section>`
        : '<div class="note"><b>Yönetici onayı bekleniyor.</b> Saha rolü işi tamamlayamaz.</div>') : ''}

      <div class="two">
        <section class="panel"><div class="sec-h"><h4>Kontrol listesi · ${t.checklist.filter(c => c.done).length}/${t.checklist.length}</h4></div>
          ${t.checklist.length ? `<ul class="check">${t.checklist.map(c => `<li><input type="checkbox" id="ck-${c.id}" data-change="check" data-cid="${c.id}" ${c.done ? 'checked' : ''} ${canEdit ? '' : 'disabled'}><label for="ck-${c.id}">${esc(c.text)}${c.require_proof ? '<span class="req">foto zorunlu</span>' : ''}</label>
            <span class="row" style="gap:6px">${c.proof ? `<img class="proof" src="${thumb(c.proof)}" alt="Kanıt fotoğrafı" data-act="thumb" data-pid="${c.proof}">` : `${c.done ? '<span class="noproof">Kanıtsız</span>' : ''}${ph && canEdit ? `<button class="linkbtn" data-act="proof" data-cid="${c.id}">Seçili fotoğraf kanıt</button>` : ''}`}${canEdit ? `<button class="linkbtn" data-act="ckDel" data-cid="${c.id}" aria-label="Maddeyi sil">×</button>` : ''}</span></li>`).join('')}</ul>` : '<div class="empty">Kontrol listesi yok.</div>'}
          ${canEdit ? `<div class="compose" style="margin-top:10px"><label class="vh" for="ck-new">Yeni madde</label><input id="ck-new" class="input" placeholder="Madde ekle" autocomplete="off" data-keep><button class="btn" data-act="ckAdd">Ekle</button></div>
          <label class="row" style="font-size:12.5px;margin-top:6px;gap:6px"><input type="checkbox" id="ck-req"> Fotoğraf kanıtı zorunlu olsun</label>` : ''}
        </section>
        <section class="panel"><div class="sec-h"><h4>Yorumlar · ${t.comments.length}</h4></div>
          <div class="comments">${t.comments.map(c => `<div class="cmt">${av(c.by)}<div><b>${esc(nameOf(c.by))}</b><time>${fmtTime(c.at)}</time><p>${esc(c.text)}</p></div></div>`).join('') || '<div class="muted" style="font-size:13px">Henüz yorum yok.</div>'}</div>
          ${pool ? '' : `<div class="compose" style="margin-top:10px"><label class="vh" for="c-text">Yorum</label><input id="c-text" class="input" placeholder="Yorum yaz" autocomplete="off" data-keep><button class="btn primary" data-act="comment">Gönder</button></div>`}
        </section>
      </div>

      <section class="panel sig"><div class="sec-h"><h4>Müşteri imzası</h4>${t.signature ? `<span class="mono muted">${esc(t.signature.signer)} · ${fmtTime(t.signature.at)}</span>` : ''}</div>
        ${t.signature ? `<img src="/files/signature/${t.id}?v=${encodeURIComponent(t.signature.at)}" alt="Müşteri imzası">` : ''}
        ${canEdit ? `<canvas id="sig-pad" width="800" height="240" aria-label="İmza alanı"></canvas>
        <div class="row"><label class="vh" for="sig-name">İmzalayan</label><input id="sig-name" class="input" style="flex:1 1 180px" placeholder="İmzalayanın adı" value="${esc(t.signature?.signer ?? '')}" data-keep>
          <button class="btn" data-act="sigClear">Temizle</button><button class="btn primary" data-act="sigSave">${t.signature ? 'Yeniden imzalat' : 'İmzayı kaydet'}</button></div>` : (t.signature ? '' : '<div class="muted" style="font-size:13px">İmza alınmadı.</div>')}
      </section>

      <section class="panel"><div class="sec-h"><h4>Etkinlik geçmişi</h4>${isMgr() ? '<button class="linkbtn" data-act="delTask" style="color:var(--danger)">İşi sil</button>' : ''}</div>
        <ul class="log">${[...t.activity].reverse().map(a => `<li><span class="mono">${fmtTime(a.at)}</span><span><b style="font-weight:600">${esc(nameOf(a.by))}</b> · ${esc(a.text)}</span></li>`).join('')}</ul></section>
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
  const v = { board: viewBoard, gallery: viewGallery, camera: viewCamera, report: viewReport, profile: viewProfile }[S.view] || viewBoard;
  $('#main').innerHTML = `<div class="wrap">${v()}</div>`;
}
function measureChrome() {
  const r = document.documentElement.style;
  r.setProperty('--hdr-h', ($('.top')?.offsetHeight || 57) + 'px');
  r.setProperty('--dock-h', ($('.dock')?.offsetHeight || 64) + 'px');
}
function render() {
  if (!S.me) return;
  const kept = keepInputs();
  renderHeader(); renderDock(); measureChrome(); renderMain();
  if (!(S.open && sigDirty && document.getElementById('sig-pad'))) renderSheet();
  restoreInputs(kept);
}
function applyTheme() { if (S.theme === 'system') delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = S.theme; }

/* ---------- eylemler ---------- */
async function moveTask(id, to) {
  const t = task(id); if (!t || t.status === to) return;
  if (!isMgr() && to === 'done') { toast('<b>Tamamlandı</b> durumuna yalnızca yönetici taşıyabilir. İşi “Onay bekliyor”a taşı.'); return; }
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
  go: a => { S.view = a.dataset.view; S.open = null; if (S.view !== 'map') { S.mapMode = null; S.pickPoint = null; } render(); window.scrollTo(0, 0); if (S.view === 'camera') warmCamGps(); if (S.view === 'profile' && isMgr()) loadIntegrations(); },
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
  theme: a => { S.theme = a.dataset.theme; store.set('ft-theme', S.theme); applyTheme(); render(); },
  print: () => window.print(),
  hereGps: async () => { const g = await deviceGps(); if (!g) { toast('Konum alınamadı. Konum iznini kontrol et.'); return; } $('#np-lat').value = g.lat; $('#np-lng').value = g.lng; }
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
    const r = await run(() => api('POST', '/api/projects', { name: v('mc-name') || client, short: (v('mc-name') || client).split('·')[0].trim(), client, contact: v('mc-contact'),
      address: addrEl.value.trim(), address_source: fromGeo ? 'geocode' : 'manual', lat: pk.lat, lng: pk.lng, location_source: S.here && distM(S.here.lat, S.here.lng, pk.lat, pk.lng) < 5 ? 'device' : 'map' }), 'Müşteri eklendi');
    if (r) { S.mapMode = null; S.pickPoint = null; removeTemp(); S.mapPick = r.id; S.mapDetail = true; ['mc-client', 'mc-name', 'mc-contact'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; }); updateMapLayers(); renderMapPanel(); }
  },
  password: () => run(() => api('PATCH', '/api/me/password', { old: $('#pw-old').value, new: $('#pw-new').value }), 'Parola değiştirildi'),
  user: async f => { const r = await run(() => api('POST', '/api/users', { name: $('#nu-name').value, username: $('#nu-user').value, password: $('#nu-pass').value, role: $('#nu-role').value }), 'Kişi eklendi'); if (r) ['nu-name', 'nu-user', 'nu-pass'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; }); },
  project: async () => {
    const v = id => document.getElementById(id).value.trim();
    const r = await run(() => api('POST', '/api/projects', { name: v('np-name'), short: v('np-short'), client: v('np-client'), contact: v('np-contact'), address: v('np-address'), lat: v('np-lat').replace(',', '.'), lng: v('np-lng').replace(',', '.') }), 'Proje eklendi');
    if (r) document.querySelectorAll('[data-form="project"] input').forEach(el => { el.value = ''; });
  }
};

/* ---------- olay dinleyiciler ---------- */
document.addEventListener('click', e => {
  if (swallowClick) { swallowClick = false; e.preventDefault(); return; }
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
  if (k === 'search') {
    S.q = e.target.value; clearTimeout(searchTimer);
    searchTimer = setTimeout(async () => {
      if (S.q.trim().length < 2) { S.searchIds = null; render(); return; }
      try { const r = await api('GET', '/api/search?q=' + encodeURIComponent(S.q.trim())); S.searchIds = new Set(r.ids); render(); } catch (err) { fail(err); }
    }, 300);
  }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && S.open) { acts.close(); return; }
  if (e.key !== 'Enter') return;
  const el = e.target;
  if (el.id === 'c-text') { e.preventDefault(); acts.comment(); }
  else if (el.id === 'ann-text') { e.preventDefault(); acts.annSave(); }
  else if (el.id === 'ck-new') { e.preventDefault(); acts.ckAdd(); }
  else if (el.id === 't-title') { el.blur(); }
  else if (el.matches?.('.card, .pin')) { e.preventDefault(); el.click(); }
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
