## System Architecture Flow

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

### Rollen

- Java: Tenancy/Auth/Policies/Presigned URLs/Status.
- n8n: Chat, Memory, Tool-Calling, LLM-Orchestrierung.
- Python: Preprocessing, Indexing, Retrieval.
- Supabase: Vektoren + Evidence-Metadaten.
