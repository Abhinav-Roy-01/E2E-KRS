"""
06_DEDUPLICATION -- resolve "IIT Delhi" / "IIT-D" / "Indian Institute of
Technology, Delhi" into one canonical entity ID.

Rule-based matcher, now in two passes:

  Pass 1 (anchors): rows that HAVE a state are blocked on
      canonical-name + state, exactly as before.
  Pass 2 (state-less rows): faculty and scholarship sources carry only an
      institute NAME, no state. Blocking on name|state meant every one of
      those rows became its own brand-new "institution" (~715 phantom
      entities on the live data). Now each state-less row is matched against
      the anchors by name alone: first exact canonical-name, then fuzzy
      similarity. A match is only accepted when it is UNAMBIGUOUS -- if the
      same name exists in several states ("Government Engineering College"),
      or two different anchors score nearly the same, the row is left as its
      own entity rather than guessed onto the wrong institution.

Canonical name = lowercase, punctuation stripped, common abbreviations
expanded (engg -> engineering, inst -> institute, ...), filler words
removed, tokens sorted -- so word order and abbreviations no longer split
one institute into two ("Kanpur Bapatla Engineering College" ==
"Bapatla College of Engineering, Kanpur").

Known limits (not solved here): a truncated name ("SRM Poly.") will not
match "SRM Polytechnic, South Delhi"; and two state-HAVING rows with a
typo in the name still need an exact canonical match to merge. Swap in a
Splink Linker if volumes justify probabilistic matching.
"""
import difflib
import re
from pathlib import Path

import pandas as pd
import yaml  # noqa: F401  (kept: CONFIG.YAML-driven threshold is the planned next step)

CONFIG_PATH = Path(__file__).resolve().parents[1] / "13_CONFIG" / "CONFIG.YAML"

_ABBREVIATIONS = {
    "engg": "engineering", "colg": "college", "coll": "college",
    "inst": "institute", "tech": "technology", "poly": "polytechnic",
    "mgmt": "management", "govt": "government", "gov": "government",
    "univ": "university", "sci": "science",
}
_FILLER_WORDS = {"of", "the", "and", "for"}

LAST_STATS: dict = {}


def _normalize_name(name: str | object) -> str:
    if pd.isna(name):
        return ""
    name = str(name)
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", " ", name)          # strip punctuation (IIT-D -> iit d)
    name = re.sub(r"\b(indian institute of technology|iit)\b", "iit", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _canonical_key(name: str | object) -> str:
    tokens = [_ABBREVIATIONS.get(t, t) for t in _normalize_name(name).split()]
    tokens = [t for t in tokens if t not in _FILLER_WORDS]
    return " ".join(sorted(set(tokens)))


def _best_fuzzy_block(key: str, key_to_blocks: dict, anchor_keys: list, threshold: float):
    """Best unambiguous anchor for `key` by similarity, or None."""
    best_score, best_key = 0.0, None
    second_score, second_key = 0.0, None
    for ak in anchor_keys:
        sm = difflib.SequenceMatcher(None, key, ak)
        if sm.real_quick_ratio() < threshold or sm.quick_ratio() < threshold:
            continue
        score = sm.ratio()
        if score < threshold:
            continue
        if score > best_score:
            second_score, second_key = best_score, best_key
            best_score, best_key = score, ak
        elif score > second_score:
            second_score, second_key = score, ak

    if best_key is None:
        return None
    best_blocks = key_to_blocks[best_key]
    if len(best_blocks) != 1:
        return None                      # same name in several states -- cannot pick one
    if second_key is not None and key_to_blocks[second_key] != best_blocks and best_score - second_score < 0.03:
        return None                      # two different institutes score almost equally
    return next(iter(best_blocks)), best_score


def match_entities(all_rows: pd.DataFrame, threshold: float = 0.9) -> pd.DataFrame:
    """
    Adds `master_entity_id` and `match_score` columns.
    match_score: 1.0 = exact name+state block; 0.95 = state-less row matched
    by exact canonical name; <0.95 = state-less row matched by fuzzy
    similarity (the similarity itself).
    """
    df = all_rows.copy()
    df["institution_name"] = df["institution_name"].fillna("")
    df["state"] = df["state"].fillna("")
    df["_key"] = df["institution_name"].apply(_canonical_key)
    df["_state_key"] = df["state"].astype(str).str.strip().str.lower()
    df["_block_key"] = df["_key"] + "|" + df["_state_key"]
    df["match_score"] = 1.0

    has_name = df["_key"] != ""
    has_state = df["_state_key"] != ""

    anchors = df[has_name & has_state]
    key_to_blocks = anchors.groupby("_key")["_block_key"].agg(lambda s: set(s)).to_dict()
    anchor_keys = list(key_to_blocks)

    stateless_idx = df.index[has_name & ~has_state]
    resolution = {}   # distinct stateless key -> (block, score) or None
    counts = {"exact_name": 0, "fuzzy": 0, "unresolved": 0}

    for key in df.loc[stateless_idx, "_key"].unique():
        result = None
        if key in key_to_blocks:
            blocks = key_to_blocks[key]
            if len(blocks) == 1:
                result = (next(iter(blocks)), 0.95)
        else:
            result = _best_fuzzy_block(key, key_to_blocks, anchor_keys, threshold)
        resolution[key] = result

    for idx in stateless_idx:
        result = resolution[df.at[idx, "_key"]]
        if result is None:
            counts["unresolved"] += 1
            continue
        block, score = result
        df.at[idx, "_block_key"] = block
        df.at[idx, "match_score"] = round(score, 3)
        counts["exact_name" if score == 0.95 else "fuzzy"] += 1

    LAST_STATS.clear()
    LAST_STATS.update(counts, stateless_total=len(stateless_idx))
    if len(stateless_idx):
        print(f"  [entity resolution] {len(stateless_idx)} state-less rows: "
              f"{counts['exact_name']} matched by exact name, {counts['fuzzy']} by fuzzy match, "
              f"{counts['unresolved']} left as separate entities (ambiguous or no match)")

    block_to_id = {key: f"INST_{i:04d}" for i, key in enumerate(sorted(df["_block_key"].unique()))}
    df["master_entity_id"] = df["_block_key"].map(block_to_id)

    return df.drop(columns=["_key", "_state_key", "_block_key"])


def extract_internship_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Return internship rows when the source schema contains internship fields."""
    required = [
        "student_name", "company", "duration", "internship_year",
        "performance_remark", "institution_name",
        "source_database", "source_table", "source_record_id",
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        return pd.DataFrame(columns=required)
    return df.dropna(subset=["student_name", "company"])[required].copy()


def assign_internship_ids(internship_rows: pd.DataFrame) -> pd.DataFrame:
    """
    Generates a stable internship_id since no source system provides one.
    Blocks on student_name + company + internship_year -- good enough for
    the MVP; a student with two internships at the same company in the
    same year would collide (accepted trade-off, revisit if it matters).
    """
    df = internship_rows.copy()
    if df.empty:
        return df.assign(internship_id=pd.Series(dtype="string"))
    df["_block_key"] = (
        df["student_name"].fillna("").astype(str).str.lower().str.strip() + "|" +
        df["company"].fillna("").astype(str).str.lower().str.strip() + "|" +
        df["internship_year"].fillna(0).astype(str)
    )

    block_to_id = {key: f"INTERN_{i:04d}" for i, key in enumerate(sorted(df["_block_key"].unique()))}
    df["internship_id"] = df["_block_key"].map(block_to_id)

    return df.drop(columns=["_block_key"])


def build_entity_mapping(resolved_df: pd.DataFrame) -> pd.DataFrame:
    """source_record -> master_entity_id lineage table (for ENTITY_MAPPING in Postgres)."""
    return resolved_df[[
        "master_entity_id", "institution_name", "source_system",
        "source_database", "source_record_id", "match_score",
    ]]


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "01_INGESTION"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "03_SCHEMA_MAPPING"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "04_STANDARDIZATION"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "05_NORMALIZATION"))
    from INGESTION_ENGINE import ingest_all
    from SCHEMA_MAPPER import map_all
    from STANDARDIZER import standardize_all
    from NORMALIZER import normalize_all

    sample_dir = Path(__file__).resolve().parents[1] / "DATA" / "SAMPLE"
    normalized = normalize_all(standardize_all(map_all(ingest_all(sample_dir))))
    combined = pd.concat(normalized.values(), ignore_index=True)
    resolved = match_entities(combined)
    print(build_entity_mapping(resolved).to_string(index=False))
