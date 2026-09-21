"""
Data Validation -- the stage this pipeline's own architecture diagram calls
for (Schema Mapping -> Standardization -> Normalization -> Deduplication ->
Entity Resolution -> Data Validation), but which didn't exist in code until
now. Runs right after entity resolution, right before canonical load
(08_POSTGRESQL) -- catches obviously-bad rows before they reach Postgres,
rather than crashing on a bad INSERT or silently loading garbage.

Deliberately simple, rule-based checks -- not a full Great Expectations
suite (great-expectations is in REQUIREMENTS.TXT for that future work, not
wired up yet; this is the contained version, not the escalated one).
Returns (valid_df, rejected_df) so the pipeline can report counts and
reasons rather than dropping rows silently.

Kept in 06_DEDUPLICATION/ rather than a new numbered folder -- it operates
directly on entity-resolution's output and renumbering every folder after
it for one new stage is more churn than the stage itself is worth.
"""
import pandas as pd

VALID_NAAC_GRADES = {"A++", "A+", "A", "B++", "B+", "B", "C"}


def validate_institutions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    reasons = pd.Series([""] * len(df), index=df.index)

    if "institution_name" in df.columns:
        blank_name = df["institution_name"].isna() | (df["institution_name"].astype(str).str.strip() == "")
        reasons = reasons.mask(blank_name, reasons + "blank institution_name; ")

    if "nirf_rank" in df.columns:
        rank_numeric = pd.to_numeric(df["nirf_rank"], errors="coerce")
        bad_rank = rank_numeric.notna() & (rank_numeric <= 0)
        reasons = reasons.mask(bad_rank, reasons + "nirf_rank <= 0; ")

    if "naac_grade" in df.columns:
        bad_grade = df["naac_grade"].notna() & ~df["naac_grade"].isin(VALID_NAAC_GRADES)
        reasons = reasons.mask(bad_grade, reasons + "naac_grade not in known set; ")

    is_valid = reasons == ""
    valid_df = df[is_valid].copy()
    rejected_df = df[~is_valid].copy()
    if not rejected_df.empty:
        rejected_df["rejection_reason"] = reasons[~is_valid]
    return valid_df, rejected_df


if __name__ == "__main__":
    sample = pd.DataFrame({
        "institution_name": ["IIT Delhi", "", None, "Valid College"],
        "nirf_rank": [1, 5, -3, None],
        "naac_grade": ["A++", "Z", "A", None],
    })
    valid, rejected = validate_institutions(sample)
    print(f"Valid: {len(valid)}, Rejected: {len(rejected)}")
    print(rejected)
