# 위험판별 평가 리포트

- 테스트셋: testset.jsonl (271건)
- 사전: (저장된 결과) (저장된 결과)
- 평가 단계: dict
- 판정 방식: 패턴이 하나라도 걸리면 risk, 없으면 none이다. 사전 패턴에 등급은 없다. 정답 라벨이 등급(danger/emergency)으로 붙은 테스트셋은 채점할 때 risk로 접는다.
- 평가 완료 271건, 오류 0건 (오류는 지표 분모에서 제외)

## 전체 지표

- 정확도(accuracy): 1.0000
- macro F1: 1.0000

## 라벨별 지표

| 라벨 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| none | 1.0000 | 1.0000 | 1.0000 | 147 |
| risk | 1.0000 | 1.0000 | 1.0000 | 124 |

## 혼동행렬

행=정답, 열=예측.

| 정답 \ 예측 | none | risk |
|---|---|---|
| none | 147 | 0 |
| risk | 0 | 124 |

## 패턴 매칭 통계

패턴별 매칭 건수와, 그중 정답이 none인 오탐 매칭 건수다. 자주 걸리는데 오탐이 많은 패턴부터 다듬는다.

| 패턴 | 매칭 | 오탐 매칭 |
|---|---|---|
| dg-risk-word | 61 | 0 |
| dg-phrase-01 | 27 | 0 |
| em-will | 6 | 0 |
| dg-phrase-10 | 5 | 0 |
| em-jump | 4 | 0 |
| dg-phrase-02 | 2 | 0 |
| em-phrase-02 | 2 | 0 |
| em-phrase-01 | 1 | 0 |
| ex-dg-01 | 1 | 0 |
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
| ex-em-01 | 1 | 0 |
| em-phrase-09 | 1 | 0 |
| em-phrase-08 | 1 | 0 |
| em-phrase-10 | 1 | 0 |
| em-phrase-12 | 1 | 0 |

## 오탐 (위험 아님을 위험으로 판정)

없음

## 미탐 (위험을 놓침)

없음
