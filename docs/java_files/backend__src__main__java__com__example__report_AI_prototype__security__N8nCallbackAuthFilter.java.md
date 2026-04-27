# Platzhalter

- **Originalpfad**: `backend/src/main/java/com/example/report_AI_prototype/security/N8nCallbackAuthFilter.java`
- **Bereich**: n8n Callback + Polling Pattern (sichere Job-/Chat-Callbacks)

package com.example.report_AI_prototype.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * SECURITY AUDIT-DOKUMENTATION:
 * 
 * Zweck: Authentifizierung von n8n-Callback-Requests über Secret-Header
 * 
 * Sicherheitsmechanismen:
 * - Secret-basierte Authentifizierung über X-N8N-Secret Header
 * - Nur für /api/results/callback Endpunkte aktiv
 * - Secret wird aus Konfiguration geladen (n8n.callback-secret)
 * - HTTP 401 bei fehlendem oder falschem Secret
 * 
 * Ablauf:
 * 1. Request-URI wird auf /api/results/callback geprüft
 * 2. X-N8N-Secret Header wird extrahiert
 * 3. Secret wird mit konfiguriertem Wert verglichen
 * 4. Bei Erfolg: Request wird durchgelassen
 * 5. Bei Fehler: HTTP 401 Unauthorized
 * 
 * Sicherheitslücken:
 * - HMAC-Validierung ist deaktiviert (auskommentiert)
 * - Keine Timestamp-Validierung gegen Replay-Angriffe
 * - Secret wird im Klartext übertragen
 * - Keine Rate-Limiting für Callback-Endpunkte
 * 
 * Compliance: Einfache Authentifizierung für interne n8n-Integration
 */
public class N8nCallbackAuthFilter extends OncePerRequestFilter {

    private final String secret;

    public N8nCallbackAuthFilter(String secret) {
        this.secret = secret;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {

        if (request.getRequestURI().startsWith("/api/results/callback") || 
            request.getRequestURI().startsWith("/api/assistant-results/callback")) {
            String header = request.getHeader("X-N8N-Secret");

            if (header == null) {
                response.sendError(HttpServletResponse.SC_UNAUTHORIZED, "Missing N8N Secret");
                return;
            }
            if (!header.equals(secret)) {
                response.sendError(HttpServletResponse.SC_UNAUTHORIZED, "Invalid N8N Secret");
                return;
            }
        }

        filterChain.doFilter(request, response);
    }
}



