"""Сюжеты утилит линиями: ЛЭП и ЛАЧХ, робот-балансир, балка с шестернями, трубы с дымом.
Используются каркасом «Эфира», гравировкой «Стекла», чертежом «Графита», вывесками «Неона»."""
import math
import numpy as np

APPS = ['sapr-labs', 'krrs-robot', 'op-coursework', 'eco-pdv']
NAMES = {'sapr-labs': 'Электропривод', 'krrs-robot': 'Робот-балансир', 'op-coursework': 'Основы проектирования', 'eco-pdv': 'Промышленная экология', 'нет': ''}

def lines(app, W, H, base, x, u):
    """каркас сюжета — список ломаных (точки), масштаб u ~ W/1920"""
    L = []
    if app == 'sapr-labs':
        for (px, h, s) in [(x, .5, 1.0), (x + 260 * u, .34, .7), (x - 300 * u, .3, .6)]:
            hh = h * H; b = base
            l0, r0, l1, r1 = px - 60 * s * u, px + 60 * s * u, px - 12 * s * u, px + 12 * s * u
            L += [[(l0, b), (l1, b - hh)], [(r0, b), (r1, b - hh)]]
            for k in range(6):
                y0, y1 = b - hh * k / 6, b - hh * (k + 1) / 6; a0 = 48 * s * u * (1 - k / 6); a1 = 48 * s * u * (1 - (k + 1) / 6)
                L += [[(px - a0 - 12 * s * u, y0), (px + a1 + 12 * s * u, y1)], [(px + a0 + 12 * s * u, y0), (px - a1 - 12 * s * u, y1)]]
            for yy, arm in [(.82, 110), (.66, 85)]: L.append([(px - arm * s * u, b - hh * yy), (px + arm * s * u, b - hh * yy)])
        # ЛАЧХ над горизонтом
        x0, y0, w, h = x - 560 * u, base - .52 * H, 420 * u, .2 * H
        L.append([(x0, y0 + h), (x0 + w, y0 + h)]); L.append([(x0, y0), (x0, y0 + h)])
        L.append([(x0 + w * t, y0 + h * .2 + h * .6 * (1 / (1 + math.exp(-(t - .55) * 12))) - h * .18 * math.exp(-((t - .4) / .07) ** 2)) for t in np.linspace(0, 1, 60)])
    elif app == 'krrs-robot':
        s = 1.75 * u; cx = x
        for dx in (-70, 70):
            L.append([(cx + dx * s + 44 * s * math.cos(a), base - 44 * s + 44 * s * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 40)])
            for a in np.linspace(0, math.pi, 5)[:-1]:
                L.append([(cx + dx * s - 44 * s * math.cos(a), base - 44 * s - 44 * s * math.sin(a)), (cx + dx * s + 44 * s * math.cos(a), base - 44 * s + 44 * s * math.sin(a))])
        L.append([(cx - 70 * s, base - 44 * s), (cx + 70 * s, base - 44 * s)])
        body = [(cx - 50 * s, base - 60 * s), (cx - 26 * s, base - 300 * s), (cx + 40 * s, base - 304 * s), (cx + 52 * s, base - 56 * s), (cx - 50 * s, base - 60 * s)]
        L.append(body)
        for k in range(1, 6): t = k / 6; L.append([(cx - 50 * s + 24 * s * t, base - 60 * s - 240 * s * t), (cx + 52 * s - 12 * s * t, base - 56 * s - 248 * s * t)])
        L.append([(cx - 30 * s, base - 300 * s), (cx - 30 * s, base - 350 * s), (cx + 44 * s, base - 350 * s), (cx + 44 * s, base - 304 * s)])
        L.append([(cx + 7 * s + 12 * s * math.cos(a), base - 326 * s + 12 * s * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 30)])
        L.append([(cx + 20 * s, base - 350 * s), (cx + 30 * s, base - 420 * s)])
        # дуга угла наклона
        L.append([(cx + 160 * s * math.sin(a), base - 44 * s - 160 * s * math.cos(a)) for a in np.linspace(-.3, .3, 20)])
    elif app == 'op-coursework':
        def gear(c, r, z):
            pts = []
            for i in range(z * 4 + 1):
                a = i * 2 * math.pi / (z * 4); rr = r if (i % 4) in (0, 1) else r * .84; pts.append((c[0] + rr * math.cos(a), c[1] + rr * math.sin(a)))
            L.append(pts); L.append([(c[0] + r * .3 * math.cos(a), c[1] + r * .3 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 30)])
            for a in np.linspace(0, 2 * math.pi, 7)[:-1]: L.append([(c[0] + r * .3 * math.cos(a), c[1] + r * .3 * math.sin(a)), (c[0] + r * .72 * math.cos(a), c[1] + r * .72 * math.sin(a))])
        R1 = .2 * H; gear((x, base - R1 - 20 * u), R1, 22); gear((x - R1 * 1.62, base - R1 * .62 - 20 * u), R1 * .58, 13)
        top = base - .5 * H; L.append([(x - 520 * u, top), (x + 200 * u, top), (x + 200 * u, top + 34 * u), (x - 520 * u, top + 34 * u), (x - 520 * u, top)])
        for k in range(16): L.append([(x - 520 * u + k * 45 * u, top + 34 * u), (x - 497 * u + k * 45 * u, top)])
        L.append([(x - 160 * u, top + 34 * u), (x - 160 * u, top + .14 * H)]); L.append([(x - 200 * u, top + .14 * H), (x - 120 * u, top + .14 * H), (x - 160 * u, top + .2 * H), (x - 200 * u, top + .14 * H)])
    elif app == 'eco-pdv':
        for (dx, h, w) in [(-180, .44, 34), (-40, .54, 42), (110, .38, 30)]:
            px = x + dx * u; t = base - h * H; ww = w * u
            L.append([(px - ww * 1.3, base), (px - ww, t), (px + ww, t), (px + ww * 1.3, base)])
            for k in range(1, 5): y = base - h * H * k / 5; f = 1 + .3 * (1 - k / 5); L.append([(px - ww * f, y), (px + ww * f, y)])
            for k in range(5):  # кольца дыма, сносит ветром влево
                r = (18 + k * 14) * u; cxk = px - (k * 46 + 20) * u; cyk = t - (k * 32 + 24) * u
                L.append([(cxk + r * math.cos(a), cyk + r * .6 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 36)])
        L.append([(x - 300 * u, base), (x - 300 * u, base - .13 * H), (x + 220 * u, base - .13 * H), (x + 220 * u, base)])
        # факел рассеивания
        L.append([(x - 40 * u - t * 900 * u, base - .54 * H - 30 * u + t * t * 120 * u) for t in np.linspace(0, 1, 40)])
    return L


# ---------- значки утилит (как SVG в шапке утилит), в координатах 32×32 ----------
def _cubic(p0, p1, p2, p3, n=16):
    return [((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0],
             (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1]) for t in np.linspace(0, 1, n)]

def _wave():
    # M5 22 c4 0 4-12 8-12 s4 8 7 8 3-4 7-4
    pts = _cubic((5, 22), (9, 22), (9, 10), (13, 10)); prev = (9, 10); cur = (13, 10)
    for (c2, e) in [((4, 8), (7, 8)), ((3, -4), (7, -4))]:
        c1 = (2 * cur[0] - prev[0], 2 * cur[1] - prev[1]); c2a = (cur[0] + c2[0], cur[1] + c2[1]); end = (cur[0] + e[0], cur[1] + e[1])
        pts += _cubic(cur, c1, c2a, end)[1:]; prev, cur = c2a, end
    return pts

def _rot(pts, a, c):
    ca, sa = math.cos(a), math.sin(a)
    return [(c[0] + (x - c[0]) * ca - (y - c[1]) * sa, c[1] + (x - c[0]) * sa + (y - c[1]) * ca) for x, y in pts]

def _rrect(x, y, w, h, r, n=6):
    pts = []
    for cx, cy, a0 in [(x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180)]:
        pts += [(cx + r * math.cos(math.radians(a0 + 90 * t / n)), cy + r * math.sin(math.radians(a0 + 90 * t / n))) for t in range(n + 1)]
    return pts + [pts[0]]

ICONS = {
    'sapr-labs': [('line', _wave(), 2.4)],
    'krrs-robot': [('line', _rot(_rrect(11, 5, 10, 15, 2), math.radians(8), (16, 20)), 2.2), ('circle', (10, 23), 3.6, 2.2), ('circle', (22, 23), 3.6, 2.2)],
    'op-coursework': [('circle', (12, 17), 6.5, 2.2), ('circle', (23, 11), 4, 2.2), ('line', [(12, 10.5), (12, 8.5)], 2), ('line', [(12, 25.5), (12, 23.5)], 2),
                      ('line', [(5.5, 17), (3.5, 17)], 2), ('line', [(20.5, 17), (18.5, 17)], 2)],
    'eco-pdv': [('line', [(5, 27), (27, 27)], 2.2), ('line', [(9, 27), (9, 15), (14, 15), (14, 27)], 2.2), ('line', [(18, 27), (18, 20), (24, 23), (24, 27)], 2.2),
                ('circle', (12.5, 10), 2.4, 1.9), ('circle', (17.6, 7), 2.9, 1.9), ('circle', (23.6, 5.4), 2, 1.9)],
    'hub': [('fill', _rrect(6, 6, 9, 9, 2)), ('fill', _rrect(17, 6, 9, 9, 2)), ('fill', _rrect(6, 17, 9, 9, 2)), ('line', _rrect(17, 17, 9, 9, 2), 1.6)],
}
ACCENT = {'sapr-labs': ('#0a5aa8', '#5fa8ef'), 'krrs-robot': ('#5a3ea8', '#ad97f0'), 'op-coursework': ('#0b6e62', '#4fc3ae'), 'eco-pdv': ('#557313', '#a8cd5c'), 'hub': ('#1a222b', '#e1e8ef'), 'нет': ('#3a4250', '#9aa6b8')}
