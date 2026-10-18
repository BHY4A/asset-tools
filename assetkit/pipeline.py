"""Конвейер для сайта: одна команда вместо ручных шагов.

  python at.py pipeline targets/knitu.json                 все стили
  python at.py pipeline targets/knitu.json --styles ether,neon --check

Что делает для каждого стиля из описания (targets/*.json):
  1. рисует фоны генератором для каждой утилиты и хаба, в светлой и тёмной теме, кладёт в папку текстур сайта;
  2. если у стиля указан css — переписывает в нём блок между /* @bg:begin */ и /* @bg:end */ (правила фона по утилитам);
  3. собирает styles.css командой сайта (build);
  4. поднимает номер версии (?v=… и SVER) во всех файлах, чтобы браузеры не держали старое в кэше;
  5. с --check — открывает сайт в браузере, меряет контраст текста на фоне и, если где-то не читается,
     притемняет (или высветляет) этот фон к цвету темы и проверяет снова (до трёх раз).
"""
import glob, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import numpy as np
from .registry import get
from .core import save, load, hexc

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _paths(cfg, base):
    hub = os.path.normpath(os.path.join(base, cfg['hub']))
    apps = {k: os.path.normpath(os.path.join(base, v)) for k, v in cfg.get('apps', {}).items()}
    return hub, apps

def _bg_css(sid, sc, apps):
    name = sc['name']; base = sc.get('base', {}); bl, bd = base.get('light', '#ffffff'), base.get('dark', '#000000')
    att = sc.get('attach', 'center / cover fixed no-repeat')
    L = [f'/* @bg:begin — сгенерировано: python at.py pipeline (стиль {sid}); правки внутри блока будут перезаписаны */']
    for app in apps:
        lu, du = f"url(tx/{name.format(app=app, theme='light')})", f"url(tx/{name.format(app=app, theme='dark')})"
        L.append(f'[data-app="{app}"] body {{ background: {bl} {lu} {att}; }}')
        L.append(f':root[data-theme="dark"][data-app="{app}"] body {{ background: {bd} {du} {att}; }}')
        L.append(f'@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"])[data-app="{app}"] body {{ background: {bd} {du} {att}; }} }}')
    for extra in sc.get('css_extra', []): L.append(extra)
    if sc.get('hub'):
        lu, du = f"url(tx/{name.format(app='hub', theme='light')})", f"url(tx/{name.format(app='hub', theme='dark')})"
        L += ['/*@hub*/', f'body {{ background: {bl} {lu} {att}; }}', f':root[data-theme="dark"] body {{ background: {bd} {du} {att}; }}',
              f'@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) body {{ background: {bd} {du} {att}; }} }}', '/*@endhub*/']
    L.append('/* @bg:end */')
    return '\n'.join(L)

def _inject(path, block):
    t = open(path, encoding='utf-8').read()
    if '/* @bg:begin' in t:
        i = t.index('/* @bg:begin'); j = t.index('/* @bg:end */') + len('/* @bg:end */'); t = t[:i] + block + t[j:]
    else:
        t = t.rstrip() + '\n\n' + block + '\n'
    open(path, 'w', encoding='utf-8').write(t)

def generate(sid, sc, hub, apps, size, dry=False, only=None):
    t = get(sc['tool']); tx = os.path.join(hub, sc.get('tx', 'styles/tx')); made = []
    targets = [(a, a) for a in apps] + ([('hub', sc['hub'].get('app', 'нет'))] if sc.get('hub') else [])
    for theme, tcfg in sc['themes'].items():
        for key, app in targets:
            if only and (key, theme) not in only: continue
            p = t.spec.defaults()
            if tcfg.get('preset'): p.update(t.spec.presets[tcfg['preset']])
            p.update(tcfg.get('set', {}))
            if 'app' in t.spec.by: p['app'] = app if app in t.spec.by['app'].choices else t.spec.by['app'].default
            if 'width' in t.spec.by: p['width'], p['height'] = size
            dst = os.path.join(tx, sc['name'].format(app=key, theme=theme)); made.append(dst)
            if dry: print('  нарисую', os.path.relpath(dst, hub)); continue
            img = t.run(None, p, int(tcfg.get('seed', sc.get('seed', 7))))
            save(img, dst, sc.get('quality', 80), quiet=True); print('  ', os.path.relpath(dst, hub))
    return made

def bump_version(files):
    cur = None
    for f in files:
        m = re.search(r"SVER\s*=\s*'(\d{8,14})'", open(f, encoding='utf-8').read()) if f.endswith('suite.js') else None
        if m: cur = m.group(1); break
    if not cur: print('  версия: не нашёл SVER — пропускаю'); return None
    new = time.strftime('%Y%m%d%H%M')
    if new <= cur: new = str(int(cur) + 1)
    for f in files:
        t = open(f, encoding='utf-8', newline='').read()
        if cur in t: open(f, 'w', encoding='utf-8', newline='').write(t.replace(cur, new))
    print(f'  версия {cur} → {new}'); return new

def tame(path, base_hex, amount):
    """приблизить фон к цвету темы — текст на нём станет читаемее"""
    img = load(path); c = hexc(base_hex)
    img = img * (1 - amount) + c * amount
    save(img, path, 82, quiet=True)

class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def handle(self):
        try: super().handle()
        except (BrokenPipeError, ConnectionResetError): pass   # браузер закрыл соединение — это нормально

def _site_dir(hub, apps):
    d = tempfile.mkdtemp(prefix='at-site-')
    def link(src, dst):
        try: os.symlink(src, dst, target_is_directory=os.path.isdir(src))
        except (OSError, NotImplementedError):     # Windows без прав на ссылки — копируем
            (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)
    for f in os.listdir(hub):
        if not f.startswith('.'): link(os.path.join(hub, f), os.path.join(d, f))
    for k, v in apps.items():
        dst = os.path.join(d, k)
        if not os.path.exists(dst): link(v, dst)
    return d

def contrast_check(style, hub, apps, fonts=None):
    node = shutil.which('node')
    qa = os.path.join(HERE, 'qa')
    if not node: print('  проверка: нет node — установите Node.js и выполните npm install в папке qa'); return None
    d = _site_dir(hub, apps)
    s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
    srv = ThreadingHTTPServer(('127.0.0.1', port), lambda *a, **k: _Quiet(*a, directory=d, **k))
    th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
    try:
        env = dict(os.environ)
        cmd = [node, os.path.join(qa, 'contrast.js'), style, f'http://127.0.0.1:{port}/', fonts or '-', '--json']
        r = subprocess.run(cmd, cwd=qa, capture_output=True, text=True, env=env, timeout=900)
        if r.returncode != 0:
            print('  проверка не запустилась:', '\n    '.join(((r.stderr or r.stdout).strip().splitlines() or [str(r.returncode)])[-6:]))
            print('  подсказка: cd qa && npm install && npx playwright install chromium'); return None
        return json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        srv.shutdown(); shutil.rmtree(d, ignore_errors=True)

def make_assets(cfg, hub, apps, dry=False):
    """превью ссылок (Open Graph) и иконки для каждой страницы: og.jpg, apple-touch-icon.png, favicon.ico"""
    from .gen import icon
    from .core import to_u8
    from PIL import Image
    a = cfg.get('assets', {}); og = a.get('og', {}); pages = a.get('pages', {})
    for key, meta in pages.items():
        root = hub if key == 'hub' else apps[key]; app = key if key != 'hub' else 'нет'
        if dry: print('  нарисую', key, '→ og.jpg, apple-touch-icon.png, favicon.ico'); continue
        g = get(og.get('tool', 'graphite')); p = g.spec.defaults(); p.update(g.spec.presets.get(og.get('preset', ''), {}))
        p.update(og.get('set', {})); p['width'], p['height'] = 1200, 630
        if 'app' in g.spec.by: p['app'] = app if app in g.spec.by['app'].choices else g.spec.by['app'].default
        bg = g.run(None, p, og.get('seed', 7))
        c = get('card'); cp = c.spec.defaults(); cp.update(c.spec.presets.get(og.get('card_preset', ''), {}))
        cp.update(title=meta['title'], subtitle=meta.get('subtitle', ''), label=meta.get('label', a.get('label', '')), app=key if key in ('hub',) + tuple(apps) else 'нет')
        save(c.run(bg, cp, 7), os.path.join(root, 'og.jpg'), 86, quiet=True)
        look = a.get('icon_look', 'плоский'); ia = key if key != 'hub' else 'hub'
        ip = dict(icon.SPEC.defaults(), app=ia, look=look, size=180, radius=0, shadow=0)
        Image.fromarray(to_u8(icon.apply(ip)), 'RGBA').convert('RGB').save(os.path.join(root, 'apple-touch-icon.png'))
        open(os.path.join(root, 'favicon.ico'), 'wb').write(icon.ico_bytes(ia, look))
        print('  ', key, ': og.jpg, apple-touch-icon.png, favicon.ico')

# на этих элементах текст лежит прямо на фоне — их и чиним притемнением фона
ON_BG = {'.foot', '.intro .lead', '.intro .eyebrow', '.brand small', '.brand b', '.card-e', '.last', '.var-ctl label'}

def run(target, styles=None, check=False, build=True, dry=False, size=None, check_only=False, assets=False):
    base = os.path.dirname(os.path.abspath(target)); cfg = json.load(open(target, encoding='utf-8'))
    hub, apps = _paths(cfg, base); size = tuple(map(int, (size or 'x'.join(map(str, cfg.get('size', [1920, 1200])))).lower().split('x')))
    todo = [s for s in cfg['styles'] if not styles or s in styles]
    print(f'Сайт: {cfg.get("name", target)}\n  хаб: {hub}\n  утилиты: {", ".join(apps)}\n  стили: {", ".join(todo)}  размер {size[0]}×{size[1]}')
    if assets: print('— превью ссылок и иконки'); make_assets(cfg, hub, apps, dry)
    if check_only: check, dry_gen = True, True
    else: dry_gen = False
    for sid in ([] if check_only else todo):
        sc = cfg['styles'][sid]; print(f'— {sid}: фоны генератором «{sc["tool"]}»')
        generate(sid, sc, hub, list(apps), size, dry)
        if sc.get('css') and not dry:
            _inject(os.path.join(hub, sc['css']), _bg_css(sid, sc, list(apps))); print('  CSS:', sc['css'])
    if build and not dry and not check_only and cfg.get('build'):
        b = cfg['build']; r = subprocess.run(b['cmd'], cwd=os.path.join(hub, b.get('cwd', '.')), capture_output=True, text=True)
        print('— сборка:', (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else r.returncode)
    vfiles = [f for pat in cfg.get('version_files', []) for f in glob.glob(os.path.join(base, pat))]
    if not dry and not check_only and vfiles: print('— версия'); bump_version(vfiles)
    if check and not dry:
        for sid in todo:
            sc = cfg['styles'][sid]; base_c = sc.get('base', {})
            prev = 0
            for round_ in range(3):
                print(f'— контраст «{sid}», проход {round_ + 1}')
                rows = contrast_check(sid, hub, apps, cfg.get('fonts') and os.path.join(base, cfg['fonts']))
                if rows is None: break
                bad = [r for r in rows if r['avg'] < 4.5 and r['sel'] in ON_BG]
                for r in rows:
                    if r['avg'] < 4.5: print(f'   {r["avg"]:5.2f} (мин {r["min"]:.2f})  {r["app"]} {r["theme"]} {r["sel"]}' + ('  → притемню фон' if r in bad else ''))
                if not bad: print('   всё читается'); break
                score = sum(r['avg'] for r in bad) / len(bad)
                if round_ and score <= prev + .08:
                    print('   притемнение фона почти не помогает: дело в цвете текста — поправьте его в CSS стиля'); break
                prev = score
                for app, theme in {(r['app'], r['theme']) for r in bad}:
                    f = os.path.join(hub, sc.get('tx', 'styles/tx'), sc['name'].format(app=app, theme=theme))
                    if os.path.exists(f): tame(f, base_c.get(theme, '#ffffff' if theme == 'light' else '#000000'), .22); print('   притемнил', os.path.basename(f))
                if vfiles: bump_version(vfiles)
    print('Готово.')
