"""
Pengujian db.py:
- buat_skema idempoten
- kueri berparameter aman SQL injection
- simpan_run atomik
"""
import pytest
import db
from scraper import HasilLelang, HasilScrape


def test_buat_skema_idempoten(tmp_path):
    db_file = tmp_path / "test_skema.db"
    with db.buka(db_file) as conn:
        db.buat_skema(conn)
        # Panggil kedua kali harus idempoten tanpa error
        db.buat_skema(conn)
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        assert "scrape_log" in tables
        assert "hasil_lelang" in tables
        assert "riwayat_model" in tables
        assert "perubahan" in tables
        assert "pelanggan" in tables


def test_kueri_parameter_aman_sql_injection(tmp_path):
    db_file = tmp_path / "test_sqli.db"
    with db.buka(db_file) as conn:
        db.buat_skema(conn)
        # Masukkan 1 baris
        conn.execute(
            """INSERT INTO hasil_lelang (model_slug, merek, model, tahun, lokasi, harga, jumlah, pertama_dilihat, terakhir_dilihat)
               VALUES ('avanza', 'Toyota', 'Avanza G', 2020, 'Jakarta', 150000000, 1, '2026-11-14', '2026-11-14')"""
        )
        # Uji SQL injection payload
        payload = "'; DROP TABLE hasil_lelang;--"
        hasil = db.cari_model(conn, payload)
        assert len(hasil) == 0

        # Tabel hasil_lelang tetap utuh
        count = conn.execute("SELECT COUNT(*) FROM hasil_lelang").fetchone()[0]
        assert count == 1


def test_simpan_run_atomik(tmp_path):
    db_file = tmp_path / "test_atomik.db"
    with db.buka(db_file) as conn:
        db.buat_skema(conn)

    # Scrape normal
    baris = [HasilLelang("avanza", "Toyota", "Avanza G", 2020, "Jakarta", 150000000)]
    scrape = HasilScrape(berhasil={"avanza": baris}, gagal={}, dihentikan=False, dilewati_baris=0)

    with db.buka(db_file) as conn:
        run_id = db.simpan_run(conn, scrape, "2026-11-14T00:00:00Z")
        assert run_id > 0
        total_awal = conn.execute("SELECT COUNT(*) FROM hasil_lelang").fetchone()[0]
        assert total_awal == 1

