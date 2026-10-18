"""Командная строка: python at.py <команда> …   (список — python at.py -h)"""
import argparse, glob, json, os, sys, time
from .params import add_cli, runs, save_params
from .registry import TOOLS, get
from . import recipe as R
from .core import load, save, encode

EPILOG = """примеры:
  python at.py list                                         все инструменты и пресеты
  python at.py params signal                                параметры инструмента
  python at.py photo lines фото.jpg --preset комикс          фото через фильтр
  python at.py photo signal "папка/*.jpg" --random 0.3 --variants 4 --out готово/
  python at.py gen ether --apps all --preset ночь --out фоны/
  python at.py gen tiles --preset мрамор --set size=512
  python at.py recipe мой.json фото.jpg                     цепочка из студии
  python at.py anim ether --preset ночь --frames 24 --format webp
  python at.py icons --out иконки/ --look глянец            favicon.ico, apple-touch-icon, 512 px
  python at.py pipeline targets/knitu.json --styles ether --check
  python at.py studio                                       студия в браузере (быстрый локальный режим)
"""

def _fmt_name(tpl, **kw):
    try: return tpl.format(**kw)
    except KeyError: return tpl

def cmd_list(a):
    for t in TOOLS.values():
        kind = 'фильтр   ' if t.kind == 'filter' else 'генератор'
        print(f'{t.id:<11} {kind}  {t.spec.title:<20} {t.spec.about}')
        if t.spec.presets: print(' ' * 23 + 'пресеты: ' + ', '.join(t.spec.presets))

def cmd_params(a): print(get(a.tool).spec.table())

def _plan(a, tool):
    a.params = False
    return runs(a, tool.spec)

def cmd_photo(a):
    t = get(a.tool)
    if t.kind != 'filter': raise SystemExit(f'{a.tool} — генератор, ему не нужно фото: python at.py gen {a.tool}')
    files = [f for pat in a.files for f in (glob.glob(pat) or [pat])]
    if not files: raise SystemExit('Укажите файл(ы) изображения')
    plan = _plan(a, t)
    for f in files:
        img = load(f, a.max)
        for prm, seed, suf in plan:
            res = t.run(img, prm, seed)
            base = os.path.splitext(os.path.basename(f))[0] + f'_{t.id}{suf}.{a.format}'
            out = a.out if a.out else (os.path.dirname(f) or '.')
            dst = out if (a.out and a.out.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) and len(files) == 1 and len(plan) == 1) else os.path.join(out, base)
            save(res, dst)
            if not a.no_save_params: save_params(dst, t.spec, prm, seed)

def cmd_gen(a):
    t = get(a.tool)
    if t.kind != 'gen': raise SystemExit(f'{a.tool} — фильтр, ему нужно фото: python at.py photo {a.tool} фото.jpg')
    plan = _plan(a, t)
    apps = None
    if a.apps and 'app' in t.spec.by:
        ch = t.spec.by['app'].choices
        apps = [x for x in ch if x not in ('нет', 'hub')] if a.apps == 'all' else a.apps.split(',')
    for prm, seed, suf in plan:
        for app in (apps or [prm.get('app', '')]):
            q = dict(prm)
            if app: q['app'] = app
            res = t.run(None, q, seed)
            name = _fmt_name(a.name, tool=t.id, app=app or 'x', preset=(a.preset or 'default').replace(' ', '-'), n=suf, seed=seed, fmt=a.format)
            dst = os.path.join(a.out, name); save(res, dst)
            if not a.no_save_params: save_params(dst, t.spec, q, seed)

def cmd_recipe(a):
    steps = R.load(a.recipe); photos = [f for pat in a.files for f in (glob.glob(pat) or [pat])]
    if R.needs_photo(steps) and not photos: raise SystemExit('Рецепт начинается с фильтра — укажите фото')
    for f in (photos or [None]):
        img = load(f, a.max) if f else None
        res = R.run(steps, img, None)
        base = (os.path.splitext(os.path.basename(f))[0] + '_' if f else '') + os.path.splitext(os.path.basename(a.recipe))[0] + '.' + a.format
        save(res, os.path.join(a.out, base))

def cmd_anim(a):
    from . import anim
    if a.what.lower().endswith('.json'): steps = R.load(a.what)
    else:
        t = get(a.what); prm, seed, _ = _plan(a, t)[0]; steps = [{'tool': t.id, 'params': prm, 'seed': seed}]
    photo = load(a.photo, a.max_side) if a.photo else None
    mode = a.mode or anim.modes(steps)[0]
    fr = anim.frames(steps, a.frames, mode, photo, a.max_side, progress=lambda i, n: print(f'\r  кадр {i}/{n}', end='', flush=True)); print()
    data = anim.encode(fr, a.format, a.fps); os.makedirs(a.out, exist_ok=True)
    dst = os.path.join(a.out, f'{os.path.splitext(os.path.basename(a.what))[0]}-{mode}.{a.format}'); open(dst, 'wb').write(data); print('сохранено:', dst)

def cmd_icons(a):
    from .gen import icon
    from .core import to_u8
    from PIL import Image
    apps = a.apps.split(',') if a.apps else ['sapr-labs', 'krrs-robot', 'op-coursework', 'eco-pdv', 'hub']
    for app in apps:
        d = os.path.join(a.out, app); os.makedirs(d, exist_ok=True)
        kw = {} if a.look == 'плоский' else dict(icon.SPEC.presets.get(a.look, {}))
        kw.pop('look', None)
        open(os.path.join(d, 'favicon.ico'), 'wb').write(icon.ico_bytes(app, a.look, **kw))
        for sz, name, pad in [(180, 'apple-touch-icon.png', 0), (512, 'icon-512.png', 0), (192, 'icon-192.png', 0)]:
            p = dict(icon.SPEC.defaults(), **kw); p.update(app=app, look=a.look, size=sz, shadow=0, radius=0 if name.startswith('apple') else p['radius'])
            Image.fromarray(to_u8(icon.apply(p)), 'RGBA').save(os.path.join(d, name))
        print('готово:', d)

def cmd_parts(a):
    from .gen import watercolor
    print('готово:', watercolor.parts(a.out, a.seed))

def cmd_manifest(a):
    root = os.path.dirname(os.path.abspath(__file__)); files = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != '__pycache__']
        for f in fn:
            if f.endswith(('.py', '.ttf', '.json')) and f != 'manifest.json':
                files.append(os.path.relpath(os.path.join(dp, f), os.path.dirname(root)).replace('\\', '/'))
    ver = time.strftime('%Y%m%d%H%M')
    json.dump({'version': ver, 'files': sorted(files)}, open(os.path.join(root, 'manifest.json'), 'w'), ensure_ascii=False, indent=0)
    print(f'manifest.json: {len(files)} файлов, версия {ver}')

def cmd_pipeline(a):
    from .pipeline import run
    run(a.target, styles=a.styles.split(',') if a.styles else None, check=a.check, build=not a.no_build, dry=a.dry, size=a.size, check_only=a.check_only, assets=a.assets)

def cmd_studio(a):
    from .server import serve
    serve(a.port, not a.no_browser)

def main(argv=None):
    ap = argparse.ArgumentParser(prog='at.py', description='Asset Tools: фильтры, генераторы, цепочки, анимация, конвейер для сайта',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=EPILOG)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list', help='все инструменты').set_defaults(fn=cmd_list)
    p = sub.add_parser('params', help='параметры инструмента'); p.add_argument('tool'); p.set_defaults(fn=cmd_params)
    p = sub.add_parser('photo', help='фото через фильтр'); p.add_argument('tool'); p.add_argument('files', nargs='*')
    p.add_argument('--out', default=None); p.add_argument('--max', type=int, default=2560, help='ограничить длинную сторону исходника'); p.add_argument('--format', default='webp', choices=['webp', 'png', 'jpg'])
    add_cli(p); p.set_defaults(fn=cmd_photo)
    p = sub.add_parser('gen', help='генератор'); p.add_argument('tool'); p.add_argument('--apps', default=None, help='сюжеты через запятую или all')
    p.add_argument('--out', default='out'); p.add_argument('--format', default='webp', choices=['webp', 'png', 'jpg'])
    p.add_argument('--name', default='{tool}-{app}-{preset}{n}.{fmt}', help='шаблон имени: {tool} {app} {preset} {n} {seed} {fmt}')
    add_cli(p); p.set_defaults(fn=cmd_gen)
    p = sub.add_parser('recipe', help='выполнить цепочку из .json'); p.add_argument('recipe'); p.add_argument('files', nargs='*')
    p.add_argument('--out', default='out'); p.add_argument('--max', type=int, default=2560); p.add_argument('--format', default='png', choices=['webp', 'png', 'jpg']); p.set_defaults(fn=cmd_recipe)
    p = sub.add_parser('anim', help='анимация инструмента или рецепта'); p.add_argument('what', help='инструмент или recipe.json')
    p.add_argument('--photo', default=None); p.add_argument('--frames', type=int, default=24); p.add_argument('--fps', type=int, default=12)
    p.add_argument('--mode', choices=['фаза', 'зерно', 'переход'], default=None); p.add_argument('--format', default='gif', choices=['gif', 'webp'])
    p.add_argument('--max-side', type=int, default=640); p.add_argument('--out', default='out'); add_cli(p); p.set_defaults(fn=cmd_anim)
    p = sub.add_parser('icons', help='favicon и иконки утилит'); p.add_argument('--out', default='out/icons'); p.add_argument('--apps', default=None)
    p.add_argument('--look', default='плоский', choices=['плоский', 'глянец', 'неон', 'стекло', 'бумага', 'пиксели']); p.set_defaults(fn=cmd_icons)
    p = sub.add_parser('parts', help='детали стиля «Акварель»'); p.add_argument('what', choices=['watercolor']); p.add_argument('--out', default='out/parts'); p.add_argument('--seed', type=int, default=7); p.set_defaults(fn=cmd_parts)
    p = sub.add_parser('pipeline', help='фоны стилей для сайта: генерация, сборка CSS, версия, проверка контраста')
    p.add_argument('target', help='описание сайта, например targets/knitu.json'); p.add_argument('--styles', default=None, help='какие стили (по умолчанию все)')
    p.add_argument('--check', action='store_true', help='проверить контраст в браузере и притемнить фон, если текст не читается')
    p.add_argument('--no-build', action='store_true'); p.add_argument('--assets', action='store_true', help='ещё и превью ссылок (og.jpg) и иконки для каждой страницы'); p.add_argument('--check-only', action='store_true', help='только проверить контраст (и притемнить), ничего не рисовать заново'); p.add_argument('--dry', action='store_true', help='только показать, что будет сделано')
    p.add_argument('--size', default=None, help='размер фонов ШxВ (по умолчанию из описания)'); p.set_defaults(fn=cmd_pipeline)
    p = sub.add_parser('studio', help='студия в браузере'); p.add_argument('--port', type=int, default=8777); p.add_argument('--no-browser', action='store_true'); p.set_defaults(fn=cmd_studio)
    sub.add_parser('manifest', help='обновить список файлов для веб-студии').set_defaults(fn=cmd_manifest)
    a = ap.parse_args(argv)
    if getattr(a, 'params', False) and a.cmd in ('photo', 'gen', 'anim'):
        print(get(a.tool if a.cmd != 'anim' else a.what).spec.table()); return
    a.fn(a)
