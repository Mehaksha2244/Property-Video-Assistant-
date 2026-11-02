# Implementation Plan

## Context

Codebase facts grounded in code read during exploration:

- **Frontend**: `web/index.html` (single-page, vanilla HTML), `web/styles.css` (single minified rule block, CSS custom-props on `:root`), `web/app.js` (vanilla JS, no bundler).
- **Backend**: `app/video.py` (`build_captions()` caps features at `[:5]`; `render_video()` passes `captions[-1]` as the end-card caption, causing double text), `app/main.py` (FastAPI; calls `build_captions()` in both `/api/preview-script` and `/api/render`).
- **Tests**: `tests/test_video.py` — `python -m unittest discover -s tests`.
- **Verification**: `python -m py_compile app/video.py` / `app/main.py`; no bundler for JS so no build step.
- **Do NOT start the server.**

---

- [ ] 1. **Frontend layout/design overhaul** — `web/index.html` + `web/styles.css`

  Apply all visual fixes to the existing minified CSS block and update HTML attributes/classes as needed.

  **Specific changes in `web/styles.css`:**
  - `.hero`: change `padding` from `72px 28px 54px` → `44px 28px 36px`.
  - `.studio`: change `gap` from `24px` → `16px`. Keep `grid-template-columns: 1.35fr .8fr`.
  - `.fields`: keep `gap:18px` (already consistent).
  - `.panel`: change `border-radius` from `22px` → `24px`; add `border-top: 3px solid var(--teal)` alongside the existing `border:1px solid …`.
  - `.upload`: change `padding` from `18px` → `14px 16px`; keep dashed border and grid layout.
  - `.optional`: change `margin` from `20px 0` → `16px 0 20px`; keep `gap:20px`.
  - `.notice`: add `margin-top: 20px` (breathing room above it, distinct from the optional row).
  - `.generate`: change `background` from `var(--teal)` → `linear-gradient(135deg, var(--teal) 0%, #0e9488 100%)`; change hover `background` from `#095c56` → `linear-gradient(135deg,#095c56 0%,#0b7c72 100%)`; add `box-shadow: 0 4px 14px rgba(15,118,110,.35)` on hover.
  - `.eyebrow`: change `letter-spacing` from `.15em` → `.2em`.
  - **Add** a new rule `.nav-rule` for the animated gradient line below the nav:
    ```css
    .nav-rule{height:2px;background:linear-gradient(90deg,transparent,var(--teal),var(--aqua),var(--teal),transparent);background-size:200% 100%;animation:slide-rule 3s linear infinite}
    @keyframes slide-rule{0%{background-position:200% 0}100%{background-position:-200% 0}}
    ```
  - `.play` (empty-state icon): add `border: 2px solid var(--teal)` and `transition: transform .2s, box-shadow .2s`; add hover rule `.preview-empty:hover .play { transform: scale(1.12); box-shadow: 0 0 0 6px rgba(15,118,110,.15); }`.

  **Specific changes in `web/index.html`:**
  - After the `<header class="nav">…</header>` closing tag, insert `<div class="nav-rule"></div>`.

  **Files:** `web/styles.css`, `web/index.html`

  **Verify:** Open `web/index.html` source; confirm the `<div class="nav-rule">` element is present, the `<header>` tag is closed before it, and there are no unclosed tags. Run the Python syntax check in step 4 to confirm unrelated files are untouched.

---

- [ ] 2. **Video player with play button** — `web/index.html` + `web/app.js` + `web/styles.css`

  After a successful `/api/render` call, inject a `<video>` element beneath the captions list instead of only triggering a download. The existing download `<a>` click stays.

  **Changes in `web/app.js`:**
  - The current `display(data)` function renders captions only. Add an optional second path for when `data.download_url` is present.
  - Replace the current `display(data)` function with:
    ```js
    function display(data) {
      previewContent.className = '';
      const captionHtml = `<p class="eyebrow">FACT-SAFE SCENE PLAN</p>
        <h2>${data.ai_available ? 'AI-assisted outline' : 'Template outline'}</h2>
        ${data.ai_intro ? `<p class="ai-note">${data.ai_intro}</p>` : ''}
        <ol class="caption-list">${data.captions.map(c => `<li>${c}</li>`).join('')}</ol>`;
      const videoHtml = data.download_url
        ? `<video class="video-player" src="${data.download_url}" controls></video>`
        : '';
      previewContent.innerHTML = captionHtml + videoHtml;
    }
    ```
  - No other changes to `display`; the existing form `submit` handler already calls `display(data)` and then triggers the `<a>` download — both continue to work.

  **Changes in `web/styles.css`:**
  - Add the `.video-player` class rule:
    ```css
    .video-player{width:100%;border-radius:12px;margin-top:18px;display:block;background:#073b3a;max-height:500px}
    ```

  **No changes needed in `web/index.html`** — the `#preview-content` element that receives injected HTML already exists.

  **Files:** `web/app.js`, `web/styles.css`

  **Verify:** Review `app.js` for syntax: confirm `display()` function has balanced braces, template literals are closed, and no stray characters. Confirm `.video-player` rule is present in `styles.css`.

---

- [ ] 3. **Sales-pitch captions** — `app/video.py`

  Replace `build_captions()` entirely. The new version produces persuasive human-sounding sentences, uses up to 7 features (not 5), and returns enough captions for up to 8 images.

  **Replace the existing `build_captions` function in `app/video.py` with:**
  ```python
  # Feature-to-caption mapping for persuasive sales text
  _FEATURE_CAPTIONS: dict[str, str] = {
      "private balcony": "Step out to your private balcony — mornings will never be the same.",
      "near metro": "Seamlessly connected. The metro is just minutes away.",
      "24/7 security": "Peace of mind, day and night. Secure living, always.",
      "modular kitchen": "A kitchen built for those who love to cook.",
      "gym and pool": "Your lifestyle. Elevated. Gym and pool, right at home.",
  }

  def build_captions(listing: dict) -> list[str]:
      """Produce persuasive, human-sounding sales captions from listing facts.

      Returns at least len(features)+3 captions (title + type/price + one per feature + CTA)
      so that all uploaded images (up to 8) get a caption slot before the end card.
      """
      features = listing["features"][:7]
      captions: list[str] = [
          f"{listing['property_name']} — {listing['property_type']} in {listing['location']}",
          f"Priced at {listing['price']}. A home worth every rupee.",
      ]
      for feature in features:
          key = feature.strip().lower()
          caption = _FEATURE_CAPTIONS.get(key, f"Experience {feature} — crafted for modern living.")
          captions.append(caption)
      captions.append(f"{listing['cta']}. This is your home.")
      return captions
  ```

  Note: The existing test `test_captions_only_use_listing_facts` checks that listing facts appear in the joined caption text. The new captions include `property_name`, `location`, `price`, `property_type`, all features, and `cta`, so the test still passes. The test also checks `"swimming pool"` is not present — it won't be, since that word is not in any mapping key or fallback template.

  **Files:** `app/video.py`

  **Verify:** `python -m py_compile app/video.py` — exit code 0. Then `python -m unittest discover -s tests` — all tests pass.

---

- [ ] 4. **Image ordering fix + end-card double-text fix** — `app/video.py`

  Two fixes in `render_video()`:

  **Fix A — usable slice (already correct logic, but now guaranteed by step 3):**
  The existing line `usable = images[:min(len(images), len(captions) - 1)]` is already the correct slice formula. With the new `build_captions()` returning at least `len(features)+3` entries, a listing with 7 features and 8 images produces 10 captions, so `min(8, 10-1) = 8` — all 8 images are used. No code change needed for the slice itself; this fix is validated by step 3.

  **Fix B — end-card double text:** In `render_video()`, find the line:
  ```python
  _scene(end, captions[-1], end_scene, work)
  ```
  Change it to:
  ```python
  _scene(end, "", end_scene, work)
  ```
  This passes an empty string so FFmpeg draws no text overlay on the end card. The Pillow-drawn text from `_end_card()` is already baked into the JPEG, so the end card still shows `property_name`, `location`, `price`, and `cta` — without doubling.

  **Files:** `app/video.py`

  **Verify:** `python -m py_compile app/video.py` — exit code 0. `python -m unittest discover -s tests` — all tests pass.

---

- [ ] 5. **Final verification sweep** — all changed files

  Run the full verification suite in order. Do NOT start the server.

  1. `python -m py_compile app/video.py` — must exit 0.
  2. `python -m py_compile app/main.py` — must exit 0.
  3. `python -m unittest discover -s tests` — must report 2 tests, 0 failures.
  4. Review `web/index.html`: confirm no unclosed tags, `<div class="nav-rule">` is present after `</header>`, all existing structural elements (`<header>`, `<main>`, `<section class="studio">`, `<form>`, `<aside>`, `<div class="toast">`) are present and properly closed.
  5. Review `web/app.js`: confirm `display()` function template literal is closed, `video-player` class name matches the CSS rule from step 2, no stray semicolons or unclosed brackets.

  **Files:** read-only pass over all changed files; no new edits unless a compilation error is found.

  **Verify:** All commands above return exit code 0 with no errors.
