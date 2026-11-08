#!/usr/bin/env python3
"""FotoTakip proje haritasını koddan üretir: docs/proje-haritasi.html

Kullanım (depo kökünde):
    python3 tools/proje-haritasi/uret.py           # haritayı yeniden üret
    python3 tools/proje-haritasi/uret.py --check   # harita güncel mi? (CI bunu çalıştırır)

Otomatik çıkarılanlar: API uç noktaları ve okuduğu/yazdığı tablolar (fototakip/api.py),
arayüzün çağırdığı uç noktalar (web/app.js), tablolar (fototakip/db.py).
Elle tutulanlar (bu dosyada): çağrıların hangi ekrana ait olduğu (CTX), açıklamalar ve akışlar.
Yeni bir arayüz çağrısı CTX'te yoksa uyarı verir.
Yalnızca Python standart kütüphanesi kullanılır; Termux'ta da çalışır.
"""
import ast
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "docs" / "proje-haritasi.html"
SOURCES = ["fototakip/api.py", "fototakip/db.py", "web/app.js", "web/sw.js", "fototakip/geo.py",
           "fototakip/images.py", "fototakip/auth.py", "fototakip/server.py", "fototakip/__main__.py",
           "scripts/install.sh", "scripts/install-termux.sh", "scripts/github-upload.sh", "scripts/backup.sh", "scripts/sifirla.sh",
           ".github/workflows/ci.yml", "tests/test_api.py", "tools/proje-haritasi/uret.py", "tools/proje-haritasi/sablon.html"]


def extract(R):
    api_src = (R/'fototakip/api.py').read_text()
    tree = ast.parse(api_src)
    TABLE_RE = re.compile(r'\b(INSERT\s+(?:OR\s+\w+\s+)?INTO|UPDATE|DELETE\s+FROM|FROM|JOIN)\s+([a-z_]+)', re.I)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    def direct(fn):
        reads, writes, calls, mods = set(), set(), set(), set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for kw, t in TABLE_RE.findall(node.value):
                    if t in ('settings',) or t.isidentifier():
                        (writes if kw.upper().split()[0] in ('INSERT', 'UPDATE', 'DELETE') else reads).add(t)
            if isinstance(node, ast.JoinedStr):
                s = ''.join(v.value for v in node.values if isinstance(v, ast.Constant))
                for kw, t in TABLE_RE.findall(s):
                    (writes if kw.upper().split()[0] in ('INSERT', 'UPDATE', 'DELETE') else reads).add(t)
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name) and f.id in funcs: calls.add(f.id)
                if isinstance(f, ast.Attribute):
                    base = f.value
                    name = ast.unparse(f)
                    if name.startswith(('auth.', 'images.', 'geo.', 'db.', 'ai_review.', 'secrets.', 'tunnel.')): mods.add(name)
                    if name in ('req.geo.enqueue', 'req.geo.reverse') or name.startswith('req.tunnel.'): mods.add(name)
                    if name == 'req.publish': mods.add('publish')
                    if name == 'req.file': mods.add('file')
        return reads, writes, calls, mods
    D = {n: direct(f) for n, f in funcs.items()}
    def closure(n, seen=None):
        seen = seen or set()
        r, w, c, m = map(set, D[n])
        for x in list(c):
            if x in seen: continue
            seen.add(x)
            r2, w2, m2 = closure(x, seen)
            r |= r2; w |= w2; m |= m2
        # db.setting/set_setting/next_no touch settings table
        if any(x in m for x in ('db.setting',)): r.add('settings')
        if any(x in m for x in ('db.set_setting', 'db.next_task_no')): w.add('settings')
        if 'auth.create_session' in m or 'auth.delete_session' in m: w.add('sessions')
        if 'auth.user_for_token' in m: r.add('sessions')
        return r, w, m
    routes = []
    for n, f in funcs.items():
        for d in f.decorator_list:
            if isinstance(d, ast.Call) and getattr(d.func, 'id', '') == 'route':
                method, pattern = d.args[0].value, d.args[1].value
                auth_req = not any(k.arg == 'auth_required' and k.value.value is False for k in d.keywords)
                r, w, m = closure(n)
                r -= w
                routes.append(dict(fn=n, method=method, pattern=pattern, line=f.lineno, auth=auth_req,
                                   reads=sorted(r), writes=sorted(w), mods=sorted(m), doc=ast.get_docstring(f) or ''))
    # app.js api calls
    js = (R/'web/app.js').read_text()
    calls = []
    ctx_re = re.compile(r'^\s{0,4}(?:async\s+)?(?:function\s+([A-Za-z0-9_]+)|([A-Za-z0-9_]+):\s*(?:async\s*)?\(?[a-z, ]*\)?\s*=>)', re.M)
    ctxs = [(m.start(), m.group(1) or m.group(2)) for m in ctx_re.finditer(js)]
    for m in re.finditer(r"api\('(GET|POST|PATCH|DELETE)',\s*([`'])(.*?)\2", js):
        pos = m.start(); name = None
        for p, nm in ctxs:
            if p <= pos: name = nm
            else: break
        path = re.sub(r'\$\{[^}]+\}', '{x}', m.group(3)).split('?')[0]
        line = js.count('\n', 0, pos) + 1
        calls.append(dict(method=m.group(1), path=path, ctx=name, line=line))
    # also uploadGroup '/api/photos?' + qp
    schema = (R/'fototakip/db.py').read_text()
    tables = re.findall(r'CREATE TABLE ([a-z_]+)', schema)
    return dict(routes=routes, calls=calls, tables=tables)



def build(R, raw):
    TABLES = set(raw['tables'])
    def loc(p): return sum(1 for _ in open(R / p, encoding='utf-8'))
    nodes, edges = [], []
    def N(id, layer, kind, label, desc, file=None, line=None, **kw):
        nodes.append(dict(id=id, layer=layer, kind=kind, label=label, desc=desc, file=file, line=line, **kw))
    def E(a, b, kind, label=''):
        edges.append(dict(s=a, t=b, kind=kind, label=label))

    # katman 0: cihaz ve dış servisler
    N('ext.camera', 0, 'device', 'Telefon kamerası', 'Tarayıcının dosya seçicisi kamerayı açar (capture="environment"). Fotoğraf EXIF ile gelir; Android bazen konumu siler.')
    N('ext.gps', 0, 'device', 'Telefon GPS', 'navigator.geolocation. Yalnızca güvenli bağlantıda (localhost veya HTTPS) çalışır.')
    N('ext.osm', 0, 'external', 'OpenStreetMap karoları', 'tile.openstreetmap.org. Harita görüntüsü; bakılan karolar service worker önbelleğinde tutulur.')
    N('ext.nominatim', 0, 'external', 'Nominatim', 'OpenStreetMap ters geocoding: koordinat → adres. Saniyede en fazla 1 istek, sonuçlar geocode_cache tablosunda.')
    N('ext.gmaps', 0, 'external', 'Google Haritalar', 'Yalnızca "Yol tarifi" bağlantısı; uygulama Google\'a veri göndermez.')
    N('ext.cloudflare', 0, 'external', 'Cloudflare tüneli', 'fototakip-tunel komutu: diğer telefonlar için geçici HTTPS adresi.')
    N('ext.github', 0, 'external', 'GitHub', 'FotoTakip deposu. Kurulum buradan indirir, yükleme betiği buraya gönderir, CI burada çalışır.')
    N('ext.termux', 0, 'device', 'Termux + Android', 'Sunucunun çalıştığı ortam. pkg ile python, python-pillow, git, cloudflared kurulur; DNS ayarı $PREFIX/etc/resolv.conf.')
    N('ext.openai', 0, 'external', 'OpenAI', 'İsteğe bağlı AI fotoğraf incelemesi. Fotoğraf konumsuz gönderilir; karar vermez, gözlem notu üretir.')

    # katman 1: arayüz
    UI = {
     'ui.login': ('Giriş ekranı', 'Kullanıcı adı ve parola. Hiç hesap yoksa ilk kurulum formu: kurulum kodu + ilk yönetici.', 'showLogin'),
     'ui.shell': ('Uygulama kabuğu', 'Tüm veriyi /api/bootstrap ile yükler, canlı olayları dinler, değişince yeniden yükler.', 'reload'),
     'ui.board': ('Pano · liste · takvim', 'Kanban sürükle-bırak, mobilde kaydırma, arama, havuz ve Üstlen.', 'viewBoard'),
     'ui.sheet': ('İş ayrıntısı', 'Fotoğraf görüntüleyici, işaretleme, önce/sonra, kontrol listesi, yorum, imza, onay.', 'renderSheet'),
     'ui.camera': ('Kamera', 'Fotoğraftan iş açar; en yakın müşteriyi konumdan seçer.', 'viewCamera'),
     'ui.queue': ('Çevrimdışı kuyruk', 'IndexedDB. Bağlantı yokken fotoğrafları tutar, gelince sırayla yükler.', 'flushQueue'),
     'ui.gallery': ('Galeri', 'Fotoğraflar türe göre süzülür.', 'viewGallery'),
     'ui.map': ('Harita', 'Leaflet + OSM: müşteri pinleri, mavi nokta, fotoğraf katmanı, haritadan müşteri ekleme.', 'renderMapView'),
     'ui.report': ('Rapor', 'Önce/sonra çiftleri ve imzalarla müşteri teslim belgesi.', 'viewReport'),
     'ui.profile': ('Profil ve ayarlar', 'Ekip, yeni proje, otomasyon, yedek, parola, çevrimdışı test modu.', 'viewProfile'),
     'ui.sw': ('Service worker', 'sw.js: uygulama kabuğu, son veri ve harita karoları önbelleği.', None),
    }
    js = (R/'web/app.js').read_text().split('\n')
    def jsline(name):
        if not name: return None
        for i, l in enumerate(js, 1):
            if re.search(rf'\bfunction {name}\(|\b{name}:\s', l): return i
    for k, (lab, d, fn) in UI.items():
        N(k, 1, 'ui', lab, d, 'web/sw.js' if k == 'ui.sw' else 'web/app.js', jsline(fn) if k != 'ui.sw' else 1)

    # katman 2: API
    def rid(m, p): return 'api.' + m + ' ' + re.sub(r'\(\?P<(\w+)>[^)]*\)', r'{\1}', p)
    route_by = {}
    for r in raw['routes']:
        pretty = re.sub(r'\(\?P<(\w+)>[^)]*\)', r'{\1}', r['pattern'])
        i = rid(r['method'], r['pattern'])
        route_by[(r['method'], re.sub(r'\{\w+\}', '{x}', pretty))] = i
        N(i, 2, 'api', f"{r['method']} {pretty}", r['doc'].split('\n')[0] if r['doc'] else '', 'fototakip/api.py', r['line'], method=r['method'], fn=r['fn'],
          auth=r['auth'])
    N('api.events', 2, 'api', 'GET /api/events', 'Canlı olay akışı (Server-Sent Events). Her yazma işlemi buradan tüm açık ekranlara duyurulur.', 'fototakip/server.py', None, method='SSE')

    # katman 3: sunucu modülleri
    MOD = {
     'mod.main': ('__main__.py', 'Komut satırı: port, veri klasörü, adres servisi. Boş veritabanında tek kullanımlık kurulum kodu üretir.', 'fototakip/__main__.py'),
     'mod.server': ('server.py', 'HTTP yönlendirici, statik dosyalar, çerez oturumu, SSE olay yayını.', 'fototakip/server.py'),
     'mod.auth': ('auth.py', 'PBKDF2 parola özeti, 30 günlük oturumlar.', 'fototakip/auth.py'),
     'mod.images': ('images.py', 'Tür doğrulama, EXIF okuma, döndürme, 2560 px küçültme, EXIF\'siz kayıt.', 'fototakip/images.py'),
     'mod.geo': ('geo.py', 'Uzaklık hesabı ve arka plan adres işçisi (Nominatim, önbellek, 1 istek/sn).', 'fototakip/geo.py'),
     'mod.db': ('db.py', 'SQLite bağlantısı, şema, sürüm göçleri, yazma kilidi.', 'fototakip/db.py'),
     'mod.ai': ('ai_review.py', 'OpenAI ile fotoğraf gözlemi; model çıktısını dar bir şemaya indirir, EXIF siler.', 'fototakip/ai_review.py'),
     'mod.tunnel': ('tunnel.py', 'Ücretsiz Cloudflare tüneli (hızlı / adlandırılmış) ve Termux DNS ayarı.', 'fototakip/tunnel.py'),
     'mod.secrets': ('secrets.py', 'OpenAI anahtarı ve tünel token\'ı: 0600 izinli ayrı dosya, istemciye gitmez.', 'fototakip/secrets.py'),
    }
    for k, (lab, d, f) in MOD.items(): N(k, 3, 'module', lab, d, f, 1, loc=loc(f))

    # katman 4: veri
    TDESC = {'users': 'Kişiler ve roller', 'sessions': 'Oturum anahtarları', 'projects': 'Müşteriler / sahalar, konum ve adres kaynağı', 'tasks': 'İşler, durum, sürüm', 'photos': 'Fotoğraf kaydı: konum, doğruluk, adres', 'task_photos': 'İş ↔ fotoğraf, tür', 'annotations': 'Fotoğraf üzerindeki işaretler', 'comments': 'Yorumlar', 'checklist': 'Kontrol maddeleri, kanıt fotoğrafı', 'activity': 'Etkinlik geçmişi', 'signatures': 'Müşteri imzaları', 'settings': 'Otomasyon, sayaç, AI ve tünel ayarları', 'geocode_cache': 'Adres önbelleği (~11 m hücre)', 'ai_reviews': 'AI gözlemleri (fotoğraf başına önbellek)'}
    dbpy = (R/'fototakip/db.py').read_text().split('\n')
    for t in raw['tables']:
        ln = next((i for i, l in enumerate(dbpy, 1) if f'CREATE TABLE {t}' in l), None)
        N('tbl.' + t, 4, 'table', t, TDESC.get(t, ''), 'fototakip/db.py', ln)
    N('data.db', 4, 'store', 'fototakip.db', 'Tek SQLite dosyası (WAL). Tüm tablolar burada.', None, None)
    N('data.photos', 4, 'store', 'photos/ klasörü', 'Fotoğraf dosyaları ve küçük resimler.', None, None)
    N('data.sigs', 4, 'store', 'signatures/ klasörü', 'İmza PNG dosyaları.', None, None)
    N('data.secrets', 4, 'store', 'secrets.json', 'Gizli ayarlar (0600). Yedeğe girmez.', None, None)

    # katman 5: kurulum ve işletim
    OPS = {
     'ops.install': ('install.sh', 'Tek satırlık kurulum: GitHub\'dan indirir veya günceller.', 'scripts/install.sh'),
     'ops.termux': ('install-termux.sh', 'Paketleri kurar, fototakip ve fototakip-tunel komutlarını, Termux:Boot başlatıcısını yazar.', 'scripts/install-termux.sh'),
     'ops.upload': ('github-upload.sh', 'Yüklü mü kontrol eder, gerekiyorsa yükler ve doğrular.', 'scripts/github-upload.sh'),
     'ops.backup': ('backup.sh', 'Veritabanı + fotoğrafları tarihli zip\'e yedekler.', 'scripts/backup.sh'),
     'ops.reset': ('sifirla.sh', 'Durdurur, yedekler, veriyi ve gizli ayarları siler, DNS\'i geri alır.', 'scripts/sifirla.sh'),
     'ops.ci': ('ci.yml', 'GitHub Actions: Python 3.11-3.13, Pillow\'lu/Pillow\'suz testler.', '.github/workflows/ci.yml'),
     'ops.tests': ('tests/', 'API, konum ve göç testleri.', 'tests/test_api.py'),
    }
    for k, (lab, d, f) in OPS.items(): N(k, 5, 'script', lab, d, f, 1, loc=loc(f))

    ids = {n['id'] for n in nodes}
    # arayüz → API (koddan)
    CTX = {'reload': 'ui.shell', 'uploadGroup': 'ui.camera', 'doLogin': 'ui.login', 'doSetup': 'ui.login', 'boot': 'ui.login', 'setPickPoint': 'ui.map',
           'moveTask': 'ui.board', 'step': 'ui.sheet', 'logout': 'ui.profile', 'claim': 'ui.sheet', 'annSave': 'ui.sheet', 'annDel': 'ui.sheet',
           'unlink': 'ui.sheet', 'comment': 'ui.sheet', 'ckAdd': 'ui.sheet', 'ckDel': 'ui.sheet', 'proof': 'ui.sheet', 'approve': 'ui.sheet',
           'reject': 'ui.sheet', 'sigSave': 'ui.sheet', 'delTask': 'ui.sheet', 'newTask': 'ui.board', 'pickSaveMove': 'ui.map', 'applySug': 'ui.map',
           'dismissSug': 'ui.map', 'check': 'ui.sheet', 'autoRule': 'ui.profile', 'mapCustomer': 'ui.map', 'password': 'ui.profile', 'user': 'ui.profile',
           'project': 'ui.profile', 'aiRun': 'ui.sheet', 'loadIntegrations': 'ui.profile', 'tunStart': 'ui.profile', 'tunStop': 'ui.profile',
           'saveInteg': 'ui.profile', 'resetPw': 'ui.profile'}
    seen = set()
    unmapped = []
    for c in raw['calls']:
        ui = CTX.get(c['ctx'])
        if not ui and c['path'] != '/api/search': unmapped.append(f"app.js:{c['line']} {c['method']} {c['path']} (bağlam: {c['ctx']})")
        if c['path'] == '/api/search': ui = 'ui.board'
        if c['path'] == '/api/tasks/{x}' and c['ctx'] == 'step': ui = 'ui.sheet'  # patchTask
        a = route_by.get((c['method'], c['path']))
        if ui and a and (ui, a) not in seen:
            seen.add((ui, a)); E(ui, a, 'call', f"app.js:{c['line']}")
    # fotoğraf yükleyen diğer yerler
    for ui in ('ui.sheet', 'ui.queue'):
        E(ui, route_by[('POST', '/api/photos')], 'call', 'uploadGroup')
    f_files, f_sig = route_by[('GET', '/files/{x}')], route_by[('GET', '/files/signature/{x}')]
    for ui in ('ui.board', 'ui.gallery', 'ui.sheet', 'ui.map', 'ui.report'): E(ui, f_files, 'call', '<img src>')
    for ui in ('ui.sheet', 'ui.report'): E(ui, f_sig, 'call', '<img src>')
    E('ui.profile', route_by[('GET', '/api/backup')], 'call', 'Yedek indir bağlantısı')
    E('ui.shell', 'api.events', 'call', 'EventSource')
    E('api.events', 'ui.shell', 'event', 'değişiklik → yeniden yükle')
    E('ui.camera', 'ui.queue', 'call', 'çevrimdışıyken')
    E('ui.sw', f_files, 'call', 'önbellek'); E('ui.sw', route_by[('GET', '/api/bootstrap')], 'call', 'son veri önbelleği')
    # API → tablolar, modüller
    for r in raw['routes']:
        i = rid(r['method'], r['pattern'])
        for t in r['reads']:
            if t in TABLES: E(i, 'tbl.' + t, 'read')
        for t in r['writes']:
            if t in TABLES: E(i, 'tbl.' + t, 'write')
        m = set(r['mods'])
        if any(x.startswith('auth.') for x in m): E(i, 'mod.auth', 'use')
        if 'images.store' in m or 'images.sniff' in m: E(i, 'mod.images', 'use')
        if 'req.geo.enqueue' in m: E(i, 'mod.geo', 'use', 'adres kuyruğuna ekle')
        if 'req.geo.reverse' in m: E(i, 'mod.geo', 'use', 'adres bul')
        if any(x.startswith('ai_review.') for x in m): E(i, 'mod.ai', 'use', 'gözlem iste')
        if any(x.startswith('secrets.') for x in m): E(i, 'mod.secrets', 'use')
        if any(x.startswith(('tunnel.', 'req.tunnel.')) for x in m): E(i, 'mod.tunnel', 'use')
        if 'geo.distance_m' in m: E(i, 'mod.geo', 'use', 'uzaklık uyarısı')
        if 'publish' in m: E(i, 'api.events', 'event', 'olay yayını')
        if 'file' in m and 'files' in r['pattern']: E(i, 'data.sigs' if 'signature' in r['pattern'] else 'data.photos', 'read')
        if r['fn'] == 'backup':
            for x in ('data.db', 'data.photos', 'data.sigs'): E(i, x, 'read')
        E('mod.server', i, 'route')
    E(route_by[('POST', '/api/tasks/{x}/signature')], 'data.sigs', 'write')
    E('mod.images', 'data.photos', 'write', 'tam boy + küçük resim')
    E('mod.geo', 'ext.nominatim', 'external', 'koordinat → adres')
    E('mod.ai', 'ext.openai', 'external', 'fotoğraf (EXIF\'siz) + bağlam')
    E('mod.ai', 'mod.images', 'use', 'EXIF silme')
    E('mod.tunnel', 'ext.cloudflare', 'external', 'cloudflared tunnel')
    E('mod.tunnel', 'ext.termux', 'external', 'resolv.conf (DNS)')
    E('mod.secrets', 'data.secrets', 'write')
    E('mod.main', 'mod.tunnel', 'use', 'açılışta tünel')
    for t in ('photos', 'projects', 'geocode_cache'): E('mod.geo', 'tbl.' + t, 'write')
    E('mod.geo', 'api.events', 'event', 'adres bulundu')
    E('mod.server', 'api.events', 'route')
    E('mod.db', 'data.db', 'write', 'bağlantı + göç')
    for t in raw['tables']: E('tbl.' + t, 'data.db', 'contain')
    E('mod.main', 'mod.server', 'use', 'sunucuyu başlatır'); E('mod.main', 'tbl.settings', 'write', 'kurulum kodu (özet)')
    E('mod.server', 'mod.auth', 'use', 'oturum kontrolü'); E('mod.server', 'mod.db', 'use')
    # cihaz / dış
    E('ui.camera', 'ext.camera', 'external', 'fotoğraf çek'); E('ui.camera', 'ext.gps', 'external', 'en yakın müşteri')
    E('ui.sheet', 'ext.camera', 'external'); E('ui.sheet', 'ext.gps', 'external', 'çekim anı konumu')
    E('ui.map', 'ext.gps', 'external', 'mavi nokta'); E('ui.map', 'ext.osm', 'external', 'harita karoları'); E('ui.map', 'ext.gmaps', 'external', 'yol tarifi')
    E('ui.sw', 'ext.osm', 'external', 'karo önbelleği')
    # işletim
    E('ops.install', 'ext.github', 'external', 'git clone / pull'); E('ops.install', 'ops.termux', 'use')
    E('ops.termux', 'ext.termux', 'external', 'pkg install'); E('ops.termux', 'mod.main', 'use', 'fototakip komutu')
    E('ops.termux', 'ext.cloudflare', 'external', 'fototakip-tunel')
    E('ops.upload', 'ext.github', 'external', 'git push + doğrulama')
    E('ops.reset', 'ops.backup', 'use', 'önce yedek'); E('ops.reset', 'data.db', 'write', 'siler'); E('ops.reset', 'data.secrets', 'write', 'siler'); E('ops.reset', 'ext.termux', 'external', 'DNS geri')
    E('ops.backup', 'data.db', 'read'); E('ops.backup', 'data.photos', 'read'); E('ops.backup', 'data.sigs', 'read')
    E('ext.github', 'ops.ci', 'use', 'her push'); E('ops.ci', 'ops.tests', 'use')
    E('ops.tests', 'mod.server', 'use', 'gerçek sunucu')

    bad = [e for e in edges if e['s'] not in ids or e['t'] not in ids]
    assert not bad, bad
    P = route_by
    FLOWS = [
     dict(id='photo', name='Fotoğraftan iş', steps=[
       ('ext.camera', 'Teknisyen fotoğrafı çeker.'), ('ui.camera', 'Kamera ekranı konumdan en yakın müşteriyi seçer.'), ('ext.gps', 'Çekim anının cihaz konumu ve doğruluğu alınır.'),
       (P[('POST', '/api/photos')], 'Fotoğraf ham bayt olarak yüklenir; tür ve konum sorgu dizesinde.'), ('mod.images', 'Tür doğrulanır, EXIF okunur, döndürülür, küçültülür.'),
       ('data.photos', 'Dosya EXIF\'siz kaydedilir; konum dosyada kalmaz.'), ('tbl.tasks', 'Yeni iş açılır, numara verilir.'), ('tbl.photos', 'Konum kaynağı yazılır: EXIF, cihaz ya da proje.'),
       ('mod.geo', 'Adres işçisi kuyruğa alır; uzaklık 500 m\'yi geçerse uyarı.'), ('ext.nominatim', 'Koordinat adrese çevrilir (önbellekte yoksa).'),
       ('tbl.projects', 'Müşterinin adresi boşsa doldurulur, farklıysa öneri yazılır.'), ('api.events', 'Değişiklik tüm açık ekranlara duyurulur.'), ('ui.shell', 'Diğer telefonlarda pano kendini yeniler.')]),
     dict(id='review', name='Onay / geri gönderme', steps=[
       ('ui.sheet', 'Teknisyen "sonra" fotoğrafı ekler.'), (P[('POST', '/api/photos')], 'Otomasyon kontrolü: önce fotoğrafı ve zorunlu kanıtlar var mı?'),
       ('tbl.checklist', 'Zorunlu maddelerin kanıtı aranır.'), ('tbl.tasks', 'Koşul tamamsa iş "Onay bekliyor"a geçer.'), ('api.events', 'Yöneticinin ekranına düşer.'),
       ('ui.sheet', 'Yönetici önce/sonra kaydırıcısıyla inceler.'), (P[('POST', '/api/tasks/{x}/review')], 'Onay ya da gerekçeli geri gönderme.'),
       ('tbl.comments', 'Geri gönderme nedeni yoruma yazılır.'), ('tbl.activity', 'Karar etkinlik geçmişine girer.'), ('ui.shell', 'Teknisyenin kartında "Geri gönderildi" görünür.')]),
     dict(id='customer', name='Haritadan müşteri', steps=[
       ('ui.map', 'Yönetici "+" ile haritaya dokunur ya da bulunduğu yeri kullanır.'), ('ext.gps', 'Bulunduğu yerin konumu.'), (P[('GET', '/api/geocode')], 'Nokta adrese çevrilmek istenir.'),
       ('tbl.geocode_cache', 'Önce önbelleğe bakılır.'), ('ext.nominatim', 'Yoksa Nominatim\'e sorulur.'), (P[('POST', '/api/projects')], 'Müşteri adres ve konum kaynağıyla kaydedilir.'),
       ('tbl.projects', 'Yeni pin haritada belirir.')]),
     dict(id='offline', name='Çevrimdışı yükleme', steps=[
       ('ui.camera', 'Sahada internet yok.'), ('ui.queue', 'Fotoğraflar IndexedDB kuyruğuna yazılır.'), ('ui.shell', 'Bağlantı gelince "online" olayı tetiklenir.'),
       (P[('POST', '/api/photos')], 'Kuyruk sırayla yüklenir; yarıda kalırsa kalan kısım yeniden kuyruğa girer.'), ('tbl.tasks', 'İşler oluşur.'), ('api.events', 'Ekip haberdar olur.')]),
     dict(id='ai', name='AI fotoğraf incelemesi', steps=[
       ('ui.sheet', 'Kişi fotoğrafta "AI gözlemi al"a dokunur.'), (P[('POST', '/api/photos/{x}/ai-review')], 'Yetki ve ayar kontrolü: AI açık mı, fotoğraf bu işe ait mi?'),
       ('tbl.ai_reviews', 'Önceden inceleme varsa tekrar ücret ödenmez, önbellekten döner.'), ('mod.secrets', 'Anahtar gizli dosyadan okunur.'),
       ('mod.images', 'JPEG\'den EXIF ve konum silinir.'), ('mod.ai', 'Fotoğraf ve iş bağlamı gönderilir.'), ('ext.openai', 'Model gözlemleri JSON olarak döner.'),
       ('mod.ai', 'Çıktı dar şemaya indirilir; "insan incelemesi zorunlu" her zaman doğru.'), ('tbl.ai_reviews', 'Sonuç saklanır.'),
       ('tbl.activity', 'Etkinlik geçmişine "AI gözlemi alındı" yazılır.'), ('api.events', 'Ekip haberdar olur; karar yine yöneticide.')]),
     dict(id='tunnel', name='Dışarıdan erişim', steps=[
       ('ui.profile', 'Yönetici Entegrasyonlar\'da tünel türünü seçer.'), (P[('PATCH', '/api/admin/integrations')], 'Ayar kaydedilir; token varsa gizli dosyaya yazılır.'),
       ('mod.secrets', 'Token 0600 izinli dosyada.'), (P[('POST', '/api/admin/tunnel/start')], 'Başlatma isteği.'),
       ('tbl.users', 'Eski kurulumdan kalan demo1234 parolalı hesap varsa tünel açılmaz.'), ('mod.tunnel', 'cloudflared arka planda başlatılır; token komut satırına yazılmaz.'),
       ('ext.termux', 'Gerekirse DNS (ör. OpenDNS) resolv.conf\'tan okunur.'), ('ext.cloudflare', 'Telefondan dışarıya şifreli bağlantı; port açmak gerekmez.'),
       ('ui.profile', 'https://… adresi ekranda görünür, kopyalanır.')]),
     dict(id='install', name='Kurulum ve yayın', steps=[
       ('ops.upload', 'Kod GitHub\'a gönderilir; önce "zaten yüklü mü" kontrolü.'), ('ext.github', 'Depo güncellenir.'), ('ops.ci', 'GitHub Actions testleri çalıştırır.'),
       ('ops.install', 'Telefonda tek satırlık kurulum.'), ('ops.termux', 'Paketler ve komutlar kurulur.'), ('ext.termux', 'Termux:Boot ile açılışta başlar.'),
       ('mod.main', 'fototakip komutu sunucuyu açar; veritabanı boşsa kurulum kodu yazar.'), ('mod.db', 'Veritabanı gerekiyorsa yeni sürüme taşınır.'), ('mod.server', 'http://localhost:8080 hazır.'),
       ('ui.login', 'İlk açılışta kurulum kodu ile yönetici hesabı açılır.'), (P[('POST', '/api/setup')], 'Kod doğrulanır (5 hata sınırı), ilk yönetici oluşur, kod silinir.'), ('tbl.users', 'İlk ve tek hazır hesap.')]),
    ]
    for f in FLOWS:
        for s, _ in f['steps']: assert s in ids, s
        f['steps'] = [dict(id=s, text=t) for s, t in f['steps']]
    deg = {}
    for e in edges: deg[e['s']] = deg.get(e['s'], 0) + 1; deg[e['t']] = deg.get(e['t'], 0) + 1
    for n in nodes: n['deg'] = deg.get(n['id'], 0)
    return dict(nodes=nodes, edges=edges, flows=FLOWS, unmapped=unmapped)


def source_digest(R):
    h = hashlib.sha256()
    for p in SOURCES:
        f = R / p
        if f.exists():
            h.update(p.encode()); h.update(f.read_bytes())
    return h.hexdigest()[:7]


def render(R=ROOT):
    raw = extract(R)
    g = build(R, raw)
    unmapped = g.pop("unmapped")
    g["sha"] = source_digest(R)
    data = json.dumps(g, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    page = (HERE / "sablon.html").read_text(encoding="utf-8").replace("__GRAPH__", data)
    html = ('<!doctype html>\n<html lang="tr">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<style>[hidden]{display:none!important}body{margin:0}</style>\n</head>\n<body>\n'
            + page + '\n</body>\n</html>\n')
    return html, g, unmapped


def main(argv):
    html, g, unmapped = render()
    for u in unmapped:
        print(f"uyarı: ekranı bilinmeyen çağrı → {u}. tools/proje-haritasi/uret.py içindeki CTX'e ekle.", file=sys.stderr)
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != html:
            print("Proje haritası eski. Güncellemek için: python3 tools/proje-haritasi/uret.py", file=sys.stderr)
            return 1
        print(f"Proje haritası güncel ({g['sha']}).")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"Yazıldı: {OUT.relative_to(ROOT)} · {len(g['nodes'])} düğüm · {len(g['edges'])} bağlantı · kaynak {g['sha']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
