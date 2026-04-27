# Ideen: Python + n8n für dieses RAG-Projekt

## Zielbild

- **Python (dieses Repo):** Preprocessing, Multimodal-Chunking (PDF, Audio, Video), Embeddings, Speicherung in Supabase — alles, was Dateien, MIME-Typen und stabile Retry-/Batch-Logik braucht.
- **n8n:** Konversation und **Antwortgenerierung**; **AI Agent** mit angebundenem **Retrieval-Tool** (Query embedden → Vektorsuche / `match_documents` oder dünne HTTP-API darüber). Der Agent entscheidet, wann gesucht wird; Embedding steckt im Tool, nicht manuell pro Nachricht „neben“ den Chat gelegt.

## Warum die Aufteilung

- n8n ist stark bei **Orchestrierung**, Verzweigungen, Scheduling, Integrationen und **Agent-/Tool-Schleifen** — ohne eigenen Python-Agent-Code.
- Schweres **Chunking** und konsistente **Ingest-Pipeline** bleiben in wenig Python übersichtlicher als als großer n8n-Kabelbaum.

## Chat-Qualität (n8n-Seite)

- **Memory / Session** am Agent einplanen, damit Follow-up-Fragen Sinn ergeben.
- Retrieval sollte möglichst **lesbaren Kontext** liefern (`text_content` o. Ä.); reine Bild-/Video-Treffer ohne Text sind für die **Suche** ok, für **Zitate und Antworten** schwächer.

## Optional: dünne Schnittstelle

- Falls n8n nicht direkt Supabase-RPC oder Gemini gleich sauber abbilden soll: kleines **HTTP-API** (z. B. `POST /query` → intern `rag.query`), n8n ruft nur noch dieses Tool auf — Agent-Logik bleibt in n8n, RAG-Details im Repo.

## Referenz im Code

- RAG-Pipeline: `lib/rag.py` (`ingest`, `query`)
- MCP (für andere Clients): `mcp_server.py`
