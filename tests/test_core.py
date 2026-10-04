"""Offline tests for the pure core module (no Qt/PySide6 required).

Run from the repo root:  python -m pytest tests/ -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core  # noqa: E402


# ---------------------------------------------------------------- colors

def test_color_from_name_deterministic_and_hex():
    c1 = core.color_from_name("pacman")
    c2 = core.color_from_name("pacman")
    c3 = core.color_from_name("galaga")
    assert c1 == c2
    assert c1 in core.PALETTE
    assert c3 in core.PALETTE
    assert all(c.startswith("#") and len(c) == 7 for c in (c1, c3))


def test_color_from_name_empty():
    assert core.color_from_name("") in core.PALETTE


def test_get_contrast_dark_vs_light():
    assert core.get_contrast_color("#000000") == "#ffffff"
    assert core.get_contrast_color("#ffffff") == "#000000"
    assert core.get_contrast_color("#0a84ff") == "#ffffff"
    assert core.get_contrast_color("#30d158") == "#000000"


# ---------------------------------------------------------------- sub_text

def test_sub_text_full():
    assert core.sub_text({"year": "1980", "maker": "Namco"}) == "1980 \u00b7 Namco"


def test_sub_text_missing_fields():
    assert core.sub_text({"year": "?", "maker": "?"}) == ""
    assert core.sub_text({"year": "1983", "maker": "?"}) == "1983"
    assert core.sub_text({}) == ""


# ---------------------------------------------------------------- settings

def test_load_settings_missing_file_returns_defaults(tmp_path):
    s = core.load_settings(settings_file=str(tmp_path / "nope.json"))
    assert s["fullscreen"] is False
    assert s["rom_dir"] == ""
    assert s["favorites"] == []


def test_settings_roundtrip(tmp_path):
    p = str(tmp_path / "s.json")
    core.save_settings({"fullscreen": True, "mame_cmd": "flatpak"}, p)
    loaded = core.load_settings(settings_file=p)
    assert loaded["fullscreen"] is True
    assert loaded["mame_cmd"] == "flatpak"
    # defaults fill in keys that weren't saved
    assert loaded["rom_dir"] == ""


def test_load_settings_corrupt_file(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{not valid json")
    s = core.load_settings(settings_file=str(p))
    assert s["fullscreen"] is False


# ---------------------------------------------------------------- meta

def test_meta_roundtrip(tmp_path):
    p = str(tmp_path / "m.json")
    data = {"pacman": {"desc": "Pac-Man", "year": "1980", "maker": "Namco",
                       "clone": "", "bios": False}}
    core.save_meta(data, p)
    assert core.load_meta(p) == data


def test_load_meta_missing_file(tmp_path):
    assert core.load_meta(str(tmp_path / "none.json")) == {}


# ---------------------------------------------------------------- rom listing / sizes

def test_list_roms(tmp_path):
    (tmp_path / "pacman.zip").write_bytes(b"x")
    (tmp_path / "Galaga.ZIP").write_bytes(b"x")
    (tmp_path / "readme.txt").write_text("no")
    os.makedirs(tmp_path / "sub")
    roms = core.list_roms(str(tmp_path))
    assert roms == ["Galaga", "pacman"]  # case-insensitive match, sorted


def test_list_roms_missing_dir():
    assert core.list_roms("") == []
    assert core.list_roms("/nonexistent/path/here") == []


def test_folder_size_sums_all_files(tmp_path):
    os.makedirs(tmp_path / "a" / "b")
    (tmp_path / "a" / "one.bin").write_bytes(b"12345678")  # 8 bytes
    (tmp_path / "a" / "b" / "two.bin").write_bytes(b"xy")  # 2 bytes
    assert core.folder_size(str(tmp_path)) == 10


def test_fmt_size():
    assert core.fmt_size(0) == "0 B"
    assert core.fmt_size(512) == "512 B"
    assert core.fmt_size(2048) == "2.0 KB"
    assert core.fmt_size(5 * 1024 * 1024) == "5.0 MB"
    assert core.fmt_size(2 * 1024 ** 3) == "2.0 GB"


# ---------------------------------------------------------------- thumb_name / img_path

def test_thumb_name_sanitizes():
    # Apostrophes are valid in thumbnail filenames and are kept.
    assert core.thumb_name("Street Fighter II' Champion Edition") == \
        "Street Fighter II' Champion Edition"
    assert core.thumb_name("A/B: C") == "A_B_ C"
    assert ":" not in core.thumb_name("Dr: Strangelove")


def test_img_path(tmp_path):
    assert core.img_path("pacman", str(tmp_path)) == str(tmp_path / "pacman.png")


# ---------------------------------------------------------------- mame cmd resolution

def test_resolve_native():
    assert core.resolve_mame_cmd({"mame_cmd": "native"}) == ["mame"]


def test_resolve_flatpak():
    assert core.resolve_mame_cmd({"mame_cmd": "flatpak"}) == \
        ["flatpak", "run", "org.mamedev.MAME"]


def test_resolve_default_and_unknown():
    assert core.resolve_mame_cmd({}) == ["mame"]
    assert core.resolve_mame_cmd({"mame_cmd": "custommame"}) == ["custommame"]


def test_allow_flatpak_noop_for_native():
    # Native mode returns False and never shells out.
    assert core.allow_flatpak("/some/path", cmd=["mame"]) is False


# ---------------------------------------------------------------- parse_machine_xml

def test_parse_machine_xml_basic():
    xml = """<?xml version="1.0"?>
<mame>
  <machine name="pacman" sourcefile="pacman.c">
    <description>Pac-Man</description>
    <year>1980</year>
    <manufacturer>Namco</manufacturer>
  </machine>
  <machine name="neogeo" isbios="yes" sourcefile="neogeo.c">
    <description>Neo-Geo BIOS</description>
  </machine>
  <machine name="mspacman" cloneof="pacman" sourcefile="pacman.c">
    <description>Ms. Pac-Man</description>
    <year>1981</year>
    <manufacturer>Midway</manufacturer>
  </machine>
</mame>
"""
    out = core.parse_machine_xml(xml)
    assert out["pacman"]["desc"] == "Pac-Man"
    assert out["pacman"]["year"] == "1980"
    assert out["pacman"]["maker"] == "Namco"
    assert out["pacman"]["clone"] == ""
    assert out["pacman"]["bios"] is False
    assert out["neogeo"]["bios"] is True
    assert out["neogeo"]["year"] == "?"  # missing tag falls back
    assert out["mspacman"]["clone"] == "pacman"


def test_parse_machine_xml_malformed():
    assert core.parse_machine_xml("this is not xml") == {}
    assert core.parse_machine_xml("") == {}


# ---------------------------------------------------------------- filter_games

def _meta():
    return {
        "pacman": {"desc": "Pac-Man", "year": "1980", "maker": "Namco",
                   "clone": "", "bios": False},
        "mspacman": {"desc": "Ms. Pac-Man", "year": "1981", "maker": "Midway",
                     "clone": "pacman", "bios": False},
        "galaga": {"desc": "Galaga", "year": "1981", "maker": "Namco",
                   "clone": "", "bios": False},
        "neogeo": {"desc": "Neo-Geo BIOS", "year": "?", "maker": "?",
                   "clone": "", "bios": True},
    }


def test_filter_games_sorted_by_desc():
    assert core.filter_games(list(_meta()), _meta()) == \
        ["galaga", "mspacman", "pacman"]


def test_filter_games_excludes_bios():
    # BIOS entries never appear even when there are no other games.
    bioses = {k: v for k, v in _meta().items() if v["bios"]}
    assert core.filter_games(list(bioses), bioses) == []


def test_filter_games_query_token_all_must_match():
    m = _meta()
    assert core.filter_games(list(m), m, query="Pac") == ["mspacman", "pacman"]
    # both tokens must appear; "Ms. Pac-Man" holds both "pac" and "man"
    assert core.filter_games(list(m), m, query="pac man") == ["mspacman", "pacman"]
    # token spanning a field break ("pac"+"Namco") matches pacman only
    assert core.filter_games(list(m), m, query="pac Namco") == ["pacman"]


def test_filter_games_query_matches_year_maker_clone():
    m = _meta()
    assert core.filter_games(list(m), m, query="1981") == ["galaga", "mspacman"]
    assert core.filter_games(list(m), m, query="Namco") == ["galaga", "pacman"]
    # clone field is part of the search haystack: mspacman declares clone=pacman
    assert core.filter_games(list(m), m, query="pacman") == ["mspacman", "pacman"]


def test_filter_games_favorites_only():
    m = _meta()
    assert core.filter_games(list(m), m, favorites_only=True,
                             favorites=["pacman", "neogeo"]) == ["pacman"]


def test_filter_games_unknown_roms_no_meta():
    assert core.filter_games(["zzz", "aaa"], {}) == ["aaa", "zzz"]
    assert core.filter_games(["zzz", "aaa"], {}, query="nomatch") == []


# ---------------------------------------------------------------- download_image

def test_download_image_cached_skips_network(tmp_path, monkeypatch):
    img = tmp_path / "pacman.png"
    img.write_bytes(b"PNGDATA")
    calls = []

    def fake_urlopen(url, timeout=10):
        calls.append(url)
        raise AssertionError("should not hit network when cached")

    monkeypatch.setattr(core.urllib.request, "urlopen", fake_urlopen)
    result = core.download_image("pacman", "Pac-Man", str(tmp_path), force=False)
    assert result is True
    assert calls == []


def test_download_image_none_marker_skips_network(tmp_path, monkeypatch):
    (tmp_path / "pacman.png.none").write_text("")
    calls = []

    def fake_urlopen(url, timeout=10):
        calls.append(url)
        raise AssertionError("should not hit network when .none exists")

    monkeypatch.setattr(core.urllib.request, "urlopen", fake_urlopen)
    result = core.download_image("pacman", "Pac-Man", str(tmp_path), force=False)
    assert result is False
    assert calls == []


def test_download_image_success(tmp_path, monkeypatch):
    class DummyCtx:
        def read(self):
            return b"\x89PNG"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(url, timeout=10):
        assert url.startswith(core.BASE_URL)
        return DummyCtx()

    monkeypatch.setattr(core.urllib.request, "urlopen", fake_urlopen)
    result = core.download_image("galaga", "Galaga", str(tmp_path), force=False)
    assert result is True
    assert (tmp_path / "galaga.png").read_bytes() == b"\x89PNG"
    assert not (tmp_path / "galaga.png.none").exists()


def test_download_image_all_kinds_fail_writes_none_marker(tmp_path, monkeypatch):
    def fail_urlopen(url, timeout=10):
        raise OSError("boom")

    monkeypatch.setattr(core.urllib.request, "urlopen", fail_urlopen)
    result = core.download_image("zzz", "No Cover", str(tmp_path), force=False)
    assert result is False
    assert (tmp_path / "zzz.png.none").exists()


def test_download_image_force_retries_stale_none_marker(tmp_path, monkeypatch):
    """force=True clears a stale .none marker and retries the download."""
    (tmp_path / "pacman.png.none").write_text("")
    hit = []

    def fake_urlopen(url, timeout=10):
        hit.append(url)
        class C:
            def read(self):
                return b"\x89PNG"
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
        return C()

    monkeypatch.setattr(core.urllib.request, "urlopen", fake_urlopen)
    result = core.download_image("pacman", "Pac-Man", str(tmp_path), force=True)
    assert result is True
    assert (tmp_path / "pacman.png").exists()
    assert not (tmp_path / "pacman.png.none").exists()
    assert hit  # network actually retried


def test_download_image_force_writes_none_when_still_missing(tmp_path, monkeypatch):
    def fail_urlopen(url, timeout=10):
        raise OSError("still down")

    monkeypatch.setattr(core.urllib.request, "urlopen", fail_urlopen)
    result = core.download_image("abc", "ABC", str(tmp_path), force=True)
    assert result is False
    assert (tmp_path / "abc.png.none").exists()