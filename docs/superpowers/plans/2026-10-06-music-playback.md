# 原工作台音乐播放功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 8765 工作台中加入可实际播放已授权音频的搜索入口、底部播放器、完整播放页、队列和音频导入，并保持现有商品制作流程不变。

**Architecture:** 后端新增独立 `playback_service.py` 管理音频绑定、清单解析和安全文件访问，`server.py` 只负责 HTTP 路由与 Range 响应。前端新增独立 `player.js` 与 `player.css`，通过一个原生 `<audio>` 管理队列和播放状态，并用事件接口接入现有搜索与制作页。

**Tech Stack:** Python 3 标准库 HTTP 服务、JSON 索引、HTML/CSS、原生 JavaScript、HTMLAudioElement、Python `unittest`、Playwright 浏览器验证。

**Spec:** `docs/superpowers/specs/2026-10-06-music-playback-design.md`

## Global Constraints

- 目标工作台固定为 `D:\MusicMerchStudio` 的 8765 服务，不跳转到 8770 或其他项目。
- 当前 QQ/网易云匿名搜索只提供元数据，不作为完整歌曲播放源。
- 可播放资源仅来自用户上传的已授权音频或服务器授权清单。
- 上传音频、音频索引和授权清单运行数据不得提交 Git。
- 播放状态与制作选择状态必须独立，播放按钮不能改变当前制作选择。
- 现有单曲制作、热门批量制作、打印、作品库接口与输出不得回归。
- 前端不暴露服务器绝对路径、密钥或第三方令牌。

## Review Focus

- 恶意 `trackId`、文件名和路径穿越必须被拒绝，不能读取音频库外文件。
- Range 包含有效、开放结尾、后缀、越界和格式错误五类，必须返回正确的 206、416 或完整响应。
- 同一歌曲在 QQ 和网易云的数字 ID 可能相同，索引必须用 `source:id` 区分。
- 浏览器刷新只能恢复队列元数据，绝不能自动出声。
- 队列中存在不可播放歌曲时，用户主动点击应看到原因，自动续播应跳过且不能无限循环。

---

### Task 1: 本地音频索引与播放资源解析

**Files:**
- Create: `workbench/playback_service.py`
- Create: `tests/test_playback_service.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `track_key(source: str, track_id: object) -> str`
- Produces: `class PlaybackLibrary(root: Path, manifest_path: Path | None = None)`
- Produces: `PlaybackLibrary.resolve(source: str, track_id: object) -> dict | None`
- Produces: `PlaybackLibrary.bind_upload(source: str, track_id: object, filename: str, body: bytes) -> dict`
- Produces: `PlaybackLibrary.asset_path(asset_id: str) -> Path | None`
- Produces: `PlaybackLibrary.state(source: str, track_id: object) -> str`

- [ ] **Step 1: Write failing tests for stable keys, persistence and isolation**

Add tests named `test_track_key_separates_sources`, `test_bind_upload_persists_and_resolves_after_reload`, `test_rejects_unsupported_extension`, `test_rejects_oversized_body`, `test_rejects_empty_or_unsafe_identity`, `test_asset_path_never_escapes_root`, and `test_manifest_entry_resolves_without_mutating_upload_index`.

- [ ] **Step 2: Run the service tests and verify they fail**

Run: `python -m unittest tests.test_playback_service -v`

Expected: FAIL because `workbench.playback_service` does not exist.

- [ ] **Step 3: Implement the minimal playback library**

Implement atomic JSON index writes, MIME/extension validation for MP3/M4A/AAC/WAV/OGG/FLAC, a 200 MiB upload limit, generated opaque asset IDs, manifest loading, and real-path containment checks. Use `Path` and standard library only.

- [ ] **Step 4: Ignore runtime audio data**

Add `outputs/音乐库/` and `config/playback-manifest.local.json` to `.gitignore` without changing existing ignore rules.

- [ ] **Step 5: Run tests**

Run: `python -m unittest tests.test_playback_service -v`

Expected: all Task 1 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add .gitignore workbench/playback_service.py tests/test_playback_service.py
git commit -m "feat: add authorized audio playback library"
```

### Task 2: 播放查询、上传和 Range 音频接口

**Files:**
- Modify: `workbench/server.py`
- Create: `tests/test_playback_http.py`
- Modify: `tests/test_selected_song.py`

**Interfaces:**
- Consumes: `PlaybackLibrary` from Task 1.
- Produces: `GET /api/playback?source=<source>&id=<trackId>`.
- Produces: `POST /api/audio/upload?source=<source>&id=<trackId>&name=<filename>`.
- Produces: `GET /media/audio/<assetId>` with byte ranges.
- Produces: `playback_track_fields(source: str, track_id: object) -> dict` returning `trackKey` and `playbackState`.

- [ ] **Step 1: Write failing HTTP and search-shape tests**

Test `GET /api/playback` for bound and unbound songs; upload success and invalid type; full file response; `bytes=0-3`, `bytes=4-`, `bytes=-4`, unsatisfiable range and malformed range; `/api/song` and `/api/artist` returning source, `trackKey` and `playbackState` for every song.

- [ ] **Step 2: Run the targeted tests and verify they fail**

Run: `python -m unittest tests.test_playback_http tests.test_selected_song -v`

Expected: new assertions FAIL because routes and playback fields are absent.

- [ ] **Step 3: Add the playback service singleton and search metadata fields**

Initialize the library under `outputs/音乐库`, load optional `config/playback-manifest.local.json`, add `source` to artist songs, and merge `playback_track_fields` into artist and song responses.

- [ ] **Step 4: Add playback and upload routes**

Return HTTP 200 with `{playable:false, reason}` when a search hit has no audio. Upload bytes through `PlaybackLibrary.bind_upload` and return the new asset with a same-origin URL.

- [ ] **Step 5: Add a dedicated Range response helper**

Implement `Handler._audio_file(path: Path, mime_type: str)` with `Accept-Ranges: bytes`, `Content-Range`, `Content-Length`, `206 Partial Content` and `416 Range Not Satisfiable`. Stream chunks instead of reading the full file into memory.

- [ ] **Step 6: Run targeted tests**

Run: `python -m unittest tests.test_playback_http tests.test_selected_song -v`

Expected: all targeted tests PASS.

- [ ] **Step 7: Commit**

```bash
git add workbench/server.py tests/test_playback_http.py tests/test_selected_song.py
git commit -m "feat: expose playback and audio streaming APIs"
```

### Task 3: 播放器核心、搜索按钮与底部控制条

**Files:**
- Create: `workbench/player.js`
- Create: `workbench/player.css`
- Modify: `workbench/index.html`
- Modify: `workbench/server.py`
- Create: `tests/test_player_ui.py`

**Interfaces:**
- Consumes: `/api/playback`, existing `/api/song`, `/api/artist`, and global `jget`, `toast`, `esc`, `asset`, `uiMode` helpers.
- Produces: `window.WorkbenchPlayer.setQueue(tracks: Track[], startIndex: number)`.
- Produces: `window.WorkbenchPlayer.playTrack(track: Track, queue?: Track[])`.
- Produces: `window.WorkbenchPlayer.toggle(trackKey?: string)`.
- Produces: `window.openSongMakerTrack(track: Track, context?: {artist?: object, songs?: Track[]})`, extracted from the current `renderArtistResultStage` song-maker closure so playback and existing rows use one entry.
- Produces: custom event `workbench-player-change` with current track and state.

- [ ] **Step 1: Write failing static UI tests**

Assert that the page loads `/static/player.css` and `/static/player.js`, contains one persistent `<audio>`, bottom player landmarks and accessible control labels, search result renderers emit `data-play-track`, and CSS reserves bottom space only while the player is visible.

- [ ] **Step 2: Run the UI tests and verify they fail**

Run: `python -m unittest tests.test_player_ui -v`

Expected: FAIL because the player assets and markup do not exist.

- [ ] **Step 3: Serve focused static assets**

Add allowlisted routes `/static/player.js` and `/static/player.css` in `server.py`; do not expose arbitrary files from `workbench/`.

- [ ] **Step 4: Implement queue and audio state in `player.js`**

Use one `HTMLAudioElement`; persist queue/current index/mode/volume to localStorage without auto-playing on reload. Implement play, pause, previous, next, seek, volume, list loop, single loop and shuffle. Bound automatic skip attempts by queue length.

- [ ] **Step 5: Build the bottom player UI and responsive styling**

Add the 76px desktop bar, compact mobile state, cover fallback, progress/time display, disabled/loading/error states, and 44px touch targets. Match the current workbench tokens and neutral/red visual language.

- [ ] **Step 6: Add play buttons without changing production selection**

Render play controls in the artist track table, single-song list and search suggestion rows. Stop event propagation on play controls. Feed the current result set as the temporary queue while preserving the existing row click for production selection.

- [ ] **Step 7: Run UI tests**

Run: `python -m unittest tests.test_player_ui -v`

Expected: all Task 3 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add workbench/player.js workbench/player.css workbench/index.html workbench/server.py tests/test_player_ui.py
git commit -m "feat: add persistent workbench music player"
```

### Task 4: 完整播放页、队列抽屉、音频导入与制作联动

**Files:**
- Modify: `workbench/player.js`
- Modify: `workbench/player.css`
- Modify: `workbench/index.html`
- Modify: `tests/test_player_ui.py`

**Interfaces:**
- Consumes: Task 3 `WorkbenchPlayer` state and existing single-song production entry.
- Produces: `WorkbenchPlayer.openNowPlaying()` and `WorkbenchPlayer.closeNowPlaying()`.
- Produces: `WorkbenchPlayer.openQueue()` and queue mutation controls.
- Produces: `WorkbenchPlayer.importAudio(track: Track, file: File)`.

- [ ] **Step 1: Extend failing UI tests**

Assert full player dialog semantics, current song/cover/lyrics states, queue remove/clear controls, unavailable-audio dialog, upload accept list, upload error status, and “制作同款周边” reusing the same track ID/source rather than searching again.

- [ ] **Step 2: Run UI tests and verify the new assertions fail**

Run: `python -m unittest tests.test_player_ui -v`

Expected: FAIL on the new full-player and import requirements.

- [ ] **Step 3: Implement the full player and queue drawer**

Add workbench-internal overlays with focusable close controls, responsive one-column layout, current queue selection, remove and clear behavior. Closing an overlay must not stop audio.

- [ ] **Step 4: Implement unavailable-source and upload flow**

When `/api/playback` returns `playable:false`, open the import dialog instead of pretending to play. Upload the file to the current `source/id`, refresh playback resolution, then start playback without a new search.

- [ ] **Step 5: Wire “制作同款周边” to current song data**

Call the existing single-song maker with the current track object so name, artist, album, cover, source and ID remain identical to the playing song.

- [ ] **Step 6: Add keyboard and accessibility behavior**

Support Space for play/pause when focus is outside text fields, Escape to close the top player overlay, `aria-live` for playback errors, and focus return to the opening control.

- [ ] **Step 7: Run UI tests**

Run: `python -m unittest tests.test_player_ui -v`

Expected: all Task 4 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add workbench/player.js workbench/player.css workbench/index.html tests/test_player_ui.py
git commit -m "feat: add now playing queue and audio import"
```

### Task 5: 实际播放验证与完整回归

**Files:**
- Create: `tests/e2e_playback.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: completed playback APIs and UI.
- Produces: repeatable end-to-end verification using a generated WAV fixture in a temporary runtime directory.

- [ ] **Step 1: Create an end-to-end playback fixture and browser test**

Generate a short PCM WAV with Python `wave`, bind it to a deterministic test track, start the server on a free test port, and verify search row play, bottom player visibility, time advancement, pause, seek, next/previous, queue, overlay close without stopping, and production handoff.

- [ ] **Step 2: Verify narrow-screen behavior**

At a 390×844 viewport, assert the compact player remains visible, primary controls are not obscured, full player becomes one column, and the page can scroll to all production actions.

- [ ] **Step 3: Run the playback end-to-end test**

Run: `python tests/e2e_playback.py`

Expected: PASS with no browser console errors and audio `currentTime` increasing.

- [ ] **Step 4: Run the complete Python regression suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

- [ ] **Step 5: Run source and repository checks**

Run: `python -m py_compile workbench/server.py workbench/playback_service.py`

Run: `git diff --check`

Expected: both commands succeed with no output indicating errors.

- [ ] **Step 6: Document operation and public-launch boundary**

Update README with supported upload formats, where runtime audio is stored, how to configure the local authorization manifest, and that public full-catalog playback requires an approved commercial Provider.

- [ ] **Step 7: Restart and verify the real 8765 service**

Restart via the existing launcher with `--force --no-browser`, request `/api/ping`, open `http://127.0.0.1:8765/`, and perform one real upload/play/seek smoke test without altering saved production works.

- [ ] **Step 8: Commit**

```bash
git add tests/e2e_playback.py README.md
git commit -m "test: verify workbench music playback flow"
```

