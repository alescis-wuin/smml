from __future__ import annotations

import sys
from pathlib import Path

REFERENCE = Path(__file__).resolve().parents[1] / "reference" / "python"
if str(REFERENCE) not in sys.path:
    sys.path.insert(0, str(REFERENCE))

from smml_reference.path_policy import *  # noqa: F401,F403,E402
