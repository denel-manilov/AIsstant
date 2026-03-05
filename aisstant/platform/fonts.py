"""Cross-platform monospace font selection."""

from __future__ import annotations

import sys

if sys.platform == "darwin":
    MONOSPACE_FONT = "SF Mono"
elif sys.platform == "win32":
    MONOSPACE_FONT = "Cascadia Mono"
else:
    MONOSPACE_FONT = "monospace"
