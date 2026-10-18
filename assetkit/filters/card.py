"""«Обложка» — превью ссылки (Open Graph, 1200×630) или баннер: картинка-фон + затемнение, заголовок, подзаголовок,
метка и значок утилиты. В цепочке удобно после генератора: «Эфир: сцена → Обложка»."""
import numpy as np, cv2
from PIL import Image, ImageDraw
from ..params import Param, Spec
from ..core import hexc, cover, draw_text, text_width, font
from .. import motifs

SPEC = Spec('card', [
    Param('width', 1200, 300, 3000, group='формат', help='ширина, px (OG — 1200×630)', rand=False), Param('height', 630, 150, 3000, group='формат', help='высота, px', rand=False),
    Param('title', 'Электропривод · ЛР 1–6', group='текст', help='заголовок'), Param('subtitle', 'Расчёт по варианту, отчёт Word и файлы MATLAB', group='текст', help='подзаголовок'),
    Param('label', 'КНИТУ', group='текст', help='метка в углу (пусто — нет)'),
    Param('app', 'sapr-labs', kind='choice', choices=motifs.APPS + ['hub', 'нет'], group='текст', help='значок', rand=False),
    Param('font', 'geo', kind='choice', choices=['geo', 'wide', 'disp', 'cond', 'round', 'arcade', 'sans', 'mono'], group='шрифт', help='шрифт заголовка'),
    Param('title_size', 1.0, .4, 2.0, group='шрифт', help='размер заголовка', rand=(.8, 1.2)), Param('tracking', 0.0, 0.0, .6, group='шрифт', help='разрядка заголовка'),
    Param('layout', 'слева', kind='choice', choices=['слева', 'по центру', 'снизу'], group='компоновка', help='где текст'),
    Param('scrim', .65, 0.0, 1.0, group='компоновка', help='затемнение под текстом'), Param('scrim_color', '#0b0f16', group='компоновка', help='цвет затемнения'),
    Param('text_color', '#ffffff', group='цвет', help='цвет текста'), Param('accent', 'авто', group='цвет', help='цвет метки и полосы; «авто» — цвет утилиты'),
    Param('bar', 1.0, 0.0, 1.0, group='цвет', help='цветная полоса у края'),
], {
    'OG слева': {}, 'по центру': dict(layout='по центру', scrim=.5), 'низ': dict(layout='снизу', scrim=.75),
    'светлая': dict(scrim_color='#fbfcfd', text_color='#1a222b', scrim=.8), 'неон': dict(font='arcade', scrim_color='#12041e', text_color='#ffe14a', accent='#ff2fa8'),
    'эфир': dict(font='wide', tracking=.12, scrim_color='#2a0b4a', accent='#ff32bb', layout='по центру'),
}, title='Обложка', about='Превью ссылки 1200×630: фон, затемнение, заголовок, подзаголовок, метка и значок')

def _wrap(text, kind, px, maxw):
    words = [w for w in text.replace(' · ', '\u00a0· ').replace(' — ', '\u00a0— ').split(' ') if w]; lines = []; cur = ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if text_width(t, kind, px) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def apply(img, p, seed=7):
    W, H = int(p['width']), int(p['height']); u = W / 1200
    bg = cover(img[..., :3] if img.ndim == 3 else img, W, H)
    lay = p['layout']; sc = hexc(p['scrim_color'])
    X = np.linspace(0, 1, W)[None, :]; Y = np.linspace(0, 1, H)[:, None]
    if lay == 'слева': m = np.clip(1.25 - X * 1.4, 0, 1) ** 1.2 * np.ones((H, 1))
    elif lay == 'снизу': m = np.clip((Y - .25) * 1.6, 0, 1) ** 1.2 * np.ones((1, W))
    else: m = np.clip(1 - np.sqrt(((X - .5) / .6) ** 2 + ((Y - .5) / .7) ** 2), 0, 1) * .6 + .4
    m = (m * p['scrim'])[..., None]
    out = bg * (1 - m) + sc * m
    acc = hexc(p['accent'] if str(p['accent']).startswith('#') else motifs.ACCENT.get(p['app'], motifs.ACCENT['нет'])[0 if sc.mean() > .5 else 1])
    pil = Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)); dr = ImageDraw.Draw(pil)
    tc = tuple(int(v * 255) for v in hexc(p['text_color'])); ac = tuple(int(v * 255) for v in acc)
    if p['bar'] > 0: dr.rectangle([0, 0, int(10 * u), H] if lay != 'снизу' else [0, H - int(10 * u), W, H], fill=ac)
    pad = int(72 * u); maxw = int(W * (.62 if lay == 'слева' else .84))
    tp = int(66 * u * p['title_size']); sp = int(28 * u)
    tl = _wrap(p['title'], p['font'], tp, maxw); sl = _wrap(p['subtitle'], 'sans', sp, maxw) if p['subtitle'] else []
    block_h = len(tl) * tp * 1.18 + (sp * .8 if sl else 0) + len(sl) * sp * 1.35 + (int(tp * 1.4) if p['app'] in motifs.ICONS else 0)
    y = (H - block_h) / 2 if lay != 'снизу' else H - pad - block_h
    def xpos(wd): return (W - wd) / 2 if lay == 'по центру' else pad
    if p['app'] in motifs.ICONS:
        from ..gen.icon import apply as icon
        isz = int(tp * 1.15); ic = icon({'app': p['app'], 'look': 'плоский', 'size': isz, 'bg': '#%02x%02x%02x' % ac, 'fg': '#ffffff' if float(acc @ np.array([.2126, .7152, .0722])) < .6 else '#1a222b', 'radius': .22, 'pad': 0, 'stroke': 1.0, 'shadow': 0, 'pixel': 32})
        icim = Image.fromarray((np.clip(ic, 0, 1) * 255).astype(np.uint8), 'RGBA'); pil.paste(icim, (int(xpos(isz)), int(y)), icim); y += tp * 1.4
    for ln in tl:
        draw_text(dr, (xpos(text_width(ln, p['font'], tp, p['tracking'])), y), ln, p['font'], tp, tc, p['tracking']); y += tp * 1.18
    y += sp * .8
    for ln in sl:
        draw_text(dr, (xpos(text_width(ln, 'sans', sp)), y), ln, 'sans', sp, tc); y += sp * 1.35
    if p['label']:
        fp = int(20 * u); tw = text_width(p['label'], 'sans', fp, .12); x1 = W - pad; x0 = x1 - tw - 28 * u; y0 = int(40 * u)
        dr.rounded_rectangle([x0, y0, x1, y0 + fp * 1.9], radius=int(fp), fill=ac)
        lum = acc @ np.array([.2126, .7152, .0722]); draw_text(dr, (x0 + 14 * u, y0 + fp * .42), p['label'], 'sans', fp, (20, 20, 24) if lum > .55 else (255, 255, 255), .12)
    return np.asarray(pil).astype(np.float32) / 255
