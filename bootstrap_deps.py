"""Pomocnicze ładowanie brakujących zależności Pythona dla lokalnych uruchomień."""

from __future__ import annotations

import importlib
import site
import subprocess
import sys
from typing import Optional


def ensure_module(import_name: str, package_name: Optional[str] = None):
    """Importuje moduł, a jeśli go brakuje, instaluje pakiet i ponawia import."""
    package_name = package_name or import_name
    try:
        return importlib.import_module(import_name)
    except ModuleNotFoundError:
        print(f"[BOOTSTRAP] Brak pakietu '{package_name}'. Instaluję go automatycznie...")

    install_attempts = [
        [sys.executable, "-m", "pip", "install", "--user", package_name],
        ["sudo", "pip3", "install", package_name],
    ]

    last_error = None
    for command in install_attempts:
        result = subprocess.run(command, check=False)
        if result.returncode == 0:
            site.addsitedir(site.getusersitepackages())
            try:
                return importlib.import_module(import_name)
            except ModuleNotFoundError as exc:
                last_error = exc
        else:
            last_error = RuntimeError(
                f"Instalacja pakietu '{package_name}' nie powiodła się dla komendy: {' '.join(command)}"
            )

    raise RuntimeError(
        f"Nie udało się automatycznie zainstalować brakującego pakietu '{package_name}'."
    ) from last_error
