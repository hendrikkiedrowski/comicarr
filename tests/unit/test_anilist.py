#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Coverage for the AniList manga metadata provider: title preference,
alt-title collection, idMal passthrough (for MangaDex chapter resolution), and
the search response shape shared with the MangaDex/MAL providers."""

from unittest.mock import patch


def _media():
    return {
        "id": 30013,
        "idMal": 13,
        "title": {"romaji": "ONE PIECE", "english": "One Piece", "native": "ONE PIECE"},
        "synonyms": ["OP"],
        "description": "Pirates.",
        "status": "RELEASING",
        "chapters": None,
        "volumes": 105,
        "countryOfOrigin": "JP",
        "startDate": {"year": 1997},
        "coverImage": {"large": "https://img.anili.st/media/30013.jpg"},
        "genres": ["Action", "Adventure"],
        "staff": {"edges": [{"role": "Story & Art", "node": {"name": {"full": "Eiichiro Oda"}}}]},
    }


class TestAniListDetails:
    @patch("comicarr.anilist._make_request")
    def test_prefers_english_title_and_passes_idmal(self, mock_request):
        from comicarr import anilist

        mock_request.return_value = {"Media": _media()}
        d = anilist.get_manga_details("al-30013")

        assert d["name"] == "One Piece"  # english preferred over romaji/native
        assert d["id"] == "al-30013"
        assert d["mal_id"] == "13"  # idMal carried through for MangaDex lookup
        assert d["last_volume"] == "105"
        assert d["status"] == "ongoing"
        assert "ONE PIECE" in d["alt_titles"]  # romaji/native retained as alternates
        assert d["metadata_source"] == "anilist"

    @patch("comicarr.anilist._make_request")
    def test_missing_media_returns_none(self, mock_request):
        from comicarr import anilist

        mock_request.return_value = {"Media": None}
        assert anilist.get_manga_details("al-999") is None


class TestAniListSearch:
    @patch("comicarr.anilist.listLibrary", return_value={})
    @patch("comicarr.anilist._make_request")
    def test_search_shape_matches_other_providers(self, mock_request, _lib):
        from comicarr import anilist

        mock_request.return_value = {"Page": {"pageInfo": {"total": 1, "hasNextPage": False}, "media": [_media()]}}
        result = anilist.search_manga("one piece", limit=10)

        assert result["pagination"]["returned"] == 1
        row = result["results"][0]
        assert row["comicid"] == "al-30013"
        assert row["name"] == "One Piece"
        assert row["content_type"] == "manga"
        assert row["metadata_source"] == "anilist"
