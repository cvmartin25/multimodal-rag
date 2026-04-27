# Platzhalter

- **Originalpfad**: `backend/src/main/java/com/example/report_AI_prototype/coachapp/controller/CoachAccessCodeController.java`
- **Bereich**: (Optional) Coach Client/Code Flows

>package com.example.report_AI_prototype.coachapp.controller;

import com.example.report_AI_prototype.coachapp.dto.CoachAccessCodeSummary;
import com.example.report_AI_prototype.coachapp.dto.CreateAccessCodeRequest;
import com.example.report_AI_prototype.coachapp.dto.CreateAccessCodeResponse;
import com.example.report_AI_prototype.coachapp.service.CoachAccessCodeService;
import com.example.report_AI_prototype.security.SecurityUtils;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/coach/access-codes")
public class CoachAccessCodeController {

    private final CoachAccessCodeService coachAccessCodeService;

    public CoachAccessCodeController(CoachAccessCodeService coachAccessCodeService) {
        this.coachAccessCodeService = coachAccessCodeService;
    }

    private UUID currentUserIdOrThrow() {
        return SecurityUtils.currentUserId()
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Unauthorized"));
    }

    @GetMapping
    public ResponseEntity<List<CoachAccessCodeSummary>> list() {
        UUID userId = currentUserIdOrThrow();
        return ResponseEntity.ok(coachAccessCodeService.list(userId));
    }

    @PostMapping
    public ResponseEntity<CreateAccessCodeResponse> create(@Valid @RequestBody CreateAccessCodeRequest request) {
        UUID userId = currentUserIdOrThrow();
        return ResponseEntity.ok(coachAccessCodeService.create(userId, request));
    }

    @PatchMapping("/{codeId}/revoke")
    public ResponseEntity<Void> revoke(@PathVariable UUID codeId) {
        UUID userId = currentUserIdOrThrow();
        coachAccessCodeService.revoke(userId, codeId);
        return ResponseEntity.noContent().build();
    }
}
Füge hier den Codeinhalt aus der Originaldatei ein.

