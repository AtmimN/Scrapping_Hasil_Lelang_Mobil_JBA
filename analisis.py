"""
Lapisan 3: ANALISIS DAN VISUALISASI.
"""
from pathlib import Path
from typing import Any, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import config

WARNA_UTAMA = "#1E40AF"


def ke_dataframe(rows: list[Any]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["id", "model_slug", "merek", "model", "tahun", "lokasi", "harga", "jumlah"])
    df = pd.DataFrame([dict(r) for r in rows])
    if not df.empty and "jumlah" in df.columns:
        df = df.loc[df.index.repeat(df["jumlah"])].reset_index(drop=True)
    return df


def ringkasan(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"total_hasil": 0, "jumlah_merek": 0, "jumlah_model": 0, "harga_rata2": 0.0, "median": 0.0, "termurah": 0, "termahal": 0}
    return {
        "total_hasil": len(df), "jumlah_merek": df["merek"].nunique(), "jumlah_model": df["model_slug"].nunique(),
        "harga_rata2": round(float(df["harga"].mean()), 2), "median": round(float(df["harga"].median()), 2),
        "termurah": int(df["harga"].min()), "termahal": int(df["harga"].max()),
    }


def per_model(df: pd.DataFrame, min_sampel: int = config.MIN_SAMPEL) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["model_slug", "merek", "jumlah", "rata2", "min", "maks"])
    g = df.groupby(["model_slug", "merek"])["harga"].agg(jumlah="count", rata2="mean", min="min", maks="max").reset_index()
    if min_sampel > 1:
        g = g[g["jumlah"] >= min_sampel]
    return g.sort_values("rata2", ascending=False).reset_index(drop=True)


def per_lokasi(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["lokasi", "jumlah", "rata2"])
    return df.groupby("lokasi")["harga"].agg(jumlah="count", rata2="mean").sort_values("jumlah", ascending=False).reset_index()


def per_tahun(df: pd.DataFrame, model_slug: Optional[str] = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["tahun", "jumlah", "rata2", "min", "maks"])
    data = df[df["model_slug"] == model_slug] if model_slug else df
    return data.groupby("tahun")["harga"].agg(jumlah="count", rata2="mean", min="min", maks="max").sort_values("tahun").reset_index()


def tren_run(riwayat_df: pd.DataFrame) -> pd.DataFrame:
    if riwayat_df.empty:
        return pd.DataFrame(columns=["run_id", "total_unit", "rata2"])
    return riwayat_df.groupby("run_id").agg(total_unit=("jumlah_baris", "sum"), rata2=("harga_rata2", "mean")).reset_index()


def _plot_bar_horizontal(labels, values, judul, xlabel, path, color=WARNA_UTAMA):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(labels, values, color=color)
    ax.invert_yaxis()
    ax.set_title(judul, loc="left", fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _plot_garis(x, y, judul, xlabel, ylabel, path, color="#E11D48"):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(x, y, marker="o", color=color, linewidth=2)
    ax.set_title(judul, loc="left", fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def buat_grafik_semua(df: pd.DataFrame, riwayat_df: Optional[pd.DataFrame] = None, folder: Path = config.OUTPUT_DIR / "grafik") -> dict[str, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    if df.empty:
        return {}
    res = {}
    p1 = folder / "top_model.png"
    pm = per_model(df, min_sampel=1).head(10)
    _plot_bar_horizontal(pm["model_slug"], pm["rata2"] / 1e6, "Top 10 Model (Rata-rata Harga Juta Rp)", "Juta Rp", p1)
    res["top_model"] = p1

    p2 = folder / "per_lokasi.png"
    pl = per_lokasi(df).head(10)
    _plot_bar_horizontal(pl["lokasi"], pl["jumlah"], "Jumlah Hasil Lelang per Lokasi", "Jumlah Unit", p2, color="#0D9488")
    res["per_lokasi"] = p2

    p3 = folder / "per_tahun.png"
    pt = per_tahun(df)
    _plot_garis(pt["tahun"].astype(str), pt["rata2"] / 1e6, "Rata-rata Harga per Tahun Pembuatan", "Tahun", "Juta Rp", p3)
    res["per_tahun"] = p3

    if riwayat_df is not None and not riwayat_df.empty and riwayat_df["run_id"].nunique() >= 2:
        p4 = folder / "tren_run.png"
        tr = tren_run(riwayat_df)
        _plot_garis(tr["run_id"].astype(str), tr["total_unit"], "Tren Jumlah Unit per Run", "Run ID", "Total Unit", p4, color="#7C3AED")
        res["tren_run"] = p4
    return res
