"""
Lapisan 4b: BOT TELEGRAM (Asisten Pantau Lelang JBA).

Menyajikan antarmuka perintah pengguna dan penjadwalan harian otomatis
dengan JobQueue dan catch-up start.
"""
import asyncio
import datetime
import html
import logging
from typing import Any, Optional
from zoneinfo import ZoneInfo

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import analisis
import config
import db
from main import jalankan_pipeline
import pesan

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s: %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("bot")

WIB = ZoneInfo(config.ZONA_WAKTU)


# ---------- Handlers Perintah ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    nama = update.effective_user.first_name if update.effective_user else "Pengguna"
    pesan_teks = f"Halo <b>{html.escape(nama)}</b>!\nSelamat datang di Bot Pantau Hasil Lelang JBA.\n\n" + pesan.BANTUAN
    await update.message.reply_html(pesan_teks)


async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(pesan.BANTUAN)


async def ringkas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with db.buka(config.DB_PATH, hanya_baca=True) as conn:
        rows = db.hasil_aktif(conn)
    df = analisis.ke_dataframe(rows)
    r = analisis.ringkasan(df)
    if r["total_hasil"] == 0:
        await update.message.reply_text("Database masih kosong. Harap jalankan pipeline terlebih dahulu.")
        return
    await update.message.reply_html(pesan.format_ringkasan(r))


async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Contoh: /model avanza")
        return
    nama_cari = pesan.normalisasi_nama(" ".join(context.args))
    with db.buka(config.DB_PATH, hanya_baca=True) as conn:
        stat = db.statistik_model(conn, nama_cari)
        if not stat:
            cocok = db.cari_model(conn, nama_cari, batas=1)
            if cocok:
                stat = db.statistik_model(conn, cocok[0]["model_slug"])

    if not stat:
        await update.message.reply_text(f"Model '{' '.join(context.args)}' tidak ditemukan.")
        return
    await update.message.reply_html(pesan.format_model(stat))


async def cari(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Contoh: /cari xenia")
        return
    kata = " ".join(context.args)
    with db.buka(config.DB_PATH, hanya_baca=True) as conn:
        hasil = db.cari_model(conn, kata, batas=10)
    if not hasil:
        await update.message.reply_text(f"Tidak ada model yang cocok dengan kata '{kata}'.")
        return

    teks = [f"<b>Hasil pencarian '{html.escape(kata)}':</b>\n"]
    for i, h in enumerate(hasil, 1):
        teks.append(f"{i}. <b>{html.escape(h['model'])}</b> (slug: <code>{html.escape(h['model_slug'])}</code>)")
    await update.message.reply_html("\n".join(teks))


async def lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Contoh: /lokasi jakarta")
        return
    nama_lok = " ".join(context.args)
    with db.buka(config.DB_PATH, hanya_baca=True) as conn:
        stat = db.statistik_lokasi(conn, nama_lok)
    if not stat:
        await update.message.reply_text(f"Tidak ada data untuk lokasi '{nama_lok}'.")
        return

    teks = (
        f"<b>📍 Lokasi: {html.escape(stat['lokasi'])}</b>\n\n"
        f"• Total Unit: <b>{stat['total']:,}</b>\n"
        f"• Rata-rata Harga: <b>{pesan.rupiah(stat['rata2'])}</b>\n"
        f"• Rentang: {pesan.rupiah(stat['min'])} – {pesan.rupiah(stat['maks'])}"
    )
    await update.message.reply_html(teks)


async def baru(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with db.buka(config.DB_PATH, hanya_baca=True) as conn:
        log_row = db.log_terakhir(conn)
        events = db.perubahan_run(conn)
    is_base = bool(log_row and log_row["baseline"])
    teks = pesan.format_perubahan(events, baseline=is_base)
    for bagian in pesan.potong_pesan(teks):
        await update.message.reply_html(bagian)


async def grafik(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    folder = config.OUTPUT_DIR / "grafik"
    paths = [folder / "top_model.png", folder / "per_lokasi.png", folder / "per_tahun.png"]
    ada = [p for p in paths if p.exists()]
    if not ada:
        await update.message.reply_text("Grafik belum tersedia. Jalankan pipeline terlebih dahulu.")
        return
    for p in ada:
        with open(p, "rb") as f:
            await update.message.reply_photo(photo=f, caption=p.stem.replace("_", " ").title())


async def laporan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tgl_str = datetime.datetime.now(WIB).strftime("%Y-%m-%d")
    xlsx = config.OUTPUT_DIR / f"laporan_{tgl_str}.xlsx"
    pdf = config.OUTPUT_DIR / f"laporan_{tgl_str}.pdf"
    if not (xlsx.exists() and pdf.exists()):
        await update.message.reply_text("File laporan hari ini belum ada. Tunggu jadwal atau jalankan scrape.")
        return
    with open(xlsx, "rb") as f:
        await update.message.reply_document(document=f, filename=xlsx.name)
    with open(pdf, "rb") as f:
        await update.message.reply_document(document=f, filename=pdf.name)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with db.buka(config.DB_PATH, hanya_baca=True) as conn:
        log_row = db.log_terakhir(conn)
    await update.message.reply_html(pesan.format_status(log_row, config.JAM_JADWAL))


async def langganan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    with db.buka(config.DB_PATH) as conn:
        db.tambah_pelanggan(conn, chat_id)
    await update.message.reply_html(
        f"✅ <b>Berhasil berlangganan!</b>\nLaporan harian otomatis dikirim setiap pukul {config.JAM_JADWAL} WIB."
    )


async def berhenti(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    with db.buka(config.DB_PATH) as conn:
        db.hapus_pelanggan(conn, chat_id)
    await update.message.reply_html("Berhasil berhenti langganan notifikasi harian.")


async def scrape_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    if not config.OWNER_CHAT_ID or chat_id != config.OWNER_CHAT_ID:
        await update.message.reply_text("⛔ Perintah ini khusus untuk pemilik bot.")
        return

    lock: asyncio.Lock = context.bot_data.setdefault("scrape_lock", asyncio.Lock())
    if lock.locked():
        await update.message.reply_text("Scraping sedang berjalan di latar belakang.")
        return

    await update.message.reply_text("🚀 Memulai scraping manual...")
    async with lock:
        hasil = await asyncio.to_thread(jalankan_pipeline)
    await update.message.reply_text(f"Selesai! Status: {hasil.get('status')} ({hasil.get('total_hasil', 0)} unit)")


# ---------- Penjadwalan Rutin Harian ----------
async def _kirim_ke_pelanggan(context: ContextTypes.DEFAULT_TYPE, teks: str, pelanggan_list: list[int]) -> None:
    """Mengirim pesan terpotong ke seluruh pelanggan terdaftar."""
    for cid in pelanggan_list:
        try:
            for bagian in pesan.potong_pesan(teks):
                await context.bot.send_message(chat_id=cid, text=bagian, parse_mode="HTML")
        except Exception as e:
            log.warning("Gagal kirim ke pelanggan %d: %s", cid, e)


def _muat_data_harian() -> tuple[Optional[Any], list[Any], list[int], Optional[str]]:
    """Membaca log terakhir, perubahan, pelanggan, dan stempel run sukses terakhir."""
    with db.buka(config.DB_PATH, hanya_baca=True) as conn:
        log_row = db.log_terakhir(conn)
        events = db.perubahan_run(conn)
        pelanggan = db.daftar_pelanggan(conn)
        last_valid = conn.execute(
            "SELECT selesai FROM scrape_log WHERE status IN ('sukses', 'sebagian') ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return log_row, events, pelanggan, (last_valid["selesai"] if last_valid else None)


async def _notifikasi_pemilik(context: ContextTypes.DEFAULT_TYPE, log_row: Optional[Any], err: Optional[Exception] = None) -> None:
    """Kirim detail log error/kegagalan ke pemilik bot."""
    if not config.OWNER_CHAT_ID:
        return
    teks = f"⚠️ Terjadi error saat job harian:\n{err}" if err else f"⚠️ <b>Laporan Masalah Scrape</b>\nStatus: {log_row['status']}\nCatatan: {html.escape(log_row['catatan'] or '-')}"
    try:
        await context.bot.send_message(chat_id=int(config.OWNER_CHAT_ID), text=teks, parse_mode="HTML" if not err else None)
    except Exception:
        pass


async def job_harian(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tugas harian otomatis: jalankan pipeline lalu kirim laporan ke pelanggan."""
    lock: asyncio.Lock = context.bot_data.setdefault("scrape_lock", asyncio.Lock())
    if lock.locked():
        log.warning("Job harian dilewati: scrape lain sedang berjalan.")
        return
    log.info("Memulai job harian otomatis...")
    try:
        async with lock:
            await asyncio.to_thread(jalankan_pipeline)
        log_row, events, pelanggan, tgl_valid = _muat_data_harian()
        teks = pesan.format_harian(log_row, events, config.JAM_JADWAL, config.KIRIM_JIKA_TIDAK_ADA_PERUBAHAN, tgl_valid)
        if teks:
            await _kirim_ke_pelanggan(context, teks, pelanggan)
        if log_row and log_row["status"] in ("gagal", "dihentikan"):
            await _notifikasi_pemilik(context, log_row)
    except Exception as e:
        log.exception("Error pada job harian: %s", e)
        await _notifikasi_pemilik(context, None, err=e)


async def job_catch_up(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cek apakah laptop mati saat jadwal dan perlu catch-up."""
    with db.buka(config.DB_PATH, hanya_baca=True) as conn:
        log_row = db.log_terakhir(conn)

    butuh_catchup = True
    if log_row and log_row["selesai"]:
        try:
            waktu_selesai = datetime.datetime.fromisoformat(log_row["selesai"])
            selisih = datetime.datetime.now(datetime.timezone.utc) - waktu_selesai
            if selisih.total_seconds() < 24 * 3600:
                butuh_catchup = False
        except Exception:
            pass

    if butuh_catchup:
        log.info("Catch-up diperlukan (belum scrape dalam 24 jam terakhir).")
        await job_harian(context)


async def pasca_inisialisasi(app: Application) -> None:
    """Set tombol menu perintah Telegram dan jadwalkan tugas harian."""
    await app.bot.set_my_commands([
        BotCommand("ringkas", "Ringkasan hasil lelang"),
        BotCommand("model", "Statistik satu model"),
        BotCommand("cari", "Cari model mobil"),
        BotCommand("lokasi", "Statistik per lokasi"),
        BotCommand("baru", "Perubahan hasil lelang"),
        BotCommand("grafik", "Grafik analisis"),
        BotCommand("laporan", "Unduh Excel dan PDF"),
        BotCommand("status", "Status scrape terakhir"),
        BotCommand("langganan", "Langganan harian"),
        BotCommand("berhenti", "Hentikan langganan"),
        BotCommand("help", "Bantuan perintah"),
    ])

    jam, menit = map(int, config.JAM_JADWAL.split(":"))
    jadwal_waktu = datetime.time(hour=jam, minute=menit, tzinfo=WIB)
    app.job_queue.run_daily(job_harian, time=jadwal_waktu, name="harian_jba")
    # Jadwalkan catch-up 30 detik setelah start
    app.job_queue.run_once(job_catch_up, when=30, name="catch_up_jba")
    log.info("Job harian terjadwal pukul %s WIB", config.JAM_JADWAL)


async def tangani_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler error global bot."""
    log.error("Terjadi error tak terduga: %s", context.error, exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("Maaf, terjadi kesalahan saat memproses permintaan.")


def bangun_aplikasi(token: str) -> Application:
    """Membangun objek Telegram Application dengan seluruh handler."""
    app = Application.builder().token(token).post_init(pasca_inisialisasi).build()

    daftar_handler = [
        ("start", start),
        ("help", bantuan),
        ("ringkas", ringkas),
        ("model", model_cmd),
        ("cari", cari),
        ("lokasi", lokasi),
        ("baru", baru),
        ("grafik", grafik),
        ("laporan", laporan_cmd),
        ("status", status),
        ("langganan", langganan),
        ("berhenti", berhenti),
        ("scrape", scrape_manual),
    ]
    for cmd, fn in daftar_handler:
        app.add_handler(CommandHandler(cmd, fn))

    app.add_error_handler(tangani_error)
    return app


def main() -> None:
    """Titik masuk bot Telegram."""
    config.validasi_untuk_bot()
    app = bangun_aplikasi(config.BOT_TOKEN)
    log.info("Bot Pantau Lelang JBA aktif. Tekan Ctrl+C untuk berhenti.")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()

