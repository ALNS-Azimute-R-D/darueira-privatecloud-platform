# BookAnything: Multi-Source Flag Search and Raster-to-SVG Conversion: Discussion and Action Plan

## From Andre:

Originally requested on 20.10.2026 and reopened on 23.10.2026 (the interview freeze is over). Improve how the
GeoLocation flag image is obtained:

1. search **several sources**;
2. if only non-SVG formats exist (PNG, JPG, JPEG, GIF, ...), **convert to SVG with the best possible quality**.

Collaborative format: each agent writes only its own sections, then debate and a joint final decision.
Earlier draft (Portuguese, 20/10) lives in the backup at
`/home/andre.nascimento/DevEnvALNS/projects/03-PoCs-And-Researches/HiringProcess/CodeAssessments/Voize/missoes-ninjas/melhoria-bandeira-multifonte-svg.md`.

---

## Analysis and Evaluation by Claude:

### 1. Where it lives today (from the 20/10 reading; re-verify before coding)

- Repo `bookanything-platform` (`/home/andre.nascimento/DevEnvALNS/projects/03-PoCs-And-Researches/ALNS-RemoteGitRepos/GitHub-scout23DF/bookanything-platform`),
  module `1-backends/bookanything-monolith-backend-01`.
- Entry point: `resolveAndStoreFlag(geoLocationId)` in
  `dom01geolocation/infrastructure/adapters/input/workflow/GeoLocationArtifactsActivitiesImpl.kt`, the `FLAG`
  activity of `GeoLocationArtifactsWorkflow` (StartToClose 2 min, 3 attempts, 30 s heartbeat since 20/10).
- Current providers: Wikidata, Wikimedia Commons, flagcdn. Result stored in the tenant MinIO as
  `images/geolocations/<id>/flag-<ISO3>.svg` and embedded in the PDF report rendered by JSReport.

### 2. Proposed design (open for debate)

- **Provider chain with explicit preference**: official SVG first (Wikidata P41/Commons, flagcdn `.svg`), then
  other SVG sources, then high-resolution raster; raster is never preferred over any SVG.
- **Provenance**: persist source URL, license and original format next to the asset.
- **Conversion service**: run the vectorizer in the Python `bookanything-maps-generator` (FastAPI) rather than
  in the JVM image (keeps the image light, no native build, see André's constraint). Candidates: `vtracer`
  (color, Rust, has Python bindings) and `potrace` (binary, B/W only, needs per-color layering). Flags are
  flat-color geometry, so a low color count quantization before tracing should work well; flags with detailed
  coats of arms need visual validation.
- **Quality gate**: render the SVG back to PNG, compare with the source (SSIM/pixel diff) and fall back to
  embedding the raster inside an SVG wrapper if the score is below a threshold, instead of shipping a bad trace.
- **Acceptance set**: BRA, LUX, DEU, plus one flag with a complex emblem (e.g. ESP, MEX, EGY).
- **Resilience**: conversion is a separate step with its own timeout; failure must not fail the whole workflow.

### 3. Risks and open questions (Claude)

- Which extra sources? Candidates: Wikipedia/Commons "Flag of X" category, CIA World Factbook, Flagpedia,
  OpenStreetMap/Wikidata-linked files. License of each must be checked.
- Is a SVG-wrapped raster acceptable as a fallback, or must it be a true vector?
- Is the maps-generator reachable from the backend in every environment (cluster and local compose)?
- Image drift: `vtracer` is a Rust dependency inside the Python image; check build time and size.

---

## Analysis and Evaluation by Antigravity:

_(to be filled by Antigravity: candidate sources, alternative vectorizers, risks, impact on the report)_

---

# Discussion/Debate:

## Highlighted points from Antigravity's analysis:

_(pending)_

## Highlighted points from Claude's analysis:

_(pending)_

## Counterpoints and clarifications from Antigravity:

_(pending)_

## Counterpoints and clarifications from Claude:

_(pending)_

---

# Final Decisions After Both Agreement and Disagreement:

_(pending: sources, vectorizer, where it runs, acceptance criteria, André's sign-off)_

# Action Plan for the Flag Improvement:

_(pending: feature branch + PR on bookanything-platform, never master; Tekton/ArgoCD deploy after André merges)_
