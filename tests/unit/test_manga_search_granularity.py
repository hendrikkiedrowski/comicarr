#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""The manga backlog scan searches by volume, not per chapter.

Licensed manga has no per-chapter NZB releases -- indexers carry volumes -- so
searching each wanted chapter as c001 never matched and Have stayed 0.
_collapse_manga_search_targets routes wanted rows through the blended plan:
one volume search per back-catalogue volume, chapters only past the last volume.
"""

from unittest.mock import MagicMock, patch


def _issue(iss_id, chapter, volume, status="Wanted"):
    return {
        "IssueID": iss_id,
        "ComicID": "md-x",
        "ChapterNumber": chapter,
        "VolumeNumber": volume,
        "Status": status,
        "Issue_Number": chapter,
    }


def test_volume_backcatalogue_collapses_frontier_chapter_kept():
    from comicarr import search

    all_issues = [
        _issue("md-x-ch1", "1", "1"),
        _issue("md-x-ch2", "2", "1"),
        _issue("md-x-ch3", "3", "1"),
        _issue("md-x-ch100", "100", None),  # beyond last volume -> frontier chapter
    ]
    wanted = [{"ComicID": "md-x", "IssueID": i["IssueID"], "Issue_Number": i["ChapterNumber"]} for i in all_issues]

    comic = {"ComicID": "md-x", "ContentType": "manga", "MonitorMode": "blended"}
    fake_db = MagicMock()
    fake_db.select_one.return_value = comic
    fake_db.select_all.return_value = all_issues

    with (
        patch("comicarr.search.db", fake_db),
        patch("comicarr.search.series_kind.is_manga", return_value=True),
    ):
        out = search._collapse_manga_search_targets(wanted)

    volume_jobs = [r for r in out if r.get("manga_target", {}).get("kind") == "volume"]
    chapter_jobs = [r for r in out if "manga_target" not in r]

    assert len(volume_jobs) == 1  # ch1/2/3 collapse to one v01 search
    assert volume_jobs[0]["manga_target"]["number"] == "1"
    assert volume_jobs[0]["IssueID"] == "md-x-ch1"  # first wanted chapter is the carrier
    assert [r["IssueID"] for r in chapter_jobs] == ["md-x-ch100"]  # frontier stays a chapter


def test_non_manga_results_pass_through():
    from comicarr import search

    wanted = [{"ComicID": "cv-1", "IssueID": "cv-1-i1", "Issue_Number": "1"}]
    fake_db = MagicMock()
    fake_db.select_one.return_value = {"ComicID": "cv-1", "ContentType": "comic"}

    with (
        patch("comicarr.search.db", fake_db),
        patch("comicarr.search.series_kind.is_manga", return_value=False),
    ):
        out = search._collapse_manga_search_targets(wanted)

    assert out == wanted
