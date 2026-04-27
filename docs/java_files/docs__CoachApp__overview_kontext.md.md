# Platzhalter

- **Originalpfad**: `docs/CoachApp/overview_kontext.md`
- **Bereich**: (Optional) Single Source of Truth (Klartext)

Projektkontext: MyCoach SaaS Plattform

Dieses Projekt ist eine Multi-Tenant SaaS Plattform („MyCoach“) für Coaches und deren Endkunden.

Ziel ist es, dass Coaches ohne technische Kenntnisse ihre eigene „App“ erhalten, in der ihre Inhalte (Dokumente, PDFs etc.) als KI-gestützter Chat (RAG) für ihre Kunden verfügbar sind.

Grundprinzip

Es gibt zwei Hauptrollen:

Coach
Endkunde (Client/User)

Die Plattform nutzt Clerk ausschließlich für Authentifizierung (Login, Sessions).
Alle Geschäftslogik (Rollen, Zugänge, Zuordnung) liegt im eigenen Backend und in der DB.

Auth & Usermodell
Jeder Nutzer loggt sich über Clerk ein
clerkId = JWT.sub wird als externe ID verwendet
Backend führt eigene users Tabelle:
id (UUID)
clerk_id
role (user, coach, später evtl. admin)
Beim ersten Request wird der User automatisch angelegt (ensureUser(clerkId))

Wichtig:

Clerk kennt keine Rollenlogik
Rollen kommen ausschließlich aus der DB
Rollenlogik
user = Endkunde
coach = Coach

Die Rolle wird aktuell aus der DB gelesen, aber muss noch aktiv in die Autorisierung integriert werden (z. B. für @PreAuthorize oder eigene Checks).

Coach-Struktur

Ein Coach hat:

coach_profile
coach_subscription (mit max_active_clients)
coach_access_codes (für Kundenzugang)
coach_clients (Zuordnung zu Endkunden)
coach_knowledge_sources (z. B. Google Drive Ordner)
Endkunden-Zugang (wichtiges Kernkonzept)

Endkunden haben kein eigenes Invite-Link Login, sondern:

Login über Clerk
Danach:
entweder schon aktiv → Zugriff
oder → müssen einen Code eingeben
Code-System
Coaches erzeugen Zugangscodes
Endkunden geben Code ein
Backend:
prüft Code
prüft Slotlimit (max_active_clients)
erstellt/reaktiviert coach_clients Eintrag
setzt access_until (z. B. +30 Tage)
Zugriff

Ein Endkunde ist aktiv, wenn:

status = active
access_until > now

Sonst muss ein neuer Code eingegeben werden.

Monetarisierung
Coaches zahlen nach gleichzeitig aktiven Endkunden
z. B. 10 / 25 / 50 aktive Clients
Backend erzwingt Limit hart (kein Überschreiten möglich)
Multi-Tenancy (sehr wichtig)

Alle Daten sind strikt mandantentrennt über:

coach_profile_id

Jede relevante Tabelle enthält diesen Bezug oder ist indirekt darüber verbunden.

Wichtig:

Frontend darf niemals selbst coachId bestimmen
Backend leitet coachProfileId immer aus:
eingeloggtem User
aktiver Membership
Knowledge / RAG Architektur
Ziel

Jeder Coach hat eigene Inhalte → eigener KI-Kontext

Setup
Pro Coach ein Google Drive Ordner
Inhalte werden über n8n verarbeitet:
Dateien laden
chunking
embeddings
Speicherung in Vector DB
Datenstruktur
coach_knowledge_sources
coach_profile_id
google_drive_folder_id
vector_namespace
status
Chunks enthalten immer:
coach_profile_id
Wichtiger Punkt

Mandantentrennung erfolgt nicht über Drive, sondern über:

DB Zuordnung
coach_profile_id in jedem Chunk
Ingestion Flow (n8n)
n8n lädt alle aktiven Knowledge Sources
pro Coach:
Dateien im Drive Ordner prüfen
neue/geänderte erkennen
Text extrahieren
chunking + embeddings
Speicherung mit coach_profile_id
Chat Flow
Backend
Endpoint z. B. /api/chat
prüft:
User eingeloggt
aktive Membership
bestimmt:
coachProfileId

→ sendet an n8n

n8n
Retrieval nur für diesen Coach (Filter oder Namespace)
LLM Call
Antwort zurück
Google Drive Setup (MVP)

Nicht automatisiert.

Ablauf:

Coach registriert sich
DB legt coach_knowledge_sources mit pending an
Entwickler:
erstellt Drive Ordner manuell
teilt ihn mit Coach
trägt google_drive_folder_id in DB ein
setzt Status auf active

Kein Admin Dashboard notwendig im MVP.

Wichtige Prinzipien
Clerk = nur Auth, keine Businesslogik
DB = einzige Wahrheit für Rollen und Zugriffe
coach_profile_id = zentrale Trennung
Slotlimits werden serverseitig enforced
Zugriff basiert auf coach_clients, nicht auf Tokens oder Links
Frontend ist nicht vertrauenswürdig, Backend entscheidet alles
Zielzustand MVP

Funktionierender Flow:

User loggt sich ein
Falls nötig → Code eingeben
User wird Coach zugeordnet
Zugriff aktiv für definierte Zeit
Chat greift auf Coach-spezifisches Wissen zu (RAG via n8n)
Coach kann Kunden über Codes steuern

