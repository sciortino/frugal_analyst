"""Align audio timestamps to blog post paragraphs using Whisper.

Usage: python align-audio.py <post.md> <audio.mp3> <output.json>

Generates a JSON file mapping each paragraph to start/end timestamps,
which the client-side scroll-sync player uses to highlight and scroll.
"""

import json
import re
import sys
from difflib import SequenceMatcher
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

        # Clean markdown for text matching
        clean = block
        clean = re.sub(r"^#{1,6}\s+", "", clean)  # headers
        clean = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", clean)  # bold/italic
        clean = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", clean)  # links
        clean = re.sub(r"`(.+?)`", r"\1", clean)  # inline code
        clean = re.sub(r"[*_~`]", "", clean)  # remaining markers
        clean = " ".join(clean.split())  # normalize whitespace

        if len(clean) < 10:
            continue  # skip very short blocks (dividers, etc.)

        paragraphs.append({
            "index": current_idx,
            "text": clean[:200],  # first 200 chars for matching
            "is_header": block.startswith("#"),
        })
        current_idx += 1

    return paragraphs


def transcribe_with_timestamps(audio_path: str) -> list[dict]:
    """Transcribe audio with segment timestamps using pywhispercpp.

    Uses whisper.cpp C++ bindings — runs locally, no PyTorch or API keys needed.
    Works on both Intel and Apple Silicon Macs.
    """
    from pywhispercpp.model import Model

    model = Model("base", print_progress=False)
    result = model.transcribe(audio_path)

    segments = []
    for seg in result:
        segments.append({
            "start": round(seg.t0 / 100, 2),
            "end": round(seg.t1 / 100, 2),
            "text": seg.text.strip(),
        })

    return segments


def align_paragraphs_to_segments(
    paragraphs: list[dict],
    segments: list[dict],
) -> list[dict]:
    """Map paragraphs to audio timestamps by fuzzy text matching."""
    if not segments or not paragraphs:
        return []

    # Build a running transcript with segment indices
    full_transcript = ""
    segment_positions = []  # (char_start, char_end, segment_idx)

    for i, seg in enumerate(segments):
        start_pos = len(full_transcript)
        full_transcript += seg["text"] + " "
        end_pos = len(full_transcript)
        segment_positions.append((start_pos, end_pos, i))

    full_lower = full_transcript.lower()

    aligned = []
    search_start = 0  # Track position in transcript to enforce ordering

    for para in paragraphs:
        para_text = para["text"].lower()[:150]  # Use first 150 chars for matching

        # Find best matching position in the transcript after search_start
        best_ratio = 0.0
        best_pos = -1
        window_size = len(para_text)

        # Slide a window through the remaining transcript
        search_region = full_lower[search_start:]
        for offset in range(0, max(1, len(search_region) - window_size + 1), 20):
            candidate = search_region[offset:offset + window_size]
            ratio = SequenceMatcher(None, para_text, candidate).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_pos = search_start + offset

        if best_ratio < 0.3 or best_pos == -1:
            # No good match — interpolate from neighbors
            aligned.append({
                "index": para["index"],
                "start": None,
                "end": None,
                "confidence": 0.0,
            })
            continue

        # Find which segment corresponds to this position
        start_seg = None
        end_seg = None
        match_end = best_pos + window_size

        for char_start, char_end, seg_idx in segment_positions:
            if char_start <= best_pos < char_end and start_seg is None:
                start_seg = seg_idx
            if char_start < match_end <= char_end:
                end_seg = seg_idx
                break
            if char_start >= match_end:
                end_seg = max(0, seg_idx - 1)
                break

        if start_seg is None:
            start_seg = 0
        if end_seg is None:
            end_seg = len(segments) - 1

        aligned.append({
            "index": para["index"],
            "start": segments[start_seg]["start"],
            "end": segments[end_seg]["end"],
            "confidence": round(best_ratio, 2),
        })

        # Advance search to avoid re-matching earlier content
        search_start = best_pos + window_size // 2

    # Interpolate missing timestamps
    for i, a in enumerate(aligned):
        if a["start"] is not None:
            continue
        # Find nearest neighbors with timestamps
        prev_end = 0.0
        next_start = segments[-1]["end"] if segments else 0.0
        for j in range(i - 1, -1, -1):
            if aligned[j]["end"] is not None:
                prev_end = aligned[j]["end"]
                break
        for j in range(i + 1, len(aligned)):
            if aligned[j]["start"] is not None:
                next_start = aligned[j]["start"]
                break
        a["start"] = round(prev_end, 2)
        a["end"] = round(next_start, 2)
        a["confidence"] = 0.1  # interpolated

    return aligned


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <post.md> <audio.mp3> <output.json>")
        sys.exit(1)

    post_path, audio_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]

    print(f"Extracting paragraphs from {post_path}...")
    paragraphs = extract_paragraphs(post_path)
    print(f"  Found {len(paragraphs)} paragraphs")

    print(f"Transcribing {audio_path} with Whisper...")
    segments = transcribe_with_timestamps(audio_path)
    print(f"  Got {len(segments)} segments")

    print("Aligning paragraphs to audio...")
    aligned = align_paragraphs_to_segments(paragraphs, segments)

    good = sum(1 for a in aligned if a["confidence"] >= 0.3)
    print(f"  Aligned {good}/{len(aligned)} paragraphs (confidence >= 0.3)")

    output = {
        "paragraphs": aligned,
        "duration": segments[-1]["end"] if segments else 0,
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
