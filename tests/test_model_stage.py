import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from riskcheck.evaluate import evaluate_combined, evaluate_model, model_label, run_model
from riskcheck.model import (FileScoresAdapter, HttpModelAdapter, StubModelAdapter,
                             validate_scores)

TH = {"depression": 0.5, "anxiety": 0.5}
TESTSET = [
    {"id": "a", "text": "우울해서 아무것도 하기 싫어", "label": "none"},
    {"id": "b", "text": "불안해서 잠이 안 와", "label": "none"},
    {"id": "c", "text": "오늘 점심 뭐 먹을까", "label": "none"},
    {"id": "d", "text": "죽고 싶어", "label": "danger"},
]


def test_validate_scores_fills_else():
    scores = validate_scores({"depression": 0.3, "anxiety": 0.2})
    assert scores == {"depression": 0.3, "anxiety": 0.2, "else": 0.5}
    with pytest.raises(ValueError):
        validate_scores({"depression": 1.5, "anxiety": 0.0})


def test_stub_adapter_and_labels():
    adapter = StubModelAdapter()
    rows = run_model(TESTSET, adapter, adapter.version)
    by_id = {r["id"]: r for r in rows}
    assert model_label(by_id["a"]["scores"], TH) == "risk"
    assert model_label(by_id["b"]["scores"], TH) == "risk"
    assert model_label(by_id["c"]["scores"], TH) == "none"
    assert all(r["predicted"] is None for r in rows)  # 판정은 채점 단계에서만


def test_margin_policy_requires_gap_over_else():
    # 마진: 임계값을 넘어도 else보다 margin 이상 크지 않으면 신호로 보지 않는다
    scores = {"depression": 0.55, "anxiety": 0.1, "else": 0.35}
    assert model_label(scores, TH) == "risk"
    assert model_label(scores, {**TH, "margin": 0.3}) == "none"  # 0.55-0.35=0.2 < 0.3
    assert model_label(scores, {**TH, "margin": 0.2}) == "risk"  # 경계값은 신호로 본다


def test_threshold_rescoring_without_rerun():
    rows = run_model(TESTSET, StubModelAdapter(), "stub")
    strict = evaluate_model(TESTSET, rows, {"depression": 0.95, "anxiety": 0.95})
    assert strict["binary_risk"]["recall"] == 0.0  # 스텁 점수 0.85가 임계값에 못 미침
    loose = evaluate_model(TESTSET, rows, TH)
    assert loose["counts"]["evaluated"] == 4


def test_model_errors_excluded_from_metrics():
    class Flaky:
        version = "flaky"

        def predict(self, text, item_id=None):
            if item_id == "b":
                raise RuntimeError("모델 서버 오류")
            return {"depression": 0.1, "anxiety": 0.1, "else": 0.8}

    rows = run_model(TESTSET, Flaky(), "flaky")
    report = evaluate_model(TESTSET, rows, TH)
    assert report["counts"] == {"total": 4, "evaluated": 3, "errors": 1}
    assert report["error_cases"][0]["id"] == "b"


def test_combined_dict_priority_and_model_lift():
    dict_rows = [
        {"id": "a", "stage": "dict", "predicted": "none", "matches": []},
        {"id": "b", "stage": "dict", "predicted": "none", "matches": []},
        {"id": "c", "stage": "dict", "predicted": "none", "matches": []},
        {"id": "d", "stage": "dict", "predicted": "danger", "matches": []},
    ]
    model_rows = run_model(TESTSET, StubModelAdapter(), "stub")
    report = evaluate_combined(TESTSET, dict_rows, model_rows, TH)
    # a(우울)·b(불안)는 모델이 danger로 올리고, d는 사전 판정 유지
    assert report["overall"]["accuracy"] == 0.5  # c(일치)·d(일치), a·b는 정답 none이라 오탐
    fp_ids = {c["id"] for c in report["false_positives"]}
    assert fp_ids == {"a", "b"}
    # 기여 분해: d는 사전 포착, a·b 오탐은 모델에서, c는 clean
    assert report["contribution"] == {
        "caught_by_dict": 1, "caught_by_model": 0, "missed": 0,
        "fp_from_dict": 0, "fp_from_model": 2, "clean_none": 1, "model_errors": 0}


def test_combined_gold_includes_sublabel_positives():
    # 통합 채점의 정답은 위해 라벨 또는 하위 라벨(우울/불안) 양성이다.
    # label=none이어도 우울 양성이면 정답 risk — 감정 신호 포착은 정탐으로 센다.
    testset = [
        {"id": "a", "text": "x", "label": "none",
         "sublabels": {"depression": True, "anxiety": False}},
        {"id": "b", "text": "x", "label": "none",
         "sublabels": {"depression": False, "anxiety": False}},
        {"id": "c", "text": "x", "label": "danger"},
    ]
    dict_rows = [{"id": i, "stage": "dict", "predicted": "none", "matches": []}
                 for i in ("a", "b", "c")]
    model_rows = [
        {"id": "a", "stage": "model", "predicted": None, "matches": [],
         "scores": {"depression": 0.9, "anxiety": 0.1, "else": 0.0}},
        {"id": "b", "stage": "model", "predicted": None, "matches": [],
         "scores": {"depression": 0.1, "anxiety": 0.1, "else": 0.8}},
        {"id": "c", "stage": "model", "predicted": None, "matches": [],
         "scores": {"depression": 0.1, "anxiety": 0.1, "else": 0.8}},
    ]
    report = evaluate_combined(testset, dict_rows, model_rows, TH)
    # a는 감정 신호로 정탐, b는 정탐(none), c는 위해인데 놓침
    assert report["binary_risk"]["recall"] == 0.5
    assert report["binary_risk"]["precision"] == 1.0
    assert report["false_positives"] == []
    assert report["contribution"]["caught_by_model"] == 1
    assert "gold_definition" in report
    # 미탐 사례(c)의 정답 근거는 위해 라벨
    assert report["false_negatives"][0]["gold_basis"] == "harm"


def test_sublabel_metrics_with_null_exclusion():
    testset = [
        {"id": "a", "text": "x", "label": "none", "sublabels": {"depression": True, "anxiety": False}},
        {"id": "b", "text": "x", "label": "none", "sublabels": {"depression": False, "anxiety": True}},
        {"id": "c", "text": "x", "label": "none", "sublabels": {"depression": None, "anxiety": False}},
        {"id": "d", "text": "x", "label": "none", "sublabels": {"depression": False, "anxiety": False}},
    ]
    rows = [
        {"id": "a", "stage": "model", "predicted": None, "matches": [],
         "scores": {"depression": 0.9, "anxiety": 0.1, "else": 0.0}},
        {"id": "b", "stage": "model", "predicted": None, "matches": [],
         "scores": {"depression": 0.8, "anxiety": 0.2, "else": 0.0}},
        {"id": "c", "stage": "model", "predicted": None, "matches": [],
         "scores": {"depression": 0.9, "anxiety": 0.9, "else": 0.0}},
        {"id": "d", "stage": "model", "predicted": None, "matches": [],
         "scores": {"depression": 0.1, "anxiety": 0.1, "else": 0.8}},
    ]
    report = evaluate_model(testset, rows, TH)
    sub = report["sublabel_metrics"]
    # 우울: 양성은 a만 (c는 null 제외), a 맞춤 + b 오탐
    assert sub["depression"]["support"] == 1 and sub["depression"]["recall"] == 1.0
    assert sub["depression"]["precision"] == 0.5
    # 불안: 양성은 b만, b를 놓침 (c는 우울 null이지만 불안 false라 포함)
    assert sub["anxiety"]["support"] == 1 and sub["anxiety"]["recall"] == 0.0
    # 합산: c는 한쪽 null이라 제외, a 맞춤 b 맞춤(우울 점수로) d 맞춤
    assert sub["any_signal"]["recall"] == 1.0


def test_file_adapter(tmp_path):
    path = tmp_path / "scores.jsonl"
    path.write_text(json.dumps({"id": "x", "scores": {"depression": 0.9, "anxiety": 0.0}}) + "\n",
                    encoding="utf-8")
    adapter = FileScoresAdapter({"path": str(path)})
    assert adapter.predict("아무 텍스트", "x")["depression"] == 0.9
    with pytest.raises(KeyError):
        adapter.predict("없음", "y")


def test_http_adapter_with_local_server():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["Content-Length"])
            json.loads(self.rfile.read(length))
            body = json.dumps({"result": {"depression": 0.9, "anxiety": 0.05}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        adapter = HttpModelAdapter({
            "url": f"http://127.0.0.1:{server.server_port}/predict",
            "response_map": {"depression": "result.depression", "anxiety": "result.anxiety"},
        })
        scores = adapter.predict("아무 발화")
        assert scores["depression"] == 0.9 and scores["else"] == pytest.approx(0.05)
    finally:
        server.shutdown()


def test_default_model_configs_are_wired():
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent.parent
    """기본 모델 설정이 함께 배포되는 실모델 폴더와 다운로드 도구를 가리키는지."""
    from riskcheck.model import load_model_config

    emotion = load_model_config(ROOT / "models" / "default-emotion.yaml")
    assert emotion["adapter"] == "local"
    assert emotion["local"]["path"] == "models/emotion-heads-v1"
    outputs = emotion["local"]["outputs"]
    assert outputs["depression"]["from"] == 6
    assert outputs["anxiety"]["from"] == 7

    harm = load_model_config(ROOT / "models" / "default-harm.yaml")
    assert harm["adapter"] == "local"
    assert harm["local"]["path"] == "models/harm-genuine-v2"
    assert harm["local"]["harm_output"]["from"] == 1
    assert harm["policy"] == {"confirm": 0.5, "standalone": 0.4}

    assert (ROOT / "tools" / "download_models.py").exists()
