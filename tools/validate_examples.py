#!/usr/bin/env python3
"""riskcheck 스키마 예시 검증 + 리포트 예시 생성.

- 스키마 4종 자체의 문법(JSON Schema) 검증
- 예시 파일 3종이 각 스키마를 따르는지 검증
- 스키마로 표현 못 하는 규칙 추가 검증: id 유일성, predictions↔테스트셋 id 일치,
  matches.pattern_id 가 사전에 존재하는지
- 테스트셋+predictions 예시로 지표를 계산해 report.example.json 생성 후 스키마 검증

사용법: python3 tools/validate_examples.py
필요 패키지: jsonschema, pyyaml
"""
import json
from collections import Counter
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
LABELS = ["none", "risk"]


def load_schema(name):
    schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def load_jsonl(name):
    rows = []
    for line in (ROOT / "examples" / name).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def check(validator, obj, where):
    errors = sorted(validator.iter_errors(obj), key=lambda e: e.path)
    if errors:
        for e in errors:
            print(f"FAIL {where}: {list(e.path)} {e.message}")
        raise SystemExit(1)


def per_label(gold, pred, label):
    tp = sum(1 for g, p in zip(gold, pred) if g == label and p == label)
    fp = sum(1 for g, p in zip(gold, pred) if g != label and p == label)
    fn = sum(1 for g, p in zip(gold, pred) if g == label and p != label)
    support = sum(1 for g in gold if g == label)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall else (0.0 if precision == 0.0 or recall == 0.0 else None))
    return {"precision": rnd(precision), "recall": rnd(recall), "f1": rnd(f1), "support": support}


def rnd(x):
    return None if x is None else round(x, 4)


def main():
    testset_v = load_schema("testset.schema.json")
    dict_v = load_schema("dictionary.schema.json")
    pred_v = load_schema("predictions.schema.json")
    report_v = load_schema("report.schema.json")
    print("schemas: 4종 모두 JSON Schema 문법 정상")

    testset = load_jsonl("testset.example.jsonl")
    preds = load_jsonl("predictions.example.jsonl")
    dictionary = yaml.safe_load((ROOT / "examples" / "dictionary.example.yaml").read_text(encoding="utf-8"))

    for row in testset:
        check(testset_v, row, f"testset:{row.get('id')}")
    for row in preds:
        check(pred_v, row, f"predictions:{row.get('id')}")
    check(dict_v, dictionary, "dictionary")
    print(f"examples: testset {len(testset)}건, predictions {len(preds)}건, 사전 패턴 {len(dictionary['patterns'])}개 스키마 통과")

    ids = [r["id"] for r in testset]
    assert len(ids) == len(set(ids)), "테스트셋 id 중복"
    pattern_ids = [p["id"] for p in dictionary["patterns"]] + [e["id"] for e in dictionary.get("excludes", [])]
    assert len(pattern_ids) == len(set(pattern_ids)), "사전 id 중복"
    assert {p["id"] for p in preds} == set(ids), "predictions와 테스트셋 id 불일치"
    known = {p["id"] for p in dictionary["patterns"]}
    for p in preds:
        for m in p["matches"]:
            assert m["pattern_id"] in known, f"없는 패턴 참조: {m['pattern_id']}"
    print("cross-check: id 유일성, id 연결, 패턴 참조 전부 일치")

    # 채점은 이진: 등급(danger/emergency) 정답은 risk로 접는다.
    gold_by_id = {r["id"]: ("none" if r["label"] == "none" else "risk") for r in testset}
    evaluated = [p for p in preds if p["predicted"] is not None]
    error_cases = [{"id": p["id"], "error": p["error"]} for p in preds if p["predicted"] is None]
    gold = [gold_by_id[p["id"]] for p in evaluated]
    pred = [p["predicted"] for p in evaluated]

    confusion = [[sum(1 for g, q in zip(gold, pred) if g == gl and q == pl) for pl in LABELS] for gl in LABELS]
    per = {label: per_label(gold, pred, label) for label in LABELS}
    accuracy = sum(1 for g, q in zip(gold, pred) if g == q) / len(gold) if gold else None
    f1s = [per[l]["f1"] for l in LABELS if per[l]["f1"] is not None]
    macro_f1 = sum(f1s) / len(f1s) if f1s else None

    gold_bin = ["risk" if g != "none" else "none" for g in gold]
    pred_bin = ["risk" if q != "none" else "none" for q in pred]
    binary = per_label(gold_bin, pred_bin, "risk")

    report = {
        "schema_version": "0.1",
        "stage": "dict",
        "dataset": {"name": "testset.example.jsonl", "count": len(testset)},
        "dictionary": {"name": dictionary["name"], "version": dictionary["version"]},
        "counts": {"total": len(preds), "evaluated": len(evaluated), "errors": len(error_cases)},
        "overall": {"accuracy": rnd(accuracy), "macro_f1": rnd(macro_f1)},
        "per_label": per,
        "binary_risk": binary,
        "confusion": {"labels": LABELS, "matrix": confusion},
        "false_positives": [{"id": p["id"], "gold": gold_by_id[p["id"]], "predicted": p["predicted"]}
                            for p in evaluated if p["predicted"] != "none" and gold_by_id[p["id"]] == "none"],
        "false_negatives": [{"id": p["id"], "gold": gold_by_id[p["id"]], "predicted": p["predicted"]}
                            for p in evaluated if gold_by_id[p["id"]] != "none" and p["predicted"] == "none"],
        "error_cases": error_cases,
    }
    out = ROOT / "examples" / "report.example.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    check(report_v, report, "report.example.json")
    print(f"report: {out.relative_to(ROOT)} 생성·스키마 통과 "
          f"(accuracy={report['overall']['accuracy']}, macro_f1={report['overall']['macro_f1']}, "
          f"binary recall={binary['recall']})")
    print("label counts:", dict(Counter(gold_by_id.values())))


if __name__ == "__main__":
    main()
