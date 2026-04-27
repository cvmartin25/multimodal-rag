# Platzhalter

- **Originalpfad**: `backend/src/main/java/com/example/report_AI_prototype/coachapp/controller/OnboardingController.java`
- **Bereich**: Tenancy/Bootstrap (coachProfileId, States, Rollenlogik)

package com.example.report_AI_prototype.coachapp.controller;

import com.example.report_AI_prototype.coachapp.domain.model.CoachProfile;
import com.example.report_AI_prototype.coachapp.dto.ActivateCoachCodeRequest;
import com.example.report_AI_prototype.coachapp.dto.BootstrapResponse;
import com.example.report_AI_prototype.coachapp.dto.CoachRegistrationRequest;
import com.example.report_AI_prototype.coachapp.service.BootstrapService;
import com.example.report_AI_prototype.coachapp.service.ClientActivationService;
import com.example.report_AI_prototype.coachapp.service.CoachOnboardingService;
import com.example.report_AI_prototype.security.SecurityUtils;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.UUID;

@RestController
@RequestMapping("/api/onboarding")
public class OnboardingController {

    private final BootstrapService bootstrapService;
    private final CoachOnboardingService coachOnboardingService;
    private final ClientActivationService clientActivationService;

    public OnboardingController(
        BootstrapService bootstrapService,
        CoachOnboardingService coachOnboardingService,
        ClientActivationService clientActivationService
    ) {
        this.bootstrapService = bootstrapService;
        this.coachOnboardingService = coachOnboardingService;
        this.clientActivationService = clientActivationService;
    }

    private UUID currentUserIdOrThrow() {
        return SecurityUtils.currentUserId()
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Unauthorized"));
    }

    @GetMapping("/bootstrap")
    public ResponseEntity<BootstrapResponse> bootstrap() {
        UUID userId = currentUserIdOrThrow();
        return ResponseEntity.ok(bootstrapService.getBootstrap(userId));
    }

    @PostMapping("/register-coach")
    public ResponseEntity<BootstrapResponse> registerCoach(@Valid @RequestBody CoachRegistrationRequest request) {
        UUID userId = currentUserIdOrThrow();
        CoachProfile profile = coachOnboardingService.registerCoach(
            userId,
            request.getDisplayName(),
            request.getMaxActiveClients()
        );

        // Hinweis: Da wir in CoachOnboardingService aktuell keine User-Role in DB setzen,
        // bauen wir die Antwort hier direkt wie im Frontend benötigt.
        BootstrapResponse response = new BootstrapResponse();
        response.setRole("coach");
        response.setState("COACH_ACTIVE");
        response.setCoachProfileId(profile.getId());
        response.setCoachDisplayName(profile.getDisplayName());
        return ResponseEntity.ok(response);
    }

    @PostMapping("/activate-code")
    public ResponseEntity<BootstrapResponse> activateCode(@Valid @RequestBody ActivateCoachCodeRequest request) {
        UUID userId = currentUserIdOrThrow();
        clientActivationService.activate(userId, request.getCode());
        return ResponseEntity.ok(bootstrapService.getBootstrap(userId));
    }
}


