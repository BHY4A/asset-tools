"""«Неон: вывеска» — ночная стена с неоновой трубкой-сюжетом утилиты и наклонным «выдавленным» заголовком.

Трубка: ядро почти белое, вокруг цветное свечение в три радиуса, тень трубки на стене, держатели; часть сегментов
мерцает. Стена — кирпич, психоделические волны (как титры Hotline Miami) или закат в полоску. Сверху — VHS-строки.
"""
import math
import numpy as np, cv2
from PIL import Image, ImageDraw
from ..params import Param, Spec
from ..core import Ctx, hexc, fbm, font, polyline, vignette, screen
from .. import motifs

PALETTES = {
    'ночь':     dict(dark=True,  wall=('#14061f', '#2b0b3d'), mortar='#07020b', tube='#ff2fa8', tube2='#22e8ff', text=('#ffe14a', '#ff2fa8'), extrude='#3a0a52', outline='#22e8ff', waves=('#2b0b44', '#ff2fa8', '#12041e', '#22e8ff')),
    'кислота':  dict(dark=True,  wall=('#081a12', '#0f2e22'), mortar='#020805', tube='#7cff3c', tube2='#ff3cd0', text=('#e8ff3c', '#ff3cd0'), extrude='#123a20', outline='#00ffd5', waves=('#0b2a18', '#7cff3c', '#081a12', '#ff3cd0')),
    'полдень':  dict(dark=False, wall=('#ffd6ea', '#ffb3d6'), mortar='#f29cc6', tube='#ff2fa8', tube2='#00a3c4', text=('#ffe14a', '#ff2fa8'), extrude='#7a1f63', outline='#00a3c4', waves=('#ffd6ea', '#ff7ac0', '#fff1b8', '#7ae8ff')),
    'мята':     dict(dark=False, wall=('#d6fff1', '#b5f2de'), mortar='#8edfc4', tube='#ff3f9f', tube2='#0090b0', text=('#fff27a', '#ff3f9f'), extrude='#1f5f55', outline='#0090b0', waves=('#d6fff1', '#7fe0c4', '#fff6c8', '#ff9fd0')),
}
WORDS = {'sapr-labs': 'ТОК ЯКОРЯ', 'krrs-robot': 'БАЛАНС', 'op-coursework': 'ПЕРЕДАЧА', 'eco-pdv': 'ВЫБРОС', 'нет': 'НОЧЬ'}

SPEC = Spec('neonsign', [
    Param('app', 'sapr-labs', kind='choice', choices=motifs.APPS + ['нет'], group='сюжет', help='что изображает трубка', rand=False),
    Param('palette', 'ночь', kind='choice', choices=list(PALETTES), group='сюжет', help='ночь/кислота — тёмные, полдень/мята — светлые'),
    Param('width', 1920, 320, 4096, group='сюжет', help='ширина, px', rand=False), Param('height', 1200, 240, 4096, group='сюжет', help='высота, px', rand=False),
    Param('backdrop', 'кирпич', kind='choice', choices=['кирпич', 'волны', 'закат'], group='стена', help='что за вывеской'),
    Param('brick', 1.0, 0.0, 2.0, group='стена', help='заметность кирпича'), Param('waves', 14, 4, 40, group='стена', help='число колец волн', rand=(6, 26)),
    Param('swirl', 1.0, 0.0, 3.0, group='стена', help='закрутка волн'), Param('rain', 0.0, 0.0, 1.0, group='стена', help='дождь', rand=(0.0, .6)),
    Param('tube', 1.0, 0.0, 1.5, group='неон', help='яркость трубки', rand=(.7, 1.3)), Param('tube_width', 1.0, .4, 3.0, group='неон', help='толщина трубки', rand=(.7, 1.6)),
    Param('glow', 1.0, 0.0, 3.0, group='неон', help='свечение', rand=(.6, 1.8)), Param('flicker', .12, 0.0, .8, group='неон', help='доля мигающих сегментов', rand=(0.0, .35)),
    Param('sign_x', .72, .3, .85, group='неон', help='где вывеска по горизонтали', rand=(.6, .8)), Param('sign_scale', .85, .4, 1.3, group='неон', help='размер вывески', rand=(.6, 1.0)),
    Param('title', 'авто', group='заголовок', help='текст; «авто» — по утилите; пусто — без заголовка'),
    Param('title_size', 1.0, .3, 2.0, group='заголовок', help='размер', rand=(.7, 1.3)), Param('title_angle', -8.0, -25.0, 25.0, group='заголовок', help='наклон, °', rand=(-14.0, 4.0)),
    Param('extrude', 14, 0, 40, group='заголовок', help='глубина «выдавливания», слоёв', rand=(6, 24)),
    Param('vhs', .5, 0.0, 1.0, group='экран', help='VHS-строки'), Param('aberration', 3, 0, 12, group='экран', help='расслоение каналов, px', rand=(0, 6)),
    Param('vignette', 1.0, 0.0, 2.0, group='экран', help='виньетка'),
    Param('phase', 0.0, 0.0, 1.0, group='анимация', help='фаза мерцания и волн (0…1 — петля)', rand=False),
], {
    'ночь': {}, 'волны': dict(backdrop='волны', title_angle=-12), 'кислота': dict(palette='кислота', backdrop='волны', swirl=2),
    'полдень': dict(palette='полдень', backdrop='закат', vhs=.25), 'мята': dict(palette='мята', backdrop='волны', vhs=.25),
    'дождь': dict(rain=.6, flicker=.3), 'без текста': dict(title=''),
}, title='Неон: вывеска', flags={'anim': 'phase'}, about='Неоновая трубка-сюжет на стене, наклонный выдавленный заголовок, волны в духе Hotline Miami, VHS')

def _wall(c, P, pal, W, H):
    u = W / 1920; a, b = hexc(pal['wall'][0]), hexc(pal['wall'][1])
    Y = np.linspace(0, 1, H)[:, None, None]; img = np.broadcast_to(a * (1 - Y) + b * Y, (H, W, 3)).astype(np.float32).copy()
    bd = P['backdrop']
    if bd == 'кирпич':
        bh, bw = int(54 * u), int(118 * u); m = np.ones((H, W), np.float32); tone = np.zeros((H, W), np.float32)
        for r in range(H // bh + 2):
            y0 = r * bh; off = (bw // 2) * (r % 2)
            cv2.line(m, (0, y0), (W, y0), 0, max(1, int(5 * u)))
            for x in range(-bw, W + bw, bw):
                xx = x + off; cv2.line(m, (xx, y0), (xx, y0 + bh), 0, max(1, int(5 * u)))
                cv2.rectangle(tone, (xx, y0), (xx + bw, y0 + bh), float(c.R.uniform(-.5, .5)), -1)
        m = cv2.GaussianBlur(m, (0, 0), 1.2 * u); rough = fbm(c, H, W, 6 * u, 3)
        k = P['brick']
        img = img * (1 + (tone[..., None] * .18 + (rough[..., None] - .5) * .25) * k)
        img = img * (1 - (1 - m[..., None]) * .55 * k) + hexc(pal['mortar']) * (1 - m[..., None]) * .55 * k
    elif bd == 'волны':
        Yg, Xg = np.mgrid[0:H, 0:W].astype(np.float32); cx, cy = W * .3, H * 1.12
        r = np.sqrt((Xg - cx) ** 2 + (Yg - cy) ** 2) / max(W, H); th = np.arctan2(Yg - cy, Xg - cx)
        v = r * P['waves'] + P['swirl'] * .25 * np.sin(th * 3 + r * 8) + P['phase']
        band = (np.floor(v * 2) % 4).astype(np.int32)
        cols = np.array([hexc(x) for x in pal['waves']], np.float32)
        img = cols[band] * (1 - .25 * np.clip(r * 1.4, 0, 1))[..., None]
        img = cv2.GaussianBlur(img, (0, 0), 1.0 * u)
    else:
        sky = np.array([hexc(x) for x in pal['waves']], np.float32)
        t = np.linspace(0, 1, H); img = np.broadcast_to(np.stack([np.interp(t, [0, .45, .62, 1], sky[[2, 1, 0, 0], i]) for i in range(3)], 1)[:, None], (H, W, 3)).astype(np.float32).copy()
        cx, cy, R = W * .3, H * .62, H * .26
        Yg, Xg = np.mgrid[0:H, 0:W].astype(np.float32); d = np.sqrt((Xg - cx) ** 2 + (Yg - cy) ** 2)
        disc = np.clip(R - d, 0, 1) * (np.sin((Yg - cy) / (R * .06) - P['phase'] * 6.283) > -.3 + (Yg - cy) / R * 1.2)
        img = img * (1 - disc[..., None]) + mix_v(hexc(pal['text'][0]), hexc(pal['text'][1]), np.clip((Yg - cy + R) / (2 * R), 0, 1)) * disc[..., None]
    return np.clip(img, 0, 1)

def mix_v(a, b, t): return a * (1 - t[..., None]) + b * t[..., None]

def _tube(c, P, pal, W, H, u):
    """маски: ядро, цвет; сегменты мерцают"""
    core = np.zeros((H, W), np.float32); col = np.zeros((H, W, 3), np.float32); shadow = np.zeros((H, W), np.float32)
    s = P['sign_scale']; base = H * (.5 + .38 * s); x = P['sign_x'] * W
    segs = motifs.lines(P['app'], W, H, base, x, u * s) if P['app'] != 'нет' else []
    if not segs:   # «нет» — кольца и молния
        cx, cy, R = x, H * .45, H * .22 * s
        segs = [[(cx + R * math.cos(a), cy + R * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 60)],
                [(cx - R * .3, cy - R * .7), (cx + R * .1, cy - R * .05), (cx - R * .15, cy + .05 * R), (cx + R * .3, cy + R * .7)]]
    # центрировать по вертикали в кадре
    ys = [p[1] for sg in segs for p in sg]; xs = [p[0] for sg in segs for p in sg]
    dy = H * .52 - (min(ys) + max(ys)) / 2; dx = min(0, W * .97 - max(xs)) + max(0, W * .45 - min(xs))
    segs = [[(px + dx, py + dy) for px, py in sg] for sg in segs]
    th = max(2, int(5 * u * P['tube_width'] * s))
    for i, sg in enumerate(segs):
        tc = hexc(pal['tube'] if i % 3 else pal['tube2'])
        lvl = 1.0
        fr = c.R.random()
        if fr < P['flicker']:
            lvl = .15 + .85 * (.5 + .5 * math.sin(2 * math.pi * (P['phase'] * 3 + c.R.random())))
        m = np.zeros((H, W), np.float32); polyline(m, sg, 1.0, th)
        core = np.maximum(core, m * lvl); col = np.maximum(col, m[..., None] * tc * lvl)
        sh = np.zeros((H, W), np.float32); polyline(sh, [(p[0] + 14 * u, p[1] + 18 * u) for p in sg], 1.0, th); shadow = np.maximum(shadow, sh)
        if len(sg) > 6 and c.R.random() < .6:   # держатели
            for k in (len(sg) // 4, 3 * len(sg) // 4):
                px, py = sg[k]; cv2.rectangle(shadow, (int(px - 4 * u), int(py - 4 * u)), (int(px + 4 * u), int(py + 16 * u)), 1, -1)
    return core, col, shadow

def _title(P, pal, W, H, u):
    txt = WORDS.get(P['app'], 'НОЧЬ') if P['title'] == 'авто' else P['title']
    if not txt: return None
    f = font('arcade', 120 * u * P['title_size'])
    pad = int(60 * u); tw = int(f.getlength(txt)) + pad * 2; th = int(f.size * 1.6) + pad * 2
    lay = Image.new('RGBA', (tw + int(P['extrude'] * 3 * u) + pad, th + int(P['extrude'] * 3 * u) + pad), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    ex = hexc(pal['extrude']); n = int(P['extrude'])
    for k in range(n, 0, -1):
        t = k / max(1, n); colk = tuple(int(v * 255 * (1 - .35 * t)) for v in ex) + (255,)
        d.text((pad + k * 2.2 * u, pad + k * 2.6 * u), txt, font=f, fill=colk)
    oc = tuple(int(v * 255) for v in hexc(pal['outline'])) + (255,)
    d.text((pad, pad), txt, font=f, fill=oc, stroke_width=max(2, int(5 * u)), stroke_fill=oc)
    # заливка — вертикальный градиент
    mask = Image.new('L', lay.size, 0); ImageDraw.Draw(mask).text((pad, pad), txt, font=f, fill=255)
    a, b = hexc(pal['text'][0]), hexc(pal['text'][1]); hh = lay.size[1]
    grad = np.zeros((hh, lay.size[0], 3), np.float32); tt = np.clip((np.arange(hh) - pad) / (f.size * 1.1), 0, 1)[:, None, None]
    grad[:] = a * (1 - tt) + b * tt; gi = Image.fromarray((grad * 255).astype(np.uint8)).convert('RGBA'); lay.paste(gi, (0, 0), mask)
    lay = lay.rotate(P['title_angle'], resample=Image.BICUBIC, expand=True)
    return np.asarray(lay).astype(np.float32) / 255

def apply(P, seed=7):
    c = Ctx(seed); W, H = int(P['width']), int(P['height']); u = W / 1920; pal = PALETTES[P['palette']]; dark = pal['dark']
    img = _wall(c, P, pal, W, H)
    core, col, shadow = _tube(Ctx(seed + 1), P, pal, W, H, u)
    k = P['tube'] * (1 - .1 * (.5 + .5 * math.sin(2 * math.pi * P['phase'] * 2))); g = P['glow']   # трубка слегка «гудит»
    sh = cv2.GaussianBlur(shadow, (0, 0), 6 * u)[..., None]
    img = img * (1 - sh * (.55 if dark else .3))
    glow = (cv2.GaussianBlur(col, (0, 0), 6 * u) * 1.6 + cv2.GaussianBlur(col, (0, 0), 22 * u) * 1.1 + cv2.GaussianBlur(col, (0, 0), 70 * u) * .8) * g * k
    img = screen(img, np.clip(glow * (1 if dark else .45), 0, 1))
    tubec = np.clip(col * 1.2 + core[..., None] * .55 * k, 0, 1) if dark else np.clip(col * .92 + core[..., None] * .12 * k, 0, 1)
    a = np.clip(core * 1.4, 0, 1)[..., None]
    img = img * (1 - a) + tubec * a
    hot = cv2.GaussianBlur(core, (0, 0), .8 * u)[..., None] * .5 * k
    if dark: img = screen(img, hot * np.array([1, .97, 1], np.float32))
    t = _title(P, pal, W, H, u)
    if t is not None:
        th, tw = t.shape[:2]; x0, y0 = int(.05 * W), int(.08 * H)
        x1, y1 = min(W, x0 + tw), min(H, y0 + th); sub = t[:y1 - y0, :x1 - x0]
        al = sub[..., 3:4]
        glow_t = cv2.GaussianBlur(sub[..., :3] * al, (0, 0), 14 * u) * .6 * g
        reg = img[y0:y1, x0:x1]; reg = screen(reg, np.clip(glow_t, 0, 1)); img[y0:y1, x0:x1] = reg * (1 - al) + sub[..., :3] * al
    if P['rain'] > 0:
        r = np.zeros((H, W), np.float32)
        for _ in range(int(900 * P['rain'] * u * u)):
            x, y = c.R.uniform(0, W), (c.R.uniform(0, H) + P['phase'] * H * 3) % H; L = c.R.uniform(20, 60) * u
            cv2.line(r, (int(x), int(y)), (int(x - L * .12), int(y + L)), float(c.R.uniform(.2, .6)), 1, cv2.LINE_AA)
        img = screen(img, (r[..., None] * (np.array([.8, .85, 1.0]) if dark else np.array([1, 1, 1])) * .6).astype(np.float32))
    if P['vhs'] > 0:
        img = img * (1 - P['vhs'] * .22 * ((np.arange(H)[:, None] // max(1, int(2 * u))) % 2))[..., None]
    ab = int(P['aberration'] * u)
    if ab: img = np.dstack([np.roll(img[..., 0], ab, 1), img[..., 1], np.roll(img[..., 2], -ab, 1)])
    img = img * (vignette(H, W, .5 * P['vignette']) if dark else 1 - (1 - vignette(H, W, .5 * P['vignette'])) * .3)[..., None]
    return np.clip(img, 0, 1)
