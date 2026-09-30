import type { SearchResult } from "@/types";

export const SOURCE_LABELS: Record<string, string> = {
  comicvine: "CV",
  metron: "Metron",
  mangadex: "MangaDex",
  mal: "MAL",
  anilist: "AniList",
};

const htmlParser = new DOMParser();

function stripHtml(html: string): string {
  const doc = htmlParser.parseFromString(html, "text/html");
  return doc.body.textContent || "";
}

export function isSafeUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export function getDescription(comic: SearchResult): string | null {
  if (comic.deck && comic.deck !== "None") return comic.deck;
  if (comic.description) return stripHtml(comic.description);
  return null;
}

export function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, max).trimEnd() + "…";
}

export function getCoverUrl(comic: SearchResult): string | undefined {
  return comic.comicthumb || comic.image || comic.comicimage || undefined;
}

/** MangaDex serves each cover at fixed widths; search returns the 256px one. */
const MANGADEX_THUMB =
  /^(https:\/\/uploads\.mangadex\.org\/covers\/.+)\.256\.jpg$/;

/**
 * Cover for a grid card, which renders far larger than a list thumbnail.
 * Prefers the full image over the thumb (Comic Vine's thumb is avatar-sized)
 * and asks MangaDex for its 512px rendition.
 */
export function getCardCoverUrl(comic: SearchResult): string | undefined {
  const url = comic.comicimage || comic.image || comic.comicthumb || undefined;
  return url?.replace(MANGADEX_THUMB, "$1.512.jpg");
}

/** Providers send "0000" or "0" for an unknown year; treat those as absent. */
export function knownYear(year: string | number | null | undefined) {
  const text = String(year ?? "").trim();
  return text && Number(text) > 0 ? text : null;
}

/** An issue or chapter count of zero means the provider doesn't know it. */
export function knownCount(count: string | number | null | undefined) {
  const n = Number(count);
  return Number.isFinite(n) && n > 0 ? n : null;
}
