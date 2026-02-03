@echo off
cd /d %~dp0
call venv\Scripts\activate
start /B pythonw.exe simple-music-player_windows-test.py
exit