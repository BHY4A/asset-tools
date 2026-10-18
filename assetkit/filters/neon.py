"""Неон: градиентная карта заката по яркости, неоновые контуры со свечением, VHS-строки."""
import numpy as np, cv2
from ..params import Param, Spec
from ..core import Ctx, hexc, fbm, wash_mask, splatter, gesture, pollock, grain, lum, saliency

SPEC = Spec('neon', [
    Param('c0', '#12041e', group='градиент', help='цвет теней'), Param('c1', '#3b0a5c', group='градиент', help=''),
    Param('c2', '#b0177f', group='градиент', help=''), Param('c3', '#ff4f8f', group='градиент', help=''),
    Param('c4', '#ff9a3c', group='градиент', help=''), Param('c5', '#ffe14a', group='градиент', help='цвет светов'),
    Param('gamma', 1.0, .4, 2.5, group='градиент', help='сдвиг градиента к теням / светам'),
    Param('glow_color', '#22e8ff', group='свечение', help='цвет неоновых контуров'),
    Param('glow', 1.0, 0.0, 3.0, group='свечение', help='сила свечения контуров'),
    Param('edges', 50, 10, 150, group='свечение', help='порог контуров: меньше — больше линий'),
    Param('vhs_lines', .28, 0.0, .8, group='экран', help='VHS-строки'),
    Param('shift', 1.0, 0.0, 6.0, group='экран', help='сдвиг красного канала'),
    Param('grain', .035, 0.0, .15, group='экран', help='зерно'),
], {
    'закат': {},
    'океан': dict(c1='#0a2a5c', c2='#1777b0', c3='#36d1c4', c4='#b6f0a0', c5='#fffbe0', glow_color='#ff5fd2'),
    'кислота': dict(c1='#1a3a00', c2='#5ac800', c3='#e8ff3c', c4='#ff3cd0', c5='#ffffff', glow=1.6, glow_color='#00ffd5'),
    'полночь': dict(gamma=1.6, glow=1.8, vhs_lines=.45),
}, title='Неон', about='Градиентная карта заката, неоновые контуры, VHS-строки')

def apply(img, p, seed=7):
    c = Ctx(seed); h, w = img.shape[:2]; L = cv2.GaussianBlur(lum(img), (0, 0), .8) ** p['gamma']
    xs = np.array([0, .28, .5, .7, .86, 1]); cs = np.array([hexc(p[f'c{i}']) for i in range(6)])
    x = np.dstack([np.interp(L, xs, cs[:, i]) for i in range(3)])
    e = cv2.Canny((L * 255).astype(np.uint8), int(p['edges']), int(p['edges'] * 2.6)).astype(np.float32) / 255
    glow = (cv2.GaussianBlur(e, (0, 0), 3) * 2.5 + cv2.GaussianBlur(e, (0, 0), 10) * 2) * p['glow']
    x = 1 - (1 - x) * (1 - np.clip(glow, 0, 1)[..., None] * hexc(p['glow_color']) * .85)
    x *= (1 - p['vhs_lines'] * ((np.arange(h)[:, None] // 2) % 2))[..., None]
    s = int(round(p['shift'] * max(2, w // 400)))
    if s: x = np.dstack([np.roll(x[..., 0], s, axis=1), x[..., 1], x[..., 2]])
    x += grain(c, h, w, p['grain'])[..., None]
    return np.clip(x, 0, 1)
