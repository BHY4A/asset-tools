"""Фильтр «Сигнал»: изображение как аналоговый видеосигнал девяностых (VHS, эфир, видеодиск).

Своя реализация приёмов, описанных в проекте itorr/vaporwave (лицензии у него нет, поэтому код и пресеты
оттуда не заимствованы): кадр раскладывается на яркость Y и цветность U/V (YUV), и с каждой частью
обращаются отдельно, как это делала аналоговая аппаратура.

Порядок обработки:
  кадр (формат, вписывание, рамка) → уменьшение (низкое разрешение) → ядро свёртки →
  Y: контраст, яркость, подъём чёрного и срез белого, инверсия →
  U/V: насыщенность, сдвиг оттенка, ступенчатость, смещение относительно яркости, «размазывание» по строке, 4:2:0 →
  строки: чересстрочный сдвиг, перекос ленты, шум яркости →
  снег, подписи (OSD) → обратно в RGB → увеличение → JPEG-артефакты.
"""
import math
import numpy as np, cv2
from PIL import Image, ImageDraw
from ..params import Param, Spec
from ..core import font as _kfont, saliency, draw_text, text_width

KERNELS = {
    'нет': None,
    'резкость': np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], np.float32),
    'тянет вправо': np.array([[0, -1, 0], [-1, 1.6, 2.4], [0, -1, 0]], np.float32) / 1.0,
    'тянет влево': np.array([[0, -1, 0], [2.6, 1.8, -2.4], [0, -1, 0]], np.float32),
    'мягко': np.ones((3, 3), np.float32) / 9,
    'рельеф': np.array([[1, 1, .6], [1, 1, -1], [-.6, -1, -1]], np.float32),
}

P = [
    Param('frame', '4:3', kind='choice', choices=['исходный', '4:3', '16:9', '21:9', '1:1'], group='кадр', help='формат кадра', rand=False),
    Param('fit', 'cover', kind='choice', choices=['cover', 'contain', 'fill'], group='кадр', help='обрезать / вписать с полями / растянуть', rand=False),
    Param('aspect', 1.0, .5, 2.0, group='кадр', help='растяжение кадра по ширине (неквадратный пиксель)', rand=(.9, 1.2)),
    Param('width', 720, 240, 2560, group='кадр', help='ширина результата, px', rand=False),
    Param('lowres', 1.6, 1.0, 5.0, group='кадр', help='во сколько раз грубее обрабатывать (низкое разрешение)', rand=(1.0, 2.6)),
    Param('border', 0.0, 0.0, 15.0, group='кадр', help='чёрная рамка, % от кадра', rand=(0.0, 5.0)),
    Param('kernel', 'нет', kind='choice', choices=list(KERNELS), group='кадр', help='ядро свёртки до обработки', rand=('нет', 'нет', 'резкость', 'мягко', 'тянет вправо')),

    Param('contrast', 1.0, 0.0, 3.0, group='яркость', help='контраст яркости', rand=(.7, 1.5)),
    Param('light', 1.0, 0.3, 4.0, group='яркость', help='усиление яркости', rand=(.8, 1.4)),
    Param('black', 0.0, 0.0, 120.0, group='яркость', help='подъём чёрного (выцветшие тени)', rand=(0.0, 60.0)),
    Param('white', 0.0, 0.0, 120.0, group='яркость', help='срез белого (тусклые света)', rand=(0.0, 40.0)),
    Param('invert', False, group='яркость', help='инвертировать только яркость (цвета остаются)', rand=False),

    Param('sat_u', 1.0, 0.0, 2.0, group='цвет', help='насыщенность по оси синий–жёлтый (U)', rand=(.3, 1.4)),
    Param('sat_v', 1.0, 0.0, 2.0, group='цвет', help='насыщенность по оси красный–зелёный (V)', rand=(.3, 1.4)),
    Param('shift_u', 0.0, -128.0, 128.0, group='цвет', help='сдвиг оттенка к синему (+) / жёлтому (−)', rand=(-60.0, 60.0)),
    Param('shift_v', 0.0, -128.0, 128.0, group='цвет', help='сдвиг оттенка к пурпурному (+) / зелёному (−)', rand=(-60.0, 60.0)),
    Param('levels', 4, 1, 96, group='цвет', help='ступенчатость цветности (1 — плавно, больше — постеризация)', rand=(1, 24)),
    Param('chroma_x', 4, -60, 60, group='цвет', help='смещение цвета относительно яркости по горизонтали, px', rand=(-20, 20)),
    Param('chroma_y', 2, -60, 60, group='цвет', help='то же по вертикали, px', rand=(-12, 12)),
    Param('chroma_smear', 3.0, 0.0, 16.0, group='цвет', help='размазывание цвета вдоль строки (узкая полоса цветности VHS)', rand=(0.0, 8.0)),
    Param('subsample', True, group='цвет', help='прореживание цвета 4:2:0 (как в видеосжатии)'),

    Param('interlace', 1, 0, 12, group='строки', help='чересстрочный сдвиг, px', rand=(0, 4)),
    Param('interlace_period', 4, 2, 24, group='строки', help='период «гребёнки», строк', rand=(2, 10)),
    Param('interlace_light', 0.2, 0.0, 1.0, group='строки', help='мерцание яркости строк', rand=(0.0, .5)),
    Param('skew', 0.0, 0.0, 0.35, group='строки', help='перекос ленты внизу кадра (сбой трекинга)', rand=(0.0, .12)),
    Param('skew_curve', 6.0, 1.0, 20.0, group='строки', help='как резко перекос нарастает к низу', rand=(3.0, 12.0)),
    Param('skew_jitter', 0.4, 0.0, 2.0, group='строки', help='дрожание перекоса по строкам', rand=(0.0, 1.0)),
    Param('tear', 0, 0, 12, group='строки', help='число горизонтальных срывов синхронизации', rand=(0, 3)),
    Param('noise', 0.0, 0.0, 200.0, group='строки', help='шум яркости', rand=(0.0, 40.0)),
    Param('noise_dark', 0.0, 0.0, 400.0, group='строки', help='шум в тенях', rand=(0.0, 80.0)),

    Param('snow', 0.0, 0.0, 1.0, group='эфир', help='«снег» нет сигнала (0 — нет, 1 — только снег)', rand=(0.0, .12)),
    Param('scanlines', 0.15, 0.0, 1.0, group='эфир', help='тёмные строки развёртки', rand=(0.0, .5)),
    Param('bloom', 0.15, 0.0, 1.0, group='эфир', help='свечение ярких мест (люминофор)', rand=(0.0, .5)),
    Param('vignette', 0.2, 0.0, 1.0, group='эфир', help='затемнение по краям (выпуклый кинескоп)', rand=(0.0, .5)),
    Param('jpeg', 0.7, 0.05, 1.0, group='эфир', help='качество JPEG (меньше — больше блоков)', rand=(.3, .9)),
    Param('osd', '', group='подпись', help='экранная надпись (например «PLAY ▶» или «ЛР № 3»)', rand=False),
    Param('osd_pos', 'слева сверху', kind='choice', choices=['слева сверху', 'справа сверху', 'слева снизу', 'справа снизу', 'центр'], group='подпись', help='где надпись', rand=False),
    Param('osd_size', 1.0, 0.3, 4.0, group='подпись', help='размер надписи', rand=False),
    Param('osd_color', '#ffffff', group='подпись', help='цвет надписи', rand=False),
    Param('osd_wide', True, group='подпись', help='«широкие» буквы с пробелами: Э Ф И Р', rand=False),
    Param('timecode', False, group='подпись', help='счётчик времени в углу', rand=False),
    Param('protect', 0.0, 0.0, 1.0, group='кадр', help='беречь главное на фото (лица, центр): помехи, снег и срывы обходят его', rand=False),
]

PRESETS = {
    'тёплый эфир':       dict(shift_u=-14, shift_v=18, sat_u=.92, sat_v=.8, light=.92, interlace=1, interlace_light=.2, chroma_x=6, chroma_y=4),
    'розовый закат':     dict(shift_u=-20, shift_v=46, sat_u=1.15, sat_v=1.05, light=.95, bloom=.35, chroma_x=5, chroma_y=3, levels=6),
    'выцветшая кассета': dict(lowres=1.1, sat_u=.18, sat_v=.14, light=1.9, contrast=.75, black=40, noise=24, noise_dark=46, chroma_x=4),
    'чересстрочка':      dict(lowres=2.2, black=50, levels=12, interlace=3, interlace_light=.45, jpeg=.55, aspect=1.15, border=3, scanlines=.4),
    'срыв синхронизации': dict(lowres=3.0, chroma_x=22, chroma_y=14, shift_v=-10, sat_u=.6, sat_v=.5, jpeg=.3, noise=26, border=4, skew=.18, tear=5),
    'неоновый перелив':  dict(light=1.08, chroma_x=14, shift_u=-3, levels=40, sat_u=1.1, sat_v=1.05, jpeg=.4, bloom=.45),
    'ночной канал':      dict(invert=True, lowres=1.5, contrast=1.8, light=1.3, sat_u=.25, sat_v=.4, noise_dark=220, jpeg=.4, aspect=1.4, fit='contain'),
    'видеодиск':         dict(lowres=1.2, light=1.08, contrast=1.15, black=36, white=12, levels=1, sat_u=.75, sat_v=.68, noise=9, noise_dark=16, fit='contain', border=7),
    'синий час':         dict(lowres=1.4, light=.9, shift_u=60, shift_v=-55, sat_u=.9, sat_v=.75, border=1.5, scanlines=.3),
    'нет сигнала':       dict(snow=1.0, lowres=2, scanlines=.3, osd='НЕТ СИГНАЛА', osd_pos='центр', osd_size=1.4),
}

SPEC = Spec('signal', P, PRESETS, title='Сигнал', about='Аналоговый видеосигнал: YUV, сдвиг цветности, чересстрочность, снег, подписи — как VHS и эфир девяностых')

# ---------- цветовые пространства ----------
_M = np.array([[.299, .587, .114], [-.168736, -.331264, .5], [.5, -.418688, -.081312]], np.float32)
_Mi = np.linalg.inv(_M).astype(np.float32)
def rgb2yuv(x): y = x @ _M.T; y[..., 1:] += 128; return y
def yuv2rgb(x): x = x.copy(); x[..., 1:] -= 128; return x @ _Mi.T

def _frame(img, p):
    """формат кадра и вписывание; img — float 0..255"""
    h0, w0 = img.shape[:2]
    if p['frame'] == 'исходный': W = int(p['width']); H = int(round(W * h0 / w0))
    else:
        a, b = map(int, p['frame'].split(':')); W = int(p['width']); H = int(round(W * b / a))
    target = (W / H) * p['aspect']
    out = np.zeros((H, W, 3), np.float32)
    if p['fit'] == 'fill': x = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA); out[:] = x
    elif p['fit'] == 'cover':
        src = w0 / h0
        if src > target: cw = int(h0 * target); x0 = (w0 - cw) // 2; crop = img[:, x0:x0 + cw]
        else: ch = int(w0 / target); y0 = (h0 - ch) // 2; crop = img[y0:y0 + ch]
        out[:] = cv2.resize(crop, (W, H), interpolation=cv2.INTER_AREA)
    else:
        src = (w0 / h0) / p['aspect']
        if src > W / H: w, h = W, max(1, int(W / src))
        else: w, h = max(1, int(H * src)), H
        out[(H - h) // 2:(H - h) // 2 + h, (W - w) // 2:(W - w) // 2 + w] = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    if p['border'] > 0:
        bx, by = int(W * p['border'] / 200), int(H * p['border'] / 200)
        inner = cv2.resize(out, (W - 2 * bx, H - 2 * by), interpolation=cv2.INTER_AREA)
        out[:] = 0; out[by:H - by, bx:W - bx] = inner
    return out

def _shift(a, dx, dy):
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(a, M, (a.shape[1], a.shape[0]), borderMode=cv2.BORDER_REPLICATE)

def _font(px): return _kfont('cond', px)

def _osd(rgb, p, rng):
    text = p['osd']
    if p['osd_wide'] and text: text = ' '.join(text.replace(' ', '\u3000'))
    lines = [t for t in [text] if t]
    if p['timecode']: lines.append(f'▶ {int(rng.integers(0, 2)):d}:{int(rng.integers(0, 59)):02d}:{int(rng.integers(0, 59)):02d}')
    if not lines: return rgb
    H, W = rgb.shape[:2]; im = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)); dr = ImageDraw.Draw(im)
    f = _font(max(10, int(W / 24 * p['osd_size'])))
    col = tuple(int(p['osd_color'].lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
    pad = int(W * .05); y = pad
    for ln in lines:
        tw, th = text_width(ln, 'cond', f.size), f.size
        pos = p['osd_pos']
        x = pad if 'слева' in pos else (W - pad - tw if 'справа' in pos else (W - tw) // 2)
        yy = (H - th) // 2 if pos == 'центр' else (y if 'сверху' in pos else H - pad - th - (y - pad))
        draw_text(dr, (x + 2, yy + 2), ln, 'cond', f.size, (0, 0, 0))
        draw_text(dr, (x, yy), ln, 'cond', f.size, col); y += int(th * 1.5)
    return np.asarray(im).astype(np.float32)

def apply(img01, p, seed=7):
    if p.get('protect', 0) > 0 and (p['snow'] > 0 or p['tear'] or p['skew'] > 0 or p['noise'] or p['noise_dark']):
        heavy = _apply(img01, p, seed)
        calm = _apply(img01, dict(p, snow=0, tear=0, skew=0, noise=p['noise'] * .25, noise_dark=p['noise_dark'] * .25), seed)
        m = saliency(calm)[..., None] * p['protect']
        return heavy * (1 - m) + calm * m
    return _apply(img01, p, seed)

def _apply(img01, p, seed=7):
    """img01 — RGB float 0..1; возвращает RGB float 0..1"""
    rng = np.random.default_rng(seed)
    full = _frame(img01 * 255, p); H, W = full.shape[:2]
    h, w = max(8, int(H / p['lowres'])), max(8, int(W / p['lowres']))
    x = cv2.resize(full, (w, h), interpolation=cv2.INTER_AREA)
    k = KERNELS[p['kernel']]
    if k is not None: x = cv2.filter2D(x, -1, k, borderType=cv2.BORDER_REPLICATE)
    yuv = rgb2yuv(np.clip(x, 0, 255)); Y, U, V = yuv[..., 0], yuv[..., 1], yuv[..., 2]
    # яркость
    Y = (Y - 128) * p['contrast'] + 128; Y = Y * p['light']
    Y = np.clip(Y, p['black'], 255 - p['white'])
    if p['invert']: Y = 255 - Y
    # цветность
    U = (U - 128) * p['sat_u'] + p['shift_u'] + 128; V = (V - 128) * p['sat_v'] + p['shift_v'] + 128
    if p['levels'] > 1: U = np.round(U / p['levels']) * p['levels']; V = np.round(V / p['levels']) * p['levels']
    s = 1 / p['lowres'] * (w / 640) * p['lowres']  # смещения задаются в пикселях кадра 640 px шириной
    U = _shift(U, p['chroma_x'] * s, p['chroma_y'] * s); V = _shift(V, (p['chroma_x'] + p['chroma_y']) * s, 0)
    if p['chroma_smear'] > 0:
        kx = max(1, int(p['chroma_smear'] * s * 2) | 1); U = cv2.blur(U, (kx, 1)); V = cv2.blur(V, (kx, 1))
    if p['subsample']:
        U = cv2.resize(cv2.resize(U, (max(1, w // 2), max(1, h // 2)), interpolation=cv2.INTER_AREA), (w, h), interpolation=cv2.INTER_NEAREST)
        V = cv2.resize(cv2.resize(V, (max(1, w // 2), max(1, h // 2)), interpolation=cv2.INTER_AREA), (w, h), interpolation=cv2.INTER_NEAREST)
    # строки: чересстрочность и перекос двигают только яркость — цвет «отстаёт», как на ленте
    rows = np.arange(h)
    shift = np.zeros(h, np.float32); gain = np.ones(h, np.float32)
    if p['interlace'] or p['interlace_light']:
        ph = (rows % p['interlace_period']) / p['interlace_period']; tri = np.abs(ph - .5) * 2
        shift += np.ceil(p['interlace'] * tri * s); gain *= 1 + p['interlace_light'] ** 2 * (tri - .5) * 2
    if p['skew'] > 0:
        shift += w * p['skew'] * (rows / h) ** p['skew_curve'] * (1 + p['skew_jitter'] * (rng.random(h) - .5))
    for _ in range(int(p['tear'])):
        y0 = int(rng.integers(0, h)); hh = int(rng.integers(2, max(3, h // 30))); shift[y0:y0 + hh] += rng.uniform(-.08, .08) * w
    if shift.any() or (gain != 1).any():
        Yn = np.empty_like(Y)
        for r in range(h):
            Yn[r] = np.roll(Y[r], -int(shift[r])) * gain[r]
        Y = Yn
    if p['noise']: Y = Y + (rng.random(Y.shape) - .5) * p['noise']
    if p['noise_dark']: Y = Y + (rng.random(Y.shape) - .5) * p['noise_dark'] * (255 - Y) / 255
    if p['snow'] > 0:
        sY = rng.integers(0, 26, Y.shape).astype(np.float32) * 10
        sY[::2] = np.clip(sY[::2] + 60, 0, 255)
        sU = rng.uniform(108, 148, Y.shape); sV = rng.uniform(118, 138, Y.shape)
        a = p['snow']; Y = Y * (1 - a) + sY * a; U = U * (1 - a) + sU * a; V = V * (1 - a) + sV * a
    rgb = yuv2rgb(np.dstack([Y, U, V]).astype(np.float32))
    rgb = cv2.resize(np.clip(rgb, 0, 255), (W, H), interpolation=cv2.INTER_LINEAR)
    if p['bloom'] > 0:
        hi = np.clip(rgb - 170, 0, 255) * 3; rgb = 255 - (255 - rgb) * (1 - cv2.GaussianBlur(hi, (0, 0), W / 90) / 255 * p['bloom'])
    if p['scanlines'] > 0:
        per = max(2, int(round(H / 240))); m = np.ones(H, np.float32); m[(np.arange(H) % per) == 0] = 1 - p['scanlines'] * .6
        rgb *= m[:, None, None]
    if p['vignette'] > 0:
        Yv, Xv = np.mgrid[0:H, 0:W]; v = 1 - p['vignette'] * .55 * (((Xv / W - .5) ** 2 * 1.4 + (Yv / H - .5) ** 2 * 1.4) * 2.2) ** 1.4
        rgb *= np.clip(v, 0, 1)[..., None]
    rgb = _osd(rgb, p, rng)
    if p['jpeg'] < .99:
        ok, buf = cv2.imencode('.jpg', cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, int(p['jpeg'] * 100)])
        rgb = cv2.cvtColor(cv2.imdecode(buf, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB).astype(np.float32)
    return np.clip(rgb / 255, 0, 1)
