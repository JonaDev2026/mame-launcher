"""Pure core logic for MAME Launcher — no Qt/PySide6 dependency.

Everything here is UI-free so it can be imported and tested without a
display or the PySide6 stack. The GUI (z.mame.py) imports these helpers.
"""

import hashlib
import json
import os
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

CONFIG_DIR = os.path.expanduser("~/.config/mame_launcher")
IMG_DIR = os.path.join(CONFIG_DIR, "img")
META_FILE = os.path.join(CONFIG_DIR, "meta.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
BASE_URL = "https://raw.githubusercontent.com/libretro-thumbnails/MAME/master/"
IMG_KINDS = ["Named_Boxarts", "Named_Titles", "Named_Snaps"]

MAME_HOME = os.path.expanduser("~/mame")
MAME_FLATPAK_CMD = ["flatpak", "run", "org.mamedev.MAME"]
MAME_NATIVE_CMD = ["mame"]
DEFAULT_SETTINGS = {
    "fullscreen": False,
    "rom_dir": "",
    "bios_dir": "",
    "favorites": [],
    "mame_cmd": "native",
}

PALETTE = ("#ff5257", "#ff9f0a", "#ffd60a", "#30d158", "#0a84ff",
           "#bf5af2", "#ff375f", "#64d2ff")
SCALA_FILE = ("#ff5257", "#30d158", "#ff7f11", "#42a0ff",
              "#ffd60a", "#bf5af2", "#ff6fae", "#64d2ff",
              "#c19272", "#66e3b0", "#d4af37", "#9190f9",
              "#e23179", "#b4e04a", "#ff9670", "#c0c7d0")
DOT = 24
ROW_H = 44
LABEL_COLORS = {"Year": "#0a84ff", "Maker": "#30d158",
                "ROM": "#ff9f0a", "Clone of": "#bf5af2"}


def color_from_name(name):
    """Deterministic accent color for a game name (md5 of the name)."""
    n = int(hashlib.md5(name.encode("utf-8")).hexdigest()[:8], 16)
    return PALETTE[n % len(PALETTE)]


def get_contrast_color(hex_color):
    """White or black depending on the perceived luminance of hex_color."""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminance > 0.5 else "#ffffff"


def sub_text(meta):
    """'Year · Maker' subtitle line for a game's metadata dict."""
    parts = [meta.get("year", "?"), meta.get("maker", "?")]
    return " \u00b7 ".join(x for x in parts if x and x != "?")


def load_settings(settings_file=SETTINGS_FILE, defaults=None):
    s = dict(defaults or DEFAULT_SETTINGS)
    try:
        with open(settings_file, encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    return s


def save_settings(settings, settings_file=SETTINGS_FILE):
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def load_meta(meta_file=META_FILE):
    try:
        with open(meta_file, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_meta(meta, meta_file=META_FILE):
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)


def list_roms(rom_dir):
    """Sorted list of ROM names (`.zip` basenames) in rom_dir."""
    if not rom_dir or not os.path.isdir(rom_dir):
        return []
    return sorted(f[:-4] for f in os.listdir(rom_dir) if f.lower().endswith(".zip"))


def folder_size(path):
    total = 0
    for root, _d, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def fmt_size(n):
    n = float(n)
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.1f %s" % (n, u) if u != "B" else "%d B" % n
        n /= 1024
    return "%.1f TB" % n


def thumb_name(desc):
    """Sanitize a MAME description into a libretro-thumbnails-safe filename."""
    for ch in '&*/:`<>?\\|"':
        desc = desc.replace(ch, "_")
    return desc


def img_path(name, img_dir=IMG_DIR):
    return os.path.join(img_dir, name + ".png")


def resolve_mame_cmd(settings):
    """Return the MAME invocation list honoring the configured mode."""
    mode = settings.get("mame_cmd", "native")
    if mode == "flatpak":
        return list(MAME_FLATPAK_CMD)
    if mode == "native":
        return list(MAME_NATIVE_CMD)
    # Fallback: treat unknown/custom values as a plain command line.
    return [mode] if mode else list(MAME_NATIVE_CMD)


def allow_flatpak(path, cmd=None):
    """Grant flatpak filesystem access to path so MAME can see the ROMs."""
    cmd = cmd or MAME_FLATPAK_CMD
    if cmd[0] != "flatpak":
        return False
    try:
        subprocess.run(["flatpak", "override", "--user", "--filesystem=" + path,
                        cmd[-1]], capture_output=True, timeout=30)
        return True
    except Exception:
        return False


def parse_machine_xml(xml_text):
    """Parse a MAME `-listxml` document into {name: metadata}."""
    out = {}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    for m in root.iter("machine"):
        out[m.get("name")] = {
            "desc": (m.findtext("description") or m.get("name")),
            "year": m.findtext("year") or "?",
            "maker": m.findtext("manufacturer") or "?",
            "clone": m.get("cloneof") or "",
            "bios": m.get("isbios") == "yes" or m.get("isdevice") == "yes",
        }
    return out


def fetch_meta_chunk(names, mame_cmd=None):
    """Query MAME `-listxml` for the given names and return metadata."""
    out = {}
    if not names:
        return out
    try:
        res = subprocess.run((mame_cmd or MAME_NATIVE_CMD) + ["-listxml"] + names,
                             capture_output=True, text=True, timeout=60)
        out = parse_machine_xml(res.stdout)
    except Exception:
        pass
    return out


def download_image(name, desc, img_dir=IMG_DIR, force=False):
    """Download the first available cover kind for a game.

    Returns True on success, False on total failure. When a thumbnail is
    unavailable a `.none` marker is written so later runs skip it; pass
    force=True to retry downloads that previously failed.
    """
    path = img_path(name, img_dir)
    if not force and (os.path.exists(path) or os.path.exists(path + ".none")):
        return os.path.exists(path)
    if force:
        # Clear stale `.none` marker so we actually retry.
        if os.path.exists(path + ".none"):
            try:
                os.remove(path + ".none")
            except OSError:
                pass
    fname = urllib.parse.quote(thumb_name(desc)) + ".png"
    for kind in IMG_KINDS:
        try:
            with urllib.request.urlopen(BASE_URL + kind + "/" + fname,
                                        timeout=10) as r:
                data = r.read()
            with open(path, "wb") as f:
                f.write(data)
            return True
        except Exception:
            continue
    # No cover available: mark it so we don't re-hit the network every run.
    with open(path + ".none", "w") as f:
        f.close()
    return False


def filter_games(roms, meta, query="", favorites_only=False, favorites=None):
    """Pure filter/sort used by the GUI list.

    Returns the ROM names matching query terms (each token must appear
    somewhere in desc/short-name/year/maker/clone), honoring a favorites
    filter, sorted by display description (case-insensitive). BIOS entries
    are always excluded.
    """
    favs = set(favorites or [])
    q_tokens = [t.lower() for t in query.split()] if query else []
    filtered = []
    for r in roms:
        m = meta.get(r) or {}
        if m.get("bios", False):
            continue
        if favorites_only and r not in favs:
            continue
        if q_tokens:
            desc = m.get("desc", r)
            hay = " ".join((desc, r, m.get("year", "?"),
                            m.get("maker", "?"), m.get("clone", ""))).lower()
            if not all(t in hay for t in q_tokens):
                continue
        filtered.append(r)
    filtered.sort(key=lambda r: (meta.get(r, {}).get("desc", r)).lower())
    return filtered