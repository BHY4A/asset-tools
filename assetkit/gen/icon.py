"""«Значок» — иконка утилиты (как в шапке) в разных манерах: плоская, глянец «Лазури», неон, стекло, бумага, пиксели.
Подходит для favicon, apple-touch-icon и иконки приложения. Прозрачный фон за скруглённым квадратом."""
import math
import numpy as np, cv2
from ..params import Param, Spec
from ..core import hexc, screen
from .. import motifs

SPEC = Spec('icon', [
    Param('app', 'sapr-labs', kind='choice', choices=motifs.APPS + ['hub'], group='значок', help='чей значок', rand=False),
    Param('look', 'плоский', kind='choice', choices=['плоский', 'глянец', 'неон', 'стекло', 'бумага', 'пиксели'], group='значок', help='манера'),
    Param('size', 512, 16, 1024, group='значок', help='размер, px', rand=False),
    Param('bg', 'авто', group='цвет', help='цвет плашки; «авто» — цвет утилиты'), Param('fg', '#ffffff', group='цвет', help='цвет рисунка'),
    Param('radius', .19, 0.0, .5, group='форма', help='скругление (.5 — круг)', rand=(.1, .5)), Param('pad', .0, 0.0, .2, group='форма', help='поле вокруг плашки'),
    Param('stroke', 1.0, .5, 2.0, group='форма', help='толщина линий', rand=(.8, 1.4)), Param('shadow', .4, 0.0, 1.0, group='форма', help='тень под плашкой'),
    Param('pixel', 32, 8, 64, group='пиксели', help='разрешение пиксельной манеры', step=8),
], {
    'плоский': {}, 'глянец': dict(look='глянец'), 'неон': dict(look='неон', bg='#12041e', fg='#22e8ff'), 'стекло': dict(look='стекло'),
    'бумага': dict(look='бумага', bg='#ece3cf', fg='#1f1b17', radius=.06), 'пиксели': dict(look='пиксели', radius=0, pixel=24),
    'круглый': dict(radius=.5),
}, title='Значок', about='Иконка утилиты для favicon и ярлыков: плоская, глянец, неон, стекло, бумага, пиксели')

def _rr(S, x, y, w, h, r):
    m = np.zeros((S, S), np.float32); r = int(max(0, min(r, w / 2, h / 2)))
    cv2.rectangle(m, (int(x + r), int(y)), (int(x + w - r), int(y + h)), 1, -1); cv2.rectangle(m, (int(x), int(y + r)), (int(x + w), int(y + h - r)), 1, -1)
    for cx, cy in [(x + r, y + r), (x + w - r, y + r), (x + r, y + h - r), (x + w - r, y + h - r)]: cv2.circle(m, (int(cx), int(cy)), r, 1, -1, cv2.LINE_AA)
    return m

def glyph(app, S, x0, y0, k, stroke=1.0):
    """маска рисунка значка: k — пикселей на единицу 32-сетки"""
    m = np.zeros((S, S), np.float32)
    for it in motifs.ICONS[app]:
        if it[0] == 'line':
            cv2.polylines(m, [np.array([(x0 + px * k, y0 + py * k) for px, py in it[1]], np.float32).round().astype(np.int32)], False, 1.0, max(1, int(round(it[2] * k * stroke))), cv2.LINE_AA)
        elif it[0] == 'circle':
            cv2.circle(m, (int(round(x0 + it[1][0] * k)), int(round(y0 + it[1][1] * k))), int(round(it[2] * k)), 1.0, max(1, int(round(it[3] * k * stroke))), cv2.LINE_AA)
        elif it[0] == 'fill':
            cv2.fillPoly(m, [np.array([(x0 + px * k, y0 + py * k) for px, py in it[1]], np.float32).round().astype(np.int32)], 1.0, cv2.LINE_AA)
    return m

def apply(P, seed=7):
    S0 = int(P['size']); SS = 4 if S0 < 128 else 2; S = S0 * SS   # рисуем крупнее и уменьшаем — чистые края на 16–32 px
    app = P['app']; look = P['look']
    bg = hexc(P['bg'] if str(P['bg']).startswith('#') else motifs.ACCENT.get(app, motifs.ACCENT['hub'])[0]); fg = hexc(P['fg'])
    pad = P['pad'] * S; side = S - 2 * pad; sh_off = P['shadow'] * S * .03
    plate = _rr(S, pad, pad, side, side - sh_off, P['radius'] * side)
    k = (side - sh_off) / 32; gl = glyph(app, S, pad, pad, k, P['stroke'])
    rgb = np.zeros((S, S, 3), np.float32); a = np.zeros((S, S), np.float32)
    if P['shadow'] > 0:
        sh = cv2.GaussianBlur(cv2.warpAffine(plate, np.float32([[1, 0, 0], [0, 1, sh_off]]), (S, S)), (0, 0), S * .015) * .35 * P['shadow']
        a = np.maximum(a, sh)
    Y = np.linspace(0, 1, S)[:, None, None]
    if look == 'плоский':
        body = np.broadcast_to(bg, (S, S, 3)).astype(np.float32)
        body = body * (1 - gl[..., None]) + fg * gl[..., None]
    elif look == 'глянец':
        body = (bg * (1.25 - .45 * Y) + .06).astype(np.float32); body = np.broadcast_to(np.clip(body, 0, 1), (S, S, 3)).copy()
        body = body * (1 - gl[..., None]) + fg * gl[..., None]
        hl = _rr(S, pad + side * .06, pad + side * .04, side * .88, side * .46, P['radius'] * side * .9) * (1 - Y[..., 0] / .5).clip(0, 1) * .55
        body = screen(body, cv2.GaussianBlur(hl, (0, 0), S * .004)[..., None])
        rim = plate - cv2.erode(plate, np.ones((max(2, S // 90),) * 2)); body = screen(body, rim[..., None] * .35)
    elif look == 'неон':
        body = np.broadcast_to(bg, (S, S, 3)).astype(np.float32).copy()
        g = cv2.GaussianBlur(gl, (0, 0), S * .02) * 1.6 + cv2.GaussianBlur(gl, (0, 0), S * .05)
        body = screen(body, np.clip(g, 0, 1)[..., None] * fg); body = body * (1 - gl[..., None]) + (fg * .5 + .5) * gl[..., None]
    elif look == 'стекло':
        body = np.broadcast_to(np.clip(bg * .55 + .45, 0, 1), (S, S, 3)).astype(np.float32).copy()
        body = body * (.92 + .08 * (1 - Y)); body = body * (1 - gl[..., None] * .9) + bg * .7 * gl[..., None] * .9
        rim = plate - cv2.erode(plate, np.ones((max(2, S // 70),) * 2)); body = screen(body, rim[..., None] * .7)
    elif look == 'бумага':
        rng = np.random.default_rng(seed); n = cv2.GaussianBlur(rng.random((S, S)).astype(np.float32), (0, 0), S * .004)
        body = np.broadcast_to(bg, (S, S, 3)).astype(np.float32) * (.94 + .12 * n[..., None])
        wob = cv2.GaussianBlur(gl, (0, 0), S * .003); body = body * (1 - wob[..., None]) + fg * wob[..., None]
    else:  # пиксели
        n = int(P['pixel']); small = cv2.resize(gl, (n, n), interpolation=cv2.INTER_AREA) > .35
        gl2 = cv2.resize(small.astype(np.float32), (S, S), interpolation=cv2.INTER_NEAREST)
        body = np.broadcast_to(bg, (S, S, 3)).astype(np.float32) * (1 - gl2[..., None]) + fg * gl2[..., None]
        pl = cv2.resize((cv2.resize(plate, (n, n), interpolation=cv2.INTER_AREA) > .5).astype(np.float32), (S, S), interpolation=cv2.INTER_NEAREST); plate = pl
    rgb = rgb * (1 - plate[..., None]) + body * plate[..., None]
    a = np.maximum(a * (1 - plate), plate)
    out = np.dstack([rgb, a])
    return cv2.resize(out, (S0, S0), interpolation=cv2.INTER_AREA)

def ico_bytes(app, look='плоский', sizes=(16, 32, 48, 64), **kw):
    """favicon.ico из нескольких размеров"""
    import io
    from PIL import Image
    from ..core import to_u8
    big = apply(dict(SPEC.defaults(), app=app, look=look, size=256, **kw))
    b = io.BytesIO(); Image.fromarray(to_u8(big), 'RGBA').save(b, 'ICO', sizes=[(s, s) for s in sizes]); return b.getvalue()
