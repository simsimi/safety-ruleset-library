#!/usr/bin/env python3
"""기본 사전(dicts/default.yaml)을 기본 규칙 파일에서 생성한다.

입력으로 받는 파이썬 규칙 파일의 RISK_* 상수에서 패턴을 뽑는다.
- RISK_EMERGENCY / RISK_DANGER 구 목록 -> phrase 패턴 (항목별 id 부여)
- RISK_WORD / RISK_WILL / RISK_JUMP -> regex 패턴 (컴파일된 패턴 문자열 그대로)
- 제외 로직(듣는 상대에게 하는 말을 거르는 판정 등)은 정규식으로 옮길 수 없어
  탐지기 내장 규칙이라 사전 excludes는 비워 둔다.

사용법: python3 tools/build_default_dict.py <규칙 파일 경로>
"""
import importlib.util
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_rules_module(path: str):
    spec = importlib.util.spec_from_file_location("rules_src", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    sr = load_rules_module(sys.argv[1])

    patterns = []
    for i, phrase in enumerate(sr.RISK_EMERGENCY, 1):
        patterns.append({
            "id": f"em-phrase-{i:02d}", "type": "phrase",
            "pattern": phrase, "category": "suicide_self_harm",
            "note": "기본 규칙 — 행위 완료·진행 형태",
        })
    patterns.append({
        "id": "em-will", "type": "regex",
        "pattern": sr.RISK_WILL.pattern, "category": "suicide_self_harm",
        "note": "기본 규칙 — 유서를 썼다는 말",
    })
    patterns.append({
        "id": "em-jump", "type": "regex",
        "pattern": sr.RISK_JUMP.pattern, "category": "suicide_self_harm",
        "note": "기본 규칙 — 뛰어내림. 놀이·운동 맥락 제외는 탐지기 내장 규칙",
    })
    for i, phrase in enumerate(sr.RISK_DANGER, 1):
        patterns.append({
            "id": f"dg-phrase-{i:02d}", "type": "phrase",
            "pattern": phrase, "category": "suicide_self_harm",
            "note": "기본 규칙 — 사고·소망 형태",
        })
    patterns.append({
        "id": "dg-risk-word", "type": "regex",
        "pattern": sr.RISK_WORD.pattern, "category": "suicide_self_harm",
        "note": "기본 규칙 — 자살·자해·투신 단일어 (오탐 방지 경계 조건 포함)",
    })

    extras_path = ROOT / "dicts" / "default_extras.yaml"
    n_extras = 0
    if extras_path.exists():
        extras = yaml.safe_load(extras_path.read_text(encoding="utf-8"))["patterns"]
        ids = {p["id"] for p in patterns}
        for p in extras:
            if p["id"] in ids:
                raise ValueError(f"확장 패턴 id 중복: {p['id']}")
            patterns.append(p)
        n_extras = len(extras)

    dictionary = {
        "name": "default",
        "version": "0.5.0",
        "description": "위험 표현 기본 규칙과 추가 패턴(dicts/default_extras.yaml)을 "
                       "병합한 기본 사전이다. 패턴에 등급은 없으며 판정은 위험/비위험 이진이다. "
                       "성능 측정의 출발점으로 제공되며, 실서비스의 안전 판정에 그대로 쓰지 않는다.",
        "patterns": patterns,
        "excludes": [],
    }
    out = ROOT / "dicts" / "default.yaml"
    header = ("# riskcheck 기본 사전 — tools/build_default_dict.py로 생성한다.\n"
              "# 직접 고치지 말고, 기본 규칙은 원본 규칙 파일을, 확장 패턴은 dicts/default_extras.yaml을 고친 뒤 재생성할 것.\n"
              "# 제외(듣는 상대에게 하는 말) 로직은 탐지기 내장 규칙이라 excludes는 비어 있다.\n")
    out.write_text(header + yaml.safe_dump(dictionary, allow_unicode=True, sort_keys=False),
                   encoding="utf-8")
    print(f"{out}: 패턴 {len(patterns)}개 "
          f"(emergency 구 {len(sr.RISK_EMERGENCY)}, danger 구 {len(sr.RISK_DANGER)}, regex 3, 확장 {n_extras})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
