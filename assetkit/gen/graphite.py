"""«Графит: чертёж» — ночная лаборатория: точечная сетка, светящийся чертёж сюжета утилиты с размерными линиями,
метками и шкалами по краям, мягкое свечение под шапкой. Светлая тема — та же логика на светлом листе."""
import math
import numpy as np, cv2
from PIL import Image, ImageDraw
from ..params import Param, Spec
from ..core import Ctx, hexc, polyline, font, screen, vignette, draw_text
from .. import motifs

NOTES = {
    'sapr-labs': ['ω = 2πn/60', 'Tм ≥ 4Tэ', 'U = 110 В', 'LAФЧХ', 'Kп = 12,4'],
    'krrs-robot': ['θ, ψ, φ', 'K = [−0,71 −39,5]', 'λmax = 5,735', 'R = 0,1 м', 'LQR'],
    'op-coursework': ['aw = 160 мм', 'z₁/z₂ = 25/56', 'm = 2,5', 'σH ≤ [σ]H', 'Ø 40 k6'],
    'eco-pdv': ['H = 30 м', 'Xmax = 171 м', 'Cmax = 0,197', 'ПДК м.р.', 'u = 1 м/с'],
    'нет': ['x = 0', 'y = 0', 'A1', 'B2', '1:1'],
}

SPEC = Spec('graphite', [
    Param('app', 'sapr-labs', kind='choice', choices=motifs.APPS + ['нет'], group='сюжет', help='что начерчено', rand=False),
    Param('theme', 'тёмная', kind='choice', choices=['тёмная', 'светлая'], group='сюжет', help='тема'),
    Param('width', 1920, 320, 4096, group='сюжет', help='ширина, px', rand=False), Param('height', 1200, 240, 4096, group='сюжет', help='высота, px', rand=False),
    Param('accent', 'авто', group='цвет', help='цвет линий; «авто» — цвет утилиты'),
    Param('dots', 22, 8, 64, group='сетка', help='шаг точечной сетки, px', rand=(14, 36)), Param('dot_alpha', 1.0, 0.0, 2.5, group='сетка', help='заметность точек'),
    Param('fade', .7, 0.0, 1.0, group='сетка', help='растворение сетки к краям'), Param('major', 5, 0, 10, group='сетка', help='каждая N-я линия — крупная сетка (0 — нет)'),
    Param('drawing', 1.0, 0.0, 1.5, group='чертёж', help='яркость чертежа', rand=(.6, 1.2)), Param('glow', 1.0, 0.0, 3.0, group='чертёж', help='свечение линий', rand=(.4, 1.8)),
    Param('draw_x', .72, .3, .85, group='чертёж', help='где чертёж по горизонтали', rand=(.62, .8)),
    Param('dims', 1.0, 0.0, 2.0, group='чертёж', help='размерные линии и подписи'), Param('scales', 1.0, 0.0, 2.0, group='чертёж', help='шкалы по краям'),
    Param('halo', 1.0, 0.0, 2.5, group='свет', help='свечение под шапкой'), Param('scan', 0.0, 0.0, 1.0, group='свет', help='луч развёртки', rand=(0.0, .5)),
    Param('vignette', 1.0, 0.0, 2.0, group='свет', help='виньетка'),
], {
    'тёмная': {}, 'светлая': dict(theme='светлая'), 'чистая сетка': dict(drawing=0, dims=0, scales=.6),
    'синька': dict(accent='#9fd0ff', dots=28, major=4, glow=1.6), 'осциллограф': dict(accent='#7dff9a', scan=.5, glow=2.0, dims=.5),
}, title='Графит: чертёж', about='Точечная сетка, светящийся чертёж сюжета с размерами и шкалами — ночная лаборатория')

def _arrow(m, a, b, th, u):
    polyline(m, [a, b], 1.0, th); ang = math.atan2(b[1] - a[1], b[0] - a[0]); L = 9 * u
    for p, s in ((a, 1), (b, -1)):
        for d in (.35, -.35):
            polyline(m, [p, (p[0] + s * L * math.cos(ang + d), p[1] + s * L * math.sin(ang + d))], 1.0, th)

def apply(P, seed=7):
    c = Ctx(seed); W, H = int(P['width']), int(P['height']); u = W / 1920; dark = P['theme'] == 'тёмная'; app = P['app']
    acc = hexc(P['accent'] if str(P['accent']).startswith('#') else motifs.ACCENT.get(app, motifs.ACCENT['нет'])[1 if dark else 0])
    bg = (acc * .04 + hexc('#08090c') * .96) if dark else (acc * .02 + hexc('#f7f8fa') * .98)
    img = np.ones((H, W, 3), np.float32) * bg
    Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
    # свечение под шапкой
    if P['halo'] > 0:
        g = np.exp(-(((X - W / 2) / (W * .32)) ** 2 + ((Y + H * .05) / (H * .28)) ** 2)) * P['halo']
        img = screen(img, g[..., None] * acc * (.38 if dark else .12)) if dark else img * (1 - g[..., None] * .1) + acc * g[..., None] * .1
    # точечная сетка
    step = max(4, int(P['dots'] * u)); dots = np.zeros((H, W), np.float32)
    dots[step // 2::step, step // 2::step] = 1
    dots = cv2.dilate(dots, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(2, int(2.4 * u)),) * 2))
    if P['major'] > 0:
        maj = np.zeros((H, W), np.float32); ms = step * int(P['major'])
        for yy in range(step // 2, H, ms): cv2.line(maj, (0, yy), (W, yy), .35, 1)
        for xx in range(step // 2, W, ms): cv2.line(maj, (xx, 0), (xx, H), .35, 1)
        dots = np.maximum(dots, maj)
    fade = 1 - P['fade'] * np.clip(np.sqrt(((X / W - .5) / .62) ** 2 + ((Y / H - .1) / .95) ** 2), 0, 1)
    da = dots * fade * (.13 if dark else .16) * P['dot_alpha']
    dc = np.array([1, 1, 1], np.float32) if dark else hexc('#141e2d')
    img = img * (1 - da[..., None]) + dc * da[..., None]
    # чертёж
    lay = np.zeros((H, W), np.float32); thin = np.zeros((H, W), np.float32)
    base = H * .86; x0 = P['draw_x'] * W
    segs = motifs.lines(app, W, H, base, x0, u * .9) if app != 'нет' else []
    for sg in segs: polyline(lay, sg, 1.0, 1.6 * u)
    pil = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(pil); fm = font('mono', 15 * u)
    if segs and P['dims'] > 0:
        xs = [p[0] for sg in segs for p in sg]; ys = [p[1] for sg in segs for p in sg]
        l, r, t, b = min(xs), max(xs), min(ys), max(ys)
        _arrow(thin, (l, b + 40 * u), (r, b + 40 * u), 1.1 * u, u); polyline(thin, [(l, b + 8 * u), (l, b + 52 * u)], 1.0, u); polyline(thin, [(r, b + 8 * u), (r, b + 52 * u)], 1.0, u)
        _arrow(thin, (r + 40 * u, t), (r + 40 * u, b), 1.1 * u, u); polyline(thin, [(r + 8 * u, t), (r + 52 * u, t)], 1.0, u); polyline(thin, [(r + 8 * u, b), (r + 52 * u, b)], 1.0, u)
        dr.text(((l + r) / 2 - 30 * u, b + 46 * u), f'{int((r - l) / u)}', font=fm, fill=200)
        notes = NOTES.get(app, NOTES['нет'])
        for i, n in enumerate(notes[:4]):
            px, py = l + (r - l) * c.R.uniform(.1, .9), t + (b - t) * c.R.uniform(.1, .8)
            qx, qy = px - (140 + 30 * i) * u, py - (60 + 20 * i) * u
            polyline(thin, [(px, py), (qx, qy), (qx - 110 * u, qy)], 1.0, u); cv2.circle(thin, (int(px), int(py)), max(2, int(3 * u)), 1.0, -1, cv2.LINE_AA)
            draw_text(dr, (qx - 108 * u, qy - 20 * u), n, 'mono', 15 * u, 230)
    if P['scales'] > 0:
        for i in range(0, W, step):
            L = 10 * u if (i // step) % 5 else 20 * u
            polyline(thin, [(i + step // 2, H - 1), (i + step // 2, H - L)], .6, u)
        for j in range(0, H, step):
            L = 10 * u if (j // step) % 5 else 20 * u
            polyline(thin, [(W - 1, j + step // 2), (W - L, j + step // 2)], .6, u)
        fs = font('mono', 12 * u)
        for k, i in enumerate(range(0, W, step * 5)): dr.text((i + step // 2 + 3 * u, H - 40 * u), str(k * 50), font=fs, fill=150)
    txt = np.asarray(pil).astype(np.float32) / 255
    thin = np.maximum(thin * P['dims'] * .75, txt * P['dims'] * .85)
    k = P['drawing']
    if dark:
        glow = (cv2.GaussianBlur(lay, (0, 0), 4 * u) * 1.2 + cv2.GaussianBlur(lay, (0, 0), 16 * u) * .9) * P['glow']
        img = screen(img, np.clip(glow * .55 * k, 0, 1)[..., None] * acc)
        img = screen(img, np.clip(lay * .95 * k, 0, 1)[..., None] * (acc * .6 + .4))
        img = screen(img, np.clip(thin * .55, 0, 1)[..., None] * (acc * .5 + .5))
    else:
        glow = cv2.GaussianBlur(lay, (0, 0), 6 * u) * .35 * P['glow']
        img = img * (1 - np.clip(glow * k, 0, 1)[..., None] * (1 - acc) * .5)
        a = np.clip(lay * .9 * k, 0, 1)[..., None]; img = img * (1 - a) + acc * a
        a = np.clip(thin * .6, 0, 1)[..., None]; img = img * (1 - a) + hexc('#3a4658') * a
    if P['scan'] > 0:
        y = int(H * c.R.uniform(.3, .7)); band = np.exp(-((np.arange(H) - y) / (40 * u)) ** 2)[:, None] * np.ones((1, W))
        img = screen(img, (band[..., None] * acc * .35 * P['scan']).astype(np.float32)) if dark else img
    v = vignette(H, W, .55 * P['vignette'])
    img = img * (v if dark else 1 - (1 - v) * .25)[..., None]
    return np.clip(img, 0, 1)
