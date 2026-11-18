"""
Lapisan 2: PENYIMPANAN DATA (SQLite).
"""
import sqlite3
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

import config
from scraper import HasilScrape
from skema import SKEMA_SQL


def waktu_utc_sekarang() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def buka(path: Path = config.DB_PATH, hanya_baca: bool = False) -> Generator[sqlite3.Connection, None, None]:
    path = Path(path)
    if hanya_baca:
        conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def buat_skema(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript(SKEMA_SQL)


def _cek_baseline(conn: sqlite3.Connection) -> bool:
    cur = conn.execute("SELECT COUNT(*) FROM scrape_log WHERE status IN ('sukses', 'sebagian')")
    return cur.fetchone()[0] == 0


def _hitung_statistik_slug(daftar_baris: list[Any]) -> tuple[int, float, int, int]:
    if not daftar_baris:
        return 0, 0.0, 0, 0
    total = len(daftar_baris)
    h_list = [b.harga for b in daftar_baris]
    return total, sum(h_list) / total, min(h_list), max(h_list)


def _cek_anomali_slug(conn: sqlite3.Connection, slug: str, n_sekarang: int) -> bool:
    """True jika terdeteksi anomali (jumlah baris anjlok drastis)."""
    prev = conn.execute(
        "SELECT jumlah_baris FROM riwayat_model WHERE model_slug = ? ORDER BY id DESC LIMIT 1", (slug,)
    ).fetchone()
    return bool(prev and prev["jumlah_baris"] > 0 and n_sekarang < config.AMBANG_ANOMALI * prev["jumlah_baris"])


def _update_atau_insert_baris(conn: sqlite3.Connection, slug: str, counter: Counter, ada_db: dict, baseline: int, selesai: str, run_id: int) -> int:
    event_baru = 0
    for (merek, model, tahun, lokasi, harga), c_baru in counter.items():
        kunci = (model, tahun, lokasi, harga)
        if kunci not in ada_db:
            conn.execute(
                """INSERT INTO hasil_lelang (model_slug, merek, model, tahun, lokasi, harga, jumlah, pertama_dilihat, terakhir_dilihat, run_pertama)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (slug, merek, model, tahun, lokasi, harga, c_baru, selesai, selesai, run_id),
            )
            if not baseline:
                conn.execute(
                    """INSERT INTO perubahan (run_id, model_slug, jenis, model, tahun, lokasi, harga, jumlah_lama, jumlah_baru)
                       VALUES (?, ?, 'baru', ?, ?, ?, ?, 0, ?)""",
                    (run_id, slug, model, tahun, lokasi, harga, c_baru),
                )
                event_baru += 1
        else:
            b_db = ada_db[kunci]
            c_lama = b_db["jumlah"]
            conn.execute("UPDATE hasil_lelang SET jumlah = ?, terakhir_dilihat = ? WHERE id = ?", (c_baru, selesai, b_db["id"]))
            if not baseline and c_baru != c_lama:
                jenis = "tambah" if c_baru > c_lama else "kurang"
                conn.execute(
                    """INSERT INTO perubahan (run_id, model_slug, jenis, model, tahun, lokasi, harga, jumlah_lama, jumlah_baru)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (run_id, slug, jenis, model, tahun, lokasi, harga, c_lama, c_baru),
                )
    return event_baru


def _deteksi_baris_hilang(conn: sqlite3.Connection, slug: str, counter: Counter, ada_db: dict, baseline: int, run_id: int) -> None:
    for (model, tahun, lokasi, harga), b_db in ada_db.items():
        if (b_db["merek"], model, tahun, lokasi, harga) not in counter and b_db["jumlah"] > 0:
            conn.execute("UPDATE hasil_lelang SET jumlah = 0 WHERE id = ?", (b_db["id"],))
            if not baseline:
                conn.execute(
                    """INSERT INTO perubahan (run_id, model_slug, jenis, model, tahun, lokasi, harga, jumlah_lama, jumlah_baru)
                       VALUES (?, ?, 'hilang', ?, ?, ?, ?, ?, 0)""",
                    (run_id, slug, model, tahun, lokasi, harga, b_db["jumlah"]),
                )


def _proses_slug(conn: sqlite3.Connection, slug: str, daftar: list[Any], baseline: int, selesai: str, run_id: int) -> int:
    counter = Counter((b.merek, b.model, b.tahun, b.lokasi, b.harga) for b in daftar)
    ada_db = {(r["model"], r["tahun"], r["lokasi"], r["harga"]): r for r in conn.execute("SELECT * FROM hasil_lelang WHERE model_slug = ?", (slug,)).fetchall()}
    event_baru = _update_atau_insert_baris(conn, slug, counter, ada_db, baseline, selesai, run_id)
    _deteksi_baris_hilang(conn, slug, counter, ada_db, baseline, run_id)
    jml, rata, mn, mx = _hitung_statistik_slug(daftar)
    conn.execute(
        """INSERT INTO riwayat_model (run_id, model_slug, jumlah_baris, harga_rata2, harga_min, harga_maks)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (run_id, slug, jml, rata, mn, mx),
    )
    return event_baru


def simpan_run(conn: sqlite3.Connection, hasil: HasilScrape, mulai: str, selesai: Optional[str] = None) -> int:
    selesai = selesai or waktu_utc_sekarang()
    buat_skema(conn)
    with conn:
        baseline = 1 if (hasil.berhasil and _cek_baseline(conn)) else 0
        catatan, m_berhasil, m_gagal = [], 0, len(hasil.gagal)
        cur = conn.execute(
            """INSERT INTO scrape_log (mulai, selesai, status, baseline, model_berhasil, model_gagal, baris_total, hasil_baru, catatan)
               VALUES (?, ?, 'gagal', ?, 0, ?, ?, 0, '')""",
            (mulai, selesai, baseline, m_gagal, sum(len(b) for b in hasil.berhasil.values())),
        )
        run_id = cur.lastrowid
        tot_baru = 0
        for slug, daftar in hasil.berhasil.items():
            if _cek_anomali_slug(conn, slug, len(daftar)):
                catatan.append(f"Anomali {slug}: penurunan drastis")
                m_gagal += 1
                continue
            m_berhasil += 1
            tot_baru += _proses_slug(conn, slug, daftar, baseline, selesai, run_id)

        st = "dihentikan" if hasil.dihentikan else ("gagal" if m_berhasil == 0 and len(hasil.berhasil) + len(hasil.gagal) > 0 else ("sebagian" if m_gagal > 0 else "sukses"))
        if hasil.gagal:
            catatan.append("Gagal: " + ", ".join(f"{s} ({r})" for s, r in hasil.gagal.items()))
        conn.execute(
            """UPDATE scrape_log SET status = ?, model_berhasil = ?, model_gagal = ?, hasil_baru = ?, catatan = ? WHERE id = ?""",
            (st, m_berhasil, m_gagal, tot_baru, "; ".join(catatan), run_id),
        )
    return run_id


def hasil_aktif(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM hasil_lelang WHERE jumlah > 0 ORDER BY model, tahun DESC").fetchall()


def daftar_model(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT DISTINCT model_slug FROM hasil_lelang WHERE jumlah > 0 ORDER BY model_slug").fetchall()
    return [r[0] for r in rows]


def cari_model(conn: sqlite3.Connection, kata: str, batas: int = 10) -> list[sqlite3.Row]:
    pola = f"%{kata}%"
    return conn.execute(
        """SELECT DISTINCT model_slug, merek, model FROM hasil_lelang WHERE (model LIKE ? OR model_slug LIKE ?) AND jumlah > 0 LIMIT ?""",
        (pola, pola, batas),
    ).fetchall()


def statistik_model(conn: sqlite3.Connection, slug: str) -> Optional[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM hasil_lelang WHERE model_slug = ? AND jumlah > 0", (slug,)).fetchall()
    if not rows:
        return None
    semua_harga = [r["harga"] for r in rows for _ in range(r["jumlah"])]
    top5 = conn.execute(
        "SELECT * FROM hasil_lelang WHERE model_slug = ? AND jumlah > 0 ORDER BY tahun DESC, harga ASC LIMIT 5", (slug,)
    ).fetchall()
    return {
        "slug": slug, "merek": rows[0]["merek"], "total": len(semua_harga),
        "rata2": sum(semua_harga) / len(semua_harga), "min": min(semua_harga), "maks": max(semua_harga),
        "terbaru": top5,
    }


def statistik_lokasi(conn: sqlite3.Connection, lokasi: str) -> Optional[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM hasil_lelang WHERE lokasi LIKE ? AND jumlah > 0", (f"%{lokasi}%",)).fetchall()
    if not rows:
        return None
    semua_harga = [r["harga"] for r in rows for _ in range(r["jumlah"])]
    return {
        "lokasi": rows[0]["lokasi"], "total": len(semua_harga),
        "rata2": sum(semua_harga) / len(semua_harga), "min": min(semua_harga), "maks": max(semua_harga),
    }


def perubahan_run(conn: sqlite3.Connection, run_id: Optional[int] = None) -> list[sqlite3.Row]:
    if run_id is None:
        last = conn.execute("SELECT id FROM scrape_log WHERE baseline = 0 ORDER BY id DESC LIMIT 1").fetchone()
        if not last:
            return []
        run_id = last["id"]
    return conn.execute("SELECT * FROM perubahan WHERE run_id = ? ORDER BY jenis, model_slug", (run_id,)).fetchall()


def log_terakhir(conn: sqlite3.Connection) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM scrape_log ORDER BY id DESC LIMIT 1").fetchone()


def riwayat_model_slug(conn: sqlite3.Connection, slug: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT r.*, s.selesai as waktu FROM riwayat_model r JOIN scrape_log s ON s.id = r.run_id WHERE r.model_slug = ? ORDER BY r.id ASC""",
        (slug,),
    ).fetchall()


def tambah_pelanggan(conn: sqlite3.Connection, chat_id: int) -> bool:
    with conn:
        return conn.execute("INSERT OR IGNORE INTO pelanggan (chat_id, sejak) VALUES (?, ?)", (chat_id, waktu_utc_sekarang())).rowcount > 0


def hapus_pelanggan(conn: sqlite3.Connection, chat_id: int) -> bool:
    with conn:
        return conn.execute("DELETE FROM pelanggan WHERE chat_id = ?", (chat_id,)).rowcount > 0


def daftar_pelanggan(conn: sqlite3.Connection) -> list[int]:
    return [r[0] for r in conn.execute("SELECT chat_id FROM pelanggan").fetchall()]
