import sys
from pathlib import Path

# Add parent directory to sys.path so 'app' can be imported cleanly
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.main import app
