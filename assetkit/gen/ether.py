"""Стиль «Эфир»: сцена в духе вейпорвейва, пропущенная через аналоговый сигнал (filters/signal.py).

Сцена: небо-градиент, солнце в полосках, низкополигональные горы, неоновая сетка-пол в перспективе,
каркасный (wireframe) сюжет утилиты — ЛЭП и ЛАЧХ, балансирующий робот, балка с шестернями, трубы с кольцами дыма;
окно «ретро-ОС» с подписью в 「скобках」, широкая надпись по-русски и катаканой, пальмы, звёзды.
Потом кадр проходит через «Сигнал»: сдвиг цветности, чересстрочность, строки развёртки, свечение.

Запуск: python at.py gen ether --preset ночь --apps all
         python at.py anim ether --frames 24   # петля: сетка едет, сигнал мерцает
"""
import math
import numpy as np, cv2
from PIL import Image, ImageDraw
from ..params import Param, Spec
from ..core import hexc, font, draw_text
from ..filters import signal as SIG
from .. import motifs

PALETTES = {
    'пастель':  dict(dark=False, sky=('#bfe9ff', '#ffd9ec', '#ffb3d9'), sun=('#fff27a', '#ff6fb5'), mount=('#c6a8ff', '#ffd0ec'), floor='#ffe6f3',
                     grid='#ff32bb', wire='#00a835', text='#ff32bb', win=('#fff7fb', '#ff32bb', '#00a835'), star='#ffffff', palm='#7a3c8c'),
    'мята':     dict(dark=False, sky=('#d6fff1', '#e9e2ff', '#ffc7e6'), sun=('#ffe9a0', '#ff8acb'), mount=('#7fe0c4', '#c8f5e6'), floor='#eafff7',
                     grid='#00a88f', wire='#ff32bb', text='#008f6c', win=('#f6fffb', '#00a88f', '#ff32bb'), star='#ffffff', palm='#2f6d64'),
    'полночь':  dict(dark=True, sky=('#090322', '#2a0b4a', '#ff4fa3'), sun=('#ffe066', '#ff2f92'), mount=('#3a0f63', '#140629'), floor='#0b0418',
                     grid='#ff3fd0', wire='#3ff2ff', text='#ffd1f2', win=('#1a0d33', '#ff3fd0', '#3ff2ff'), star='#ffe9ff', palm='#05010d'),
    'океан':    dict(dark=True, sky=('#020a1f', '#0b2e5a', '#25c3d8'), sun=('#fff3a8', '#ff5fa8'), mount=('#0b3a63', '#04162b'), floor='#02101f',
                     grid='#2ff3ff', wire='#ff67d4', text='#c9fbff', win=('#071a33', '#2ff3ff', '#ff67d4'), star='#e6ffff', palm='#010712'),
}
APPS = ['sapr-labs', 'krrs-robot', 'op-coursework', 'eco-pdv']
TITLES = {'sapr-labs': ('ТОК ЯКОРЯ', 'ラボ', 'ЛР № 3.exe'), 'krrs-robot': ('РАВНОВЕСИЕ', 'ロボット', 'robot.exe'),
          'op-coursework': ('ПЕРЕДАЧА', 'ギア', 'КП_ОП.exe'), 'eco-pdv': ('ВЫБРОС', 'エコ', 'ПДВ.exe'), 'нет': ('ЭФИР', 'エーテル', 'ether.exe')}

SPEC = Spec('ether', [
    Param('app', 'sapr-labs', kind='choice', choices=APPS + ['нет'], group='сюжет', help='каркасный сюжет утилиты', rand=False),
    Param('palette', 'пастель', kind='choice', choices=list(PALETTES), group='сюжет', help='пастель/мята — светлые, полночь/океан — тёмные'),
    Param('width', 1920, 320, 4096, group='сюжет', help='ширина, px', rand=False), Param('height', 1200, 240, 4096, group='сюжет', help='высота, px', rand=False),
    Param('horizon', .58, .35, .8, group='сцена', help='линия горизонта (доля высоты)', rand=(.5, .66)),
    Param('sun', 1.0, 0.0, 1.0, group='сцена', help='солнце в полосках'), Param('sun_size', .2, .06, .4, group='сцена', help='радиус солнца (доля высоты)', rand=(.12, .28)),
    Param('sun_x', .5, .1, .9, group='сцена', help='солнце по горизонтали', rand=(.25, .75)), Param('sun_stripes', 7, 0, 16, group='сцена', help='прорези в солнце'),
    Param('mountains', 1.0, 0.0, 1.0, group='сцена', help='горы'), Param('stars', 1.0, 0.0, 3.0, group='сцена', help='звёзды (заметнее ночью)'),
    Param('palms', 2, 0, 6, group='сцена', help='пальмы по краям'),
    Param('grid', 1.0, 0.0, 1.5, group='сетка', help='яркость сетки-пола', rand=(.6, 1.3)), Param('grid_lines', 22, 6, 60, group='сетка', help='продольные линии', rand=(12, 34)),
    Param('grid_rows', 16, 4, 40, group='сетка', help='поперечные линии', rand=(8, 24)), Param('glow', 1.0, 0.0, 3.0, group='сетка', help='свечение неона'),
    Param('wire', 1.0, 0.0, 1.3, group='сюжет', help='каркасный сюжет утилиты', rand=(.6, 1.2)), Param('wire_x', .74, .2, .85, group='сюжет', help='где сюжет по горизонтали', rand=(.6, .8)),
    Param('window', 1.0, 0.0, 1.0, group='надписи', help='окно «ретро-ОС»'), Param('title', 'авто', group='надписи', help='широкая надпись; «авто» — по утилите; пусто — без неё'),
    Param('kana', 'авто', group='надписи', help='катакана под надписью; «авто» — по утилите; пусто — без неё'),
    Param('title_size', 1.0, .4, 2.0, group='надписи', help='размер надписи', rand=(.7, 1.3)),
    Param('tracking', .45, 0.0, 1.5, group='надписи', help='разрядка букв (доля кегля) — «широкие» буквы', rand=(.2, .8)),
    Param('signal', 1.0, 0.0, 1.0, group='сигнал', help='сила аналогового сигнала (0 — чистая сцена)', rand=(.6, 1.0)),
    Param('signal_preset', 'розовый закат', kind='choice', choices=list(SIG.PRESETS), group='сигнал', help='пресет фильтра «Сигнал»',
          rand=('розовый закат', 'тёплый эфир', 'неоновый перелив', 'синий час', 'чересстрочка')),
    Param('scan', .35, 0.0, 1.0, group='сигнал', help='строки развёртки поверх', rand=(.1, .5)),
    Param('phase', 0.0, 0.0, 1.0, group='анимация', help='фаза движения сетки (0…1 — одна петля)', rand=False),
], {
    'день': {}, 'мята': dict(palette='мята'), 'ночь': dict(palette='полночь', signal_preset='неоновый перелив'),
    'океан': dict(palette='океан', signal_preset='синий час', sun_x=.3),
    'кассета': dict(signal_preset='выцветшая кассета', signal=.8, palms=0),
    'чистая сцена': dict(signal=0, scan=0),
    'без надписей': dict(window=0, title='', kana=''),
}, title='Эфир: сцена', flags={'anim': 'phase'}, about='Вейпорвейв-сцена (солнце, сетка, каркасный сюжет, окно ретро-ОС) через аналоговый сигнал')

def _glowline(layer, pts, col, th, closed=False):
    cv2.polylines(layer, [np.array(pts, np.int32)], closed, tuple(float(c) for c in col), th, cv2.LINE_AA)

def _wire(app, W, H, base, x, u): return motifs.lines(app, W, H, base, x, u)

def scene(P, seed):
    rng = np.random.default_rng(seed)
    W, H = int(P['width']), int(P['height']); u = W / 1920; pal = PALETTES[P['palette']]; dark = pal['dark']
    hz = int(H * P['horizon'])
    # небо
    Y = np.linspace(0, 1, hz)[:, None, None]; a, b, c = (hexc(x) for x in pal['sky'])
    sky = np.where(Y < .55, a * (1 - Y / .55) + b * (Y / .55), b * (1 - (Y - .55) / .45) + c * ((Y - .55) / .45))
    img = np.zeros((H, W, 3), np.float32); img[:hz] = sky
    # звёзды
    if P['stars'] > 0:
        n = int((260 if dark else 60) * P['stars'] * u * u)
        st = np.zeros((H, W), np.float32)
        for _ in range(n):
            x, y = int(rng.uniform(0, W)), int(rng.uniform(0, hz * .8)); st[y, x] = rng.uniform(.4, 1)
            if rng.random() < .06: cv2.line(st, (x - int(5 * u), y), (x + int(5 * u), y), 1, 1); cv2.line(st, (x, y - int(5 * u)), (x, y + int(5 * u)), 1, 1)
        st = cv2.GaussianBlur(st, (0, 0), .7) * (1 if dark else .7)
        img = 1 - (1 - img) * (1 - st[..., None] * hexc(pal['star']))
    # солнце
    if P['sun'] > 0:
        r = P['sun_size'] * H; cx, cy = P['sun_x'] * W, hz - r * .35
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        disc = np.clip(r - d + 1, 0, 1); t = np.clip((yy - (cy - r)) / (2 * r), 0, 1)
        s0, s1 = hexc(pal['sun'][0]), hexc(pal['sun'][1]); col = s0 * (1 - t[..., None]) + s1 * t[..., None]
        n = int(P['sun_stripes'])
        if n:
            cut = np.ones((H, W), np.float32)
            top = cy - r * .35; span = hz - top
            for k in range(n):
                y0 = top + span * (k / n) ** .85; th = max(2.0, span * .03 * (k + 1) * 1.1)
                cut[int(y0):int(y0 + th)] = 0
            disc *= cut
        halo = np.exp(-np.maximum(d - r, 0) / (r * .5)) * .55 * P['sun']
        img = 1 - (1 - img) * (1 - halo[..., None] * s1 * (np.arange(H)[:, None, None] < hz))
        disc *= P['sun'] * (np.arange(H)[:, None] < hz)
        img = img * (1 - disc[..., None]) + col * disc[..., None]
    # горы — низкополигональные, с каркасом
    lay = np.zeros((H, W, 3), np.float32)
    if P['mountains'] > 0:
        for layer, (k, hh) in enumerate([(9, .2), (13, .12)]):
            xs = np.linspace(-50 * u, W + 50 * u, k); ys = hz - rng.uniform(.25, 1, k) * hh * H
            ys[np.abs(xs - P['sun_x'] * W) < P['sun_size'] * H * 1.1] = hz - .02 * H
            poly = [(xs[0], hz)] + list(zip(xs, ys)) + [(xs[-1], hz)]
            m = np.zeros((H, W), np.float32); cv2.fillPoly(m, [np.array(poly, np.int32)], 1, cv2.LINE_AA)
            yy = np.linspace(0, 1, H)[:, None, None]
            mc = hexc(pal['mount'][0]) * (1 - layer * .25); md = hexc(pal['mount'][1])
            grad = mc * (1 - np.clip((yy - .3) / .4, 0, 1)) + md * np.clip((yy - .3) / .4, 0, 1)
            al = m[..., None] * P['mountains'] * (.92 if layer else .8)
            img = img * (1 - al) + np.broadcast_to(grad, (H, W, 3)) * al
            for i in range(len(xs) - 1):
                _glowline(lay, [(xs[i], ys[i]), (xs[i + 1], ys[i + 1])], hexc(pal['grid']) * .7 * P['mountains'], max(1, int(2 * u)))
                if layer == 1: _glowline(lay, [(xs[i], ys[i]), ((xs[i] + xs[i + 1]) / 2, hz)], hexc(pal['grid']) * .35 * P['mountains'], max(1, int(1.5 * u)))
    # пол
    img[hz:] = hexc(pal['floor'])
    fy = np.linspace(0, 1, H - hz)[:, None, None]; img[hz:] = img[hz:] * (1 - .25 * (1 - fy)) + hexc(pal['sky'][2]) * .25 * (1 - fy)
    g = np.zeros((H, W, 3), np.float32); gc = hexc(pal['grid']) * P['grid']; vx = W / 2
    nl = int(P['grid_lines'])
    for i in range(-nl, nl + 1):
        xb = vx + i * (W / nl) * 1.6; _glowline(g, [(vx + i * W * .012, hz), (xb, H)], gc, max(1, int(2.2 * u)))
    for j in range(0, int(P['grid_rows']) + 1):
        t = ((j + P['phase']) / P['grid_rows']) ** 2.1
        if t <= 0: continue
        y = hz + (H - hz) * t; _glowline(g, [(0, y), (W, y)], gc, max(1, int((1 + 2.4 * t) * u)))
    _glowline(g, [(0, hz), (W, hz)], gc * 1.2, max(1, int(3 * u)))
    lay += g
    # каркасный сюжет
    if P['app'] != 'нет' and P['wire'] > 0:
        wc = hexc(pal['wire']) * P['wire']; wl = np.zeros((H, W, 3), np.float32)
        for pts in _wire(P['app'], W, H, hz, P['wire_x'] * W, u): _glowline(wl, pts, wc, max(1, int(3.2 * u)))
        # тень-заливка под каркасом, чтобы линии читались на солнце
        m = (cv2.dilate(wl.max(2), np.ones((int(9 * u) | 1, int(9 * u) | 1))) > .05).astype(np.float32)
        m = cv2.GaussianBlur(m, (0, 0), 6 * u)[..., None] * (.35 if dark else .18)
        img = img * (1 - m) + (hexc(pal['floor']) if dark else np.array([1, 1, 1], np.float32)) * m
        lay += wl
    # неон: линия + свечение
    if dark:
        glow = cv2.GaussianBlur(lay, (0, 0), 6 * u) * 1.4 * P['glow'] + cv2.GaussianBlur(lay, (0, 0), 18 * u) * .9 * P['glow']
        img = 1 - (1 - img) * (1 - np.clip(lay + glow, 0, 1))
    else:
        glow = cv2.GaussianBlur(lay, (0, 0), 7 * u) * .7 * P['glow']
        a = np.clip(lay.max(2, keepdims=True) * 2.4, 0, 1)
        img = img * (1 - a) + np.clip(lay * 1.2, 0, 1) * a
        img = 1 - (1 - img) * (1 - np.clip(glow * .6, 0, 1))
    # пальмы — силуэты
    for k in range(int(P['palms'])):
        side = k % 2; px = (rng.uniform(.0, .05) if side == 0 else rng.uniform(.93, .99)) * W; base = H + rng.uniform(0, .05) * H
        hgt = rng.uniform(.45, .7) * H; bend = rng.uniform(.05, .12) * W * (1 if side == 0 else -1)
        m = np.zeros((H, W), np.float32); top = None; prev = None
        for t in np.linspace(0, 1, 40):
            x = px + bend * t * t; y = base - hgt * t
            if prev: cv2.line(m, (int(prev[0]), int(prev[1])), (int(x), int(y)), 1, max(2, int((18 - 10 * t) * u)), cv2.LINE_AA)
            prev = (x, y)
        top = prev
        for a in np.linspace(-math.pi + .15, -.15, 8) + rng.normal(0, .08, 8):
            L = rng.uniform(.13, .2) * H; pts = []; x, y = top; ang = a
            for i in range(24):   # лист: выходит вверх-в сторону и под своей тяжестью загибается вниз
                x += math.cos(ang) * L / 24; y += math.sin(ang) * L / 24; ang += (.075 if math.cos(a) > 0 else -.075); pts.append((x, y))
            for i in range(len(pts) - 1):
                cv2.line(m, tuple(map(int, pts[i])), tuple(map(int, pts[i + 1])), 1, max(1, int((14 * math.sin(math.pi * (i + 2) / 26) + 1) * u)), cv2.LINE_AA)
                if i % 2 == 0 and i < 21:   # пёрышки
                    nx, ny = -(pts[i + 1][1] - pts[i][1]), pts[i + 1][0] - pts[i][0]; nn = math.hypot(nx, ny) or 1; ln = (1 - i / 24) * 22 * u
                    cv2.line(m, tuple(map(int, pts[i])), (int(pts[i][0] + nx / nn * ln + (pts[i+1][0]-pts[i][0]) * 2), int(pts[i][1] + abs(ny / nn) * ln + 6 * u)), 1, max(1, int(2 * u)), cv2.LINE_AA)
        img = img * (1 - m[..., None]) + hexc(pal['palm']) * m[..., None]
    return np.clip(img, 0, 1)

def _wide(s): return s if ' ' in s.strip() else ' '.join(s)

def overlay(img, P, seed):
    """окно ретро-ОС, широкая надпись, катакана — текстом через PIL"""
    rng = np.random.default_rng(seed + 1)
    H, W = img.shape[:2]; u = W / 1920; pal = PALETTES[P['palette']]; app = P['app']
    t_auto, k_auto, w_auto = TITLES[app]
    title = t_auto if P['title'] == 'авто' else P['title']; kana = k_auto if P['kana'] == 'авто' else P['kana']
    pil = Image.fromarray((img * 255).astype(np.uint8)).convert('RGBA'); dr = ImageDraw.Draw(pil, 'RGBA')
    def F(kind, sz): return font(kind, sz)
    tc = tuple(int(c * 255) for c in hexc(pal['text']))
    if title:
        f = F('wide', 92 * u * P['title_size']); x, y = int(.06 * W), int(.1 * H)
        def spaced(x, y, col):
            draw_text(dr, (x, y), title, 'wide', f.size, col, P['tracking'])
        for dx, col in [(int(6 * u), (0, 255, 255, 110) if pal['dark'] else (0, 168, 53, 120)), (-int(4 * u), (255, 50, 187, 110))]:
            spaced(x + dx, y, col)
        spaced(x, y, tc + (255,))
        if kana:
            fk = F('wide', 52 * u * P['title_size'])
            dr.text((x + int(4 * u), y + int(110 * u * P['title_size'])), '「' + kana + '」', font=fk, fill=tc + (200,))
    if P['window'] > 0:
        bg, bar, acc = (tuple(int(c * 255) for c in hexc(x)) for x in pal['win'])
        ww, wh = int(420 * u), int(250 * u); x0 = int(.07 * W); y0 = int(P['horizon'] * H - wh - .06 * H)
        al = int(235 * P['window'])
        dr.rectangle([x0 + int(10 * u), y0 + int(10 * u), x0 + ww + int(10 * u), y0 + wh + int(10 * u)], fill=bar + (int(90 * P['window']),))
        dr.rectangle([x0, y0, x0 + ww, y0 + wh], fill=bg + (al,), outline=bar + (255,), width=max(1, int(3 * u)))
        dr.rectangle([x0, y0, x0 + ww, y0 + int(38 * u)], fill=bar + (255,))
        fu = F('round', 19 * u); dr.text((x0 + int(12 * u), y0 + int(8 * u)), w_auto, font=fu, fill=(255, 255, 255, 255))
        for i in range(3):
            bx = x0 + ww - int((32 + i * 30) * u); dr.rectangle([bx, y0 + int(8 * u), bx + int(22 * u), y0 + int(30 * u)], fill=bg + (255,), outline=(255, 255, 255, 255))
        fb = F('wide', 30 * u); dr.text((x0 + int(24 * u), y0 + int(64 * u)), '「 ' + (kana or 'エーテル') + ' 」', font=fb, fill=bar + (255,))
        # полоса загрузки
        px0, py0 = x0 + int(24 * u), y0 + wh - int(70 * u); pw = ww - int(48 * u)
        dr.rectangle([px0, py0, px0 + pw, py0 + int(26 * u)], outline=bar + (255,), width=max(1, int(2 * u)))
        n = int(rng.uniform(8, 15))
        for i in range(n): bx = px0 + int(5 * u) + i * int(22 * u); dr.rectangle([bx, py0 + int(5 * u), bx + int(16 * u), py0 + int(21 * u)], fill=acc + (255,))
        dr.text((px0, py0 + int(34 * u)), 'ЗАГРУЗКА  ' + str(int(n / 18 * 100)) + ' %', font=F('round', 14 * u), fill=bar + (255,))
    return np.asarray(pil.convert('RGB')).astype(np.float32) / 255

def render(P, seed=7):
    img = overlay(scene(P, seed), P, seed)
    if P['signal'] > 0:
        sp = SIG.SPEC.defaults(); sp.update(SIG.PRESETS[P['signal_preset']])
        H, W = img.shape[:2]
        sp.update(frame='исходный', fit='fill', width=W, border=0, osd='', snow=min(sp.get('snow', 0), .2), lowres=max(1.0, sp['lowres'] * W / 1920 * 1.2))
        sig = SIG.apply(img, sp, seed + int(round(P['phase'] * 997)))
        if sig.shape[:2] != (H, W): sig = cv2.resize(sig, (W, H), interpolation=cv2.INTER_CUBIC)
        img = img * (1 - P['signal']) + sig * P['signal']
    if P['scan'] > 0:
        H = img.shape[0]; lines = (np.arange(H) % 3 == 0).astype(np.float32)[:, None, None]
        img = img * (1 - lines * .22 * P['scan'])
    return np.clip(img, 0, 1)

apply = render
