## Video Indexing Flow

```mermaid
flowchart TD
  A[Java upload complete] --> B[n8n index workflow]
  B --> C[Python /v1/rag/index]
  C --> D[Video relevance pass]
  D --> E[Relevant segments with label + summary]
  E --> F[Windowing 120s with 10s overlap]
  F --> G[Gemini Embedding 2 per window]
  G --> H[Store vector + locator + segment metadata]
  H --> I[Job status active/error]
```

### Aktueller technischer Stand

- Windowing ist implementiert (120s/10s).
- Segment-Metadaten sind als Struktur vorgesehen.
- Der produktive Flash-Relevanzpass ist noch als nächster Ausbauschritt offen; aktuell sichere Fallback-Segmentierung.

### Qualitäts-/Kostenregel

- Keine Summary pro Window.
- Summary/Tags pro Segment reichen für Hybrid-Filter und Explainability.
