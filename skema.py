SKEMA_SQL = """
CREATE TABLE IF NOT EXISTS scrape_log (
    id INTEGER PRIMARY KEY,
    mulai TEXT,
    selesai TEXT,
    status TEXT CHECK(status IN ('sukses','sebagian','gagal','dihentikan')),
    baseline INTEGER,
    model_berhasil INTEGER,
    model_gagal INTEGER,
    baris_total INTEGER,
    hasil_baru INTEGER,
    catatan TEXT
);

CREATE TABLE IF NOT EXISTS hasil_lelang (
    id INTEGER PRIMARY KEY,
    model_slug TEXT,
    merek TEXT,
    model TEXT,
    tahun INTEGER,
    lokasi TEXT,
    harga INTEGER,
    jumlah INTEGER,
    pertama_dilihat TEXT,
    terakhir_dilihat TEXT,
    run_pertama INTEGER REFERENCES scrape_log(id),
    UNIQUE(model_slug, model, tahun, lokasi, harga)
);

CREATE TABLE IF NOT EXISTS riwayat_model (
    id INTEGER PRIMARY KEY,
    run_id INTEGER REFERENCES scrape_log(id),
    model_slug TEXT,
    jumlah_baris INTEGER,
    harga_rata2 REAL,
    harga_min INTEGER,
    harga_maks INTEGER
);

CREATE TABLE IF NOT EXISTS perubahan (
    id INTEGER PRIMARY KEY,
    run_id INTEGER REFERENCES scrape_log(id),
    model_slug TEXT,
    jenis TEXT CHECK(jenis IN ('baru','tambah','kurang','hilang')),
    model TEXT,
    tahun INTEGER,
    lokasi TEXT,
    harga INTEGER,
    jumlah_lama INTEGER,
    jumlah_baru INTEGER
);

CREATE TABLE IF NOT EXISTS pelanggan (
    chat_id INTEGER PRIMARY KEY,
    sejak TEXT
);

CREATE INDEX IF NOT EXISTS idx_hasil_slug ON hasil_lelang(model_slug);
CREATE INDEX IF NOT EXISTS idx_riwayat_run ON riwayat_model(run_id);
CREATE INDEX IF NOT EXISTS idx_perubahan_run ON perubahan(run_id);
"""

