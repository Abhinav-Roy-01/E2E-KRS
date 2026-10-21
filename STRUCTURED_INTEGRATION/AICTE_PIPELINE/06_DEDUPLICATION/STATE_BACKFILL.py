"""
STATE_BACKFILL -- second-pass entity resolution for rows that have no state.

Why this exists: ENTITY_RESOLVER blocks on institution_name + state. Faculty
and scholarship rows only carry an institute NAME (no state), so they can
never land in the same block as the state-carrying institute rows -- every
distinct name variant became its own "institution". Result on the live mock
data: 1220 master entities where the registry has ~500.

This pass runs AFTER match_entities(). For every master entity whose rows
all have a blank state, it looks for a state-carrying entity with a
near-identical (normalized, token-sorted) name and, only when the match is
confident AND unambiguous, merges the state-less group into it and fills
in the state. Generic names that fit several states ("Government
Engineering College") are deliberately left alone -- forcing a merge there
would be wrong, and a few unmerged rows is the honest outcome.

Pure pandas + stdlib (difflib). No DB, no network, no new dependency.
"""
import re
from difflib import SequenceMatcher

import pandas as pd

_ABBREVIATIONS = {
    "engg": "engineering", "colg": "college", "inst": "institute",
    "tech": "technology", "poly": "polytechnic", "govt": "government",
    "gov": "government", "univ": "university", "mgmt": "management",
    "mgt": "management", "sci": "science",
}
_STOPWORDS = {"of", "the", "and", "for"}


def normalize_name(name) -> str:
    """lowercase, expand abbreviations, drop punctuation/stopwords, sort tokens."""
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return ""
    text = str(name).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = []
    for tok in text.split():
        tok = _ABBREVIATIONS.get(tok, tok)
        if tok not in _STOPWORDS:
            tokens.append(tok)
    return " ".join(sorted(tokens))


def _is_blank(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip() == ""


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    sm = SequenceMatcher(None, a, b)
    # cheap upper bounds first -- most pairs are nowhere near and this keeps
    # a few hundred x a few hundred comparisons fast
    if sm.real_quick_ratio() < 0.5 or sm.quick_ratio() < 0.5:
        return 0.0
    return sm.ratio()


def backfill_stateless_entities(df: pd.DataFrame, threshold: float = 0.92, margin: float = 0.04):
    """
    Returns (new_df, report). Requires columns: master_entity_id,
    institution_name, state. Does not modify the input frame.
    """
    out = df.copy()
    if not {"master_entity_id", "institution_name", "state"} <= set(out.columns):
        return out, {"skipped": "missing required columns"}

    out["_norm"] = out["institution_name"].map(normalize_name)
    blank_state = _is_blank(out["state"])
    has_name = out["_norm"] != ""

    # group-level: an entity is "state-less" only if NONE of its rows has a state
    group_has_state = (~blank_state).groupby(out["master_entity_id"]).transform("any")
    stateless_rows = out[~group_has_state & has_name]
    stateful_rows = out[~blank_state & has_name]

    entities_before = out["master_entity_id"].nunique()
    report = {"entities_before": entities_before, "stateless_entities": 0,
              "merged": 0, "ambiguous": 0, "unmatched": 0}

    if stateless_rows.empty or stateful_rows.empty:
        report["entities_after"] = entities_before
        return out.drop(columns="_norm"), report

    # candidate side: master id -> (state, set of normalized name variants)
    candidates = {}
    for mid, grp in stateful_rows.groupby("master_entity_id"):
        state = grp.loc[~_is_blank(grp["state"]), "state"].iloc[0]
        candidates[mid] = (state, set(grp["_norm"]))

    remap = {}       # stateless master id -> (target master id, state)
    for mid, grp in stateless_rows.groupby("master_entity_id"):
        report["stateless_entities"] += 1
        variants = set(grp["_norm"])

        scores = {}
        for cand_id, (_, cand_names) in candidates.items():
            best = 0.0
            for v in variants:
                if v in cand_names:
                    best = 1.0
                    break
                for c in cand_names:
                    best = max(best, _similarity(v, c))
            if best >= threshold:
                scores[cand_id] = best

        if not scores:
            report["unmatched"] += 1
            continue

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        top_id, top_score = ranked[0]
        ambiguous = any(
            other_score >= top_score - margin and candidates[other_id][0] != candidates[top_id][0]
            for other_id, other_score in ranked[1:]
        )
        if ambiguous:
            report["ambiguous"] += 1
            continue

        remap[mid] = (top_id, candidates[top_id][0])
        report["merged"] += 1

    for old_id, (new_id, state) in remap.items():
        mask = out["master_entity_id"] == old_id
        out.loc[mask, "master_entity_id"] = new_id
        # fill state too: DB_LOADER takes the FIRST row per master id for the
        # institution record, so any row may end up as the representative
        out.loc[mask & _is_blank(out["state"]), "state"] = state

    report["entities_after"] = out["master_entity_id"].nunique()
    return out.drop(columns="_norm"), report
