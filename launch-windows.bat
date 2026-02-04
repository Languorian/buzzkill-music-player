@echo off
cd /d %~dp0
call venv\Scripts\activate
start /B pythonw.exe buzzkill-music-player.py
exit