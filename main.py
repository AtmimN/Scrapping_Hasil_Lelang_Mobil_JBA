"""
Titik masuk pipeline pemantau lelang JBA.
"""
import argparse
import logging
import sys
import time
from typing import Any, Optional
import pandas as pd

import analisis
import config
import db
import laporan
from scraper import Pengambil

config.LOG_DIR.mkdir(parents=True, exist_ok=True)
config.DATA_DIR.mkdir(parents=True, exist_ok=True)
config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_DIR / "pipeline.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("pipeline")


def _lakukan_scraping(conn, maks_model: Optional[int]) -> str:
    config.bangun_user_agent()
    mulai_iso = db.waktu_utc_sekarang()
    hasil_scrape = Pengambil(jeda=config.JEDA_DETIK).ambil_semua(maks_model=maks_model)
    selesai_iso = db.waktu_utc_sekarang()
    run_id = db.simpan_run(conn, hasil_scrape, mulai_iso, selesai_iso)
    log.info("Hasil tersimpan di database dengan run_id: %d", run_id)
    if hasil_scrape.dihentikan:
        return "dihentikan"
    if not hasil_scrape.berhasil and hasil_scrape.gagal:
        return "gagal"
    return "sukses"


def _buat_output_analisis(conn, df, r, buat_laporan_flag: bool):
    riw = conn.execute("SELECT * FROM riwayat_model").fetchall()
    riw_df = pd.DataFrame([dict(rw) for rw in riw]) if riw else None
    grafik = analisis.buat_grafik_semua(df, riwayat_df=riw_df)
    xl = pdf = None
    if buat_laporan_flag:
        xl = laporan.buat_excel(df, r, db.perubahan_run(conn))
        pdf = laporan.buat_pdf(r, analisis.per_model(df), grafik)
        log.info("Laporan dibuat: %s & %s", xl.name, pdf.name)
    return grafik, xl, pdf


def jalankan_pipeline(maks_model: Optional[int] = None, tanpa_scrape: bool = False, buat_laporan_flag: bool = True) -> dict[str, Any]:
    log.info("Memulai pipeline pantau lelang JBA")
    t0, status_run = time.time(), "sukses"
    with db.buka(config.DB_PATH) as conn:
        db.buat_skema(conn)
        if not tanpa_scrape:
            try:
                status_run = _lakukan_scraping(conn, maks_model)
            except Exception as e:
                log.error("Scraping gagal: %s", e)
                return {"status": "gagal", "alasan": str(e)}
        df = analisis.ke_dataframe(db.hasil_aktif(conn))
        r = analisis.ringkasan(df)
        log.info("Total data aktif: %d unit dari %d model", r["total_hasil"], r["jumlah_model"])
        grafik, xl, pdf = _buat_output_analisis(conn, df, r, buat_laporan_flag)

    durasi = time.time() - t0
    log.info("Pipeline selesai dalam %.1f detik dengan status: %s", durasi, status_run)
    return {"status": status_run, "total_hasil": r["total_hasil"], "jumlah_model": r["jumlah_model"], "excel": xl, "pdf": pdf, "grafik": grafik, "durasi": durasi}


def main() -> None:
    p = argparse.ArgumentParser(description="Pipeline Pemantau Hasil Lelang JBA")
    p.add_argument("--maks-model", type=int, help="Batasi jumlah model yang diambil")
    p.add_argument("--tanpa-scrape", action="store_true", help="Gunakan data lokal database")
    p.add_argument("--tanpa-laporan", action="store_true", help="Lewati pembuatan laporan")
    args = p.parse_args()
    res = jalankan_pipeline(args.maks_model, args.tanpa_scrape, not args.tanpa_laporan)
    if res.get("status") in ("gagal", "dihentikan"):
        sys.exit(1)


if __name__ == "__main__":
    main()
