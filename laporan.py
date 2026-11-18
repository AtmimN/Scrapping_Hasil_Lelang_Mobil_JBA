"""
Lapisan 4a: LAPORAN OTOMATIS (Excel & PDF).
"""
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import analisis
import config

WIB = ZoneInfo(config.ZONA_WAKTU)


def _format_ws(ws, kolom_uang=None):
    kolom_uang = kolom_uang or []
    fill = PatternFill(start_color="1E40AF", end_color="1E40AF", fill_type="solid")
    font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    border = Border(*(Side(style="thin", color="D1D5DB") for _ in range(4)))
    ws.freeze_panes = "A2"
    for cell in ws[1]:
        cell.fill, cell.font, cell.alignment = fill, font, Alignment(horizontal="center", vertical="center")
    for row in ws.iter_rows(min_row=2):
        for idx, cell in enumerate(row, 1):
            cell.border = border
            if idx in kolom_uang and isinstance(cell.value, (int, float)):
                cell.number_format = '"Rp"#,##0'
    for col in ws.columns:
        ws.column_dimensions[get_column_letter(col[0].column)].width = max(max(len(str(c.value or "")) for c in col) + 3, 12)


def _isi_sheet_analisis(wb, df, r, perubahan_rows):
    ws_r = wb.active
    ws_r.title = "Ringkasan"
    ws_r.append(["Metrik", "Nilai"])
    for k, v in [("Total Unit", r.get("total_hasil", 0)), ("Jumlah Merek", r.get("jumlah_merek", 0)), ("Jumlah Model", r.get("jumlah_model", 0)), ("Rata-rata Harga", r.get("harga_rata2", 0)), ("Median Harga", r.get("median", 0)), ("Harga Termurah", r.get("termurah", 0)), ("Harga Termahal", r.get("termahal", 0))]:
        ws_r.append([k, v])
    _format_ws(ws_r, [2])

    ws_m = wb.create_sheet("Per Model")
    ws_m.append(["Model Slug", "Merek", "Jumlah Unit", "Rata-rata Harga", "Harga Min", "Harga Maks"])
    for _, rw in analisis.per_model(df, 1).iterrows():
        ws_m.append([rw["model_slug"], rw["merek"], int(rw["jumlah"]), rw["rata2"], rw["min"], rw["maks"]])
    _format_ws(ws_m, [4, 5, 6])

    ws_l = wb.create_sheet("Per Lokasi")
    ws_l.append(["Lokasi Lelang", "Jumlah Unit", "Rata-rata Harga"])
    for _, rw in analisis.per_lokasi(df).iterrows():
        ws_l.append([rw["lokasi"], int(rw["jumlah"]), rw["rata2"]])
    _format_ws(ws_l, [3])

    ws_t = wb.create_sheet("Per Tahun")
    ws_t.append(["Tahun", "Jumlah Unit", "Rata-rata Harga", "Harga Min", "Harga Maks"])
    for _, rw in analisis.per_tahun(df).iterrows():
        ws_t.append([int(rw["tahun"]), int(rw["jumlah"]), rw["rata2"], rw["min"], rw["maks"]])
    _format_ws(ws_t, [3, 4, 5])


def buat_excel(df: pd.DataFrame, r: dict[str, Any], perubahan_rows: list[Any], folder: Path = config.OUTPUT_DIR) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    nama = folder / f"laporan_{datetime.now(WIB):%Y-%m-%d}.xlsx"
    wb = openpyxl.Workbook()
    _isi_sheet_analisis(wb, df, r, perubahan_rows)

    ws_p = wb.create_sheet("Perubahan")
    ws_p.append(["Model Slug", "Jenis", "Model", "Tahun", "Lokasi", "Harga", "Jumlah Lama", "Jumlah Baru"])
    for p in perubahan_rows:
        ws_p.append([p["model_slug"], p["jenis"], p["model"], p["tahun"], p["lokasi"], p["harga"], p["jumlah_lama"], p["jumlah_baru"]])
    _format_ws(ws_p, [6])

    ws_d = wb.create_sheet("Data")
    ws_d.append(["Merek", "Model", "Tahun", "Lokasi", "Harga"])
    if not df.empty:
        for _, rw in df[["merek", "model", "tahun", "lokasi", "harga"]].iterrows():
            ws_d.append([rw["merek"], rw["model"], int(rw["tahun"]), rw["lokasi"], rw["harga"]])
    _format_ws(ws_d, [5])
    wb.save(nama)
    return nama


def _buat_tabel_pdf(top_model_df: pd.DataFrame) -> Table:
    t_data = [["Model", "Merek", "Unit", "Rata-rata Harga"]]
    for _, row in top_model_df.head(10).iterrows():
        t_data.append([str(row["model_slug"]), str(row["merek"]), str(row["jumlah"]), f"Rp {int(row['rata2']):,}"])
    tbl = Table(t_data, colWidths=[150, 100, 50, 150])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E40AF")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
    ]))
    return tbl


def buat_pdf(r: dict[str, Any], top_model_df: pd.DataFrame, grafik_paths: dict[str, Path], folder: Path = config.OUTPUT_DIR) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    nama = folder / f"laporan_{datetime.now(WIB):%Y-%m-%d}.pdf"
    doc = SimpleDocTemplate(str(nama), pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    t_style = ParagraphStyle("T", parent=styles["Title"], fontSize=18, leading=22, textColor=colors.HexColor("#1E40AF"), alignment=0)
    h_style = ParagraphStyle("H", parent=styles["Heading2"], fontSize=12, leading=16, textColor=colors.HexColor("#1E40AF"))
    story = [
        Paragraph("Laporan Pemantauan Hasil Lelang JBA", t_style),
        Paragraph(f"Tanggal: {datetime.now(WIB):%d %B %Y} · Sumber: jba.co.id", styles["Normal"]),
        Spacer(1, 10),
        Paragraph(f"Total: <b>{r.get('total_hasil', 0):,} unit</b> ({r.get('jumlah_model', 0)} model). Rata-rata: <b>Rp {int(r.get('harga_rata2', 0)):,}</b>.", styles["Normal"]),
        Spacer(1, 10), Paragraph("Top 10 Model", h_style), Spacer(1, 5),
    ]
    if not top_model_df.empty:
        story.append(_buat_tabel_pdf(top_model_df))
    story += [Spacer(1, 15), Paragraph("Visualisasi", h_style), Spacer(1, 5)]
    for p in grafik_paths.values():
        if p.exists():
            story += [Image(str(p), width=480, height=270), Spacer(1, 10)]
    story += [Paragraph("Catatan: Data publik tanpa ID/tanggal per baris. Tujuan edukasi.", styles["Normal"])]
    doc.build(story)
    return nama
