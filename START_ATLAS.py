#!/usr/bin/env python3
"""ATLAS Launcher — double-click to start everything."""
import subprocess, sys, time, webbrowser
from pathlib import Path
HERE = Path(__file__).parent
PY = sys.executable
print('Starting ATLAS v3...')
bot  = subprocess.Popen([PY, 'auto_bot.py', '--watch'], cwd=HERE)
dash = subprocess.Popen([PY, 'dashboard_server.py', '--no-browser'], cwd=HERE)
time.sleep(3)
webbrowser.open('http://localhost:8765')
print('ATLAS running. Dashboard: http://localhost:8765')
print('Close this window to stop.')
try:
    bot.wait()
except KeyboardInterrupt:
    bot.terminate()
    dash.terminate()
