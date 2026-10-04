import hashlib
import html
import json
import os
import re
import subprocess
import sys
import urllib.parse
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
STATUS_FILE = os.path.join(CONFIG_DIR, "status_cache.json")
PROGRESS_FILE = os.path.join(CONFIG_DIR, "worker_progress.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
LOCK_FILE = os.path.join(CONFIG_DIR, "worker.lock")
MAME_CMD = ["flatpak", "run", "org.mamedev.MAME"]
MAME_HOME = os.path.expanduser("~/mame")
DEFAULT_SETTINGS = {"fullscreen": False, "rom_dir": "", "bios_dir": "", "favorites": [], "language": "en"}

os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

DOT = 24
STATUS_COLORS = {"buono": "#30d158", "imperfetto": "#ff9f0a", "inavviabile": "#ff5257"}

COLOR_GAMES = "#64d2ff"  # Azzurro per i giochi
COLOR_BIOS = "#bf5af2"   # Viola per i BIOS
COLOR_WORKER_LABEL = "#ffd60a" # Giallo per la scritta "Worker:"

AUTHOR, YEAR = "Jonathan Sanfilippo", "2026"
STATO = "#0c0c0c"
FONDO, PANNELLO, CERCA = "#121212", "#131215", "#252428"
TASTO, SCELTO, TESTO, GRIGIO = "#2c2c2c", "#3a3a3a", "#e0e0e0", "#9e9e9e"
IN_ONDA = "#3b2f4f"

FALLBACK_MAKER_COLORS = ("#30d158", "#bf5af2", "#ff6fae", "#64d2ff", "#ffd60a", "#a0724a")
DEFAULT_MAKER_COLOR = "#8a94a6"

LANGS = {
    "en": {
        "search_placeholder": "Search",
        "play": "Play",
        "favorite": "Favorite",
        "library": "Library",
        "all_games": "All games",
        "favorites": "Favorites",
        "status_good": "Good",
        "status_imperfect": "Imperfect",
        "status_nonrunnable": "Non-runnable",
        "worker_inactive": "Background worker inactive",
        "worker_starting": "starting...",
        "worker_idle": "inactive or completed",
        "ready": "Ready",
        "no_rom_folder": "No ROM folder set",
        "select_rom_start": "Select a ROM folder to start.",
        "first_run_title": "MAME Launcher",
        "first_run_msg": "First run: select the ROM folder, then the BIOS folder.",
        "menu_file": "File",
        "menu_refresh": "Refresh ROMs",
        "menu_open_mame": "Open MAME folder",
        "menu_quit": "Quit",
        "menu_settings": "Settings",
        "menu_rom_folder": "ROM folder...",
        "menu_bios_folder": "BIOS folder...",
        "menu_display_mode": "Display mode",
        "menu_window": "Windowed",
        "menu_fullscreen": "Fullscreen",
        "menu_language": "Language",
        "games_count": "games",
        "bios_count": "BIOS",
        "no_images": "No image",
        "loading_bg": "Loading in background...",
        "loading": "Loading...",
        "ready_to_play": "Ready to play...",
        "year": "Year",
        "maker": "Maker",
        "rom": "ROM",
        "clone_of": "Clone of"
    },
    "it": {
        "search_placeholder": "Cerca",
        "play": "Avvia",
        "favorite": "Preferito",
        "library": "Libreria",
        "all_games": "Tutti i giochi",
        "favorites": "Preferiti",
        "status_good": "Buono",
        "status_imperfect": "Imperfetto",
        "status_nonrunnable": "Inavviabile",
        "worker_inactive": "Background worker inattivo",
        "worker_starting": "avvio in corso...",
        "worker_idle": "inattivo o completato",
        "ready": "Pronto",
        "no_rom_folder": "Nessuna cartella ROM impostata",
        "select_rom_start": "Seleziona una cartella ROM per iniziare.",
        "first_run_title": "MAME Launcher",
        "first_run_msg": "Primo avvio: seleziona la cartella delle ROM, poi quella dei file BIOS.",
        "menu_file": "File",
        "menu_refresh": "Aggiorna ROM",
        "menu_open_mame": "Apri cartella MAME",
        "menu_quit": "Esci",
        "menu_settings": "Impostazioni",
        "menu_rom_folder": "Cartella ROM...",
        "menu_bios_folder": "Cartella BIOS...",
        "menu_display_mode": "Modalità schermo",
        "menu_window": "Finestra",
        "menu_fullscreen": "Schermo intero",
        "menu_language": "Lingua",
        "games_count": "giochi",
        "bios_count": "BIOS",
        "no_images": "Nessuna immagine",
        "loading_bg": "Caricamento in background...",
        "loading": "Caricamento...",
        "ready_to_play": "Pronto per giocare...",
        "year": "Anno",
        "maker": "Produttore",
        "rom": "ROM",
        "clone_of": "Clone di"
    }
}

_MAKER_TABLE = [
    (("acclaim", "ljn"), "#30d158"),
    (("american laser games",), "#bf5af2"),
    (("arcadia systems", "arcadia"), "#ff6fae"),
    (("aristocrat",), "#ff6b6b"),
    (("artic",), "#64d2ff"),
    (("atari",), "#ff5a5f"),
    (("atlus",), "#ff453a"),
    (("bandai",), "#ff6a3d"),
    (("bally midway", "bally"), "#ff5c5c"),
    (("banpresto",), "#ffd60a"),
    (("capcom",), "#ffd60a"),
    (("cave",), "#a0724a"),
    (("centuri",), "#30d158"),
    (("cinematronics",), "#bf5af2"),
    (("data east",), "#ff6fae"),
    (("dooyong",), "#64d2ff"),
    (("electronic arts",), "#ff4747"),
    (("eolith",), "#ffd60a"),
    (("esco trading", "amuse"), "#a0724a"),
    (("exelo",), "#30d158"),
    (("face",), "#bf5af2"),
    (("faelg",), "#ff6fae"),
    (("gaelco",), "#ff4d4d"),
    (("game tec", "g.t."), "#64d2ff"),
    (("gottlieb",), "#ffd60a"),
    (("gremlin",), "#a0724a"),
    (("hori",), "#30d158"),
    (("irem",), "#bf5af2"),
    (("jaleco",), "#ff6fae"),
    (("kaneko",), "#64d2ff"),
    (("kiwako",), "#ffd60a"),
    (("konami",), "#ff453a"),
    (("lethal",), "#a0724a"),
    (("lyn",), "#30d158"),
    (("mcr",), "#ff5c5c"),
    (("memtech",), "#bf5af2"),
    (("metamorphic",), "#ff6fae"),
    (("midway",), "#ff5d73"),
    (("mitchell",), "#64d2ff"),
    (("nichibutsu", "nihon bussan"), "#ffd60a"),
    (("nintendo",), "#ff453a"),
    (("nmk",), "#a0724a"),
    (("pacific novelty",), "#30d158"),
    (("psikyo",), "#bf5af2"),
    (("quirex",), "#ff6fae"),
    (("ramtek",), "#64d2ff"),
    (("rck",), "#ffd60a"),
    (("sammy",), "#a0724a"),
    (("sanyo",), "#004ea2"),
    (("seta",), "#30d158"),
    (("sega",), "#0089cf"),
    (("sigma",), "#bf5af2"),
    (("snk",), "#4a90ff"),
    (("sony",), "#003087"),
    (("stern",), "#ff6fae"),
    (("sun electronics", "sunsoft"), "#f39800"),
    (("taito",), "#1a5fa8"),
    (("technos japan", "technos"), "#64d2ff"),
    (("tecmo",), "#ffd60a"),
    (("toaplan",), "#a0724a"),
    (("tuni",), "#30d158"),
    (("universal",), "#bf5af2"),
    (("vap",), "#ff6fae"),
    (("video system",), "#64d2ff"),
    (("visco",), "#ffd60a"),
    (("williams",), "#a0724a"),
    (("zaccaria",), "#30d158"),
    (("namco",), "#30d158"),
]

def get_maker_color(maker_name):
    if not maker_name or maker_name == "?":
        return DEFAULT_MAKER_COLOR
    m_lower = maker_name.lower()
    for keys, color in _MAKER_TABLE:
        for k in keys:
            pattern = r'\b' + re.escape(k) + r'\b'
            if re.search(pattern, m_lower):
                return color
    
    h = int(hashlib.md5(m_lower.encode("utf-8")).hexdigest(), 16)
    return FALLBACK_MAKER_COLORS[h % len(FALLBACK_MAKER_COLORS)]

def get_contrast_color(hex_color):
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
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
    {{ background: {CERCA}; color: #ffffff; }}
QPushButton {{ background: {TASTO}; color: {TESTO}; border: none; border-radius: 6px;
              padding: 8px; }}
QPushButton:hover {{ background: {SCELTO}; }}
QSplitter::handle {{ background: {SCELTO}; }}
QWidget#status {{ background: {STATO}; }}
QWidget#status QLabel {{ color: #ffffff; }}
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

ROW_H = 46

class GameDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(option.rect.width(), ROW_H)

    def paint(self, painter, option, index):
        painter.save()
        r = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        if selected:
            painter.fillRect(r, QColor(CERCA))
            
        icon = index.data(Qt.DecorationRole)
        if isinstance(icon, QIcon):
            icon.paint(painter, QRect(r.left() + 4, r.top() + (r.height() - DOT) // 2, DOT, DOT))
        x = r.left() + DOT + 10
        w = r.width() - DOT - 18
        
        name = painter.fontMetrics().elidedText(index.data(Qt.DisplayRole) or "", Qt.ElideRight, w)
        painter.setPen(QColor("#ffffff" if selected else TESTO))
        painter.drawText(QRect(x, r.top() + 7, w, 16), Qt.AlignLeft | Qt.AlignVCenter, name)
        
        f = painter.font()
        if f.pointSizeF() > 0:
            f.setPointSizeF(max(f.pointSizeF() - 1.5, 7))
            painter.setFont(f)
            
        fm = painter.fontMetrics()
        cur_x = x

        year_str = index.data(Qt.UserRole + 1) or ""
        maker_str = index.data(Qt.UserRole + 3) or ""
        maker_color = index.data(Qt.UserRole + 4) or DEFAULT_MAKER_COLOR

        if year_str:
            painter.setPen(QColor(GRIGIO))
            painter.drawText(QRect(cur_x, r.top() + 25, w, 15), Qt.AlignLeft | Qt.AlignVCenter, year_str)
            cur_x += fm.horizontalAdvance(year_str) + 4

        if year_str and maker_str:
            painter.setPen(QColor(GRIGIO))
            sep = " \u00b7 "
            painter.drawText(QRect(cur_x, r.top() + 25, w, 15), Qt.AlignLeft | Qt.AlignVCenter, sep)
            cur_x += fm.horizontalAdvance(sep) + 2

        if maker_str:
            painter.setPen(QColor(maker_color))
            painter.drawText(QRect(cur_x, r.top() + 25, w, 15), Qt.AlignLeft | Qt.AlignVCenter, maker_str)

        painter.restore()

class SearchBox(QLineEdit):
    def __init__(self, placeholder="Search"):
        super().__init__()
        self.setPlaceholderText(placeholder)
        pal = self.palette()
        pal.setColor(QPalette.PlaceholderText, QColor(GRIGIO))
        self.setPalette(pal)
        self.addAction(lens_icon(), QLineEdit.LeadingPosition)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.clear()
        else:
            super().keyPressEvent(e)

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass

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
        subprocess.run(["flatpak", "override", "--user", "--filesystem=" + path, MAME_CMD[-1]], capture_output=True, timeout=10)
    except Exception:
        pass

def img_path(name):
    return os.path.join(IMG_DIR, name + ".png")

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
        self.resize(1100, 660)
        
        self.settings = dict(DEFAULT_SETTINGS)
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                self.settings.update(json.load(f))
        except Exception:
            pass

        self.start_background_worker()
        
        self.worker_was_active = os.path.exists(LOCK_FILE)

        self.meta = load_json(META_FILE)
        self.status_cache = load_json(STATUS_FILE)
        self.roms = list_roms(self.settings["rom_dir"])
        self.bios_dir_names = set(list_roms(self.settings["bios_dir"])) if self.settings["bios_dir"] else set()
        self.rom_size = 0
        self.all_item_cache = {}
        self.mame_thread = None

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(250)
        self.search_timer.timeout.connect(self.fill_list)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(1500)
        self.poll_timer.timeout.connect(self.poll_background_updates)
        self.poll_timer.start()

        self.search = SearchBox(self.tr("search_placeholder"))
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

        self.cover = QLabel(self.tr("loading"))
        self.cover.setAlignment(Qt.AlignCenter)
        self.cover.setMinimumSize(400, 300)

        self.info = QLabel(self.tr("ready_to_play"))
        self.info.setWordWrap(True)
        self.info.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        self.btn = QPushButton(self.tr("play"))
        self.btn.clicked.connect(self.launch)
        
        self.fav_btn = QPushButton(self.tr("favorite"))
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

        self.library_header_lbl = QLabel()
        self.folders_list = QListWidget()
        self.folders_list.setIconSize(QSize(DOT, DOT))
        self.folders_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.folders_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.folders_list.currentItemChanged.connect(lambda *_: self.fill_list())

        folders_layout = QVBoxLayout()
        folders_layout.setContentsMargins(10, 10, 10, 10)
        folders_layout.addWidget(self.library_header_lbl)
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

        self.menu_bar_widget = self.build_menu()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setMenuBar(self.menu_bar_widget)
        lay.setSpacing(0)
        lay.addLayout(body)

        status = QWidget()
        status.setObjectName("status")
        status.setFixedHeight(26)
        sl = QHBoxLayout(status)
        sl.setContentsMargins(12, 0, 12, 0)
        self.count_lbl = QLabel(self.tr("ready"))
        self.prog_lbl = QLabel(self.tr("worker_inactive"))
        sl.addWidget(self.count_lbl)
        sl.addSpacing(18)
        sl.addWidget(self.prog_lbl)
        sl.addStretch(1)
        self.copy_lbl = QLabel("\u00a9 %s %s \u00b7 MIT license" % (YEAR, AUTHOR))
        self.copy_lbl.setStyleSheet("color: #ffffff;")
        sl.addWidget(self.copy_lbl)
        lay.addWidget(status)

        self.setStyleSheet(STYLE)
        
        self.update_library_header()
        self.build_item_cache()
        self.update_folders_list()
        self.fill_list()

        if not self.settings["rom_dir"]:
            self.cover.setText(self.tr("no_rom_folder"))
            self.info.setText(self.tr("select_rom_start"))
            QTimer.singleShot(100, self.first_run)
        else:
            QTimer.singleShot(200, self.compute_folder_size_async)

    def tr(self, key):
        lang = self.settings.get("language", "en")
        return LANGS.get(lang, LANGS["en"]).get(key, key)

    def set_language(self, lang_code):
        self.settings["language"] = lang_code
        save_settings(self.settings)
        self.retranslate_ui()

    def retranslate_ui(self):
        # Ricostruisci il menu per aggiornare le voci localizzate
        new_bar = self.build_menu()
        self.layout().setMenuBar(new_bar)
        self.menu_bar_widget.deleteLater()
        self.menu_bar_widget = new_bar

        self.search.setPlaceholderText(self.tr("search_placeholder"))
        self.update_library_header()
        self.update_folders_list()
        self.fill_list()
        
        curr = self.current_name()
        if curr:
            self.show_game()
        else:
            if not self.settings["rom_dir"]:
                self.cover.setText(self.tr("no_rom_folder"))
                self.info.setText(self.tr("select_rom_start"))
            else:
                self.cover.setText(self.tr("loading_bg"))
                self.info.setText(self.tr("ready_to_play"))
        self.update_status()

    def update_library_header(self):
        self.library_header_lbl.setText(f"<b>{self.tr('library')}</b>")

    def start_background_worker(self):
        worker_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mame_background_worker.py")
        if os.path.exists(worker_script):
            if os.path.exists(LOCK_FILE):
                return
            try:
                subprocess.Popen([sys.executable, worker_script])
            except Exception:
                pass

    def compute_folder_size_async(self):
        if self.settings["rom_dir"] and os.path.isdir(self.settings["rom_dir"]):
            self.rom_size = folder_size(self.settings["rom_dir"])
            self.update_status()

    def poll_background_updates(self):
        is_locked = os.path.exists(LOCK_FILE)

        prog_data = load_json(PROGRESS_FILE)
        if prog_data:
            task = prog_data.get("task", "Processing...")
            current = prog_data.get("current", 0)
            total = prog_data.get("total", 0)
            if total > 0:
                pct = int((current / total) * 100)
                self.prog_lbl.setText(f"<span style='color:{COLOR_WORKER_LABEL};'>Worker:</span> <span style='color:#ffffff;'>{task} ({current}/{total} - {pct}%)</span>")
            else:
                self.prog_lbl.setText(f"<span style='color:{COLOR_WORKER_LABEL};'>Worker:</span> <span style='color:#ffffff;'>{task}</span>")
        else:
            if is_locked:
                self.prog_lbl.setText(f"<span style='color:{COLOR_WORKER_LABEL};'>Worker:</span> <span style='color:#ffffff;'>{self.tr('worker_starting')}</span>")
            else:
                self.prog_lbl.setText(f"<span style='color:{COLOR_WORKER_LABEL};'>Worker:</span> <span style='color:#ffffff;'>{self.tr('worker_idle')}</span>")

        if self.worker_was_active and not is_locked:
            self.meta = load_json(META_FILE)
            self.status_cache = load_json(STATUS_FILE)
            self.roms = list_roms(self.settings["rom_dir"])
            self.build_item_cache()
            self.update_folders_list()
            self.fill_list()
            curr = self.current_name()
            if curr:
                self.set_cover(curr)
                self.update_play_button_color(curr)

        self.worker_was_active = is_locked

    def game_status_color(self, name):
        st = self.status_cache.get(name, "buono")
        return STATUS_COLORS.get(st, STATUS_COLORS["buono"])

    def build_item_cache(self):
        self.all_item_cache = {}
        games = [r for r in self.roms if not self.meta.get(r, {}).get("bios", False)]
        games.sort(key=lambda r: (self.meta.get(r, {}).get("desc", r)).lower())
        
        for r in self.roms:
            m = self.meta.get(r)
            desc = m["desc"] if m else r
            it = QListWidgetItem(desc)
            it.setData(Qt.UserRole, r)
            
            st = self.status_cache.get(r, "buono")
            c = STATUS_COLORS.get(st, STATUS_COLORS["buono"])
            it.setIcon(make_dot(c))
            
            m_info = self.meta.get(r, {})
            year_val = m_info.get("year", "?")
            maker_val = m_info.get("maker", "?")
            maker_c = get_maker_color(maker_val)

            it.setData(Qt.UserRole + 1, year_val)
            it.setData(Qt.UserRole + 3, maker_val)
            it.setData(Qt.UserRole + 4, maker_c)
            it.setData(Qt.UserRole + 5, st)
            it.setData(Qt.UserRole + 6, c)
            
            self.all_item_cache[r] = it

    def update_folders_list(self):
        curr_item = self.folders_list.currentItem()
        curr_data = curr_item.data(Qt.UserRole) if curr_item else "all"

        self.folders_list.blockSignals(True)
        self.folders_list.clear()

        valid_roms = [r for r in self.roms if not self.meta.get(r, {}).get("bios", False)]
        total_count = len(valid_roms)
        favs = set(self.settings.get("favorites", []))
        fav_count = sum(1 for r in valid_roms if r in favs)

        it_all = QListWidgetItem(f"{self.tr('all_games')}  ({total_count})")
        it_all.setIcon(make_dot(COLOR_GAMES))
        it_all.setData(Qt.UserRole, "all")
        self.folders_list.addItem(it_all)

        it_fav = QListWidgetItem(f"{self.tr('favorites')}  ({fav_count})")
        it_fav.setIcon(make_dot("#bf5af2"))
        it_fav.setData(Qt.UserRole, "favorites")
        self.folders_list.addItem(it_fav)

        status_counts = {"buono": 0, "imperfetto": 0, "inavviabile": 0}
        for r in valid_roms:
            st = self.status_cache.get(r, "buono")
            if st in status_counts:
                status_counts[st] += 1

        status_labels = [
            (self.tr("status_good"), "buono", STATUS_COLORS["buono"]),
            (self.tr("status_imperfect"), "imperfetto", STATUS_COLORS["imperfetto"]),
            (self.tr("status_nonrunnable"), "inavviabile", STATUS_COLORS["inavviabile"])
        ]

        for label, st_key, color in status_labels:
            count = status_counts[st_key]
            it_st = QListWidgetItem(f"{self.tr('status_label')} {label}  ({count})")
            it_st.setIcon(make_dot(color))
            it_st.setData(Qt.UserRole, f"status:{st_key}")
            self.folders_list.addItem(it_st)

        found = False
        for i in range(self.folders_list.count()):
            item = self.folders_list.item(i)
            if item.data(Qt.UserRole) == curr_data:
                self.folders_list.setCurrentItem(item)
                found = True
                break
        if not found and self.folders_list.count() > 0:
            self.folders_list.setCurrentRow(0)

        self.folders_list.blockSignals(False)

    def first_run(self):
        QMessageBox.information(self, self.tr("first_run_title"), self.tr("first_run_msg"))
        if self.set_folder("rom_dir"):
            self.set_folder("bios_dir")

    def set_folder(self, key):
        title = "Select ROM folder" if key == "rom_dir" else "Select BIOS folder"
        start = self.settings[key] or (MAME_HOME if os.path.isdir(MAME_HOME) else os.path.expanduser("~"))
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
        self.start_background_worker()
        self.worker_was_active = True
        self.roms = list_roms(self.settings["rom_dir"])
        self.meta = load_json(META_FILE)
        self.status_cache = load_json(STATUS_FILE)
        self.build_item_cache()
        self.update_folders_list()
        self.fill_list()
        self.compute_folder_size_async()

    def build_menu(self):
        bar = QMenuBar()
        file_menu = bar.addMenu(self.tr("menu_file"))
        
        a_refresh = QAction(self.tr("menu_refresh"), self)
        a_refresh.setShortcut(QKeySequence.Refresh)
        a_refresh.triggered.connect(self.reload_roms)
        file_menu.addAction(a_refresh)

        file_menu.addSeparator()
        a_open = QAction(self.tr("menu_open_mame"), self)
        a_open.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(MAME_HOME)))
        file_menu.addAction(a_open)
        file_menu.addSeparator()
        a_quit = QAction(self.tr("menu_quit"), self)
        a_quit.triggered.connect(self.close)
        file_menu.addAction(a_quit)

        sett = bar.addMenu(self.tr("menu_settings"))
        a_rom = QAction(self.tr("menu_rom_folder"), self)
        a_rom.triggered.connect(lambda: self.set_folder("rom_dir"))
        sett.addAction(a_rom)
        a_bios = QAction(self.tr("menu_bios_folder"), self)
        a_bios.triggered.connect(lambda: self.set_folder("bios_dir"))
        sett.addAction(a_bios)
        sett.addSeparator()

        lang_menu = sett.addMenu(self.tr("menu_language"))
        lang_grp = QActionGroup(self)
        lang_grp.setExclusive(True)
        current_lang = self.settings.get("language", "en")
        for l_code, l_label in (("en", "English"), ("it", "Italiano")):
            a = QAction(l_label, self, checkable=True)
            a.setChecked(current_lang == l_code)
            a.triggered.connect(lambda _c, code=l_code: self.set_language(code))
            lang_grp.addAction(a)
            lang_menu.addAction(a)

        sett.addSeparator()
        disp = sett.addMenu(self.tr("menu_display_mode"))
        grp = QActionGroup(self)
        grp.setExclusive(True)
        for label_key, fs in ((self.tr("menu_window"), False), (self.tr("menu_fullscreen"), True)):
            a = QAction(label_key, self, checkable=True)
            a.setChecked(self.settings["fullscreen"] == fs)
            a.triggered.connect(lambda _c, v=fs: self.set_fullscreen(v))
            grp.addAction(a)
            disp.addAction(a)
        return bar

    def set_fullscreen(self, value):
        self.settings["fullscreen"] = value
        save_settings(self.settings)

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
        self.update_folders_list()

    def update_favorite_button(self, name):
        favs = self.settings.get("favorites", [])
        star = "★" if name in favs else "☆"
        self.fav_btn.setText(f"{star} {self.tr('favorite')}")

    def update_play_button_color(self, name):
        if not name:
            self.btn.setStyleSheet("")
            self.btn.setText(self.tr("play"))
            return
        c = self.game_status_color(name)
        text_color = get_contrast_color(c)
        st = self.status_cache.get(name, "buono")
        st_label = self.tr(f"status_{st}") if f"status_{st}" in LANGS[self.settings.get("language", "en")] else st
        self.btn.setText(f"{self.tr('play')} ({st_label.capitalize()})")
        self.btn.setStyleSheet(f"""
            QPushButton {{ background-color: {c}; color: {text_color}; border: none; border-radius: 6px; padding: 8px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {c}; }}
        """)

    def on_search_changed(self):
        self.search_timer.stop()
        self.search_timer.start()

    def fill_list(self):
        q = self.search.text().lower()
        curr_item = self.folders_list.currentItem()
        curr_data = curr_item.data(Qt.UserRole) if curr_item else "all"
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
            m = self.meta.get(r)
            if m and m.get("bios", False):
                continue
            if curr_data == "favorites" and r not in favs:
                continue
            elif str(curr_data).startswith("status:"):
                target_st = str(curr_data).split(":", 1)[1]
                st = self.status_cache.get(r, "buono")
                if st != target_st:
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
        if self.list.count() and not self.list.currentItem():
            self.list.setCurrentRow(0)

        self.list.setUpdatesEnabled(True)
        self.update_status()

    def update_status(self):
        valid_roms = [r for r in self.roms if not self.meta.get(r, {}).get("bios", False)]
        total_games = len(valid_roms)
        names = self.bios_dir_names | {r for r in self.roms if self.meta.get(r, {}).get("bios", False)}
        
        parts = [
            f"<span style='color:{COLOR_GAMES};'>●</span> <span style='color:#ffffff;'>{total_games} {self.tr('games_count')}</span>",
            f"<span style='color:{COLOR_BIOS};'>●</span> <span style='color:#ffffff;'>{len(names)} {self.tr('bios_count')}</span>"
        ]
        if self.rom_size:
            parts.append(f"<span style='color:#ffffff;'>{fmt_size(self.rom_size)}</span>")
        
        self.count_lbl.setText(" \u00b7 ".join(parts))

    def current_name(self):
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def show_game(self, *_):
        name = self.current_name()
        if not name:
            self.update_play_button_color(None)
            return
        m = self.meta.get(name, {"desc": name, "year": "?", "maker": "?", "clone": ""})
        
        rows = [
            (self.tr("year"), m.get("year", "?")), 
            (self.tr("maker"), m.get("maker", "?")), 
            (self.tr("rom"), name + ".zip")
        ]
        if m.get("clone"):
            rows.append((self.tr("clone_of"), m["clone"]))
            
        txt = "<b>%s</b>" % html.escape(m.get("desc", name))
        LABEL_COLORS = {
            self.tr("year"): "#0a84ff", 
            self.tr("maker"): "#30d158", 
            self.tr("rom"): "#ff9f0a", 
            self.tr("clone_of"): "#bf5af2"
        }
        for k, v in rows:
            color = LABEL_COLORS.get(k, "#ffffff")
            txt += "<br><span style='color:%s'>%s:</span> %s" % (color, k, html.escape(v))
            
        self.info.setText(txt)
        self.set_cover(name)
        self.update_favorite_button(name)
        self.update_play_button_color(name)

    def set_cover(self, name):
        p = img_path(name)
        if os.path.exists(p):
            pm = QPixmap(p)
            self.cover.setPixmap(pm.scaled(self.cover.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        elif os.path.exists(p + ".none"):
            self.cover.setPixmap(QPixmap())
            self.cover.setText(self.tr("no_images"))
        else:
            self.cover.setPixmap(QPixmap())
            self.cover.setText(self.tr("loading_bg"))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        name = self.current_name()
        if name:
            self.set_cover(name)

    def launch(self, *_):
        name = self.current_name()
        if not name and self.roms:
            name = self.roms[0]
            
        if name and self.settings["rom_dir"]:
            rompath = ";".join(d for d in (self.settings["rom_dir"], self.settings["bios_dir"]) if d)
            cmd = MAME_CMD + ["-rompath", rompath, "-window", "-nomax", "-resolution", "1100x620", name]
            self.hide()
            self.mame_thread = MameRunnerThread(cmd)
            self.mame_thread.finished.connect(lambda: (self.show(), self.raise_(), self.activateWindow()))
            self.mame_thread.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Launcher()
    w.show()
    sys.exit(app.exec())
