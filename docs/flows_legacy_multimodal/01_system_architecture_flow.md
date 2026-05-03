## Flow: Gesamtarchitektur (Java + n8n + Python RAG)

Dieses Dokument erklärt die übergreifende Architektur, damit zukünftige Änderungen klar einer Schicht zugeordnet werden können.

---

## Kurzüberblick

- **Java Backend** ist Source of Truth für Auth, Tenancy (`coachProfileId`), Storage-Policies und Status.
- **n8n** ist Chat-Orchestrator (Memory, Tool Calling, Agent-Entscheidung, LLM-Aufruf).
- **Python RAG Service** macht Indexing und Retrieval (Evidence ohne presigned URLs).
- **Supabase** speichert Embeddings + Evidence-Metadaten.
- **S3** hält Originalmedien und Derivate (z. B. PDF-Seitenbilder).

---

## 1. Verantwortlichkeiten (warum diese Trennung)

### Java Backend

- Setzt den vertrauenswürdigen Kontext (`coachProfileId`) aus DB/Session.
- Erzwingt Zugriff auf Media-Objekte per Policy und stellt presigned URLs aus.
- Führt Statusmaschinen für Uploads/Jobs.
- Ist der Ort für Quotas, Billing-nahe Regeln und Audit.

### n8n

- Empfängt den Chat-Request in einem agentischen Workflow.
- Ruft Python-Tools auf (`retrieve`, optional `prepare-context`).
- Ruft Java Batch-Resolve auf.
- Baut finalen Prompt/Attachment-Context für Gemini Flash.

### Python RAG Service

- Indexiert Text/PDF/Video/Audio in Vektor- und Evidence-Form.
- Führt semantisches Retrieval tenant-sicher aus.
- Liefert strukturierte Evidences (`storageRefs`, `locator`, `labels`, `hintForLLM`).

---

## 2. Datenfluss auf hoher Ebene

```mermaid
flowchart LR
  FE[Frontend] --> JAVA[Java Backend]
  JAVA --> N8N[n8n Agent Runtime]
  N8N --> PY[Python RAG Service]
  PY --> SB[(Supabase + pgvector)]
  JAVA --> S3[(S3 Storage)]
  N8N --> LLM[Gemini Flash]

  JAVA -->|trusted coachProfileId| N8N
  PY -->|storageRefs + locator| N8N
  N8N -->|batch resolve refs| JAVA
  JAVA -->|presigned URLs| N8N
  N8N -->|question + memory + evidence| LLM
```

---

## 3. Kritische Architekturregeln

- Python liefert **niemals** dauerhafte URLs, nur `storageRefs`.
- n8n ruft Java Resolve im **Batch** auf (kein N+1 pro Evidence).
- Tenancy ist immer serverseitig: `coachProfileId` aus Java-Kontext, nie aus Usertext.
- Q&A-Quellen sind markiert und standardmäßig nicht als primäre Faktenquelle zu behandeln.

---

## 4. Fehler- und Recovery-Pfade

- Wenn Python Retrieval fehlschlägt: n8n gibt kontrollierte Fehlermeldung zurück; kein stilles Halluzinieren.
- Wenn Java Resolve einzelne Refs verweigert: nur verfügbare Refs an LLM geben, verweigerte in Debug/Audit markieren.
- Wenn LLM-Aufruf scheitert: Chat-Request als transient error klassifizieren; Retry-Policy über n8n.

---

## Relevante Dateien

| Bereich | Datei |
|---|---|
| Python API | `services/rag_service/src/rag_service/main.py` |
| Python Orchestrierung | `services/rag_service/src/rag_service/service.py` |
| Flows-Spezifikation | `docs/building/plan_initial_overview.md` |
