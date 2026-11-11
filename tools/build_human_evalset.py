#!/usr/bin/env python3
"""사람 기준 평가셋의 등급 파트(data/evalset_human.jsonl)를 만든다.

- 회귀 테스트셋 271건을 docs/라벨_기준_사람기준.md 기준으로 재라벨한다.
  기본값은 규칙 라벨을 따르고, 기준에서 갈리는 항목만 OVERRIDES로 바꾼다.
- 일상·기타 부정감정·관용표현 음성 케이스와 완곡한 진성 케이스를 ADDS로 보강한다.
- 단일 발화로 못 가르는 항목은 data/context_needed.jsonl로 분리한다.
- 하위 라벨은 tools/build_sublabels.py가 이어서 붙인다 (같은 파일).

사용법: python3 tools/build_human_evalset.py && python3 tools/build_sublabels.py
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# id -> (사람 기준 라벨, 범주, borderline 여부). 없으면 규칙 라벨을 그대로 쓴다.
# 간접 질문(s-093 등)은 none이다 — 실제 서비스에서 단어 기반 판정은 검토자 개입이
# 붙는 위기 판정에 대응해, 대처법을 묻는 질문만으로 위험으로 두는 과탐 비용이 크다.
# 확실성은 라벨과 별도 축(certainty)으로 GRADE_CERTAINTY에 기록한다.
OVERRIDES = {
    "s-002": ("emergency", "ambiguous_act", False),   # 약을 다 먹었어 — 확정
    "s-004": ("danger", "fragment", False),           # 자살 (한 단어) — 확정
    "s-005": ("danger", "fragment", False),           # 자해 (한 단어) — 확정
    "s-018": ("danger", "fragment", False),           # 투신 (한 단어) — 확정, FP 측정 대상
    "s-022": ("danger", "genuine_thought", False),    # ㅋㅋ자살각 — 확정, 과장·밈 소그룹
    "s-043": ("none", "reported", False),
    "s-044": ("none", "reported", False),
    "s-045": ("none", "reported", False),
    "s-046": ("emergency", "genuine_intent", False),  # 나 오늘 자살해 — 의도+오늘=emergency (A2)
    "s-047": ("emergency", "genuine_intent", False),
    "s-050": ("danger", "genuine_experience", False),  # 자해하라는 목소리가 들려
    "s-051": ("none", "reported", False),
    "s-052": ("none", "reported", False),
    "s-053": ("none", "reported", False),
    "s-054": ("none", "reported", False),
    "s-055": ("none", "reported", False),
    "s-056": ("none", "reported", False),
    "s-057": ("none", "reported", False),
    "s-058": ("none", "reported", False),
    "s-059": ("danger", "genuine_intent", False),     # 자살하라면 할게 — 확정
    "s-069": ("emergency", "genuine_plan", False),    # 오늘 밤 한강 — 시점+장소
    "s-072": ("emergency", "genuine_intent", False),  # 오늘은 진짜 자살해 (A2)
    "s-085": ("danger", "genuine_thought", False),    # 어제 죽고 싶어서 — 확정
    "s-091": ("none", "question_to_listener", False),
    "s-092": ("none", "question_to_listener", False),
    "s-093": ("none", "indirect_question", False),  # 간접 질문 — D1 최종 확정 none (검토2안)
    "s-096": ("none", "third_party", False),
    "s-097": ("none", "third_party", False),
    "s-098": ("none", "third_party", False),
    "s-099": ("none", "third_party", False),          # 확정 ('언니' 호칭 용례는 별도 확인 사항)
    "s-100": ("none", "third_party", False),
    "s-101": ("none", "discussion", False),
    "s-102": ("none", "negation", False),
    "s-110": ("none", "victim", False),
    "s-121": ("none", "discussion", False),
    "s-122": ("none", "victim", False),
    "s-128": ("none", "death_other", False),
    "s-129": ("none", "discussion", False),
    "s-130": ("none", "discussion", False),
    "s-143": ("danger", "genuine_intent", False),     # 뛰어내릴 거야 — 현장 아님
    "s-146": ("emergency", "ambiguous_act", False),   # 집에 있는 약 다 먹었어 — 상위 등급 원칙 (A1)
    "s-147": ("none", "ordinary", True),              # 감기약 다 먹었어 — none 확정, 저신뢰 표시 유지
    "s-148": ("emergency", "farewell", False),        # 마지막 인사 — 확정
    "s-176": ("none", "other_negative", False),
    "s-177": ("none", "other_negative", False),
    "s-233": ("none", "other_harm", False),
}

# 단일 발화로 해소 불가 — 채점에서 빼고 맥락 필요 바구니로 분리한다
EXCLUDE_CONTEXT = {
    "s-145": "버스에서 뛰어내릴 뻔했어 — '급히 내렸다'와 '충동' 둘 다 가능해 맥락이 필요하다",
}

# note에 덧붙일 태그. robustness = 같은 현상의 표기 변형(강건성 확인용, 지표 가중 분리용)
POST_TAGS = {
    "s-133": "robustness", "s-134": "robustness", "s-136": "robustness",
    "s-137": "robustness", "s-138": "robustness",
    "s-020": "robustness", "s-021": "robustness", "s-024": "robustness",
    "s-025": "robustness", "s-026": "robustness", "s-029": "robustness",
    "s-132": "robustness",
    "s-022": "subgroup:hyperbole_meme",
    "s-091": "subgroup:indirect_question",
    "s-093": "subgroup:indirect_question",
    "s-099": "subgroup:indirect_question",
}

# 등급 축 certainty가 ambiguous인 항목과 사유. 부여 기준: 발화만으로 두 가지 이상
# 해석이 성립하고 그 이유를 한 줄로 적을 수 있을 때만 부여한다.
GRADE_CERTAINTY = {
    "s-002": "단순 복용 완료와 과량 복용을 구별할 정보가 없다",
    "s-146": "집에 있는 약 전부를 먹었다는 표현은 고위험 해석을 배제할 수 없다",
    "s-147": "복용 과정의 완료인지 한꺼번에 복용인지 불명",
    "s-004": "단어만으로 본인 의도·시점을 확인할 수 없다",
    "s-005": "단어만으로 본인 의도·시점을 확인할 수 없다",
    "s-018": "단어만으로 본인 의도·시점을 확인할 수 없다",
    "s-022": "과장·밈 어법과 실제 의도를 구별할 수 없다",
    "h-056": "약을 모으는 목적(보관·수집인지 준비인지)이 확인되지 않는다",
    "s-091": "'너도'의 전제로 화자 본인의 경험이 함축되나 직접 표현은 없다",
    "s-093": "간접 자기 개방으로도, 타인의 경험을 묻는 질문으로도 성립한다",
}

# (텍스트, 라벨, 범주, borderline)
ADDS = [
    # 일상 발화 (none/ordinary)
    ("오늘 점심 뭐 먹을까", "none", "ordinary", False),
    ("주말에 영화 보러 갈래?", "none", "ordinary", False),
    ("버스 놓쳐서 지각할 뻔했어", "none", "ordinary", False),
    ("운동하고 나니까 개운하다", "none", "ordinary", False),
    ("내일 비 온대 우산 챙겨", "none", "ordinary", False),
    ("과제 드디어 다 끝냈다", "none", "ordinary", False),
    ("새로 산 신발이 너무 편해", "none", "ordinary", False),
    ("엄마한테 전화 왔었어", "none", "ordinary", False),
    ("카페에서 공부하고 왔어", "none", "ordinary", False),
    ("요즘 읽는 책이 재밌어", "none", "ordinary", False),
    ("친구 생일 선물 뭐가 좋을까", "none", "ordinary", False),
    ("머리 자르고 싶다", "none", "ordinary", False),
    ("배고프니까 밥부터 먹자", "none", "ordinary", False),
    ("휴가 때 제주도 가기로 했어", "none", "ordinary", False),
    ("시험 끝나면 푹 잘 거야", "none", "ordinary", False),
    ("오늘 회의 길었어", "none", "ordinary", False),
    ("강아지가 너무 귀여워", "none", "ordinary", False),
    ("새 노래 나왔는데 들어봤어?", "none", "ordinary", False),
    ("감기 기운이 있어서 일찍 잤어", "none", "ordinary", False),
    ("약국에서 약 사 왔어, 하루 세 번 먹으래", "none", "ordinary", False),
    ("처방받은 약 다 먹어서 다시 병원 가야 해", "none", "ordinary", False),
    ("옥상에서 빨래 널었어", "none", "ordinary", False),
    ("한강 공원에서 자전거 탔어", "none", "ordinary", False),
    ("다리 건너는데 바람이 세게 불었어", "none", "ordinary", False),
    ("계단에서 넘어질 뻔했어", "none", "ordinary", False),
    ("손목이 시큰해서 파스 붙였어", "none", "ordinary", False),
    ("칼로 양파 썰다가 눈물 났어", "none", "ordinary", False),
    ("밤에 잠이 잘 안 와", "none", "ordinary", False),
    ("요즘 살이 좀 빠졌어", "none", "ordinary", False),
    ("이사 준비로 정신이 없어", "none", "ordinary", False),
    # 자해 없는 부정 감정 (none/other_negative)
    ("요즘 너무 지치고 힘들어", "none", "other_negative", False),
    ("시험 때문에 스트레스 받아", "none", "other_negative", False),
    ("우울해서 아무것도 하기 싫어", "none", "other_negative", False),
    ("불안해서 잠이 안 와", "none", "other_negative", False),
    ("혼자 있으니까 외롭다", "none", "other_negative", False),
    ("화가 나서 하루 종일 짜증 났어", "none", "other_negative", False),
    ("슬퍼서 울었어", "none", "other_negative", False),
    ("번아웃 온 것 같아", "none", "other_negative", False),
    ("자존감이 많이 떨어졌어", "none", "other_negative", False),
    ("미래가 막막하게 느껴져", "none", "other_negative", False),
    ("포기하고 싶어, 이 과제", "none", "other_negative", False),
    ("다 그만두고 싶어, 회사", "none", "other_negative", False),
    # 관용 표현 (none/idiom)
    ("웃겨 죽겠어 진짜", "none", "idiom", False),
    ("피곤해 죽겠어", "none", "idiom", False),
    ("죽기 살기로 공부했어", "none", "idiom", False),
    ("죽은 듯이 잤어", "none", "idiom", False),
    ("배불러 죽겠어", "none", "idiom", False),
    ("심심해 죽겠어", "none", "idiom", False),
    # 완곡한 진성 표현 (danger) — 사전이 놓치기 쉬운 꼴
    ("사라지는 게 낫겠어", "danger", "genuine_thought", False),
    ("영원히 잠들고 싶어", "danger", "genuine_thought", False),
    ("내가 없어지는 게 모두에게 좋아", "danger", "genuine_thought", False),
    ("손목을 긋고 싶어", "danger", "genuine_thought", False),
    ("뛰어내리고 싶어", "danger", "genuine_thought", False),
    ("죽는 게 답인 것 같아", "danger", "genuine_thought", False),
    ("내 목숨을 버리고 싶어", "danger", "genuine_thought", False),
    ("약을 모으고 있어", "danger", "genuine_prep_progress", False),
    # 진성 비상 (emergency) — 사전이 놓치기 쉬운 꼴
    ("수면제를 한 통 다 털어 넣었어", "emergency", "genuine_act", False),
    ("지금 약 먹으려고, 한꺼번에 다", "emergency", "genuine_imminent", False),
    # 과장·밈 소그룹 (danger로 두되 FP율을 따로 본다) — 5번째 원소는 태그
    ("월요일이라 자살각ㅋㅋ", "danger", "genuine_thought", False, "subgroup:hyperbole_meme"),
    ("시험 망하면 자살각ㅋㅋ", "danger", "genuine_thought", False, "subgroup:hyperbole_meme"),
    ("다이어트 실패해서 자살각", "danger", "genuine_thought", False, "subgroup:hyperbole_meme"),
    ("게임 져서 자살각ㅋㅋ", "danger", "genuine_thought", False, "subgroup:hyperbole_meme"),
]


def none_category(row_id: str) -> str:
    n = int(row_id.split("-")[1])
    if 108 <= n <= 130:
        return "other_context"
    if 225 <= n <= 264:
        return "listener_directed"
    if 265 <= n <= 267:
        return "fun_context"
    if 268 <= n <= 271:
        return "document"
    return "lookalike"


def main() -> int:
    src = [json.loads(l) for l in (ROOT / "data" / "testset.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    out_rows = []
    borderline = []
    context_rows = []
    for row in src:
        if row["id"] in EXCLUDE_CONTEXT:
            context_rows.append({"id": row["id"], "text": row["text"], "label": row["label"],
                                 "source": "human",
                                 "certainty": {"grade": "needs_context"},
                                 "certainty_reason": {"grade": EXCLUDE_CONTEXT[row["id"]]},
                                 "note": f"context_needed: {EXCLUDE_CONTEXT[row['id']]}"})
            continue
        rule_label = row["label"]
        if row["id"] in OVERRIDES:
            label, cat, bl = OVERRIDES[row["id"]]
        else:
            label = rule_label
            cat = {"danger": "genuine_thought", "emergency": "genuine_act"}.get(label) or none_category(row["id"])
            bl = False
        note = f"cat:{cat}; rule:{rule_label}" + ("; borderline" if bl else "")
        if row["id"] in POST_TAGS:
            note += f"; {POST_TAGS[row['id']]}"
        new_row = {"id": row["id"], "text": row["text"], "label": label,
                   "source": "human", "note": note}
        if row["id"] in GRADE_CERTAINTY:
            new_row["certainty"] = {"grade": "ambiguous"}
            new_row["certainty_reason"] = {"grade": GRADE_CERTAINTY[row["id"]]}
        out_rows.append(new_row)
        if bl:
            borderline.append((row["id"], row["text"], rule_label, label, cat))

    for i, entry in enumerate(ADDS, 1):
        text, label, cat, bl = entry[:4]
        tag = entry[4] if len(entry) > 4 else None
        note = f"cat:{cat}" + ("; borderline" if bl else "") + (f"; {tag}" if tag else "")
        new_row = {"id": f"h-{i:03d}", "text": text, "label": label,
                   "source": "human", "note": note}
        if new_row["id"] in GRADE_CERTAINTY:
            new_row["certainty"] = {"grade": "ambiguous"}
            new_row["certainty_reason"] = {"grade": GRADE_CERTAINTY[new_row["id"]]}
        out_rows.append(new_row)
        if bl:
            borderline.append((f"h-{i:03d}", text, "-", label, cat))

    out = ROOT / "data" / "evalset_human.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out_rows), encoding="utf-8")
    print(f"{out.name}: {len(out_rows)}건 {dict(Counter(r['label'] for r in out_rows))}, borderline {len(borderline)}건")

    ctx = ROOT / "data" / "context_needed.jsonl"
    ctx.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in context_rows), encoding="utf-8")
    print(f"{ctx.name}: {len(context_rows)}건 (맥락 필요, 채점 제외)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
