"""Align audio timestamps to blog post paragraphs.

Usage: python align-audio.py <post.md> <audio.mp3> <output.json>

Generates a JSON file mapping each paragraph to start/end timestamps,
which the client-side scroll-sync player uses to highlight and scroll.

Uses word-count proportional distribution as the primary method,
with optional Whisper refinement when available.
"""

import json
import re
import sys
from pathlib import Path


def extract_paragraphs(md_path: str) -> list[dict]:
    """Extract paragraphs from a markdown post, skipping frontmatter."""
    text = Path(md_path).read_text(encoding="utf-8")

    # Strip frontmatter
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].strip()

    paragraphs = []
    current_idx = 0

    for block in re.split(r"\n{2,}", text):
        block = block.strip()
        if not block:
            continue

        # Clean markdown for word counting
        clean = block
        clean = re.sub(r"^#{1,6}\s+", "", clean)  # headers
        clean = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", clean)  # bold/italic
        clean = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", clean)  # links
        clean = re.sub(r"`(.+?)`", r"\1", clean)  # inline code
        clean = re.sub(r"[*_~`]", "", clean)  # remaining markers
        clean = re.sub(r"!\[.*?\]\(.*?\)", "", clean)  # image refs
        clean = " ".join(clean.split())  # normalize whitespace

        if len(clean) < 5:
            continue  # skip very short blocks (dividers, image captions, etc.)

        # Skip data sources / metadata sections
        if clean.startswith("Data Sources") or clean.startswith("Corporate financials"):
            continue

        word_count = len(clean.split())
        paragraphs.append({
            "index": current_idx,
            "text": clean[:100],
            "word_count": word_count,
        })
        current_idx += 1

    return paragraphs


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    import subprocess

    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", audio_path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def align_by_word_count(paragraphs: list[dict], duration: float) -> list[dict]:
    """Distribute timestamps proportionally by word count.

    Simple and reliable — if a paragraph has 10% of the words,
    it gets 10% of the audio time. Accounts for natural pauses
    between sections by adding a small buffer per paragraph.
    """
    total_words = sum(p["word_count"] for p in paragraphs)
    if total_words == 0:
        return []

    # Reserve ~2% of duration for inter-paragraph pauses
    pause_per_para = (duration * 0.02) / max(len(paragraphs), 1)
    speaking_duration = duration - (pause_per_para * len(paragraphs))

    aligned = []
    current_time = 0.0

    for para in paragraphs:
        proportion = para["word_count"] / total_words
        para_duration = speaking_duration * proportion

        start = round(current_time, 2)
        end = round(current_time + para_duration, 2)

        aligned.append({
            "index": para["index"],
            "start": start,
            "end": end,
            "confidence": 0.8,  # proportional estimate
        })

        current_time = end + pause_per_para

    return aligned


def refine_with_whisper(aligned: list[dict], audio_path: str) -> list[dict]:
    """Optionally refine timestamps using Whisper segment boundaries.

    If pywhispercpp is available, transcribe the audio and snap
    paragraph boundaries to the nearest Whisper segment boundary.
    This improves accuracy without requiring perfect text matching.
    """
    try:
        from pywhispercpp.model import Model
    except ImportError:
        print("  pywhispercpp not available — using word-count estimates only")
        return aligned

    print("  Refining with Whisper segment boundaries...")
    model = Model("base", print_progress=False)
    result = model.transcribe(audio_path)

    # Collect segment boundaries (transition points in the audio)
    boundaries = []
    for seg in result:
        boundaries.append(round(seg.t0 / 100, 2))
        boundaries.append(round(seg.t1 / 100, 2))
    boundaries = sorted(set(boundaries))

    if not boundaries:
        return aligned

    # Snap each paragraph start/end to nearest Whisper boundary
    def snap(t: float) -> float:
        closest = min(boundaries, key=lambda b: abs(b - t))
        # Only snap if within 3 seconds — don't make huge jumps
        if abs(closest - t) < 3.0:
            return closest
        return t

    refined = []
    for a in aligned:
        refined.append({
            "index": a["index"],
            "start": snap(a["start"]),
            "end": snap(a["end"]),
            "confidence": 0.9 if abs(snap(a["start"]) - a["start"]) < 3.0 else 0.8,
        })

    # Fix any overlaps or inversions from snapping
    for i in range(1, len(refined)):
        if refined[i]["start"] < refined[i - 1]["end"]:
            refined[i]["start"] = refined[i - 1]["end"]
        if refined[i]["start"] > refined[i]["end"]:
            refined[i]["end"] = refined[i]["start"] + 1.0

    return refined


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <post.md> <audio.mp3> <output.json>")
        sys.exit(1)

    post_path, audio_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]

    print(f"Extracting paragraphs from {post_path}...")
    paragraphs = extract_paragraphs(post_path)
    print(f"  Found {len(paragraphs)} paragraphs ({sum(p['word_count'] for p in paragraphs)} words)")

    print(f"Getting audio duration...")
    duration = get_audio_duration(audio_path)
    print(f"  Duration: {int(duration // 60)}m {int(duration % 60)}s")

    print("Aligning by word count...")
    aligned = align_by_word_count(paragraphs, duration)

    print("Attempting Whisper refinement...")
    aligned = refine_with_whisper(aligned, audio_path)

    output = {
        "paragraphs": aligned,
        "duration": round(duration, 2),
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
