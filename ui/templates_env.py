"""Jinja2 templates for operational UI."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.templating import Jinja2Templates

UI_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(UI_DIR / "templates"))
templates.env.filters["tojson"] = lambda value, indent=2: json.dumps(value, indent=indent, default=str)
