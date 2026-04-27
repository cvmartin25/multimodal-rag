# Platzhalter

- **Originalpfad**: `frontend/src/services/CoachAppService.js`
- **Bereich**: API-Übersicht (Index aller CoachApp-Endpunkte fürs Frontend)

import { baseApiService } from './BaseApiService';

class CoachAppService {
  async getBootstrap() {
    return baseApiService.apiFetch('/api/onboarding/bootstrap', { method: 'GET' });
  }

  async registerCoach(payload) {
    return baseApiService.apiFetch('/api/onboarding/register-coach', {
      method: 'POST',
      body: payload,
    });
  }

  async activateCode(payload) {
    return baseApiService.apiFetch('/api/onboarding/activate-code', {
      method: 'POST',
      body: payload,
    });
  }

  async listAccessCodes() {
    return baseApiService.apiFetch('/api/coach/access-codes', { method: 'GET' });
  }

  async createAccessCode(payload) {
    return baseApiService.apiFetch('/api/coach/access-codes', {
      method: 'POST',
      body: payload,
    });
  }

  async revokeAccessCode(codeId) {
    return baseApiService.apiFetch(`/api/coach/access-codes/${codeId}/revoke`, {
      method: 'PATCH',
    });
  }

  async listCoachClients() {
    return baseApiService.apiFetch('/api/coach/clients', { method: 'GET' });
  }

  async createCoachClient(payload) {
    return baseApiService.apiFetch('/api/coach/clients', {
      method: 'POST',
      body: payload,
    });
  }

  async updateCoachClient(clientId, payload) {
    return baseApiService.apiFetch(`/api/coach/clients/${clientId}`, {
      method: 'PATCH',
      body: payload,
    });
  }

  async createClientAccessCode(clientId, payload) {
    return baseApiService.apiFetch(`/api/coach/clients/${clientId}/access-codes`, {
      method: 'POST',
      body: payload,
    });
  }

  async deleteCoachClient(clientId) {
    return baseApiService.apiFetch(`/api/coach/clients/${clientId}`, {
      method: 'DELETE',
    });
  }

  async listCoachDocuments() {
    return baseApiService.apiFetch('/api/coach/documents', { method: 'GET' });
  }

  async beginCoachDocumentUpload(payload) {
    return baseApiService.apiFetch('/api/coach/documents:begin-upload', {
      method: 'POST',
      body: payload,
    });
  }

  async completeCoachDocumentUpload(documentId, payload) {
    return baseApiService.apiFetch(`/api/coach/documents/${documentId}:complete-upload`, {
      method: 'POST',
      body: payload,
    });
  }

  async deleteCoachDocument(documentId) {
    return baseApiService.apiFetch(`/api/coach/documents/${documentId}`, {
      method: 'DELETE',
    });
  }
}

export const coachAppService = new CoachAppService();



