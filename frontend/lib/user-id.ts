const STORAGE_KEY = 'voyager_user_id';

let inMemoryId: string | null = null;

function generateId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `id-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function getUserId(): string {
  if (typeof window === 'undefined') return 'anonymous';
  try {
    let id = localStorage.getItem(STORAGE_KEY);
    if (!id) {
      id = generateId();
      localStorage.setItem(STORAGE_KEY, id);
    }
    return id;
  } catch {
    if (!inMemoryId) inMemoryId = generateId();
    return inMemoryId;
  }
}
