# Platzhalter

- **Originalpfad**: `backend/src/main/java/com/example/report_AI_prototype/controller/AssistantResultController.java`
- **Bereich**: n8n Callback + Polling Pattern (sichere Job-/Chat-Callbacks)

package com.example.report_AI_prototype.controller;

import com.example.report_AI_prototype.dto.AssistantCallbackPayload;
import com.example.report_AI_prototype.dto.AssistantResultDto;
import com.example.report_AI_prototype.model.AssistantResultRecord;
import com.example.report_AI_prototype.security.SecurityUtils;
import com.example.report_AI_prototype.service.AssistantResultService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.UUID;

/**
 * Controller für Assistant-Verarbeitungsergebnisse
 * 
 * Endpoints:
 * - POST /api/assistant-results/callback - n8n Callback (permitAll)
 * - GET /api/therapie-bericht-temp/result/{requestId} - Polling für TherapieBericht
 * - GET /api/text-assistant/result/{requestId} - Polling für TextAssistant
 */
@RestController
@RequestMapping("/api")
public class AssistantResultController {

    private static final Logger log = LoggerFactory.getLogger(AssistantResultController.class);

    private final AssistantResultService assistantResultService;
    private final ObjectMapper objectMapper;

    public AssistantResultController(AssistantResultService assistantResultService, ObjectMapper objectMapper) {
        this.assistantResultService = assistantResultService;
        this.objectMapper = objectMapper;
    }

    /**
     * n8n Callback für Assistant-Verarbeitungen (permitAll)
     * 
     * Empfängt Ergebnisse von n8n für TherapieBerichtTemp und TextAssistant
     * Security: userId wird IMMER aus DB geholt (über requestId), nicht aus Payload
     * - Verhindert Security-Bypass durch falschen userId im Payload
     * - Genau wie bei Voice Results (dort wird userId über fileId indirekt geholt)
     * 
     * Format: Genau wie bei Voice Results (/api/results/callback)
     * - n8n sendet Array: [{"requestId": "...", "status": "READY", ...}]
     * - Jackson parsed automatisch das erste Element wenn Array
     */
    @PostMapping("/assistant-results/callback")
    public ResponseEntity<AssistantResultDto> callback(@RequestBody String rawBody) {
        try {
            AssistantCallbackPayload payload = objectMapper.readValue(rawBody, AssistantCallbackPayload.class);
            
            if (payload.requestId == null || payload.type == null) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "requestId and type required");
            }

            // Security: userId IMMER aus DB holen (nicht aus Payload)
            // Genau wie bei Voice Results - dort wird userId über fileId indirekt geholt
            UUID userId = assistantResultService.findUserIdByRequestId(payload.requestId, payload.type)
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "userId not found for requestId"));

            AssistantResultRecord r = assistantResultService.handleCallback(
                payload.requestId,
                userId,
                payload.type,
                payload.status,
                payload.content,
                payload.errorMessage
            );

            // Verwende AssistantResultDto (wie ResultDto bei Voice Results)
            // Status wird als Enum serialisiert → UPPERCASE ("PROCESSING", "READY")
            AssistantResultDto dto = AssistantResultDto.from(r);
            return ResponseEntity.ok(dto);

        } catch (Exception e) {
            log.error("Fehler beim Verarbeiten des Assistant-Callbacks", e);
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Callback parse/handle failed: " + e.getMessage());
        }
    }

    private UUID currentUserIdOrThrow() {
        return SecurityUtils.currentUserId()
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Unauthorized"));
    }

    /**
     * GET /api/therapie-bericht-temp/result/{requestId}
     * 
     * Polling-Endpoint für TherapieBericht Ergebnisse
     * Status wird als Enum serialisiert → UPPERCASE ("PROCESSING", "READY")
     * Frontend muss .toLowerCase() machen (wie bei Voice Results)
     */
    @GetMapping("/therapie-bericht-temp/result/{requestId}")
    public ResponseEntity<AssistantResultDto> getTherapieBerichtResult(@PathVariable("requestId") UUID requestId) {
        UUID userId = currentUserIdOrThrow();
        return assistantResultService.getByRequestIdForUser(userId, requestId, "therapie_bericht")
                .map(r -> ResponseEntity.ok(AssistantResultDto.from(r)))
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Result not found"));
    }

    /**
     * GET /api/text-assistant/result/{requestId}
     * 
     * Polling-Endpoint für TextAssistant Ergebnisse
     * Status wird als Enum serialisiert → UPPERCASE ("PROCESSING", "READY")
     * Frontend muss .toLowerCase() machen (wie bei Voice Results)
     */
    @GetMapping("/text-assistant/result/{requestId}")
    public ResponseEntity<AssistantResultDto> getTextAssistantResult(@PathVariable("requestId") UUID requestId) {
        UUID userId = currentUserIdOrThrow();
        return assistantResultService.getByRequestIdForUser(userId, requestId, "text_assistant")
                .map(r -> ResponseEntity.ok(AssistantResultDto.from(r)))
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Result not found"));
    }
}




