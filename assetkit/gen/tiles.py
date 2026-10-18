"""«Плитка» — бесшовные текстуры для фона страниц и панелей: бумага, зерно плёнки, точки, клетка, строки развёртки,
полутон, штриховка, мрамор, холст, терраццо. Все узоры строятся с периодом, кратным размеру плитки, а шум —
через периодическое размытие (FFT), поэтому стыков нет; проверка стыка считается и показывается в студии."""
import math
import numpy as np, cv2
from ..params import Param, Spec
from ..core import Ctx, hexc, wrap_blur, wrap_noise

KINDS = ['бумага', 'зерно', 'точки', 'клетка', 'строки', 'полутон', 'штриховка', 'мрамор', 'холст', 'терраццо']

SPEC = Spec('tiles', [
    Param('kind', 'бумага', kind='choice', choices=KINDS, group='узор', help='какой узор'),
    Param('size', 384, 32, 1024, group='узор', help='размер плитки, px (квадрат)', step=32, rand=False),
    Param('scale', 1.0, .25, 4.0, group='узор', help='масштаб узора', rand=(.5, 2.0)),
    Param('contrast', 1.0, 0.0, 3.0, group='узор', help='контраст узора', rand=(.5, 1.6)),
    Param('angle', 45, 0, 180, group='узор', help='угол штриховки, ° (кратно 45 — без стыков)', step=45),
    Param('detail', 1.0, 0.0, 2.0, group='узор', help='мелкие детали (волокна, неровность)', rand=(.3, 1.5)),
    Param('base', '#efe6d2', group='цвет', help='цвет основы'), Param('ink', '#3a3026', group='цвет', help='цвет узора'),
    Param('alpha', False, group='цвет', help='прозрачная основа (PNG с альфой: узор поверх любого цвета)', rand=False),
], {
    'бумага': {}, 'тёмная бумага': dict(base='#1a1814', ink='#e8dcc4', contrast=1.4),
    'зерно плёнки': dict(kind='зерно', base='#808080', ink='#000000', alpha=True, size=256),
    'точки графита': dict(kind='точки', base='#08090c', ink='#ffffff', scale=1.0, contrast=.6, size=176),
    'тетрадь': dict(kind='клетка', base='#fbfcfd', ink='#7aa3cc', scale=1.0, contrast=.7),
    'строки VHS': dict(kind='строки', base='#000000', ink='#000000', alpha=True, size=64, contrast=1.2),
    'мрамор': dict(kind='мрамор', base='#e9e6e1', ink='#6d6a74', scale=1.2), 'холст': dict(kind='холст', base='#d8cfbd', ink='#6b5e48'),
    'терраццо': dict(kind='терраццо', base='#efeae2', ink='#c0573e'),
}, title='Плитка', flags={'tile': True}, about='Бесшовные текстуры: бумага, зерно, точки, клетка, строки, полутон, штриховка, мрамор, холст, терраццо')

def seam_score(img):
    """доля строк и столбцов, где перепад на стыке больше любого перепада внутри той же строки (0 — шва нет)"""
    g = img.mean(2) if img.ndim == 3 else img
    def side(a):
        inner = np.abs(np.diff(a, axis=1)); lim = inner.max(axis=1) * 1.1 + 1e-3
        return (np.abs(a[:, 0] - a[:, -1]) > lim).mean()
    return float((side(g) + side(g.T)) / 2)

def tile_preview(img, n=3):
    return np.tile(img, (n, n, 1))

def _periodic_lines(S, period, angle_deg):
    """синус с периодом, укладывающимся в плитку: направление подбирается к ближайшему целочисленному"""
    a = math.radians(angle_deg); k = max(1, round(S / period))
    kx, ky = round(k * math.cos(a)), round(k * math.sin(a))
    if kx == 0 and ky == 0: kx = k
    Y, X = np.mgrid[0:S, 0:S].astype(np.float32)
    return np.sin(2 * math.pi * (kx * X + ky * Y) / S)

def apply(P, seed=7):
    c = Ctx(seed); S = int(P['size']); k = P['scale']; con = P['contrast']; det = P['detail']
    kind = P['kind']; Y, X = np.mgrid[0:S, 0:S].astype(np.float32)
    def per(n): return max(2, S // max(1, round(S / n)))     # ближайший делитель-период
    if kind == 'бумага':
        n = c.R.random((S, S)).astype(np.float32)
        a = wrap_blur(n, .8); b = wrap_blur(n, 14 * k); fib = wrap_blur(c.R.random((S, S)).astype(np.float32), 4 * k, .6)
        v = (a - a.mean()) * .55 * det + (b - b.mean()) * 7 + (fib - fib.mean()) * .8 * det
        m = np.clip(.5 + v * .9 * con, 0, 1)
    elif kind == 'зерно':
        n = c.R.normal(0, 1, (S, S)).astype(np.float32); n = wrap_blur(n, .6 * k) + wrap_blur(n, 1.6 * k) * .5 * det
        m = np.clip(.5 + n / (n.std() + 1e-6) * .18 * con, 0, 1)
    elif kind == 'точки':
        p = per(22 * k); d = np.sqrt(((X % p) - p / 2) ** 2 + ((Y % p) - p / 2) ** 2)
        m = np.clip(1.4 * k - d, 0, 1) * .5 * con + .0
    elif kind == 'клетка':
        p = per(24 * k); g = np.minimum(X % p, Y % p); major = np.minimum(X % (p * 4 if S % (p * 4) == 0 else p), Y % (p * 4 if S % (p * 4) == 0 else p))
        m = (np.clip(1.2 - g, 0, 1) * .35 + np.clip(1.4 - major, 0, 1) * .35) * con
    elif kind == 'строки':
        p = per(3 * k); m = ((Y % p) < max(1, p / 3)).astype(np.float32) * .45 * con
    elif kind == 'полутон':
        p = per(10 * k); tone = wrap_noise(c, S, S, 30 * k, 3)
        d = np.sqrt((((X + (Y // p % 2) * p / 2) % p) - p / 2) ** 2 + ((Y % p) - p / 2) ** 2)
        m = np.clip((tone * p * .55 - d) * 1.5, 0, 1) * con
    elif kind == 'штриховка':
        s = _periodic_lines(S, 8 * k, P['angle']); tone = wrap_noise(c, S, S, 40 * k, 3)
        m = np.clip((s - (1 - tone * 1.4)) * 2, 0, 1) * con
        if det > .5: m = np.maximum(m, np.clip((_periodic_lines(S, 8 * k, P['angle'] + 90) - (1.6 - tone * 1.4)) * 2, 0, 1) * con)
    elif kind == 'мрамор':
        n1 = wrap_noise(c, S, S, 60 * k, 5) - .5; n2 = wrap_noise(c, S, S, 18 * k, 4) - .5
        s = _periodic_lines(S, 140 * k, 30) + 0  # базовые полосы
        v = np.sin(2 * math.pi * (X / S * 2 + Y / S) + n1 * 9 + n2 * 3 * det)
        m = np.clip((1 - np.abs(v)) ** 6 * 1.2 + (n1 + .5) * .15, 0, 1) * con
    elif kind == 'холст':
        p = per(6 * k); wx = (np.sin(2 * math.pi * X / p) * .5 + .5); wy = (np.sin(2 * math.pi * Y / p) * .5 + .5)
        chk = ((X // p + Y // p) % 2).astype(np.float32)
        m = (wx * chk + wy * (1 - chk)) * .35 * con + (wrap_noise(c, S, S, 2, 2) - .5) * .25 * det
        m = np.clip(m, 0, 1)
    else:  # терраццо
        m = np.zeros((S, S), np.float32); cols = np.zeros((S, S, 3), np.float32)
        ink = hexc(P['ink']); pal = [ink, ink * .6 + .4 * hexc(P['base']), hexc('#3b4a5a'), hexc('#d9a441'), hexc('#6c8a6a')]
        for i in range(int(90 * det + 20)):
            cx, cy = c.R.uniform(0, S), c.R.uniform(0, S); r = c.R.uniform(2, 11) * k; nv = int(c.R.integers(4, 8))
            pts = [(cx + r * c.R.uniform(.6, 1.2) * math.cos(t), cy + r * c.R.uniform(.6, 1.2) * math.sin(t)) for t in np.sort(c.R.uniform(0, 2 * math.pi, nv))]
            col = pal[int(c.R.integers(0, len(pal)))]
            for ox in (-S, 0, S):
                for oy in (-S, 0, S):
                    q = np.array([(x + ox, y + oy) for x, y in pts], np.int32)
                    cv2.fillPoly(m, [q], 1.0, cv2.LINE_AA); cv2.fillPoly(cols, [q], tuple(float(v) for v in col), cv2.LINE_AA)
        a = np.clip(m * con, 0, 1)[..., None]
        base = hexc(P['base']) * (1 + (wrap_noise(c, S, S, 3, 2)[..., None] - .5) * .12)
        if P['alpha']: return np.dstack([cols, a[..., 0]])
        return np.clip(base * (1 - a) + cols * a, 0, 1)
    m = np.clip(m, 0, 1)
    base, ink = hexc(P['base']), hexc(P['ink'])
    if P['alpha']:
        if kind in ('бумага', 'зерно'):   # светлое и тёмное зерно: альфа = отклонение от середины, цвет — светлый или тёмный
            dv = (m - .5) * 2; rgb = np.where(dv[..., None] > 0, np.ones(3, np.float32), np.zeros(3, np.float32))
            return np.dstack([rgb, np.clip(np.abs(dv) * .9, 0, 1)])
        return np.dstack([np.broadcast_to(ink, (S, S, 3)), m])
    if kind in ('бумага', 'зерно'):
        return np.clip(base * (1 + (m[..., None] - .5) * (.35 if base.mean() > .5 else .9)) + (ink - base) * 0, 0, 1)
    return np.clip(base * (1 - m[..., None]) + ink * m[..., None], 0, 1)
