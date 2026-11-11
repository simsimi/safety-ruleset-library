"""단어 사전 단계 탐지기.

판정 순서는 아래와 같다.

1. 공백 정규화: 줄바꿈·연속 공백은 한 칸으로.
2. 듣는 상대에게 하는 말 제거(내장 규칙, 아래): "죽고 싶냐"·"자살해라"처럼 틀림없이
   상대에게 하는 꼴만 먼저 뺀다. 애매하면 빼지 않는다(놓치는 쪽보다 확인이 낫다).
3. 사전 excludes(정규식) 구간 제거.
4. phrase 패턴은 공백을 지운 텍스트에서, regex 패턴은 공백을 줄인 원문에서 찾는다.
5. 패턴이 하나라도 걸리면 risk, 아니면 none이며, 걸린 패턴 전부를 matches에 남긴다.

내장 제외 규칙은 사전 파일로 다 옮길 수 없는 절(clause) 단위 로직이라 코드에 둔다.
"""
import re

from .dictionary import Dictionary

# ── 내장 제외: 듣는 상대에게 하는 말 ─────────────────────
_WISH = r"(?:죽어 ?버리고 ?싶|죽고 ?싶|사망하고 ?싶|살해 ?당하고 ?싶|살기 ?싫)"
_THREAT = re.compile(
    rf"{_WISH}(?:냐(?!면|고)|니(?![가-힣]))"
    rf"|{_WISH}어서? ?(?:환장|안달|난리) ?(?:했|났|이)?(?:냐(?!면|고)|니(?![가-힣])|어 ?\?)"
    rf"|(?<![가-힣])(?:너|넌|니가|네가) (?:(?:진짜|정말|지금) )?{_WISH}(?:어 ?\?|구나)"
)
_AT_YOU = r"(?:야|너|넌|너나|니가|네가|가서|나가|나가서|꺼져|닥쳐|닥치고|씨발|시발|ㅅㅂ|그냥|좀|제발|빨리|얼른)"
_NAMES = r"(?:좀|제발|그냥|임마|새끼야?|이 ?새끼야?|병신아?|미친놈아?|미친년아?|개새끼야?)"
_ORDER = re.compile(
    rf"(?:{_AT_YOU} )*(?:자살|자해)(?:이나|나)? ?(?:해라|하라|하렴|하세요|하쇼|하셈|해 ?버려라?)(?: {_NAMES})*[ㅋㅎ~, ]*"
    rf"|(?:{_AT_YOU} )*(?:자살이나|자해나) ?해(?: {_NAMES})*[ㅋㅎ~, ]*"
)
_ORDER_ALONE = re.compile(
    rf"(?:(?:야|너|넌|너나|니가|네가|가서|나가|나가서|꺼져|닥쳐|닥치고|씨발|시발|ㅅㅂ) )*자살해"
    rf"(?: (?:임마|새끼야?|이 ?새끼야?|병신아?|미친놈아?|미친년아?|개새끼야?))*[ㅋㅎ~, ]*"
)
_SENTENCE_END = re.compile(r"[.!?…]+")

# 뛰어내린다는 말이 놀이·운동 맥락이면 위험이 아니다
_JUMP_FOR_FUN = re.compile(r"다이빙|수영장|번지|점프대|트램펄린|트램폴린|낙하산|패러글라이딩|놀이기구")


def _not_to_the_listener(spaced: str) -> str:
    """듣는 상대에게 하는 말을 뺀 글. 뺀 자리는 '/'로 갈라 앞뒤 글자가 붙지 않게 한다."""
    clauses = [c.strip() for c in _SENTENCE_END.split(_THREAT.sub(" / ", spaced))]
    clauses = [c for c in clauses if c]
    alone = len(clauses) == 1
    return " / ".join(
        c for c in clauses
        if not (_ORDER.fullmatch(c) or (alone and _ORDER_ALONE.fullmatch(c)))
    )


class DictDetector:
    """사전 기반 탐지기. detect(text) -> {"predicted": "risk"|"none", "matches": [...]}.

    판정은 이진이다 — 패턴이 하나라도 걸리면 risk, 아니면 none.
    """

    def __init__(self, dictionary: Dictionary):
        self.dictionary = dictionary

    def detect(self, text: str) -> dict:
        spaced = re.sub(r"\s+", " ", text).strip()
        spaced = _not_to_the_listener(spaced)
        for ex in self.dictionary.excludes:
            if ex.enabled and ex.compiled is not None:
                spaced = ex.compiled.sub(" ", spaced)
        compact = re.sub(r"\s+", "", spaced)
        fun_context = bool(_JUMP_FOR_FUN.search(compact))

        matches: list[dict] = []
        for p in self.dictionary.patterns:
            if not p.enabled:
                continue
            if p.type == "phrase":
                if p.pattern in compact:
                    matches.append({"pattern_id": p.id, "matched": p.pattern})
            else:
                m = p.compiled.search(spaced) if p.compiled is not None else None
                if m is not None:
                    if fun_context and "뛰어내" in m.group(0):
                        continue  # 놀이·운동으로 뛰어내린다는 말은 위험이 아니다
                    matches.append({
                        "pattern_id": p.id, "matched": m.group(0),
                        "span": [m.start(), m.end()],
                    })

        return {"predicted": "risk" if matches else "none", "matches": matches}
