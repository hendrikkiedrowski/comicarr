#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""A MangaDex chapter title is trusted only when the chosen chapter is in the
reader's first configured language; otherwise the issue is named "Chapter N".

MangaDex chapter titles are scanlator free text and are frequently in another
language (or absent) even on an upload tagged as the preferred one, so surfacing
them verbatim put Portuguese/Arabic names on an English library.
"""

from unittest.mock import MagicMock, patch


def _run_populate(chapters, preferred_languages):
    """Invoke the importer's chapter populator with everything external mocked,
    returning {chapter_number: IssueName} from the captured issue upserts."""
    from comicarr import importer

    captured = {}

    def fake_upsert(table, values, keys):
        if table == "issues":
            captured[values["Issue_Number"]] = values["IssueName"]

    fake_db = MagicMock()
    fake_db.upsert.side_effect = fake_upsert
    fake_db.select_all.return_value = []

    with (
        patch("comicarr.CONFIG", MagicMock(AUTOWANT_ALL=False)),
        patch("comicarr.mangadex.get_all_chapters", return_value=chapters),
        patch("comicarr.mangadex.get_total_chapter_count", return_value=0),
        patch("comicarr.mangadex._get_languages", return_value=preferred_languages),
        patch("comicarr.importer.db", fake_db),
        patch("comicarr.importer._upsert_placeholder_manga_chapters", return_value=0),
        patch("comicarr.importer.helpers.now", return_value="now"),
        patch("comicarr.importer.helpers.today", return_value="today"),
    ):
        importer._populate_manga_chapters("md-x", "Test", "x", None, {"ComicID": "md-x"})

    return captured


def test_preferred_language_title_kept_others_become_chapter_n():
    chapters = [
        {"chapter": "1", "language": "en", "title": "Romance Dawn"},
        {"chapter": "5", "language": "pt-br", "title": "O Rei dos Piratas"},
        {"chapter": "15.5", "language": "ar", "title": "\u0635\u0642\u0644 \u0627\u0644\u0646\u0641\u0633"},
        {"chapter": "20", "language": "en", "title": None},
    ]
    names = _run_populate(chapters, ["en", "pt-br", "es", "ar"])

    assert names["1"] == "Romance Dawn"  # en upload, real title kept
    assert names["5"] == "Chapter 5"  # pt-br fallback -> numbered
    assert names["15.5"] == "Chapter 15.5"  # ar fallback -> numbered
    assert names["20"] == "Chapter 20"  # en but no title -> numbered
