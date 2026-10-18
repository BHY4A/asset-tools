#!/usr/bin/env python3
"""Студия в браузере, быстрый локальный режим.  python studio.py [--port 8777] [--no-browser]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assetkit.cli import main
if __name__ == '__main__': main(['studio'] + sys.argv[1:])
