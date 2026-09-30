---
"comicarr": patch
---

Manga backlog search now finds licensed volumes that were sitting unsearched. When a chapter had no upload in your preferred language (common for popular licensed series whose English chapters were taken down), it previously carried no volume number, so the faster volume-pack search never ran for it and only a slow, often-empty per-chapter search was tried. Comicarr now backfills the missing volume from MangaDex's language-unfiltered chapter list, the same source already used to compute the total chapter count.
