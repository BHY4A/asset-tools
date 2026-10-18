"""Параметры инструментов: описание, пресеты, случайный выбор, сохранение.

Каждый фильтр и генератор описывает свои параметры списком Param. Отсюда же берутся:
  • ключи командной строки: --preset, --set имя=значение, --random [сила], --lock, --params, --save-params;
  • слайдеры и списки в «студии» (studio.py);
  • файл .json рядом с результатом — по нему результат воспроизводится один в один (--preset файл.json).
"""
import json, os, random as _random, sys

class Param:
    def __init__(self, name, default, lo=None, hi=None, kind=None, help='', group='', choices=None, step=None, rand=None):
        # rand: None — случайность во всём диапазоне; (a, b) — разумный диапазон для --random; False — не трогать
        self.rand = rand
        self.name, self.default, self.lo, self.hi, self.help, self.group, self.choices = name, default, lo, hi, help, group, choices
        self.kind = kind or ('bool' if isinstance(default, bool) else 'choice' if choices else 'int' if isinstance(default, int) else
                             'color' if isinstance(default, str) and default.startswith('#') else 'text' if isinstance(default, str) else 'float')
        self.step = step if step is not None else (1 if self.kind == 'int' else None)

    def parse(self, s):
        if self.kind == 'bool': return str(s).lower() in ('1', 'true', 'да', 'yes', 'on', 'вкл')
        if self.kind == 'int': return int(round(float(s)))
        if self.kind == 'float': return float(s)
        if self.kind == 'choice':
            if s not in self.choices: raise SystemExit(f'{self.name}: допустимо {", ".join(map(str, self.choices))}')
            return s
        return str(s)

    def clamp(self, v):
        if self.kind in ('int', 'float') and self.lo is not None:
            v = max(self.lo, min(self.hi, v)); return int(round(v)) if self.kind == 'int' else float(v)
        return v

    def jitter(self, v, amount, rng):
        """случайное значение: amount=1 — любое из диапазона, меньше — отклонение от текущего"""
        if self.rand is False: return v
        if self.kind in ('int', 'float') and self.lo is not None:
            lo, hi = self.rand if isinstance(self.rand, tuple) else (self.lo, self.hi)
            if amount >= 1: return self.clamp(rng.uniform(lo, hi))
            return self.clamp(v + (rng.random() - .5) * 2 * amount * (hi - lo))
        if self.kind == 'choice' and isinstance(self.rand, tuple):
            return rng.choice(list(self.rand)) if rng.random() < amount else v
        if self.kind == 'bool': return (not v) if rng.random() < amount * .5 else v
        if self.kind == 'choice': return rng.choice(self.choices) if rng.random() < amount else v
        if self.kind == 'color' and rng.random() < amount:
            h = v.lstrip('#'); c = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
            return '#' + ''.join(f'{max(0, min(255, int(x + (rng.random() - .5) * 140 * amount))):02x}' for x in c)
        return v

class Spec:
    def __init__(self, tool, params, presets=None, about='', title=None, flags=None):
        self.tool, self.params, self.presets, self.about = tool, params, presets or {}, about
        self.title = title or tool; self.flags = flags or {}
        self.by = {p.name: p for p in params}

    def defaults(self): return {p.name: p.default for p in self.params}

    def table(self):
        out = [f'Параметры «{self.tool}» (имя — по умолчанию — диапазон — что делает):']
        grp = None
        for p in self.params:
            if p.group != grp: grp = p.group; out.append(f'\n  [{grp}]' if grp else '')
            rng = f'{p.lo}…{p.hi}' if p.lo is not None else ('|'.join(map(str, p.choices)) if p.choices else p.kind)
            out.append(f'  {p.name:<18} {str(p.default):<10} {rng:<16} {p.help}')
        if self.presets: out.append('\nПресеты: ' + ', '.join(self.presets))
        return '\n'.join(out)

    def load_preset(self, ref):
        if ref in self.presets: return dict(self.presets[ref]), None
        if os.path.exists(ref):
            d = json.load(open(ref, encoding='utf-8'))
            return dict(d.get('params', d)), d.get('seed')
        raise SystemExit(f'Нет пресета «{ref}». Есть: {", ".join(self.presets) or "—"}; или укажите путь к .json')

    def resolve(self, preset=None, sets=(), random_amount=None, lock=(), seed=None):
        p = self.defaults(); seed_from = None
        if preset:
            pr, seed_from = self.load_preset(preset)
            unknown = set(pr) - set(self.by)
            if unknown: print('  (пропущены неизвестные параметры: ' + ', '.join(sorted(unknown)) + ')', file=sys.stderr)
            p.update({k: v for k, v in pr.items() if k in self.by})
        if seed is None: seed = seed_from if seed_from is not None else (_random.randrange(1, 10 ** 6) if random_amount else 7)
        if random_amount:
            rng = _random.Random(seed * 7919 + 13)
            for prm in self.params:
                if prm.name not in lock and prm.kind not in ('text',) and not prm.name.startswith('_'): p[prm.name] = prm.jitter(p[prm.name], random_amount, rng)
        for s in sets:
            if '=' not in s: raise SystemExit(f'--set ожидает имя=значение, получено «{s}»')
            k, v = s.split('=', 1); k = k.strip()
            if k not in self.by: raise SystemExit(f'Нет параметра «{k}». Список: --params')
            p[k] = self.by[k].clamp(self.by[k].parse(v.strip()))
        return p, seed

    def to_json(self, params, seed): return {'tool': self.tool, 'seed': seed, 'params': params}

    def ui(self):
        """описание для студии"""
        return {'tool': self.tool, 'title': self.title, 'about': self.about, 'flags': self.flags, 'presets': list(self.presets), 'presetValues': self.presets,
                'params': [{'name': p.name, 'default': p.default, 'lo': p.lo, 'hi': p.hi, 'kind': p.kind, 'help': p.help,
                            'group': p.group, 'choices': p.choices, 'step': p.step, 'rand': p.rand is not False} for p in self.params]}

def add_cli(ap):
    g = ap.add_argument_group('параметры')
    g.add_argument('--preset', help='имя встроенного пресета или путь к .json (сохранённому ранее)')
    g.add_argument('--set', action='append', default=[], metavar='ИМЯ=ЗНАЧЕНИЕ', help='задать параметр; можно несколько раз')
    g.add_argument('--random', nargs='?', const=1.0, type=float, metavar='СИЛА',
                   help='случайные параметры: без числа — из всего диапазона; 0.2 — небольшое отклонение от пресета')
    g.add_argument('--lock', default='', help='параметры через запятую, которые --random не трогает')
    g.add_argument('--variants', type=int, default=1, help='сколько вариантов сделать (с --random — разные)')
    g.add_argument('--seed', type=int, default=None, help='зерно случайности; одно и то же зерно — один и тот же результат')
    g.add_argument('--params', action='store_true', help='показать все параметры и пресеты и выйти')
    g.add_argument('--no-save-params', action='store_true', help='не сохранять .json с параметрами рядом с результатом')
    return ap

def runs(args, spec):
    """перечень прогонов: [(params, seed, suffix)]"""
    if args.params: print(spec.table()); raise SystemExit(0)
    lock = {x.strip() for x in args.lock.split(',') if x.strip()}
    out = []
    for i in range(max(1, args.variants)):
        seed = None if args.seed is None else args.seed + i
        if args.random is None and args.seed is None and args.variants > 1: seed = 7 + i
        p, s = spec.resolve(args.preset, args.set, args.random, lock, seed)
        out.append((p, s, f'_{i + 1}' if args.variants > 1 else ''))
    return out

def save_params(path, spec, params, seed):
    jp = os.path.splitext(path)[0] + '.json'
    json.dump(spec.to_json(params, seed), open(jp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return jp
