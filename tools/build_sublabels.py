#!/usr/bin/env python3
"""사람 기준 평가셋에 하위 라벨을 붙여 완성한다.

tools/build_human_evalset.py가 만든 등급 파트(data/evalset_human.jsonl)에
docs/하위라벨_기준.md 기준으로 sublabels(우울/불안)를 전건 부여하고,
우울/불안 양성 발화와 경계 음성 발화를 보강해 같은 파일에 쓴다.
하위 라벨의 판정 경계(피로·번아웃은 false 등)는 docs/하위라벨_기준.md를 따른다.
null(판정 보류) 항목은 docs/하위라벨_경계목록.md로 뽑는다.

사용법: python3 tools/build_human_evalset.py && python3 tools/build_sublabels.py
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 우울 true: 감정 상태 서술이 있는 발화만 (하위 라벨 기준). 자살·자해 생각/욕구/의도
# 진술은 위해 신호라 등급의 영역이며, 그 자체로는 우울 양성이 아니다 —
# 진술만 있는 발화는 아래 집합에 없어 기본값 false가 된다.
# s-081은 "밥도 안 넘어가"(식욕 상실 — 우울 증상 서술)가 동반돼 true로 둔다.
DEP_TRUE = {
    "s-081", "s-177",
    "h-033", "h-039", "h-040",
}
# 우울 null: 행위/준비/현장 진술, 조각 단어, 농담조 (피로·소진은 false — 기준 문서 참고)
DEP_NULL = {
    "s-002", "s-004", "s-005", "s-007", "s-018", "s-020", "s-021", "s-022", "s-024",
    "s-025", "s-026", "s-029", "s-050",
    "s-131", "s-132", "s-133", "s-134", "s-135", "s-136", "s-137", "s-138", "s-139",
    "s-140", "s-141", "s-142", "s-144", "s-148",
    "h-056", "h-057", "h-058",
    "h-059", "h-060", "h-061", "h-062",  # 과장·밈 소그룹 — s-022와 같은 취급
}
ANX_TRUE = {"h-034"}
ANX_NULL = {"s-050"}  # 환청 진술 — 불안·당황 신호가 섞여 false로 단정하지 않는다

# (텍스트, 우울, 불안) — 등급은 전부 none (자살·자해 위험 없음)
ADDS = [
    # 우울 양성
    ("뭘 해도 재미가 없어", True, False), ("아침에 눈 뜨기가 싫어", True, False),
    ("의욕이 하나도 안 생겨", True, False), ("내가 쓸모없는 사람 같아", True, False),
    ("자꾸 눈물만 나", True, False), ("밥맛이 없어", True, False),
    ("사람 만나기가 귀찮고 피하게 돼", True, False), ("하루 종일 누워만 있고 싶어", True, False),
    ("기분이 계속 가라앉아 있어", True, False), ("희망이 안 보여", True, False),
    ("다 내 탓인 것 같아", True, False), ("집중이 안 되고 멍해", True, False),
    ("좋아하던 음악도 시들해", True, False), ("몸이 천근만근 무거워", True, False),
    ("웃는 게 힘들어", True, False), ("미래가 캄캄해", True, False),
    ("모든 게 의미 없게 느껴져", True, False), ("기운이 쭉 빠져서 아무것도 못 하겠어", True, False),
    ("혼자 있고만 싶어", True, False), ("계속 잠만 자고 싶어", True, False),
    ("마음이 텅 빈 것 같아", True, False), ("사는 게 재미없어", True, False),
    ("사소한 일에도 눈물이 나", True, False), ("내가 사라져도 아무도 모를 것 같아", True, False),
    # 불안 양성
    ("발표 생각하면 가슴이 두근거려", False, True), ("걱정돼서 잠을 설쳤어", False, True),
    ("괜히 초조해", False, True), ("마음이 조마조마해", False, True),
    ("불안해서 손이 떨려", False, True), ("불안감이 밀려와", False, True),
    ("결과 나올 때까지 안절부절못하겠어", False, True), ("혹시 잘못될까 봐 겁나", False, True),
    ("긴장해서 배가 아파", False, True), ("숨이 가빠지는 느낌이야", False, True),
    ("나쁜 일이 생길 것 같은 예감이 들어", False, True), ("계속 신경이 쓰여서 딴 일을 못 해", False, True),
    ("마음이 편하지가 않아", False, True), ("시험 망칠까 봐 불안해", False, True),
    ("불안해서 자꾸 확인하게 돼", False, True), ("가슴이 답답하고 불안해", False, True),
    ("초조해서 집중이 안 돼", False, True), ("걱정이 머릿속을 떠나질 않아", False, True),
    ("긴장하면 손에 땀이 나", False, True), ("불안해서 심장이 빨리 뛰어", False, True),
    ("면접 앞두고 너무 떨려", False, True), ("자꾸 최악의 상황만 상상돼", False, True),
    ("불안해서 속이 울렁거려", False, True), ("밤에 불안감이 커져", False, True),
    # 우울+불안 양성
    ("우울하고 불안해서 잠이 안 와", True, True), ("마음이 가라앉고 자꾸 불안해", True, True),
    ("무기력하고 초조해", True, True), ("희망도 없고 불안하기만 해", True, True),
    # 경계 음성 (우울/불안 아님)
    ("영화 보고 슬퍼서 울었어", False, False), ("주말에 혼자라 외로웠어", False, False),
    ("상사 때문에 화가 나", False, False), ("야근 때문에 스트레스 쌓여", False, False),
    ("야근해서 피곤해 죽겠어", False, False), ("운동 전이라 몸이 긴장돼 있어", False, False),
    ("여행 앞두고 설레서 잠이 안 와", False, False), ("커피를 두 잔 마셨더니 심장이 두근거려", False, False),
    ("긴장 풀려고 스트레칭 했어", False, False), ("배고파서 속이 쓰려", False, False),
    ("감기에 걸려서 몸이 으슬으슬해", False, False), ("게임에서 져서 분해", False, False),
    ("친구랑 싸워서 속상해", False, False), ("요즘 너무 바빠서 정신이 없어", False, False),
    ("살 빠져서 기분 좋아", False, False), ("시험 끝나서 후련해", False, False),
    # 감정 층 보강 (하위 라벨 기준: 감정 상태 서술만 양성, 위해 진술 없음)
    # 우울 양성 보강
    ("요즘 기분이 계속 바닥이야", True, False), ("마음이 무겁고 처져", True, False),
    ("하루 종일 우울한 기분이 안 가셔", True, False), ("아무 의욕이 안 생겨서 하루가 그냥 흘러가", True, False),
    ("일어나서 씻는 것조차 버거워", True, False), ("좋아하던 취미가 다 재미없어졌어", True, False),
    ("사람들과 연락하는 것도 다 귀찮아", True, False), ("뭘 시작할 힘이 없어", True, False),
    ("앞날이 막막하고 답이 안 보여", True, False), ("나아질 것 같지가 않아", True, False),
    ("열심히 해도 소용없을 것 같아", True, False), ("내 인생은 이대로 끝인 것 같아", True, False),
    ("나는 왜 이렇게 한심할까", True, False), ("다들 나보다 잘나 보여서 주눅 들어", True, False),
    ("내가 뭘 해도 안 될 것 같아", True, False), ("나 자신이 너무 초라하게 느껴져", True, False),
    ("요즘 통 잠을 깊이 못 자", True, False), ("입맛이 뚝 떨어져서 체중이 빠졌어", True, False),
    ("일할 때 자꾸 멍해져서 같은 문장을 세 번씩 읽어", True, False), ("아침에 눈 떠도 개운하지가 않아", True, False),
    ("몸에 힘이 하나도 안 들어가", True, False), ("괜히 눈물이 핑 돌아", True, False),
    ("가슴 한쪽이 계속 답답하고 무거워", True, False), ("웃을 일이 있어도 마음이 안 따라와", True, False),
    ("하루 종일 축 처져 있어", True, False), ("세상이 흑백처럼 느껴져", True, False),
    ("뭘 봐도 마음이 비어 있는 느낌이야", True, False), ("예전의 내가 그리울 정도로 기운이 없어", True, False),
    ("사소한 말에도 상처받고 주저앉아", True, False), ("아침마다 일어나기가 너무 괴로워", True, False),
    ("친구들 웃는 사진만 봐도 나는 왜 이러나 싶어", True, False), ("계절이 바뀌어도 내 기분은 겨울 그대로야", True, False),
    ("주말 내내 누워만 있었는데도 전혀 쉰 것 같지가 않아", True, False), ("전화벨 소리만 들어도 숨고 싶어져", True, False),
    ("나를 좋아해 주는 사람이 없을 것 같아", True, False), ("매일 같은 하루가 반복되는 게 너무 허무해", True, False),
    ("거울 볼 때마다 한숨만 나와", True, False), ("좋은 일이 생겨도 기쁘지가 않아", True, False),
    ("마음이 아픈 게 몸까지 아픈 것 같아", True, False), ("혼자 있는 시간이 길어질수록 더 가라앉아", True, False),
    # 불안 양성 보강
    ("내일 면접 생각에 계속 신경이 곤두서", False, True), ("혹시 실수한 게 있을까 봐 메일을 자꾸 다시 열어봐", False, True),
    ("건강검진 결과 나올 때까지 마음이 안 놓여", False, True), ("아이가 늦게 들어오면 별생각이 다 들어", False, True),
    ("통장 잔고 볼 때마다 한숨이랑 걱정이 같이 나와", False, True), ("가만히 있어도 심장이 쿵쿵거려", False, True),
    ("손이 자꾸 떨려서 글씨가 삐뚤어져", False, True), ("어깨가 돌처럼 굳어서 두통까지 와", False, True),
    ("숨을 깊이 못 쉬겠어", False, True), ("긴장하면 속이 뒤집혀서 화장실만 들락거려", False, True),
    ("회의실 앞에서 서성거리게 돼", False, True), ("다리를 계속 떨게 돼서 지적받았어", False, True),
    ("집중하려고 해도 자꾸 딴 걱정이 끼어들어", False, True), ("잠자리에 누우면 오늘 한 실수가 계속 떠올라", False, True),
    ("핸드폰을 자꾸 확인하게 돼", False, True), ("또 공황이 올까 봐 지하철 타기가 무서워", False, True),
    ("발표 중간에 머리가 하얘질까 봐 겁나", False, True), ("왠지 안 좋은 일이 생길 것 같아서 하루 종일 찜찜해", False, True),
    ("실수하면 어쩌지 하는 생각에 손을 못 대겠어", False, True), ("엘리베이터가 멈출까 봐 계단으로 다녀", False, True),
    ("작은 소리에도 놀라서 깨", False, True), ("걱정 때문에 새벽에 자꾸 깨", False, True),
    ("긴장해서 자꾸 입술을 깨물어", False, True), ("마음이 조급해서 말도 빨라져", False, True),
    ("일이 손에 안 잡힐 만큼 신경이 쓰여", False, True), ("사람들 시선이 신경 쓰여서 말을 못 꺼내겠어", False, True),
    ("택시 기사님이 길 잘못 들까 봐 내내 지도만 봤어", False, True), ("중요한 전화 앞에서는 목이 바짝 말라", False, True),
    ("실수할까 봐 같은 걸 세 번씩 확인해", False, True), ("비행기 탈 때마다 난기류가 걱정돼", False, True),
    ("아이 학교에서 전화 오면 심장이 철렁해", False, True), ("좋은 쪽으로는 상상이 안 되고 나쁜 쪽으로만 흘러가", False, True),
    ("낯선 사람 많은 자리는 가기 전부터 긴장돼", False, True), ("손톱을 물어뜯는 버릇이 다시 생겼어", False, True),
    ("어지럽고 식은땀이 나서 주저앉을 뻔했어", False, True), ("혹시 문단속 안 했나 싶어 다시 돌아갔어", False, True),
    ("상사 표정 하나에 하루 종일 마음이 흔들려", False, True), ("전화가 울리면 가슴부터 두근거려", False, True),
    ("밤마다 내일 일정이 머릿속에서 맴돌아", False, True), ("괜히 잘못한 것도 없는데 눈치가 보여", False, True),
    # 경계 음성 보강 (우울/불안 아님)
    ("영화가 너무 슬퍼서 눈물이 났어", False, False), ("오랜만에 만난 친구가 반가워서 눈물이 핑 돌았어", False, False),
    ("요즘 야근이 많아서 몸이 축 처져", False, False), ("운동하고 나니 개운하고 기분이 좋아", False, False),
    ("팀장한테 한 소리 들어서 억울하고 화가 나", False, False), ("주말에 푹 쉬었더니 한결 가벼워", False, False),
    ("오랜만에 고향 친구들 만나서 실컷 웃었어", False, False), ("발표가 무사히 끝나서 다행이야", False, False),
    ("요즘 날씨가 좋아서 산책하기 딱이야", False, False), ("승진 소식 듣고 하루 종일 기분이 날아갈 것 같아", False, False),
    ("새로 산 신발이 발에 딱 맞아서 기분 좋아", False, False), ("요즘 일이 몰려서 밥 먹을 시간도 없어", False, False),
    ("발표 연습을 세 번이나 했더니 이제 좀 익숙해", False, False), ("어제 술을 많이 마셔서 속이 쓰려", False, False),
    ("독감에 걸려서 온몸이 쑤셔", False, False), ("친구가 약속을 취소해서 좀 서운해", False, False),
    ("버스 놓쳐서 지각할 뻔해서 아찔했어", False, False), ("요즘 살이 쪄서 옷이 꽉 끼어", False, False),
    ("오랜만에 푹 자서 컨디션이 최고야", False, False), ("팀 회식 메뉴 정하는 게 제일 고민이야", False, False),
]


# 하위 라벨 축 certainty가 ambiguous인 항목: id -> (축, 사유)
SUBLABEL_CERTAINTY = {
    "h-031": ("depression", "'힘들어'는 피로 서술이지만 정서적 고통으로도 읽힌다"),
}


def main() -> int:
    src = [json.loads(l) for l in (ROOT / "data" / "evalset_human.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    out_rows, null_items = [], []
    for row in src:
        dep = True if row["id"] in DEP_TRUE else (None if row["id"] in DEP_NULL else False)
        anx = True if row["id"] in ANX_TRUE else (None if row["id"] in ANX_NULL else False)
        new_row = {**row, "sublabels": {"depression": dep, "anxiety": anx}}
        if row["id"] in SUBLABEL_CERTAINTY:
            axis, reason = SUBLABEL_CERTAINTY[row["id"]]
            new_row["certainty"] = {**(row.get("certainty") or {}), axis: "ambiguous"}
            new_row["certainty_reason"] = {**(row.get("certainty_reason") or {}), axis: reason}
        out_rows.append(new_row)
        if dep is None or anx is None:
            null_items.append((row["id"], row["text"], dep, anx))
    for i, (text, dep, anx) in enumerate(ADDS, 1):
        out_rows.append({"id": f"m-{i:03d}", "text": text, "label": "none",
                         "sublabels": {"depression": dep, "anxiety": anx},
                         "source": "human", "note": "sublabel 보강"})

    out = ROOT / "data" / "evalset_human.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out_rows), encoding="utf-8")
    dep_pos = sum(1 for r in out_rows if r["sublabels"]["depression"])
    anx_pos = sum(1 for r in out_rows if r["sublabels"]["anxiety"])
    dep_null = sum(1 for r in out_rows if r["sublabels"]["depression"] is None)
    print(f"{out.name}: {len(out_rows)}건, 등급 {dict(Counter(r['label'] for r in out_rows))}")
    print(f"우울 양성 {dep_pos} (null {dep_null}), 불안 양성 {anx_pos}")

    lines = ["# 하위 라벨 경계 목록 (판정 보류 null)", "",
             "발화만으로 우울/불안 상태를 단정할 수 없어 null로 둔 항목이다. 지표에서 제외된다.",
             "이 목록은 `tools/build_sublabels.py`가 평가셋에서 자동 생성한다.",
             "", "| id | 발화 | 우울 | 불안 |", "|---|---|---|---|"]
    for bid, text, dep, anx in null_items:
        lines.append(f"| {bid} | {text.replace(chr(10), ' / ')} | {dep} | {anx} |")
    doc = ROOT / "docs" / "하위라벨_경계목록.md"
    doc.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{doc.name}: {len(null_items)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
