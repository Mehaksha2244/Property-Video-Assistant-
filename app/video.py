from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
SCENE_DURATION = 4          # seconds per scene clip
FONT = Path("C:/Windows/Fonts/arial.ttf")


# ─── Feature-to-caption mapping ──────────────────────────────────────────────
_FEATURE_CAPTIONS: dict[str, str] = {
    "private balcony":  "Step out to your private balcony — mornings will never be the same.",
    "near metro":       "Seamlessly connected. The metro is just minutes away.",
    "metro":            "Seamlessly connected. The metro is just minutes away.",
    "24/7 security":    "Peace of mind, day and night. Secure living, always.",
    "security":         "Peace of mind, day and night. Secure living, always.",
    "modular kitchen":  "A kitchen built for those who love to cook.",
    "kitchen":          "A kitchen built for those who love to cook.",
    "gym and pool":     "Your lifestyle. Elevated. Gym and pool, right at home.",
    "gym":              "Stay fit without stepping out. Your personal gym is right here.",
    "pool":             "Dive into luxury. A sparkling pool awaits.",
    "swimming pool":    "Dive into luxury. A sparkling pool awaits.",
    "parking":          "Your vehicle, always safe. Dedicated parking included.",
    "lift":             "Modern living at every level. Elevator access throughout.",
    "power backup":     "Never in the dark. Full power backup, always on.",
    "garden":           "Breathe easy. Step into a lush private garden.",
    "terrace":          "Your rooftop retreat — a terrace made for golden evenings.",
    "clubhouse":        "Community and comfort. A world-class clubhouse at your doorstep.",
    "vaastu":           "Built with intention. Vaastu-compliant design for a harmonious home.",
    "semi-furnished":   "Move in ready. Semi-furnished and thoughtfully designed.",
    "furnished":        "Fully furnished. Just bring yourself.",
    "school":           "Top schools nearby — the perfect neighbourhood to raise a family.",
    "hospital":         "Healthcare close at hand. Leading hospitals just minutes away.",
    "park":             "Green spaces all around. A park right at your doorstep.",
}


def build_captions(listing: dict) -> list[str]:
    """Produce persuasive, human-sounding sales captions from listing facts.

    Uses up to 7 features so all uploaded images (4–8) each get a dedicated scene.
    Every caption is derived exclusively from submitted listing facts.
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


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"Video rendering failed: {result.stderr[-800:]}")


def _end_card(listing: dict, path: Path) -> None:
    """Render the end-card JPEG using Pillow. FFmpeg will NOT draw text on top of this."""
    canvas = Image.new("RGB", (W, H), "#073b3a")
    draw = ImageDraw.Draw(canvas)
    font_lg = ImageFont.truetype(str(FONT), 68)
    font_sm = ImageFont.truetype(str(FONT), 42)
    draw.text((W // 2, 720),  listing["property_name"], anchor="mm", font=font_lg, fill="white")
    draw.text((W // 2, 840),  listing["location"],      anchor="mm", font=font_sm, fill="#99f6e4")
    draw.text((W // 2, 1160), listing["price"],          anchor="mm", font=font_lg, fill="white")
    draw.text((W // 2, 1300), listing["cta"],            anchor="mm", font=font_sm, fill="white")
    canvas.save(path, quality=94)


def _scene(image: Path, caption: str, output: Path, work: Path) -> None:
    """Encode a single image into a SCENE_DURATION-second clip with a caption overlay.

    If caption is an empty string, the drawtext/drawbox filters are omitted so the
    image (e.g. an end card with Pillow-baked text) is encoded without a second text layer.
    """
    font_escaped = str(FONT).replace("\\", "/").replace(":", "\\:")

    zoom_crop = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        f"zoompan=z='min(zoom+0.0007,1.07)':d={FPS * SCENE_DURATION}:s={W}x{H}:fps={FPS}"
    )

    if caption:
        caption_file = work / f"{output.stem}.txt"
        caption_file.write_text(caption, encoding="utf-8")
        textfile_escaped = str(caption_file).replace("\\", "/").replace(":", "\\:")
        text_filters = (
            f",drawbox=x=0:y={H - 390}:w={W}:h=270:color=black@0.55:t=fill,"
            f"drawtext=fontfile='{font_escaped}':textfile='{textfile_escaped}':"
            f"fontcolor=white:fontsize=48:line_spacing=14:"
            f"x=(w-text_w)/2:y={H - 300}:text_shaping=1"
        )
    else:
        text_filters = ""

    filters = zoom_crop + text_filters

    _run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image),
        "-t", str(SCENE_DURATION),
        "-vf", filters,
        "-r", str(FPS),
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "medium",
        str(output),
    ])


def _narrate_one(text: str, output: Path) -> None:
    """Synthesise speech for a single caption and save to output (WAV)."""
    try:
        import pyttsx3
    except ImportError as error:
        raise RuntimeError(
            "Narration needs the optional package: pip install pyttsx3"
        ) from error
    engine = pyttsx3.init()
    engine.setProperty("rate", 155)          # slightly slower for clarity
    engine.save_to_file(text, str(output))
    engine.runAndWait()
    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError(
            "Local narration could not be created. "
            "Uncheck narration or install a Windows voice."
        )


def _pad_audio_to(audio: Path, duration: float, output: Path) -> None:
    """Trim or silence-pad audio to exactly `duration` seconds."""
    _run([
        "ffmpeg", "-y",
        "-i", str(audio),
        "-af", f"apad=whole_dur={duration}",
        "-t", str(duration),
        "-c:a", "pcm_s16le",
        str(output),
    ])


def _mux_audio_into_scene(video: Path, audio: Path, output: Path) -> None:
    """Combine a mute video clip with an audio track, keeping the video duration."""
    _run([
        "ffmpeg", "-y",
        "-i", str(video),
        "-i", str(audio),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac",
        "-shortest",
        str(output),
    ])


def _verify(path: Path) -> None:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    try:
        duration = float(json.loads(probe.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        duration = 0
    if probe.returncode or duration < 8:
        raise RuntimeError("Export verification failed. Please try different source images.")


# ─── Public render entry point ────────────────────────────────────────────────

def render_video(
    listing: dict,
    images: list[Path],
    output: Path,
    music: Path | None,
    narration: bool,
) -> None:
    work = output.parent / f"work-{output.stem}"
    work.mkdir(exist_ok=True)

    captions = build_captions(listing)
    # Reserve the last caption for the end card; match image count to available content captions.
    content_captions = captions[:-1]
    usable = images[: min(len(images), len(content_captions))]

    scenes: list[Path] = []

    try:
        # ── Build one scene clip per image ──────────────────────────────────
        for index, image in enumerate(usable):
            caption = content_captions[index]
            silent_scene = work / f"scene-{index:02}-silent.mp4"
            _scene(image, caption, silent_scene, work)

            if narration:
                # Generate speech for this caption, pad/trim to SCENE_DURATION
                raw_voice = work / f"voice-{index:02}.wav"
                padded_voice = work / f"voice-{index:02}-padded.wav"
                _narrate_one(caption, raw_voice)
                _pad_audio_to(raw_voice, SCENE_DURATION, padded_voice)

                scene_with_audio = work / f"scene-{index:02}.mp4"
                _mux_audio_into_scene(silent_scene, padded_voice, scene_with_audio)
                scenes.append(scene_with_audio)
            else:
                scenes.append(silent_scene)

        # ── End card (Pillow-rendered, no FFmpeg text overlay) ───────────────
        end_jpg = work / "end-card.jpg"
        _end_card(listing, end_jpg)
        end_silent = work / "scene-end-silent.mp4"
        _scene(end_jpg, "", end_silent, work)   # empty caption → no drawtext

        if narration:
            end_text = captions[-1]             # "Book a viewing. This is your home."
            raw_end_voice = work / "voice-end.wav"
            padded_end_voice = work / "voice-end-padded.wav"
            _narrate_one(end_text, raw_end_voice)
            _pad_audio_to(raw_end_voice, SCENE_DURATION, padded_end_voice)
            end_scene = work / "scene-end.mp4"
            _mux_audio_into_scene(end_silent, padded_end_voice, end_scene)
            scenes.append(end_scene)
        else:
            scenes.append(end_silent)

        # ── Concatenate all scenes ───────────────────────────────────────────
        concat = work / "playlist.txt"
        concat.write_text(
            "".join(f"file '{scene.as_posix()}'\n" for scene in scenes),
            encoding="utf-8",
        )
        silent_full = work / "silent.mp4"
        _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(silent_full)])

        # ── Mix background music (optional) ─────────────────────────────────
        if music:
            if narration:
                # Scenes already have narration baked in; duck the music under it
                _run([
                    "ffmpeg", "-y",
                    "-i", str(silent_full),
                    "-stream_loop", "-1", "-i", str(music),
                    "-filter_complex",
                    "[0:a]volume=1[v];[1:a]volume=0.12[m];[v][m]amix=inputs=2:duration=first[a]",
                    "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-shortest",
                    str(output),
                ])
            else:
                # No narration — music only
                _run([
                    "ffmpeg", "-y",
                    "-i", str(silent_full),
                    "-stream_loop", "-1", "-i", str(music),
                    "-filter:a", "volume=0.16",
                    "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-shortest",
                    str(output),
                ])
        else:
            silent_full.replace(output)

        _verify(output)

    finally:
        for item in work.glob("*"):
            item.unlink(missing_ok=True)
        work.rmdir()
