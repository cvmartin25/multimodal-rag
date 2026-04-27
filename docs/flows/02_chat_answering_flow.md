## Chat Answering Flow (2-Call Pattern)

```mermaid
sequenceDiagram
  participant U as User
  participant FE as Frontend
  participant J as Java Backend
  participant N as n8n Agent
  participant P as Python RAG Service
  participant G as Gemini Flash

  U->>FE: Frage stellen
  FE->>J: Chat request
  J->>N: Request + trusted coachProfileId
  N->>P: /v1/rag/retrieve
  P-->>N: evidences[] (storageRefs + locator)
  N->>J: /api/media:resolve (batch)
  J-->>N: presigned URLs
  N->>G: Frage + Memory + URLs + Locator
  G-->>N: Antwort + Quellenhinweise
  N-->>J: Antwortpayload
  J-->>FE: Antwort
  FE-->>U: Antwort + Seite/Timestamp
```

### Kernregeln

- n8n ruft genau 2 Tools auf: `retrieve` und `resolve-media-refs`.
- Python liefert niemals dauerhafte URLs, nur `storageRefs`.
- Java bleibt Owner für URL-Resolution und Tenancy-Checks.
