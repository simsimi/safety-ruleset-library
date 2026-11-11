#!/usr/bin/env python3
"""기존 규칙 테스트 케이스를 riskcheck 테스트셋(data/testset.jsonl)으로 변환한다.

입력으로 받는 테스트 파일에서 위험 판정 함수 관련 파라미터라이즈 케이스만
AST로 뽑는다.

라벨 원칙: 라벨은 '사람 기준 진짜 위험 여부'가 아니라 초안 규칙의 기대값
(판정 함수가 내야 하는 값)이다. 즉 이 테스트셋은 사전 탐지기의 규칙 동작
재현(회귀) 검증용이다. 규칙이 잡지만 실제로는 위험이 아닌 케이스(부정문, 인용,
남의 이야기 등)도 규칙 기대값대로 danger로 들어 있으며, 사람 기준 라벨은
평가셋(data/evalset_human.jsonl)이 따로 맡는다.

사용법: python3 tools/convert_rule_tests.py <규칙 테스트 파일 경로>
"""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 함수명 -> (라벨, 비고). test_risk_words만 (text, expected) 튜플이다.
SOURCES = {
    "test_risk_words": None,  # 튜플에서 expected를 읽는다
    "test_words_that_mean_danger": ("danger", "규칙 테스트: 위험으로 잡는 말"),
    "test_words_about_harming_others_sexual_violence_and_death_are_not_suicide_signals":
        ("none", "규칙 테스트: 타해·성폭력·죽음 낱말은 자살 신호가 아님"),
    "test_words_that_mean_emergency": ("emergency", "규칙 테스트: 비상으로 잡는 말"),
    "test_words_that_only_look_like_danger": ("none", "규칙 테스트: 위험처럼 보이지만 아님"),
}


def strings_of(node) -> list[str]:
    return [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    tree = ast.parse(Path(sys.argv[1]).read_text(encoding="utf-8"))

    rows: list[dict] = []
    seen: dict[str, str] = {}
    conflicts: list[tuple[str, str, str]] = []

    def add(text: str, label: str, note: str):
        if text in seen:
            if seen[text] != label:
                conflicts.append((text, seen[text], label))
            return
        seen[text] = label
        rows.append({
            "id": f"s-{len(rows) + 1:03d}", "text": text, "label": label,
            "source": "rule-test", "note": note,
        })

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in SOURCES:
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            list_arg = next((a for a in dec.args if isinstance(a, ast.List)), None)
            if list_arg is None:
                continue
            if node.name == "test_risk_words":
                for item in list_arg.elts:
                    if isinstance(item, ast.Tuple) and len(item.elts) == 2:
                        text = item.elts[0].value
                        label = item.elts[1].value or "none"
                        add(text, label, "규칙 테스트: test_risk_words")
            else:
                label, note = SOURCES[node.name]
                for text in strings_of(list_arg):
                    add(text, label, note)

    out = ROOT / "data" / "testset.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    from collections import Counter
    print(f"{out}: {len(rows)}건 {dict(Counter(r['label'] for r in rows))}")
    for text, kept, dropped in conflicts:
        print(f"라벨 충돌(먼저 것 유지): {text!r} {kept} vs {dropped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
