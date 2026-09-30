#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Two levers that keep a manga search from taking minutes per chapter:
drop native-script alternates usenet can't match, and search a chapter that
belongs to a volume as that volume (so the per-issue/queued path doesn't search
c001 forever)."""

from comicarr.search import _latin_only_alternates


def test_native_script_alternates_are_dropped():
    alt = "##".join(
        [
            "One Piece c001",
            "ワンピース",  # Japanese -> drop
            "Ван Піс",  # Cyrillic -> drop
            "One Piece. Большой куш",  # mostly Cyrillic -> drop
            "وان پیس",  # Arabic -> drop
            "Wanpanman",  # romaji -> keep
        ]
    )
    kept = _latin_only_alternates(alt).split("##")
    assert kept == ["One Piece c001", "Wanpanman"]


def test_passthrough_edges():
    assert _latin_only_alternates(None) is None
    assert _latin_only_alternates("None") == "None"
    assert _latin_only_alternates("ワンピース##Ван Піс") == "None"  # all dropped
    assert _latin_only_alternates("One-Punch Man") == "One-Punch Man"
