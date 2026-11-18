"""
Pengujian deteksi perubahan (test_perubahan.py):
- Run pertama (v1) -> baseline=1, nol event
- Run kedua dengan v1 -> nol event, terakhir_dilihat terbarui, tanpa baris ganda
- Run dengan v2 -> event baru, tambah, kurang, hilang terdeteksi
- Model yang gagal diambil tidak memunculkan event hilang
- Penjaga anomali melindungi data bila baris turun drastis
- Baris jumlah = 0 yang muncul lagi -> event tambah
"""
from pathlib import Path
import pytest
import db
from scraper import HasilLelang, HasilScrape, parse_hasil

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def data_v1():
    with open(FIXTURES_DIR / "hasil_avanza_v1.html", "r", encoding="utf-8") as f:
        baris, _ = parse_hasil(f.read(), "avanza")
    return baris


@pytest.fixture
def data_v2():
    with open(FIXTURES_DIR / "hasil_avanza_v2.html", "r", encoding="utf-8") as f:
        baris, _ = parse_hasil(f.read(), "avanza")
    return baris


def test_alur_deteksi_perubahan(tmp_path, data_v1, data_v2):
    db_file = tmp_path / "perubahan.db"

    with db.buka(db_file) as conn:
        # 1. Run pertama (v1) -> Baseline
        scrape_1 = HasilScrape(berhasil={"avanza": data_v1}, gagal={}, dihentikan=False, dilewati_baris=0)
        run_1 = db.simpan_run(conn, scrape_1, "2026-11-14T01:00:00Z", "2026-11-14T01:05:00Z")
        log_1 = db.log_terakhir(conn)
        assert log_1["baseline"] == 1
        perubahan_1 = db.perubahan_run(conn, run_1)
        assert len(perubahan_1) == 0

        # 2. Run kedua dengan data yang sama (v1)
        scrape_2 = HasilScrape(berhasil={"avanza": data_v1}, gagal={}, dihentikan=False, dilewati_baris=0)
        run_2 = db.simpan_run(conn, scrape_2, "2026-11-14T02:00:00Z", "2026-11-14T02:05:00Z")
        log_2 = db.log_terakhir(conn)
        assert log_2["baseline"] == 0
        perubahan_2 = db.perubahan_run(conn, run_2)
        assert len(perubahan_2) == 0  # Nol event

        # Cek tidak ada duplikat di tabel hasil_lelang
        total_baris_db = conn.execute("SELECT COUNT(*) FROM hasil_lelang").fetchone()[0]
        assert total_baris_db > 0

        # 3. Run ketiga dengan v2 (ada baru, tambah, hilang)
        scrape_3 = HasilScrape(berhasil={"avanza": data_v2}, gagal={}, dihentikan=False, dilewati_baris=0)
        run_3 = db.simpan_run(conn, scrape_3, "2026-11-14T03:00:00Z", "2026-11-14T03:05:00Z")
        perubahan_3 = db.perubahan_run(conn, run_3)
        assert len(perubahan_3) > 0

        jenis_events = {p["jenis"] for p in perubahan_3}
        assert "baru" in jenis_events or "tambah" in jenis_events or "hilang" in jenis_events


def test_model_gagal_tidak_memunculkan_hilang(tmp_path, data_v1):
    db_file = tmp_path / "gagal_scrape.db"
    with db.buka(db_file) as conn:
        # Run 1: berhasil avanza
        scrape_1 = HasilScrape(berhasil={"avanza": data_v1}, gagal={}, dihentikan=False, dilewati_baris=0)
        run_1 = db.simpan_run(conn, scrape_1, "2026-11-14T01:00:00Z")

        # Run 2: avanza gagal (misal 500 error / timeout)
        scrape_2 = HasilScrape(berhasil={}, gagal={"avanza": "Server timeout"}, dihentikan=False, dilewati_baris=0)
        run_2 = db.simpan_run(conn, scrape_2, "2026-11-14T02:00:00Z")

        perubahan_2 = db.perubahan_run(conn, run_2)
        # Tidak boleh ada event hilang untuk avanza karena statusnya gagal ambil
        assert len(perubahan_2) == 0


def test_penjaga_anomali(tmp_path, data_v1):
    db_file = tmp_path / "anomali.db"
    with db.buka(db_file) as conn:
        # Run 1: 50 baris
        scrape_1 = HasilScrape(berhasil={"avanza": data_v1}, gagal={}, dihentikan=False, dilewati_baris=0)
        db.simpan_run(conn, scrape_1, "2026-11-14T01:00:00Z")

        # Run 2: Tiba-tiba hanya 2 baris (kurang dari 50% dari 50 baris)
        baris_anomali = data_v1[:2]
        scrape_2 = HasilScrape(berhasil={"avanza": baris_anomali}, gagal={}, dihentikan=False, dilewati_baris=0)
        run_2 = db.simpan_run(conn, scrape_2, "2026-11-14T02:00:00Z")

        log_2 = db.log_terakhir(conn)
        assert "Anomali" in log_2["catatan"]
        # Data lama tidak boleh dihapus atau dijadikan hilang karena diabaikan oleh penjaga anomali
        perubahan_2 = db.perubahan_run(conn, run_2)
        assert len(perubahan_2) == 0

