# Platzhalter

- **Originalpfad**: `docs/CoachApp/coachApp-S3-flow.md`
- **Bereich**: (Optional) Single Source of Truth (Klartext)

# CoachApp S3 Flow (Presigned Uploads) – Single Source of Truth

Dieses Dokument beschreibt den **einheitlichen S3/Objekt-Storage Upload-Flow** der CoachApp über **Presigned URLs**.

Ziel:
- Uploads laufen **direkt vom Browser** in den Object Storage (S3-kompatibel, z. B. Hetzner).
- Das Backend ist **Quelle der Wahrheit** für:
  - Mandantentrennung (`coach_profile_id`)
  - Ownership/Authorization
  - Metadaten in der DB
  - Status-Transitions

Es gibt zwei fachliche Anwendungsfälle, die **denselben technischen Upload-Mechanismus** nutzen:
- **Audio Upload** (Legacy aus Vorgänger-App, Case-basiert)
- **Coach Documents Upload** (neu, Coach-Dashboard: PDF/MD/TXT/…)

---

## Grundprinzip (für alle Uploads)

1) **Upload Init**: Frontend fragt Backend nach einer **Presigned PUT URL**  
2) **Direct PUT**: Frontend lädt Datei **direkt** in S3 hoch (CORS nötig)  
3) **Upload Complete**: Frontend bestätigt Upload beim Backend, Backend setzt Status/Metadaten  
4) **Weiterverarbeitung (optional)**: Backend triggert n8n / Pipeline (später)

Wichtig:
- Das Backend gibt **keine Storage-Credentials** an den Client.
- Presigned URLs sind **zeitlich begrenzt** (TTL, z. B. 300 Sekunden).
- Der Storage-Key wird **vom Backend** definiert, nicht vom Frontend.

---

## Storage / Bucket Konfiguration

### Gemeinsame S3 Settings (Backend)
- `storage.s3.endpoint`
- `storage.s3.region`
- `storage.s3.accessKey`
- `storage.s3.secretKey`

### Buckets
- **Audio Bucket**: `storage.s3.bucket` (z. B. `voicefiles`)
- **Documents Bucket**: `storage.s3.documents-bucket` (z. B. `coach-documents`)

Hinweis:
- Bucket CORS muss PUT/GET/HEAD von eurer Frontend-Origin erlauben, sonst schlägt der Browser-PUT fehl.
- Siehe auch `docs/CORS_solution.md`.

Reminder (aktueller Dev-Shortcut):
- Für lokale Tests können Dokumente **vorerst im selben Bucket wie Audio** landen (dann reicht die bestehende Bucket-/CORS-Konfiguration).
- Später wieder trennen auf einen eigenen Bucket `coach-documents`, um Policies/Lifecycle/Retention sauber zu isolieren.

---

## Flow A: Coach Documents (neu)

### Ziel
Coach lädt im Dashboard Dateien hoch (PDF/MD/TXT/…), die im Storage landen und in der DB in `coach_documents` erfasst werden.

Die Verarbeitung (n8n) wird später über `documentId` gestartet; für das MVP reicht:
- DB-Eintrag anlegen (pending_upload)
- Presigned Upload URL zurückgeben
- Upload Complete → Status `uploaded`

---

### A1) Upload Init (Documents)

**Frontend:**
- User wählt Datei im Coach-Dashboard.
- Frontend ruft Backend auf: „Begin Upload“ (Init).

**Backend:**
- Leitet `coach_profile_id` aus eingeloggtem User ab (DB, nicht aus Frontend).
- Erzeugt `document_id`.
- Baut `storage_key` (siehe unten).
- Legt Datensatz in `coach_documents` an:
  - `status = 'pending_upload'`
  - `storage_bucket`, `storage_key`
  - `original_filename`, optional `mime_type`, optional `file_size_bytes` (expected)
  - `uploaded_by_user_id = currentUserId`
- Erzeugt Presigned PUT URL für (`storage_bucket`, `storage_key`) mit TTL.
- Antwort ans Frontend:
  - `documentId`
  - `uploadUrl`

**Status nach A1:** `pending_upload`

---

### A1.1) Backend-API (Documents) – konkrete Endpunkte (Ist-Stand)

- `GET /api/coach/documents`
  - Listet Dokumente für den eingeloggten Coach (DB: `coach_documents`).
- `POST /api/coach/documents:begin-upload`
  - Legt DB-Row mit `status='pending_upload'` an und liefert `{ documentId, uploadUrl }`.
- `POST /api/coach/documents/{documentId}:complete-upload`
  - Setzt `status='uploaded'`, `uploaded_at=now()`, schreibt `mime_type` und `file_size_bytes`.
- `DELETE /api/coach/documents/{documentId}`
  - Löscht Dokument (MVP: blockiert bei `processing`/`active`).

---

### A2) Browser PUT (Documents)

**Frontend:**
- Führt `PUT uploadUrl` aus (Body = Datei/Blob).
- Muss je nach Implementierung evtl. den passenden `Content-Type` Header setzen.

**Storage:**
- Akzeptiert PUT nur, wenn CORS korrekt konfiguriert ist.

---

### A3) Upload Complete (Documents)

**Frontend:**
- Nach erfolgreichem PUT ruft Frontend Backend „Complete Upload“ auf und übergibt:
  - `documentId`
  - `mimeType`
  - `sizeBytes`

**Backend:**
- Prüft, dass das Dokument zu diesem Coach gehört (`coach_profile_id`).
- Prüft Status-Transition:
  - nur `pending_upload` → `uploaded` (MVP)
- Setzt:
  - `status = 'uploaded'`
  - `uploaded_at = now()`
  - `mime_type`, `file_size_bytes`

**Status nach A3:** `uploaded`

---

### A4) n8n Start (später)

Wenn ihr später verarbeitet:
- Backend triggert n8n mit **nur** `documentId`.
- n8n lädt Metadaten über Backend/DB.
- n8n lädt Datei aus S3 (server-to-server).
- n8n setzt Status:
  - `processing` → `active` oder `error`

Empfohlene Statuswerte:
- `pending_upload`
- `uploaded`
- `processing`
- `active`
- `error`

---

## Frontend Prototyp (Documents) – Ist-Stand

- **Toggle/Screens**
  - Die App rendert je nach Toggle einen „Screen“ (conditional rendering).
  - Für Coaches existiert zusätzlich zum Chat und Dashboard ein **Dokumente-Screen**.
- **Screen**
  - `CoachDocumentsScreen` bietet:
    - Upload via Presigned PUT (mit Progress)
    - Liste (via `GET /api/coach/documents`)
    - Delete (via `DELETE /api/coach/documents/{documentId}`)
- **Upload-Ablauf im UI**
  - 1) `begin-upload` (Backend) → `{ documentId, uploadUrl }`
  - 2) Browser `PUT uploadUrl` (Body = `File`)
  - 3) `complete-upload` (Backend) → Status wird `uploaded`

---

## Dokumente: Storage-Key (Pfad) – Konvention

Der Key muss:
- Mandantentrennung abbilden
- eindeutig + stabil sein
- unabhängig vom Dateinamen bleiben

**Empfehlung:**

`mycoach/{coachProfileId}/documents/{documentId}/original`

Begründung:
- `coachProfileId` kapselt Tenant
- `documentId` kapselt Objekt eindeutig
- Dateiname bleibt DB-Metadatum (`original_filename`)

---

## Flow B: Audio Upload (Legacy)

Dieser Flow existiert bereits und nutzt denselben technischen Mechanismus (Presigned PUT + Confirm), ist aber **Case-bezogen**.

Siehe auch `docs/flow-audio-upload-s3.md` für den aktuellen Stand.

Kurzform:
1) `POST /api/files:begin` → `{ fileId, uploadUrl }`
2) Browser `PUT uploadUrl`
3) `POST /api/files/{fileId}:confirm?caseId=...` → Backend verknüpft mit Case und setzt Status „queued“
4) optional n8n Job Start

---

## Stolperfallen / Best Practices

### CORS (Pflicht)
- Der PUT kommt aus dem Browser zur Storage-Domain.
- Ohne Bucket-CORS-Regeln scheitert der Upload (CORS-Fehler im Browser).

### Content-Type
- Für Documents darf der Presign nicht hart auf `audio/webm` festgelegt sein.
- Entweder:
  - Content-Type beim Presign **weglassen**, oder
  - als Parameter erlauben (und Frontend muss denselben Header senden).

### Security / Ownership
- Init/Complete müssen serverseitig prüfen:
  - aktueller User ist Coach
  - Dokument gehört zu `coach_profile_id` des Users
- Frontend darf niemals `coachProfileId` „vorgeben“.

### Kein S3-Download-Link ans Frontend (gewollt)
- Für Documents soll das Backend **keine Presigned Download URL** zurückgeben.
- Weiterverarbeitung erfolgt später serverseitig (n8n holt über `documentId`).


