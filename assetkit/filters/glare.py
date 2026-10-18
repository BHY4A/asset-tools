"""Засветка: выжженная или ночная плёнка — кросс-процесс, свечение, засветка края, двоение, сплит-врезки."""
import numpy as np, cv2
from ..params import Param, Spec
from ..core import Ctx, hexc, fbm, wash_mask, splatter, gesture, pollock, grain, lum, saliency

SPEC = Spec('glare', [
    Param('time', 'день', kind='choice', choices=['день', 'ночь'], group='плёнка', help='выжженный день или бирюзово-янтарная ночь'),
    Param('lift', .10, 0.0, .4, group='плёнка', help='подъём теней (выцветание)'),
    Param('burn', 1.35, 1.0, 3.0, group='плёнка', help='выжигание светов'),
    Param('fade', .18, 0.0, .8, group='плёнка', help='потеря цвета'),
    Param('shadow_tint', '#1fa0a0', group='плёнка', help='в какой цвет уходят тени'),
    Param('highlight_tint', '#e0e050', group='плёнка', help='в какой цвет уходят света'),
    Param('tint', .5, 0.0, 2.0, group='плёнка', help='сила кросс-процесса'),
    Param('bloom', 1.0, 0.0, 3.0, group='свет', help='свечение светлых мест'),
    Param('leak', .45, 0.0, 1.5, group='свет', help='засветка края плёнки'),
    Param('leak_side', 'справа', kind='choice', choices=['справа', 'слева', 'сверху', 'снизу'], group='свет', help='откуда засветка'),
    Param('double', 0.0, 0.0, 1.0, group='кадр', help='двоение кадра'),
    Param('double_shift', 2.5, 0.0, 10.0, group='кадр', help='сдвиг двоения, % ширины'),
    Param('aberration', 1.0, 0.0, 8.0, group='кадр', help='хроматическая аберрация'),
    Param('split', 0, 0, 3, group='кадр', help='врезки сплит-экрана (0–3)'),
    Param('split_zoom', 2.0, 1.2, 4.0, group='кадр', help='увеличение во врезках'),
    Param('scanlines', 0.0, 0.0, 1.0, group='кадр', help='строки развёртки'),
    Param('grain', .05, 0.0, .2, group='кадр', help='зерно'),
    Param('vignette', .3, 0.0, 1.0, group='кадр', help='виньетка'),
    Param('protect', 0.0, 0.0, 1.0, group='кадр', help='беречь главное: засветка и двоение слабее на лицах и в центре, врезки не закрывают его', rand=False),
], {
    'полдень': {},
    'сиеста': dict(lift=.2, burn=1.8, fade=.35, bloom=1.6, leak=.8),
    'ночь': dict(time='ночь', shadow_tint='#0a8a80', highlight_tint='#ffb040', bloom=1.4, scanlines=.4, leak=.3, leak_side='слева', grain=.07),
    'флешбэк': dict(double=.8, double_shift=3.5, aberration=4, split=2, bloom=1.3, fade=.3),
    'сухой воздух': dict(lift=.06, burn=1.2, fade=.08, tint=.9, highlight_tint='#f0d060', bloom=.6, leak=.2),
}, title='Засветка', about='Выжженная или ночная плёнка: кросс-процесс, свечение, засветка, двоение, сплит-врезки')

def apply(img, p, seed=7):
    c = Ctx(seed); h, w = img.shape[:2]; L = lum(img)[..., None]; night = p['time'] == 'ночь'
    st, ht = hexc(p['shadow_tint']) - .5, hexc(p['highlight_tint']) - .5
    if not night:
        x = np.clip((img - .02) * 1.05 + p['lift'], 0, 1); x = 1 - (1 - x) ** p['burn']
        x = x + (1 - L) * st * .14 * p['tint'] + L * ht * .2 * p['tint']; x = x * (1 - p['fade']) + L * p['fade']
    else:
        x = np.clip(img * .85 + p['lift'] * .3, 0, 1) ** 1.15
        x = x + (1 - L) * st * .2 * p['tint'] + L * ht * .3 * p['tint']; x = x * (1 - p['fade'] * .5) + L * p['fade'] * .5
    hi = np.clip((lum(x) - (.62 if not night else .5)) * 3, 0, 1)[..., None] * x
    x = 1 - (1 - x) * (1 - cv2.GaussianBlur(hi, (0, 0), max(h, w) / 70) * .9 * p['bloom'])
    prot = saliency(img)[..., None] * p['protect'] if p['protect'] > 0 else 0
    base = x.copy()
    side = p['leak_side']
    if side in ('справа', 'слева'): d = (np.arange(w)[None, :] - (w if side == 'справа' else 0)) / (.3 * w); lx = np.exp(-d ** 2) * np.ones((h, 1))
    else: d = (np.arange(h)[:, None] - (0 if side == 'сверху' else h)) / (.3 * h); lx = np.exp(-d ** 2) * np.ones((1, w))
    x = 1 - (1 - x) * (1 - lx[..., None] * (hexc(p['highlight_tint']) * .6 + .4) * p['leak'])
    if p['double'] > 0:
        sh = np.roll(x, (int(.006 * h), int(p['double_shift'] / 100 * w)), axis=(0, 1)); x = np.clip(x * (1 - .25 * p['double']) + sh * .32 * p['double'], 0, 1)
    if p['protect'] > 0: x = x * (1 - prot * .8) + base * prot * .8
    a = int(round(p['aberration'] * w / 1200))
    if a: x = np.dstack([np.roll(x[..., 0], a, axis=1), x[..., 1], np.roll(x[..., 2], -a, axis=1)])
    if p['split']:
        out = x.copy(); fr = hexc('#f7f4ea') if not night else hexc('#0a0d0d'); t = max(4, w // 180); z = p['split_zoom']
        boxes = [(.05, .07, .26, .3), (.69, .63, .27, .3), (.69, .07, .26, .28)][:int(p['split'])]
        for (x0, y0, ww, hh) in boxes:
            X0, Y0, WW, HH = int(x0 * w), int(y0 * h), int(ww * w), int(hh * h)
            zx, zy = c.R.uniform(.2, .6), c.R.uniform(.25, .55)
            if p['protect'] > 0 and float(prot[Y0:Y0 + HH, X0:X0 + WW].mean()) > .35 * p['protect']: continue
            crop = x[int(zy * h):int(zy * h + HH / z), int(zx * w):int(zx * w + WW / z)]
            if crop.size: out[Y0:Y0 + HH, X0:X0 + WW] = cv2.resize(crop, (WW, HH), interpolation=cv2.INTER_CUBIC)
            cv2.rectangle(out, (X0, Y0), (X0 + WW, Y0 + HH), tuple(float(v) for v in fr), t)
        x = out
    if p['scanlines']: x *= (1 - .12 * p['scanlines'] * (1 + np.sin(np.arange(h)[:, None] / 1.5)))[..., None]
    x += grain(c, h, w, p['grain'])[..., None]
    Yv, Xv = np.mgrid[0:h, 0:w]; v = 1 - p['vignette'] * (((Xv / w - .5) ** 2 + (Yv / h - .5) ** 2) * 2.4); x *= v[..., None]
    return np.clip(x, 0, 1)
