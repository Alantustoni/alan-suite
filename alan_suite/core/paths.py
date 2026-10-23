"""
paths.py — Resolução de caminhos da suíte.

Regra: dados do usuário (config, histórico, logs) NUNCA moram dentro do
.EXE/pasta do programa — vão para ~/.alan_suite. Assim o PyInstaller
onefile funciona e nada se perde em atualização de versão.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

APP_DIR = Path.home() / ".alan_suite"
LOG_DIR = APP_DIR / "logs"

CONFIG_PATH    = APP_DIR / "config.json"
HISTORICO_PATH = APP_DIR / "historico.json"
SESSION_PATH   = APP_DIR / "session.json"


def resource_dir() -> Path:
    """Pasta dos recursos empacotados (suporta PyInstaller onefile)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    # raiz do projeto (pasta que contém main.py / config.json de fábrica)
    return Path(__file__).resolve().parent.parent.parent


def garantir_dirs() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    # Primeira execução: copia o config.json de fábrica para ~/.alan_suite
    if not CONFIG_PATH.exists():
        fabrica = resource_dir() / "config.json"
        if fabrica.exists():
            shutil.copy(fabrica, CONFIG_PATH)
