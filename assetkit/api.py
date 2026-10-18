"""Единая точка входа для студии: одинаково работает в браузере (Pyodide, веб-воркер) и через локальный studio.py.

call(cmd, args, blobs) → (result_dict, out_blobs). Картинки ходят байтами (PNG/JPEG/WebP), всё остальное — JSON.
"""
import io, json, time, zipfile, random as _random
import numpy as np, cv2
from . import recipe as R, anim
from .registry import TOOLS, get
from .core import decode, encode, flatten

PHOTO = {'full': None, 'cache': {}, 'name': 'photo'}
FULL_LIMIT = 4096

def _photo(max_side):
    if PHOTO['full'] is None: return None
    if not max_side: return PHOTO['full']
    c = PHOTO['cache']
    if max_side not in c:
        im = PHOTO['full']; k = min(1.0, max_side / max(im.shape[:2]))
        c[max_side] = cv2.resize(im, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else im
    return c[max_side]

def _img_out(img, fmt, quality):
    if fmt == 'jpg' and img.ndim == 3 and img.shape[2] == 4: fmt = 'png'   # прозрачность — только в PNG/WebP
    return encode(img, fmt, quality), fmt

def call(cmd, args, blobs=()):
    a = args or {}
    if cmd == 'tools':
        return {'tools': [t.ui() for t in TOOLS.values()]}, []
    if cmd == 'photo':
        PHOTO['full'] = decode(bytes(blobs[0]), FULL_LIMIT); PHOTO['cache'] = {}; PHOTO['name'] = a.get('name', 'photo')
        h, w = PHOTO['full'].shape[:2]; return {'w': w, 'h': h}, []
    if cmd == 'clear_photo':
        PHOTO['full'] = None; PHOTO['cache'] = {}; return {}, []
    if cmd == 'render':
        t0 = time.time(); steps = R.normalize(a['steps']); ms = int(a.get('max_side') or 0) or None
        img = R.run(steps, _photo(ms), ms, a.get('upto'))
        info = {'w': int(img.shape[1]), 'h': int(img.shape[0]), 'alpha': bool(img.ndim == 3 and img.shape[2] == 4)}
        last = [s for s in steps if s['on']]
        if last and get(last[-1]['tool']).id == 'tiles':
            from .gen.tiles import seam_score
            info['seam'] = round(seam_score(img), 3)
        data, fmt = _img_out(img, a.get('fmt', 'jpg'), int(a.get('quality', 88)))
        info.update(fmt=fmt, ms=int((time.time() - t0) * 1000)); return info, [data]
    if cmd == 'random':
        t = get(a['tool']); spec = t.spec; p = spec.defaults(); p.update(a.get('params') or {})
        rng = _random.Random(int(a.get('seed', 7)) * 7919 + 13); lock = set(a.get('lock') or [])
        for prm in spec.params:
            if prm.name in lock or prm.kind == 'text': continue
            p[prm.name] = prm.jitter(p[prm.name], float(a.get('amount', 1)), rng)
        return {'params': p}, []
    if cmd == 'preset':
        t = get(a['tool']); p = t.spec.defaults(); p.update(t.spec.presets.get(a['name'], {})); return {'params': p}, []
    if cmd == 'batch':
        steps = R.normalize(a['steps']); names = a.get('names') or []; fmt = a.get('fmt', 'png')
        buf = io.BytesIO(); z = zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED); saved = PHOTO.copy()
        try:
            for i, b in enumerate(blobs):
                PHOTO['full'] = decode(bytes(b), FULL_LIMIT); PHOTO['cache'] = {}
                img = R.run(steps, PHOTO['full'], None)
                data, f = _img_out(img, fmt, int(a.get('quality', 92)))
                base = (names[i] if i < len(names) else f'img{i + 1}').rsplit('.', 1)[0]
                z.writestr(f'{base}.{f}', data)
            z.writestr('recipe.json', json.dumps(R.dump(steps), ensure_ascii=False, indent=1))
        finally:
            PHOTO.update(saved)
        z.close(); return {'count': len(blobs)}, [buf.getvalue()]
    if cmd == 'anim':
        steps = R.normalize(a['steps']); ms = int(a.get('max_side') or 480)
        fr = anim.frames(steps, int(a.get('n', 24)), a.get('mode', 'фаза'), _photo(ms), ms, int(a.get('step_index', 0)), a.get('target'))
        fmt = a.get('fmt', 'gif'); return {'fmt': fmt, 'n': len(fr)}, [anim.encode(fr, fmt, int(a.get('fps', 12)))]
    if cmd == 'anim_modes':
        return {'modes': anim.modes(R.normalize(a['steps']))}, []
    raise ValueError(f'неизвестная команда {cmd}')

def call_json(cmd, args_json, blobs=()):
    """для Pyodide: аргументы — JSON-строка, ответ — (JSON-строка, список memoryview)"""
    try:
        res, out = call(cmd, json.loads(args_json or '{}'), [b.to_bytes() if hasattr(b, 'to_bytes') else bytes(b) for b in blobs])
        return json.dumps(res, ensure_ascii=False), list(out)
    except Exception as e:
        import traceback
        return json.dumps({'error': str(e) or e.__class__.__name__, 'trace': traceback.format_exc()[-1500:]}, ensure_ascii=False), []
