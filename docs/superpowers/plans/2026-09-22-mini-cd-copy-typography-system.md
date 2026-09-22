# Mini CD 文案与字体系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic Copy Layout A/B and a commercial-aware Typography System to Mini CD design without changing physical production geometry.

**Architecture:** Add a small Python copy/typography module that owns font records, role matching, copy presets and safe-zone rendering. `design_service.py` carries one serializable settings object through preview and production; `design.html` edits it and renders the controls. Existing `spec_minicd.py` remains the physical source of truth.

**Tech Stack:** Python, Pillow, existing `tools/typo.py`, HTML/CSS/vanilla JavaScript, Mini CD 300 DPI renderer.

**Spec:** `docs/superpowers/specs/2026-09-22-mini-cd-copy-typography-system-design.md`

## Global Constraints

- Never alter Mini CD geometry: disc `40/5`, cover `82×41`, tray `111.2×38`, segments `4.4|49|4.4|4.4|49`.
- Artwork contains no final typography; program renders all readable text.
- Barcode, copyright, tracklist, fold lines and center hole remain program-owned production areas.
- Default font matching only uses `verified-open` Font Library records.
- Do not modify non-Mini-CD modules.

## Review Focus

- A user’s manual font selection must survive preview, formal build, PDF/PNG export and reopening history.
- Legacy tasks without copy settings must render exactly as before.
- Empty Concept Copy fields must render no example copy.
- Long Chinese/English Copy must obey safe zones and minimum sizes instead of invading barcode or tracklist space.
- The auto recommendation must remain deterministic for the same cover and never override an explicit A/B or font choice.

---

### Task 1: Add copy and typography domain configuration

**Files:**
- Create: `tools/copy_typography.py`
- Modify: `tools/design_parts.py`
- Test: `tests/test_copy_typography.py`

**Interfaces:**
- Consumes: `D` from `read_design()`, Mini CD mm constants from `spec_minicd.py`.
- Produces: `normalize_copy_settings(raw)`, `recommend_copy_layout(settings, D)`, `recommend_typography(D)`, `font_library()`.

- [ ] **Step 1: Write failing tests for defaults and explicit selections**

```python
from copy_typography import normalize_copy_settings, recommend_copy_layout

def test_explicit_copy_layout_is_never_overridden():
    settings = normalize_copy_settings({"copyLayout": "minimal"})
    assert recommend_copy_layout(settings, {"style": "bold"}) == "minimal"

def test_empty_copy_never_invents_reference_words():
    settings = normalize_copy_settings({})
    assert settings["conceptCopy"] == {"primaryChinese": "", "secondaryEnglish": "", "shortEnglish": ""}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_copy_typography.py -v`

Expected: FAIL because `copy_typography` does not exist.

- [ ] **Step 3: Implement the normalized settings and Font Library**

```python
def normalize_copy_settings(raw):
    raw = raw or {}
    return {
        "copyLayout": raw.get("copyLayout") if raw.get("copyLayout") in ("auto", "editorial", "minimal") else "auto",
        "conceptCopy": {key: str((raw.get("conceptCopy") or {}).get(key) or "").strip()
                        for key in ("primaryChinese", "secondaryEnglish", "shortEnglish")},
        "typography": {role: str((raw.get("typography") or {}).get(role) or "auto")
                       for role in ("display", "artist", "chineseCopy", "englishCopy", "metadata", "spine")},
    }
```

- [ ] **Step 4: Run the domain tests**

Run: `python -m pytest tests/test_copy_typography.py -v`

Expected: PASS.

### Task 2: Render copy layers with mm safe zones

**Files:**
- Modify: `tools/design_parts.py`
- Modify: `tools/make_minicd.py`
- Test: `tests/test_copy_typography.py`

**Interfaces:**
- Consumes: normalized copy settings and resolved type roles from Task 1.
- Produces: `design_disc2`, `design_cover_fold2`, `design_back2`, `design_tray2` that accept `copy_settings`.

- [ ] **Step 1: Write failing rendering tests**

```python
def test_editorial_copy_does_not_touch_back_cover_production_areas(rendered_back):
    forbidden = [barcode_rect_px(rendered_back.width, rendered_back.height),
                 copyright_rect_px(rendered_back.width, rendered_back.height)]
    assert copy_text_boxes(rendered_back.info)["secondaryEnglish"].intersects_any(forbidden) is False
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `python -m pytest tests/test_copy_typography.py::test_editorial_copy_does_not_touch_back_cover_production_areas -v`

Expected: FAIL because copy box metadata is absent.

- [ ] **Step 3: Implement fixed candidate zones and role rendering**

Use separate render helpers for disc, cover interior/front, back cover, spines and tray. Each helper accepts a panel-local mm rectangle list and returns the actual rendered rectangles for verification. Select candidates around existing Visual DNA safe bands; skip a copy item if no safe candidate remains.

- [ ] **Step 4: Run rendering tests and geometry validation**

Run: `python -m pytest tests/test_copy_typography.py -v && python tools/validate_minicd.py`

Expected: PASS; all physical dimensions remain unchanged.

### Task 3: Carry settings through preview, build, export and history

**Files:**
- Modify: `workbench/design_service.py`
- Test: `tests/test_design_service_copy_settings.py`

**Interfaces:**
- Consumes: request JSON fields `copyLayout`, `conceptCopy`, `typography`.
- Produces: identical settings in preview response, formal build `meta.json` and history state API.

- [ ] **Step 1: Write persistence test**

```python
def test_build_persists_copy_settings(client, sample_design_payload):
    payload = {**sample_design_payload, "copyLayout": "editorial",
               "conceptCopy": {"primaryChinese": "测试", "secondaryEnglish": "TEST", "shortEnglish": "TAG"}}
    result = client.build(payload)
    assert result.meta["copyLayout"] == "editorial"
    assert result.meta["conceptCopy"]["secondaryEnglish"] == "TEST"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_design_service_copy_settings.py -v`

Expected: FAIL because build metadata does not contain copy settings.

- [ ] **Step 3: Pass settings into `build_parts` and save normalized values**

Normalize once at the API boundary. Pass the result unchanged to preview and formal rendering, and save it in `meta.json`; missing fields use neutral legacy defaults.

- [ ] **Step 4: Run persistence and legacy regression tests**

Run: `python -m pytest tests/test_design_service_copy_settings.py -v`

Expected: PASS.

### Task 4: Add “文案与字体” controls to the Mini CD design UI

**Files:**
- Modify: `workbench/design.html`
- Test: manual browser verification plus `node --check` on extracted inline script.

**Interfaces:**
- Consumes: Typography Direction and Font Library response from Task 1, saved setting JSON from Task 3.
- Produces: request fields `copyLayout`, `conceptCopy`, `typography` on preview and build.

- [ ] **Step 1: Add Copy Layout controls and three copy inputs**

Create compact thumbnail buttons: `自动推荐`, `A · Editorial / 丰富型`, `B · Minimal / 克制型`; inputs are Chinese primary, English secondary and short English. Input updates call existing debounced preview.

- [ ] **Step 2: Add Typography Direction and six role selectors**

Display deterministic directions for Chinese Display, Chinese Body, English Display and Metadata. Add selector rows for Display, Artist, Chinese Copy, English Copy, Metadata and Spine; each starts at `自动` and shows license status.

- [ ] **Step 3: Wire request, history hydration and fallback state**

```javascript
const copySettings = {
  copyLayout: COPY_LAYOUT,
  conceptCopy: {primaryChinese: $('#primaryCopy').value.trim(), secondaryEnglish: $('#secondaryCopy').value.trim(), shortEnglish: $('#shortTag').value.trim()},
  typography: readTypographyRoles()
};
```

Merge `copySettings` into preview/build requests and restore it from saved history without affecting barcode, tracks or back layout controls.

- [ ] **Step 4: Verify UI and requests**

Run: extract inline script and `node --check`; open design page, switch A/B, type copy, change one font role, verify immediate preview and saved/reopened job.

### Task 5: Final regression and production verification

**Files:**
- Modify: `docs/golden-reference-mini-cd.md`
- Test: `tests/test_copy_typography.py`, `tests/test_design_service_copy_settings.py`

- [ ] **Step 1: Document Copy Layout A/B and Typography System**

Add a short section linking to the new settings and explicitly state that Golden Reference phrases are never default copy.

- [ ] **Step 2: Run full relevant verification**

Run: `python -m pytest tests/test_copy_typography.py tests/test_design_service_copy_settings.py -v && python tools/validate_minicd.py && git diff --check`

Expected: PASS.

- [ ] **Step 3: Manually verify production artifacts**

Build one Editorial and one Minimal project at 300 DPI. Inspect disc, cover fold, strip, A4 PNG and PDF: no copy overlaps center hole, folds, tracks, barcode or copyright; physical structure remains correct.
