"""
Pengujian pesan.py:
- rupiah
- normalisasi_nama
- potong_pesan
- format_ringkasan & format_perubahan (baseline vs non-baseline)
"""
import pesan


def test_rupiah():
    assert pesan.rupiah(104500000) == "Rp 104.500.000"
    assert pesan.rupiah(0) == "Rp 0"
    assert pesan.rupiah(None) == "Rp 0"


def test_normalisasi_nama():
    assert pesan.normalisasi_nama("X-Trail") == "xtrail"
    assert pesan.normalisasi_nama(" x_trail ") == "xtrail"
    assert pesan.normalisasi_nama("Avanza Veloz") == "avanzaveloz"


def test_potong_pesan():
    teks_pendek = "Halo Dunia"
    assert pesan.potong_pesan(teks_pendek, batas=50) == [teks_pendek]

    teks_panjang = "\n".join([f"Baris ke-{i}" for i in range(100)])
    potongan = pesan.potong_pesan(teks_panjang, batas=200)
    assert len(potongan) > 1
    for p in potongan:
        assert len(p) <= 250


def test_format_perubahan():
    # Baseline
    teks_base = pesan.format_perubahan([], baseline=True)
    assert "Data Awal (Baseline)" in teks_base

    # Kosong
    teks_kosong = pesan.format_perubahan([], baseline=False)
    assert "Tidak Ada Perubahan" in teks_kosong

    # Ada event
    events = [
        {"model": "Avanza G", "tahun": 2022, "harga": 160000000, "lokasi": "Jakarta", "jenis": "baru", "jumlah_lama": 0, "jumlah_baru": 1},
        {"model": "Xenia R", "tahun": 2020, "harga": 140000000, "lokasi": "Bandung", "jenis": "hilang", "jumlah_lama": 1, "jumlah_baru": 0},
    ]
    teks_ev = pesan.format_perubahan(events, baseline=False)
    assert "[Baru]" in teks_ev
    assert "[Selesai/Hilang]" in teks_ev


def test_format_harian():
    # 1. Sukses tanpa perubahan dengan True -> menghasilkan pesan
    log_sukses_nol = {
        "status": "sukses",
        "baseline": 0,
        "model_berhasil": 10,
        "model_gagal": 0,
        "baris_total": 450,
        "selesai": "2026-11-15T07:05:00+00:00",
    }
    msg_true = pesan.format_harian(log_sukses_nol, [], "07:00", kirim_jika_tanpa_perubahan=True)
    assert msg_true is not None
    assert "Tidak ada hasil lelang baru atau perubahan" in msg_true
    assert "WIB" in msg_true
    assert "450" in msg_true

    # 2. Sukses tanpa perubahan dengan False -> mengembalikan None
    msg_false = pesan.format_harian(log_sukses_nol, [], "07:00", kirim_jika_tanpa_perubahan=False)
    assert msg_false is None

    # 3. Baseline menghasilkan pesan data awal
    log_base = {
        "status": "sukses",
        "baseline": 1,
        "model_berhasil": 5,
        "model_gagal": 0,
        "baris_total": 200,
        "selesai": "2026-11-15T07:05:00+00:00",
    }
    msg_base = pesan.format_harian(log_base, [], "07:00", kirim_jika_tanpa_perubahan=False)
    assert msg_base is not None
    assert "Data Awal (Baseline)" in msg_base
    assert "200" in msg_base
    assert "5" in msg_base

    # 4. Status sebagian tetap menghasilkan pesan walau False
    log_sebagian = {
        "status": "sebagian",
        "baseline": 0,
        "model_berhasil": 4,
        "model_gagal": 1,
        "baris_total": 150,
        "selesai": "2026-11-15T07:05:00+00:00",
    }
    msg_seb = pesan.format_harian(log_sebagian, [], "07:00", kirim_jika_tanpa_perubahan=False)
    assert msg_seb is not None
    assert "1 model gagal" in msg_seb

    # 5. Status gagal dan dihentikan selalu menghasilkan pesan
    log_gagal = {
        "status": "gagal",
        "baseline": 0,
        "model_berhasil": 0,
        "model_gagal": 5,
        "baris_total": 0,
        "selesai": "2026-11-15T07:05:00+00:00",
    }
    msg_gagal = pesan.format_harian(log_gagal, [], "07:00", kirim_jika_tanpa_perubahan=False, tanggal_data_terakhir="2026-11-14T07:00:00+00:00")
    assert msg_gagal is not None
    assert "GAGAL" in msg_gagal
    assert "Tanggal data terakhir yang valid" in msg_gagal

    log_stop = {
        "status": "dihentikan",
        "baseline": 0,
        "model_berhasil": 1,
        "model_gagal": 1,
        "baris_total": 50,
        "selesai": "2026-11-15T07:05:00+00:00",
    }
    msg_stop = pesan.format_harian(log_stop, [], "07:00", kirim_jika_tanpa_perubahan=False)
    assert msg_stop is not None
    assert "DIHENTIKAN" in msg_stop

    # 6. Lebih dari 10 perubahan dipotong menjadi 10 baris ditambah "dan N lainnya"
    banyak_perubahan = [
        {"model": f"Model {i}", "tahun": 2020 + (i % 3), "harga": 100000000 + i * 1000000, "lokasi": "Jakarta", "jenis": "baru", "jumlah_lama": 0, "jumlah_baru": 1}
        for i in range(15)
    ]
    msg_banyak = pesan.format_harian(log_sukses_nol, banyak_perubahan, "07:00")
    assert msg_banyak is not None
    assert "Model 0" in msg_banyak
    assert "Model 9" in msg_banyak
    assert "Model 10" not in msg_banyak
    assert "dan 5 lainnya" in msg_banyak


