#!/usr/bin/env python3
"""Asset Tools — фильтры для фото, генераторы фонов и текстур, цепочки, анимация и конвейер для сайта.

  python at.py -h          все команды
  python at.py studio      студия в браузере
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')      # кириллица в консоли Windows
    except Exception: pass
from assetkit.cli import main

if __name__ == '__main__': main()
