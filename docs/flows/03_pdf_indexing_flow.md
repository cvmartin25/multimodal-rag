## PDF Indexing Flow

```mermaid
flowchart TD
  A[Java marks upload complete] --> B[n8n index workflow]
  B --> C[Python /v1/rag/index]
  C --> D[Load PDF bytes]
  D --> E[Split into pages]
  E --> F[Render page image]
  F --> G[Extract page text optional]
  G --> H[Gemini Embedding 2 per page]
  H --> I[Store vector + locator.pageNumber + storageRef]
  I --> J[Job status active/error]
```

### Entscheidungslogik

- Eine Seite entspricht einer Evidence-Einheit (`pdf_page`).
- Beim Answering sieht Flash die Top-Seiten als Bild/PDF (nicht nur Textchunk).
- Nachbarseiten können bei Bedarf (`p-1`, `p`, `p+1`) ergänzt werden.
