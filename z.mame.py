#!/usr/bin/env python3
"""MAME Launcher - lists ROMs from a folder, shows cover + info, launches game.
Metadata comes from MAME itself (-listxml). Images from libretro-thumbnails
(no API key). Everything is cached on disk."""
import colorsys
import hashlib
import html
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from PySide6.QtCore import QRect, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import (QAction, QActionGroup, QColor, QDesktopServices, QIcon,
                           QImage, QPainter, QPalette, QPen, QPixmap)
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QStyle, QStyledItemDelegate,
                               QListWidget, QListWidgetItem, QMenuBar,
                               QPushButton, QVBoxLayout, QWidget)

MAME_CMD = ["flatpak", "run", "org.mamedev.MAME"]
CACHE_DIR = os.path.expanduser("~/.cache/mame_launcher")
IMG_DIR = os.path.join(CACHE_DIR, "img")
META_FILE = os.path.join(CACHE_DIR, "meta.json")
BASE_URL = "https://raw.githubusercontent.com/libretro-thumbnails/MAME/master/"
IMG_KINDS = ["Named_Boxarts", "Named_Titles", "Named_Snaps"]

SETTINGS_FILE = os.path.expanduser("~/.config/mame_launcher/settings.json")
MAME_HOME = os.path.expanduser("~/mame")
DEFAULT_SETTINGS = {"fullscreen": False, "rom_dir": "", "bios_dir": ""}

os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)


PALETTE = ("#ff5257", "#ff9f0a", "#ffd60a", "#30d158", "#0a84ff",
           "#bf5af2", "#ff375f", "#64d2ff")
DOT = 24


def color_from_name(name):
    """Fallback: always the same colour for the same name."""
    n = int(hashlib.md5(name.encode("utf-8")).hexdigest()[:8], 16)
    return PALETTE[n % len(PALETTE)]


def color_from_image(path):
    """Dominant colour of the cover (same method as the XVB dots):
    skip transparent, white, black and grey pixels, take the most common
    hue, bring it to a brightness that shows on dark."""
    im = QImage(path)
    if im.isNull():
        return None
    im = im.scaled(48, 48, Qt.KeepAspectRatio)
    buckets = {}
    for y in range(im.height()):
        for x in range(im.width()):
            c = im.pixelColor(x, y)
            if c.alpha() < 128:
                continue
            h, l, sa = colorsys.rgb_to_hls(c.redF(), c.greenF(), c.blueF())
            if sa < 0.35 or l < 0.12 or l > 0.92:
                continue
            t = buckets.setdefault(int(h * 12) % 12, [0, 0.0, 0.0, 0.0])
            t[0] += 1
            t[1] += h
            t[2] += l
            t[3] += sa
    if not buckets:
        return None
    n, h, l, sa = max(buckets.values(), key=lambda t: t[0])
    h, l, sa = h / n, l / n, sa / n
    l = min(0.72, max(0.55, l))
    sa = max(0.75, sa)
    if 0.55 <= h <= 0.75:
        l = max(l, 0.63)
    r, g, b = colorsys.hls_to_rgb(h, l, sa)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def make_dot(color):
    pm = QPixmap(DOT, DOT)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    r = DOT * 0.22
    p.drawEllipse(DOT / 2.0 - r, DOT / 2.0 - r, 2 * r, 2 * r)
    p.end()
    return QIcon(pm)


# XVB palette
AUTHOR, YEAR = "Jonathan Sanfilippo", "2026"
STATO = "#0c0c0c"
FONDO, PANNELLO, CERCA = "#121212", "#131215", "#252428"
TASTO, SCELTO, TESTO, GRIGIO = "#2c2c2c", "#3a3a3a", "#e0e0e0", "#9e9e9e"
IN_ONDA = "#3b2f4f"

STYLE = f"""
QWidget {{ background: {FONDO}; color: {TESTO}; }}
QLabel {{ background: transparent; }}
QWidget#side {{ background: {PANNELLO}; }}
QMenuBar {{ background: {PANNELLO}; color: #ffffff; }}
QMenuBar::item {{ background: transparent; padding: 4px 10px; }}
QMenuBar::item:selected {{ background: {CERCA}; }}
QMenu {{ background: {CERCA}; color: {TESTO}; border: 1px solid {SCELTO}; }}
QMenu::item {{ padding: 5px 24px; }}
QMenu::item:selected {{ background: {IN_ONDA}; color: #ffffff; }}
QMenu::separator {{ height: 1px; background: {SCELTO}; margin: 4px 0; }}
QLineEdit {{ background: {CERCA}; color: {TESTO}; border: none; border-radius: 18px;
            padding: 0 14px 0 4px; min-height: 36px; selection-background-color: {IN_ONDA}; }}
QListWidget {{ background: {PANNELLO}; border: none; outline: 0; }}
QListWidget::item:selected, QListWidget::item:selected:!active
    {{ background: {SCELTO}; color: #ffffff; }}
QPushButton {{ background: {TASTO}; color: {TESTO}; border: none; border-radius: 6px;
              padding: 8px; }}
QPushButton:hover {{ background: {SCELTO}; }}
QWidget#status {{ background: {STATO}; }}
QWidget#status QLabel {{ color: {GRIGIO}; }}
"""


def lens_icon():
    pm = QPixmap(20, 20)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(GRIGIO), 2)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.drawEllipse(3, 3, 10, 10)
    p.drawLine(11, 11, 16, 16)
    p.end()
    return QIcon(pm)


ROW_H = 44                      # two lines: name and, below, year / maker
LABEL_COLORS = {"Year": "#0a84ff", "Maker": "#30d158",
                "ROM": "#ff9f0a", "Clone of": "#bf5af2"}


def sub_text(m):
    parts = [m["year"], m["maker"]]
    return " \u00b7 ".join(x for x in parts if x and x != "?")


class GameDelegate(QStyledItemDelegate):
    """Dot + name, and under the name the subtitle in the dot's colour."""

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), ROW_H)

    def paint(self, painter, option, index):
        painter.save()
        r = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        if selected:
            painter.fillRect(r, QColor(SCELTO))
        icon = index.data(Qt.DecorationRole)
        if isinstance(icon, QIcon):
            icon.paint(painter, QRect(r.left() + 4, r.top() + (r.height() - DOT) // 2,
                                      DOT, DOT))
        x = r.left() + DOT + 10
        w = r.width() - DOT - 18
        name = painter.fontMetrics().elidedText(index.data(Qt.DisplayRole) or "",
                                                Qt.ElideRight, w)
        painter.setPen(QColor("#ffffff" if selected else TESTO))
        painter.drawText(QRect(x, r.top() + 4, w, 18), Qt.AlignLeft | Qt.AlignVCenter, name)
        f = painter.font()
        if f.pointSizeF() > 0:
            f.setPointSizeF(max(f.pointSizeF() - 1.5, 7))
            painter.setFont(f)
        sub = painter.fontMetrics().elidedText(index.data(Qt.UserRole + 1) or "",
                                               Qt.ElideRight, w)
        painter.setPen(QColor(index.data(Qt.UserRole + 2) or GRIGIO))
        painter.drawText(QRect(x, r.top() + 23, w, 16), Qt.AlignLeft | Qt.AlignVCenter, sub)
        painter.restore()


class SearchBox(QLineEdit):
    """Pill search box with a lens on the left, like XVB. Esc clears it."""

    def __init__(self):
        super().__init__()
        self.setPlaceholderText("Search")
        pal = self.palette()
        pal.setColor(QPalette.PlaceholderText, QColor(GRIGIO))
        self.setPalette(pal)
        self.addAction(lens_icon(), QLineEdit.LeadingPosition)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.clear()
        else:
            super().keyPressEvent(e)


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    return s


def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def load_meta():
    try:
        with open(META_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_meta(meta):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)


def list_roms(rom_dir):
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


def allow_flatpak(path):
    """Let the Flatpak MAME see a folder outside its sandbox."""
    if MAME_CMD[0] != "flatpak":
        return
    try:
        subprocess.run(["flatpak", "override", "--user", "--filesystem=" + path,
                        MAME_CMD[-1]], capture_output=True, timeout=30)
    except Exception:
        pass


def fetch_meta(names):
    """Ask MAME for info on the given zip names only."""
    out = {}
    if not names:
        return out
    try:
        res = subprocess.run(MAME_CMD + ["-listxml"] + names, capture_output=True,
                             text=True, timeout=300)
        root = ET.fromstring(res.stdout)
    except Exception:
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


def thumb_name(desc):
    for ch in '&*/:`<>?\\|"':
        desc = desc.replace(ch, "_")
    return desc


def img_path(name):
    return os.path.join(IMG_DIR, name + ".png")


def download_image(name, desc):
    """Download first available image; leave .none marker if missing."""
    path = img_path(name)
    if os.path.exists(path) or os.path.exists(path + ".none"):
        return
    fname = urllib.parse.quote(thumb_name(desc)) + ".png"
    for kind in IMG_KINDS:
        try:
            with urllib.request.urlopen(BASE_URL + kind + "/" + fname, timeout=15) as r:
                data = r.read()
            with open(path, "wb") as f:
                f.write(data)
            return
        except urllib.error.HTTPError as e:
            if e.code != 404:
                return  # network problem: retry next time
        except Exception:
            return
    open(path + ".none", "w").close()


class Worker(QThread):
    meta_ready = Signal(dict)
    image_ready = Signal(str)
    progress = Signal(int, int)
    covers_done = Signal(int)
    size_ready = Signal(float)

    def __init__(self, roms, rom_dir):
        super().__init__()
        self.roms = roms
        self.rom_dir = rom_dir
        self.priority = []

    def run(self):
        if self.rom_dir and os.path.isdir(self.rom_dir):
            self.size_ready.emit(float(folder_size(self.rom_dir)))
        meta = load_meta()
        missing = [r for r in self.roms if r not in meta]
        if missing:
            meta.update(fetch_meta(missing))
            save_meta(meta)
        if self.isInterruptionRequested():
            return
        self.meta_ready.emit(meta)

        def need(r):
            return not os.path.exists(img_path(r)) and not os.path.exists(img_path(r) + ".none")

        games = [r for r in self.roms if r in meta and not meta[r]["bios"]]
        total = sum(1 for r in games if need(r))
        done = got = 0
        if total:
            self.progress.emit(0, total)
        for r in games:
            if self.isInterruptionRequested():
                return
            wanted = need(r)
            download_image(r, meta[r]["desc"])
            if wanted:
                done += 1
                got += os.path.exists(img_path(r))
                self.progress.emit(done, total)
            self.image_ready.emit(r)
        if total:
            self.covers_done.emit(got)


class Launcher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MAME Launcher")
        self.resize(1000, 620)
        self.meta = {}
        self.settings = load_settings()
        self.roms = list_roms(self.settings["rom_dir"])
        self.bios_dir_names = set(list_roms(self.settings["bios_dir"]))
        self.rom_size = 0
        self.workers = []

        self.search = SearchBox()
        self.search.textChanged.connect(self.fill_list)
        self.list = QListWidget()
        self.list.setIconSize(QSize(DOT, DOT))
        self.list.setItemDelegate(GameDelegate(self.list))
        self.colors = {}
        self.items = {}
        self.list.currentItemChanged.connect(self.show_game)
        self.list.itemActivated.connect(lambda _i: self.launch())

        left = QVBoxLayout()
        left.setContentsMargins(10, 10, 10, 10)
        left.addWidget(self.search)
        left.addWidget(self.list)
        side = QWidget()
        side.setObjectName("side")
        side.setLayout(left)

        self.cover = QLabel("Loading...")
        self.cover.setAlignment(Qt.AlignCenter)
        self.cover.setMinimumSize(400, 300)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.info.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.btn = QPushButton("Play")
        self.btn.clicked.connect(self.launch)

        right = QVBoxLayout()
        right.setContentsMargins(14, 10, 14, 10)
        right.addWidget(self.cover, 3)
        right.addWidget(self.info, 1)
        right.addWidget(self.btn)

        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(side, 1)
        body.addLayout(right, 2)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setMenuBar(self.build_menu())
        lay.setSpacing(0)
        lay.addLayout(body)

        status = QWidget()
        status.setObjectName("status")
        status.setFixedHeight(26)
        sl = QHBoxLayout(status)
        sl.setContentsMargins(12, 0, 12, 0)
        self.count_lbl = QLabel("Loading...")
        self.prog_lbl = QLabel("")
        sl.addWidget(self.count_lbl)
        sl.addSpacing(18)
        sl.addWidget(self.prog_lbl)
        sl.addStretch(1)
        sl.addWidget(QLabel("\u00a9 %s %s \u00b7 MIT license" % (YEAR, AUTHOR)))
        lay.addWidget(status)

        self.setStyleSheet(STYLE)
        self.start_worker()
        if not self.settings["rom_dir"]:
            self.cover.setText("No ROM folder set")
            QTimer.singleShot(0, self.first_run)

    def start_worker(self):
        for w in self.workers:
            w.requestInterruption()
            for sig in (w.meta_ready, w.image_ready, w.progress, w.covers_done, w.size_ready):
                try:
                    sig.disconnect()
                except Exception:
                    pass
        self.prog_lbl.setText("")
        w = Worker(self.roms, self.settings["rom_dir"])
        w.meta_ready.connect(self.on_meta)
        w.image_ready.connect(self.on_image)
        w.progress.connect(lambda d, t: self.prog_lbl.setText(
            "downloading covers... %d/%d" % (d, t)))
        w.covers_done.connect(lambda n: self.prog_lbl.setText(
            "%d covers downloaded" % n if n else ""))
        w.size_ready.connect(self.on_size)
        self.workers.append(w)
        w.start()

    def first_run(self):
        QMessageBox.information(self, "MAME Launcher",
                                "First run: choose the folder with your ROMs, "
                                "then the folder with your BIOS files.")
        if self.set_folder("rom_dir"):
            self.set_folder("bios_dir")     # Cancel to skip

    def set_folder(self, key):
        title = "Select ROM folder" if key == "rom_dir" else "Select BIOS folder"
        start = self.settings[key] or (MAME_HOME if os.path.isdir(MAME_HOME)
                                       else os.path.expanduser("~"))
        d = QFileDialog.getExistingDirectory(self, title, start)
        if not d:
            return False
        self.settings[key] = d
        save_settings(self.settings)
        allow_flatpak(d)
        if key == "rom_dir":
            self.reload_roms()
        else:
            self.bios_dir_names = set(list_roms(d))
            self.update_status()
        return True

    def reload_roms(self):
        self.roms = list_roms(self.settings["rom_dir"])
        self.meta = {}
        self.colors = {}
        self.items = {}
        self.rom_size = 0
        self.list.clear()
        self.info.setText("")
        self.cover.setPixmap(QPixmap())
        self.cover.setText("Loading..." if self.roms else "No ROMs found")
        self.start_worker()

    def build_menu(self):
        bar = QMenuBar()
        file_menu = bar.addMenu("File")
        a_open = QAction("Open Folder", self)
        a_open.triggered.connect(self.open_folder)
        file_menu.addAction(a_open)
        file_menu.addSeparator()
        a_quit = QAction("Quit", self)
        a_quit.triggered.connect(self.close)
        file_menu.addAction(a_quit)

        sett = bar.addMenu("Settings")
        a_rom = QAction("ROM folder...", self)
        a_rom.triggered.connect(lambda: self.set_folder("rom_dir"))
        sett.addAction(a_rom)
        a_bios = QAction("BIOS folder...", self)
        a_bios.triggered.connect(lambda: self.set_folder("bios_dir"))
        sett.addAction(a_bios)
        sett.addSeparator()
        disp = sett.addMenu("Display mode")
        grp = QActionGroup(self)
        grp.setExclusive(True)
        for label, fs in (("Window", False), ("Full screen", True)):
            a = QAction(label, self, checkable=True)
            a.setChecked(self.settings["fullscreen"] == fs)
            a.triggered.connect(lambda _c, v=fs: self.set_fullscreen(v))
            grp.addAction(a)
            disp.addAction(a)
        return bar

    def open_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(MAME_HOME))

    def set_fullscreen(self, value):
        self.settings["fullscreen"] = value
        save_settings(self.settings)

    def on_meta(self, meta):
        self.meta = meta
        self.fill_list()

    def fill_list(self):
        q = self.search.text().lower()
        self.list.clear()
        self.items = {}
        items = []
        for r in self.roms:
            m = self.meta.get(r)
            if not m or m["bios"]:
                continue
            hay = " ".join((m["desc"], r, m["year"], m["maker"], m["clone"])).lower()
            if q and not all(t in hay for t in q.split()):
                continue
            items.append((m["desc"], r))
        for desc, r in sorted(items, key=lambda x: x[0].lower()):
            it = QListWidgetItem(desc)
            it.setData(Qt.UserRole, r)
            c = self.dot_color(r)
            it.setIcon(make_dot(c))
            it.setData(Qt.UserRole + 1, sub_text(self.meta[r]))
            it.setData(Qt.UserRole + 2, c)
            self.items[r] = it
            self.list.addItem(it)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.update_status()

    def update_status(self):
        total = sum(1 for r in self.roms if r in self.meta and not self.meta[r]["bios"])
        shown = self.list.count()
        parts = ["%d of %d games" % (shown, total) if shown != total
                 else "%d games" % total]
        names = self.bios_dir_names | {r for r in self.roms
                                       if r in self.meta and self.meta[r]["bios"]}
        parts.append("%d BIOS" % len(names))
        if self.rom_size:
            parts.append(fmt_size(self.rom_size))
        self.count_lbl.setText(" \u00b7 ".join(parts))

    def on_size(self, n):
        self.rom_size = n
        self.update_status()

    def dot_color(self, name):
        if name not in self.colors:
            p = img_path(name)
            c = color_from_image(p) if os.path.exists(p) else None
            self.colors[name] = c or color_from_name(name)
        return self.colors[name]

    def current_name(self):
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def show_game(self, *_):
        name = self.current_name()
        if not name:
            return
        m = self.meta[name]
        rows = [("Year", m["year"]), ("Maker", m["maker"]), ("ROM", name + ".zip")]
        if m["clone"]:
            rows.append(("Clone of", m["clone"]))
        txt = "<b>%s</b>" % html.escape(m["desc"])
        for k, v in rows:
            txt += "<br><span style='color:%s'>%s:</span> %s" % (
                LABEL_COLORS[k], k, html.escape(v))
        self.info.setText(txt)
        self.set_cover(name)

    def set_cover(self, name):
        p = img_path(name)
        if os.path.exists(p):
            pm = QPixmap(p)
            self.cover.setPixmap(pm.scaled(self.cover.size(), Qt.KeepAspectRatio,
                                           Qt.SmoothTransformation))
        elif os.path.exists(p + ".none"):
            self.cover.setPixmap(QPixmap())
            self.cover.setText("No image")
        else:
            self.cover.setPixmap(QPixmap())
            self.cover.setText("Downloading...")

    def on_image(self, name):
        self.colors.pop(name, None)
        if name in self.items:
            c = self.dot_color(name)
            self.items[name].setIcon(make_dot(c))
            self.items[name].setData(Qt.UserRole + 2, c)
        if name == self.current_name():
            self.set_cover(name)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        n = self.current_name()
        if n:
            self.set_cover(n)

    def launch(self):
        name = self.current_name()
        if name and self.settings["rom_dir"]:
            mode = "-nowindow" if self.settings["fullscreen"] else "-window"
            rompath = ";".join(d for d in (self.settings["rom_dir"],
                                           self.settings["bios_dir"]) if d)
            subprocess.Popen(MAME_CMD + ["-rompath", rompath, mode, name])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Launcher()
    w.show()
    sys.exit(app.exec())
