# TODO Backend + n8n (Finalisierung)

Dieses Dokument ist die **konkrete Umsetzungs- und Entscheidungsgrundlage** für das andere Projekt (Java + n8n).

---

## 1) Kontext, der der KI im anderen Projekt mitgegeben werden muss

### Pflicht
- `docs/building/plan_initial_overview.md`
- `docs/building/build_log.md`
- `docs/flows/00_index.md`
- `docs/flows/01_system_architecture_flow.md`
- `docs/flows/02_chat_answering_flow.md`
- `docs/flows/03_pdf_indexing_flow.md`
- `docs/flows/04_video_indexing_flow.md`
- `docs/flows/06_security_and_tenancy_flow.md`
- `docs/flows/07_indexing_job_orchestration_flow.md`
- `docs/flows/90_stellschrauben_tuning.md`

### Für Java-Integration zusätzlich
- `docs/kontext/java_projectinfo.md`
- Relevante Dateien aus `docs/java_files/` (Onboarding, CoachDocument-Flow, Callback/Auth)

### Für Python-Referenz zusätzlich
- `services/rag_service/src/rag_service/*`
- `services/rag_service/tests/*`
- `services/rag_service/README.md`

---

## 2) Finaler Ziel-Jobflow (verbindlich)

1. Frontend lädt Datei über Java (`begin-upload` / `complete-upload`).
2. Java setzt Status auf `uploaded`.
3. Java triggert n8n-Workflow `index-start` mit trusted Kontext:
   - `coachProfileId`
   - `documentId` oder `videoId`
4. n8n ruft Python Indexing-Endpoint auf.
5. Python verarbeitet:
   - PDF: page-based embedding
   - Video: full-video Flash relevance pass -> segment timestamps -> window embedding nur in relevanten Segmenten
6. Python liefert Jobstatus (`succeeded/failed`) + inserted records.
7. n8n schreibt Ergebnis an Java zurück.
8. Java setzt final:
   - `processing -> active` bei Erfolg
   - `processing -> error` bei Fehler

Wichtige Chat-Seite (2-Call-Pattern):
1. n8n -> Python `/v1/rag/retrieve`
2. n8n -> Java `/api/media:resolve` (Batch)
3. n8n -> Gemini Flash mit presigned URLs + Locator + Memory

---

## 3) Entscheidungen zu offenen Punkten (verbindlich)

### Punkt 3 (Soll man schon anfangen / Qualität ohne Testing?)
**Ja, anfangen.**  
**Nein, ohne Tests nicht “finalisieren”.**

Regel:
- Entwicklung kann sofort weiterlaufen.
- Merge/Release nur mit:
  - Unit-Tests (mindestens Retrieval + Video Indexing)
  - 1 Integrationstest Ende-zu-Ende (Upload -> Index -> Chat mit Quelle)

Ohne Testing steigt das Risiko stark bei:
- Tenancy-Leaks
- falschem Resolve-Mapping
- fehlerhaften Timestamps/Zitaten

### Punkt 4 (wie machen wir das am besten?)
Best Practice:
1. Erst Java Resolve + Statusflow stabil bauen.
2. Dann n8n Workflow mit 2 Toolcalls.
3. Danach Integrationstest auf echter Staging-Kette.
4. Dann Feintuning (topK/topN, threshold, retries).

### Punkt 5 (Wochenreport: in dieses TODO?)
**Ja, hier rein ist sinnvoll**, weil die operative Umsetzung primär Java/n8n betrifft.  
Aber: “RAG-ready” Design muss von Anfang an berücksichtigt werden.

Mindestanforderung:
- Frage-Logging pro Coach (`coachProfileId`, `createdAt`, `questionText`, optional feedback, answerHadEvidence)
- Weekly aggregation in n8n
- Persistenz `coach_weekly_reports`
- Optionales Feld für `questionEmbedding` vorbereiten (auch wenn später befüllt)

### Punkt 6 (StorageRef/Quelle laden – Vorschlag)
Verbindlicher Zielpfad:
- Python liefert nur `storageRefs` + `locator`.
- Java resolved Batch-presigned URLs.
- n8n gibt diese URLs + `startSec/endSec/paddingSec` an Flash.
- Padding Default: 30s.

Kein dauerhafter URL-Speicher in Memory/DB.

---

## 4) Konkrete Aufgabenliste für das andere Projekt (DoD)

### Java
- [ ] `POST /api/media:resolve` (Batch mit `evidenceId`-Mapping) implementieren
- [ ] Tenancy/Ownership-Prüfung pro `bucket/key` im Resolve
- [ ] Statusmaschine finalisieren (`pending_upload -> uploaded -> processing -> active|error`)
- [ ] Trigger n8n bei `complete-upload`
- [ ] Job-/Audit-Logging ergänzen

### n8n
- [ ] Chat-Workflow mit exakt 2 Toolcalls implementieren (`retrieve`, `resolve`)
- [ ] Fehlerpfade implementieren (keine Evidenz, denied refs, timeout, fallback response)
- [ ] Index-Workflow (`index-start`) mit Retry/Backoff + final callback zu Java
- [ ] Weekly report workflow (Cron -> group -> summarize -> persist)

### Tests
- [ ] Unit-Tests für Java Resolve/Statusregeln
- [ ] 1 E2E Test: PDF Upload -> Frage -> Seite als Zitat
- [ ] 1 E2E Test: Video Upload -> Frage -> Timestamp als Zitat
- [ ] Negativtest: denied Resolve -> kontrollierte Agent-Antwort

### Ops
- [ ] Secrets/TTL/Timeouts/Retry-Limits dokumentieren
- [ ] `topK=8`, `topN=3`, `padding=30`, `window=120/10` als Defaults setzen
- [ ] Monitoring für p95 Retrieval und Flash-Latenz

---

## 5) Master-Anweisung (Copy-Paste für KI im anderen Projekt)

Wir bauen eine produktionsnahe Integration zwischen Java Backend, n8n Agent Runtime und Python RAG Service.

Nicht verhandelbar:
1) Java ist Source of Truth für Auth/Tenancy/coachProfileId/Status/Policies/presigned URLs.
2) n8n macht Chat-Memory + Tool-Calling + LLM-Orchestrierung.
3) Python macht Indexing + Retrieval und liefert Evidence ohne dauerhafte URLs.
4) Chat-Flow ist 2-Call: n8n->Python retrieve, n8n->Java resolve(batch), dann n8n->Flash.
5) Video-Indexing: Full-Video-First Flash-Relevanzpass, danach Windowing nur in relevanten Segmenten.
6) Retrieval: 2-stage (lexikalisch + semantisch).

Bitte Schritt für Schritt umsetzen:
1. Java Endpoints/Status/Resolve-Batch
2. n8n Workflows (Chat + Index + Error paths)
3. Integrations-Tests
4. Dokumentation aktualisieren

Am Ende berichten:
- Was implementiert wurde
- Welche Endpoints/Nodes/Configs neu sind
- Welche Tests laufen
- Welche offenen Risiken bleiben