"""
04_STANDARDIZATION — normalize surface-level value inconsistencies BEFORE
entity resolution: state names, boolean-ish text, whitespace/case. Sequence
that matters: RAW -> STANDARDIZATION -> NORMALIZATION -> ENTITY RESOLUTION.
"""
import re

import pandas as pd

# Minimal state lookup for the MVP — extend with the full state/UT list.
STATE_ALIASES = {
    "delhi": "Delhi", "dl": "Delhi",
    "mh": "Maharashtra", "maharashtra": "Maharashtra",
    "up": "Uttar Pradesh", "u.p.": "Uttar Pradesh", "uttar pradesh": "Uttar Pradesh",
}

TRUTHY = {"yes", "y", "true", "1", "approved"}
FALSY = {"no", "n", "false", "0", "rejected", "not approved"}


def standardize_state(value: str) -> str:
    """
    Resolve a state value to its canonical name.

    Tries an exact alias match first (fast path for clean data). If that
    fails, falls back to searching the text for any known state token as a
    whole word — real source systems sometimes put junk/annotations around
    the actual state (e.g. "uttar pradesh's neighbor - Delhi"). If more than
    one state token is found, the LAST one wins, since messy free-text state
    fields in practice tend to correct/clarify toward the end
    ("<noise> - <actual state>"). If nothing matches, the original text is
    kept (title-cased) rather than guessed, so it's still visible for review
    instead of silently resolving to the wrong state.
    """
    if not isinstance(value, str):
        return value
    key = value.strip().lower()

    if key in STATE_ALIASES:
        return STATE_ALIASES[key]

    found = []
    for alias, canonical in STATE_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", key):
            found.append((key.rfind(alias), canonical))

    if found:
        found.sort(key=lambda x: x[0])  # by position in text
        return found[-1][1]             # last (rightmost) match wins

    return value.strip().title()


def standardize_boolean(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return None
    key = str(value).strip().lower()
    if key in TRUTHY:
        return True
    if key in FALSY:
        return False
    return None  # unrecognized — flag for review rather than guessing


def standardize_text(value: str) -> str:
    if not isinstance(value, str):
        return value
    return re.sub(r"\s+", " ", value).strip()


def standardize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "state" in df.columns:
        df["state"] = df["state"].apply(standardize_state)
    if "approval_status" in df.columns:
        df["approval_status"] = df["approval_status"].apply(standardize_boolean)
    for col in ("institution_name", "performance_remark"):
        if col in df.columns:
            df[col] = df[col].apply(standardize_text)
    return df

    # TODO: dates -> ISO 8601, phone/email normalization, abbreviation expansion


def standardize_all(mapped_sources: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {name: standardize_dataframe(df) for name, df in mapped_sources.items()}


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "01_INGESTION"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "03_SCHEMA_MAPPING"))
    from INGESTION_ENGINE import ingest_all
    from SCHEMA_MAPPER import map_all

    sample_dir = Path(__file__).resolve().parents[1] / "DATA" / "SAMPLE"
    raw = ingest_all(sample_dir)
    mapped = map_all(raw)
    std = standardize_all(mapped)
    for name, df in std.items():
        cols = [c for c in ("state", "approval_status") if c in df.columns]
        print(name, df[cols].to_dict("records") if cols else "(no state/approval cols)")
