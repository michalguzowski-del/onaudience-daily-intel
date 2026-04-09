#!/usr/bin/env python3
"""Inlinuje CSS do HTML i zapisuje finalny plik email-ready."""
from pathlib import Path

from bootstrap_deps import ensure_module

transform = ensure_module("premailer", "premailer").transform

src = Path("/home/ubuntu/onaudience_daily_intel_src.html").read_text(encoding="utf-8")
result = transform(src, remove_classes=False, strip_important=False)
Path("/home/ubuntu/onaudience_daily_intel_2026-04-03.html").write_text(result, encoding="utf-8")
print("✅ CSS zinlinowany i zapisany do onaudience_daily_intel_2026-04-03.html")
