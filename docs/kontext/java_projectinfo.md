
welche infos oder code teile muss cursor kennen für das python projekt, damit er gleich richtig baut

Damit Cursor im Python‑Projekt “gleich richtig baut”, muss er vor allem eure harten Contracts aus dem Java‑Backbone kennen (Tenancy/IDs/Status/StorageKeys) und das n8n‑Integrationsmuster. Das sind die wichtigsten Infos/Code‑Stellen, die du ihm (als Kontext) mitgeben solltest:

#1) Tenancy & Rolle: coachProfileId kommt aus Java/DB (nicht aus Client)
Warum wichtig: Python darf niemals “coachId” aus dem Chat annehmen; alles muss über verifizierten Kontext laufen (Java/n8n).
Code: BootstrapService bestimmt State/Role und liefert coachProfileId.

BootstrapService.java
Lines 34-69
public BootstrapResponse getBootstrap(UUID userId) {
  User user = userRepository.findById(userId).orElseThrow(...);
  response.setRole(user.getRole());
  if (role == UserRole.COACH) { ... response.setCoachProfileId(profile.getId()); ... }
  CoachClient activeMembership = coachClientRepository.findActiveByClientUserId(userId, now).orElse(null);
  if (activeMembership != null) {
    response.setState("CLIENT_ACTIVE");
    response.setCoachProfileId(activeMembership.getCoachProfileId());
    ...
  }
  response.setState("NEEDS_COACH_CODE");
  return response;
}
Anweisung für Python: Jede Query/Index‑Operation muss mindestens coachProfileId (oder documentId/videoId) haben und serverseitig filtern.

#2) Dokument-Upload & Statusmaschine (Triggerpunkt fürs Indexing)
Warum wichtig: Indexing erst nach complete-upload (Status uploaded), niemals bei pending_upload.
Code: Upload‑Flow im Frontend und Statusregeln im Backend.

CoachDocumentController.java
Lines 45-60
@PostMapping("/documents:begin-upload") ...
@PostMapping("/documents/{documentId}:complete-upload") ...
@DeleteMapping("/documents/{documentId}") ...

CoachDocumentService.java
Lines 41-122
beginUpload(...) -> createPendingUpload(... status 'pending_upload') + presigned PUT
completeUpload(...) -> only pending_upload can be completed -> status 'uploaded'
delete(...) -> blocks if status is processing/active
Anweisung für Python: “Index job” startet auf uploaded und muss später processing/active/error zurückschreiben (über Java‑Endpoint oder DB).

#3) Storage-Key Konvention (Originaldokument) – Python darf keine eigenen Keys erfinden
Warum wichtig: Evidence/Derivate müssen auf das Original referenzieren; spätere Resolve/Signing muss konsistent bleiben.
Code:

CoachDocumentService.java
Lines 129-131
private String buildStorageKey(UUID coachProfileId, UUID documentId) {
  return "mycoach/" + coachProfileId + "/documents/" + documentId + "/original";
}
Anweisung für Python:

Original liegt immer unter diesem Key.
Derivate (z. B. Seitenbilder) sollten unter demselben Namespace liegen, z. B.
mycoach/{coachProfileId}/documents/{documentId}/pages/{page}.png
(nicht irgendwo anders).

#4) Sicherheits-/Callback-Prinzip: IDs nie aus Payload “vertrauen”
Das Repo hat bereits ein gutes Pattern: n8n callbackt, aber Java holt userId aus DB anhand requestId (nicht aus Payload).

Warum wichtig: Wenn ihr Python/n8n später “Index fertig” zurückmelden lasst, soll es nach dem gleichen Muster laufen.
Code:

AssistantResultController.java
Lines 40-74
// Security: userId IMMER aus DB holen (über requestId), nicht aus Payload
UUID userId = assistantResultService.findUserIdByRequestId(payload.requestId, payload.type)...
Anweisung für Python Tools:

Für Chat‑Tools: coachProfileId kommt aus verifiziertem Kontext (n8n bekommt ihn aus Java).
Für Job‑Callbacks: arbeite ID-basiert (documentId/jobId), nicht “trust me bro”.

#5) Welche API-Endpunkte es im Backbone schon gibt (damit Python sich dran orientiert)
Cursor sollte wissen, dass es bereits diese CoachApp-API gibt (Python soll das nicht duplizieren):

Bootstrap/Onboarding: /api/onboarding/bootstrap, /api/onboarding/activate-code, /api/onboarding/register-coach
Coach Ops: /api/coach/clients, /api/coach/access-codes
Documents: /api/coach/documents, :begin-upload, :complete-upload
Quelle: frontend/src/services/CoachAppService.js (gute kompakte Übersicht).


CoachAppService.js
Lines 4-92
async getBootstrap() { ... '/api/onboarding/bootstrap' }
...
async beginCoachDocumentUpload(payload) { ... '/api/coach/documents:begin-upload' }
async completeCoachDocumentUpload(documentId, payload) { ... `/api/coach/documents/${documentId}:complete-upload` }
Was du Cursor (für Python) als “Pflichtenheft” in 6 Sätzen geben kannst
Python ist Processing Plane: indexiert documentId/videoId → schreibt Embeddings + Evidence‑Metadaten in Supabase (filterbar nach coachProfileId).
Tenancy ist hart: jede Query ist scoped auf coachProfileId; Python akzeptiert keine “freien” coachIds aus User‑Input.
Dokumente werden erst nach Java complete-upload verarbeitet (status=uploaded).
StorageKeys sind canon: Original mycoach/{coachProfileId}/documents/{documentId}/original; Derivate darunter.
Signed URLs nur just-in-time, keine persistenten public URLs speichern.
n8n ist Chat/Agent Runtime: Python bietet wenige HTTP‑Tools (/rag/query, /media/resolve, /index/document, …).
Wenn du willst, formuliere ich dir daraus einen copy‑paste “Cursor Context Prompt” (1–2 Screens) für das andere Repo, inklusive vorgeschlagenen Python-Endpunkten und dem Evidence‑Schema, damit Cursor direkt sauber scaffolden kann.

##Liste welche files aus Java einsehbar sind:


#Tenancy/Bootstrap (Quelle von coachProfileId, States, Role-Logik)

backend/src/main/java/com/example/report_AI_prototype/coachapp/service/BootstrapService.java
backend/src/main/java/com/example/report_AI_prototype/coachapp/controller/OnboardingController.java

#Documents: Upload-Contract, Statusmaschine, Storage-Key-Konvention

backend/src/main/java/com/example/report_AI_prototype/coachapp/controller/CoachDocumentController.java
backend/src/main/java/com/example/report_AI_prototype/coachapp/service/CoachDocumentService.java
backend/src/main/java/com/example/report_AI_prototype/coachapp/repository/CoachDocumentRepository.java
frontend/src/components/coachapp/CoachDocumentsScreen.jsx

#API-Übersicht (schnellster “Index” aller CoachApp-Endpunkte fürs Frontend)

frontend/src/services/CoachAppService.js

#n8n Callback + Polling Pattern (als Blaupause für sichere Job-/Chat-Callbacks)

backend/src/main/java/com/example/report_AI_prototype/controller/AssistantResultController.java
backend/src/main/java/com/example/report_AI_prototype/security/N8nCallbackAuthFilter.java
backend/src/main/java/com/example/report_AI_prototype/service/impl/TextAssistantServiceImpl.java
frontend/src/hooks/useAssistantPolling.js

#(Optional, aber hilfreich) Coach Client/Code Flows, falls RAG später klient-/slot-abhängig werden soll

backend/src/main/java/com/example/report_AI_prototype/coachapp/service/ClientActivationService.java
backend/src/main/java/com/example/report_AI_prototype/coachapp/controller/CoachClientController.java
backend/src/main/java/com/example/report_AI_prototype/coachapp/controller/CoachAccessCodeController.java

#(Optional, als “Single Source of Truth” in Klartext)

docs/CoachApp/coachApp-S3-flow.md
docs/CoachApp/overview_coachapp_backend_flow.md
docs/CoachApp/overview_kontext.md