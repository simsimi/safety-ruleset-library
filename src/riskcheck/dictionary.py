"""단어 사전 로딩과 검증.

사전 파일(YAML)의 형식은 schemas/dictionary.schema.json 을 따른다.
여기서는 실행에 필요한 최소 검증(필수 필드, id 중복, 정규식 컴파일)만 직접 한다 —
JSON Schema 전체 검증은 도구가 아니라 스키마 파일과 예시 검증 스크립트의 몫이다.
"""
from dataclasses import dataclass, field
from pathlib import Path
import re

import yaml


@dataclass
class Pattern:
    id: str
    type: str  # phrase | regex
    pattern: str
    category: str | None = None
    enabled: bool = True
    note: str | None = None
    compiled: re.Pattern | None = field(default=None, repr=False)


@dataclass
class Exclude:
    id: str
    pattern: str
    enabled: bool = True
    note: str | None = None
    compiled: re.Pattern | None = field(default=None, repr=False)


@dataclass
class Dictionary:
    name: str
    version: str
    patterns: list[Pattern]
    excludes: list[Exclude] = field(default_factory=list)
    description: str | None = None


def load_dictionary(path: str | Path) -> Dictionary:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"사전 파일이 매핑이 아닙니다: {path}")
    for key in ("name", "version", "patterns"):
        if key not in raw:
            raise ValueError(f"사전 필수 필드 누락: {key}")

    patterns: list[Pattern] = []
    seen: set[str] = set()
    for item in raw["patterns"]:
        for key in ("id", "type", "pattern"):
            if key not in item:
                raise ValueError(f"패턴 필수 필드 누락: {key} (id={item.get('id')})")
        if item["id"] in seen:
            raise ValueError(f"패턴 id 중복: {item['id']}")
        seen.add(item["id"])
        # 구 형식의 level 필드가 있어도 무시한다 (판정은 위험/비위험 이진).
        if item["type"] not in ("phrase", "regex"):
            raise ValueError(f"패턴 type 오류: {item['id']} -> {item['type']}")
        compiled = None
        if item["type"] == "regex":
            try:
                compiled = re.compile(item["pattern"])
            except re.error as e:
                raise ValueError(f"정규식 컴파일 실패: {item['id']}: {e}") from e
        patterns.append(Pattern(
            id=item["id"], type=item["type"], pattern=item["pattern"],
            category=item.get("category"), enabled=item.get("enabled", True),
            note=item.get("note"), compiled=compiled,
        ))

    excludes: list[Exclude] = []
    for item in raw.get("excludes") or []:
        if item["id"] in seen:
            raise ValueError(f"제외 패턴 id 중복/충돌: {item['id']}")
        seen.add(item["id"])
        try:
            compiled = re.compile(item["pattern"])
        except re.error as e:
            raise ValueError(f"제외 정규식 컴파일 실패: {item['id']}: {e}") from e
        excludes.append(Exclude(
            id=item["id"], pattern=item["pattern"], enabled=item.get("enabled", True),
            note=item.get("note"), compiled=compiled,
        ))

    return Dictionary(
        name=raw["name"], version=str(raw["version"]), patterns=patterns,
        excludes=excludes, description=raw.get("description"),
    )
