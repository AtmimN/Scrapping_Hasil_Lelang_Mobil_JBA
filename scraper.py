"""
Lapisan 1: PENGAMBILAN DATA (Scraper JBA).
"""
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup
from protego import Protego

import config

log = logging.getLogger(__name__)


class AksesDitolak(Exception):
    pass


class HalamanTidakAda(Exception):
    pass


class GagalAmbil(Exception):
    pass


class StrukturBerubah(Exception):
    pass


@dataclass(frozen=True)
class HasilLelang:
    model_slug: str
    merek: str
    model: str
    tahun: int
    lokasi: str
    harga: int


@dataclass(frozen=True)
class HasilScrape:
    berhasil: dict[str, list[HasilLelang]]
    gagal: dict[str, str]
    dihentikan: bool
    dilewati_baris: int


def harga_ke_int(teks: Optional[str]) -> Optional[int]:
    """Mengubah format harga teks ke integer rupiah."""
    if not teks:
        return None
    bersih = teks.replace("\xa0", " ").strip()
    m = re.search(r"Rp\s*([\d,.]+)", bersih, re.IGNORECASE)
    if not m:
        digits = re.sub(r"[^\d]", "", bersih)
        return int(digits) if digits and int(digits) > 0 else None
    nilai_str = m.group(1).replace(",", "").replace(".", "")
    return int(nilai_str) if nilai_str.isdigit() and int(nilai_str) > 0 else None


def parse_sitemap(xml_teks: str) -> list[tuple[str, str]]:
    """Mengambil pasangan (slug, url) yang cocok dengan pola sitemap model."""
    if not xml_teks:
        return []
    hasil_dict = {}
    for elem in ET.fromstring(xml_teks).iter():
        if elem.tag.endswith("loc") and elem.text:
            url = elem.text.strip()
            m = config.POLA_URL_MODEL.match(url)
            if m:
                slug = m.group(1).lower()
                hasil_dict.setdefault(slug, url)
    return sorted(hasil_dict.items(), key=lambda x: x[0])


def _cocok_header(teks_header: list[str]) -> bool:
    gabung = " ".join(t.lower() for t in teks_header)
    return all(k in gabung for k in ["merk", "model", "tahun", "lokasi", "harga"])


def _ekstrak_baris_buku(cols, slug: str) -> Optional[HasilLelang]:
    """Ekstrak satu baris tabel menjadi objek HasilLelang jika valid."""
    if len(cols) < 5:
        return None
    merek, model = cols[0].get_text(strip=True), cols[1].get_text(strip=True)
    thn_teks = cols[2].get_text(strip=True)
    lokasi, hrg_teks = cols[3].get_text(strip=True), cols[4].get_text(strip=True)
    if not (thn_teks.isdigit() and len(thn_teks) == 4):
        return None
    hrg = harga_ke_int(hrg_teks)
    if hrg is None or not merek or not model:
        return None
    return HasilLelang(slug, merek, model, int(thn_teks), lokasi, hrg)


def parse_hasil(html: str, slug: str) -> tuple[list[HasilLelang], int]:
    """Parse tabel hasil lelang dari HTML."""
    soup = BeautifulSoup(html, "html.parser")
    tabel = soup.find("div", class_="table-style") or soup.find("table")
    if not tabel:
        raise StrukturBerubah("Kontainer tabel hasil lelang tidak ditemukan")
    groups = tabel.find_all("div", class_="list-group")
    if not groups:
        raise StrukturBerubah("Elemen list-group di dalam tabel tidak ditemukan")
    headers = [d.get_text(strip=True) for d in groups[0].find_all("div", recursive=False)]
    if not _cocok_header(headers):
        raise StrukturBerubah(f"Header kolom tidak sesuai: {headers}")

    hasil, dilewati = [], 0
    for baris in groups[1:]:
        obj = _ekstrak_baris_buku(baris.find_all("div", recursive=False), slug)
        if obj:
            hasil.append(obj)
        else:
            dilewati += 1
    return hasil, dilewati


def boleh_diambil(url: str, robots_teks: str, user_agent: str) -> bool:
    return Protego.parse(robots_teks).can_fetch(url, user_agent) if robots_teks else True


class Pengambil:
    def __init__(self, jeda: float = config.JEDA_DETIK, session: Optional[requests.Session] = None):
        self.jeda = jeda
        self.ua = config.bangun_user_agent()
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": self.ua})
        self.robots_teks: Optional[str] = None

    def ambil_robots(self) -> str:
        try:
            r = self.session.get(config.ROBOTS_URL, timeout=config.TIMEOUT_DETIK)
            self.robots_teks = r.text if r.status_code == 200 else ""
        except Exception:
            self.robots_teks = ""
        return self.robots_teks

    def ambil_html(self, url: str) -> str:
        if self.robots_teks is None:
            self.ambil_robots()
        if not boleh_diambil(url, self.robots_teks, self.ua):
            raise GagalAmbil(f"URL dilarang oleh robots.txt: {url}")
        for coba in range(1, config.MAKS_COBA + 1):
            if self.jeda > 0:
                time.sleep(self.jeda)
            try:
                r = self.session.get(url, timeout=config.TIMEOUT_DETIK)
                if r.status_code in (403, 429) or any(c in r.text for c in ("cf-chl-bypass", "challenge-running", "g-recaptcha")):
                    raise AksesDitolak(f"Akses ditolak ({r.status_code}) di {url}")
                if r.status_code == 404:
                    raise HalamanTidakAda(f"404: {url}")
                r.raise_for_status()
                return r.text
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
                if isinstance(e, requests.exceptions.HTTPError) and r.status_code in (403, 429, 404):
                    raise
                if coba >= config.MAKS_COBA:
                    raise GagalAmbil(f"Gagal mengambil {url}: {e}")
                time.sleep(config.FAKTOR_BACKOFF ** coba)
        raise GagalAmbil(f"Menyerah mengambil {url}")

    def daftar_model(self) -> list[tuple[str, str]]:
        return parse_sitemap(self.ambil_html(config.SITEMAP_HASIL))

    def ambil_semua(self, maks_model: Optional[int] = None) -> HasilScrape:
        try:
            target = self.daftar_model()[:maks_model] if maks_model else self.daftar_model()
        except Exception as e:
            return HasilScrape({}, {"sitemap": str(e)}, isinstance(e, AksesDitolak), 0)
        berhasil, gagal, dihentikan, total_dilewati = {}, {}, False, 0
        for slug, url in target:
            try:
                baris, dilewati = parse_hasil(self.ambil_html(url), slug)
                berhasil[slug] = baris
                total_dilewati += dilewati
            except AksesDitolak as e:
                gagal[slug], dihentikan = str(e), True
                break
            except Exception as e:
                gagal[slug] = str(e)
        return HasilScrape(berhasil, gagal, dihentikan, total_dilewati)
