#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""The manga search endpoint (/api/search/manga -> find_manga) honours the
provider selector, and adding an AniList result keeps its al- id.

Regression: the served search path had no provider param (always MAL-or-
MangaDex), and add_manga re-prefixed an al- id as MangaDex -> "md-al-...".
"""

from types import SimpleNamespace
from unittest.mock import patch


def _ctx():
    return SimpleNamespace(config=SimpleNamespace(MAL_ENABLED=False, MAL_CLIENT_ID=None, MANGADEX_ENABLED=True))


def _fake_results(tag):
    return {"results": [{"comicid": "%s-1" % tag, "name": tag, "haveit": "No"}], "pagination": {}}


def test_find_manga_dispatches_to_selected_provider():
    from comicarr.app.search import service

    with (
        patch("comicarr.anilist.search_manga", return_value=_fake_results("al")) as al,
        patch("comicarr.mangadex.search_manga", return_value=_fake_results("md")) as md,
    ):
        out = service.find_manga(_ctx(), "one piece", provider="anilist")

    assert al.called and not md.called
    assert out["results"][0]["comicid"] == "al-1"
    assert out["results"][0]["in_library"] is False  # enrichment preserved


def test_find_manga_mal_without_config_errors():
    from comicarr.app.search import service

    out = service.find_manga(_ctx(), "x", provider="mal")
    assert "error" in out  # MAL selected but no client id


def test_find_manga_no_provider_keeps_auto_fallback():
    from comicarr.app.search import service

    with patch("comicarr.mangadex.search_manga", return_value=_fake_results("md")) as md:
        out = service.find_manga(_ctx(), "x")  # no provider, MAL off -> MangaDex
    assert md.called and out["results"][0]["comicid"] == "md-1"


def test_add_manga_keeps_anilist_prefix():
    from comicarr import series_kind

    # provider_of + add_prefix must not turn al-30013 into md-al-30013
    provider = series_kind.provider_of("al-30013")
    assert provider is series_kind.SeriesProvider.ANILIST
    assert series_kind.add_prefix("al-30013", provider) == "al-30013"
