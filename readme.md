# MAME Launcher

Un launcher desktop moderno, leggero ed elegante per **MAME**, scritto in Python con PySide6. Gestisce la tua collezione di ROM, recupera automaticamente i metadati, scarica le copertine e permette di avviare i giochi con un'interfaccia grafica curata e reattiva[cite: 2].

## Caratteristiche Principali

- **Scansione Automatica delle ROM:** Rileva istantaneamente gli archivi `.zip` standard presenti nella cartella ROM[cite: 2].
- **Worker in Background Dedicato:** Un processo asincrono elabora i metadati e aggiorna lo stato in tempo reale con una barra di progresso dettagliata nella barra di stato.
- **Libreria e Filtri Avanzati:** Sidebar laterale per filtrare rapidamente tra *Tutti i giochi*, *Preferiti* e suddivisione per stato di funzionamento (*Buono*, *Imperfetto*, *Inavviabile*).
- **Integrazione Metadati e BIOS:** Rilevamento automatico dei file BIOS, dei produttori con colorazione dedicata e dei cloni.
- **Download delle Copertine:** Recupera automaticamente box art e schermate dal repository `libretro-thumbnails` senza bisogno di chiavi API[cite: 2].
- **Supporto Flatpak:** Funziona nativamente con le installazioni Flatpak di MAME gestendo i permessi della sandbox in autonomia[cite: 2].
- **Configurazione Persistente:** Salvataggio di preferenze, cache e immagini nella cartella utente `~/.config/mame_launcher`.

## Requisiti

- Python 3.8+[cite: 2]
- [PySide6](https://pypi.org/project/PySide6/)[cite: 2]
- MAME installato sul sistema (tramite pacchetto Flatpak o eseguibile)[cite: 2]

## Installazione e Utilizzo

1. Clona o scarica questa repository.
2. Installa le dipendenze necessarie (esempio per sistemi Debian/Ubuntu):
   ```bash
   sudo apt install python3 python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets flatpak
   flatpak remote-add --if-not-exists flathub [https://dl.flathub.org/repo/flathub.flatpakrepo](https://dl.flathub.org/repo/flathub.flatpakrepo)
   flatpak install flathub org.mamedev.MAME
