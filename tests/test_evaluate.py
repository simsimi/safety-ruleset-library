from pathlib import Path

from riskcheck.detector import DictDetector
from riskcheck.dictionary import load_dictionary
from riskcheck.evaluate import evaluate, load_jsonl, run_detector

ROOT = Path(__file__).resolve().parent.parent


def test_examples_reproduce_reference_metrics():
    """examples/의 참조 리포트와 같은 수치가 나와야 한다 (accuracy 0.8333, macro F1 0.85)."""
    dictionary = load_dictionary(ROOT / "examples" / "dictionary.example.yaml")
    testset = load_jsonl(ROOT / "examples" / "testset.example.jsonl")
    predictions = run_detector(testset, DictDetector(dictionary), dictionary.version)
    report = evaluate(testset, predictions)
    assert report["overall"] == {"accuracy": 0.8333, "macro_f1": 0.8286}
    assert report["binary_risk"]["recall"] == 0.8571
    assert report["counts"] == {"total": 12, "evaluated": 12, "errors": 0}
    assert [c["id"] for c in report["false_positives"]] == ["t-011"]
    assert [c["id"] for c in report["false_negatives"]] == ["t-012"]


def test_error_rows_are_excluded_from_denominator():
    testset = [{"id": "a", "text": "x", "label": "none"}]
    predictions = [{"id": "a", "stage": "dict", "predicted": None, "matches": [], "error": "boom"}]
    report = evaluate(testset, predictions)
    assert report["counts"] == {"total": 1, "evaluated": 0, "errors": 1}
    assert report["overall"]["accuracy"] is None


def test_certainty_and_subgroup_sections():
    """certainty 분리 집계와 소그룹 지표: ambiguous 방향별, certain-only, FP율."""
    testset = [
        {"id": "a", "text": "x", "label": "danger"},  # certain, 정답
        {"id": "b", "text": "x", "label": "none",
         "certainty": {"grade": "ambiguous"}, "note": "subgroup:indirect_question"},  # 과탐
        {"id": "c", "text": "x", "label": "danger",
         "certainty": {"grade": "ambiguous"}},  # 누락
        {"id": "d", "text": "x", "label": "none", "note": "subgroup:indirect_question"},  # 정답
    ]
    predictions = [
        {"id": "a", "stage": "dict", "predicted": "danger", "matches": []},
        {"id": "b", "stage": "dict", "predicted": "danger", "matches": []},
        {"id": "c", "stage": "dict", "predicted": "none", "matches": []},
        {"id": "d", "stage": "dict", "predicted": "none", "matches": []},
    ]
    report = evaluate(testset, predictions)
    cs = report["certainty_summary"]
    assert cs["counts"] == {"certain": 2, "ambiguous": 2, "needs_context": 0}
    assert cs["certain_only"]["n"] == 2 and cs["certain_only"]["accuracy"] == 1.0
    assert cs["ambiguous_directional"] == {
        "n": 2, "correct": 0, "miss": 1, "overcall": 1}
    sg = report["subgroup_metrics"]["indirect_question"]
    assert sg["n"] == 2 and sg["negatives"] == 2 and sg["fp_rate"] == 0.5


def test_cli_evaluate_writes_html_report(tmp_path):
    from riskcheck.cli import main
    out = tmp_path / "run"
    rc = main(["evaluate", "--dataset", str(ROOT / "data" / "testset.jsonl"),
               "--dict", str(ROOT / "dicts" / "default.yaml"), "--out", str(out)])
    assert rc == 0
    html = (out / "report_dict.html").read_text(encoding="utf-8")
    assert "위험판별 평가 리포트" in html and "사전 단계" in html
    assert "1.0000" in html  # 회귀 셋 정확도
    assert (out / "report_dict.md").exists() and (out / "report_dict.json").exists()


def test_pattern_stats_in_dict_report():
    testset = [
        {"id": "a", "text": "x", "label": "danger"},
        {"id": "b", "text": "x", "label": "none"},
        {"id": "c", "text": "x", "label": "none"},
    ]
    predictions = [
        {"id": "a", "stage": "dict", "predicted": "risk",
         "matches": [{"pattern_id": "p1", "matched": "x"}, {"pattern_id": "p2", "matched": "y"}]},
        {"id": "b", "stage": "dict", "predicted": "risk",
         "matches": [{"pattern_id": "p1", "matched": "x"}]},
        {"id": "c", "stage": "dict", "predicted": "none", "matches": []},
    ]
    report = evaluate(testset, predictions)
    # p1은 2건 히트 중 1건이 오탐(b), p2는 1건 히트·오탐 0
    assert report["pattern_stats"] == [
        {"pattern_id": "p1", "hits": 2, "fp_hits": 1},
        {"pattern_id": "p2", "hits": 1, "fp_hits": 0},
    ]
