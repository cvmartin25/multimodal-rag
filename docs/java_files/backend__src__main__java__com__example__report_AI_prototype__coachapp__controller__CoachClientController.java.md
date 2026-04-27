# Platzhalter

- **Originalpfad**: `backend/src/main/java/com/example/report_AI_prototype/coachapp/controller/CoachClientController.java`
- **Bereich**: (Optional) Coach Client/Code Flows

package com.example.report_AI_prototype.coachapp.controller;

import com.example.report_AI_prototype.coachapp.dto.CoachClientSummary;
import com.example.report_AI_prototype.coachapp.dto.CoachClientsOverviewResponse;
import com.example.report_AI_prototype.coachapp.dto.CreateAccessCodeRequest;
import com.example.report_AI_prototype.coachapp.dto.CreateAccessCodeResponse;
import com.example.report_AI_prototype.coachapp.dto.CreateCoachClientRequest;
import com.example.report_AI_prototype.coachapp.dto.UpdateCoachClientRequest;
import com.example.report_AI_prototype.coachapp.service.CoachAccessCodeService;
import com.example.report_AI_prototype.coachapp.service.CoachClientManagementService;
import com.example.report_AI_prototype.security.SecurityUtils;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.UUID;

@RestController
@RequestMapping("/api/coach/clients")
public class CoachClientController {

    private final CoachClientManagementService coachClientManagementService;
    private final CoachAccessCodeService coachAccessCodeService;

    public CoachClientController(
        CoachClientManagementService coachClientManagementService,
        CoachAccessCodeService coachAccessCodeService
    ) {
        this.coachClientManagementService = coachClientManagementService;
        this.coachAccessCodeService = coachAccessCodeService;
    }

    private UUID currentUserIdOrThrow() {
        return SecurityUtils.currentUserId()
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Unauthorized"));
    }

    @GetMapping
    public ResponseEntity<CoachClientsOverviewResponse> list() {
        UUID userId = currentUserIdOrThrow();
        return ResponseEntity.ok(coachClientManagementService.getOverview(userId));
    }

    @PostMapping
    public ResponseEntity<CoachClientSummary> create(@Valid @RequestBody CreateCoachClientRequest request) {
        UUID userId = currentUserIdOrThrow();
        return ResponseEntity.ok(coachClientManagementService.create(userId, request));
    }

    @PatchMapping("/{clientId}")
    public ResponseEntity<CoachClientSummary> update(
        @PathVariable UUID clientId,
        @Valid @RequestBody UpdateCoachClientRequest request
    ) {
        UUID userId = currentUserIdOrThrow();
        return ResponseEntity.ok(coachClientManagementService.update(userId, clientId, request));
    }

    @PostMapping("/{clientId}/access-codes")
    public ResponseEntity<CreateAccessCodeResponse> createClientCode(
        @PathVariable UUID clientId,
        @Valid @RequestBody CreateAccessCodeRequest request
    ) {
        UUID userId = currentUserIdOrThrow();
        return ResponseEntity.ok(coachAccessCodeService.createForClient(userId, clientId, request));
    }

    @DeleteMapping("/{clientId}")
    public ResponseEntity<Void> delete(@PathVariable UUID clientId) {
        UUID userId = currentUserIdOrThrow();
        coachClientManagementService.delete(userId, clientId);
        return ResponseEntity.noContent().build();
    }
}


