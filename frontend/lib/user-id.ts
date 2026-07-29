const STORAGE_KEY = 'voyager_user_id';

export function getUserId(): string {
  if (typeof window === 'undefined') return 'anonymous';
  let id = localStorage.getItem(STORAGE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(STORAGE_KEY, id);
  }
  return id;
}
