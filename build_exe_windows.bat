@echo off
cd /d "%~dp0"
if not exist .venv (
  py -3.12 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt
pyinstaller --noconfirm --clean --windowed --name ImageRemasterAI --add-data "ai;ai" --add-data "input;input" --add-data "output;output" app.py
