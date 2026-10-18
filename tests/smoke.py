"""Быстрая проверка: каждый инструмент рисует, пресеты применяются, анимация по фазе действительно двигается.
   python tests/smoke.py"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from assetkit.registry import TOOLS
from assetkit import anim

def main():
    rng = np.random.default_rng(1); photo = np.clip(rng.random((180, 240, 3)).astype(np.float32) * .3 + np.linspace(0, .7, 240)[None, :, None], 0, 1)
    bad = 0
    for t in TOOLS.values():
        for name in [None] + list(t.spec.presets):
            p = t.spec.defaults()
            if name: p.update(t.spec.presets[name])
            if 'width' in p and t.kind == 'gen': p['width'], p['height'] = 240, 160
            if t.id == 'icon': p['size'] = 64
            if t.id == 'tiles': p['size'] = 64
            if t.id == 'card': p['width'], p['height'] = 300, 160
            t0 = time.time()
            try:
                out = t.run(photo if t.kind == 'filter' else None, p, 3)
                ok = out.ndim == 3 and out.shape[2] in (3, 4) and np.isfinite(out).all() and 0 <= out.min() and out.max() <= 1
            except Exception as e:
                ok = False; print('  ОШИБКА', t.id, name, e)
            if not ok: bad += 1
            print(f'{"ok " if ok else "BAD"} {t.id:<10} {name or "по умолчанию":<20} {time.time() - t0:5.2f} с')
        if t.spec.flags.get('anim') == 'phase':
            p = {'width': 200, 'height': 130} if 'width' in t.spec.by else {}
            fr = anim.frames([{'tool': t.id, 'params': p, 'seed': 3}], 3, 'фаза')
            moving = float(np.abs(fr[0] - fr[1]).mean()) > 1e-4
            print(f'{"ok " if moving else "BAD"} {t.id:<10} анимация по фазе'); bad += not moving
    print('\nвсё в порядке' if not bad else f'\nпроблем: {bad}'); return bad

if __name__ == '__main__': sys.exit(1 if main() else 0)
