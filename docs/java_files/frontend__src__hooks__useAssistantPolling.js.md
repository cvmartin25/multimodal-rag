# Platzhalter

- **Originalpfad**: `frontend/src/hooks/useAssistantPolling.js`
- **Bereich**: n8n Callback + Polling Pattern (sichere Job-/Chat-Callbacks)

import { useRef, useCallback } from 'react';
import { assistantResultsRepository } from '../repositories/AssistantResultsRepository.js';

/**
 * Polling Hook für Assistant-Verarbeitungsergebnisse
 * 
 * Verwendung: TherapieBerichtTemp und TextAssistant
 * Pattern: Genau wie usePolling.js für Voice Results
 */
export function useAssistantPolling() {
  const pollIntervalRef = useRef(null);

  const startPolling = useCallback((requestId, type, onStatusUpdate, onComplete) => {
    // Falls noch ein alter Poller läuft → stoppen
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    let elapsed = 0;
    let consecutiveErrors = 0;
    const pollInterval = 3000;   // alle 3s (Polling-Endpoints sind vom Rate-Limiting ausgenommen)
    const maxTime = 5 * 60 * 1000; // 5 Minuten
    const maxConsecutiveErrors = 5; // 5 aufeinanderfolgende Fehler = Webhook-Problem

    const stopPolling = () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };

    pollIntervalRef.current = setInterval(async () => {
      elapsed += pollInterval;

      try {
        // Je nach Type den richtigen Endpoint aufrufen
        const res = type === 'therapie_bericht'
          ? await assistantResultsRepository.getTherapieBerichtResult(requestId)
          : await assistantResultsRepository.getTextAssistantResult(requestId);
        
        consecutiveErrors = 0; // Reset error counter bei erfolgreichem API-Call
        
        if (res && res.status) {
          const status = res.status.toLowerCase();
          console.log(`Polling für ${type} Request ${requestId}: Status=${status}`);

          if (status === "ready") {
            const statusUpdate = {
              status: "ready",
              content: res.content || "Kein Ergebnis erhalten.",
              errorMessage: null,
            };
            
            onStatusUpdate(statusUpdate);
            stopPolling();
            onComplete?.();
            return;
          }

          if (status === "error") {
            onStatusUpdate({
              status: "error",
              errorMessage: res.errorMessage || "Unbekannter Fehler",
              content: null,
            });
            stopPolling();
            onComplete?.();
            return;
          }

          if (status === "processing" || status === "queued") {
            onStatusUpdate({
              status: "processing",
              content: "Verarbeitung läuft, bitte warten...",
              errorMessage: null,
            });
          }
        }
      } catch (e) {
        consecutiveErrors++;
        console.error(`Polling-Fehler für ${type} Request ${requestId} (${consecutiveErrors}/${maxConsecutiveErrors}):`, e.message);
        
        // Nach mehreren aufeinanderfolgenden Fehlern → Webhook-Problem
        if (consecutiveErrors >= maxConsecutiveErrors) {
          onStatusUpdate({
            status: "error",
            errorMessage: "Verarbeitung war nicht möglich. Bitte versuchen Sie es erneut oder kontaktieren Sie den Support.",
            content: null,
          });
          stopPolling();
          onComplete?.();
          return;
        }
      }

      if (elapsed > maxTime) {
        onStatusUpdate({
          status: "error",
          errorMessage: "Verarbeitung dauert zu lange. Bitte versuchen Sie es erneut.",
          content: null,
        });
        stopPolling();
        onComplete?.();
      }
    }, pollInterval);

    return stopPolling;
  }, []);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  return {
    startPolling,
    stopPolling,
  };
}



