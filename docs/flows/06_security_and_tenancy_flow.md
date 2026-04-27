## Security and Tenancy Flow

```mermaid
sequenceDiagram
  participant FE as Frontend
  participant J as Java Backend
  participant N as n8n
  participant P as Python

  FE->>J: User request
  J->>J: Resolve user -> coachProfileId from DB
  J->>N: trusted coachProfileId + request context
  N->>P: call tool with service auth + coachProfileId
  P->>P: enforce tenant scope in retrieval/indexing
  P-->>N: storageRefs only (no public URLs)
  N->>J: batch resolve storageRefs
  J->>J: policy check + tenancy check
  J-->>N: short-lived presigned URLs
```

### Sicherheitsprinzipien

- `coachProfileId` niemals aus Usertext übernehmen.
- Service-to-service Auth via Bearer Secret (MVP), später HMAC/mTLS/JWT.
- Presigned URLs ausschließlich serverseitig (Java) erzeugen.
