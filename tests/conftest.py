import sys
from pathlib import Path

# Tambahkan direktori root proyek ke sys.path agar modul utama dapat diimpor
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

