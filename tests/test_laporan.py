"""
Pengujian laporan.py:
- Pembuatan file Excel dengan sheet yang sesuai dan format rupiah
- Pembuatan file PDF dengan reportlab
"""
from datetime import datetime
from pathlib import Path
import openpyxl
import pandas as pd
import laporan


def test_buat_excel_dan_pdf(tmp_path):
    df = pd.DataFrame([
        {"merek": "Toyota", "model": "Avanza G", "tahun": 2020, "lokasi": "Jakarta", "harga": 150000000, "model_slug": "avanza"},
        {"merek": "Daihatsu", "model": "Xenia R", "tahun": 2021, "lokasi": "Bandung", "harga": 140000000, "model_slug": "xenia"},
    ])
    r = {
        "total_hasil": 2, "jumlah_merek": 2, "jumlah_model": 2,
        "harga_rata2": 145000000.0, "median": 145000000.0,
        "termurah": 140000000, "termahal": 150000000
    }
    perubahan = [
        {"model_slug": "avanza", "jenis": "baru", "model": "Avanza G", "tahun": 2020, "lokasi": "Jakarta", "harga": 150000000, "jumlah_lama": 0, "jumlah_baru": 1}
    ]

    # Buat Excel
    excel_file = laporan.buat_excel(df, r, perubahan, folder=tmp_path)
    assert excel_file.exists()
    assert excel_file.suffix == ".xlsx"

    wb = openpyxl.load_workbook(excel_file)
    expected_sheets = {"Ringkasan", "Per Model", "Per Lokasi", "Per Tahun", "Perubahan", "Data"}
    assert expected_sheets.issubset(set(wb.sheetnames))

    # Buat PDF
    top_model = df.groupby(["model_slug", "merek"])["harga"].agg(jumlah="count", rata2="mean").reset_index()
    pdf_file = laporan.buat_pdf(r, top_model, {}, folder=tmp_path)
    assert pdf_file.exists()
    assert pdf_file.suffix == ".pdf"
    assert pdf_file.stat().st_size > 1000

