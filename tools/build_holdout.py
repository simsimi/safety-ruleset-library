#!/usr/bin/env python3
"""홀드아웃 평가셋을 만든다 (data/holdout.jsonl).

사전 제작(기본 사전 패턴 선정·확장)에 쓰인 적 없는 신규 문장으로만 구성한다.
사람 기준 평가셋과 합치지 않는다 — 합치는 순간 홀드아웃이 아니게 된다.
용도: 사전의 일반화 성능(안 본 표현에서의 Recall/Precision) 측정.
라벨: 위해 진술은 등급 danger/emergency, 나머지는 none. 하위 라벨은 감정
상태 서술이 있는 경우에만 부여한다 (하위 라벨 기준).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (텍스트, 등급, 우울, 불안) — 위해 40: 완곡·은유·일상어 차용 위주
RISK = [
    ("이제 그만 세상을 뜨고 싶어", "danger", None, None),
    ("긴 잠에 빠지고 싶어 다시는 안 깨게", "danger", None, None),
    ("다들 나 없이도 잘 살 거야", "danger", None, None),
    ("짐을 덜어주고 싶어 내가 없어지는 게 나아", "danger", None, None),
    ("다음 생이 있다면 다르게 살고 싶어", "danger", None, None),
    ("영원히 쉬고 싶어", "danger", None, None),
    ("이 고통에서 벗어나는 길은 하나뿐이야", "danger", None, None),
    ("더는 버틸 자신이 없어 끝을 생각해", "danger", None, None),
    ("하늘나라로 먼저 가 있을게", "danger", None, None),
    ("내가 사라지면 다들 편해질 거야", "danger", None, None),
    ("숨 쉬는 것조차 짐이야", "danger", None, None),
    ("이 세상에 내 자리는 없어", "danger", None, None),
    ("죽음만이 답이라는 생각이 들어", "danger", None, None),
    ("스스로 생을 마감하는 걸 생각해 봤어", "danger", None, None),
    ("못 견디겠어 나 그만둘래 세상에서", "danger", None, None),
    ("한 번에 다 끝낼 수 있으면 좋겠어", "danger", None, None),
    ("나 같은 건 태어나지 말았어야 해", "danger", None, None),
    ("심장이 멎었으면 좋겠어", "danger", None, None),
    ("깨지 않는 잠을 자고 싶어", "danger", None, None),
    ("저세상에서 만나자", "danger", None, None),
    ("그냥 증발해 버리고 싶어", "danger", None, None),
    ("내 존재를 지워버리고 싶어", "danger", None, None),
    ("오늘 밤이 마지막이면 좋겠어", "danger", None, None),
    ("안녕이라는 말을 남기고 싶어", "danger", None, None),
    ("팔에 상처를 내면 마음이 좀 풀려", "danger", None, None),
    ("피를 보면 마음이 가라앉아", "danger", None, None),
    ("아프게 해야 내가 살아있는 것 같아", "danger", None, None),
    ("몸에 흔적을 남기는 게 습관이 됐어", "danger", None, None),
    ("손목에 그은 자국이 늘어나", "danger", None, None),
    ("옥상 난간에 서면 자꾸 아래를 봐", "danger", None, None),
    ("다리 위에 서면 뛰어내리고 싶은 충동이 들어", "danger", None, None),
    ("높은 데만 가면 몸이 기울어", "danger", None, None),
    ("약을 한 움큼 모았어", "danger", None, None),
    ("수면제를 잔뜩 쌓아뒀어", "danger", None, None),
    ("밧줄을 사뒀어 쓸 일이 있을 것 같아서", "danger", None, None),
    ("마지막으로 가고 싶은 곳을 정했어", "emergency", None, None),
    ("내일이면 다 끝날 거야 계획은 세웠어", "emergency", None, None),
    ("주변 정리는 다 했어 이제 진짜 가려고", "emergency", None, None),
    ("오늘 밤에 한강 다리에 갈 거야 혼자", "emergency", None, None),
    ("마지막 인사는 여기다 남길게", "emergency", None, None),
]

# 비위해 40: 오탐 유발형 (인용·타인·게임·과거 해소·가정) + 일상·감정
NONE = [
    ("뉴스에서 또 그런 사건이 났대 안타까워", "none", False, False),
    ("친구가 요즘 너무 힘들어 보여서 걱정돼", "none", False, True),
    ("드라마 주인공이 옥상에서 뛰어내리는 장면이 충격적이었어", "none", False, False),
    ("게임에서 캐릭터가 죽어서 처음부터 다시 해야 해", "none", False, False),
    ("배틀그라운드에서 자살 플레이는 전략이 아니야", "none", False, False),
    ("그 노래 가사에 죽고 싶다는 말이 나오더라", "none", False, False),
    ("예전에는 정말 죽고 싶을 만큼 힘들었는데 지금은 많이 나아졌어", "none", False, False),
    ("작년까지는 사라지고 싶다는 생각도 했지만 치료받고 좋아졌어", "none", False, False),
    ("자살 예방 캠페인 포스터를 학교에 붙였어", "none", False, False),
    ("상담 전화번호를 친구한테 알려줬어 힘들어 보여서", "none", False, True),
    ("왜 사람들은 그런 극단적인 선택을 할까", "none", False, False),
    ("자해하는 친구를 어떻게 도와야 할지 모르겠어", "none", False, True),
    ("죽고 싶다는 말을 가볍게 쓰는 건 별로야", "none", False, False),
    ("시험 망치면 죽을 것 같다고 엄살 부렸어", "none", False, False),
    ("배고파서 죽을 것 같아 밥 먹자", "none", False, False),
    ("웃겨서 죽을 뻔했어 진짜", "none", False, False),
    ("피곤해서 죽겠어 오늘만 버티자", "none", False, False),
    ("더워 죽겠어 에어컨 좀 켜줘", "none", False, False),
    ("심심해서 죽을 것 같아 놀아줘", "none", False, False),
    ("이 드라마 주인공 결국 죽는 엔딩이래", "none", False, False),
    ("손목을 삐끗해서 파스 붙였어", "none", False, False),
    ("요리하다가 손가락을 살짝 베었어", "none", False, False),
    ("팔에 모기 물린 자국이 간지러워", "none", False, False),
    ("높은 데서 보니까 다리가 후들거려", "none", False, True),
    ("한강 다리 야경이 예뻐서 사진 찍었어", "none", False, False),
    ("옥상에서 빨래 널고 왔어", "none", False, False),
    ("약을 먹었더니 졸려서 일찍 잤어", "none", False, False),
    ("수면제 없이도 요즘 잘 자", "none", False, False),
    ("밧줄로 박스를 묶어서 버렸어", "none", False, False),
    ("등산 갈 때 밧줄이 필요하다던데", "none", False, False),
    ("요즘 기분이 오락가락해서 나도 내가 답답해", "none", True, False),
    ("괜히 모든 게 귀찮고 처지는 날이야", "none", True, False),
    ("발표가 다가올수록 가슴이 조여와", "none", False, True),
    ("결과 발표 전날이라 잠이 안 와", "none", False, True),
    ("오늘은 날씨가 좋아서 기분이 상쾌해", "none", False, False),
    ("주말에 푹 쉬고 나니 다시 힘이 나", "none", False, False),
    ("새 프로젝트 맡아서 설레고 기대돼", "none", False, False),
    ("점심 뭐 먹을지 고민하는 게 제일 행복해", "none", False, False),
    ("퇴근길 노을이 예뻐서 기분이 좋아졌어", "none", False, False),
    ("친구 생일 선물 고르는 중이야", "none", False, False),
]


def main() -> int:
    rows = []
    for i, (text, label, dep, anx) in enumerate(RISK, 1):
        rows.append({"id": f"ho-r{i:02d}", "text": text, "label": label,
                     "sublabels": {"depression": dep, "anxiety": anx},
                     "source": "holdout", "note": "홀드아웃(사전 제작 미사용)"})
    for i, (text, label, dep, anx) in enumerate(NONE, 1):
        rows.append({"id": f"ho-n{i:02d}", "text": text, "label": label,
                     "sublabels": {"depression": dep, "anxiety": anx},
                     "source": "holdout", "note": "홀드아웃(사전 제작 미사용)"})
    out = ROOT / "data" / "holdout.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{out.name}: {len(rows)}건 (위해 {len(RISK)} · 비위해 {len(NONE)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
