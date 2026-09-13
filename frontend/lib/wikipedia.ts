export async function fetchWikipediaDescription(searchQuery: string): Promise<string | null> {
  try {
    const url = `https://en.wikipedia.org/w/api.php?action=query&format=json&origin=*&prop=extracts&exintro=true&exsentences=2&explaintext=true&titles=${encodeURIComponent(searchQuery)}`;
    const res = await fetch(url);
    const data = await res.json();
    const pages = data?.query?.pages;
    if (!pages) return null;

    const page = Object.values(pages)[0] as { extract?: string } | undefined;
    return page?.extract ?? null;
  } catch {
    return null;
  }
}
