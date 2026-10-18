"""Общие примитивы: шум, акварельный размыв, брызги, сухая кисть, бумага, шрифты, ввод-вывод, карта заметности."""
import math, os
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(HERE, 'fonts')

class Ctx:
    def __init__(self, seed=7): self.R = np.random.default_rng(seed)

def hexc(s):
    s = str(s).strip().lstrip('#')
    if len(s) == 3: s = ''.join(ch * 2 for ch in s)
    return np.array([int(s[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)

def to_hex(c): return '#' + ''.join(f'{int(round(max(0, min(1, v)) * 255)):02x}' for v in c)

def lum(img): return img[..., 0] * .2126 + img[..., 1] * .7152 + img[..., 2] * .0722

def mix(a, b, t): return a * (1 - t) + b * t

def screen(a, b): return 1 - (1 - a) * (1 - b)

# ---------- шум ----------
def vnoise(c, h, w, cell):
    cell = max(2, int(cell)); sh, sw = max(2, h // cell + 3), max(2, w // cell + 3)
    s = c.R.random((sh, sw)).astype(np.float32)
    return cv2.resize(s, (sw * cell, sh * cell), interpolation=cv2.INTER_CUBIC)[:h, :w]

def fbm(c, h, w, cell, octaves=5, gain=.5):
    out = np.zeros((h, w), np.float32); a = 1; t = 0
    for i in range(octaves):
        out += a * vnoise(c, h, w, max(2, int(cell / 2 ** i))); t += a; a *= gain
    return out / t

def warp(c, m, amp, cell):
    h, w = m.shape; dx = (fbm(c, h, w, cell, 4) - .5) * amp; dy = (fbm(c, h, w, cell, 4) - .5) * amp
    X, Y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(m, X + dx, Y + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def wrap_blur(x, sx, sy=None):
    """гауссово размытие с периодическими краями (FFT) — для бесшовных плиток"""
    sy = sx if sy is None else sy; h, w = x.shape
    fy = np.fft.fftfreq(h)[:, None]; fx = np.fft.fftfreq(w)[None, :]
    k = np.exp(-2 * (math.pi ** 2) * ((fx * sx) ** 2 + (fy * sy) ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(x) * k)).astype(np.float32)

def wrap_noise(c, h, w, scale, octaves=4, gain=.55):
    """бесшовный фрактальный шум 0..1"""
    out = np.zeros((h, w), np.float32); a = 1; t = 0
    for i in range(octaves):
        n = wrap_blur(c.R.random((h, w)).astype(np.float32), max(.5, scale / 2 ** i))
        n = (n - n.mean()) / (n.std() + 1e-6); out += a * n; t += a; a *= gain
    out /= t; return np.clip(out * .22 + .5, 0, 1)

# ---------- акварель ----------
def wash_mask(c, m, dark=False, amp=90, cell=160, edge_px=9):
    """маска → акварельный размыв: пигмент у края, грануляция, затёки «цветной капустой»"""
    h, w = m.shape
    m = cv2.GaussianBlur(warp(c, m, amp, cell), (0, 0), 1.6)
    inner = cv2.GaussianBlur(m, (0, 0), edge_px); edge = np.clip(m - inner, 0, 1) * 3.2
    gran = fbm(c, h, w, 3, 2)
    bloom = np.clip((fbm(c, h, w, 40, 4) - .62) * 6, 0, 1) * m
    bloom_r = np.clip(cv2.GaussianBlur(bloom, (0, 0), 3) - bloom, 0, 1) * 4
    if dark: return np.clip(m * (.5 + .35 * gran) + edge * .6 + bloom_r * .5, 0, 1.3)
    return np.clip(m * (.42 + .38 * gran) * (1 - .55 * bloom) + edge * .55 + bloom_r * .35, 0, 1.3)

def wash(c, h, w, cx, cy, rx, ry, rough=.55, dark=False):
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2)
    n = fbm(c, h, w, int(max(rx, ry) / 2.2), 5)
    return wash_mask(c, np.clip((1.0 + rough * (n - .5) * 2 - d) * 3.2, 0, 1), dark, amp=max(20, min(90, w / 21)), cell=max(40, min(160, w / 12)))

def splatter(c, h, w, n, rmin=1, rmax=14, area=None, avoid=None):
    """брызги с потёками; avoid — карта 0..1, где брызги нежелательны"""
    R = c.R; m = np.zeros((h, w), np.float32)
    for _ in range(int(n)):
        for _try in range(6):
            if area: cx, cy = R.uniform(area[0], area[2]), R.uniform(area[1], area[3])
            else: cx, cy = R.uniform(0, w), R.uniform(0, h)
            if avoid is None or R.random() > avoid[int(min(h - 1, max(0, cy))), int(min(w - 1, max(0, cx)))]: break
        r = R.uniform(rmin, rmax)
        cv2.circle(m, (int(cx), int(cy)), int(r), 1, -1, cv2.LINE_AA)
        ang = R.uniform(0, 2 * math.pi)
        for j in range(int(R.integers(4, 22))):
            dd = R.uniform(r * .8, r * 7); a = ang + R.normal(0, .35); rr = max(.6, r * R.uniform(.05, .35) * (1 - dd / (r * 8)))
            cv2.circle(m, (int(cx + math.cos(a) * dd), int(cy + math.sin(a) * dd)), int(rr), 1, -1, cv2.LINE_AA)
        if r > 5 and R.random() < .45:
            L = R.uniform(14, 70); x = cx; y = cy; t = max(1.6, r * .7)
            for s in range(int(L)):
                y += 1; x += R.normal(0, .2); t = max(1.2, t * .992)
                cv2.circle(m, (int(x), int(y)), int(t), 1, -1, cv2.LINE_AA)
            cv2.ellipse(m, (int(x), int(y + 2)), (max(1, int(t * 1.3)), max(2, int(t * 2))), 0, 0, 360, 1, -1, cv2.LINE_AA)
    return cv2.GaussianBlur(m, (0, 0), .7)

def pollock(c, h, w, n, width=(.8, 2.4)):
    R = c.R; m = np.zeros((h, w), np.float32)
    for _ in range(int(n)):
        x, y = R.uniform(-100, w + 100), R.uniform(-100, h + 100); a = R.uniform(0, 2 * math.pi); t = R.uniform(*width)
        for s in range(int(R.uniform(200, 900))):
            a += R.normal(0, .06) + .02 * math.sin(s / 30); x += math.cos(a) * 3; y += math.sin(a) * 3
            t = float(np.clip(t + R.normal(0, .35), .3, width[1] * 2.4))
            if R.random() < .012: cv2.circle(m, (int(x), int(y)), int(t * R.uniform(2, 4)), 1, -1, cv2.LINE_AA)
            if R.random() < .94: cv2.circle(m, (int(x), int(y)), max(0, int(t)), 1, -1, cv2.LINE_AA)
    return cv2.GaussianBlur(m, (0, 0), .6)

def gesture(c, h, w, n, wid=(40, 120)):
    """широкий мазок сухой кистью"""
    R = c.R; m = np.zeros((h, w), np.float32)
    for _ in range(int(n)):
        x, y = R.uniform(0, 1) * w, R.uniform(0, 1) * h; a = R.uniform(0, 2 * math.pi); W_ = R.uniform(*wid); L = int(R.uniform(140, 420)); bend = R.normal(0, .004)
        nb = int(W_ / 1.6); offs = np.sort(R.uniform(-W_ / 2, W_ / 2, nb)); press = R.uniform(.35, 1, nb); stop = R.uniform(.55, 1, nb) * L
        for s in range(L):
            bend = bend * .96 + R.normal(0, .0016); a += bend; x += math.cos(a) * 2.2; y += math.sin(a) * 2.2
            fade = min(1, s / 18) * (1 - max(0, (s - L * .6) / (L * .4))) ** .6
            nx, ny = -math.sin(a), math.cos(a)
            for o, pz, st in zip(offs, press, stop):
                if s > st or R.random() < .08 + (1 - fade) * .5: continue
                cv2.circle(m, (int(x + nx * o), int(y + ny * o)), 2, float(pz * fade), -1)
    m = cv2.GaussianBlur(m, (0, 0), 1.2)
    return np.clip(m * (0.7 + 0.6 * fbm(c, h, w, 6, 3)), 0, 1)

def grain(c, h, w, amt):
    g = c.R.normal(0, 1, (h, w)).astype(np.float32); return cv2.GaussianBlur(g, (0, 0), .7) * amt

def vignette(h, w, amt, power=1.0):
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32)
    return np.clip(1 - amt * (((X / w - .5) ** 2 + (Y / h - .5) ** 2) * 2.2) ** power, 0, 1)

def polyline(m, pts, col, th, closed=False):
    if len(pts) < 2: return
    cv2.polylines(m, [np.array(pts, np.float32).round().astype(np.int32)], closed, col if isinstance(col, (int, float)) else tuple(float(v) for v in col), max(1, int(round(th))), cv2.LINE_AA)

# ---------- карта заметности: где на фото «главное» ----------
def saliency(img, center_bias=.35):
    """0..1: спектральный остаток (Hou & Zhang 2007) + лица (если есть каскад OpenCV) + небольшое смещение к центру"""
    h, w = img.shape[:2]
    g = cv2.resize(lum(img).astype(np.float32), (64, 64), interpolation=cv2.INTER_AREA)
    F = np.fft.fft2(g); A = np.log(np.abs(F) + 1e-6); P = np.angle(F)
    R_ = A - cv2.blur(A, (3, 3))
    s = np.abs(np.fft.ifft2(np.exp(R_ + 1j * P))) ** 2
    s = cv2.GaussianBlur(s.astype(np.float32), (0, 0), 2.5)
    s = cv2.resize(s, (w, h), interpolation=cv2.INTER_CUBIC)
    s = (s - s.min()) / (s.max() - s.min() + 1e-6)
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32)
    cb = np.exp(-(((X / w - .5) / .32) ** 2 + ((Y / h - .5) / .36) ** 2))
    s = np.clip(s * (1 - center_bias) + cb * center_bias, 0, 1)
    try:
        casc = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
        if os.path.exists(casc):
            u8 = (lum(img) * 255).astype(np.uint8); k = 640 / max(h, w)
            small = cv2.resize(u8, None, fx=k, fy=k) if k < 1 else u8; k = min(1.0, k)
            for (x, y, fw, fh) in cv2.CascadeClassifier(casc).detectMultiScale(small, 1.15, 5, minSize=(24, 24)):
                cx, cy, rr = (x + fw / 2) / k, (y + fh / 2) / k, max(fw, fh) / k
                s = np.maximum(s, np.exp(-(((X - cx) / (rr * .9)) ** 2 + ((Y - cy) / (rr * 1.2)) ** 2)))
    except Exception: pass
    s = cv2.GaussianBlur(s, (0, 0), max(h, w) / 60)
    return np.clip((s - .25) / .6, 0, 1).astype(np.float32)

# ---------- шрифты (в комплекте, OFL) ----------
FONTS = {
    'wide': 'DelaGothicOne.ttf',        # широкий гротеск, кириллица и катакана, 「」
    'round': 'MPLUSRounded1c-ExtraBold.ttf',
    'cond': 'RobotoCondensed-Bold.ttf',
    'disp': 'Oswald-SemiBold.ttf',
    'typewriter': 'PTMono.ttf',
    'mono': 'JetBrainsMono-Medium.ttf',
    'plex': 'IBMPlexMono-Medium.ttf',
    'arcade': 'RubikMonoOne.ttf',
    'pixel': 'PressStart2P.ttf',
    'geo': 'Unbounded-Bold.ttf',
    'sans': 'Onest-SemiBold.ttf',
    'symbols': 'DejaVuSans-Symbols.ttf',  # запасной: греческий, математика, стрелки, ▶ ● и т. п.
}
_cov = None
def covers(kind, ch):
    global _cov
    if _cov is None:
        import json
        try: _cov = json.load(open(os.path.join(FONTS_DIR, 'coverage.json')))
        except Exception: _cov = {}
    rng = _cov.get(FONTS.get(kind, kind))
    if rng is None: return True
    import bisect
    o = ord(ch); i = bisect.bisect_right([r[0] for r in rng], o) - 1
    return i >= 0 and rng[i][0] <= o <= rng[i][1]

def draw_text(draw, xy, text, kind, px, fill, tracking=0.0, stroke=0, stroke_fill=None):
    """текст с запасным шрифтом для символов, которых нет в основном (≥, ω, ▶ …); xy — левый верх; возвращает x конца"""
    f = font(kind, px); fb = font('symbols', px * .92); x, y = xy
    base = y + f.getmetrics()[0]
    runs = []
    for ch in text:
        k = f if (ch in ' \t' or covers(kind, ch)) else fb
        if tracking or not runs or runs[-1][0] is not k: runs.append([k, ch])
        else: runs[-1][1] += ch
    for k, s in runs:
        kw = dict(stroke_width=int(stroke), stroke_fill=stroke_fill) if stroke else {}
        draw.text((x, base), s, font=k, fill=fill, anchor='ls', **kw)
        x += k.getlength(s) + (f.size * tracking * (1.6 if s == ' ' else 1) if tracking else 0)
    return x

def text_width(text, kind, px, tracking=0.0):
    f = font(kind, px); fb = font('symbols', px * .92)
    return sum((f if covers(kind, ch) or ch == ' ' else fb).getlength(ch) for ch in text) + (len(text) * f.size * tracking if tracking else 0)
_fcache = {}
def font(kind, px):
    from PIL import ImageFont
    px = max(6, int(px)); key = (kind, px)
    if key not in _fcache:
        p = os.path.join(FONTS_DIR, FONTS.get(kind, kind))
        _fcache[key] = ImageFont.truetype(p, px) if os.path.exists(p) else ImageFont.load_default()
    return _fcache[key]

# ---------- ввод-вывод ----------
def load(path, max_side=None):
    data = np.fromfile(path, np.uint8)      # так работают и пути с кириллицей в Windows
    im = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if im is None: raise SystemExit(f'Не удалось открыть {path}')
    return _prep(im, max_side)

def decode(buf, max_side=None):
    im = cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_COLOR)
    if im is None: raise ValueError('Не удалось прочитать изображение')
    return _prep(im, max_side)

def _prep(im, max_side):
    if max_side and max(im.shape[:2]) > max_side:
        k = max_side / max(im.shape[:2]); im = cv2.resize(im, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float32) / 255

def to_u8(img): return (np.clip(img, 0, 1) * 255 + .5).astype(np.uint8)

def flatten(img, bg=(1, 1, 1)):
    """RGBA → RGB поверх фона"""
    if img.ndim == 3 and img.shape[2] == 4:
        a = img[..., 3:4]; return img[..., :3] * a + np.array(bg, np.float32) * (1 - a)
    return img

def encode(img, fmt='png', quality=90):
    fmt = fmt.lower().lstrip('.')
    if fmt in ('jpg', 'jpeg'): img = flatten(img)
    if fmt in ('webp', 'gif'):
        import io
        from PIL import Image
        b = io.BytesIO(); im = Image.fromarray(to_u8(img))
        if fmt == 'webp': im.save(b, 'WEBP', quality=quality, method=4)
        else: im.save(b, 'GIF')
        return b.getvalue()
    ext = '.jpg' if fmt in ('jpg', 'jpeg') else '.png'
    prm = [cv2.IMWRITE_JPEG_QUALITY, int(quality)] if ext == '.jpg' else [cv2.IMWRITE_PNG_COMPRESSION, 3]
    u = to_u8(img); u = cv2.cvtColor(u, cv2.COLOR_RGBA2BGRA if u.shape[2] == 4 else cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(ext, u, prm)
    return buf.tobytes()

def save(img, path, quality=88, quiet=False):
    from PIL import Image
    d = os.path.dirname(path)
    if d: os.makedirs(d, exist_ok=True)
    if path.lower().endswith(('.jpg', '.jpeg')): img = flatten(img)
    im = Image.fromarray(to_u8(img))
    kw = {'quality': quality} if path.lower().endswith(('.jpg', '.jpeg', '.webp')) else {}
    if path.lower().endswith('.webp'): kw['method'] = 6
    im.save(path, **kw)
    if not quiet: print('сохранено:', path)

def cover(img, W, H):
    """обрезать и масштабировать под W×H без искажений"""
    h, w = img.shape[:2]; k = max(W / w, H / h)
    r = cv2.resize(img, (max(W, int(round(w * k))), max(H, int(round(h * k)))), interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_CUBIC)
    y0, x0 = (r.shape[0] - H) // 2, (r.shape[1] - W) // 2
    return r[y0:y0 + H, x0:x0 + W]
