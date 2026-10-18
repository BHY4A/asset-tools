"""Акварель по фото: пятна пигмента с каймой и грануляцией, тушь по форме, брызги, сухие мазки, капли Поллока."""
import numpy as np, cv2
from ..params import Param, Spec
from ..core import Ctx, hexc, fbm, wash_mask, splatter, gesture, pollock, grain, lum, saliency

SPEC = Spec('aquarelle', [
    Param('ground', 'бумага', kind='choice', choices=['бумага', 'тёмный грунт'], group='основа', help='светлая бумага или пигмент на тёмном'),
    Param('paper_color', '#e8e1d2', group='основа', help='цвет бумаги'),
    Param('colors', 9, 2, 24, group='краски', help='сколько красок (пятен цвета)'),
    Param('simplify', 12, 2, 40, group='краски', help='упрощение формы перед покраской'),
    Param('color_merge', 28, 6, 80, group='краски', help='насколько близкие цвета сливаются'),
    Param('pigment', .9, .2, 1.0, group='краски', help='плотность пигмента'),
    Param('saturation', 1.08, .3, 2.0, group='краски', help='насыщенность красок'),
    Param('bleed', 1.0, 0.0, 4.0, group='краски', help='насколько краска растекается за контур'),
    Param('edge_dark', 1.0, 0.0, 3.0, group='краски', help='тёмная кайма по краю размыва'),
    Param('ink', .7, 0.0, 1.0, group='тушь', help='сила рисунка тушью по контурам'),
    Param('ink_detail', 40, 10, 120, group='тушь', help='порог контуров: меньше — больше линий'),
    Param('ink_wobble', 6.0, 0.0, 20.0, group='тушь', help='дрожание руки, px'),
    Param('ink_breaks', .42, 0.0, .9, group='тушь', help='доля разрывов линии'),
    Param('ink_color', '#1b1712', group='тушь', help='цвет туши'),
    Param('ink_method', 'по форме', kind='choice', choices=['по форме', 'контуры'], group='тушь', help='по форме — линии вдоль формы (как пером), контуры — резкие края', rand=False),
    Param('splatter', 1.0, 0.0, 4.0, group='брызги и мазки', help='брызги и потёки'),
    Param('splatter_size', 10, 3, 30, group='брызги и мазки', help='размер крупных брызг'),
    Param('splatter_color', '#8b2f1f', group='брызги и мазки', help='цвет второй краски брызг'),
    Param('gestures', 2, 0, 12, group='брызги и мазки', help='широкие мазки сухой кистью'),
    Param('drips', 2, 0, 12, group='брызги и мазки', help='линии «капель Поллока»'),
    Param('grain', 0.0, 0.0, .1, group='основа', help='зерно поверх'),
    Param('protect', 0.0, 0.0, 1.0, group='основа', help='беречь главное (лица, центр): брызги и мазки обходят его', rand=False),
], {
    'классика': {},
    'лёгкий набросок': dict(colors=6, pigment=.6, ink=.85, ink_detail=30, splatter=.4, gestures=0, drips=0),
    'ночная тушь': dict(ground='тёмный грунт', colors=10, ink_color='#e6dcc4', splatter=1.5, gestures=1),
    'экспрессия': dict(colors=7, bleed=3.0, edge_dark=2.2, splatter=3, gestures=6, drips=5, ink_wobble=12, saturation=1.4),
    'выцветший': dict(pigment=.55, saturation=.6, ink=.4, splatter=.5, paper_color='#efe6d2'),
}, title='Акварель', about='Пятна акварели по бумаге, тушь по форме, брызги и сухие мазки')

def apply(img, p, seed=7):
    c = Ctx(seed); h, w = img.shape[:2]; dark = p['ground'] == 'тёмный грунт'
    u8 = (img * 255).astype(np.uint8)
    flat = cv2.pyrMeanShiftFiltering(cv2.cvtColor(u8, cv2.COLOR_RGB2BGR), sp=int(p['simplify']), sr=int(p['color_merge']))
    flat = cv2.cvtColor(flat, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    cv2.setRNGSeed(seed)
    _, lab, cen = cv2.kmeans(flat.reshape(-1, 3), int(p['colors']), None, crit, 2, cv2.KMEANS_PP_CENTERS); lab = lab.reshape(h, w)
    out = np.ones((h, w, 3), np.float32) * (hexc(p['paper_color']) if not dark else hexc('#141311'))
    out *= ((0.93 + 0.07 * fbm(c, h, w, 3, 3)) if not dark else (0.85 + 0.3 * fbm(c, h, w, 3, 3)))[..., None]
    order = np.argsort(cen.sum(1))[::-1] if not dark else np.argsort(cen.sum(1))
    for k in order:
        m = (lab == k).astype(np.float32)
        if m.mean() < .002: continue
        m = cv2.GaussianBlur(m, (0, 0), 1.2)
        d = wash_mask(c, m, dark=dark, amp=max(3, w / 260) * p['bleed'], cell=max(16, w // 40), edge_px=max(3, w / 220) * max(.3, p['edge_dark'])) * p['pigment']
        gray = cen[k].mean(); col = np.clip(gray + (cen[k] - gray) * p['saturation'], 0, 1)
        if dark: out = 1 - (1 - out) * (1 - d[..., None] * col)
        else: out *= (1 - d[..., None]) + d[..., None] * col
    prot = saliency(img) * p['protect'] if p['protect'] > 0 else None
    if p['ink'] > 0 and p['ink_method'] == 'по форме':
        from .lines import ink_map
        e, _ = ink_map(img, detail=.6 + p['ink_detail'] / 60, smooth=3, threshold=(p['ink_detail'] - 40) / 40, sharpness=60)
        e = e * (fbm(c, h, w, 24, 3) > p['ink_breaks'] * .8)
        X, Y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32)); a = p['ink_wobble']
        e = cv2.remap(e, X + (fbm(c, h, w, 60, 3) - .5) * a, Y + (fbm(c, h, w, 60, 3) - .5) * a, cv2.INTER_LINEAR) * p['ink']
        out = out * (1 - e[..., None]) + hexc(p['ink_color']) * e[..., None]
    elif p['ink'] > 0:
        g = cv2.GaussianBlur((lum(img) * 255).astype(np.uint8), (0, 0), 1.6)
        e = cv2.Canny(g, int(p['ink_detail']), int(p['ink_detail'] * 2.7)).astype(np.float32) / 255
        e = cv2.dilate(e, np.ones((2, 2))) * (fbm(c, h, w, 24, 3) > p['ink_breaks'])
        X, Y = np.meshgrid(np.arange(w), np.arange(h)); a = p['ink_wobble']
        e = cv2.remap(e, (X + (fbm(c, h, w, 60, 3) - .5) * a).astype(np.float32), (Y + (fbm(c, h, w, 60, 3) - .5) * a).astype(np.float32), cv2.INTER_LINEAR)
        e = cv2.GaussianBlur(e, (0, 0), .7) * p['ink']
        out = out * (1 - e[..., None]) + hexc(p['ink_color']) * e[..., None]
    sp = p['splatter']
    if sp > 0:
        s = max(1, int(sp * (h * w) / (1200 * 800) * 10)); rm = int(p['splatter_size'])
        for col, n, r in ([(p['ink_color'], s, rm), (p['splatter_color'], s // 2 + 1, max(3, rm - 2))]):
            m = splatter(c, h, w, n, 1, r, avoid=prot); out = out * (1 - m[..., None] * .85) + hexc(col) * m[..., None] * .85
    if p['gestures']:
        gg = gesture(c, h, w, int(p['gestures']))
        if prot is not None: gg = gg * (1 - prot)
        gc = hexc('#3b3f4a') if not dark else hexc('#8a7f68'); o = .25 if not dark else .15
        out = out * (1 - gg[..., None] * o) + gc * gg[..., None] * o
    if p['drips']:
        q = pollock(c, h, w, int(p['drips']), (.6, 1.6)) * (1 if prot is None else 1 - prot); out = out * (1 - q[..., None] * .6) + hexc(p['ink_color']) * q[..., None] * .6
    if p['grain']: out += grain(c, h, w, p['grain'])[..., None]
    return np.clip(out, 0, 1)
