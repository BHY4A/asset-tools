"""Рецепт — цепочка шагов: генератор или фото → фильтр → фильтр …  Сохраняется в .json и повторяется один в один.

{
  "kind": "assetkit-recipe", "version": 1,
  "steps": [
    {"tool": "ether", "params": {"palette": "полночь"}, "seed": 7},
    {"tool": "palette", "params": {"palette": "Графит"}, "seed": 7, "on": true}
  ]
}
Старый формат одного инструмента ({"tool", "seed", "params"}) тоже читается.
"""
import json, os
import numpy as np, cv2
from .registry import get

def normalize(data):
    if isinstance(data, list): steps = data
    elif 'steps' in data: steps = data['steps']
    elif 'tool' in data: steps = [{'tool': data['tool'], 'params': data.get('params', {}), 'seed': data.get('seed', 7)}]
    else: raise ValueError('Это не рецепт: нет поля steps')
    out = []
    for s in steps:
        t = get(s['tool'])
        out.append({'tool': t.id, 'params': dict(s.get('params', {})), 'seed': int(s.get('seed', 7)), 'on': bool(s.get('on', True))})
    return out

def load(path):
    return normalize(json.load(open(path, encoding='utf-8')))

def dump(steps, path=None):
    data = {'kind': 'assetkit-recipe', 'version': 1, 'steps': steps}
    if path: json.dump(data, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return data

def needs_photo(steps):
    on = [s for s in steps if s.get('on', True)]
    return bool(on) and get(on[0]['tool']).kind == 'filter'

def scaled(tool, params, max_side):
    """параметры генератора для уменьшенного предпросмотра (пропорции сохраняются)"""
    p = dict(params); sp = tool.spec
    if max_side and 'width' in sp.by and 'height' in sp.by:
        W = p.get('width', sp.by['width'].default); H = p.get('height', sp.by['height'].default)
        k = min(1.0, max_side / max(W, H))
        if k < 1: p['width'], p['height'] = max(64, int(W * k)), max(48, int(H * k))
    if max_side and 'size' in sp.by and tool.id == 'icon': p['size'] = min(p.get('size', 512), max(64, max_side))
    return p

def run(steps, photo=None, max_side=None, upto=None):
    """выполнить цепочку; photo — RGB float 0..1 или None; upto — сколько шагов выполнить (для «до/после»)"""
    img = photo
    active = [s for s in steps if s.get('on', True)]
    if upto is not None: active = active[:upto]
    if not active:
        if img is None: raise ValueError('Цепочка пуста')
        return img
    for i, s in enumerate(active):
        t = get(s['tool'])
        if t.kind == 'gen':
            img = t.run(None, scaled(t, s.get('params', {}), max_side), s.get('seed', 7))
        else:
            if img is None: raise ValueError('Первый шаг — фильтр: загрузите фото или начните цепочку с генератора')
            src = img
            if src.ndim == 3 and src.shape[2] == 4:   # прозрачность: фильтру — картинку на сером
                a = src[..., 3:4]; src = src[..., :3] * a + .5 * (1 - a)
            p = dict(s.get('params', {}))
            if max_side and t.id == 'card':
                W, H = p.get('width', 1200), p.get('height', 630); k = min(1.0, max_side / max(W, H)); p['width'], p['height'] = int(W * k), int(H * k)
            if max_side and t.id == 'signal':
                p['width'] = min(p.get('width', 720), max_side)
            img = t.run(src, p, s.get('seed', 7))
    return img
