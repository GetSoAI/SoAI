# SoAIType

A warm, open UI typeface for SoAI. Derived from **Inter** (Rasmus Andersson), customized and rebranded.

## What makes it SoAIType (not just renamed Inter)

The following Inter alternates are **baked in as the default letterforms** (so the face looks distinct out of the box, while keeping Inter-grade quality):

- `cv05` — lowercase **l** with a curved tail (warmer; disambiguates l / I / 1)
- `cv10` — **open G** (spur removed)
- `cv13` — **softer t** (curved foot)
- `ss01` — **open digits** (open apertures on 4 / 6 / 9 …)
- `ss03` — **round quotes & commas**

The cold/geometric single-story `a` (`cv11`) was deliberately **not** applied — SoAIType keeps the warm double-story `a`.

## Files

- `ttf/` — 18 static fonts (Thin→Black + italics) for system install / desktop.
- `variable/` — `SoAIType[opsz,wght].ttf` (+ italic): two axes, `opsz` 14–32, `wght` 100–900.
- `woff2/` — web fonts (variable + statics).
- `soaitype.css` — ready `@font-face` (variable) + `--soaitype` stack.
- `specimen.png` — visual specimen.
- `OFL.txt` — license (see below).

## License (SIL Open Font License 1.1) — your obligations

- ✅ Use in the SoAI UI, install on systems, embed in PDFs, ship commercially — all allowed.
- ✅ **No user-facing attribution required** (no credit line in UI or PDFs).
- ⚠️ Keep `OFL.txt` alongside the font files when you distribute them.
- ⚠️ SoAIType (as a derivative) stays under OFL; don't sell the font files on their own.
- ⚠️ The original Inter copyright is retained in each font's name table (nameID 0); leave it intact.

Version 1.000 · vendor `SOAI` · based on Inter 4.001.
