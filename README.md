# Simple Music Player

A lightweight desktop music player built with Python + PyQt6.
Browse your library and play audio with a simple interface.

![Screenshot on Windows 11](screenshot-windows.jpg)

## Requirements
- Python 3.10+
- pip
- Git (optional, for cloning)

## Setup
Clone or download the project, then open terminal/command-prompt in the project folder (the folder containing simple-music-player.py).

You should see:
```
simple-music-player.py
icons/
requirements.txt
launch-linux.sh
launch-windows.bat
```

### Linux (Kubuntu / Ubuntu / Debian)
```
sudo apt install python3-venv
python3 -m venv venv
source venv/bin/activate
cd ../..
pip install -r requirements.txt
```
launch-linux.sh

### Windows
```
python -m venv venv
cd venv\Scripts
activate
cd ../..
pip install -r requirements.txt
```
launch-windows.bat
