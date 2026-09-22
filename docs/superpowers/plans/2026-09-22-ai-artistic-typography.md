# AI Artistic Typography Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a provider-independent title-lettering asset system that offers four artistic-title candidates and applies one chosen asset consistently across the Mini CD set.

**Architecture:** Keep title lettering as a separate transparent asset layer. `title_typography.py` owns data validation, direction analysis, candidate storage, and provider dispatch; `title_compositor.py` owns millimetre-safe asset placement; `design_service.py` orchestrates them alongside the existing Visual DNA, copy, and print composition code.

**Tech Stack:** Python 3, Pillow, SVG metadata preservation, existing standard-library HTTP server, browser-side vanilla JavaScript, existing `tools/spec_minicd.py` dimensions.

**Spec:** `docs/superpowers/specs/2026-09-22-ai-artistic-typography.md`

## Global Constraints

- Do not call, scrape, or hard-depend on Adobe Express, ArtFont, Canva, or 标智客.
- Phase 1 does not call a paid provider; it ships complete provider-ready architecture.
- Phase 2 must make “自动生成” return four real title-lettering candidates through a configured AI provider, without changing UI, asset, compositor, or Mini CD geometry contracts.
- AI title lettering is never used for tracklist, duration, copyright, barcode, catalog number, or production metadata.
- Never change Mini CD physical dimensions or fold positions.
- Reuse one selected title asset across every component; do not regenerate per panel.
- A failed/unconfigured provider must return an explicit unavailable state, never a normal-font image described as AI lettering.

## Review Focus

- Chinese title with an unavailable Phase 1 provider: four candidate slots show an actionable unavailable state and `cover-follow` still generates a complete print-ready set.
- A configured Phase 2 provider returns four visibly distinct controlled variants: closest-original, editorial, expressive, and minimal.
- Transparent PNG with large padding: visual bounds, not raw canvas bounds, determine safe-area fit.
- SVG upload: SVG source persists; preview must rasterize safely; missing rasterizer falls back with an explicit message.
- Title asset cannot cross centre hole, back tracklist, copyright, barcode, fold or trim boundaries at any DPI.
- A selected title asset renders identically as source content on all six Mini CD surfaces while only placement changes.

---

### Task 1: Define title-lettering domain types and provider boundary

**Files:**
- Create: `tools/title_typography.py`
- Test: `tests/test_title_typography.py`
- Modify: `workbench/design_service.py`

**Interfaces:**
- Produces `normalize_title_settings(raw) -> dict`, `analyze_title_direction(visual_dna, album) -> dict`, and `generate_artistic_typography(request, provider_id) -> dict`.
- Consumes Visual DNA from `design_parts.read_design` and title/artist request fields.

- [ ] **Step 1: Write failing tests**

```python
def test_unconfigured_provider_never_claims_to_generate_art():
    result = generate_artistic_typography(request_for("如果呢"), "unavailable")
    assert result["status"] == "unavailable"
    assert result["candidates"] == []

def test_title_settings_default_to_cover_follow():
    assert normalize_title_settings({})["titleMode"] == "cover-follow"
```

- [ ] **Step 2: Run the test**

Run: `python -m unittest tests.test_title_typography -v`
Expected: failure because module/functions do not exist.

- [ ] **Step 3: Implement `tools/title_typography.py`**

Create `ArtisticTypographyRequest`, `TitleLetteringCandidate`, and `ArtisticTypographyProvider` exactly as in the spec. Implement `ManualAssetProvider` and `UnavailableProvider`; reserve provider IDs `openai`, `adobe`, and `custom` but map each to unavailable until explicitly configured. Implement direction categories from `visual_dna.style`, `visual_dna.mood`, source-language, title length, and optional cover-title reference. Define the Phase 2 request fields now, including the four controlled variants.

- [ ] **Step 4: Add service orchestration**

In `build_preview` and `build_job`, normalize `titleMode`, `titleDirection`, candidate list, and selected asset id. Return title state in preview responses and persist it in `meta.json`.

- [ ] **Step 5: Run tests**

Run: `python -m unittest tests.test_title_typography tests.test_copy_typography -v`
Expected: PASS.

### Task 2: Add safe asset storage and upload validation

**Files:**
- Create: `tools/title_assets.py`
- Modify: `workbench/server.py`
- Modify: `workbench/design_service.py`
- Test: `tests/test_title_assets.py`

**Interfaces:**
- Produces `save_title_asset(upload_path, album_key) -> TitleLetteringAsset` and `load_title_asset(asset_id) -> PIL.Image.Image`.
- Consumes only files returned by existing `/api/upload` and stores normalized assets beneath `outputs/迷你CD设计/_title_assets/`.

- [ ] **Step 1: Write failing tests**

```python
def test_png_asset_preserves_alpha_and_records_visible_bounds(tmp_path):
    asset = save_title_asset(make_padded_rgba_png(tmp_path), "album-a")
    assert asset.transparent is True
    assert asset.visible_bounds == (20, 10, 180, 90)

def test_rejects_non_image_upload():
    with pytest.raises(ValueError, match="PNG|SVG"):
        save_title_asset("bad.txt", "album-a")
```

- [ ] **Step 2: Implement validation and persistence**

Allow PNG and SVG only. Preserve original bytes, create a normalized PNG preview for SVG when a local rasterizer is available, hash bytes for stable asset IDs, record transparent bounds, dimensions, source filename and source mode. Never accept filesystem paths from browser requests.

- [ ] **Step 3: Add `POST /api/design/title-assets`**

Accept `{upload, album, titleDirection}` where `upload` is an existing upload UID. Return asset metadata and a safe preview URL. Reuse existing upload size/type guardrails.

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_title_assets -v`
Expected: PASS.

### Task 3: Build millimetre-safe title-asset compositor

**Files:**
- Create: `tools/title_compositor.py`
- Modify: `tools/spec_minicd.py`
- Modify: `tools/design_parts.py`
- Modify: `tools/make_minicd.py`
- Test: `tests/test_title_compositor.py`

**Interfaces:**
- Produces `place_title_asset(image, asset, placement, protected_rects, dpi) -> image`.
- `placement` is `{panel, xMm, yMm, maxWidthMm, maxHeightMm, anchor, rotationDeg}`.
- Consumes `TitleLetteringAsset` and protected rectangles from spec functions.

- [ ] **Step 1: Write failing tests**

```python
def test_disc_asset_does_not_intersect_hole():
    placement = resolve_title_placement("disc", spec, direction)
    assert not intersects(placement.bounds_mm, spec.disc_hole_bounds_mm())

def test_back_asset_avoids_all_production_rectangles():
    placement = resolve_title_placement("back", spec, direction)
    assert not any(intersects(placement.bounds_mm, rect) for rect in spec.back_protected_rects_mm())
```

- [ ] **Step 2: Add title safe areas to `spec_minicd.py`**

Expose protected rectangles for disc hole, back tracklist, copyright, barcode, cover fold, strip folds, trim and a 1.0mm panel safety inset. Use named constants; do not alter physical component dimensions.

- [ ] **Step 3: Implement compositor**

Fit against alpha-visible bounds, rotate only the asset layer, clip to the panel’s safe area, and return a placement report with final mm bounds. If the chosen asset cannot meet minimum readable width, fall back to functional title rendering and return a warning.

- [ ] **Step 4: Attach to all component render paths**

Add optional `title_asset`/`title_placements` arguments to `design_disc2`, `design_inner2`, `design_back2`, `design_tray2`, `design_spine2`, and `make_cover_fold`. Suppress only the matching program-rendered album-title layer when the selected asset is successfully placed. Keep artist and metadata roles unchanged.

- [ ] **Step 5: Run tests**

Run: `python -m unittest tests.test_title_compositor -v`
Expected: PASS.

### Task 4: Add title-lettering UI and four-candidate selection

**Files:**
- Modify: `workbench/design.html`
- Modify: `workbench/design_service.py`
- Test: `tests/test_design_title_state.py`

**Interfaces:**
- Consumes preview response `titleTypography` with direction, provider status, candidates, and selected id.
- Sends `{titleMode, titleProvider, titleReferenceUpload, selectedTitleAssetId}` with preview/build requests.

- [ ] **Step 1: Write service-state test**

```python
def test_preview_exposes_four_candidate_slots_when_artistic_mode_selected():
    response = build_preview(request_with(titleMode="artistic"))
    assert len(response["titleTypography"]["slots"]) == 4
    assert response["titleTypography"]["providerStatus"] == "unavailable"
```

- [ ] **Step 2: Add the `标题艺术字` panel**

Place it after Visual DNA and before custom component artwork. Include title-mode segmented controls: 原封面标题 / 普通字体 / AI艺术字; Typography Direction summary; four equal candidate cards; 自动生成 / 重新生成; 上传参考字; 上传透明 PNG/SVG; and a selected-state marker.

- [ ] **Step 3: Implement interaction rules**

`cover-follow` is initial state. Selecting `artistic` opens four slots without pretending they contain generated art. A provider result fills slots; selecting a card updates all three realtime previews. Uploading a title asset creates a candidate card and auto-selects only after user clicks it. A user may always switch back to functional title mode.

- [ ] **Step 4: Run service test and browser smoke test**

Run: `python -m unittest tests.test_design_title_state -v`
Expected: PASS.

Open `http://127.0.0.1:8765/design?...`; verify candidate selection changes all three preview images without changing CD/fold/strip dimensions.

### Task 5: Implement provider-ready four-candidate generation and production verification

**Files:**
- Create: `tools/title_providers/__init__.py`
- Create: `tools/title_providers/manual.py`
- Create: `tools/title_providers/unavailable.py`
- Modify: `tools/title_typography.py`
- Modify: `workbench/design_service.py`
- Test: `tests/test_title_provider_contract.py`

**Interfaces:**
- `provider.generate(request)` returns 0–4 candidates; service normalizes UI slots to exactly four.

- [ ] **Step 1: Write contract tests**

```python
def test_provider_result_is_capped_at_four_and_keeps_single_source_asset_ids():
    result = normalize_provider_candidates(provider_returning_five())
    assert len(result) == 4
    assert len({candidate.id for candidate in result}) == 4

def test_selected_asset_is_reused_for_every_panel():
    job = build_job(request_with(selectedTitleAssetId="ttl_01"))
    assert set(job["meta"]["titleAssetUsage"].values()) == {"ttl_01"}
```

- [ ] **Step 2: Implement four-slot normalization and title-usage manifest**

Persist provider, prompt, title direction, candidate IDs, selected ID, and final component placement report in `meta.json`. Include selected source PNG/SVG in the export ZIP under `title-lettering/`.

- [ ] **Step 3: Verify print output**

Generate one Chinese title with `ManualAssetProvider`, one Latin title with functional fallback, and one no-asset job. Inspect all three at 300 DPI and verify title assets do not enter protected rectangles. Verify all output component dimensions against `spec_minicd.py`.

- [ ] **Step 4: Run full tests**

Run: `python -m unittest discover -s tests -v`
Expected: PASS.

## Spec Coverage Review

- Visual DNA → Typography Direction: Tasks 1 and 4.
- Three title modes and four candidates: Tasks 1, 4, and 5.
- Transparent PNG/SVG title asset lifecycle: Task 2.
- One title asset reused across all Mini CD pieces: Tasks 3 and 5.
- Functional text remains separate: Task 3 tests and compositor inputs.
- Provider isolation/Phase 1 without paid API: Tasks 1 and 5.
- Conservative original-title reference extraction: Task 6.
- Phase 2 real AI generation with four controlled variants: Task 7.
- Fixed physical Mini CD template: Task 3 and print verification.

### Task 6: Extract and validate the original cover-title reference

**Files:**
- Create: `tools/title_reference.py`
- Modify: `tools/design_parts.py`
- Modify: `tools/title_typography.py`
- Modify: `workbench/design_service.py`
- Test: `tests/test_title_reference.py`

**Interfaces:**
- Produces `extract_cover_title_reference(cover, visual_dna, album) -> CoverTitleReference`.
- Returns `status`, normalized `titleBBox`, `cropPng`, `confidence`, `titleStyleDescription`, and `titleDirection`.

- [ ] **Step 1: Write failing tests**

```python
def test_low_confidence_candidate_is_rejected_not_cropped():
    ref = extract_cover_title_reference(face_dominant_cover(), dna(), "如果呢")
    assert ref.status == "rejected"
    assert ref.crop_png is None

def test_safe_high_confidence_title_crop_records_normalized_bbox():
    ref = extract_cover_title_reference(title_in_safe_top_band(), dna(), "如果呢")
    assert ref.status == "detected"
    assert 0 <= ref.title_bbox["x"] <= 1
    assert ref.crop_png.endswith(".png")
```

- [ ] **Step 2: Implement conservative extraction**

Use the Visual DNA safe bands, title-like edge-density region detection and album-title length as ranking signals. Reject candidates intersecting detected faces, candidates below the configured confidence threshold, and crops whose source pixels cannot produce a legible reference. Save only accepted crops under `outputs/迷你CD设计/_title_references/`.

- [ ] **Step 3: Feed the reference to title direction and Provider requests**

Extend `ArtisticTypographyRequest` with `cover_title_reference`. Persist `coverTitleReference`, `titleBBox`, and `titleStyleDescription` in preview response and `meta.json`. When unavailable, omit the image from the Provider request while retaining Visual DNA direction.

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_title_reference -v`
Expected: PASS.

### Task 7: Implement Phase 2 real AI candidate generation with controlled variation

**Files:**
- Create: `tools/title_providers/openai_image.py`
- Modify: `tools/title_typography.py`
- Modify: `tools/title_providers/__init__.py`
- Modify: `workbench/design_service.py`
- Test: `tests/test_title_provider_contract.py`

**Interfaces:**
- `OpenAIArtisticTypographyProvider.generate(request)` returns exactly four `TitleLetteringCandidate` records with variants `closest-original`, `editorial`, `expressive`, `minimal`.
- Consumes `ArtisticTypographyRequest.cover_title_reference`, Visual DNA, title direction and source title text.

- [ ] **Step 1: Write failing controlled-variation tests**

```python
def test_generation_request_has_exactly_four_named_variants():
    prompts = build_variant_prompts(request_for("如果呢"))
    assert [p.variant for p in prompts] == [
        "closest-original", "editorial", "expressive", "minimal"
    ]

def test_candidate_variants_do_not_share_identical_prompt_or_asset_id():
    candidates = normalize_provider_candidates(fake_provider_four_variants())
    assert len({c.prompt for c in candidates}) == 4
    assert len({c.id for c in candidates}) == 4
```

- [ ] **Step 2: Implement prompt construction**

Build a shared visual-DNA base prompt, then append one explicit variant instruction for each required direction. Include the literal album title, required transparent background, no extra words, no background artwork, no tracklist, no logo icon, and the accepted `coverTitleReference` when available. Reject provider output whose text cannot be verified as the requested title before candidate storage.

- [ ] **Step 3: Implement provider response normalization**

Store every successful candidate through `title_assets.save_title_asset`. Set `transparent`, visible bounds, provider ID, prompt, variant, direction and generation timestamp. If a provider returns fewer than four valid candidates, preserve valid candidates and mark failed slots individually; never duplicate one candidate to fill empty slots.

- [ ] **Step 4: Wire Phase 2 UI behavior**

When a configured provider is available, `自动生成` and `重新生成` invoke the provider and update exactly four candidate cards. Each card visibly labels its controlled direction: 最接近原封面 / Editorial / Expressive / Minimal. The user must choose one; no candidate becomes selected solely because it was generated.

- [ ] **Step 5: Run tests and print verification**

Run: `python -m unittest tests.test_title_provider_contract tests.test_title_compositor -v`
Expected: PASS.

Generate one job from each controlled variant, select one, and verify all component placement reports reference the same selected asset ID.

## Execution Handoff

Plan complete. Execution should be **Native**: the new types, storage, compositor, UI and render integration depend on the same asset identifiers and need one coherent implementation pass. Review this plan before authorizing code changes.
