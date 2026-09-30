import { useConfig } from "@/hooks/useConfig";

export interface MangaProvider {
  value: "mangadex" | "mal" | "anilist";
  label: string;
}

// AniList needs no API key (public GraphQL), so it is always available; MangaDex
// and MAL appear only when configured. MangaDex still supplies chapters for
// whichever provider a series is added from.
export function useMangaProviders(
  config: ReturnType<typeof useConfig>["data"],
) {
  const providers: MangaProvider[] = [{ value: "anilist", label: "AniList" }];
  if (config?.mangadex_enabled)
    providers.unshift({ value: "mangadex", label: "MangaDex" });
  if ((config?.mal_enabled as boolean | undefined) === true)
    providers.push({ value: "mal", label: "MyAnimeList" });
  return providers;
}

export function useContentSources() {
  const { data: config } = useConfig();
  const mangaProviders = useMangaProviders(config);
  return {
    comicsEnabled: config?.comicvine_enabled ?? true,
    comicsConfigured:
      (config?.comicvine_api_set as boolean | undefined) ?? false,
    // AniList is always in mangaProviders, so manga search is always available.
    mangaEnabled: mangaProviders.length > 0,
    mangaProviders,
    isLoaded: !!config,
  };
}
