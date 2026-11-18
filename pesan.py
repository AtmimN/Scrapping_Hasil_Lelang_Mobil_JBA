"""
Format teks balasan bot dan utilitas pemformatan.
Fungsi murni tanpa dependensi telegram (mudah diuji).
"""
import html
import re
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

BANTUAN = (
    "<b>🚗 Pantau Lelang JBA Bot</b>\n\n"
    "Daftar perintah yang tersedia:\n"
    "/ringkas — Ringkasan umum hasil lelang terkini\n"
    "/model &lt;nama&gt; — Statistik satu model (contoh: /model avanza)\n"
    "/cari &lt;kata&gt; — Cari model kendaraan\n"
    "/lokasi &lt;nama&gt; — Statistik lelang di satu lokasi\n"
    "/baru — Perubahan hasil lelang pada scrape terakhir\n"
    "/grafik — Kirim grafik analisis terbaru\n"
    "/laporan — Unduh file laporan Excel &amp; PDF\n"
    "/status — Info run scrape terakhir &amp; jadwal\n"
    "/langganan — Langganan ringkasan harian terjadwal\n"
    "/berhenti — Hentikan langganan harian\n"
    "/scrape — Jalankan scraping manual (khusus pemilik)\n"
    "/help — Bantuan perintah"
)


def rupiah(nilai: Optional[float | int]) -> str:
    """Format angka integer/float ke format Rupiah standar, misal Rp 104.500.000."""
    if nilai is None:
        return "Rp 0"
    n = int(round(nilai))
    teks = f"{n:,}".replace(",", ".")
    return f"Rp {teks}"


def normalisasi_nama(teks: str) -> str:
    """Menormalisasi nama kendaraan (huruf kecil, hapus spasi dan tanda hubung)."""
    if not teks:
        return ""
    return re.sub(r"[\s\-_]+", "", teks.strip().lower())


def potong_pesan(teks: str, batas: int = 4000) -> list[str]:
    """Memotong pesan panjang agar tidak melebihi batas Telegram tanpa memotong tag HTML di tengah."""
    if len(teks) <= batas:
        return [teks]
    baris_list = teks.split("\n")
    bagian: list[str] = []
    saat_ini: list[str] = []
    panjang = 0

    for baris in baris_list:
        if panjang + len(baris) + 1 > batas:
            if saat_ini:
                bagian.append("\n".join(saat_ini))
                saat_ini = [baris]
                panjang = len(baris)
            else:
                # Baris tunggal sangat panjang
                bagian.append(baris[:batas])
                saat_ini = [baris[batas:]]
                panjang = len(saat_ini[0])
        else:
            saat_ini.append(baris)
            panjang += len(baris) + 1

    if saat_ini:
        bagian.append("\n".join(saat_ini))
    return bagian


def format_ringkasan(r: dict[str, Any]) -> str:
    """Format teks HTML untuk perintah /ringkas."""
    return (
        "<b>📊 Ringkasan Hasil Lelang JBA</b>\n\n"
        f"• Total Unit Terdata: <b>{r['total_hasil']:,}</b> unit\n"
        f"• Jumlah Merek: <b>{r['jumlah_merek']}</b> merek\n"
        f"• Jumlah Model: <b>{r['jumlah_model']}</b> model\n"
        f"• Rata-rata Harga: <b>{rupiah(r['harga_rata2'])}</b>\n"
        f"• Nilai Median: <b>{rupiah(r['median'])}</b>\n"
        f"• Harga Termurah: <b>{rupiah(r['termurah'])}</b>\n"
        f"• Harga Termahal: <b>{rupiah(r['termahal'])}</b>\n"
    )


def format_model(stat: dict[str, Any]) -> str:
    """Format teks HTML untuk perintah /model."""
    slug_esc = html.escape(stat["slug"].title())
    merek_esc = html.escape(stat["merek"])
    teks = [
        f"<b>🚘 Statistik Model: {slug_esc} ({merek_esc})</b>\n",
        f"• Total Unit: <b>{stat['total']}</b>",
        f"• Rata-rata Harga: <b>{rupiah(stat['rata2'])}</b>",
        f"• Rentang: {rupiah(stat['min'])} – {rupiah(stat['maks'])}\n",
        "<b>5 Unit Terbaru/Teratas:</b>",
    ]
    for i, u in enumerate(stat["terbaru"], 1):
        m_esc = html.escape(u["model"])
        lok_esc = html.escape(u["lokasi"])
        teks.append(f"{i}. {m_esc} ({u['tahun']}) - {rupiah(u['harga'])} [{lok_esc}]")
    return "\n".join(teks)


def format_perubahan(events: list[Any], baseline: bool = False) -> str:
    """Format teks HTML untuk perintah /baru atau notifikasi scrape harian."""
    if baseline:
        return (
            "<b>ℹ️ Data Awal (Baseline) Berhasil Dimuat</b>\n\n"
            "Seluruh data saat ini dicatat sebagai data acuan awal.\n"
            "Perubahan unit baru, penambahan, atau pengurangan akan terdeteksi pada run berikutnya."
        )
    if not events:
        return "<b>✅ Tidak Ada Perubahan</b>\n\nBelum ada perubahan data unit lelang sejak run sebelumnya."

    teks = [f"<b>📢 Perubahan Terdeteksi ({len(events)} catatan):</b>\n"]
    for e in events[:20]:
        model_esc = html.escape(e["model"])
        jenis = e["jenis"]
        if jenis == "baru":
            teks.append(f"🟢 <b>[Baru]</b> {model_esc} ({e['tahun']}) - {rupiah(e['harga'])} ({e['lokasi']})")
        elif jenis == "tambah":
            teks.append(f"🔵 <b>[Tambah +{e['jumlah_baru'] - e['jumlah_lama']}]</b> {model_esc} ({e['tahun']})")
        elif jenis == "kurang":
            teks.append(f"🟡 <b>[Kurang]</b> {model_esc} ({e['tahun']}) sisa {e['jumlah_baru']} unit")
        elif jenis == "hilang":
            teks.append(f"🔴 <b>[Selesai/Hilang]</b> {model_esc} ({e['tahun']}) - {rupiah(e['harga'])}")

    if len(events) > 20:
        teks.append(f"\n<i>...dan {len(events) - 20} perubahan lainnya.</i>")
    return "\n".join(teks)


def format_status(log_row: Optional[Any], jam_jadwal: str) -> str:
    """Format status scrape terakhir dan jam jadwal harian."""
    if not log_row:
        return f"<b>Status:</b> Belum ada catatan scrape.\nJadwal harian: Pukul {jam_jadwal} WIB."

    status_icon = "✅" if log_row["status"] == "sukses" else "⚠️"
    catatan_esc = html.escape(log_row["catatan"] or "-")
    return (
        f"<b>{status_icon} Status Scrape Terakhir</b>\n\n"
        f"• Status: <b>{log_row['status'].upper()}</b>\n"
        f"• Waktu Selesai: {log_row['selesai']}\n"
        f"• Model Berhasil: {log_row['model_berhasil']}\n"
        f"• Model Gagal: {log_row['model_gagal']}\n"
        f"• Total Baris: {log_row['baris_total']}\n"
        f"• Hasil Baru: {log_row['hasil_baru']}\n"
        f"• Catatan: <i>{catatan_esc}</i>\n\n"
        f"⏰ Jadwal Rutin Berikutnya: Pukul <b>{jam_jadwal} WIB</b> (jika bot aktif)."
    )


def _waktu_wib(iso_str: Optional[str]) -> str:
    """Konversi waktu ISO UTC ke format tanggal dan jam WIB."""
    if not iso_str:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_str).astimezone(ZoneInfo("Asia/Jakarta"))
        return dt.strftime("%d-%m-%Y %H:%M WIB")
    except Exception:
        return iso_str


def _format_daftar_perubahan(events: list[Any], batas: int = 10) -> list[str]:
    """Format daftar perubahan dipotong maksimal batas item."""
    teks = []
    for e in events[:batas]:
        model_esc = html.escape(str(e["model"]))
        jenis = e["jenis"]
        if jenis == "baru":
            teks.append(f"🟢 <b>[Baru]</b> {model_esc} ({e['tahun']}) - {rupiah(e['harga'])} ({e['lokasi']})")
        elif jenis == "tambah":
            teks.append(f"🔵 <b>[Tambah +{e['jumlah_baru'] - e['jumlah_lama']}]</b> {model_esc} ({e['tahun']})")
        elif jenis == "kurang":
            teks.append(f"🟡 <b>[Kurang]</b> {model_esc} ({e['tahun']}) sisa {e['jumlah_baru']} unit")
        elif jenis == "hilang":
            teks.append(f"🔴 <b>[Selesai/Hilang]</b> {model_esc} ({e['tahun']}) - {rupiah(e['harga'])}")
    if len(events) > batas:
        teks.append(f"<i>...dan {len(events) - batas} lainnya.</i>")
    return teks


def _format_harian_sukses(log: Any, perubahan: list[Any], kirim_tanpa_ubah: bool) -> Optional[str]:
    """Format pesan harian untuk status sukses."""
    if perubahan:
        teks = [f"<b>📢 Laporan Harian Hasil Lelang JBA</b>", f"Ditemukan {len(perubahan)} perubahan:\n"]
        teks.extend(_format_daftar_perubahan(perubahan, batas=10))
        return "\n".join(teks)
    if not kirim_tanpa_ubah:
        return None
    waktu = _waktu_wib(log["selesai"] if log else None)
    total_model = log["model_berhasil"] if log else 0
    total_baris = log["baris_total"] if log else 0
    return (
        "<b>ℹ️ Laporan Harian Hasil Lelang JBA</b>\n\n"
        f"• Waktu selesai: {waktu}\n"
        f"• Model dicek: {total_model}\n"
        f"• Total baris: {total_baris}\n\n"
        "Tidak ada hasil lelang baru atau perubahan."
    )


def _format_harian_sebagian(log: Any, perubahan: list[Any]) -> str:
    """Format pesan harian untuk status sebagian."""
    teks = [
        f"<b>⚠️ Laporan Harian Sebagian ({log['model_gagal']} model gagal)</b>",
        f"• Model berhasil: {log['model_berhasil']}",
        f"• Total baris: {log['baris_total']}\n"
    ]
    if perubahan:
        teks.append(f"Daftar perubahan ({len(perubahan)}):")
        teks.extend(_format_daftar_perubahan(perubahan, batas=10))
    else:
        teks.append("Tidak ada hasil lelang baru atau perubahan pada model yang berhasil.")
    return "\n".join(teks)


def _format_harian_gagal(status: str, log: Any, tgl_terakhir: Optional[str]) -> str:
    """Format pesan harian untuk status gagal atau dihentikan."""
    tgl = _waktu_wib(tgl_terakhir or (log["selesai"] if log else None))
    return (
        f"<b>⚠️ Scraping Hari Ini {status.upper()}</b>\n\n"
        "Maaf, proses pembaruan data lelang hari ini gagal dijalankan.\n"
        f"Tanggal data terakhir yang valid: <b>{tgl}</b>."
    )


def format_harian(
    log: Optional[Any],
    perubahan: list[Any],
    jam_jadwal: str,
    kirim_jika_tanpa_perubahan: bool = True,
    tanggal_data_terakhir: Optional[str] = None
) -> Optional[str]:
    """Format pesan harian ke pelanggan berdasarkan status run."""
    if not log:
        return None
    if log["baseline"]:
        return (
            "<b>ℹ️ Data Awal (Baseline) Berhasil Dimuat</b>\n\n"
            "Seluruh data saat ini dicatat sebagai data acuan awal, bukan perubahan.\n"
            f"• Model tersimpan: <b>{log['model_berhasil']}</b>\n"
            f"• Baris tersimpan: <b>{log['baris_total']}</b> unit\n"
            f"Laporan rutin akan dikirim setiap hari pukul {jam_jadwal} WIB."
        )
    status = log["status"]
    if status == "sukses":
        return _format_harian_sukses(log, perubahan, kirim_jika_tanpa_perubahan)
    if status == "sebagian":
        return _format_harian_sebagian(log, perubahan)
    if status in ("gagal", "dihentikan"):
        return _format_harian_gagal(status, log, tanggal_data_terakhir)
    return None

