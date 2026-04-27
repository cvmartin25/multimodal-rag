# Platzhalter

- **Originalpfad**: `backend/src/main/java/com/example/report_AI_prototype/service/impl/TextAssistantServiceImpl.java`
- **Bereich**: n8n Callback + Polling Pattern (sichere Job-/Chat-Callbacks)

package com.example.report_AI_prototype.service.impl;

import com.example.report_AI_prototype.dto.TextAssistantRequest;
import com.example.report_AI_prototype.dto.TextAssistantResponse;
import com.example.report_AI_prototype.model.Status;
import com.example.report_AI_prototype.repository.AssistantResultRepository;
import com.example.report_AI_prototype.service.TextAssistantService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestClient;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Service Implementation für Text-Assistent mit n8n-Integration
 * 
 * Zweck: Asynchrone n8n-Integration für Textverarbeitung
 * Rechtsgrundlage: Art. 6 DSGVO (Vertragserfüllung) - Textverarbeitung
 * Datenminimierung: Nur notwendige Daten für Textverarbeitung
 * Speicherdauer: Temporär (nur während der Anfrage)
 */
@Service
public class TextAssistantServiceImpl implements TextAssistantService {

    private final RestClient http;
    private final AssistantResultRepository assistantResultRepository;

    @Value("${n8n.webhook-text-assistant.url}")
    private String n8nWebhookUrl;

    @Value("${n8n.webhook-text-assistant.secret:}")
    private String n8nSecret;

    public TextAssistantServiceImpl(AssistantResultRepository assistantResultRepository) {
        this.assistantResultRepository = assistantResultRepository;
        var rf = new SimpleClientHttpRequestFactory();
        rf.setConnectTimeout(3000);
        rf.setReadTimeout(3000); // Kurzes Timeout, da fire-and-forget
        this.http = RestClient.builder().requestFactory(rf).build();
    }

    @Override
    @Transactional
    public TextAssistantResponse process(UUID userId, TextAssistantRequest request) {
        // Request validieren
        if (request == null) {
            return new TextAssistantResponse(false, null, "Request fehlt");
        }
        if (request.getTextContent() == null || request.getTextContent().trim().isEmpty()) {
            return new TextAssistantResponse(false, null, "Textinhalt ist erforderlich");
        }
        if (request.getUserPrompt() == null || request.getUserPrompt().trim().isEmpty()) {
            return new TextAssistantResponse(false, null, "Benutzer-Prompt ist erforderlich");
        }

        // Request-ID generieren
        UUID requestId = UUID.randomUUID();

        // Initialen DB-Eintrag erstellen (Status: PROCESSING)
        assistantResultRepository.upsertByRequestId(
            requestId,
            userId,
            "text_assistant",
            Status.PROCESSING,
            null,
            null
        );

        // Payload für n8n bauen
        Map<String, Object> payload = new HashMap<>();
        payload.put("version", "1");
        payload.put("event", "start");
        payload.put("requestId", requestId.toString());
        payload.put("userId", userId.toString());
        payload.put("type", "text_assistant");
        payload.put("userPrompt", request.getUserPrompt());
        payload.put("textContent", request.getTextContent());
        payload.put("textLength", request.getTextLength() != null ? request.getTextLength() : "normal");
        payload.put("timestamp", Instant.now().toString());

        try {
            // Fire-and-forget an n8n (nicht auf Antwort warten)
            var req = http.post()
                    .uri(n8nWebhookUrl)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(payload);

            if (n8nSecret != null && !n8nSecret.isBlank()) {
                req = req.header("X-Webhook-Key", n8nSecret);
            }

            req.retrieve().toBodilessEntity();

            // Response mit requestId zurückgeben
            TextAssistantResponse response = new TextAssistantResponse();
            response.setSuccess(true);
            response.setProcessedText(null); // Wird später via Polling geholt
            response.setMessage("Verarbeitung gestartet. Bitte warten Sie auf das Ergebnis.");
            response.setRequestId(requestId.toString()); // Request-ID für Polling
            
            return response;

        } catch (Exception e) {
            // Bei Fehler: Status auf ERROR setzen
            assistantResultRepository.upsertByRequestId(
                requestId,
                userId,
                "text_assistant",
                Status.ERROR,
                null,
                "Fehler beim Starten der Verarbeitung: " + e.getMessage()
            );
            
            return new TextAssistantResponse(
                    false,
                    null,
                    "Fehler beim Starten der Textverarbeitung: " + e.getMessage()
            );
        }
    }
}


