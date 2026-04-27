# Platzhalter

- **Originalpfad**: `docs/CoachApp/overview_coachapp_backend_flow.md`
- **Bereich**: (Optional) Single Source of Truth (Klartext)

## CoachApp Backend-Flow (konsolidierter Stand)

Dieses Dokument ist die aktuelle „Single Source of Truth“ für den CoachApp-Backend-Flow nach den letzten Erweiterungen:

- Client-Bindung über Dashboard-Client + Code + eingeloggten Enduser
- Coach-Client-Management (anlegen, Status ändern, löschen)
- Code-Revoke
- Bootstrap mit client-spezifischen Feldern für UI

## Zielbild

1. User loggt sich über Clerk ein -> Backend mapped/erstellt `users`.
2. `bootstrap` entscheidet den App-Flow (`COACH_ACTIVE`, `CLIENT_ACTIVE`, `NEEDS_COACH_CODE`).
3. Coach verwaltet Clients im Dashboard.
4. Codes werden für konkrete Dashboard-Clients erzeugt.
5. Endkunde löst Code ein und wird an genau diesen Client gebunden.
6. Zugriff läuft über `coach_clients` (`status` + `access_until`), nicht über Token-Claims.

---

## Komponenten / Zuständigkeiten

- **Security / User-Mapping**
  - `ClerkUserMappingFilter`
  - `UserServiceImpl` / `UserRepository`
- **Onboarding**
  - `OnboardingController`
  - `BootstrapService`
  - `CoachOnboardingService`
  - `ClientActivationService`
- **Coach-Funktionen**
  - `CoachAccessCodeController` / `CoachAccessCodeService`
  - `CoachClientController` / `CoachClientManagementService`
- **Repositories**
  - `CoachProfileRepository`
  - `CoachSubscriptionRepository`
  - `CoachClientRepository`
  - `CoachAccessCodeRepository`

---

## Datenmodell (relevante Tabellen)

- `users` (inkl. `role`)
- `coach_profiles`
- `coach_subscriptions` (`max_active_clients`, `status`)
- `coach_clients`
  - `client_user_id` ist nullable (für vorab angelegte Clients)
  - `client_first_name`, `client_last_name`
  - `status`, `access_until`
- `coach_access_codes`
  - `code_hash`, `status`, `expires_at`, `max_uses`, `used_count`
  - `coach_client_id` (Bindung auf konkreten Dashboard-Client)

---

## 0) Login & User-Mapping

- JWT wird validiert.
- `clerkId = JWT.sub` wird gelesen.
- `ensureUser(clerkId)` legt bei Bedarf `users`-Eintrag mit `role='user'` an.
- `AppPrincipal` enthält `userId`, `clerkId`, `role`.

---

## 1) Bootstrap als zentraler Router

Endpoint: `GET /api/onboarding/bootstrap`

`BootstrapService.getBootstrap(userId)`:

- **Coach (`role=coach`)**
  - `state = COACH_ACTIVE`
  - liefert `coachProfileId`, `coachDisplayName`.
- **Client mit aktiver Membership**
  - `state = CLIENT_ACTIVE`
  - liefert `coachProfileId`, `accessUntil`, `coachDisplayName`
  - liefert zusätzlich `clientFirstName`, `clientLastName` (für UI-Gruß).
- **sonst**
  - `state = NEEDS_COACH_CODE`.

---

## 2) Coach-Registrierung

Endpoint: `POST /api/onboarding/register-coach`

- setzt `users.role = coach`
- erstellt `coach_profile`
- erstellt `coach_subscription` (default `max_active_clients = 20`, `status=active`)
- Response orientiert sich an `COACH_ACTIVE`.

---

## 3) Coach-Client-Management

Basis-Endpoint: `/api/coach/clients`

- `GET /api/coach/clients`
  - liefert Overview:
    - `activeCount`
    - `maxActiveClients`
    - `remainingActiveSlots`
    - `clients[]`.
- `POST /api/coach/clients`
  - legt Client mit Vor-/Nachname an
  - initial `status=inactive`, `access_until=now`, `client_user_id=null`.
- `PATCH /api/coach/clients/{clientId}`
  - aktualisiert Name/Status
  - Status `active`/`inactive` möglich.
- `DELETE /api/coach/clients/{clientId}`
  - blockiert bei aktiv + gebunden
  - erlaubt bei inaktiv/ungebunden.

Aktuelle Löschregel:
- **aktiv + gebunden** -> `409` (`Active bound clients cannot be deleted...`)
- sonst Hard-Delete.

---

## 4) Code-Erzeugung & Code-Verwaltung

### 4.1 Allgemeine Code-Endpunkte

`/api/coach/access-codes`

- `GET` listet Codes (inkl. `coachClientId`)
- `POST` erzeugt allgemeinen Code (legacy/optional)
- `PATCH /{codeId}/revoke` setzt aktiven Code auf `revoked`.

### 4.2 Client-gebundener Code (primärer Flow)

Endpoint: `POST /api/coach/clients/{clientId}/access-codes`

Regeln:
- Coach-Client muss existieren.
- Subscription muss aktiv sein.
- **Neue Regel:** Für `active` Clients kein neuer Code (`Client is already active...`).
- Bei inaktiven Clients:
  - Slotlimit wird früh geprüft.
  - nur ein offener aktiver Code pro Client erlaubt.
- Code wird gehasht gespeichert, Klartext nur einmalig im Response.

---

## 5) Endkunden-Aktivierung

Endpoint: `POST /api/onboarding/activate-code`

Flow in `ClientActivationService`:

1. Code normalisieren + hashen, Code laden.
2. Validieren (`status active`, nicht abgelaufen, `used_count < max_uses`).
3. Subscription/Slotlimit prüfen.
4. Bindung/Activation:
   - wenn Code `coach_client_id` hat:
     - genau diesen Client laden,
     - falls bereits an anderes Konto gebunden -> Fehler,
     - falls ungebunden -> `client_user_id` setzen + aktivieren,
     - sonst reaktivieren.
   - fallback (legacy) ohne `coach_client_id` bleibt kompatibel.
5. `used_count` inkrementieren.
6. Response liefert neues `bootstrap`.

Wichtig:
- Aktivierung geschieht bei Code-Einlösung, nicht beim Code-Erzeugen.

---

## 6) Zugriffslogik aktiv/inaktiv

Aktiver Zugriff = `status='active'` und `access_until > now`.

Folgen:
- `inactive` oder abgelaufen -> `bootstrap` liefert `NEEDS_COACH_CODE`.
- Reaktivierung kann per Code-Einlösung erfolgen.
- UI-seitig wurde die Hauptlogik für Coaches auf:
  - `active`: „Inaktiv schalten“
  - `inactive`: „Code erzeugen“ oder „Löschen“
  reduziert; zusätzlicher „Aktivieren“-Button existiert derzeit nur in separater Test-Spalte.

---

## 7) Fehlerbehandlung (aktueller Stand)

- `IllegalArgumentException` -> `400`
- `IllegalStateException` -> `409`
- `DataAccessException` -> `500` (aktuell mit detaillierter Meldung für Dev-Phase)

Hinweis:
- Vor Go-Live müssen technische Rohmeldungen/DB-Details aus Responses entfernt/sanitized werden.

---

## 8) Aktuelle API-Zustände / Strings

### Bootstrap-States
- `COACH_ACTIVE`
- `CLIENT_ACTIVE`
- `NEEDS_COACH_CODE`

### Relevante Statuswerte
- Client: `active`, `inactive`
- Access-Code: `active`, `revoked` (sowie faktisch „nicht nutzbar“ bei expiry/maxUses)

---

## 9) Offene/optionale nächste Schritte

- Entscheidung finalisieren, ob manuelles `active` (Coach-Patch) im Produktflow erlaubt bleibt oder nur Reaktivierung via Code.
- Optional Soft-Delete/Archiv statt Hard-Delete für Clients.
- Optional strengere Laufzeitregel (z. B. AccessUntil nur verlängern, nie verkürzen).
- Optional Concurrency-Härtung für Slotchecks (DB-Locking-Strategie).



