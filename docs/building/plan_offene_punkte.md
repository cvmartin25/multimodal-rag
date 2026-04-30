## Plan – Offene Punkte & Entscheidungen (Stand: 28.04.2026)

Dieses Dokument sammelt **alle offenen Überlegungen/Produktentscheidungen** aus den letzten Gesprächen, inklusive Begründungen, Trade-offs und Empfehlungen. Ziel: in 3–6 Monaten ist nachvollziehbar, **warum** wir welche Richtung gewählt haben, ohne alte Chats lesen zu müssen.

---

## 1) Multimodal-first vs. Transcript-first (Video)

### 1.1 Begriffe

- **Multimodal-first**: Video-Fenster werden direkt (multimodal) embedded. Retrieval findet Zeitfenster; für Zitate sieht Flash das relevante Fenster (± Padding) und liefert einen Start-Timestamp.
- **Transcript-first**: Das Video wird transkribiert (ASR). Die Suche arbeitet primär auf Transcript-Spans (Text + timestamps), ggf. zusätzlich mit Embeddings/BM25.

### 1.2 Was wir erreichen wollen (Produktziel)

- **Korrekte Antworten** mit Mehrwert
- **Belegbarkeit**: “Seite X” (PDF) und “ab mm:ss” (Video)
- **Minimaler Aufwand** für Coaches (kein Vorformatieren/MD-Pflicht)

### 1.3 Vorteile Multimodal-first (empfohlener Default)

- Robust gegen heterogene Quellen (Slides/Tabellen/Screenrecordings/“messy” PDFs/Videos)
- Kein ASR als Pflichtschritt
- Zitate sind möglich ohne Transkriptzwang (Fenster → Flash findet Satzanfang)
- Besonders stark bei visuellen Inhalten (Marketing/Analytics/Onboarding/Immobilien-Tabellen/Tools)

### 1.4 Vorteile Transcript-first (späteres Upgrade)

- UX wie im Screenshot (sehr “sekündliche” Trefferlisten, Textstellen anzeigen/highlighten)
- In vielen Fällen günstigere Chatkosten, weil LLM nur Text sieht (statt Video)
- Sehr gut, wenn Inhalte überwiegend gesprochen und textnah sind (Q&A, Podcast-artig)

### 1.5 Nachteile / Risiken

- Multimodal-first kann pro Chat-Turn teurer sein, wenn häufig Video an Flash geht (Gegenmaßnahme: TopN=3, kurze Fenster, klare Quotas).
- Transcript-first braucht ASR und produziert Zusatzkomplexität (Qualität der Transkription, Fachbegriffe, Datenschutz, Storage/Index).

### 1.6 Entscheidung (MVP)

- **MVP = Multimodal-first** (wie im Plan gebaut).
- Transcript-Spans sind **optional** als spätere UX-/Kosten-Optimierung (z. B. nur für `teaching`-Segmente).

---

## 2) PDF: Seite vs. Text-only Chunking

### 2.1 Warum “Seite als Einheit” (Default)

- Coach muss nichts vorbearbeiten (kein “mach es zu Markdown”)
- Tabellen/Layouts bleiben auffindbar und erklärbar (Flash sieht Seite als Bild)
- Sehr gute Zitierfähigkeit (“Seite X”)

### 2.2 Was wir speichern

- Pro Seite: Embedding + `locator.pageNumber` + `storageRef` zur Seitenimage
- Optional: extractedText pro Seite (für Hybrid/Debug; ggf. gekürzt)

### 2.3 Flash-Nutzung (wichtig für Kosten)

- **Kein** Flash “pro Seite” beim Indexing.
- Flash sieht Seiten **on-demand** nur für TopN (z. B. 3) bei der Antwort.

---

## 3) Search-UX: 1 Suche vs. 2 Suchen (RAG + Keyword)

### 3.1 Beobachtung (Screenshot-Produkt)

- “Research” (klassisch RAG) + separate “Search” (Keyword über DB/Chunks).

### 3.2 Bewertung

- Für Endkunden ist eine zweite Suche oft Overhead.
- Für Coaches/Admins ist Keyword-Suche ein **Power-Tool**:
  - Audit/Vertrauen (“zeige alle Stellen mit Begriff X”)
  - Debugging (“kommt der Begriff überhaupt vor?”)
  - präzise Begriffssuche (Paragraphen, Namen, exakte Formulierungen)

### 3.3 Entscheidung (MVP)

- **Endkunden**: 1 primäre Suche (Guide-Chat) + “Quellen öffnen”.
- **Admin/Coach**: optional später eine reine Text-/Keyword-Suche (keine Pflicht für MVP).

---

## 4) Work vs. Research Modus (Endkunden)

### 4.1 Warum trennen?

Endkunden wollen oft nicht nur “Wissen”, sondern “mach mit mir die Aufgabe”:
- z. B. Kalkulation nach Methode XY
- Schritt-für-Schritt Anleitung
- Inputs abfragen, Zwischenergebnisse, Ergebnis

### 4.2 Definition

- **Research-Modus**: erklärend, belegend, Quellen prominent.
- **Work-Modus**: ausführend, Schrittplan + Interaktion, Quellen kompakt (aber vorhanden).

### 4.3 Quellen-Policy (nicht Blackbox, aber nicht nervig)

- Research: Quellen sichtbar standardmäßig (Seite/Timestamp + ggf. kurzer Bezug).
- Work: Quellen als **kompakte Marker** + “Belege anzeigen” (aufklappbar).
- Hochrisiko-Themen (Steuer/Recht/Finanzen): Quellen prominenter (auch im Work-Modus).

### 4.4 Entscheidung (MVP)

- Wir bauen “Work/Research” als **interne Moduslogik** (n8n Router).
- UI kann später einen Toggle bieten, muss aber nicht am Tag 1.

---

## 5) Topics / Scopes / Jahre (Sammlung eingrenzen)

### 5.1 Warum Topics helfen

- Qualität: weniger Rauschen, präzisere Treffer
- Performance: kleinerer Suchraum
- Kosten: weniger irrelevante Quellen an Flash
- UX: Nutzer hat Kontext (“ich bin im Modul Steuern”)

### 5.2 Hard vs. Soft Filter

- **Hard**: nur Topic durchsuchen (Risiko: Recall sinkt).
- **Soft (empfohlen)**: Topic bevorzugen, aber fallback auf “all topics”, wenn zu wenig Treffer.

### 5.3 Entscheidung (MVP)

- Topics/Collections als Metadatum unterstützen (mind. `collection`).
- Standard: topic-scoped, mit fallback, wenn keine Treffer.

---

## 6) 2-Stage Retrieval (Stage 1 + Stage 2) – brauchen wir das?

### 6.1 Ziel

Bei großen Datenmengen/Concurrency soll Retrieval stabil bleiben, auch ohne ANN/HNSW.

### 6.2 Gefahr

Stage 1 kann “gute Treffer” wegfiltern, wenn zu aggressiv.

### 6.3 Sichere Variante (Policy)

- Stage 1 muss **high-recall** sein (lieber zu viele Kandidaten).
- Stage 2 macht Präzision (Embedding rerank).
- Fallback: Wenn Stage 2 zu wenig Treffer liefert → CandidateCount hoch oder direkte Vector Search.
- Stage‑1 wahrscheinlich durch BM25/FTS ersetzen, sobald produciton ready
### 6.4 Ersatz durch Topics?

Topics + Coach scoping sind ein sehr starker “Stage-0” Filter.
Sie ersetzen Stage 1 **teilweise**, aber nicht garantiert bei:
- sehr großen Topics
- globaler Suche “alle Inhalte”
- hoher Parallelität

### 6.5 Entscheidung (MVP)

- 2-Stage bleibt **optional aktivierbar** (Performance-Modus).
- Primär setzen wir auf **Coach + Topic scoping**.
- Aktivierungsregel: 2-Stage nur, wenn Scope groß oder p95 Retrieval zu hoch (siehe `docs/flows/90_stellschrauben_tuning.md`).

---

## 7) Kosten-/Qualitätshebel (wichtige Prinzipien)

- Flash wird nicht “flächig” beim Indexing genutzt (außer Video-Relevanzpass).
- Flash sieht in Antworten nur TopN Quellen (Default 3).
- Video: Full-video Pass → relevante Segmente → Windowing nur dort → Embeddings.
- PDFs: Seite embeddeden; Flash sieht Seite nur bei Answering.
- Quellenpflicht: Antwort ohne passende Evidence soll “nicht sicher gefunden” zurückgeben.

---

## 8) Wochenreport “häufigste Fragen” (Coach-Feature)

### 8.1 MVP

- Wochenreport reicht (kein vollwertiges “Fragen-RAG” nötig).
- Speicherung: minimaler Fragen-Log (coachProfileId, createdAt, questionText, optional feedback/outcome).
- Retention: z. B. 12 Monate Rohfragen, Reports dauerhaft.

### 8.2 RAG-ready

- optional `questionEmbedding` Feld/Tabelle vorbereiten, später backfill möglich.

---

## 9) Offene Entscheidungen (noch final festzulegen)

- Ob Admin/Coach Keyword-Suche in MVP enthalten ist oder erst nach Validierung.
- UI-Konzept für Work/Research: Toggle vs. automatische Erkennung + Hinweis.
- Topic-Taxonomie: wie fein? (Jahr, Kurs, Modul, Thema).
- Transcript-Spans: wann aktivieren? (nur für teaching-segmente? nur für bestimmte Coaches?)

---

## 10) Memory-Design: Topic-Switch Detection & “dazu”-Auflösung (ohne RAG-Verfälschung)

Problem:
- Nutzer wechseln im Chat spontan Themen und nutzen Anaphern wie “dazu”, “das”, “suche alles dazu”.
- Wir brauchen genug Kontext, um “dazu” korrekt aufzulösen, ohne den gesamten Chatverlauf in die Retrieval-Query zu kippen.

Ziel:
- Prompt bleibt klein (letzte N Turns + Working State + Summary).
- RAG-Query bleibt **fragezentriert** und wird nur mit minimalem Task-Kontext angereichert.

### 10.1 Working State (minimal)

Der Agent pflegt ein kleines State-Objekt (persistiert), u. a.:
- `activeTopic`: aktuelles Thema (z. B. `steuern_fixflip`)
- `previousTopic`: vorheriges Thema
- optional `topicStack`: letzte 3 Topics (mit Timestamp)
- `activeMode`: `work` oder `research`
- `entities`: wichtige Entitäten/Parameter (z. B. Methode XY, Kaufpreis, Zinssatz)

### 10.2 Router-Schritt pro Usermessage

Für jede neue User-Nachricht wird (kurz) entschieden:
- Ist ein **Topic-Wechsel** passiert? (ja/nein)
- Welche Entitäten/Methode sind neu?
- Welcher Modus passt? (`work` vs `research`)

Regeln:
- Enthält die Nachricht starke neue Signale (neue Keywords/Entitäten), setze `activeTopic` neu.
- Ist die Nachricht anaphorisch (“dazu alles”, “mehr dazu”), behalte `activeTopic` und löse “dazu” damit auf.

### 10.3 Retrieval Query Builder (Guardrail)

Die Retrieval-Query an Python besteht aus:
- **aktueller Userfrage** (immer)
- plus 1–2 Sätze Task-Kontext aus Working State (z. B. `activeTopic`, Methode)

Explizit NICHT:
- kompletter Chatverlauf
- komplette Summary

Fallback-Policy:
- Wenn Retrieval “komisch” wirkt oder zu wenige Treffer liefert:
  - retry mit Query = nur letzte Usermessage (ohne State)
  - oder CandidateCount erhöhen (wenn Two-stage aktiv)

### 10.4 Warum das funktioniert

- “Dazu” wird zuverlässig interpretiert, weil `activeTopic` bewusst gepflegt wird.
- RAG wird nicht verfälscht, weil nur minimaler Kontext in die Query gelangt.
- Nutzer können Themen wechseln, ohne dass “alte” Themen ungewollt reinmischen.

---

## 11) “Fühlt sich wie ChatGPT an” ohne riesige Kontextfenster (n8n Memory pragmatisch)

Ziel:
- Nutzer sollen nicht frustriert sein (“Chat ist weg / Bot vergisst alles”),
- aber wir wollen **keine** unendlich wachsenden Prompt-Kontexte.

### 11.1 Warum sich das gut anfühlt

- Der Bot setzt **kontinuierlich** an der letzten Session an (Auto-Resume).
- Relevante Fakten (Inputs, Ziele, Annahmen) sind im **Working State** gespeichert und werden nicht “vergessen”.
- Der Prompt bleibt klein: “letzte N Turns” + “Working State” + “kurze Summary”.
- Kurswissen kommt weiterhin über RAG und wird nicht aus Chat-Text “halluziniert”.

### 11.2 Minimal-Implementierung (ohne Overengineering)

Wir brauchen nur drei Bausteine:

1) **Short-term Memory (Window)**:
   - In n8n: Window/Buffer Memory an den Agent hängen (z. B. 6–12 letzte Nachrichten).
2) **Working State (JSON, persistiert)**:
   - Pro Session ein kleiner Datensatz: `activeTopic`, `activeMode`, `entities/inputs`, `openQuestions`, `assumptions`.
   - Pro Turn aktualisieren.
3) **Summary so far (kurz, persistiert)**:
   - Alle 10–20 Turns oder bei Meilensteinen aktualisieren.
   - Nicht “jede Nachricht speichern”, sondern “was wurde entschieden”.

### 11.3 Guardrail: Memory darf Retrieval nicht verwässern

- Retrieval-Query bekommt **nicht** den kompletten Verlauf.
- Retrieval-Query bekommt: letzte Userfrage + 1–2 Kontext-Sätze aus Working State.
- Bei Unsicherheit: Router fragt einmal nach (“Meinst du Thema A oder B?”) oder fallback auf Query ohne State.

### 11.4 UX-Optionen (nicht Bibliothek, aber kein Frust)

- Kein “Chat-Archiv” nötig.
- Empfohlen: Auto-Resume + “Zuletzt” Liste (z. B. 5 Sessions) oder “1 Session pro Topic”.
