import json
import os
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

CONFIG_DIR = os.path.expanduser("~/.config/mame_launcher")
IMG_DIR = os.path.join(CONFIG_DIR, "img")
META_FILE = os.path.join(CONFIG_DIR, "meta.json")
STATUS_FILE = os.path.join(CONFIG_DIR, "status_cache.json")
PROGRESS_FILE = os.path.join(CONFIG_DIR, "worker_progress.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
LOCK_FILE = os.path.join(CONFIG_DIR, "worker.lock")
MAME_CMD = ["flatpak", "run", "org.mamedev.MAME"]
BASE_URL = "https://raw.githubusercontent.com/libretro-thumbnails/MAME/master/"
IMG_KINDS = ["Named_Boxarts", "Named_Titles", "Named_Snaps"]

os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def update_progress(task, current, total):
    save_json(PROGRESS_FILE, {"task": task, "current": current, "total": total})

def get_roms(rom_dir):
    if not rom_dir or not os.path.isdir(rom_dir):
        return []
    return sorted(f[:-4] for f in os.listdir(rom_dir) if f.lower().endswith(".zip"))

def thumb_name(desc):
    for ch in '&*/:`<>?\\|"':
        desc = desc.replace(ch, "_")
    return desc

def background_process():
    # Crea il lock file per indicare che il worker è in esecuzione
    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass

    try:
        settings = load_json(SETTINGS_FILE)
        rom_dir = settings.get("rom_dir", "")
        roms = get_roms(rom_dir)
        if not roms:
            update_progress("Nessuna ROM trovata", 0, 0)
            return

        meta = load_json(META_FILE)
        status_cache = load_json(STATUS_FILE)

        # Identifica i giochi che mancano di metadati o stato
        to_process = [r for r in roms if r not in meta or r not in status_cache]
        total = len(roms)
        processed = total - len(to_process)

        update_progress("Elaborazione giochi", processed, total)

        chunk_size = 30  # Batch ridotti per elaborazione fluida
        for i in range(0, len(to_process), chunk_size):
            chunk = to_process[i:i + chunk_size]
            try:
                res = subprocess.run(MAME_CMD + ["-listxml"] + chunk, capture_output=True, text=True, timeout=40)
                root = ET.fromstring(res.stdout)
                found_in_chunk = set()
                
                for m in root.iter("machine"):
                    name = m.get("name")
                    found_in_chunk.add(name)
                    
                    desc = m.findtext("description") or name
                    year = m.findtext("year") or "?"
                    maker = m.findtext("manufacturer") or "?"
                    clone = m.get("cloneof") or ""
                    is_bios = m.get("isbios") == "yes" or m.get("isdevice") == "yes"
                    
                    meta[name] = {"desc": desc, "year": year, "maker": maker, "clone": clone, "bios": is_bios}

                    driver = m.find("driver")
                    status = "buono"
                    if driver is not None:
                        st = driver.get("status", "good")
                        emul = driver.get("emulation", "good")
                        if st == "preliminary" or emul == "preliminary":
                            status = "inavviabile"
                        elif st == "imperfect" or emul == "imperfect":
                            status = "imperfetto"
                    status_cache[name] = status

                for r in chunk:
                    if r not in found_in_chunk:
                        if r not in meta:
                            meta[r] = {"desc": r, "year": "?", "maker": "?", "clone": "", "bios": False}
                        if r not in status_cache:
                            status_cache[r] = "buono"

                save_json(META_FILE, meta)
                save_json(STATUS_FILE, status_cache)
            except Exception:
                for r in chunk:
                    if r not in meta:
                        meta[r] = {"desc": r, "year": "?", "maker": "?", "clone": "", "bios": False}
                    if r not in status_cache:
                        status_cache[r] = "buono"

            # Scarica le copertine gioco per gioco per i file analizzati nel batch
            for r in chunk:
                if not meta.get(r, {}).get("bios", False):
                    path = os.path.join(IMG_DIR, r + ".png")
                    if not os.path.exists(path) and not os.path.exists(path + ".none"):
                        desc = meta.get(r, {}).get("desc", r)
                        fname = urllib.parse.quote(thumb_name(desc)) + ".png"
                        downloaded = False
                        for kind in IMG_KINDS:
                            try:
                                with urllib.request.urlopen(BASE_URL + kind + "/" + fname, timeout=4) as r_img:
                                    data = r_img.read()
                                with open(path, "wb") as f_img:
                                    f_img.write(data)
                                downloaded = True
                                break
                            except Exception:
                                continue
                        if not downloaded:
                            try:
                                open(path + ".none", "w").close()
                            except Exception:
                                pass

            processed += len(chunk)
            update_progress("Elaborazione giochi", min(processed, total), total)

        update_progress("Completato", total, total)

    finally:
        # Rimuove il file di lock alla fine del processo
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
            except Exception:
                pass

if __name__ == "__main__":
    background_process()
