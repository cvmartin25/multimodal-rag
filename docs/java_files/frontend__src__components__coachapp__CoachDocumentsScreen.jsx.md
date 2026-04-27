# Platzhalter

- **Originalpfad**: `frontend/src/components/coachapp/CoachDocumentsScreen.jsx`
- **Bereich**: Documents (Upload-Contract, Statusmaschine, Storage-Key-Konvention)

import React from 'react';
import { coachAppService } from '../../services/CoachAppService';

function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function formatBytes(bytes) {
  if (bytes == null || Number.isNaN(Number(bytes))) return '-';
  const b = Number(bytes);
  if (b < 1024) return `${b} B`;
  const kb = b / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  const gb = mb / 1024;
  return `${gb.toFixed(1)} GB`;
}

async function putToPresignedUrl(uploadUrl, file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) {
        const percent = Math.round((event.loaded / event.total) * 100);
        onProgress?.(percent);
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response);
      } else {
        reject(new Error(`Upload fehlgeschlagen: ${xhr.status} ${xhr.statusText}`));
      }
    });

    xhr.addEventListener('error', () => reject(new Error('Upload-Fehler: Netzwerkfehler')));
    xhr.addEventListener('timeout', () => reject(new Error('Upload-Fehler: Timeout')));

    xhr.timeout = 5 * 60 * 1000;
    xhr.open('PUT', uploadUrl);
    xhr.send(file);
  });
}

export function CoachDocumentsScreen() {
  const [documents, setDocuments] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');

  const [uploading, setUploading] = React.useState(false);
  const [uploadProgress, setUploadProgress] = React.useState(0);
  const [uploadError, setUploadError] = React.useState('');
  const fileInputRef = React.useRef(null);

  const loadDocuments = React.useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await coachAppService.listCoachDocuments();
      setDocuments(Array.isArray(result) ? result : []);
    } catch (e) {
      setError(e?.message || 'Dokumente konnten nicht geladen werden.');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const handleUploadSelected = async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadProgress(0);
    setUploadError('');
    setError('');

    try {
      const begin = await coachAppService.beginCoachDocumentUpload({
        originalFilename: file.name,
        mimeType: file.type || null,
        expectedSizeBytes: file.size,
      });

      const { documentId, uploadUrl } = begin || {};
      if (!documentId || !uploadUrl) {
        throw new Error('Upload Init fehlgeschlagen: keine documentId/uploadUrl erhalten');
      }

      await putToPresignedUrl(uploadUrl, file, setUploadProgress);

      await coachAppService.completeCoachDocumentUpload(documentId, {
        mimeType: file.type || null,
        sizeBytes: file.size,
      });

      if (fileInputRef.current) fileInputRef.current.value = '';
      await loadDocuments();
    } catch (e) {
      setUploadError(e?.message || 'Upload fehlgeschlagen.');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (doc) => {
    if (!doc?.id) return;
    setError('');
    try {
      await coachAppService.deleteCoachDocument(doc.id);
      await loadDocuments();
    } catch (e) {
      setError(e?.message || 'Dokument konnte nicht gelöscht werden.');
    }
  };

  return (
    <div className="flex-1 p-4 bg-gray-200 dark:bg-gray-700">
      <div className="max-w-6xl mx-auto space-y-4">
        <div className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-1">Dokumente</h2>
          <p className="text-sm text-gray-600 dark:text-gray-300">
            Lade PDFs, Markdown oder Textdateien hoch. Der Upload läuft direkt in den Object Storage (Presigned URL).
          </p>
        </div>

        <div className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Dokument hochladen</h3>

          <div className="flex flex-col md:flex-row md:items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              disabled={uploading}
              className="block w-full text-sm text-gray-700 dark:text-gray-200 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-gray-200 file:text-gray-800 hover:file:bg-gray-300 dark:file:bg-gray-700 dark:file:text-gray-100 dark:hover:file:bg-gray-600"
              accept=".pdf,.md,.txt,text/plain,text/markdown,application/pdf"
            />
            <button
              type="button"
              onClick={handleUploadSelected}
              disabled={uploading}
              className="rounded-md bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-400 text-white text-sm px-4 py-2"
            >
              {uploading ? 'Upload läuft…' : 'Upload starten'}
            </button>
            <button
              type="button"
              onClick={loadDocuments}
              disabled={uploading}
              className="rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-4 py-2 text-sm text-gray-700 dark:text-gray-200"
            >
              Neu laden
            </button>
          </div>

          {uploading ? (
            <div className="mt-4">
              <div className="flex items-center justify-between text-xs text-gray-600 dark:text-gray-300 mb-1">
                <span>Upload-Fortschritt</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="h-2 w-full rounded bg-gray-200 dark:bg-gray-700 overflow-hidden">
                <div className="h-2 bg-emerald-600" style={{ width: `${uploadProgress}%` }} />
              </div>
            </div>
          ) : null}

          {uploadError ? (
            <div className="mt-4 rounded-lg border border-red-300 bg-red-50 dark:bg-red-950/40 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300">
              {uploadError}
            </div>
          ) : null}
        </div>

        <div className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Deine Dokumente</h3>
            {loading ? <span className="text-sm text-gray-600 dark:text-gray-300">Lade…</span> : null}
          </div>

          {error ? (
            <div className="mb-4 rounded-lg border border-red-300 bg-red-50 dark:bg-red-950/40 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300">
              {error}
            </div>
          ) : null}

          {!loading ? (
            <div className="overflow-auto">
              <table className="w-full text-sm text-left">
                <thead>
                  <tr className="text-gray-600 dark:text-gray-300 border-b border-gray-200 dark:border-gray-700">
                    <th className="py-2 pr-2">Datei</th>
                    <th className="py-2 pr-2">Typ</th>
                    <th className="py-2 pr-2">Größe</th>
                    <th className="py-2 pr-2">Status</th>
                    <th className="py-2 pr-2">Erstellt</th>
                    <th className="py-2 pr-2">Uploaded</th>
                    <th className="py-2 pr-2">Aktion</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr key={doc.id} className="border-b border-gray-100 dark:border-gray-800 text-gray-800 dark:text-gray-100">
                      <td className="py-2 pr-2">{doc.originalFilename || '-'}</td>
                      <td className="py-2 pr-2">{doc.mimeType || '-'}</td>
                      <td className="py-2 pr-2">{formatBytes(doc.fileSizeBytes)}</td>
                      <td className="py-2 pr-2">{doc.status || '-'}</td>
                      <td className="py-2 pr-2">{formatDate(doc.createdAt)}</td>
                      <td className="py-2 pr-2">{formatDate(doc.uploadedAt)}</td>
                      <td className="py-2 pr-2">
                        <button
                          type="button"
                          onClick={() => handleDelete(doc)}
                          className="rounded-md border border-red-300 dark:border-red-700 px-2 py-1 text-xs text-red-700 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-950/30"
                        >
                          Löschen
                        </button>
                      </td>
                    </tr>
                  ))}
                  {documents.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-3 text-gray-600 dark:text-gray-300">Noch keine Dokumente vorhanden.</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}




