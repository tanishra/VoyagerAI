const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
import { withAuthParams } from './api-headers';

export interface UploadedFile {
  file_id: string;
  data_url: string;
  filename: string;
  content_type: string;
  size: number;
}

export async function uploadFile(file: File): Promise<UploadedFile> {
  const formData = new FormData();
  formData.append('file', file);

  // No custom headers here — multipart/form-data (set automatically by the
  // browser for FormData bodies) is CORS-safelisted, but custom headers like
  // X-Session-Token/X-API-Key would still force a preflight OPTIONS request,
  // which some hosting proxies (e.g. Hugging Face Spaces) mishandle. Auth is
  // passed via query params instead.
  const res = await fetch(withAuthParams(`${API_URL}/upload`), {
    method: 'POST',
    body: formData,
    credentials: 'include',
  });

  if (res.status === 401) {
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload failed (${res.status})`);
  }

  return await res.json();
}
