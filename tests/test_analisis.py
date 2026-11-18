"""
Pengujian analisis.py:
- ke_dataframe memperluas menurut jumlah
- ringkasan, per_model (MIN_SAMPEL), per_lokasi, per_tahun
- tren_run dengan satu run tidak menghasilkan grafik
- buat_grafik_semua menghasilkan file PNG
"""
import pandas as pd
import pytest
import analisis


@pytest.fixture
def data_dummy():
    return [
        {"id": 1, "model_slug": "avanza", "merek": "Toyota", "model": "Avanza G", "tahun": 2020, "lokasi": "Jakarta", "harga": 150000000, "jumlah": 2},
        {"id": 2, "model_slug": "avanza", "merek": "Toyota", "model": "Avanza E", "tahun": 2019, "lokasi": "Bandung", "harga": 130000000, "jumlah": 1},
        {"id": 3, "model_slug": "xenia", "merek": "Daihatsu", "model": "Xenia R", "tahun": 2021, "lokasi": "Jakarta", "harga": 140000000, "jumlah": 1},
    ]


def test_ke_dataframe_dan_ringkasan(data_dummy):
    df = analisis.ke_dataframe(data_dummy)
    # Total baris setelah perluas jumlah=2 pada id=1 adalah 4
    assert len(df) == 4

    r = analisis.ringkasan(df)
    assert r["total_hasil"] == 4
    assert r["jumlah_merek"] == 2
    assert r["jumlah_model"] == 2
    assert r["termurah"] == 130000000
    assert r["termahal"] == 150000000


def test_per_model_dan_lokasi(data_dummy):
    df = analisis.ke_dataframe(data_dummy)
    pm = analisis.per_model(df, min_sampel=1)
    assert len(pm) == 2
    assert pm.iloc[0]["model_slug"] == "avanza"

    pl = analisis.per_lokasi(df)
    assert len(pl) == 2
    assert pl.iloc[0]["lokasi"] == "Jakarta"
    assert pl.iloc[0]["jumlah"] == 3


def test_per_tahun(data_dummy):
    df = analisis.ke_dataframe(data_dummy)
    pt = analisis.per_tahun(df)
    assert len(pt) == 3
    assert set(pt["tahun"]) == {2019, 2020, 2021}


def test_tren_run_dan_grafik(data_dummy, tmp_path):
    df = analisis.ke_dataframe(data_dummy)
    # Satu run saja
    riwayat_df = pd.DataFrame([{"run_id": 1, "jumlah_baris": 4, "harga_rata2": 142500000}])
    paths = analisis.buat_grafik_semua(df, riwayat_df=riwayat_df, folder=tmp_path)

    assert "top_model" in paths and paths["top_model"].exists()
    assert "per_lokasi" in paths and paths["per_lokasi"].exists()
    assert "per_tahun" in paths and paths["per_tahun"].exists()
    # tren_run tidak dibuat bila hanya 1 run
    assert "tren_run" not in paths

    # Bila ada 2 run
    riwayat_2 = pd.DataFrame([
        {"run_id": 1, "jumlah_baris": 4, "harga_rata2": 142500000},
        {"run_id": 2, "jumlah_baris": 5, "harga_rata2": 145000000},
    ])
    paths2 = analisis.buat_grafik_semua(df, riwayat_df=riwayat_2, folder=tmp_path)
    assert "tren_run" in paths2 and paths2["tren_run"].exists()

