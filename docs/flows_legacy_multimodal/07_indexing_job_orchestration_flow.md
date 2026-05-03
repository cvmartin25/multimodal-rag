## Flow: Indexing Job Orchestrierung (Java ↔ n8n ↔ Python)

Dieses Dokument beschreibt den Soll-Ablauf für den Job-Lifecycle ab `uploaded` bis `active/error`.

---

## Kurzüberblick

- Java ist Owner der Upload- und Job-Status.
- n8n orchestriert Trigger/Retry.
- Python führt die eigentliche Verarbeitung aus.

---

## 1. Detaillierter Ablauf

1) Frontend führt Upload über Java aus (`begin-upload`, `complete-upload`).
2) Java setzt Medium auf `uploaded`.
3) Java stößt n8n Workflow `index-start` an (Payload nur IDs + trusted `coachProfileId`).
4) n8n erstellt/aktualisiert Job-Kontext und ruft Python `POST /v1/rag/index`.
5) Python verarbeitet:
   - `text`: chunk -> embed -> store
   - `pdf`: page -> embed -> store
   - `video`: window -> classify -> embed -> store
6) Python liefert Job-Ergebnis (`succeeded`/`failed`) und Anzahl inserted records.
7) n8n (oder Java via Polling) setzt Java-Status:
   - Erfolg: `processing -> active`
   - Fehler: `processing -> error` + Fehlergrund

---

## 2. Warum dieser Ablauf wartbar ist

- Java bleibt zentrale Wahrheit für UI/Businesslogik.
- n8n kann Retry/Dead-letter steuern, ohne Python-Code umzuschreiben.
- Python bleibt austauschbarer Worker mit klaren APIs.

---

## 3. Fehlerbehandlung / Retry

- Transiente Fehler (Netzwerk/API): n8n retry mit Backoff.
- Persistente Fehler (invalid file): sofort `error`, kein endloser Retry.
- Jede Pipeline-Stufe soll sinnvolle Fehlermeldungen liefern, die in Java angezeigt werden können.

---

## Relevante Dateien

| Bereich | Datei |
|---|---|
| Python index endpoint | `services/rag_service/src/rag_service/main.py` |
| Index processing logic | `services/rag_service/src/rag_service/service.py` |
| Build target design | `docs/building/plan_initial_overview.md` |
