# Third-party notices & licensing

**Read this before you sell.** It explains why the product zips are structured the
way they are, and the one thing you should seriously consider doing first.

---

## TL;DR

1. The presets you sell are **your own work** — a set of numeric tuning values and
   a colour LUT you generated. Selling *your own configuration* is generally
   defensible and common in the ReShade scene.
2. But a number of the **shaders** those presets drive are under
   **"all rights reserved"** and/or **non-commercial** licences — most importantly
   **iMMERSE / METEOR (Pascal Gilcher)**, which explicitly forbids monetisation of
   works using its parts.
3. **Therefore: the zips you ship contain NO third-party `.fx` shader code.** They
   contain only your files. Buyers install the free shaders themselves from the
   official ReShade installer. This keeps you out of the *redistribution* business
   entirely — the thing the licences actually prohibit.
4. **Recommendation:** for full commercial comfort, contact the shader authors
   (especially Pascal Gilcher) and get written permission / an affiliate
   arrangement. He sells his own presets commercially and is reachable on
   Patreon/Discord. This is exactly what his licence contemplates.

---

## Licence status of every shader used

| Shader / package | Author | Used in | Licence | Sell a tuned `.ini`? |
|------------------|--------|---------|---------|----------------------|
| **iMMERSE** (SMAA, MXAO) | Pascal Gilcher | T3, T4 | **Custom — "All rights reserved"**, §1 forbids public propagation, §4 forbids monetisation of works using its parts | ⚠️ Highest risk — get permission |
| **METEOR** | Pascal Gilcher | T3, T4 | Same custom licence as iMMERSE | ⚠️ Same |
| **qUINT** (Bloom, Deband) | Marty McFly | T3, T4 | **No licence file** (= all rights reserved by default) | ⚠️ Gray zone |
| **AstrayFX** (Tonemap, CAS, Levels, SMAA) | BlueSkyDefender | T1–T4 | **No licence file** | ⚠️ Gray zone |
| **brussell** (DepthHaze, Flair) | brussell | T4 | **No licence file** | ⚠️ Gray zone |
| **SweetFX / reshade-shaders** (LUT, Curves, Vibrance) | CeeJay.dk | T1–T4 | **MIT** (SweetFX) | ✅ Fine |
| **prod80** (CA, FilmGrain, LiftGammaGain) | prod80 | T2–T4 | **MIT** | ✅ Fine |
| **OtisFX** (Clarity, DOF, EyeAdaption, Lightroom) | Frans Bouma | T3, T4 | **MIT** (except PandaFX) | ✅ Fine |

"No licence file" means the author never granted any rights — under copyright law
that defaults to *all rights reserved*, so the safe assumption is the same as the
restrictive case.

---

## What your zips actually contain (and why)

`build_products.py` packages **only**:

* your `.ini` preset files (your tuning values),
* `Textures/lut.png` (the LUT your own `generate_lut.py` produced),
* your documentation (`README*.md`, `START_HERE.txt`),
* your `Tools/generate_lut.py` script.

It **refuses** to include anything ending in `.fx`, `.fxh`, `.hlsl`, `.cso`,
`.dll` or `.exe`. So you never redistribute the authors' copyrighted shader source
or binaries. The customer installs ReShade + the shader packages themselves through
the official installer — which is how ReShade presets are normally distributed
anyway, and which keeps the licence risk where it belongs (their own download from
the author's repo).

---

## What the customer is really buying

A curated configuration: the exact numbers, the colour grade, and the guides that
tie them together. That's your creative work. The heavy lifting of *rendering* is
done by free shaders the customer obtains at the source.

Because the "product" is largely factual parameter values, its copyright protection
is thinner than, say, software — which is exactly why the **Terms of Service** and
the deterrent of enforcement matter more than copyright alone. See `public/tos.html`.

---

## Attribution (ship this with the product)

The presets require these free, third-party shaders. Include a line like this in
your docs / product description:

> This preset uses free third-party ReShade shaders by **Pascal Gilcher**
> (iMMERSE/METEOR), **Marty McFly** (qUINT), **BlueSkyDefender** (AstrayFX),
> **CeeJay.dk** (SweetFX), **prod80**, **Frans Bouma** (OtisFX) and **brussell**,
> installed separately via the ReShade installer. All rights to those shaders
> remain with their authors. Not affiliated with SCS Software or the ReShade
> project.

---

## Strong recommendation

Before taking real money for the Premium tiers (which lean on iMMERSE/METEOR/qUINT):

1. Message **Pascal Gilcher** (iMMERSE/METEOR author) and ask for a commercial
   licence or affiliate arrangement. Selling tuning *for* his shaders, with his
   blessing, removes the single biggest risk.
2. Optionally do the same for the no-licence authors (qUINT, AstrayFX, brussell).
3. Have a lawyer glance at `public/tos.html`.

Selling your own preset is a normal, legitimate thing to do — this note is about
doing it cleanly, not about whether you may.
