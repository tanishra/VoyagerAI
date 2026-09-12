export async function fetchWikimediaImage(searchQuery: string): Promise<string | null> {
  try {
    const searchUrl = `https://commons.wikimedia.org/w/api.php?action=query&format=json&origin=*&generator=search&gsrsearch=${encodeURIComponent(searchQuery)}&gsrnamespace=6&gsrlimit=1&prop=imageinfo&iiprop=url&iiurlwidth=400`;
    const res = await fetch(searchUrl);
    const data = await res.json();
    const pages = data?.query?.pages;
    if (!pages) return null;

    const page = Object.values(pages)[0] as any;
    return page?.imageinfo?.[0]?.thumburl ?? null;
  } catch {
    return null;
  }
}
