"""
Lapisan 4c: DASHBOARD STREAMLIT.

Dashboard web hanya-baca (read-only) untuk eksplorasi data hasil lelang JBA.
Jalankan: streamlit run app.py
"""
import pandas as pd
import streamlit as st

import analisis
import config
import db
import pesan

st.set_page_config(
    page_title="Dashboard Pantau Lelang JBA",
    page_icon="🚗",
    layout="wide"
)


@st.cache_data(ttl=300)
def muat_data():
    """Membaca data dari database SQLite dalam mode hanya-baca."""
    if not config.DB_PATH.exists():
        return pd.DataFrame(), pd.DataFrame(), [], None
    try:
        with db.buka(config.DB_PATH, hanya_baca=True) as conn:
            rows = db.hasil_aktif(conn)
            df = analisis.ke_dataframe(rows)
            riwayat_rows = conn.execute("SELECT * FROM riwayat_model").fetchall()
            riwayat_df = pd.DataFrame([dict(r) for r in riwayat_rows]) if riwayat_rows else pd.DataFrame()
            perubahan_data = db.perubahan_run(conn)
            log_row = db.log_terakhir(conn)
            return df, riwayat_df, [dict(p) for p in perubahan_data], dict(log_row) if log_row else None
    except Exception:
        return pd.DataFrame(), pd.DataFrame(), [], None


df, riwayat_df, perubahan_list, log_terakhir = muat_data()

st.title("🚗 Dashboard Pemantau Hasil Lelang Mobil JBA")

if df.empty:
    st.info(
        "ℹ️ **Database lelang masih kosong atau belum ada.**\n\n"
        "Silakan jalankan pipeline pengumpulan data terlebih dahulu dengan perintah di terminal:\n"
        "```bash\npython main.py --maks-model 3\n```"
    )
    st.stop()

# Info Stempel Waktu Terakhir
waktu_selesai = log_terakhir.get("selesai", "-") if log_terakhir else "-"
st.caption(f"Sumber data: jba.co.id &middot; Pembaruan terakhir (UTC): {waktu_selesai}")

# ---------- Filter Sidebar ----------
st.sidebar.header("🔍 Filter Pencarian")

semua_merek = sorted(df["merek"].dropna().unique())
pilih_merek = st.sidebar.multiselect("Merek Kendaraan", options=semua_merek, placeholder="Semua merek")

df_terpilih = df[df["merek"].isin(pilih_merek)] if pilih_merek else df

semua_model = sorted(df_terpilih["model_slug"].dropna().unique())
pilih_model = st.sidebar.multiselect("Model Kendaraan", options=semua_model, placeholder="Semua model")

if pilih_model:
    df_terpilih = df_terpilih[df_terpilih["model_slug"].isin(pilih_model)]

# Rentang Tahun
min_thn = int(df["tahun"].min())
maks_thn = int(df["tahun"].max())
rentang_thn = st.sidebar.slider("Tahun Pembuatan", min_thn, maks_thn, (min_thn, maks_thn))

# Filter Lokasi
semua_lokasi = sorted(df["lokasi"].dropna().unique())
pilih_lokasi = st.sidebar.multiselect("Lokasi Lelang", options=semua_lokasi, placeholder="Semua lokasi")

# Rentang Harga
min_hrg = int(df["harga"].min())
maks_hrg = int(df["harga"].max())
rentang_hrg = st.sidebar.slider(
    "Rentang Harga (Rp)",
    min_value=min_hrg,
    max_value=maks_hrg,
    value=(min_hrg, maks_hrg),
    step=5_000_000,
    format="Rp %d"
)

# Terapkan Filter
f = df_terpilih[
    df_terpilih["tahun"].between(rentang_thn[0], rentang_thn[1]) &
    df_terpilih["harga"].between(rentang_hrg[0], rentang_hrg[1])
]
if pilih_lokasi:
    f = f[f["lokasi"].isin(pilih_lokasi)]

if f.empty:
    st.warning("Tidak ada data mobil yang cocok dengan kombinasi filter di atas.")
    st.stop()

# ---------- Baris Metrik Utama ----------
r = analisis.ringkasan(f)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Unit", f"{r['total_hasil']:,}")
c2.metric("Jumlah Model", f"{r['jumlah_model']}")
c3.metric("Rata-rata Harga", pesan.rupiah(r["harga_rata2"]))
c4.metric("Harga Median", pesan.rupiah(r["median"]))

st.divider()

# ---------- Tab Konten ----------
tab_ringkas, tab_model, tab_lokasi, tab_tren, tab_data = st.tabs([
    "📊 Ringkasan", "🚘 Per Model", "📍 Per Lokasi", "📈 Tren & Perubahan", "📋 Data Lengkap"
])

with tab_ringkas:
    st.subheader("Statistik Umum")
    col_a, col_b = st.columns(2)
    with col_a:
        st.write("**Top 10 Model Terbanyak**")
        top_unit = f["model_slug"].value_counts().head(10).reset_index()
        top_unit.columns = ["Model", "Jumlah Unit"]
        st.bar_chart(top_unit.set_index("Model"))
    with col_b:
        st.write("**Rata-rata Harga per Tahun Pembuatan**")
        pt = analisis.per_tahun(f)
        st.line_chart(pt.set_index("tahun")["rata2"])

with tab_model:
    st.subheader("Analisis Harga per Model")
    pm = analisis.per_model(f, min_sampel=1)
    st.dataframe(
        pm.style.format({
            "rata2": "Rp {:,.0f}",
            "min": "Rp {:,.0f}",
            "maks": "Rp {:,.0f}",
            "jumlah": "{:,}"
        }),
        use_container_width=True
    )

with tab_lokasi:
    st.subheader("Sebaran Unit per Lokasi Lelang")
    pl = analisis.per_lokasi(f)
    col_l1, col_l2 = st.columns([1, 1])
    with col_l1:
        st.dataframe(pl.style.format({"rata2": "Rp {:,.0f}", "jumlah": "{:,}"}), use_container_width=True)
    with col_l2:
        st.bar_chart(pl.head(10).set_index("lokasi")["jumlah"])

with tab_tren:
    st.subheader("Perubahan Data & Riwayat Run")
    if perubahan_list:
        st.write("Catatan Perubahan pada Run Terakhir:")
        df_p = pd.DataFrame(perubahan_list)
        st.dataframe(df_p, use_container_width=True)
    else:
        st.info("Belum ada catatan perubahan unit.")

    if not riwayat_df.empty and riwayat_df["run_id"].nunique() >= 2:
        st.write("Tren Total Unit per Run:")
        tr = analisis.tren_run(riwayat_df)
        st.line_chart(tr.set_index("run_id")["total_unit"])

with tab_data:
    st.subheader("Tabel Data Hasil Lelang Lengkap")
    kolom_tampil = ["merek", "model", "tahun", "lokasi", "harga"]
    tampil_df = f[kolom_tampil].sort_values("harga", ascending=False)
    st.dataframe(tampil_df.style.format({"harga": "Rp {:,.0f}"}), use_container_width=True)
    csv_bytes = tampil_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Unduh Data Terfilter (.CSV)",
        data=csv_bytes,
        file_name="hasil_lelang_terfilter.csv",
        mime="text/csv"
    )

