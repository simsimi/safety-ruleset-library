# 위험판별 평가 리포트

- 테스트셋: evalset_human.jsonl (500건)
- 통합: (저장된 결과) (저장된 결과)
- 평가 단계: combined
- 판정 방식: 1단계(사전+위해 모델 결합)가 risk면 그대로 확정하고, none일 때만 2단계(감정 모델) 신호로 risk까지 올린다. 정답은 위해 라벨이 risk이거나 하위 라벨(우울/불안) 중 하나라도 양성이면 risk다 — 여기서 risk는 단계명이 아니라 보편적인 위험 탐지의 이진 정답이다.
- 평가 완료 500건, 오류 0건 (오류는 지표 분모에서 제외)
- 모델 임계값: depression ≥ 0.5, anxiety ≥ 0.5

## 전체 지표

- 정확도(accuracy): 0.7320
- macro F1: 0.7286

## 라벨별 지표

| 라벨 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| none | 0.6851 | 0.8508 | 0.7590 | 248 |
| risk | 0.8073 | 0.6151 | 0.6982 | 252 |

## 단계 기여 분해

최종 판정의 정답·오탐이 어느 단계에서 왔는지 분해한 것이다.

| 구분 | 건수 |
|---|---|
| 사전이 잡은 위험 | 115 |
| 모델 신호로 잡은 위험 (사전은 놓침) | 40 |
| 끝내 놓친 위험 | 97 |
| 사전이 만든 오탐 | 23 |
| 모델 신호가 만든 오탐 (사전은 none) | 14 |
| 맞게 비위험으로 둔 건 | 211 |

## 확실성(certainty) 분리 지표

주 지표는 위 전체 지표다. certain-only는 참고용이며, ambiguous 건은 방향별로 센다.

- certainty 분포: certain 490건, ambiguous 10건, needs_context 0건
- certain-only (490건): 정확도 0.7327, 위험 Precision 0.8132, Recall 0.6041, F1 0.6932
- ambiguous (10건): 정답 7건, 누락(위험→none) 0건, 과탐(none→위험) 3건

## 소그룹 지표

| 소그룹 | 건수 | 위험 정답 | 탐지 | 탐지율 | none 정답 | 오탐 | FP율 |
|---|---|---|---|---|---|---|---|
| hyperbole_meme | 5 | 5 | 5 | 1.0000 | 0 | 0 | - |
| indirect_question | 3 | 0 | 0 | - | 3 | 3 | 1.0000 |

## 혼동행렬

행=정답, 열=예측.

| 정답 \ 예측 | none | risk |
|---|---|---|
| none | 211 | 37 |
| risk | 97 | 155 |

## 오탐 (위험 아님을 위험으로 판정)

| id | 정답 | 예측 |
|---|---|---|
| s-043 | none | risk |
| s-044 | none | risk |
| s-045 | none | risk |
| s-051 | none | risk |
| s-052 | none | risk |
| s-053 | none | risk |
| s-054 | none | risk |
| s-055 | none | risk |
| s-056 | none | risk |
| s-057 | none | risk |
| s-058 | none | risk |
| s-091 | none | risk |
| s-092 | none | risk |
| s-093 | none | risk |
| s-096 | none | risk |
| s-097 | none | risk |
| s-098 | none | risk |
| s-099 | none | risk |
| s-100 | none | risk |
| s-101 | none | risk |
| s-102 | none | risk |
| s-147 | none | risk |
| h-021 | none | risk |
| h-027 | none | risk |
| h-028 | none | risk |
| h-037 | none | risk |
| h-038 | none | risk |
| h-041 | none | risk |
| h-042 | none | risk |
| m-053 | none | risk |
| m-054 | none | risk |
| m-058 | none | risk |
| m-059 | none | risk |
| m-060 | none | risk |
| m-061 | none | risk |
| m-149 | none | risk |
| m-150 | none | risk |

## 미탐 (위험을 놓침)

| id | 정답 | 예측 |
|---|---|---|
| m-001 | risk (우울) | none |
| m-002 | risk (우울) | none |
| m-004 | risk (우울) | none |
| m-006 | risk (우울) | none |
| m-007 | risk (우울) | none |
| m-008 | risk (우울) | none |
| m-009 | risk (우울) | none |
| m-010 | risk (우울) | none |
| m-011 | risk (우울) | none |
| m-012 | risk (우울) | none |
| m-013 | risk (우울) | none |
| m-014 | risk (우울) | none |
| m-015 | risk (우울) | none |
| m-016 | risk (우울) | none |
| m-017 | risk (우울) | none |
| m-018 | risk (우울) | none |
| m-019 | risk (우울) | none |
| m-020 | risk (우울) | none |
| m-021 | risk (우울) | none |
| m-022 | risk (우울) | none |
| m-024 | risk (우울) | none |
| m-028 | risk (불안) | none |
| m-031 | risk (불안) | none |
| m-032 | risk (불안) | none |
| m-034 | risk (불안) | none |
| m-035 | risk (불안) | none |
| m-036 | risk (불안) | none |
| m-037 | risk (불안) | none |
| m-045 | risk (불안) | none |
| m-046 | risk (불안) | none |
| m-069 | risk (우울) | none |
| m-070 | risk (우울) | none |
| m-073 | risk (우울) | none |
| m-074 | risk (우울) | none |
| m-075 | risk (우울) | none |
| m-076 | risk (우울) | none |
| m-078 | risk (우울) | none |
| m-079 | risk (우울) | none |
| m-080 | risk (우울) | none |
| m-081 | risk (우울) | none |
| m-082 | risk (우울) | none |
| m-083 | risk (우울) | none |
| m-084 | risk (우울) | none |
| m-085 | risk (우울) | none |
| m-086 | risk (우울) | none |
| m-087 | risk (우울) | none |
| m-088 | risk (우울) | none |
| m-089 | risk (우울) | none |
| m-091 | risk (우울) | none |
| m-092 | risk (우울) | none |
| m-093 | risk (우울) | none |
| m-094 | risk (우울) | none |
| m-095 | risk (우울) | none |
| m-096 | risk (우울) | none |
| m-097 | risk (우울) | none |
| m-098 | risk (우울) | none |
| m-099 | risk (우울) | none |
| m-100 | risk (우울) | none |
| m-101 | risk (우울) | none |
| m-102 | risk (우울) | none |
| m-103 | risk (우울) | none |
| m-105 | risk (우울) | none |
| m-106 | risk (우울) | none |
| m-107 | risk (우울) | none |
| m-108 | risk (우울) | none |
| m-109 | risk (불안) | none |
| m-110 | risk (불안) | none |
| m-111 | risk (불안) | none |
| m-112 | risk (불안) | none |
| m-114 | risk (불안) | none |
| m-115 | risk (불안) | none |
| m-116 | risk (불안) | none |
| m-117 | risk (불안) | none |
| m-119 | risk (불안) | none |
| m-120 | risk (불안) | none |
| m-122 | risk (불안) | none |
| m-123 | risk (불안) | none |
| m-124 | risk (불안) | none |
| m-125 | risk (불안) | none |
| m-126 | risk (불안) | none |
| m-127 | risk (불안) | none |
| m-128 | risk (불안) | none |
| m-129 | risk (불안) | none |
| m-132 | risk (불안) | none |
| m-133 | risk (불안) | none |
| m-134 | risk (불안) | none |
| m-135 | risk (불안) | none |
| m-136 | risk (불안) | none |
| m-137 | risk (불안) | none |
| m-139 | risk (불안) | none |
| m-140 | risk (불안) | none |
| m-142 | risk (불안) | none |
| m-143 | risk (불안) | none |
| m-144 | risk (불안) | none |
| m-145 | risk (불안) | none |
| m-147 | risk (불안) | none |
| m-148 | risk (불안) | none |
