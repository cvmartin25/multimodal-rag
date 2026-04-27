# Ideen (Operational) — RAGbot Architektur, MCP vs API, Security/Hosting

Diese Notizen sammeln die in diesem Chat diskutierten **operationalen** Ansätze rund um ein “RAGbot für Coaches”-Produkt (React UI, Spring Backend, n8n Agent, Python für Chunking/Embeddings/Retrieval) sowie die Rolle von MCP vs klassischer HTTP-API.

## 1) Kontext: Was dieses Repo heute ist

- **Streamlit-Prototyp** (`app.py`): Upload/Embed, Search, Browse (Delete/Stats).
- **Python RAG-Pipeline** (`lib/*`): Chunking (Text/PDF/Audio/Video), Gemini Embeddings, Supabase/pgvector Storage & Vector Search, optional Reasoning via Gemini.
- **MCP-Server** (`mcp_server.py`): stellt ausgewählte Funktionen als MCP-Tools bereit (Search, Search+Reason, Collections, Stats). Wird von MCP-fähigen Clients/Agenten genutzt, nicht von der Streamlit-App.

## 2) MCP (Model Context Protocol) — wofür es gut ist

### 2.1 Begriffsklärung

- In MCP-Sprache ist der “**Host**” die App, die Tools konsumiert und orchestriert (z. B. Claude Desktop). In klassischer API-Sprache fühlt sich das wie ein **Client** an.
- Der “**MCP-Server**” ist der Tool-Anbieter (hier: `python mcp_server.py`), der Tools registriert und Calls beantwortet.

### 2.2 MCP vs klassische API (Mapping)

- HTTP API: Controller/Routes (`POST /search`) → Service (`rag.query`) → JSON über Netzwerk
- MCP: Tool-Funktion (`search_documents(query, top_k, ...)`) → Service (`rag.query`) → Tool-Result (z. B. String/JSON) über MCP-Transport (häufig stdio)

### 2.3 Was MCP an Aufwand abnimmt

- Tool-Discovery (welche Tools/Parameter/Defaults gibt es)
- Parameter-Validierung und Dispatch (passende Funktion finden und aufrufen)
- Standardisierte “Agent ↔ Tools” Integration für LLM-Hosts

### 2.4 Was MCP nicht “automatisch” löst

- Monetarisierung (Billing), Quotas/Budgets, Tenant-Isolation, AuthN/AuthZ
- Standard-Enterprise-Operations (WAF, API-Versionierung, Load Balancing etc.)

Pragmatische Sicht: In “Enterprise/Produkt”-Setups ist MCP oft **ergänzend** (Tool-Layer für Agenten/Dev), während **HTTP/gRPC** die primäre Produkt-Schnittstelle ist.

## 3) Produkt-Realität: Warum der aktuelle Prototyp nicht “production ready” ist

### 3.1 Security

- Nutzung von `SUPABASE_SERVICE_KEY` ist für Prototyp ok, aber in Produktion riskant (bypasst RLS).
- Kein User-/Tenant-Modell, keine Quotas, keine Policies.

### 3.2 Kosten & Skalierung

- Binärdaten (Image/Video/Audio) als Base64 in DB ist teuer (Speicher + Bandbreite).
- 3072-dim Embeddings → kein HNSW (pgvector Limit), Suche ist bruteforce/exakt und skaliert linear.
- Chunking von Audio/Video ist “fixed window” (75s/120s) und kann relevante Stellen ungünstig zerschneiden.

## 4) Zielarchitektur für “RAGbot für Coaches”

### 4.1 Rollenverteilung (empfohlen)

- **React**: UI, keine Secrets.
- **Spring Backend**: Auth, Stripe/Billing, Policies, Quotas/Budgets, Logging/Observability. “System of Record”.
- **Python RAG Service**: Chunking, Embedding (Gemini), Retrieval (Supabase RPC), optional Reasoning. Hält Gemini/Supabase Secrets.
- **n8n**: Chat/Agent-Orchestrierung (Agent Node), entscheidet, wann Retrieval-Tool genutzt wird — aber sollte keine DB/LLM Service Keys besitzen.

### 4.2 Wichtiges Prinzip: “Policy-Grenze”

- n8n und Frontend dürfen **nicht** direkt mit `SUPABASE_SERVICE_KEY` oder Gemini Keys arbeiten.
- Ein zentraler “Gatekeeper” (typisch Spring) erzwingt:
  - AuthZ (wer darf was)
  - Quotas/Budgets (Kostenkontrolle)
  - Tool-Scopes (z. B. `rag:query`, `rag:ingest`)
  - Audit Logs

## 5) Wie n8n den RAG-Teil aufruft (ohne fertige OpenAI-Embedding-Nodes)

### 5.1 Empfohlen: Dünne HTTP-API um den Python-RAG

Motivation:

- n8n kann HTTP als Tool sehr zuverlässig.
- Man ist nicht von “Vector Store Node + OpenAI Embeddings” abhängig.
- Security/Observability sind klarer als bei cross-container stdio.

Beispiel-Endpunkte (Shape, nicht final):

- `POST /rag/query`
  - Request: `query`, `top_k`, `threshold`, `content_type`, `collection`, `use_reasoning`
  - Response: `{ answer, sources: [...] }`
- `POST /rag/ingest` (idealerweise async job)
  - Request: `tenant_id`, `file_url`/`bytes`, `filename`, `mime_type`, `title`, `collection`
  - Response: `job_id` (oder result für sehr kleine Dateien)

### 5.2 Multimodale Queries (optional)

Viele Chat-Queries sind text-only. Wenn du “User fragt mit Bild/Audio/Video” willst, brauchst du:

- einen Endpoint/Tool, der `bytes + mime_type` (oder Storage-URL) akzeptiert,
- daraus ein Gemini-Embedding macht (`Part.from_bytes`),
- und damit in Supabase sucht.

## 6) Wo MCP im Zielbild reinpasst (optional)

Zwei sinnvolle Einsatzarten:

1. **Developer/Support Tooling**: Claude Desktop/Cursor kann auf interne Tools zugreifen, ohne dass du eine öffentliche API für alles bauen musst.
2. **Interner Agent-Layer**: Wenn du einen eigenen “Agent Orchestrator” betreibst, kann er als MCP-Host Tools nutzen (mit zusätzlicher Policy-Schicht).

Für Produktion über mehrere Container/Services ist HTTP/gRPC meist die robustere Schnittstelle; MCP kann ergänzend bleiben.

## 7) Performance-Einschätzung

- MCP/Tool-Call Overhead ist selten relevant.
- Dominant sind:
  - Embedding-Calls (Gemini)
  - Vector Search (Supabase/pgvector Roundtrip)
  - Chunking/Transcoding (Video/PDF/Audio IO/CPU)
  - Optional Reasoning (LLM Call)

## 7.1 Skalierung von n8n: Hash-based Sharding (pro Coach)

Wenn n8n “Memory”/State instanzgebunden ist oder du eine einfache Lastverteilung willst, kannst du Coaches **deterministisch** auf mehrere n8n-Instanzen verteilen (“Sharding”). Das Spring-Backend routet dann Requests zu der passenden n8n-URL.

### A) Einfach: `hash(coach_id) % N`

- Du hast \(N\) n8n-Instanzen.
- Du berechnest einen stabilen Hash über `coach_id` (z. B. SHA-256) und nimmst `mod N`.
- Ergebnis ist “sticky”: ein Coach landet immer auf derselben Instanz, solange \(N\) gleich bleibt.

**Trade-off:** Wenn \(N\) sich ändert (z. B. 3 → 4), werden sehr viele Coaches neu verteilt (massives Rebalancing).

### B) Besser: Rendezvous Hashing (HRW) / Consistent Hashing

Idee: Für jedes `(coach_id, shard_id)` berechnest du einen Score und wählst den Shard mit dem höchsten Score:

- `score(shard) = hash(coach_id + ":" + shard_id)`
- nimm den Shard mit `max(score)`

**Vorteile:**

- Beim Hinzufügen eines Shards wechseln nur ca. \(1/(N+1)\) der Coaches.
- Beim Ausfall eines Shards wechseln nur die Coaches dieses Shards.

### C) Healthchecks & Failover

Für Produktion brauchst du eine Strategie, wenn “der richtige” Shard down ist:

- Rendezvous hashing erlaubt elegant “Top-2” Auswahl: nimm den zweitbesten Shard als Fallback.
- Shards sollten Healthchecks haben; unhealthy Shards werden temporär aus der Kandidatenliste entfernt.

### D) Gewichte (optional)

Wenn Shards unterschiedlich groß sind, kannst du sie “gewichteten” (z. B. Shard mehrfach in die Kandidatenliste aufnehmen oder Score-Adjustment), damit große Instanzen mehr Coaches übernehmen.

## 8) “Python nur intern erreichbar” (Security Patterns)

Je nach Plattform-Fähigkeiten:

### 8.1 Best Case: Private Networking

- Python Service hat **keine öffentliche URL**, nur private interne Erreichbarkeit.
- Nur Spring/n8n im selben privaten Netz dürfen zugreifen.

### 8.2 Wenn Python doch eine öffentliche URL hat: “Public but locked down”

Mindestens:

- Service-to-service Auth (Header/JWT):
  - Spring sendet `Authorization: Bearer <kurzlebiges JWT>` oder `X-Internal-Key`.
  - Python validiert und lehnt alles andere ab.
- Optional zusätzlich:
  - IP-Allowlist (nur wenn IPs stabil)
  - mTLS (stark, aber ops-lastiger)

### 8.3 Gateway-Ansatz: Spring als einziges öffentliches Frontdoor

- Python wird “versteckt”.
- Spring proxyt intern zu Python (oder ruft intern per Service-URL).
- Außen gibt es nur Spring-Endpunkte; Security/Policies bleiben an einer Stelle.

## 9) Hosting auf Scalingo (pragmatische Empfehlung)

- **Python als eigener 3. Dienst** (separate App) ist meist am saubersten:
  - getrennte Skalierung (Ingest vs Auth/API)
  - Isolation (lange Jobs blocken Spring nicht)
  - klare Secrets-Grenze
- “Python im gleichen Deployable” (Subprocess/Sidecar) ist möglich, aber oft wartungsintensiver.

## 10) Nächste sinnvolle Schritte (wenn man daraus ein Produkt bauen will)

- Binärdaten in **Object Storage** auslagern; DB speichert URL/Key + Embedding + Metadaten.
- Multi-Tenant-Design: `tenant_id` pro Dokument/Chunk (oder getrennte Projekte/schemas).
- Quotas/Budgets/Rate-Limits im Spring Gateway.
- Async Ingest (Queue/Worker), um Timeouts zu vermeiden.
- Observability: structured logs, tracing, per-tenant usage metrics.

