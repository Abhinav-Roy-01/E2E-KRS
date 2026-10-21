"""Run: python TEST_STATE_BACKFILL.py   (plain asserts, no pytest needed)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "06_DEDUPLICATION"))
import pandas as pd
from STATE_BACKFILL import backfill_stateless_entities, normalize_name


def test_normalize():
    assert normalize_name("Reva Institute of Technology, Gwalior") == normalize_name("Gwalior Reva Inst. of Tech.")
    assert normalize_name("Govt. Engg. Colg., Ajmer") == normalize_name("Government Engineering College, Ajmer")
    assert normalize_name(None) == "" and normalize_name(float("nan")) == ""


def build():
    rows = [
        # stateful anchors
        ("INST_1", "Reva Institute of Technology, Gwalior", "Madhya Pradesh"),
        ("INST_2", "Government Engineering College, Ajmer", "Rajasthan"),
        ("INST_3", "Government Engineering College, Bikaner", "Rajasthan"),
        ("INST_4", "Government Engineering College", "Karnataka"),
        ("INST_5", "Government Engineering College", "Kerala"),
        ("INST_6", "Manipal Institute of Technology", "Karnataka"),
        # stateless groups (each its own entity before the fix)
        ("INST_10", "Gwalior Reva Inst. of Tech.", ""),               # noisy variant -> INST_1
        ("INST_11", "Government Engg. Colg., Ajmer", None),            # abbreviations -> INST_2
        ("INST_12", "Government Engineering College", ""),            # generic, ambiguous -> stays
        ("INST_13", "Totally Unknown Academy of Arts", ""),           # no match -> stays
        ("INST_14", "", ""),                                           # blank name -> stays
    ]
    return pd.DataFrame(rows, columns=["master_entity_id", "institution_name", "state"])


def test_backfill():
    df = build()
    before = df.copy()
    out, report = backfill_stateless_entities(df)

    ids = dict(zip(out["institution_name"] + "|" + out.index.astype(str), out["master_entity_id"]))
    by_row = out["master_entity_id"].tolist()
    assert by_row[6] == "INST_1", by_row          # Reva variant merged
    assert by_row[7] == "INST_2", by_row          # Ajmer abbreviation variant merged
    assert by_row[8] == "INST_12"                 # ambiguous generic left alone
    assert by_row[9] == "INST_13"                 # unmatched left alone
    assert by_row[10] == "INST_14"                # blank name left alone
    assert out.loc[6, "state"] == "Madhya Pradesh" and out.loc[7, "state"] == "Rajasthan"
    assert out.loc[8, "state"] == ""              # state not invented for ambiguous row
    assert report["merged"] == 2 and report["ambiguous"] == 1, report
    assert report["entities_after"] == report["entities_before"] - 2, report
    pd.testing.assert_frame_equal(df, before)    # input frame untouched
    # already-stateful rows never move
    assert by_row[:6] == ["INST_1", "INST_2", "INST_3", "INST_4", "INST_5", "INST_6"]


def test_missing_columns_is_noop():
    df = pd.DataFrame({"x": [1]})
    out, report = backfill_stateless_entities(df)
    assert "skipped" in report and out.equals(df)


if __name__ == "__main__":
    test_normalize(); test_backfill(); test_missing_columns_is_noop()
    print("ALL STATE_BACKFILL TESTS PASSED")
