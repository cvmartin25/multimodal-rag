# Flow: Text-Assistent (KI-Textverarbeitung)

Dieses Dokument beschreibt den Ablauf der **Text-Assistent-Funktion**: Nutzer:in gibt Anweisung und Text ein, das Backend startet einen n8n-Workflow, und das verarbeitete Ergebnis kommt per Callback und wird vom Frontend per Polling abgerufen. Für neue Teammitglieder gedacht.

---

## Kurzüberblick

- **Frontend** sendet **POST /api/text-assistant/process** mit userPrompt, textContent und optional textLength.
- **Backend** legt einen Eintrag in der **Assistant-Result-Tabelle** an (Status PROCESSING), sendet die Daten per **POST** an die **n8n Text-Assistent-Webhook-URL** (fire-and-forget) und gibt sofort **requestId** zurück.
- **n8n** verarbeitet den Text (z.B. mit GPT) und sendet das Ergebnis an **POST /api/assistant-results/callback** (Header **X-N8N-Secret**).
- **Backend** speichert das Ergebnis zum **requestId** (userId aus DB, nicht aus Payload).
- **Frontend** pollt **GET /api/text-assistant/result/{requestId}** bis Status **ready** oder **error** und zeigt den verarbeiteten Text bzw. Fehlermeldung.

---

## 1. Frontend: Process auslösen

- **Service:** `TextAssistantService.js` – Methode **processText(userPrompt, textContent, textLength)** (textLength z.B. 'short', 'normal', 'long').
- **Validierung:** userPrompt und textContent erforderlich, nicht leer.
- **Request:** **POST /api/text-assistant/process** mit Body:
  - `userPrompt`: Anweisung für die KI
  - `textContent`: zu verarbeitender Text
  - `textLength`: optional, Standard 'normal'
- **Antwort:** `{ success, requestId, message, processedText: null }` – der verarbeitete Text kommt per Polling; **requestId** für Polling.

---

## 2. Backend: Process

**Controller:** `TextAssistantController` – **POST /api/text-assistant/process**

- User aus JWT.
- Body: **TextAssistantRequest** (userPrompt, textContent, textLength).

**TextAssistantServiceImpl.process:**

- Validierung: Request nicht null; textContent und userPrompt nicht leer.
- **requestId:** neu generiert (UUID).
- **DB:** **AssistantResultRepository.upsertByRequestId(requestId, userId, "text_assistant", PROCESSING, null, null)**.
- **Payload für n8n:** version, event "start", requestId, userId, type "text_assistant", userPrompt, textContent, textLength, timestamp.
- **POST** an **n8n.webhook-text-assistant.url**, optional Header **X-Webhook-Key** mit **n8n.webhook-text-assistant.secret**. Fire-and-forget.
- Bei Erfolg: Response mit **requestId**, success, Message (Ergebnis per Polling).
- Bei Exception: Status in DB auf ERROR setzen, Fehlermeldung zurückgeben.

---

## 3. n8n-Workflow (extern)

- n8n empfängt Webhook mit requestId, userId, userPrompt, textContent, textLength.
- Workflow verarbeitet den Text (z.B. GPT). Am Ende: **POST /api/assistant-results/callback** mit **X-N8N-Secret** und **AssistantCallbackPayload** (requestId, type "text_assistant", status READY/ERROR, content/errorMessage).

---

## 4. Callback (Backend)

- **Gleicher Endpoint** wie bei TherapieBericht: **POST /api/assistant-results/callback**.
- **AssistantResultController** unterscheidet über **payload.type** (therapie_bericht vs. text_assistant); userId wird aus DB über requestId + type geholt.
- **AssistantResultServiceImpl.handleCallback** speichert/aktualisiert das Result für diese requestId.

---

## 5. Frontend: Polling

- **Hook:** **useAssistantPolling.js** – **startPolling(requestId, type, ...)**. Für Text-Assistent: **type === 'text_assistant'**.
- **API:** **GET /api/text-assistant/result/{requestId}** (mit JWT).
- **Status:** **ready** → content (verarbeiteter Text) anzeigen; **error** → errorMessage; **processing** → weiter warten.
- **Timeout/Abbruch (UI):**
  - Das Frontend hat ein Polling-Timeout (aktuell 5 Minuten). Bei Timeout (oder manuellem „Abbrechen“) wird das Polling gestoppt.
  - Zusätzlich kann das Frontend die Transportdaten aufräumen: **DELETE /api/assistant-results/text_assistant/{requestId}** (JWT, user-scoped).
  - Kommt danach ein verspäteter n8n-Callback, wird er bewusst abgewiesen, weil `assistant_results` für `requestId+type` nicht mehr existiert (Backend findet keine userId → 400 „userId not found for requestId“).

---

## 6. Konfiguration (Backend)

- **n8n.webhook-text-assistant.url:** n8n-Webhook-URL für den Text-Assistent-Workflow.
- **n8n.webhook-text-assistant.secret:** Optional, X-Webhook-Key an n8n.
- **n8n.callback-secret:** Für X-N8N-Secret beim Callback (gemeinsam mit Report und Voice).

---

## 7. Ablaufdiagramm (vereinfacht)

```
[User: Anweisung + Text eingeben] → Frontend
        ↓
POST /api/text-assistant/process { userPrompt, textContent, textLength }
        ↓
Backend: DB-Eintrag (PROCESSING), POST an n8n (requestId, userId, type "text_assistant", Daten)
        ↓
Antwort: { requestId, success, message }
        ↓
n8n: Text verarbeiten → POST /api/assistant-results/callback (requestId, type, status, content)
        ↓
Backend: userId aus DB, upsert Result
        ↓
Frontend: GET /api/text-assistant/result/{requestId} (alle 3s) → bei ready: content anzeigen
```

---

## Relevante Dateien

| Bereich   | Datei / Ort |
|-----------|-------------|
| Frontend  | `TextAssistantService.js`, `AssistantResultsRepository.js`, `useAssistantPolling.js` |
| Backend   | `TextAssistantController.java`, `TextAssistantServiceImpl.java`, `AssistantResultController.java`, `AssistantResultServiceImpl.java` |
| Feature   | **backend/docs/TextAssistant-README.md** |
