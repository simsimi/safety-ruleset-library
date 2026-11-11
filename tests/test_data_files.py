"""레포에 들어 있는 데이터 파일들이 스키마를 지키는지 검증한다."""
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent


def validator(name):
    schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def rows(name):
    return [json.loads(l) for l in (ROOT / "data" / name).read_text(encoding="utf-8").splitlines() if l.strip()]


@pytest.mark.parametrize("name", ["testset.jsonl", "evalset_human.jsonl",
                                  "evalset_balanced30.jsonl", "context_needed.jsonl", "holdout.jsonl"])
def test_datasets_follow_schema(name):
    v = validator("testset.schema.json")
    data = rows(name)
    for row in data:
        assert list(v.iter_errors(row)) == [], f"{name}:{row.get('id')}"
    ids = [r["id"] for r in data]
    assert len(ids) == len(set(ids)), f"{name} id 중복"


def test_default_dictionary_follows_schema():
    v = validator("dictionary.schema.json")
    dictionary = yaml.safe_load((ROOT / "dicts" / "default.yaml").read_text(encoding="utf-8"))
    assert list(v.iter_errors(dictionary)) == []


def test_human_evalset_covers_regression_ids():
    regression = {r["id"] for r in rows("testset.jsonl")}
    human = {r["id"] for r in rows("evalset_human.jsonl")}
    context_needed = {r["id"] for r in rows("context_needed.jsonl")}
    # 맥락 필요 바구니로 분리한 건만 평가셋 밖에 있다
    assert regression - context_needed <= human


def test_evalset_has_sublabels():
    data = rows("evalset_human.jsonl")
    assert all("sublabels" in r for r in data)
    dep_pos = sum(1 for r in data if r["sublabels"]["depression"])
    anx_pos = sum(1 for r in data if r["sublabels"]["anxiety"])
    assert dep_pos >= 30 and anx_pos >= 25  # 클래스별 지표가 의미를 갖는 최소 표본


def test_evalset_boundary_rules():
    """라벨 기준 문서의 경계 규칙이 평가셋 데이터에 반영됐는지 고정한다."""
    data = {r["id"]: r for r in rows("evalset_human.jsonl")}
    # 약 복용: 집에 있는 약 전부 복용은 emergency (상위 등급 원칙), 감기약 복용은 none
    assert data["s-146"]["label"] == "emergency"
    assert data["s-147"]["label"] == "none"
    # 의도+오늘 -> emergency
    assert data["s-046"]["label"] == data["s-047"]["label"] == data["s-072"]["label"] == "emergency"
    # 간접 질문은 none (대처법을 묻는 질문만으로 위험으로 두지 않는다)
    assert data["s-093"]["label"] == "none"
    assert data["s-091"]["label"] == "none"
    assert data["s-099"]["label"] == "none"
    # s-145는 맥락 필요 바구니로 분리
    assert "s-145" not in data
    ctx = {r["id"]: r for r in rows("context_needed.jsonl")}
    assert set(ctx) == {"s-145"}
    assert ctx["s-145"]["certainty"]["grade"] == "needs_context"
    # 피로·번아웃은 우울 false / 환청 진술(s-050)은 불안 null
    assert data["h-031"]["sublabels"]["depression"] is False
    assert data["h-038"]["sublabels"]["depression"] is False
    assert data["s-050"]["sublabels"]["anxiety"] is None
    # 강건성 태그와 소그룹 (과장·밈 5건, 간접 질문 3건)
    assert "robustness" in data["s-137"]["note"]
    assert sum(1 for r in data.values() if "hyperbole_meme" in (r.get("note") or "")) == 5
    assert sum(1 for r in data.values() if "indirect_question" in (r.get("note") or "")) == 3
    # certainty: 등급 ambiguous 10건에 사유가 있고, h-031은 우울 축만 ambiguous
    amb = {i for i, r in data.items() if (r.get("certainty") or {}).get("grade") == "ambiguous"}
    assert amb == {"s-002", "s-146", "s-147", "s-004", "s-005", "s-018",
                   "s-022", "h-056", "s-091", "s-093"}
    assert all(data[i]["certainty_reason"]["grade"] for i in amb)
    assert data["h-031"]["certainty"] == {"depression": "ambiguous"}
    assert "certainty" not in data["h-038"]
