"""
Konfigurasi terpusat aplikasi pantau lelang JBA.
"""
import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Muat file .env jika ada
load_dotenv()

# Direktori utama
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
LOG_DIR = ROOT / "logs"

# Database
DB_PATH = DATA_DIR / "lelang.db"

# URL dan Pola JBA
BASE_URL = os.getenv("BASE_URL", "https://www.jba.co.id")
SITEMAP_HASIL = f"{BASE_URL}/sitemap/id-hasil-lelang-mobil.xml"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
POLA_URL_MODEL = re.compile(r"^https://www\.jba\.co\.id/id/hasil-harga-lelang/lelang/([a-z0-9-]+)$")

# Parameter Scraping
JEDA_DETIK = max(1.0, float(os.getenv("JEDA_DETIK", "1.5")))
TIMEOUT_DETIK = int(os.getenv("TIMEOUT_DETIK", "15"))
MAKS_COBA = int(os.getenv("MAKS_COBA", "3"))
FAKTOR_BACKOFF = float(os.getenv("FAKTOR_BACKOFF", "2.0"))

# Ambang Deteksi
AMBANG_ANOMALI = 0.5
MIN_SAMPEL = 5

# Waktu dan Penjadwalan
JAM_JADWAL = os.getenv("JAM_JADWAL", "07:00")
ZONA_WAKTU = "Asia/Jakarta"
KIRIM_JIKA_TIDAK_ADA_PERUBAHAN = os.getenv("KIRIM_JIKA_TIDAK_ADA_PERUBAHAN", "true").lower() in ("true", "1", "yes")

# Kredensial dan Kontak
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "").strip()


def bangun_user_agent() -> str:
    """Membangun string User-Agent dengan kontak email pengguna."""
    if not CONTACT_EMAIL:
        raise ValueError(
            "CONTACT_EMAIL di .env belum diisi! Harap cantumkan email kontak untuk mematuhi etika scraping."
        )
    return f"PantauHasilLelangJBA/1.0 (Tugas Kuliah Scripting Language; kontak: {CONTACT_EMAIL})"


def validasi_untuk_bot() -> None:
    """Memvalidasi kelengkapan token bot Telegram."""
    if not BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN di .env belum diisi! Salin .env.example menjadi .env lalu isi token bot dari @BotFather."
        )

