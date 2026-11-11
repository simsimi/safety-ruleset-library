"""위해 모델(옵션 슬롯) 단계 테스트: 어댑터, 결합 판정, 통합 평가."""
import json

import pytest

from riskcheck.evaluate import (evaluate_combined, evaluate_harm, harm_decision,
                                run_harm_model)
from riskcheck.model import (FileHarmAdapter, LocalHarmAdapter, StubHarmAdapter,
                             build_harm_adapter, harm_policy, resolve_harm_output)

POLICY = {"confirm": 0.5, "standalone": 0.4}


def test_harm_decision_mixed_policy():
    # 사전 포착분은 confirm 이상일 때만 확정
    assert harm_decision("risk", 0.9, POLICY) == "risk"
    assert harm_decision("risk", 0.45, POLICY) == "none"
    # 사전이 놓친 건은 standalone 이상이면 단독 승격
    assert harm_decision("none", 0.45, POLICY) == "risk"
    assert harm_decision("none", 0.3, POLICY) == "none"
    # 점수가 없으면 폴백 신호(None)
    assert harm_decision("risk", None, POLICY) is None


def test_harm_decision_or_form():
    # confirm=0이면 사전 판정을 그대로 확정한다 (기존 OR 결합과 같은 형태)
    policy = {"confirm": 0.0, "standalone": 0.5}
    assert harm_decision("risk", 0.1, policy) == "risk"
    assert harm_decision("none", 0.4, policy) == "none"


def test_harm_decision_confirm_only_form():
    # standalone이 1보다 크면 단독 승격이 꺼진다 (순수 확인형)
    policy = {"confirm": 0.5, "standalone": 2.0}
    assert harm_decision("none", 0.99, policy) == "none"
    assert harm_decision("risk", 0.99, policy) == "risk"


def test_harm_policy_defaults_and_overrides():
    assert harm_policy({}) == {"confirm": 0.5, "standalone": 0.4}
    assert harm_policy({"policy": {"confirm": 0.7}}, {"standalone": 0.3}) == \
        {"confirm": 0.7, "standalone": 0.3}


def test_stub_harm_adapter():
    adapter = StubHarmAdapter()
    assert adapter.predict("요즘 죽고 싶어")["harm"] >= 0.5
    assert adapter.predict("오늘 날씨 좋다")["harm"] < 0.5


def test_file_harm_adapter(tmp_path):
    path = tmp_path / "harm.jsonl"
    path.write_text(
        json.dumps({"id": "a", "harm": 0.83}) + "\n"
        + json.dumps({"id": "b", "scores": {"harm": 0.12}}) + "\n",
        encoding="utf-8")
    adapter = FileHarmAdapter({"path": str(path)})
    assert adapter.predict("무엇", "a") == {"harm": 0.83}
    assert adapter.predict("무엇", "b") == {"harm": 0.12}
    with pytest.raises(KeyError):
        adapter.predict("무엇", "c")


class _FakeBackend:
    class_labels = ["non_genuine", "genuine"]

    def logits(self, text):
        return [0.0, 2.0] if "위험" in text else [2.0, 0.0]


def test_local_harm_adapter_with_fake_backend():
    config = {"path": "dummy", "harm_output": {"from": 1, "activation": "softmax",
                                               "group": [0, 1]}}
    adapter = LocalHarmAdapter(config, backend=_FakeBackend())
    assert adapter.predict("위험한 발화")["harm"] > 0.8
    assert adapter.predict("평온한 발화")["harm"] < 0.2


def test_resolve_harm_output_by_name():
    resolved = resolve_harm_output(
        {"from": "genuine", "activation": "softmax", "group": ["non_genuine", "genuine"]},
        ["non_genuine", "genuine"])
    assert resolved[0] == [1]
    assert resolved[2] == (0, 1)


def _testset():
    return [
        {"id": "t1", "text": "사전이 잡고 위해도 높은 진성", "label": "danger"},
        {"id": "t2", "text": "사전이 잡았지만 위해가 낮은 비진성", "label": "none"},
        {"id": "t3", "text": "사전은 놓쳤지만 위해가 높은 진성", "label": "danger"},
        {"id": "t4", "text": "둘 다 놓친 진성", "label": "danger"},
        {"id": "t5", "text": "평범한 비진성", "label": "none"},
    ]


def _dict_rows():
    return [
        {"id": "t1", "stage": "dict", "predicted": "risk", "matches": []},
        {"id": "t2", "stage": "dict", "predicted": "risk", "matches": []},
        {"id": "t3", "stage": "dict", "predicted": "none", "matches": []},
        {"id": "t4", "stage": "dict", "predicted": "none", "matches": []},
        {"id": "t5", "stage": "dict", "predicted": "none", "matches": []},
    ]


def _harm_rows():
    scores = {"t1": 0.9, "t2": 0.3, "t3": 0.8, "t4": 0.2, "t5": 0.1}
    return [{"id": i, "stage": "harm", "predicted": None, "matches": [],
             "scores": {"harm": s}} for i, s in scores.items()]


def test_combined_with_harm_policy():
    report = evaluate_combined(_testset(), _dict_rows(), None,
                               {"depression": 0.5, "anxiety": 0.5},
                               _harm_rows(), POLICY)
    # t1 확인 통과(포착), t2 확인 탈락(정상 판정), t3 단독 승격(포착), t4 미탐, t5 정상
    assert report["binary_risk"]["recall"] == round(2 / 3, 4)
    assert report["binary_risk"]["precision"] == 1.0
    c = report["contribution"]
    assert c["caught_by_dict"] == 1
    assert c["caught_by_harm"] == 1
    assert c["missed"] == 1
    assert c["dict_dropped_by_harm"] == 1
    assert c["fp_from_dict"] == 0
    assert report["harm_policy"] == POLICY


def test_combined_without_harm_unchanged():
    # 감정 모델 행(전부 무신호)을 함께 줘서 기여 분해가 생기는 경로로 확인한다
    model_rows = [{"id": t["id"], "stage": "model", "predicted": None, "matches": [],
                   "scores": {"depression": 0.1, "anxiety": 0.1, "else": 0.8}}
                  for t in _testset()]
    report = evaluate_combined(_testset(), _dict_rows(), model_rows,
                               {"depression": 0.5, "anxiety": 0.5})
    # 위해 모델이 없으면 사전 판정 그대로: t1·t2 risk → recall 1/3, precision 1/2
    assert report["binary_risk"]["recall"] == round(1 / 3, 4)
    assert report["binary_risk"]["precision"] == 0.5
    assert "caught_by_harm" not in report["contribution"]
    assert "harm_policy" not in report


def test_evaluate_harm_standalone_and_confirm():
    report = evaluate_harm(_testset(), _harm_rows(), POLICY)
    # standalone 0.4: t1·t3 risk → recall 2/3, precision 1.0
    assert report["binary_risk"]["recall"] == round(2 / 3, 4)
    # confirm 0.5도 같은 결과 (0.45 구간 케이스 없음)
    assert report["harm_confirm_metrics"]["recall"] == round(2 / 3, 4)
    assert report["policy"] == POLICY


def test_run_harm_model_error_fallback():
    class _Bad:
        version = "bad"

        def predict(self, text, item_id=None):
            raise RuntimeError("모델 오류")

    rows = run_harm_model(_testset(), _Bad(), "bad")
    assert all(r.get("error") for r in rows)
    # 오류 건은 위해 결합을 건너뛰고 사전 판정으로 평가된다
    report = evaluate_combined(_testset(), _dict_rows(), None,
                               {"depression": 0.5, "anxiety": 0.5}, rows, POLICY)
    assert report["contribution"]["harm_errors"] == 5
    assert report["binary_risk"]["recall"] == round(1 / 3, 4)


def test_build_harm_adapter_kinds():
    assert isinstance(build_harm_adapter({"adapter": "stub"}), StubHarmAdapter)
    with pytest.raises(ValueError):
        build_harm_adapter({"adapter": "unknown"})


def test_default_model_config_available():
    # 기본 구성(사전+감정 모델): 기본 모델 가중치가 준비된 환경에서만 설정이 잡힌다.
    # 미준비 환경(tools/download_models.py 실행 전)에서는 검증할 대상이 없어 건너뛴다.
    from riskcheck.cli import _default_model_config

    config = _default_model_config()
    if config is None:
        pytest.skip("기본 모델 미준비 환경 (tools/download_models.py 실행 전)")
    assert config["adapter"] == "local"


def test_default_harm_config_available():
    # 위해 모델도 기본 구성이다: 가중치가 준비된 환경에서만 설정이 잡힌다.
    from riskcheck.cli import _default_harm_config

    config = _default_harm_config()
    if config is None:
        pytest.skip("기본 위해 모델 미준비 환경 (tools/download_models.py 실행 전)")
    assert config["adapter"] == "local"
    assert config["policy"]["confirm"] == 0.5
