# 위험판별 평가 리포트

- 테스트셋: evalset_human.jsonl (500건)
- 사전: (저장된 결과) (저장된 결과)
- 평가 단계: dict
- 판정 방식: 패턴이 하나라도 걸리면 risk, 없으면 none이다. 사전 패턴에 등급은 없다. 정답 라벨이 등급(danger/emergency)으로 붙은 테스트셋은 채점할 때 risk로 접는다.
- 평가 완료 500건, 오류 0건 (오류는 지표 분모에서 제외)

## 전체 지표

- 정확도(accuracy): 0.9540
- macro F1: 0.9391

## 라벨별 지표

| 라벨 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| none | 1.0000 | 0.9403 | 0.9692 | 385 |
| risk | 0.8333 | 1.0000 | 0.9091 | 115 |

## 확실성(certainty) 분리 지표

주 지표는 위 전체 지표다. certain-only는 참고용이며, ambiguous 건은 방향별로 센다.

- certainty 분포: certain 490건, ambiguous 10건, needs_context 0건
- certain-only (490건): 정확도 0.9592, 위험 Precision 0.8438, Recall 1.0000, F1 0.9153
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
| none | 362 | 23 |
| risk | 0 | 115 |

## 패턴 매칭 통계

패턴별 매칭 건수와, 그중 정답이 none인 오탐 매칭 건수다. 자주 걸리는데 오탐이 많은 패턴부터 다듬는다.

| 패턴 | 매칭 | 오탐 매칭 |
|---|---|---|
| dg-risk-word | 65 | 12 |
| dg-phrase-01 | 27 | 7 |
| em-will | 6 | 0 |
| dg-phrase-10 | 5 | 2 |
| ex2-04 | 4 | 2 |
| ex3-03 | 4 | 0 |
| ex3-06 | 3 | 0 |
| em-jump | 3 | 0 |
| ex-dg-01 | 2 | 0 |
| dg-phrase-02 | 2 | 0 |
| ex-em-01 | 2 | 0 |
| em-phrase-02 | 2 | 1 |
| em-phrase-01 | 1 | 0 |
| dg-phrase-08 | 1 | 0 |
| dg-phrase-13 | 1 | 0 |
| dg-phrase-14 | 1 | 0 |
| dg-phrase-15 | 1 | 0 |
| dg-phrase-17 | 1 | 0 |
| dg-phrase-18 | 1 | 0 |
| dg-phrase-16 | 1 | 0 |
| dg-phrase-03 | 1 | 0 |
| dg-phrase-04 | 1 | 0 |
| dg-phrase-07 | 1 | 0 |
| em-phrase-04 | 1 | 0 |
| em-phrase-03 | 1 | 0 |
| em-phrase-09 | 1 | 0 |
| em-phrase-08 | 1 | 0 |
| ex2-19 | 1 | 0 |
| em-phrase-10 | 1 | 0 |
| em-phrase-12 | 1 | 0 |
| ex-dg-02 | 1 | 0 |
| ex-dg-03 | 1 | 0 |
| ex-dg-04 | 1 | 0 |
| ex-dg-05 | 1 | 0 |
| ex-dg-06 | 1 | 0 |
| ex-dg-07 | 1 | 0 |
| ex-dg-08 | 1 | 0 |
| ex-em-02 | 1 | 0 |

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

## 미탐 (위험을 놓침)

없음
