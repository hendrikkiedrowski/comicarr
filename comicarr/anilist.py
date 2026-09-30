#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Comicarr is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Comicarr.  If not, see <http://www.gnu.org/licenses/>.

"""
AniList (GraphQL) integration for manga search and metadata.

Used as a manga metadata source (clean romaji/english/native titles, synopsis,
cover, status, staff) while MangaDex provides chapter-level data. AniList exposes
each series' MyAnimeList id (``idMal``), which is reused to resolve the MangaDex
entry for chapters, so no AniList-specific MangaDex resolver is needed.

Public GraphQL API, no key required: https://docs.anilist.co/
"""

import time
from datetime import datetime

import requests

import comicarr
from comicarr import logger, series_kind
from comicarr.helpers import listLibrary

ANILIST_API = "https://graphql.anilist.co"

# AniList status enum -> the shared internal vocabulary myanimelist/mangadex use.
_STATUS_MAP = {
    "RELEASING": "ongoing",
    "FINISHED": "completed",
    "NOT_YET_RELEASED": "upcoming",
    "HIATUS": "hiatus",
    "CANCELLED": "completed",
}

_last_request_time = 0.0
_rate_limit_interval = 0.7  # AniList allows ~90 req/min; stay well under.

_SEARCH_QUERY = """
query ($search: String, $page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { total currentPage hasNextPage }
    media(search: $search, type: MANGA, sort: SEARCH_MATCH) {
      id idMal
      title { romaji english native }
      synonyms
      description(asHtml: false)
      status
      chapters volumes
      countryOfOrigin
      startDate { year }
      coverImage { large medium }
      genres
      staff(perPage: 4) { edges { role node { name { full } } } }
    }
  }
}
"""

_DETAIL_QUERY = """
query ($id: Int) {
  Media(id: $id, type: MANGA) {
    id idMal
    title { romaji english native }
    synonyms
    description(asHtml: false)
    status
    chapters volumes
    countryOfOrigin
    startDate { year }
    coverImage { large medium }
    genres
    staff(perPage: 8) { edges { role node { name { full } } } }
  }
}
"""


def _rate_limit():
    """Throttle to stay within AniList's rate budget."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _rate_limit_interval:
        time.sleep(_rate_limit_interval - elapsed)
    _last_request_time = time.time()


def _make_request(query, variables):
    """POST a GraphQL query. Returns the ``data`` object or None on error."""
    _rate_limit()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": comicarr.CONFIG.CV_USER_AGENT if comicarr.CONFIG else "Comicarr/1.0",
    }
    try:
        response = requests.post(
            ANILIST_API, json={"query": query, "variables": variables}, headers=headers, timeout=30
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            logger.error("[ANILIST] GraphQL errors: %s" % payload["errors"])
            return None
        return payload.get("data")
    except requests.exceptions.Timeout:
        logger.error("[ANILIST] Request timeout")
        return None
    except requests.exceptions.RequestException as e:
        logger.error("[ANILIST] Request failed: %s" % e)
        return None
    except Exception as e:
        logger.error("[ANILIST] Unexpected error: %s" % e)
        return None


def _preferred_title(title):
    """english > romaji > native, matching how the rest of the app labels manga."""
    title = title or {}
    return title.get("english") or title.get("romaji") or title.get("native") or "Unknown"


def _alt_titles(title, synonyms):
    """Collect distinct alternate titles, primary excluded, for MangaDex matching."""
    primary = _preferred_title(title)
    out = []
    for candidate in (
        (title or {}).get("romaji"),
        (title or {}).get("native"),
        *(synonyms or []),
    ):
        if candidate and candidate != primary and candidate not in out:
            out.append(candidate)
    return out


def _staff_name(staff, role_needle=None):
    """Join staff names, optionally filtered by a role substring (e.g. "Art")."""
    names = []
    for edge in (staff or {}).get("edges", []):
        role = edge.get("role", "") or ""
        if role_needle and role_needle.lower() not in role.lower():
            continue
        name = (edge.get("node", {}).get("name", {}) or {}).get("full")
        if name:
            names.append(name)
    return ", ".join(names) if names else None


def _proxy_image_url(url):
    """Route an external image URL through the Comicarr image proxy."""
    if not url:
        return ""
    from urllib.parse import quote

    return "/api/metadata/image-proxy?url=%s" % quote(url, safe="")


def search_manga(name, limit=None, offset=None, sort=None):
    """Search AniList for manga. Response shape matches mangadex.search_manga()."""
    logger.info("[ANILIST] Searching for: %s (limit=%s, offset=%s)" % (name, limit, offset))
    comic_library = listLibrary()

    per_page = min(limit, 50) if limit else 10
    page_offset = offset or 0
    # AniList paginates by page number, not offset; derive a page from the offset.
    page = (page_offset // per_page) + 1 if per_page else 1

    data = _make_request(_SEARCH_QUERY, {"search": name, "page": page, "perPage": per_page})
    if not data or not data.get("Page"):
        return {"results": [], "pagination": {"total": 0, "limit": per_page, "offset": page_offset, "returned": 0}}

    page_data = data["Page"]
    results = []
    for media in page_data.get("media", []):
        al_id = media.get("id")
        if not al_id:
            continue
        title = _preferred_title(media.get("title"))
        year = (media.get("startDate") or {}).get("year") or "0000"
        cover = media.get("coverImage") or {}
        comic_id = series_kind.add_prefix(al_id, series_kind.SeriesProvider.ANILIST)

        haveit = "No"
        if comic_id in comic_library:
            haveit = comic_library[comic_id]
        elif title and year:
            name_key = "name:" + title.lower().strip() + ":" + str(year).strip()
            if name_key in comic_library:
                haveit = comic_library[name_key]

        year_range = [str(year)]
        if str(year).isdigit():
            current_year = datetime.now().year
            for y in range(int(year), min(int(year) + 30, current_year + 1)):
                if str(y) not in year_range:
                    year_range.append(str(y))

        description = media.get("description") or ""
        results.append(
            {
                "name": title,
                "comicyear": str(year),
                "comicid": comic_id,
                "cv_comicid": None,
                "url": "https://anilist.co/manga/%s" % al_id,
                "issues": str(media.get("chapters")) if media.get("chapters") else "0",
                "comicimage": _proxy_image_url(cover.get("large") or cover.get("medium") or ""),
                "comicthumb": _proxy_image_url(cover.get("large") or cover.get("medium") or ""),
                "publisher": _staff_name(media.get("staff")) or "Unknown",
                "description": description[:500] if description else None,
                "deck": None,
                "type": "Manga",
                "haveit": haveit,
                "lastissueid": None,
                "firstissueid": None,
                "volume": str(media.get("volumes")) if media.get("volumes") else None,
                "imprint": None,
                "seriesrange": year_range,
                "status": _STATUS_MAP.get(media.get("status"), "unknown"),
                "content_rating": "safe",
                "content_type": "manga",
                "reading_direction": "ltr" if media.get("countryOfOrigin") in ("KR", "CN") else "rtl",
                "metadata_source": "anilist",
                "external_id": str(al_id),
                "alt_titles": _alt_titles(media.get("title"), media.get("synonyms")),
                "score": None,
            }
        )

    page_info = page_data.get("pageInfo", {})
    total = page_info.get("total") or (page_offset + len(results) + (1 if page_info.get("hasNextPage") else 0))
    logger.info("[ANILIST] Search returned %d results" % len(results))
    return {
        "results": results,
        "pagination": {"total": total, "limit": per_page, "offset": page_offset, "returned": len(results)},
    }


def get_manga_details(anilist_id):
    """Fetch detailed manga metadata from AniList. Shape matches mangadex.get_manga_details().

    Includes ``mal_id`` (AniList's ``idMal``) so the caller can resolve the
    MangaDex entry for chapters via mangadex.find_by_mal_id().
    """
    numeric_id = series_kind.strip_prefix(anilist_id)
    logger.info("[ANILIST] Fetching details for manga ID: %s" % numeric_id)

    try:
        variables = {"id": int(numeric_id)}
    except (TypeError, ValueError):
        logger.error("[ANILIST] Non-numeric AniList id: %s" % numeric_id)
        return None

    data = _make_request(_DETAIL_QUERY, variables)
    if not data or not data.get("Media"):
        logger.error("[ANILIST] Failed to get details for manga %s" % numeric_id)
        return None

    media = data["Media"]
    title = _preferred_title(media.get("title"))
    year = (media.get("startDate") or {}).get("year")
    cover = media.get("coverImage") or {}
    author = _staff_name(media.get("staff"), role_needle="Story") or _staff_name(media.get("staff"))
    artist = _staff_name(media.get("staff"), role_needle="Art") or author

    return {
        "id": series_kind.add_prefix(numeric_id, series_kind.SeriesProvider.ANILIST),
        "anilist_id": str(numeric_id),
        "mal_id": str(media["idMal"]) if media.get("idMal") else None,
        "name": title,
        "alt_titles": _alt_titles(media.get("title"), media.get("synonyms")),
        "description": media.get("description") or "",
        "year": str(year) if year else None,
        "status": _STATUS_MAP.get(media.get("status"), "unknown"),
        "content_rating": "safe",
        "original_language": {"KR": "ko", "CN": "zh", "JP": "ja"}.get(media.get("countryOfOrigin"), "ja"),
        "last_chapter": str(media["chapters"]) if media.get("chapters") else None,
        "last_volume": str(media["volumes"]) if media.get("volumes") else None,
        "tags": media.get("genres") or [],
        "author": author or "Unknown",
        "artist": artist or "Unknown",
        "cover_url": cover.get("large") or cover.get("medium") or "",
        "url": "https://anilist.co/manga/%s" % numeric_id,
        "content_type": "manga",
        "reading_direction": "ltr" if media.get("countryOfOrigin") in ("KR", "CN") else "rtl",
        "metadata_source": "anilist",
        "score": None,
    }
