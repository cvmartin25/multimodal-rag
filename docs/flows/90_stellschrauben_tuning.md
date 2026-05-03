## Stellschrauben: Chunking, Performance, Qualität, Kosten

Dieses Dokument ist die zentrale Referenz für Feinjustierung. Ziel: Bei späterem Tuning nicht in Code/Chats suchen müssen.

---

## 1) Chat-Retrieval Stellschrauben

| Stellschraube | Standard | Wirkung | Wo ändern |
|---|---:|---|---|
| `topK` (Retrieve) | 8 | Mehr Kandidaten = bessere Recall, mehr CPU/Latency | `RAG_TOPK_DEFAULT`, `config.py` |
| `topN` (Resolve/Flash) | 3 | Mehr Quellen = bessere Abdeckung, höhere LLM-Kosten | `RAG_TOPN_DEFAULT`, n8n workflow |
| Similarity Threshold | 0.3 | Höher = präziser, niedriger = mehr Recall | Request `options.threshold` |
| `includeQa` | false | true erlaubt Q&A-Quellen stärker | Request `options.includeQa` |
| Collection Filter | default | Begrenzt Suchraum | Request `options.collection` |
| `useTwoStage` | true | Lexikalische Vorselektion vor Embedding-Rerank | Request `options.useTwoStage`, `RAG_TWO_STAGE_ENABLED` |

---

## 2) Video-Indexing Stellschrauben

| Stellschraube | Standard | Wirkung | Wo ändern |
|---|---:|---|---|
| `transcriptTargetSpanSec` | 40 | Kürzer = präziser, mehr Chunks | `RAG_TRANSCRIPT_TARGET_SPAN_SECONDS` |
| `transcriptMaxSpanSec` | 60 | Obergrenze für Chunk-Länge | `RAG_TRANSCRIPT_MAX_SPAN_SECONDS` |
| Sprache | `de` | steuert Whisper-Spracherkennung | `RAG_TRANSCRIPT_LANGUAGE` |
| Whisper Modell | `whisper-1` | Qualität/Kosten der Transkription | `RAG_WHISPER_MODEL` |
| Relevanzpass aktiv | true | Spart Kosten, erhöht Signalqualität | Index payload `analyzeVideoRelevance` |
| Full-pass priorisiert | true | Erst globale Segmente, dann Range-Transkription | `video_analysis.py` + `service.py` |

---

## 3) PDF-Indexing Stellschrauben

| Stellschraube | Standard | Wirkung | Wo ändern |
|---|---:|---|---|
| Seite als Einheit | ja | Robust für Layout/Tabellen | `processors.py` / `service.py` |
| Render-Zielbreite | 1280px | Kosten/Lesbarkeit Trade-off | `RAG_PDF_RENDER_TARGET_WIDTH` |
| Render-Format | jpeg | kleinere Artefakte vs. Größe | `RAG_PDF_RENDER_FORMAT` |
| JPEG-Qualität | 80 | Qualität/Kosten Trade-off | `RAG_PDF_RENDER_QUALITY` |
| Neighbor Pages im Answering | bedarfsbasiert | Besserer Kontext, mehr Resolve/LLM | n8n Prompt-Logik / flow policy |
| `extractedText` speichern | aktiv (best effort) | Hilft bei Policy/Debug/Qualität | `service.py` PDF branch |

---

## 3b) Indexing: Worker Object Storage (Python ↔ S3)

Optional: Python lädt Originale per **`contentBucket` + `contentKey`** und kann PDF-Seitenbilder zurück nach S3 schreiben (`object_storage.py`). Voraussetzung: `RAG_S3_*` gesetzt und Allowlists passend zur Produktions-Pfadstruktur.

| Stellschraube | Standard | Wirkung | Wo ändern |
|---|---|---|---|
| Worker aktiv | aus (ohne Env) | ohne Credentials nur Base64/URL | `RAG_S3_ENDPOINT_URL`, `RAG_S3_ACCESS_KEY_ID`, `RAG_S3_SECRET_ACCESS_KEY` |
| Bucket-Allowlist | leer = alle konfigurierten Buckets erlaubt (Implementierung prüfen) | Begrenzt Blast-Radius bei falscher Payload | `RAG_S3_ALLOWED_BUCKETS` |
| Key-Prefix-Allowlist | leer = keine Extra-Prüfung | Erzwingt Präfix z. B. `coachId/` | `RAG_S3_KEY_PREFIX_ALLOWLIST` |
| Addressing style | `path` | S3-kompatible Provider (Hetzner, MinIO) | `RAG_S3_ADDRESSING_STYLE` |

**Hinweis:** Das betrifft nur den **Indexing-Worker**. Kurzlebige URLs für **Chat/Flash** kommen weiterhin über **Java Resolve**, nicht über diese Credentials.

---

## 4) Performance- und Skalierungshebel

| Stellschraube | Ziel | Wirkung | Ort |
|---|---|---|---|
| Tenant Filter | immer | verhindert Cross-tenant scans | `service.py` tenant filtering |
| Tenant-Filter im RPC | immer | reduziert unnötige Rückgaben | `match_rag_chunks` |
| Two-stage Retrieval | ab >50k vectors/coach | reduziert teure Vector-Scans | Retrieval layer (später) |
| Prefilter Limit | 1200 | mehr Kandidaten = besserer Recall, höherer CPU/RAM-Bedarf | `RAG_TWO_STAGE_PREFILTER_LIMIT` |
| Candidate Count | 120 | steuert Kosten von Stage-2-Reranking | `RAG_TWO_STAGE_CANDIDATE_COUNT` |
| Dedupe in Resolve | immer | weniger Java/S3 Calls | n8n + Java resolve contract |
| Caching (Query->Evidence) | optional | bessere p95 bei Hot-Queries | n8n/Python layer (später) |
| Vector backend swap | optional | besseres Scale/QPS | Abstraktion in `vector_store.py` |

---

## 5) Sicherheits-Stellschrauben

| Stellschraube | Standard | Wirkung | Wo |
|---|---|---|---|
| Service Auth | Bearer secret | MVP schnell umsetzbar | `auth.py` |
| URL TTL | 300s | kurze Exposition | Java resolve endpoint |
| Trusted coach context | Pflicht | verhindert tenant leaks | Java→n8n Übergabe |
| Keine persistenten URLs | Pflicht | reduziert Leak-Risiko | gesamter Flow |
| S3-Worker-Allowlists (Indexing) | empfohlen in Prod | Bucket/Key-Pfade einschränken | `RAG_S3_ALLOWED_BUCKETS`, `RAG_S3_KEY_PREFIX_ALLOWLIST` |

---

## 6) Wochenreport Stellschrauben

| Stellschraube | Standard | Wirkung | Wo |
|---|---|---|---|
| Zeitraum | 7 Tage | Report-Rhythmus | n8n cron workflow |
| Retention raw questions | 12 Monate | Speicher vs. Historie | DB retention policy |
| Gruppierungsstrategie | LLM grouping | schnell startbar | n8n reporting flow |
| Beispiele paraphrasiert | ja | datenschutzfreundlicher | report generation step |

---

## 7) Troubleshooting-Checkliste (kurz)

Wenn Antworten zu langsam/teuer/unpräzise werden:

1. Prüfen: `topK`/`topN` zu hoch?
2. Prüfen: Werden unnötig viele Video-Spans erzeugt (`target/max span`)?
3. Prüfen: Tenant-Filter greift?
4. Prüfen: Q&A wird ungewollt als Faktquelle genutzt?
5. Prüfen: Resolve im Batch oder N+1?
6. Prüfen: p95 Retrieval > 800ms -> Two-stage Retrieval priorisieren.
