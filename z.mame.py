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
                           QPainter, QPalette, QPen, QPixmap, QKeySequence)
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QSplitter, QStyle, QStyledItemDelegate,
                               QListWidget, QListWidgetItem, QMenuBar,
                               QPushButton, QVBoxLayout, QWidget)

CONFIG_DIR = os.path.expanduser("~/.config/mame_launcher")
IMG_DIR = os.path.join(CONFIG_DIR, "img")
META_FILE = os.path.join(CONFIG_DIR, "meta.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
BASE_URL = "https://raw.githubusercontent.com/libretro-thumbnails/MAME/master/"
IMG_KINDS = ["Named_Boxarts", "Named_Titles", "Named_Snaps"]

MAME_CMD = ["flatpak", "run", "org.mamedev.MAME"]
MAME_HOME = os.path.expanduser("~/mame")
DEFAULT_SETTINGS = {"fullscreen": False, "rom_dir": "", "bios_dir": "", "favorites": []}

os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

PALETTE = ("#ff5257", "#ff9f0a", "#ffd60a", "#30d158", "#0a84ff",
           "#bf5af2", "#ff375f", "#64d2ff")
DOT = 24
SCALA_FILE = ("#ff5257", "#30d158", "#ff7f11", "#42a0ff",
              "#ffd60a", "#bf5af2", "#ff6fae", "#64d2ff",
              "#c19272", "#66e3b0", "#d4af37", "#9190f9",
              "#e23179", "#b4e04a", "#ff9670", "#c0c7d0")


def color_from_name(name):
    n = int(hashlib.md5(name.encode("utf-8")).hexdigest()[:8], 16)
    return PALETTE[n % len(PALETTE)]


def get_contrast_color(hex_color):
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminance > 0.5 else "#ffffff"


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


AUTHOR, YEAR = "Jonathan Sanfilippo", "2026"
STATO = "#0c0c0c"
FONDO, PANNELLO, CERCA = "#121212", "#131215", "#252428"
TASTO, SCELTO, TESTO, GRIGIO = "#2c2c2c", "#3a3a3a", "#e0e0e0", "#9e9e9e"
IN_ONDA = "#3b2f4f"

STYLE = f"""
QWidget {{ background: {FONDO}; color: {TESTO}; }}
QLabel {{ background: transparent; }}
QWidget#side, QWidget#folders {{ background: {PANNELLO}; }}
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
QSplitter::handle {{ background: {SCELTO}; }}
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


ROW_H = 44
LABEL_COLORS = {"Year": "#0a84ff", "Maker": "#30d158",
                "ROM": "#ff9f0a", "Clone of": "#bf5af2"}


def sub_text(m):
    parts = [m.get("year", "?"), m.get("maker", "?")]
    return " \u00b7 ".join(x for x in parts if x and x != "?")


class GameDelegate(QStyledItemDelegate):
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
    if MAME_CMD[0] != "flatpak":
        return
    try:
        subprocess.run(["flatpak", "override", "--user", "--filesystem=" + path,
                        MAME_CMD[-1]], capture_output=True, timeout=30)
    except Exception:
        pass


def fetch_meta_chunk(names):
    out = {}
    if not names:
        return out
    try:
        res = subprocess.run(MAME_CMD + ["-listxml"] + names, capture_output=True,
                             text=True, timeout=60)
        root = ET.fromstring(res.stdout)
        for m in root.iter("machine"):
            out[m.get("name")] = {
                "desc": (m.findtext("description") or m.get("name")),
                "year": m.findtext("year") or "?",
                "maker": m.findtext("manufacturer") or "?",
                "clone": m.get("cloneof") or "",
                "bios": m.get("isbios") == "yes" or m.get("isdevice") == "yes",
            }
    except Exception:
        pass
    return out


def thumb_name(desc):
    for ch in '&*/:`<>?\\|"':
        desc = desc.replace(ch, "_")
    return desc


def img_path(name):
    return os.path.join(IMG_DIR, name + ".png")


def download_image(name, desc):
    path = img_path(name)
    if os.path.exists(path) or os.path.exists(path + ".none"):
        return
    fname = urllib.parse.quote(thumb_name(desc)) + ".png"
    for kind in IMG_KINDS:
        try:
            with urllib.request.urlopen(BASE_URL + kind + "/" + fname, timeout=10) as r:
                data = r.read()
            with open(path, "wb") as f:
                f.write(data)
            return
        except Exception:
            continue
    open(path + ".none", "w").close()


class Worker(QThread):
    meta_ready = Signal(dict)
    image_ready = Signal(str)
    progress = Signal(int, int, str)
    covers_done = Signal(int)
    size_ready = Signal(float)

    def __init__(self, roms, rom_dir, force_scrape=False):
        super().__init__()
        self.roms = roms
        self.rom_dir = rom_dir
        self.force_scrape = force_scrape

    def run(self):
        if self.rom_dir and os.path.isdir(self.rom_dir):
            self.size_ready.emit(float(folder_size(self.rom_dir)))
        
        meta = load_meta()
        missing = [r for r in self.roms if r not in meta or self.force_scrape]
        if self.force_scrape:
            missing = self.roms

        if missing:
            chunk_size = 100
            total_missing = len(missing)
            for i in range(0, total_missing, chunk_size):
                if self.isInterruptionRequested():
                    return
                chunk = missing[i:i + chunk_size]
                self.progress.emit(i, total_missing, "Caricamento metadati...")
                partial = fetch_meta_chunk(chunk)
                for r in chunk:
                    if r not in partial:
                        partial[r] = {"desc": r, "year": "?", "maker": "?", "clone": "", "bios": False}
                meta.update(partial)
                save_meta(meta)
                self.meta_ready.emit(meta)

        if self.isInterruptionRequested():
            return

        def need(r):
            if self.force_scrape:
                return True
            return not os.path.exists(img_path(r)) and not os.path.exists(img_path(r) + ".none")

        games = [r for r in self.roms if r in meta and not meta[r].get("bios", False)]
        total_img = sum(1 for r in games if need(r))
        done = got = 0
        if total_img:
            self.progress.emit(0, total_img, "Download copertine...")
        
        for r in games:
            if self.isInterruptionRequested():
                return
            wanted = need(r)
            desc = meta[r].get("desc", r)
            if wanted:
                download_image(r, desc)
                done += 1
                got += os.path.exists(img_path(r))
                self.progress.emit(done, total_img, "Download copertine...")
            self.image_ready.emit(r)
            
        if total_img:
            self.covers_done.emit(got)


class MameRunnerThread(QThread):
    finished = Signal()

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    def run(self):
        try:
            p = subprocess.Popen(self.cmd)
            p.wait()
        except Exception:
            pass
        self.finished.emit()


class Launcher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MAME Launcher")
        self.resize(1100, 620)
        
        self.meta = load_meta()
        self.settings = load_settings()
        self.roms = []
        self.bios_dir_names = set()
        self.rom_size = 0
        self.workers = []
        self.all_item_cache = {}
        self.mame_thread = None

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(120)
        self.search_timer.timeout.connect(self.fill_list)

        self.search = SearchBox()
        self.search.textChanged.connect(self.on_search_changed)
        
        self.list = QListWidget()
        self.list.setIconSize(QSize(DOT, DOT))
        self.list.setItemDelegate(GameDelegate(self.list))
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

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

        self.cover = QLabel("Caricamento...")
        self.cover.setAlignment(Qt.AlignCenter)
        self.cover.setMinimumSize(400, 300)

        self.info = QLabel("Caricamento in corso...")
        self.info.setWordWrap(True)
        self.info.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        self.btn = QPushButton("Play")
        self.btn.clicked.connect(self.launch)
        
        self.fav_btn = QPushButton("Preferito")
        self.fav_btn.clicked.connect(self.toggle_favorite)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn, 3)
        btn_layout.addWidget(self.fav_btn, 1)

        center_layout = QVBoxLayout()
        center_layout.setContentsMargins(14, 10, 14, 10)
        center_layout.addWidget(self.cover, 3)
        center_layout.addWidget(self.info, 1)
        center_layout.addLayout(btn_layout)
        
        center_container = QWidget()
        center_container.setLayout(center_layout)

        self.folders_list = QListWidget()
        self.folders_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.folders_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        f_all = QListWidgetItem("Tutti i giochi")
        f_fav = QListWidgetItem("Preferiti")
        self.folders_list.addItem(f_all)
        self.folders_list.addItem(f_fav)
        self.folders_list.setCurrentItem(f_all)
        self.folders_list.currentItemChanged.connect(lambda *_: self.fill_list())

        folders_layout = QVBoxLayout()
        folders_layout.setContentsMargins(10, 10, 10, 10)
        folders_layout.addWidget(QLabel("<b>Libreria</b>"))
        folders_layout.addWidget(self.folders_list)
        folders_widget = QWidget()
        folders_widget.setObjectName("folders")
        folders_widget.setLayout(folders_layout)

        splitter_main = QSplitter(Qt.Horizontal)
        splitter_main.addWidget(side)
        splitter_main.addWidget(center_container)
        splitter_main.addWidget(folders_widget)
        splitter_main.setSizes([300, 500, 300])

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(splitter_main)

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
        self.count_lbl = QLabel("Inizializzazione...")
        self.prog_lbl = QLabel("Caricamento...")
        sl.addWidget(self.count_lbl)
        sl.addSpacing(18)
        sl.addWidget(self.prog_lbl)
        sl.addStretch(1)
        sl.addWidget(QLabel("\u00a9 %s %s \u00b7 MIT license" % (YEAR, AUTHOR)))
        lay.addWidget(status)

        self.setStyleSheet(STYLE)
        
        QTimer.singleShot(50, self.deferred_init)

    def deferred_init(self):
        self.prog_lbl.setText("Scansione cartella ROM...")
        QApplication.processEvents()

        self.roms = list_roms(self.settings["rom_dir"])
        if self.settings["bios_dir"]:
            self.bios_dir_names = set(list_roms(self.settings["bios_dir"]))
        
        self.prog_lbl.setText("Indicizzazione giochi...")
        QApplication.processEvents()

        self.build_item_cache()
        self.fill_list()
        
        self.prog_lbl.setText("Avvio servizi...")
        self.start_worker(force_scrape=False)

        if not self.settings["rom_dir"]:
            self.cover.setText("No ROM folder set")
            self.info.setText("Seleziona una cartella ROM per iniziare.")
            self.first_run()

    def game_color(self, name):
        i = getattr(self, "color_slot", {}).get(name)
        return SCALA_FILE[i % len(SCALA_FILE)] if i is not None else color_from_name(name)

    def build_item_cache(self):
        self.all_item_cache = {}
        games = [r for r in self.roms if not self.meta.get(r, {}).get("bios", False)]
        games.sort(key=lambda r: (self.meta.get(r, {}).get("desc", r)).lower())
        self.color_slot = {r: i for i, r in enumerate(games)}
        for r in self.roms:
            m = self.meta.get(r)
            desc = m["desc"] if m else r
            it = QListWidgetItem(desc)
            it.setData(Qt.UserRole, r)
            c = self.game_color(r)
            it.setIcon(make_dot(c))
            m_info = self.meta.get(r, {})
            it.setData(Qt.UserRole + 1, sub_text(m_info))
            it.setData(Qt.UserRole + 2, c)
            self.all_item_cache[r] = it

    def start_worker(self, force_scrape=False):
        for w in self.workers:
            w.requestInterruption()
            for sig in (w.meta_ready, w.image_ready, w.progress, w.covers_done, w.size_ready):
                try:
                    sig.disconnect()
                except Exception:
                    pass
        w = Worker(self.roms, self.settings["rom_dir"], force_scrape=force_scrape)
        w.meta_ready.connect(self.on_meta)
        w.image_ready.connect(self.on_image)
        w.progress.connect(lambda d, t, msg: self.prog_lbl.setText(
            "%s %d/%d" % (msg, d, t) if t else msg))
        w.covers_done.connect(lambda n: self.prog_lbl.setText(
            "Copertine scaricate: %d" % n if n else ""))
        w.size_ready.connect(self.on_size)
        self.workers.append(w)
        w.start()

    def first_run(self):
        QMessageBox.information(self, "MAME Launcher",
                                "Primo avvio: seleziona la cartella delle ROM, "
                                "poi quella dei file BIOS.")
        if self.set_folder("rom_dir"):
            self.set_folder("bios_dir")

    def set_folder(self, key):
        title = "Seleziona cartella ROM" if key == "rom_dir" else "Seleziona cartella BIOS"
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

    def reload_roms(self, force_scrape=False):
        self.prog_lbl.setText("Aggiornamento ROM...")
        self.roms = list_roms(self.settings["rom_dir"])
        self.build_item_cache()
        self.fill_list()
        self.start_worker(force_scrape=force_scrape)

    def manual_scrape(self):
        if not self.settings["rom_dir"] or not self.roms:
            QMessageBox.warning(self, "Scraping", "Seleziona prima una cartella ROM valida.")
            return
        res = QMessageBox.question(
            self, "Scraping Manuale", 
            "Vuoi forzare il ricaricamento completo di metadati e copertine?",
            QMessageBox.Yes | QMessageBox.No
        )
        if res == QMessageBox.Yes:
            self.reload_roms(force_scrape=True)

    def build_menu(self):
        bar = QMenuBar()
        file_menu = bar.addMenu("File")
        
        a_refresh = QAction("Aggiorna ROM", self)
        a_refresh.setShortcut(QKeySequence.Refresh)
        a_refresh.triggered.connect(lambda: self.reload_roms(force_scrape=False))
        file_menu.addAction(a_refresh)

        a_scrape = QAction("Scraping Manuale (Cover e Dati)", self)
        a_scrape.triggered.connect(self.manual_scrape)
        file_menu.addAction(a_scrape)

        file_menu.addSeparator()
        a_open = QAction("Apri cartella MAME", self)
        a_open.triggered.connect(self.open_folder)
        file_menu.addAction(a_open)
        file_menu.addSeparator()
        a_quit = QAction("Esci", self)
        a_quit.triggered.connect(self.close)
        file_menu.addAction(a_quit)

        sett = bar.addMenu("Impostazioni")
        a_rom = QAction("Cartella ROM...", self)
        a_rom.triggered.connect(lambda: self.set_folder("rom_dir"))
        sett.addAction(a_rom)
        a_bios = QAction("Cartella BIOS...", self)
        a_bios.triggered.connect(lambda: self.set_folder("bios_dir"))
        sett.addAction(a_bios)
        sett.addSeparator()
        disp = sett.addMenu("Modalità schermo")
        grp = QActionGroup(self)
        grp.setExclusive(True)
        for label, fs in (("Finestra", False), ("Schermo intero", True)):
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
        self.build_item_cache()
        self.fill_list()

    def toggle_favorite(self):
        name = self.current_name()
        if not name:
            return
        favs = self.settings.setdefault("favorites", [])
        if name in favs:
            favs.remove(name)
        else:
            favs.append(name)
        save_settings(self.settings)
        self.update_favorite_button(name)
        if self.folders_list.currentItem() and self.folders_list.currentItem().text() == "Preferiti":
            self.fill_list()

    def update_favorite_button(self, name):
        favs = self.settings.get("favorites", [])
        if name in favs:
            self.fav_btn.setText("★ Preferito")
        else:
            self.fav_btn.setText("☆ Preferito")

    def update_play_button_color(self, name):
        if not name:
            self.btn.setStyleSheet("")
            return
        c = self.game_color(name)
        text_color = get_contrast_color(c)
        self.btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c};
                color: {text_color};
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {c};
            }}
        """)

    def on_search_changed(self):
        self.search_timer.start()

    def fill_list(self):
        q = self.search.text().lower()
        curr_folder = self.folders_list.currentItem().text() if self.folders_list.currentItem() else "Tutti i giochi"
        favs = set(self.settings.get("favorites", []))

        self.list.setUpdatesEnabled(False)
        self.list.blockSignals(True)
        for i in range(self.list.count() - 1, -1, -1):
            self.list.takeItem(i)
        self.items = {}

        if not self.all_item_cache and self.roms:
            self.build_item_cache()

        filtered = []
        q_tokens = q.split() if q else []

        for r in self.roms:
            if curr_folder == "Preferiti" and r not in favs:
                continue

            m = self.meta.get(r)
            if m and m.get("bios", False):
                continue

            if q_tokens:
                desc = m["desc"] if m else r
                year = m.get("year", "?") if m else "?"
                maker = m.get("maker", "?") if m else "?"
                clone = m.get("clone", "") if m else ""
                hay = " ".join((desc, r, year, maker, clone)).lower()
                if not all(t in hay for t in q_tokens):
                    continue
            filtered.append(r)

        filtered.sort(key=lambda r: (self.meta.get(r, {}).get("desc", r)).lower())

        for r in filtered:
            it = self.all_item_cache.get(r)
            if it:
                self.items[r] = it
                self.list.addItem(it)

        self.list.blockSignals(False)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.show_game()

        self.list.setUpdatesEnabled(True)
        self.update_status()

    def update_status(self):
        total = len(self.roms)
        shown = self.list.count()
        parts = ["%d di %d giochi" % (shown, total) if shown != total
                 else "%d giochi" % total]
        names = self.bios_dir_names | {r for r in self.roms
                                       if r in self.meta and self.meta[r].get("bios", False)}
        parts.append("%d BIOS" % len(names))
        if self.rom_size:
            parts.append(fmt_size(self.rom_size))
        self.count_lbl.setText(" \u00b7 ".join(parts))

    def on_size(self, n):
        self.rom_size = n
        self.update_status()

    def current_name(self):
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def show_game(self, *_):
        name = self.current_name()
        if not name:
            self.update_play_button_color(None)
            return
        m = self.meta.get(name, {"desc": name, "year": "?", "maker": "?", "clone": ""})
        rows = [("Year", m.get("year", "?")), ("Maker", m.get("maker", "?")), ("ROM", name + ".zip")]
        if m.get("clone"):
            rows.append(("Clone of", m["clone"]))
        txt = "<b>%s</b>" % html.escape(m.get("desc", name))
        for k, v in rows:
            txt += "<br><span style='color:%s'>%s:</span> %s" % (
                LABEL_COLORS.get(k, "#ffffff"), k, html.escape(v))
        self.info.setText(txt)
        self.set_cover(name)
        self.update_favorite_button(name)
        self.update_play_button_color(name)

    def set_cover(self, name):
        p = img_path(name)
        if os.path.exists(p):
            pm = QPixmap(p)
            self.cover.setPixmap(pm.scaled(self.cover.size(), Qt.KeepAspectRatio,
                                           Qt.SmoothTransformation))
        elif os.path.exists(p + ".none"):
            self.cover.setPixmap(QPixmap())
            self.cover.setText("Nessuna immagine")
        else:
            self.cover.setPixmap(QPixmap())
            self.cover.setText("Caricamento copertina...")

    def on_image(self, name):
        if name in self.all_item_cache:
            c = self.game_color(name)
            self.all_item_cache[name].setIcon(make_dot(c))
            self.all_item_cache[name].setData(Qt.UserRole + 2, c)
        if name == self.current_name():
            self.set_cover(name)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        name = self.current_name()
        if name:
            self.set_cover(name)

    def on_mame_closed(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def launch(self, *_):
        name = self.current_name()
        if not name and self.roms:
            name = self.roms[0]
            
        if name and self.settings["rom_dir"]:
            rompath = ";".join(d for d in (self.settings["rom_dir"],
                                           self.settings["bios_dir"]) if d)
            
            cmd = MAME_CMD + [
                "-rompath", rompath,
                "-window",
                "-nomax",
                "-resolution", "1100x620",
                name
            ]
            
            self.hide()
            
            self.mame_thread = MameRunnerThread(cmd)
            self.mame_thread.finished.connect(self.on_mame_closed)
            self.mame_thread.start()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Launcher()
    w.show()
    app.processEvents()
    sys.exit(app.exec())
