#  Copyright (C) 2025–2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Age-scaled search backoff (the cooldown that keeps a large unfindable
backlog from monopolising the serial search queue every scan)."""

import datetime

import pytest

from comicarr.app.acquisition.models import AcquisitionIntent, Fulfillment
from comicarr.app.acquisition.policy import (
    EligibilityInput,
    evaluate_eligibility,
    search_cooldown_hours,
)

BASE = 6.0
MAX = 336.0  # 14 days


def test_curve_new_release_uses_base():
    assert search_cooldown_hours(0, BASE, MAX) == BASE
    assert search_cooldown_hours(-5, BASE, MAX) == BASE


def test_curve_doubles_per_week_and_caps():
    assert search_cooldown_hours(7, BASE, MAX) == pytest.approx(12.0)
    assert search_cooldown_hours(14, BASE, MAX) == pytest.approx(24.0)
    # Far past the cap stays at the cap, never runs away.
    assert search_cooldown_hours(3650, BASE, MAX) == MAX


def test_curve_disabled_when_base_zero():
    assert search_cooldown_hours(0, 0, MAX) == 0.0
    assert search_cooldown_hours(500, 0, MAX) == 0.0


def _released_wanted(**overrides):
    """A released, still-missing, actively-monitored issue — the shape the
    backlog scan feeds through the gate."""
    base = dict(
        series_active=True,
        paused=False,
        intent=AcquisitionIntent.POLICY,
        fulfillment=Fulfillment.MISSING,
        release_date="2026-01-01",  # released exactly on the fixed `today` below (age 0)
        apply_cooldown=True,
        cooldown_base_hours=BASE,
        cooldown_max_hours=MAX,
    )
    base.update(overrides)
    return EligibilityInput(**base)


TODAY = datetime.date(2026, 1, 1)
NOW_TS = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.timezone.utc).timestamp()


def test_recently_searched_release_is_held():
    item = _released_wanted(last_search=NOW_TS - 3600)  # 1h ago, cooldown is 6h
    decision = evaluate_eligibility(item, today=TODAY, now_ts=NOW_TS)
    assert decision.eligible is False
    assert decision.reason == "search_cooldown"


def test_cooled_down_release_becomes_eligible_again():
    item = _released_wanted(last_search=NOW_TS - 7 * 3600)  # 7h ago > 6h
    decision = evaluate_eligibility(item, today=TODAY, now_ts=NOW_TS)
    assert decision.eligible is True
    assert decision.reason == "released"


def test_never_searched_is_eligible():
    decision = evaluate_eligibility(_released_wanted(last_search=None), today=TODAY, now_ts=NOW_TS)
    assert decision.eligible is True


def test_interactive_search_ignores_cooldown():
    item = _released_wanted(last_search=NOW_TS - 60, apply_cooldown=False)
    decision = evaluate_eligibility(item, today=TODAY, now_ts=NOW_TS)
    assert decision.eligible is True


def test_old_release_uses_capped_cooldown():
    # A years-old chapter searched 10 days ago: still inside the 14-day cap.
    item = _released_wanted(release_date="2019-01-01", last_search=NOW_TS - 10 * 86400)
    assert evaluate_eligibility(item, today=TODAY, now_ts=NOW_TS).reason == "search_cooldown"
    # 15 days ago is past the cap — eligible again.
    item = _released_wanted(release_date="2019-01-01", last_search=NOW_TS - 15 * 86400)
    assert evaluate_eligibility(item, today=TODAY, now_ts=NOW_TS).eligible is True


def test_owned_and_paused_short_circuit_before_cooldown():
    owned = _released_wanted(fulfillment=Fulfillment.DOWNLOADED, last_search=NOW_TS - 60)
    assert evaluate_eligibility(owned, today=TODAY, now_ts=NOW_TS).reason == "owned"
    paused = _released_wanted(paused=True, last_search=NOW_TS - 60)
    assert evaluate_eligibility(paused, today=TODAY, now_ts=NOW_TS).reason == "paused"


def test_disabled_base_never_holds():
    item = _released_wanted(last_search=NOW_TS - 1, cooldown_base_hours=0)
    assert evaluate_eligibility(item, today=TODAY, now_ts=NOW_TS).eligible is True
