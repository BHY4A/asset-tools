"""Все инструменты в одном месте: фильтры (берут картинку) и генераторы (рисуют с нуля)."""
from .filters import signal, aquarelle, glare, neon, lines, palette, card
from .gen import ether, watercolor, film, neonsign, glass, graphite, tiles, icon

class Tool:
    def __init__(self, tid, kind, mod, fn=None):
        self.id, self.kind, self.mod = tid, kind, mod
        self.spec = mod.SPEC; self.fn = fn or mod.apply
    def run(self, img, params, seed):
        p = self.clean(params)
        return self.fn(img, p, seed) if self.kind == 'filter' else self.fn(p, seed)
    def clean(self, params):
        """значения из JSON/интерфейса → нужные типы и диапазоны; неизвестное и неверное — по умолчанию"""
        p = self.spec.defaults()
        for k, v in (params or {}).items():
            prm = self.spec.by.get(k)
            if prm is None: continue
            try: p[k] = prm.clamp(prm.parse(v) if not (prm.kind == 'bool' and isinstance(v, bool)) else v)
            except (ValueError, TypeError, SystemExit): pass
        return p
    def ui(self):
        d = self.spec.ui(); d.update(id=self.id, kind=self.kind); return d

TOOLS = {}
for tid, mod in [('signal', signal), ('aquarelle', aquarelle), ('glare', glare), ('neon', neon), ('lines', lines), ('palette', palette), ('card', card)]:
    TOOLS[tid] = Tool(tid, 'filter', mod)
for tid, mod in [('ether', ether), ('neonsign', neonsign), ('glass', glass), ('graphite', graphite), ('watercolor', watercolor), ('film', film), ('tiles', tiles), ('icon', icon)]:
    TOOLS[tid] = Tool(tid, 'gen', mod)

def get(tid):
    if tid not in TOOLS:
        # совместимость с .json старого формата: там tool = имя спецификации
        for t in TOOLS.values():
            if t.spec.tool == tid: return t
        raise ValueError(f'Нет инструмента «{tid}». Есть: {", ".join(TOOLS)}')
    return TOOLS[tid]
