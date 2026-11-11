from pathlib import Path

from riskcheck.detector import DictDetector
from riskcheck.dictionary import load_dictionary

ROOT = Path(__file__).resolve().parent.parent


def example_detector():
    return DictDetector(load_dictionary(ROOT / "examples" / "dictionary.example.yaml"))


def test_ideation_phrase_is_risk():
    assert example_detector().detect("요즘 진짜 죽고 싶어")["predicted"] == "risk"


def test_completed_act_phrase_is_risk():
    assert example_detector().detect("약을 다 먹었어")["predicted"] == "risk"


def test_idiom_is_none():
    assert example_detector().detect("배고파 죽겠다")["predicted"] == "none"


def test_listener_directed_is_none():
    # 듣는 상대에게 하는 말은 내장 제외 규칙이 뺀다
    assert example_detector().detect("야 죽고 싶냐?")["predicted"] == "none"


def test_lookalike_word_is_none():
    # '혼자 살아요' — 다른 단어에 걸쳐 생긴 글자는 잡지 않는다
    assert example_detector().detect("혼자 살아요")["predicted"] == "none"


def test_negation_still_caught_by_rule():
    # 규칙 단계의 한계: 부정문도 잡는다 (무르는 것은 모델 단계의 몫)
    assert example_detector().detect("죽고 싶다는 생각은 안 해")["predicted"] == "risk"


def test_jump_for_fun_is_none_with_default_dict():
    # 놀이·운동으로 뛰어내린다는 말은 위험이 아니다 (기본 사전 기준)
    detector = DictDetector(load_dictionary(ROOT / "dicts" / "default.yaml"))
    assert detector.detect("내일 번지점프대에서 뛰어내릴 거야")["predicted"] == "none"
    assert detector.detect("지금 옥상이야 뛰어내릴 거야")["predicted"] == "risk"


def test_matches_carry_pattern_id():
    result = example_detector().detect("자살하고 싶다")
    assert result["predicted"] == "risk"
    assert result["matches"][0]["pattern_id"] == "dg-risk-words"
