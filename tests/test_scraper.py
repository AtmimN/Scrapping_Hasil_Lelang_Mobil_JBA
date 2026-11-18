"""
Pengujian scraper.py:
- harga_ke_int
- parse_sitemap
- parse_hasil (v1)
- Header tidak ditemukan -> StrukturBerubah, tabel kosong valid -> daftar kosong
- boleh_diambil dengan robots_jba.txt
- Pengambil: 403, 429, 404, retry timeout
"""
from pathlib import Path
import pytest
import requests

from scraper import (
    AksesDitolak,
    GagalAmbil,
    HalamanTidakAda,
    HasilLelang,
    Pengambil,
    StrukturBerubah,
    boleh_diambil,
    harga_ke_int,
    parse_hasil,
    parse_sitemap,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_harga_ke_int():
    assert harga_ke_int("Rp 104,500,000") == 104500000
    assert harga_ke_int("Rp 104.500.000") == 104500000
    assert harga_ke_int("Rp  104,500,000 ") == 104500000
    assert harga_ke_int("Rp 0") is None
    assert harga_ke_int("") is None
    assert harga_ke_int("teks acak tidak ada angka") is None


def test_parse_sitemap():
    xml_file = FIXTURES_DIR / "sitemap_hasil_mobil.xml"
    with open(xml_file, "r", encoding="utf-8") as f:
        xml_teks = f.read()

    hasil = parse_sitemap(xml_teks)
    slugs = [slug for slug, url in hasil]
    # avanza, xenia, innova (tanpa duplikat, terurut)
    assert slugs == ["avanza", "innova", "xenia"]
    assert all(url.startswith("https://www.jba.co.id/id/hasil-harga-lelang/lelang/") for _, url in hasil)


def test_parse_hasil_v1():
    v1_file = FIXTURES_DIR / "hasil_avanza_v1.html"
    with open(v1_file, "r", encoding="utf-8") as f:
        html = f.read()

    baris, dilewati = parse_hasil(html, "avanza")
    assert len(baris) > 0
    assert isinstance(baris[0], HasilLelang)
    assert baris[0].model_slug == "avanza"
    assert baris[0].harga > 0
    assert baris[0].tahun > 1900
    assert baris[0].merek != ""
    assert baris[0].model != ""

    # Cek baris identik tetap ada
    avanza_g_2020 = [b for b in baris if "AVANZA G 1.3" in b.model and b.tahun == 2020 and b.lokasi == "Jakarta"]
    assert len(avanza_g_2020) >= 2

    # Tidak boleh ada nomor polisi atau blok rekomendasi
    for b in baris:
        assert "nomor_polisi" not in b.__dict__
        assert "nopol" not in b.__dict__


def test_parse_hasil_struktur_berubah_dan_kosong():
    html_rusak = "<div><p>Tidak ada tabel di sini</p></div>"
    with pytest.raises(StrukturBerubah):
        parse_hasil(html_rusak, "avanza")

    html_header_salah = """
    <div class="table-style">
      <div class="list-group">
        <div>Kolom A</div><div>Kolom B</div>
      </div>
    </div>
    """
    with pytest.raises(StrukturBerubah):
        parse_hasil(html_header_salah, "avanza")

    html_tabel_kosong = """
    <div class="table-style">
      <div class="list-group">
        <div>Merk</div><div>Model</div><div>Tahun</div><div>Lokasi</div><div>Harga hasil lelang</div>
      </div>
    </div>
    """
    hasil, dilewati = parse_hasil(html_tabel_kosong, "avanza")
    assert hasil == []
    assert dilewati == 0


def test_boleh_diambil_robots():
    robots_file = FIXTURES_DIR / "robots_jba.txt"
    with open(robots_file, "r", encoding="utf-8") as f:
        robots_teks = f.read()

    ua = "PantauHasilLelangJBA/1.0 (kontak: test@example.com)"
    # Dilarang
    assert not boleh_diambil("https://www.jba.co.id/id/lelang-mobil/search?vehicle_type=car", robots_teks, ua)
    assert not boleh_diambil("https://www.jba.co.id/id/search?something&page=2", robots_teks, ua)
    assert not boleh_diambil("https://www.jba.co.id/id/search-detail/51367/540014", robots_teks, ua)

    # Boleh
    assert boleh_diambil("https://www.jba.co.id/id/hasil-harga-lelang/lelang/avanza", robots_teks, ua)
    assert boleh_diambil("https://www.jba.co.id/sitemap/id-hasil-lelang-mobil.xml", robots_teks, ua)


class DummyResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


class DummySession:
    def __init__(self, responses):
        self.responses = responses
        self.panggilan = 0
        self.headers = {}

    def get(self, url, timeout=None):
        resp = self.responses[min(self.panggilan, len(self.responses) - 1)]
        self.panggilan += 1
        if isinstance(resp, Exception):
            raise resp
        return resp


def test_pengambil_status_khusus(monkeypatch):
    monkeypatch.setattr("config.CONTACT_EMAIL", "test@example.com")
    url = "https://www.jba.co.id/id/hasil-harga-lelang/lelang/avanza"

    # 403 / 429 -> AksesDitolak
    sess_403 = DummySession([DummyResponse(403, "Forbidden")])
    p = Pengambil(jeda=0, session=sess_403)
    p.robots_teks = ""
    with pytest.raises(AksesDitolak):
        p.ambil_html(url)

    # 404 -> HalamanTidakAda
    sess_404 = DummySession([DummyResponse(404, "Not Found")])
    p4 = Pengambil(jeda=0, session=sess_404)
    p4.robots_teks = ""
    with pytest.raises(HalamanTidakAda):
        p4.ambil_html(url)

    # Timeout di-retry hingga MAKS_COBA lalu GagalAmbil
    sess_timeout = DummySession([requests.exceptions.Timeout("Timeout!")] * 5)
    pt = Pengambil(jeda=0, session=sess_timeout)
    pt.robots_teks = ""
    with pytest.raises(GagalAmbil):
        pt.ambil_html(url)
    assert sess_timeout.panggilan >= 3

