# conftest.py
import sys
from pathlib import Path

# Force the project root directory onto the top of sys.path
root_path = Path(__file__).parent.resolve()
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))