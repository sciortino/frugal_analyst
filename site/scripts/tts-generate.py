"""Generate TTS audio from a blog post using Kokoro TTS.

Usage: python tts-generate.py <post.md> <output.wav>

Extracts readable text from a markdown blog post (stripping frontmatter,
images, and markup), then synthesizes speech using Kokoro TTS with an
American English voice. Outputs a single concatenated WAV file.
"""

import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf


def extract_readable_text(md_path: str) -> str:
    """Extract clean, readable text from a markdown blog post.

    Strips frontmatter, images, links (keeps text), code blocks,
    and other markup that shouldn't be read aloud.
    """
    text = Path(md_path).read_text(encoding="utf-8")

    # Strip YAML frontmatter
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3 :].strip()

    # Remove image references: ![alt](url)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

    # Remove HTML image tags
    text = re.sub(r"<img[^>]*>", "", text)

    # Convert headers to plain text with a pause marker
    text = re.sub(r"^#{1,6}\s+(.+)$", r"\n\1.\n", text, flags=re.MULTILINE)

    # Remove horizontal rules
    text = re.sub(r"^---+\s*$", "", text, flags=re.MULTILINE)

    # Convert links to just their text: [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove bold/italic markers but keep text
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}(.+?)_{1,3}", r"\1", text)

    # Remove inline code backticks
    text = re.sub(r"`(.+?)`", r"\1", text)

    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)

    # Remove blockquote markers
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)

    # Remove table formatting (pipes)
    text = re.sub(r"\|", " ", text)

    # Remove caption-style italics (standalone italic lines)
    text = re.sub(r"^\*[^*]+\*\s*$", "", text, flags=re.MULTILINE)

    # Remove "Data Sources" / metadata footer sections
    lines = text.split("\n")
    cleaned_lines = []
    skip_rest = False
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("data sources") or stripped.lower().startswith(
            "corporate financials"
        ):
            skip_rest = True
        if skip_rest:
            continue
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)

    # Collapse multiple newlines into double newlines (paragraph breaks)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Clean up whitespace
    text = text.strip()

    return text


def generate_tts(text: str, output_path: str) -> None:
    """Generate TTS audio using Kokoro and save as WAV."""
    from kokoro import KPipeline

    # American English pipeline
    pipeline = KPipeline(lang_code="a")

    # Voice selection: af_heart is the default high-quality American female voice.
    # Other options: af_bella, af_nicole, af_sarah, am_adam, am_michael
    # Using af_heart for a professional, clear narration tone.
    voice = "af_heart"

    print(f"  Voice: {voice}")
    print(f"  Text length: {len(text)} chars, ~{len(text.split())} words")

    # Generate audio in chunks (Kokoro splits on the pattern)
    all_audio = []
    generator = pipeline(text, voice=voice, speed=1.0, split_pattern=r"\n+")

    for i, (gs, ps, audio) in enumerate(generator):
        if audio is not None:
            all_audio.append(audio)
            # Add a short pause between segments (0.3s of silence at 24kHz)
            pause = np.zeros(int(24000 * 0.3), dtype=np.float32)
            all_audio.append(pause)
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1} segments...")

    if not all_audio:
        print("Error: No audio generated", file=sys.stderr)
        sys.exit(1)

    # Concatenate all audio segments
    full_audio = np.concatenate(all_audio)

    # Trim trailing silence
    if len(full_audio) > 24000:
        full_audio = full_audio[: len(full_audio) - int(24000 * 0.3)]

    print(f"  Total segments: {i + 1}")
    print(f"  Duration: {len(full_audio) / 24000:.1f}s")

    # Write WAV file
    sf.write(output_path, full_audio, 24000)
    print(f"  Saved: {output_path}")


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <post.md> <output.wav>")
        sys.exit(1)

    post_path, output_path = sys.argv[1], sys.argv[2]

    print(f"Extracting text from {post_path}...")
    text = extract_readable_text(post_path)

    if not text.strip():
        print("Error: No readable text extracted from post", file=sys.stderr)
        sys.exit(1)

    print(f"Generating TTS audio...")
    generate_tts(text, output_path)
    print("TTS generation complete.")


if __name__ == "__main__":
    main()
