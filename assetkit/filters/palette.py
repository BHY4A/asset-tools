"""Палитра стиля: приводит любое фото к цветам выбранного стиля (градиентная карта, ближайший цвет, растр)."""
import numpy as np, cv2
from ..params import Param, Spec
from ..core import hexc, lum

# от тёмного к светлому — так их удобно класть на яркость
PALETTES = {
    'Журнал':   ['#1a222b', '#0a5aa8', '#5a6776', '#dfe5ea', '#fbfcfd'],
    'Лазурь':   ['#06264a', '#0b4f9c', '#1f7fd6', '#9fd4f6', '#f2fbff'],
    'Акварель': ['#1f1b17', '#56668a', '#b0583a', '#c99a4e', '#e8e1d2'],
    'Засветка': ['#1d2219', '#4e5e4e', '#2f6f68', '#c48c1e', '#f4efd6'],
    'Неон':     ['#12041e', '#3b0a5c', '#b0177f', '#ff4f8f', '#ff9a3c', '#ffe14a'],
    'Эфир':     ['#090322', '#2a0b4a', '#b05cff', '#ff32bb', '#ffb3d9', '#bfe9ff'],
    'Стекло':   ['#1b2236', '#4a5f9a', '#8fb8ff', '#ffc4a2', '#eef0f5'],
    'Графит':   ['#08090c', '#1b2130', '#2a3340', '#3f74b0', '#cfe3ff'],
    'Геймбой':  ['#0f380f', '#306230', '#8bac0f', '#9bbc0f'],
    'Сепия':    ['#2b1d12', '#6b4a2b', '#a27a4a', '#d9c7a5', '#f4ead6'],
    'Ч/б':      ['#000000', '#ffffff'],
}
_BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) / 16 - .47

SPEC = Spec('palette', [
    Param('palette', 'Эфир', kind='choice', choices=list(PALETTES) + ['своя'], group='палитра', help='палитра какого стиля'),
    Param('custom', '#101820, #f2aa4c, #f7f3e8', group='палитра', help='своя палитра: цвета через запятую (тёмные → светлые)'),
    Param('mode', 'градиент', kind='choice', choices=['градиент', 'ближайший', 'растр'], group='палитра',
          help='градиент — плавная карта по яркости; ближайший — каждый пиксель к ближайшему цвету; растр — то же с узором', rand=('градиент', 'ближайший', 'растр')),
    Param('amount', 1.0, 0.0, 1.0, group='смешивание', help='сила (0 — исходник)', rand=(.6, 1.0)),
    Param('keep_luma', 0.0, 0.0, 1.0, group='смешивание', help='сохранить исходную яркость'),
    Param('contrast', 1.0, .3, 2.5, group='смешивание', help='контраст до перекраски', rand=(.8, 1.6)),
    Param('shift', 0.0, -.5, .5, group='смешивание', help='сдвиг по палитре к тёмным / светлым'),
    Param('dither', 1.0, 1.0, 8.0, group='растр', help='размер клетки растра', step=1, rand=(1.0, 4.0)),
    Param('posterize', 0, 0, 12, group='растр', help='ступени градиента (0 — плавно)', rand=(0, 8)),
], {
    'эфир': {}, 'неон': dict(palette='Неон'), 'графит': dict(palette='Графит', contrast=1.2),
    'геймбой': dict(palette='Геймбой', mode='растр', dither=2), 'сепия': dict(palette='Сепия', keep_luma=.4),
    'газета': dict(palette='Ч/б', mode='растр', dither=3, contrast=1.3),
}, title='Палитра стиля', about='Приводит фото к цветам стиля: градиентная карта, ближайший цвет или растр')

def colors(p):
    if p['palette'] == 'своя':
        cs = [hexc(x) for x in str(p['custom']).replace(';', ',').split(',') if x.strip()]
        return np.array(cs if len(cs) >= 2 else [hexc('#000'), hexc('#fff')], np.float32)
    return np.array([hexc(x) for x in PALETTES[p['palette']]], np.float32)

def apply(img, p, seed=7):
    cs = colors(p); n = len(cs); h, w = img.shape[:2]
    L = np.clip((lum(img) - .5) * p['contrast'] + .5 + p['shift'], 0, 1)
    if p['mode'] == 'градиент':
        t = L
        if p['posterize'] >= 2: t = np.round(t * (p['posterize'] - 1)) / (p['posterize'] - 1)
        xs = np.linspace(0, 1, n); out = np.dstack([np.interp(t, xs, cs[:, i]) for i in range(3)]).astype(np.float32)
    else:
        src = np.clip((img - .5) * p['contrast'] + .5 + p['shift'], 0, 1)
        if p['mode'] == 'растр':
            k = int(p['dither']); th = np.tile(np.repeat(np.repeat(_BAYER, k, 0), k, 1), (h // (4 * k) + 1, w // (4 * k) + 1))[:h, :w]
            src = np.clip(src + th[..., None] * (1.0 / max(1, n - 1)), 0, 1)
        d = ((src[:, :, None, :] - cs[None, None]) ** 2).sum(-1)
        # яркость важнее оттенка — иначе тёмное уходит в соседний по тону цвет
        d += 2.0 * (lum(src)[..., None] - lum(cs[None, None])) ** 2
        out = cs[np.argmin(d, -1)]
    if p['keep_luma'] > 0:
        r = (lum(img) + 1e-3) / (lum(out) + 1e-3); out = out * (1 - p['keep_luma']) + np.clip(out * r[..., None], 0, 1) * p['keep_luma']
    return np.clip(img * (1 - p['amount']) + out * p['amount'], 0, 1)
