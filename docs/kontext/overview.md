Hier ist die vollständige, thematisch gegliederte Zusammenfassung unserer Architektur-Strategie. Damit hast du das Lastenheft für deine nächsten 6 Wochen und den Input für Cursor und n8n.

1. Das Kernkonzept: "Natives Multimodales RAG"
Das System nutzt Gemini Embedding 2 und Gemini 1.5 Flash anstelle von Textumwandlung (Transkription/OCR). Die KI "sieht" und "hört" die Originaldateien.
Vorteil: Das System versteht Layouts, Tabellen, Tonfall und Bildinhalte.
Technik: Vektordatenbank (Supabase) mit 3072 Dimensionen.

2. Video-Workflow
Das System speichert nur das Originalvideo im S3-Storage.
Indizierung:
video_processor.py scannt das Video mit Gemini Flash.
Markiert "wertvolle Bereiche" (Lehre) vs. "Müll" (Smalltalk/Technik).
Wertvolle Teile werden alle 110 Sek. (mit 10 Sek. Overlap) an das Embedding-Modell gesendet.
In Supabase werden Vektor, Original-URL und Start-Timestamp gespeichert.
Retrieval:
Vektorsuche findet den relevanten 2-Minuten-Block.
Gemini Flash erhält die URL des Originalvideos mit dem Parameter video_metadata (Zeitfenster: Fundstelle +/- 30 Sek. Puffer).
Flash findet den logischen Satzanfang und liefert Textantwort + Timestamp.

3. PDF-Workflow
Das System ersetzt "1000-Token-Chunks" durch "Seiten-Logik".
Speicherung: Gesamt-PDF + Einzelseiten als JPG/PNG im S3.
Indizierung:
document_processor.py zerlegt PDF in Einzelseiten.
Jede Seite wird als Bild/PDF an Gemini Embedding 2 gesendet. Das Modell erfasst Text + räumliche Anordnung (Tabellen/Grafiken).
In Supabase werden Vektor, Text-Inhalt, Seitennummer und Link zum Seiten-Bild gespeichert.
Retrieval:
Vektorsuche findet die Seite.
Gemini Flash erhält das Bild der Seite und erklärt Grafiken und Tabellen, wie sie im Layout erscheinen.

4. Infrastruktur & Sicherheit
Das Java-Backend bietet Auth (Clerk), Stripe und Multi-Tenancy.
Das System nutzt Google Vertex AI mit Standort Frankfurt. Daten werden nicht zum Training verwendet.
n8n dient als Dirigent und mit der AI Agent Node als chat-Endpunkt. Python-Skripte erledigen das "Heavy Lifting" (ffmpeg, Slicing, API-Calls). n8n ruft python als Tool für den Chat.

5. Geschäftsmodell & Preisgestaltung
Zielkunden: High-Ticket Coaches.
Strategie: "Sell it before you build it" mit einer Video-Live-Demo.
Preisgestaltung:
Setup-Gebühr (2.500 €+) für Mediathek-Indizierung.
Monatlich 20 € pro Endkunde (User-Seat-Modell).
Abrechnung via Stripe Metered Billing.

6. Die nächsten Schritte (optionale Liste)
DB-Upgrade: Supabase-Tabelle auf vector(3072) umstellen.
Python-Tools: video_processor.py und embedder.py finalisieren (Fokus auf YouTube-Import für die Demo).
Frontend-Player: Video-Komponente bauen, die Zeitstempel-Parameter (#t=X) versteht.
Demo-Video: Einen "Golden Path" für Immocation vorbereiten (öffentliches Video nehmen, indizieren, komplexe Detailfrage stellen).