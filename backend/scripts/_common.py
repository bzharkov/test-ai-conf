import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # allows `python -I scripts/x.py`
    sys.path.insert(0, str(ROOT))
