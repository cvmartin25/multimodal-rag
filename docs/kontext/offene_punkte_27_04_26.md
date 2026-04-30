Was wir hier schon gelöst haben (in diesem Repo)
Python-RAG-Service gebaut (retrieve, index, jobs, prepare-context)
Full-Video-First Relevanzpass im Python-Service eingebaut (mit Fallback)
2-Stage Retrieval eingebaut
Tenant-Filter im Retrieval eingebaut
Evidence-Format mit storageRefs + locator eingebaut
Flows + Stellschrauben + Build-Log ausführlich dokumentiert
Mock-Tests für zentrale Logik laufen
Was noch nicht gelöst ist (weil Java/n8n-Teil fehlt)
1) Java + n8n Live-Integration
Nicht gelöst

Java resolve-media-refs Batch-Endpoint ist hier nicht implementiert
n8n Chat-Workflow retrieve -> resolve -> flash ist nicht live verdrahtet
2) Indexing-Trigger + Status-Owner in Java
Nicht final gelöst

Ziel: Java ist Job-of-record (uploaded -> processing -> active|error)
Aktuell: Python kann indexen, aber die echte Status-Orchestrierung über Java+n8n fehlt noch
3) Index-Payload (Base64 vs. ID/StorageRef)
Teilweise gelöst, noch nicht final

Aktuell Python-Index per contentBase64 (pragmatisch, testbar)
Zielbild: Java/n8n schicken IDs/Refs, Python arbeitet source-of-truth-getrieben
4) “Quelle wirklich laden + Flash final prüfen”
Teilweise gelöst, noch nicht End-to-End

Gelöst: Python liefert locator + storageRefs
Offen: Java resolve + n8n Flash-Aufruf mit presigned URLs ist noch nicht als produktiver Flow gebaut
5) Wochenreport
Nur konzeptionell gelöst

Flows/Plan/DoD dokumentiert
Nicht produktiv umgesetzt (kein laufender n8n-Cron + Persistenzpipeline im Zielsystem)