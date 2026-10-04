# MAME Launcher

A sleek, lightweight, and modern desktop launcher for **MAME** built with Python and PySide6. It lists your ROM collection from a folder, automatically fetches metadata from MAME, downloads cover art from the Libretro thumbnails repository without needing an API key, extracts vibrant dominant colors for a polished UI look, and launches your games seamlessly.

![MAME Launcher Preview](preview.png)

## Features

- **Automatic ROM Scanning:** Reads standard `.zip` ROM archives from your custom ROM directory.
- **MAME Metadata Integration:** Queries MAME (`-listxml`) to retrieve game titles, release years, manufacturers, clone lineage, and BIOS requirements.
- **Cover Art Downloader:** Automatically fetches box arts, titles, and snapshots from the `libretro-thumbnails` repository.
- **Dynamic Accent Colors:** Computes the dominant color of each game's cover art to style list icons automatically.
- **Flatpak Support:** Works out-of-the-box with Flatpak installations of MAME, handling sandbox folder permissions automatically.
- **Persistent Caching:** Caches metadata and images locally in `~/.cache/mame_launcher` for instant startups.
- **Clean XVB-inspired Dark Theme:** Custom styled widgets, pill search bar, and full-screen toggle support.

## Requirements

- Python 3.8+
- [PySide6](https://pypi.org/project/PySide6/)
- MAME installed on your system (configured as a command or Flatpak package)

## Installation & Usage

1. Clone or download this repository.
2. Install the required dependencies:
   ```bash
   sudo apt install python3 python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets flatpak
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install flathub org.mamedev.MAME
   ```
3. Run the application:
   ```bash
   python z.mame.py
   ```

On your first launch, you will be prompted to select your **ROM folder** and optionally your **BIOS folder**. You can also update these paths at any time via the **Settings** menu.

## License

Distributed under the MIT License. See the code headers for more details.
