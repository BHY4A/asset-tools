"""«Стекло: аура» — мягкое цветное свечение и плавающие стеклянные пластины с преломлением.

Фон — «меш-градиент» из размытых пятен цвета утилиты; пластины (скруглённые прямоугольники и диски) преломляют
то, что за ними (смещение растёт к краю, как у линзы), матовые внутри, с бликом по верхней кромке, тонкой световой
гранью и мягкой тенью. На самой большой — гравировка сюжета утилиты.
"""
import math
import numpy as np, cv2
from ..params import Param, Spec
from ..core import Ctx, hexc, polyline, wrap_noise, screen
from .. import motifs

SPEC = Spec('glass', [
    Param('app', 'sapr-labs', kind='choice', choices=motifs.APPS + ['нет'], group='сюжет', help='цвета и гравировка утилиты', rand=False),
    Param('theme', 'светлая', kind='choice', choices=['светлая', 'тёмная'], group='сюжет', help='тема'),
    Param('width', 1920, 320, 4096, group='сюжет', help='ширина, px', rand=False), Param('height', 1200, 240, 4096, group='сюжет', help='высота, px', rand=False),
    Param('accent', 'авто', group='цвет', help='главный цвет; «авто» — цвет утилиты'), Param('accent2', '#f0874a', group='цвет', help='второй цвет'),
    Param('blobs', 6, 2, 14, group='свечение', help='пятен цвета', rand=(3, 9)), Param('aura', 1.0, 0.0, 2.0, group='свечение', help='насыщенность ауры', rand=(.5, 1.5)),
    Param('blob_size', 1.0, .4, 2.0, group='свечение', help='размер пятен', rand=(.6, 1.5)),
    Param('panes', 5, 0, 10, group='стекло', help='число пластин', rand=(2, 7)), Param('refraction', 1.0, 0.0, 3.0, group='стекло', help='сила преломления', rand=(.4, 2.0)),
    Param('frost', 1.0, 0.0, 3.0, group='стекло', help='матовость', rand=(.3, 2.0)), Param('rim', 1.0, 0.0, 2.0, group='стекло', help='световая грань и блик'),
    Param('roundness', .35, 0.0, .5, group='стекло', help='скругление углов', rand=(.1, .5)), Param('discs', .3, 0.0, 1.0, group='стекло', help='доля дисков среди пластин'),
    Param('engrave', 1.0, 0.0, 2.0, group='стекло', help='гравировка сюжета'),
    Param('grain', 1.0, 0.0, 3.0, group='фактура', help='зерно поверх цвета'),
], {
    'светлая': {}, 'тёмная': dict(theme='тёмная'), 'много стекла': dict(panes=9, refraction=1.6, blobs=8),
    'чистая аура': dict(panes=0, blobs=8, aura=1.3), 'лёд': dict(frost=2.4, refraction=.6, aura=.6),
}, title='Стекло: аура', about='Цветная аура утилиты и стеклянные пластины с преломлением, бликом и гравировкой')

def _rrect_mask(H, W, x, y, w, h, r):
    m = np.zeros((H, W), np.float32); r = int(max(0, min(r, w / 2, h / 2)))
    cv2.rectangle(m, (int(x + r), int(y)), (int(x + w - r), int(y + h)), 1, -1); cv2.rectangle(m, (int(x), int(y + r)), (int(x + w), int(y + h - r)), 1, -1)
    for cx, cy in [(x + r, y + r), (x + w - r, y + r), (x + r, y + h - r), (x + w - r, y + h - r)]: cv2.circle(m, (int(cx), int(cy)), r, 1, -1, cv2.LINE_AA)
    return m

def apply(P, seed=7):
    c = Ctx(seed); W, H = int(P['width']), int(P['height']); u = W / 1920; dark = P['theme'] == 'тёмная'; app = P['app']
    acc = hexc(P['accent'] if str(P['accent']).startswith('#') else motifs.ACCENT.get(app, motifs.ACCENT['нет'])[1 if dark else 0])
    acc2 = hexc(P['accent2'])
    base = (acc * .05 + hexc('#f2f3f6') * .95) if not dark else (acc * .07 + hexc('#0a0c11') * .93)
    img = np.ones((H, W, 3), np.float32) * base
    # аура: пятна цвета, наложенные по очереди (не усреднённые — иначе всё сливается в один тон)
    sm = 4; h2, w2 = H // sm + 1, W // sm + 1; Y, X = np.mgrid[0:h2, 0:w2].astype(np.float32); low = cv2.resize(img, (w2, h2))
    anchors = [(.06, .05), (.97, .14), (.62, 1.02), (.3, .7)]
    s = (.85 if not dark else .6) * P['aura']
    for i in range(int(P['blobs'])):
        ax, ay = anchors[i] if i < len(anchors) else (c.R.uniform(0, 1), c.R.uniform(0, 1))
        r = c.R.uniform(.16, .3) * (1 if not dark else .8) * P['blob_size'] * max(w2, h2)
        col = acc if i % 3 != 1 else acc2
        if i >= 4 and c.R.random() < .4: col = acc * .5 + acc2 * .5
        if not dark: col = col * .8 + .2
        else: col = col * .62
        g = np.exp(-(((X - ax * w2) ** 2 + (Y - ay * h2) ** 2) / (2 * r * r)))[..., None] * s
        low = low * (1 - g) + col * g if not dark else low * (1 - g * .55) + col * g * .55
    img = cv2.resize(low, (W, H), interpolation=cv2.INTER_CUBIC)
    # стекло
    eng = np.zeros((H, W), np.float32)
    panes = []
    for i in range(int(P['panes'])):
        if i == 0: w_, h_ = c.R.uniform(.34, .44) * W, c.R.uniform(.42, .56) * H; x_, y_ = c.R.uniform(.52, .6) * W, c.R.uniform(.2, .32) * H
        else:
            w_ = c.R.uniform(.07, .2) * W; h_ = w_ * c.R.uniform(.5, 1.3)
            for _t in range(20):
                x_, y_ = c.R.uniform(-.04, .96) * W, c.R.uniform(-.04, .92) * H
                if all(x_ + w_ < q[0] or q[0] + q[2] < x_ or y_ + h_ < q[1] or q[1] + q[3] < y_ for q in panes) or _t == 19: break
        disc = i > 0 and c.R.random() < P['discs']
        if disc: h_ = w_
        panes.append((x_, y_, w_, h_, disc))
    for (x_, y_, w_, h_, disc) in sorted(panes, key=lambda q: -q[2] * q[3]):
        m = _rrect_mask(H, W, x_, y_, w_, h_, (min(w_, h_) / 2) if disc else P['roundness'] * min(w_, h_))
        if m.sum() < 10: continue
        dist = cv2.distanceTransform((m > .5).astype(np.uint8), cv2.DIST_L2, 5).astype(np.float32)
        edge = np.clip(dist / (28 * u), 0, 1)
        gx = cv2.Sobel(dist, cv2.CV_32F, 1, 0, ksize=5); gy = cv2.Sobel(dist, cv2.CV_32F, 0, 1, ksize=5); nrm = np.sqrt(gx * gx + gy * gy) + 1e-4
        k = (1 - edge) ** 2 * 26 * u * P['refraction']
        Xg, Yg = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        refr = cv2.remap(img, Xg + gx / nrm * k, Yg + gy / nrm * k, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        fr = max(.1, 10 * u * P['frost']); refr = cv2.GaussianBlur(refr, (0, 0), fr)
        tint = np.ones(3, np.float32) * (1 if not dark else .14)
        refr = refr * (1 - .22) + tint * .22
        # тень
        sh = cv2.GaussianBlur(cv2.warpAffine(m, np.float32([[1, 0, 6 * u], [0, 1, 18 * u]]), (W, H)), (0, 0), 24 * u)[..., None] * (.16 if not dark else .45)
        img = img * (1 - sh * (1 - m[..., None]))
        mm = m[..., None]
        img = img * (1 - mm) + refr * mm
        # грань и блик
        rim = np.clip(1 - np.abs(dist - 1.2 * u) / (1.6 * u), 0, 1) * m
        top = np.clip(-gy / nrm, 0, 1)
        hl = (rim * (.35 + .65 * top) * (.9 if not dark else .5) + np.clip(1 - dist / (40 * u), 0, 1) * top * m * .18) * P['rim']
        img = screen(img, np.clip(hl[..., None], 0, 1))
        if not eng.any() and P['engrave'] > 0 and app != 'нет':
            em = np.zeros((H, W), np.float32)
            for sg in motifs.lines(app, W, H, y_ + h_ * .92, x_ + w_ * .62, u * min(w_ / W / .4, 1.0) * .62):
                polyline(em, sg, 1.0, max(1, 1.6 * u))
            eng = em * m
    if eng.any():
        e = cv2.GaussianBlur(eng, (0, 0), .6 * u)[..., None] * P['engrave']
        lo = cv2.warpAffine(e[..., 0], np.float32([[1, 0, 1.5 * u], [0, 1, 1.5 * u]]), (W, H))[..., None]
        img = img * (1 - lo * (.18 if not dark else .5)); img = screen(img, e * (.55 if not dark else .35))
    if P['grain'] > 0:
        n = wrap_noise(c, H, W, .7, 2) - .5
        img = img + n[..., None] * .06 * P['grain'] * (1 if not dark else .6)
    return np.clip(img, 0, 1)
