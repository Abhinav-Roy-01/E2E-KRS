"""
Language detection. Ratio-based (not raw-count) so a short repeated
non-English phrase in a mostly-English document doesn't falsely dominate
(the bug we found and fixed earlier in this project).
"""
from langdetect import detect, DetectorFactory

DetectorFactory.seed = 0

SCRIPT_RANGES = {
    "ml": (0x0D00, 0x0D7F),
    "hi": (0x0900, 0x097F),
    "ta": (0x0B80, 0x0BFF),
    "kn": (0x0C80, 0x0CFF),
    "te": (0x0C00, 0x0C7F),
    "bn": (0x0980, 0x09FF),
}

DOMINANCE_RATIO_THRESHOLD = 0.3
MIN_SCRIPT_CHARS = 15


def detect_language(text: str, sample_chars: int = 2000) -> str:
    sample = text[:sample_chars]

    script_counts = {lang: 0 for lang in SCRIPT_RANGES}
    total_alpha = 0
    for ch in sample:
        if not ch.isalpha():
            continue
        total_alpha += 1
        codepoint = ord(ch)
        for lang, (lo, hi) in SCRIPT_RANGES.items():
            if lo <= codepoint <= hi:
                script_counts[lang] += 1
                break

    if total_alpha > 0:
        best_lang, best_count = max(script_counts.items(), key=lambda kv: kv[1])
        ratio = best_count / total_alpha
        if best_count >= MIN_SCRIPT_CHARS and ratio >= DOMINANCE_RATIO_THRESHOLD:
            return best_lang

    try:
        return detect(sample)
    except Exception:
        return "unknown"
