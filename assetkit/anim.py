"""Анимация цепочки: петля по фазе (у генераторов с параметром phase), мерцание зерна или плавный переход параметров.

  фаза    — phase идёт 0 → 1, последний кадр стыкуется с первым (сетка «Эфира» едет, неон мигает, волны бегут);
  зерно   — меняется только зерно случайности: брызги, шум, снег живут, композиция стоит;
  переход — числовые параметры выбранного шага плавно идут к целевым и обратно (петля «туда-обратно»).
"""
import io, math
import numpy as np
from PIL import Image
from .recipe import run
from .registry import get
from .core import to_u8, flatten

def modes(steps):
    m = ['зерно', 'переход']
    if any(get(s['tool']).spec.flags.get('anim') == 'phase' for s in steps if s.get('on', True)): m.insert(0, 'фаза')
    return m

def frames(steps, n=24, mode='фаза', photo=None, max_side=None, step_index=0, target=None, progress=None):
    out = []; n = max(2, int(n))
    for i in range(n):
        t = i / n; st = [dict(s, params=dict(s.get('params', {}))) for s in steps]
        if mode == 'фаза':
            for s in st:
                if get(s['tool']).spec.flags.get('anim') == 'phase': s['params']['phase'] = t
        elif mode == 'зерно':
            for s in st: s['seed'] = int(s.get('seed', 7)) + i
        else:
            k = .5 - .5 * math.cos(2 * math.pi * t)      # туда и обратно, плавно
            s = st[step_index]; spec = get(s['tool']).spec; base = spec.defaults(); base.update(s['params'])
            for name, v in (target or {}).items():
                prm = spec.by.get(name)
                if prm and prm.kind in ('int', 'float') and name not in ('width', 'height', 'size'):
                    val = base[name] + (v - base[name]) * k
                    s['params'][name] = int(round(val)) if prm.kind == 'int' else val
        out.append(run(st, photo, max_side))
        if progress: progress(i + 1, n)
    return out

def encode(fr, fmt='gif', fps=12):
    ims = [Image.fromarray(to_u8(flatten(f))) for f in fr]
    b = io.BytesIO(); dur = int(1000 / max(1, fps))
    if fmt == 'webp':
        ims[0].save(b, 'WEBP', save_all=True, append_images=ims[1:], duration=dur, loop=0, quality=72, method=4)
    else:
        pal = [im.convert('P', palette=Image.ADAPTIVE, colors=255) for im in ims]
        pal[0].save(b, 'GIF', save_all=True, append_images=pal[1:], duration=dur, loop=0, disposal=2, optimize=False)
    return b.getvalue()
