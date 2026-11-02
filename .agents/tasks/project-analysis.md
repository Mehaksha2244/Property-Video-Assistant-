# Reality Assistant Drive — Project Analysis

**Prepared by:** Kiro analysis agent  
**Date:** 2025-07-14  
**Scope:** Full codebase read — all 11 files

---

## Summary

Reality Assistant Drive is a small, well-scoped local-first web application that converts real-estate listing details and 4–8 property photos into a vertical (1080×1920) MP4 suitable for social media. The architecture is a single-process FastAPI server that serves a vanilla HTML/JS frontend, processes uploads, orchestrates FFmpeg for video composition, optionally calls a local Ollama LLM for a one-sentence intro, and optionally generates TTS narration. The codebase is clean and focused, with a clearly enforced "fact-safety" constraint (AI output is rejected if it adds any word not present in the submitted listing facts). The implementation is functionally complete for the core path; the main gaps are Windows-only assumptions, a thin test suite, and a frontend that does not yet fully match the design system specified in `MASTER.md`.

---

## 1. Project Purpose and Overview

The app solves a specific real-estate marketing problem: turning a text listing + a handful of photos into a share-ready portrait video without needing video editing software. The key design principle is **fact-safety** — the system is explicitly constrained so that AI assistance can never invent amenities, measurements, or claims that are not in the submitted form data. This is called out in the README, enforced in `_is_fact_safe()` in `main.py`, and tested in `test_video.py`.

---

## 2. Architecture and Tech Stack

### Runtime
- **Python 3.11+** (uses `from __future__ import annotations` throughout)
- **FastAPI 0.115.12** — serves both the SPA and the API under one process
- **Uvicorn 0.34.0** — ASGI runner
- **Pillow 11.2.1** — generates the end-card JPEG in Python before passing to FFmpeg
- **FFmpeg** (system dependency, not in `requirements.txt`) — all video encoding via subprocess
- **httpx 0.28.1** — async HTTP client used to call the local Ollama API
- **python-multipart 0.0.20** — enables FastAPI's `UploadFile` / `Form` parsing
- **pyttsx3** — optional TTS (not pinned in `requirements.txt`); lazy-imported inside `_narrate()`

### Frontend
- Vanilla HTML + CSS + JavaScript, no framework, no build step
- Served as static files via FastAPI's `StaticFiles` mount at `/assets`
- Google Fonts (Cinzel + Josefin Sans) loaded over CDN

### Optional External Services
- **Ollama** (local, `http://127.0.0.1:11434`) with model `gemma4:e2b` for a one-sentence AI intro
- No cloud dependencies; entirely local-first

### Data Flow

```
Browser form submit
  → POST /api/render (multipart)
    → FastAPI main.py: validates Listing, saves uploads to data/uploads/<uuid>/
      → app/video.py render_video()
          → _scene() per image (FFmpeg: scale/crop/zoompan/drawtext → scene-NN.mp4)
          → _end_card() → Pillow generates end-card.jpg → _scene() again
          → FFmpeg concat → silent.mp4
          → optional _narrate() → narration.wav
          → FFmpeg mux (voice + music combinations) → final output.mp4
          → _verify() via ffprobe
      → job_dir cleaned up in finally block
    → returns { download_url, captions }
  → Browser auto-clicks an <a download> link
  → GET /api/download/<job_id> → FileResponse from data/renders/
```

---

## 3. Key Components and Responsibilities

### `app/main.py`
- **FastAPI app setup**: creates `data/uploads/` and `data/renders/` on startup; mounts `web/` at `/assets`
- **`Listing` model** (Pydantic BaseModel): validates all form fields with length constraints; `features` is a list of 1–8 strings
- **`clean_name()`**: sanitises uploaded filenames to alphanumeric + `._-`
- **`ollama_script()`**: async call to local Ollama; has a 40-second timeout; returns `None` on any error — fail-open design
- **`_is_fact_safe()`**: the core guardrail. Builds an allowed-word set from all listing fields + a small set of neutral glue words, then checks every word in the AI response against it. Case-insensitive, tokenises on `[a-z0-9]+`
- **`GET /`**: serves `index.html`
- **`POST /api/preview-script`**: fast path — no file uploads; returns `build_captions()` + optional AI intro
- **`POST /api/render`**: full path — parses multipart form, validates, saves uploads, calls `render_video()`, returns download URL; cleans up the upload directory in `finally`
- **`GET /api/download/{job_id}`**: serves the rendered MP4

### `app/video.py`
- **Constants**: `W=1080`, `H=1920`, `FPS=30`, `FONT=Path("C:/Windows/Fonts/arial.ttf")` — hardcoded Windows path
- **`build_captions()`**: deterministic, fact-safe caption builder. Returns a list of strings built only from listing fields; max 5 features are used. Last caption is always price + CTA
- **`_run()`**: thin subprocess wrapper; raises `RuntimeError` with last 800 chars of stderr on non-zero exit
- **`_end_card()`**: Pillow-based image generation for the final "credits" frame in dark teal (#073b3a)
- **`_scene()`**: writes caption to a `.txt` file, then calls FFmpeg with a filter chain: scale/crop → zoompan (Ken Burns, 1.07× max zoom) → semi-transparent caption bar → drawtext from file
- **`_verify()`**: runs `ffprobe` to check the output MP4 has a duration ≥ 8 seconds
- **`_narrate()`**: lazily imports `pyttsx3`; saves narration to WAV; validates the output file exists and is non-empty
- **`render_video()`**: orchestrates the full pipeline; 4 audio-mux code paths (voice+music, music only, voice only, silent); cleans up work directory in `finally`

### `web/index.html`
- Single-page form: property details, image upload (4–8 files), optional narration checkbox, optional music file
- Two-panel layout: form on left, preview on right
- ARIA: `role="status"` + `aria-live="polite"` on toast; `aria-labelledby` on studio section

### `web/app.js`
- Minimal, imperative vanilla JS — ~8 logical lines
- `listing()` helper: reads `FormData`, splits features string on `,`
- `validDetails()`: calls `form.reportValidity()` (native HTML5 validation) + checks features list is non-empty
- `preview` click: `POST /api/preview-script` with JSON body; calls `display()` on success
- `form` submit: `POST /api/render` with `FormData`; on success calls `display()` then auto-triggers a download via `<a>` click

### `web/styles.css`
- Minified single-file CSS
- CSS custom properties defined on `:root` (`--teal`, `--aqua`, `--ink`, `--muted`, `--paper`, `--line`)
- Glassmorphism panels: `backdrop-filter: blur(14px)`, `background: rgba(255,255,255,.76)`, `border: 1px solid rgba(255,255,255,.9)`
- Responsive: breakpoints at 820px and 500px
- `prefers-reduced-motion`: disables all transitions

### `design-system/reality-assistant-drive/MASTER.md`
- Defines the intended design language: teal/aqua palette, Cinzel (headings) + Josefin Sans (body), glassmorphism, Hero-Centric page pattern, GSAP ScrollTrigger motion
- Not a design spec for a future version — it is the living design contract the UI is meant to conform to

### `tests/test_video.py`
- 2 test cases covering the fact-safety system:
  1. `test_captions_only_use_listing_facts`: verifies all listing fields appear in caption output; verifies no invented text
  2. `test_ai_text_with_unsupported_feature_is_rejected`: verifies `_is_fact_safe()` returns `False` when AI adds a word not in the listing

### `requirements.txt`
- 5 pinned dependencies (exact versions): fastapi, uvicorn[standard], python-multipart, httpx, Pillow
- `pyttsx3` is intentionally not included (optional, platform-specific)
- FFmpeg is a system dependency not tracked here

---

## 4. Frontend–Backend Communication

| Interaction | Method | Format | Path |
|---|---|---|---|
| Load app | GET | — | `/` |
| Serve static assets | GET | — | `/assets/*` |
| Preview captions | POST | JSON body | `/api/preview-script` |
| Render video | POST | `multipart/form-data` | `/api/render` |
| Download MP4 | GET | — | `/api/download/{job_id}` |

The preview endpoint (`/api/preview-script`) accepts a `Listing` JSON object directly. The render endpoint (`/api/render`) uses `multipart/form-data` because it carries binary file uploads. The frontend parses the form into a plain object for the preview call, and passes `new FormData(form)` for the render call — clean separation.

Error responses use FastAPI's default `{"detail": "..."}` shape; the frontend reads `data.detail` in its catch blocks.

There is no WebSocket, no polling, and no authentication. The download URL is returned in the render response body and immediately triggered by the frontend.

---

## 5. Current State of Implementation

### Complete and Working
- Full video pipeline: per-scene FFmpeg rendering, Ken Burns effect, caption overlay, end card, concat, output verification
- All 4 audio-mux paths (silent, music, narration, both)
- FastAPI routes with Pydantic validation
- Fact-safety guardrail on AI output
- Responsive UI with glassmorphism panels
- `prefers-reduced-motion` support in CSS
- ARIA attributes on toast
- Cleanup of temporary files in `finally` blocks
- Image and music MIME-type validation

### Incomplete or Missing
1. **`app/__init__.py` is empty** — The package is importable but has no public API surface. Acceptable for this structure, but no re-exports.
2. **Test coverage is minimal** — Only 2 tests; no tests for `render_video()`, `_scene()`, `_end_card()`, the API endpoints, input validation edge cases, or `clean_name()`
3. **GSAP / ScrollTrigger animation not implemented** — `MASTER.md` specifies GSAP scroll-reveal motion; the current `app.js` has none of this
4. **Design system token mismatch** — `MASTER.md` defines CSS variables `--color-primary`, `--color-secondary`, etc.; `styles.css` uses a different, shorter set (`--teal`, `--aqua`, `--ink`, etc.) and does not match the token names
5. **`MASTER.md` defines an accent/CTA color `#0369A1` (blue)** — the actual UI uses `--teal: #0f766e` for the generate button, not the design-system accent
6. **No `tests/__init__.py`** — not strictly required for `unittest discover` but could cause issues with some test runners
7. **No render progress feedback** — the UI shows "Rendering video…" on the button but there is no server-sent event, WebSocket, or polling; a slow CPU render can take minutes with no intermediate feedback
8. **`pyttsx3` not in `requirements.txt`** — intended as optional, but a first-time user enabling narration will get a `RuntimeError` with the message to `pip install pyttsx3` rather than a clear pre-flight warning in the UI
9. **`FONT` path hardcoded to `C:/Windows/Fonts/arial.ttf`** — only works on Windows; fails silently or crashes on macOS/Linux
10. **No page-level design-system overrides** — `MASTER.md` mentions `design-system/pages/[page-name].md` files; none exist, meaning the master rules are the only rules but the main page has no dedicated spec

---

## 6. Code Quality Observations

### Strengths
- **Clean separation of concerns**: `main.py` handles HTTP/validation; `video.py` handles media processing — easy to follow
- **Defensive error handling**: all FFmpeg calls go through `_run()` which raises a clean `RuntimeError`; `try/finally` ensures upload directories are always cleaned up even on exception
- **Fail-open AI**: `ollama_script()` returns `None` on any exception; the endpoint works fully without Ollama present
- **Input sanitisation**: `clean_name()` prevents path traversal in uploaded filenames; MIME type checks on uploads
- **Pydantic validation**: `Listing` model enforces length constraints at the boundary; re-validated on the render endpoint after multipart parsing
- **Fact-safety is testable and tested**: the core safety property is a pure function with deterministic tests

### Weaknesses
- **`app.js` is minified/concatenated into a single long line** — difficult to read, diff, and maintain; no source map; should be written as readable source and minified at build time if needed
- **`styles.css` is also minified** — same issue; a build step that produces human-readable source + a minified dist would be better
- **No async rendering** — `render_video()` is called synchronously in the request handler; a long render will block the Uvicorn worker thread for minutes; this is acceptable for local/single-user use but not for any multi-user deployment
- **No CSRF protection** — not critical for a local app but worth noting if the app is ever exposed beyond localhost
- **`job_id` is `uuid.uuid4().hex`** — fine, but renders are never cleaned up from `data/renders/`; the directory grows indefinitely
- **`_is_fact_safe()` tokenises on `[a-z0-9]+`**, which means multi-word features like "Near metro" pass as two separate tokens (`near`, `metro`) — the allowed set includes both, which is correct, but a feature like "₹1.25 Cr" only contributes `1`, `25`, `cr` to the allowed set; Devanagari rupee symbols are stripped. This could allow the AI to use any alphanumeric from a numeric price string in unintended contexts.
- **`captions[-1]` is always the price/CTA caption**, which is passed to `_scene()` using the end-card image (a Pillow-generated JPEG); but this means the drawtext overlay renders the caption on top of the end card that already has the same text drawn via Pillow — **text is doubled on the end card**
- **No logging** — `_run()` discards stdout; failures surface only as `RuntimeError`; no structured logging for debugging render issues
- **`features` validation gap**: the `Listing` model uses `Field(min_length=1, max_length=8)` on the list, but the multipart render path splits on commas client-side and server-side — if the user submits a form with a features field containing 9 comma-separated items, Pydantic will reject it with a 422, which is correct, but the error message is a raw Pydantic error string

---

## 7. Notable Design Patterns and Decisions

1. **Local-first, zero external services required** — Ollama, pyttsx3, and music are all optional; the app works with just FFmpeg and Python. This is a strong design principle stated in the README and enforced by the code.

2. **Fact-safety as a first-class constraint** — The system explicitly cannot invent content. `_is_fact_safe()` is a pure function with a clear contract, making it independently testable. The caption builder (`build_captions`) is entirely deterministic. This is the most architecturally interesting decision in the project.

3. **Two-endpoint preview/render split** — The preview endpoint is cheap (no file I/O, no FFmpeg) and lets users verify the caption plan before committing to a multi-minute render. Good UX design.

4. **FFmpeg via subprocess, not a Python binding** — Avoids `moviepy` or `ffmpeg-python` dependencies; uses FFmpeg's filter_complex syntax directly. More verbose but more portable and controllable.

5. **Pillow for the end card, FFmpeg for everything else** — The end card is simpler to produce with Pillow's `ImageDraw` than with FFmpeg `drawtext` multi-line positioning. Clean pragmatism.

6. **UUID-based job directories** — Collisions are effectively impossible; no database needed for job tracking.

7. **Single-file CSS with CSS custom properties** — The design system colours are captured as tokens; the approach is correct even if the token names diverge from `MASTER.md`.

---

## 8. Potential Issues and Recommendations

### High Priority

**H1 — End card text duplication**  
`_end_card()` in `video.py` draws `property_name`, `location`, `price`, and `cta` directly onto the JPEG. `render_video()` then passes that JPEG to `_scene()` which adds the same caption via `drawtext`. The result is the text appearing twice on the final scene. **Fix**: either remove the `drawtext` call for the end card scene (pass `caption=""` or an empty text) or remove the Pillow text rendering and rely purely on FFmpeg drawtext.

**H2 — Windows-only `FONT` path**  
`FONT = Path("C:/Windows/Fonts/arial.ttf")` causes `ImageFont.truetype()` and the FFmpeg `fontfile=` parameter to fail on non-Windows systems. **Fix**: detect the OS and provide fallback paths for macOS (`/Library/Fonts/Arial.ttf`) and Linux (`/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf`), or bundle a fallback font in the repo.

**H3 — Synchronous render blocking Uvicorn**  
`render_video()` is CPU-bound and called directly in an `async` endpoint (`render()`). In an `async def` FastAPI endpoint, blocking calls block the event loop. **Fix**: wrap `render_video()` in `asyncio.to_thread()` or use `run_in_executor` to move it off the event loop, which is the correct FastAPI pattern for CPU-bound work.

### Medium Priority

**M1 — Renders accumulate on disk**  
`data/renders/*.mp4` are never deleted. For a local tool this is manageable, but renders will grow indefinitely. **Fix**: add a background cleanup task (e.g., delete renders older than 1 hour) or add a `DELETE /api/download/{job_id}` endpoint triggered after the frontend confirms the download.

**M2 — No render progress feedback**  
A 1080×1920 video from 8 images can take several minutes. The UI shows a disabled button with "Rendering video…" but there is no way for the user to know if it's progressing or stalled. **Fix**: use Server-Sent Events (SSE) or a polling `/api/status/{job_id}` endpoint to stream progress. This would require making `render_video()` async or running it in a background thread.

**M3 — Design system token drift**  
`styles.css` uses `--teal`, `--aqua`, `--ink`, etc. while `MASTER.md` defines `--color-primary`, `--color-secondary`, `--color-accent`, etc. and specifies `#0369A1` (blue) as the CTA accent, which is currently unused. **Fix**: align `styles.css` CSS variable names to the design system tokens; update the generate button to use `--color-accent` (`#0369A1`) per the spec.

**M4 — `app.js` readability**  
The entire JavaScript file is written as a single compressed block with no indentation or line breaks. **Fix**: write readable source; if minification is desired, add a simple build step (e.g., `esbuild`).

**M5 — `pyttsx3` not surfaced in the UI**  
Users enabling the narration checkbox will get a server-side `RuntimeError` if `pyttsx3` is not installed, with no pre-flight check. **Fix**: add a `GET /api/capabilities` endpoint that checks for `pyttsx3` availability (and optionally Ollama), and have the frontend display a warning before enabling narration.

### Low Priority

**L1 — `_is_fact_safe()` rupee symbol handling**  
The regex `[a-z0-9]+` strips non-ASCII characters including `₹`. A price like `₹1.25 Cr` contributes `1`, `25`, `cr` to the allowed set. An AI response containing `1` or `cr` in any context would pass. This is a minor edge case, but the fact-safety guarantee is slightly weaker for listings with currency symbols. **Fix**: include the literal price string in the allowed set as a whole, or extend the regex to preserve Unicode word characters.

**L2 — Lack of `tests/__init__.py`**  
No `tests/__init__.py` exists. While `unittest discover` works without it, adding one is conventional and enables absolute imports in test files.

**L3 — GSAP motion not implemented**  
`MASTER.md` specifies GSAP ScrollTrigger scroll-reveal animations. The current frontend has no GSAP; the `prefers-reduced-motion` media query in CSS is implemented but there is nothing to suppress. **Fix**: add GSAP + ScrollTrigger CDN links and implement the scroll-reveal pattern from `MASTER.md` on the hero and studio sections.

**L4 — No `favicon.ico`**  
The HTML has no `<link rel="icon">` and there is no favicon in `web/`. Minor polish issue.

**L5 — `features` Pydantic error surfaced raw**  
If features validation fails on the render path (e.g., >8 features), the 422 response contains a raw Pydantic error structure, not the friendlier `"detail"` string the frontend reads. **Fix**: add an exception handler or pre-validate the features count before constructing the `Listing` model.

---

## Conclusions

The project is a well-conceived, focused tool. The core invariant — that generated video content is strictly limited to submitted listing facts — is architecturally sound, correctly implemented, and tested. The video pipeline is complete and handles all major audio-mux combinations. The UI is functional and responsive.

The most important concrete defect is the **end-card text duplication** (H1) — it will visibly affect every render. The second most critical issue is the **synchronous render blocking the event loop** (H3), which is a FastAPI anti-pattern. Both are straightforward to fix without architectural changes.

The design system gap (M3) and the lack of GSAP animation (L3) represent incomplete implementation of the `MASTER.md` specification and would be the natural next round of UI polish work.
