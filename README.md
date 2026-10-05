# MAME Launcher

A sleek, lightweight, and modern desktop launcher for **MAME** built with Python, PySide6, and Pygame. Designed specifically for arcade enthusiasts, it offers an intuitive graphical interface with full gamepad support, background metadata processing, multi-language localization, and advanced game library organization.

![MAME Launcher Preview](preview.png)

## System Requirements & Compatibility

- **Target OS:** Developed and tested on **Debian 13.7**
- **Display Server:** **Xorg / X11 ONLY** (Wayland is not supported)
- **Main Executable:** `z.mame.py`

## Key Features

- **Gamepad & Controller Support:** Full navigation using gamepads (D-Pad, Left Analog Stick, and Action Button A) via Pygame integration.
- **Background Metadata Worker:** Asynchronous background worker (`mame_background_worker.py`) handling ROM scanning, MAME metadata parsing (`-listxml`), status caching, and cover art downloading.
- **Multi-Language Support:** Instant runtime switching between English and Italian from the Settings menu.
- **Game Status & Filtering:** Filter your library by **All Games**, **Favorites**, or execution status (**Good**, **Imperfect**, **Non-runnable**).
- **Arcade Manufacturer Badges:** Dynamic color coding for major arcade manufacturers (Capcom, Sega, SNK, Nintendo, Konami, Namco, Taito, Data East, Williams, and more).
- **Flatpak Integration:** Out-of-the-box support for Flatpak MAME installations (`org.mamedev.MAME`) with automatic filesystem permission overrides.
- **Favorites System:** One-click bookmarking to easily manage and filter your favorite arcade games.

## Prerequisites & Dependencies

### System Requirements
- **Operating System:** Debian 13.7 (or compatible Linux distribution running X11)
- **Display Server:** Active Xorg (X11) session
- **Python:** Version 3.8 or higher
- **MAME:** Native installation or Flatpak (`org.mamedev.MAME`)

### Installing Dependencies on Debian 13.7
Install all required system packages and Python dependencies using `apt`:

```bash
sudo apt update
sudo apt install -y \
    python3 \
    python3-pip \
    python3-pyside6 \
    python3-pygame \
    flatpak \
    x11-xserver-utils
```

### (Optional) MAME Flatpak Setup
If you prefer using the Flatpak build of MAME:

```bash
flatpak remote-add --if-not-exists flathub [https://dl.flathub.org/repo/flathub.flatpakrepo](https://dl.flathub.org/repo/flathub.flatpakrepo)
flatpak install flathub org.mamedev.MAME
```

## Installation & Launch

1. **Clone or download the repository:**
   ```bash
   git clone [https://github.com/your-username/mame-launcher.git](https://github.com/your-username/mame-launcher.git)
   cd mame-launcher
   ```

2. **Run the launcher:**
   ```bash
   python3 z.mame.py
   ```

### First Launch Setup
On initial startup, the application will prompt you to select your **ROMs folder** and **BIOS folder**. These directories can be updated anytime in the **Settings** menu.

## Controls

| Input Device | Action | Function |
| :--- | :--- | :--- |
| **Keyboard / Mouse** | Mouse Click / Arrow Keys | Navigate UI & Select Games |
| **Keyboard** | `Enter` | Launch Selected Game |
| **Keyboard** | `F5` / `Ctrl+R` | Refresh ROM Library |
| **Gamepad** | `D-Pad` / `Left Stick` | Move Selection Up / Down |
| **Gamepad** | `Button A` (Button 0) | Launch Selected Game |

## Configuration & Cache Directory

Application configuration, metadata caches, thumbnails, and execution status logs are stored in:
`~/.config/mame_launcher/`

## License

Distributed under the MIT License. See `z.mame.py` for copyright and author details.
