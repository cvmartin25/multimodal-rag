1. PowerShell öffnen.

2. Ordner + Umgebung:

cd c:\Users\Christian\dev\projects\CoachApp\multimodal-rag\services\rag_service
.\.venv\Scripts\Activate.ps1
3. Server starten:

uvicorn src.rag_service.main:app --reload --port 8010
Laufen lassen; im Browser testen: http://127.0.0.1:8010/health

4. Beenden: im gleichen Fenster Strg+C.


# RAG-Service: Installation & Start

Kurzanleitung für ein **neues** System und zum **Wiederfinden**, wo im Repo was liegt.

## Im Repo verankerte Pfade

| Was | Wo |
|-----|-----|
| Python-Service (Code, `requirements.txt`) | `services/rag_service/` |
| Umgebungsvariablen (**nicht** ins Git committen) | `services/.env` |
| Lokale Python-Umgebung (**nach** `venv`-Anlage, **nicht** im Git) | `services/rag_service/.venv/` |
| Aktivierung unter Windows | `services/rag_service/.venv/Scripts/Activate.ps1` |
| Schema für Supabase | `services/rag_service/schema.sql` |

Auf einem **neuen PC** gibt es `.venv` noch nicht — einmal anlegen (siehe unten). Die Datei `services/.env` musst du selbst anlegen oder vom Team übernehmen (Out-of-band, nie mit Keys committen).

---

## Neuer PC: einmalig

Voraussetzung: **Python 3** installiert (`python --version` oder `py --version` in PowerShell).

1. PowerShell öffnen und in den Service-Ordner wechseln (Pfad an dein Repo anpassen):

   ```powershell
   cd <repo>\services\rag_service
   ```

2. Virtuelle Umgebung erzeugen:

   ```powershell
   python -m venv .venv
   ```

   Falls `python` fehlt: `py -m venv .venv` versuchen.

3. Umgebung aktivieren:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   Bei Meldung zur Ausführungsrichtlinie einmalig:

   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   ```

   Danach Schritt 3 wiederholen. Erfolg: Zeilenanfang zeigt oft `(.venv)`.

4. Abhängigkeiten installieren:

   ```powershell
   pip install -r requirements.txt
   ```

5. **`services/.env`** mit den benötigten Variablen füllen (Minimum siehe `services/rag_service/README.md`). Der Service lädt `services/.env` automatisch beim Start.

---

## Täglich starten

Immer aus **`services/rag_service`** (virtuelle Umgebung aktivieren, dann Uvicorn):

```powershell
cd <repo>\services\rag_service
.\.venv\Scripts\Activate.ps1
uvicorn src.rag_service.main:app --reload --port 8010
```

- Healthcheck: [http://127.0.0.1:8010/health](http://127.0.0.1:8010/health) → `{"status":"ok"}`
- Beenden: **Strg+C** im gleichen Terminal

---

## Ohne virtuelle Umgebung (optional)

Wenn du keine `.venv` nutzen willst: im Ordner `services/rag_service` einmal `pip install -r requirements.txt` mit deinem System-Python und denselben `uvicorn`-Befehl wie oben. Für mehrere Projekte ist **`.venv` empfehlenswert**.

---

## Wo ist „schon installiert“?

- **Im Klone nur Quelltext** — Pakete liegen nach `pip install` unter  
  `services/rag_service/.venv/Lib/site-packages/` (lokal, nicht im Git).
- Wer dasselbe Repo auf einem **zweiten Rechner** klont, führt die Abschnitte **Neuer PC** erneut aus (oder kopiert nur `.venv` mit — üblich ist aber Neuaufbau mit Schritten 1–4).

Weitere API- und Env-Details: `services/rag_service/README.md`.
