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
| `windowLenSec` | 120 | Kürzer = präziser, mehr Vektoren | `RAG_INDEX_WINDOW_SECONDS` |
| `windowOverlapSec` | 10 | Höher = besserer Kontext, mehr Vektoren | `RAG_INDEX_WINDOW_OVERLAP_SECONDS` |
| `paddingSec` (Answering) | 30 | Höher = bessere Satzanfänge, mehr LLM-Kontext | `RAG_VIDEO_PADDING_SECONDS` |
| Relevanzpass aktiv | true | Spart Kosten, erhöht Signalqualität | Index payload `analyzeVideoRelevance` |
| Noise-Skip | true | Reduziert Datenmenge/Kosten | `service.py` (noise windows skip) |
| Full-pass priorisiert | true | Erst globale Segmente, dann Windowing | `video_analysis.py` + `service.py` |

---

## 3) PDF-Indexing Stellschrauben

| Stellschraube | Standard | Wirkung | Wo ändern |
|---|---:|---|---|
| Seite als Einheit | ja | Robust für Layout/Tabellen | `processors.py` / `service.py` |
| Neighbor Pages im Answering | bedarfsbasiert | Besserer Kontext, mehr Resolve/LLM | n8n Prompt-Logik / flow policy |
| `extractedText` speichern | optional | Hilft bei Hybrid/Debug, mehr Storage | `service.py` PDF branch |

---

## 4) Performance- und Skalierungshebel

| Stellschraube | Ziel | Wirkung | Ort |
|---|---|---|---|
| Tenant Filter | immer | verhindert Cross-tenant scans | `service.py` tenant filtering |
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
2. Prüfen: Werden `noise`-Windows dennoch indexiert?
3. Prüfen: Tenant-Filter greift?
4. Prüfen: Q&A wird ungewollt als Faktquelle genutzt?
5. Prüfen: Resolve im Batch oder N+1?
6. Prüfen: p95 Retrieval > 800ms -> Two-stage Retrieval priorisieren.
