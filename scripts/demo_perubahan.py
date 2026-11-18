"""
Skrip demo kecil untuk presentasi.

LABEL: DATA UJI, BUKAN DATA JBA.
Skrip ini mensimulasikan deteksi perubahan (baru, tambah, kurang, hilang)
menggunakan fixture v1 dan v2 ke database lokal data/demo.db tanpa menyentuh data/lelang.db.
"""
from pathlib import Path
import sys

# Tambahkan direktori root ke path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import db
from scraper import HasilScrape, parse_hasil

DEMO_DB = ROOT / "data" / "demo.db"


def main():
    print("=" * 60)
    print("DEMO DETEKSI PERUBAHAN HASIL LELANG (DATA UJI SINTETIS)")
    print("=" * 60)

    # Hapus database demo lama jika ada
    if DEMO_DB.exists():
        DEMO_DB.unlink()

    v1_file = ROOT / "tests" / "fixtures" / "hasil_avanza_v1.html"
    v2_file = ROOT / "tests" / "fixtures" / "hasil_avanza_v2.html"

    with open(v1_file, "r", encoding="utf-8") as f:
        html_v1 = f.read()
    with open(v2_file, "r", encoding="utf-8") as f:
        html_v2 = f.read()

    baris_v1, _ = parse_hasil(html_v1, "avanza")
    baris_v2, _ = parse_hasil(html_v2, "avanza")

    with db.buka(DEMO_DB) as conn:
        print("\n1. Menjalankan Run 1 (Fixture v1)...")
        scrape_1 = HasilScrape(berhasil={"avanza": baris_v1}, gagal={}, dihentikan=False, dilewati_baris=0)
        run_id_1 = db.simpan_run(conn, scrape_1, "2026-11-14T01:00:00Z", "2026-11-14T01:05:00Z")
        log_1 = db.log_terakhir(conn)
        print(f"-> Run ID: {run_id_1}, Baseline: {log_1['baseline']}, Status: {log_1['status']}")
        perubahan_1 = db.perubahan_run(conn, run_id_1)
        print(f"-> Event perubahan terdeteksi pada Run 1: {len(perubahan_1)} (seharusnya 0 karena baseline)")

        print("\n2. Menjalankan Run 2 (Fixture v2 dengan perubahan)...")
        scrape_2 = HasilScrape(berhasil={"avanza": baris_v2}, gagal={}, dihentikan=False, dilewati_baris=0)
        run_id_2 = db.simpan_run(conn, scrape_2, "2026-11-14T02:00:00Z", "2026-11-14T02:05:00Z")
        log_2 = db.log_terakhir(conn)
        print(f"-> Run ID: {run_id_2}, Baseline: {log_2['baseline']}, Status: {log_2['status']}")
        perubahan_2 = db.perubahan_run(conn, run_id_2)
        print(f"-> Total Event perubahan terdeteksi pada Run 2: {len(perubahan_2)}")

        print("\nRincian Perubahan yang Terdeteksi:")
        for p in perubahan_2:
            print(f" - [{p['jenis'].upper()}] {p['model']} ({p['tahun']}) | Harga: Rp {p['harga']:,} | Jml: {p['jumlah_lama']} -> {p['jumlah_baru']}")

    print("\n" + "=" * 60)
    print("Demo selesai. Database demo tersimpan di:", DEMO_DB)
    print("=" * 60)


if __name__ == "__main__":
    main()

