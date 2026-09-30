---
"comicarr": minor
---

Automatic searches now back off per issue instead of re-hunting every wanted
issue on every scan. Each issue records when it was last searched, and released
issues that came up empty are held for an age-scaled cooldown — retried often
while a release is fresh, rarely once it is old — so a large backlog that the
indexers simply do not carry (for example a 1000+ chapter manga on usenet) can
no longer monopolise the serial search queue and starve everything else.
Manual and interactive searches are never held. Tune with the new
`search_cooldown_base_hours` (default 6, set 0 to disable) and
`search_cooldown_max_hours` (default 336) settings.
