@echo off
REM ── Build do Contas a Pagar Suite (.EXE) ──────────────────────────────────────
REM Requisitos: pip install pyinstaller  (alem do requirements.txt)
cd /d "%~dp0"

pyinstaller --noconfirm --clean --onefile --windowed ^
  --name "Contas a Pagar Suite" ^
  --add-data "config.json;." ^
  --collect-all customtkinter ^
  --paths "contas_a_pagar_suite\vendor\remessa_v3" ^
  --hidden-import services ^
  --hidden-import services.parsers ^
  --hidden-import services.reconciler ^
  --hidden-import services.exporter ^
  --hidden-import services.excel_reader ^
  --hidden-import core ^
  --hidden-import core.utils ^
  --hidden-import core.logger ^
  --hidden-import core.session ^
  --hidden-import core.theme ^
  --hidden-import ui ^
  --hidden-import ui.main_window ^
  --hidden-import ui.dashboard ^
  --hidden-import ui.attention_table ^
  --hidden-import ui.widgets ^
  --hidden-import openpyxl ^
  --hidden-import rapidfuzz ^
  --hidden-import xlrd ^
  main.py

echo.
echo ── Build concluido. O executavel esta em dist\"Contas a Pagar Suite.exe" ──
pause
