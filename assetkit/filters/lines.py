"""Линии по фото без нейросети: поток направлений (структурный тензор) + разность гауссиан вдоль потока (FDoG / XDoG).

Классический приём нефотореалистичного рендеринга (Kang, Lee, Chui 2007; Winnemöller 2012): линии идут по форме,
а не по шуму, поэтому похожи на рисунок пером. Работает и в браузере — модель скачивать не нужно.
Режимы: только линии; линии поверх фото; «комикс» — плоские заливки и контур; «гравюра» — штрих, изогнутый тоном;
«муар» — оп-арт: штрих по направлению формы, на стыках направлений рождается муар.
"""
import math
import numpy as np, cv2
from ..params import Param, Spec
from ..core import Ctx, hexc, fbm, lum, saliency

def flow(gray, sigma):
    """касательное поле (tx, ty) и связность 0..1 по структурному тензору"""
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    Jxx = cv2.GaussianBlur(gx * gx, (0, 0), sigma); Jxy = cv2.GaussianBlur(gx * gy, (0, 0), sigma); Jyy = cv2.GaussianBlur(gy * gy, (0, 0), sigma)
    theta = .5 * np.arctan2(2 * Jxy, Jxx - Jyy)          # направление градиента
    tx, ty = -np.sin(theta), np.cos(theta)               # касательная — поперёк градиента
    tr = Jxx + Jyy; det = np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2)
    coh = np.where(tr > 1e-6, det / (tr + 1e-6), 0) ** 2
    return tx.astype(np.float32), ty.astype(np.float32), coh.astype(np.float32)

def _grid(h, w):
    X, Y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32)); return X, Y

def fdog(gray, tx, ty, sigma_c=1.0, k=1.6, rho=.99, sigma_m=3.0):
    """отклик DoG поперёк потока, сглаженный вдоль потока (свёртка по линии тока)"""
    h, w = gray.shape; X, Y = _grid(h, w); nx, ny = ty * -1, tx       # нормаль
    S = int(math.ceil(3 * k * sigma_c)); acc = np.zeros_like(gray); ws = 0
    for s in range(-S, S + 1):
        wgt = math.exp(-s * s / (2 * sigma_c ** 2)) / sigma_c - rho * math.exp(-s * s / (2 * (k * sigma_c) ** 2)) / (k * sigma_c)
        acc += wgt * cv2.remap(gray, X + s * nx, Y + s * ny, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    D = acc
    if sigma_m <= 0: return D
    L = int(math.ceil(2 * sigma_m)); out = D.copy(); tot = np.ones_like(D)
    for sign in (1, -1):
        px, py = X.copy(), Y.copy(); vx, vy = tx * sign, ty * sign
        for s in range(1, L + 1):
            px = px + vx; py = py + vy
            nvx = cv2.remap(tx, px, py, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE); nvy = cv2.remap(ty, px, py, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            flip = np.sign(nvx * vx + nvy * vy); flip[flip == 0] = 1; vx, vy = nvx * flip, nvy * flip   # не разворачиваться
            g = math.exp(-s * s / (2 * sigma_m ** 2))
            out += g * cv2.remap(D, px, py, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE); tot += g
    return out / tot

def ink_map(img, detail=1.0, smooth=3.0, threshold=.0, sharpness=40.0, flow_sigma=3.0, scale=None):
    """карта туши 0..1 (1 — линия)"""
    h, w = img.shape[:2]; s = scale or max(1.0, max(h, w) / 1000)
    g = cv2.GaussianBlur(lum(img).astype(np.float32), (0, 0), .6 * s)
    tx, ty, coh = flow(g, flow_sigma * s)
    D = fdog(g, tx, ty, detail * s, sigma_m=smooth * s)
    E = np.where(D >= threshold * .01, 1.0, 1 + np.tanh(sharpness * (D - threshold * .01)))
    return np.clip(1 - E, 0, 1).astype(np.float32), (tx, ty, coh)

SPEC = Spec('lines', [
    Param('mode', 'линии', kind='choice', choices=['линии', 'поверх фото', 'комикс', 'гравюра', 'муар'], group='режим', help='что оставить от фото', rand=False),
    Param('detail', 1.0, .4, 4.0, group='линии', help='толщина «кисти»: больше — крупнее и проще', rand=(.7, 2.2)),
    Param('smooth', 3.0, 0.0, 10.0, group='линии', help='плавность вдоль формы (длинные штрихи)', rand=(1.0, 6.0)),
    Param('flow_sigma', 3.0, .5, 12.0, group='линии', help='насколько крупно читается направление формы', rand=(1.5, 7.0)),
    Param('threshold', 0.0, -2.0, 3.0, group='линии', help='порог: выше — меньше линий', rand=(-.5, 1.5)),
    Param('sharpness', 40.0, 2.0, 200.0, group='линии', help='резкость края линии (мало — карандаш, много — тушь)', rand=(8.0, 120.0)),
    Param('weight', 1.0, .5, 4.0, group='линии', help='утолщение линий', rand=(.8, 2.0)),
    Param('wobble', 0.0, 0.0, 12.0, group='линии', help='дрожание руки, px', rand=(0.0, 4.0)),
    Param('breaks', 0.0, 0.0, .9, group='линии', help='разрывы линии', rand=(0.0, .4)),
    Param('ink', '#16120e', group='цвет', help='цвет линий'),
    Param('paper', '#f3eee3', group='цвет', help='цвет бумаги (режимы «линии» и «гравюра»)'),
    Param('colors', 6, 2, 16, group='цвет', help='число плоских цветов (режим «комикс»)', rand=(3, 9)),
    Param('photo_fade', .15, 0.0, 1.0, group='цвет', help='выцветание фото под линиями (режим «поверх фото»)'),
    Param('hatch', 7.0, 3.0, 30.0, group='гравюра', help='шаг штриха, px', rand=(4.0, 14.0)),
    Param('hatch_cross', .55, 0.0, 1.0, group='гравюра', help='с какой темноты начинается перекрёстный штрих', rand=(.3, .9)),
    Param('tone', 1.0, 0.0, 2.0, group='гравюра', help='сила тона', rand=(.6, 1.5)),
    Param('hatch_angle', 35.0, -90.0, 90.0, group='гравюра', help='угол штриха, °'),
    Param('hatch_bend', .8, 0.0, 3.0, group='гравюра', help='насколько штрих изгибается по тону', rand=(.2, 1.6)),
    Param('protect', 0.0, 0.0, 1.0, group='режим', help='в главном (лица, центр) линии тоньше и аккуратнее', rand=False),
], {
    'перо': {},
    'карандаш': dict(sharpness=6, detail=.8, smooth=4, ink='#3a3a40', paper='#f6f4ef', weight=.8),
    'тушь кистью': dict(detail=1.8, smooth=6, sharpness=90, weight=1.6, wobble=2, breaks=.2),
    'комикс': dict(mode='комикс', colors=5, detail=1.4, weight=1.4, sharpness=80),
    'гравюра': dict(mode='гравюра', hatch=5, smooth=5, weight=1.2, ink='#1d1a2a', paper='#efe8d6'),
    'поверх фото': dict(mode='поверх фото', photo_fade=.25, detail=1.2, weight=1.2),
    'муар': dict(mode='муар', hatch=6, flow_sigma=6, smooth=5, ink='#1d1a2a', paper='#efe8d6'),
}, title='Линии', about='Рисунок пером по фото: линии идут по форме (FDoG/XDoG), комикс, гравюра, карандаш')

def apply(img, p, seed=7):
    c = Ctx(seed); h, w = img.shape[:2]; s = max(1.0, max(h, w) / 1000)
    e, (tx, ty, coh) = ink_map(img, p['detail'], p['smooth'], p['threshold'], p['sharpness'], p['flow_sigma'])
    if p['weight'] > 1.05:
        k = int(round((p['weight'] - 1) * 2 * s)) * 2 + 1; e = np.maximum(e, cv2.GaussianBlur(cv2.dilate(e, np.ones((k, k), np.uint8)), (0, 0), .6) * .9)
    elif p['weight'] < .95: e = e * p['weight']
    if p['protect'] > 0:
        m = saliency(img); e = e * (1 - .45 * m * p['protect'])
    if p['breaks'] > 0: e = e * np.clip((fbm(c, h, w, 22 * s, 3) - p['breaks']) * 6 + .5, 0, 1)
    if p['wobble'] > 0:
        X, Y = _grid(h, w); a = p['wobble'] * s
        e = cv2.remap(e, X + (fbm(c, h, w, 60 * s, 3) - .5) * a, Y + (fbm(c, h, w, 60 * s, 3) - .5) * a, cv2.INTER_LINEAR)
    ink, paper = hexc(p['ink']), hexc(p['paper'])
    mode = p['mode']
    if mode == 'поверх фото':
        base = img * (1 - p['photo_fade']) + p['photo_fade']
    elif mode == 'комикс':
        u8 = (img * 255).astype(np.uint8)
        flat = cv2.bilateralFilter(cv2.bilateralFilter(u8, 9, 60, 9), 9, 60, 9).astype(np.float32) / 255
        cv2.setRNGSeed(seed)
        _, lab, cen = cv2.kmeans(flat.reshape(-1, 3), int(p['colors']), None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 1.0), 2, cv2.KMEANS_PP_CENTERS)
        g = cen.mean(1, keepdims=True); cen = np.clip(g + (cen - g) * 1.25, 0, 1)
        base = cen[lab.ravel()].reshape(h, w, 3)
    elif mode == 'гравюра':
        L = cv2.GaussianBlur(lum(img).astype(np.float32), (0, 0), 1.2 * s)
        X, Y = _grid(h, w); per = p['hatch'] * s; a = math.radians(p['hatch_angle'])
        # штрих гравюры: параллельные линии, изогнутые тоном (как на банкноте), толщина — от темноты
        bend = cv2.GaussianBlur(L, (0, 0), 6 * s) * p['hatch_bend'] * per * 3
        ph = (X * math.cos(a) + Y * math.sin(a) + bend) / per
        dark = np.clip((1 - L) * p['tone'], 0, 1)
        st1 = np.clip((dark - np.abs(np.sin(math.pi * ph)) * .95) * 2.2 * s, 0, 1)
        ph2 = (X * math.cos(a + 1.2) + Y * math.sin(a + 1.2) - bend * .7) / per
        d2 = np.clip((dark - p['hatch_cross']) / max(1e-3, 1 - p['hatch_cross']), 0, 1)
        st2 = np.clip((d2 - np.abs(np.sin(math.pi * ph2)) * .95) * 2.2 * s, 0, 1)
        hat = np.clip(st1 + st2, 0, 1)
        base = paper * (1 - hat[..., None]) + ink * hat[..., None]
    elif mode == 'муар':
        # оп-арт: штрих идёт по локальному направлению формы, и там, где направления сходятся, рождается муар
        L = cv2.GaussianBlur(lum(img).astype(np.float32), (0, 0), 1.2 * s)
        X, Y = _grid(h, w); per = p['hatch'] * s
        tsx, tsy, _ = flow(cv2.GaussianBlur(L, (0, 0), 2 * s), p['flow_sigma'] * 3 * s)
        dark = np.clip((1 - L) * p['tone'], 0, 1)
        st1 = np.clip((np.abs(np.sin(math.pi * (X * tsy - Y * tsx) / per)) - (1 - dark)) * 3, 0, 1)
        d2 = np.clip((dark - p['hatch_cross']) / max(1e-3, 1 - p['hatch_cross']), 0, 1)
        st2 = np.clip((np.abs(np.sin(math.pi * (X * tsx + Y * tsy) / per)) - (1 - d2)) * 3, 0, 1) * (dark > p['hatch_cross'])
        hat = np.clip(st1 + st2, 0, 1)
        base = paper * (1 - hat[..., None]) + ink * hat[..., None]
    else:
        base = np.ones((h, w, 3), np.float32) * paper
        base *= (0.96 + 0.04 * fbm(c, h, w, 3 * s, 3))[..., None]
    out = base * (1 - e[..., None]) + ink * e[..., None]
    return np.clip(out, 0, 1)
