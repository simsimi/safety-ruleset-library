# 위험판별 평가 리포트

- 테스트셋: evalset_balanced30.jsonl (500건)
- 사전: (저장된 결과) (저장된 결과)
- 평가 단계: dict
- 판정 방식: 패턴이 하나라도 걸리면 risk, 없으면 none이다. 사전 패턴에 등급은 없다. 정답 라벨이 등급(danger/emergency)으로 붙은 테스트셋은 채점할 때 risk로 접는다.
- 평가 완료 500건, 오류 0건 (오류는 지표 분모에서 제외)

## 전체 지표

- 정확도(accuracy): 0.6520
- macro F1: 0.6350

## 라벨별 지표

| 라벨 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| none | 0.8411 | 0.6200 | 0.7138 | 350 |
| risk | 0.4504 | 0.7267 | 0.5561 | 150 |

## 혼동행렬

행=정답, 열=예측.

| 정답 \ 예측 | none | risk |
|---|---|---|
| none | 217 | 133 |
| risk | 41 | 109 |

## 패턴 매칭 통계

패턴별 매칭 건수와, 그중 정답이 none인 오탐 매칭 건수다. 자주 걸리는데 오탐이 많은 패턴부터 다듬는다.

| 패턴 | 매칭 | 오탐 매칭 |
|---|---|---|
| dg-risk-word | 68 | 43 |
| dg-phrase-01 | 59 | 47 |
| dg-phrase-14 | 10 | 5 |
| ex2-19 | 9 | 1 |
| em-jump | 8 | 0 |
| dg-phrase-08 | 7 | 5 |
| ex-dg-01 | 7 | 5 |
| ex3-05 | 7 | 3 |
| em-will | 6 | 0 |
| dg-phrase-10 | 6 | 5 |
| ex3-06 | 6 | 0 |
| ex3-03 | 5 | 0 |
| dg-phrase-16 | 5 | 2 |
| ex3-04 | 5 | 2 |
| dg-phrase-15 | 5 | 2 |
| ex3-01 | 5 | 4 |
| ex2-04 | 3 | 0 |
| em-phrase-08 | 3 | 0 |
| ex3-18 | 3 | 0 |
| dg-phrase-13 | 3 | 2 |
| ex2-18 | 2 | 0 |
| ex2-07 | 2 | 0 |
| ex3-13 | 2 | 0 |
| ex3-02 | 2 | 0 |
| dg-phrase-17 | 2 | 2 |
| dg-phrase-09 | 2 | 2 |
| ex2-03 | 2 | 0 |
| dg-phrase-18 | 2 | 2 |
| ex2-08 | 2 | 0 |
| ex3-09 | 2 | 1 |
| em-phrase-09 | 2 | 0 |
| ex-em-01 | 2 | 0 |
| ex2-09 | 2 | 2 |
| ex-em-02 | 2 | 1 |
| ex-dg-05 | 2 | 1 |
| ex-dg-06 | 1 | 0 |
| em-phrase-10 | 1 | 0 |
| em-phrase-04 | 1 | 0 |
| ex2-06 | 1 | 0 |
| em-phrase-02 | 1 | 0 |
| em-phrase-12 | 1 | 0 |
| ex2-05 | 1 | 1 |
| ex-dg-02 | 1 | 1 |
| ex2-13 | 1 | 1 |
| em-phrase-01 | 1 | 0 |
| em-phrase-03 | 1 | 0 |
| dg-phrase-12 | 1 | 0 |
| ex3-10 | 1 | 0 |
| dg-phrase-11 | 1 | 1 |
| ex3-07 | 1 | 1 |
| ex2-15 | 1 | 0 |
| ex2-01 | 1 | 0 |

## 오탐 (위험 아님을 위험으로 판정)

| id | 정답 | 예측 |
|---|---|---|
| b30-001 | none | risk |
| b30-005 | none | risk |
| b30-007 | none | risk |
| b30-008 | none | risk |
| b30-011 | none | risk |
| b30-012 | none | risk |
| b30-016 | none | risk |
| b30-017 | none | risk |
| b30-022 | none | risk |
| b30-030 | none | risk |
| b30-042 | none | risk |
| b30-046 | none | risk |
| b30-056 | none | risk |
| b30-064 | none | risk |
| b30-065 | none | risk |
| b30-066 | none | risk |
| b30-076 | none | risk |
| b30-084 | none | risk |
| b30-088 | none | risk |
| b30-091 | none | risk |
| b30-094 | none | risk |
| b30-095 | none | risk |
| b30-104 | none | risk |
| b30-105 | none | risk |
| b30-106 | none | risk |
| b30-107 | none | risk |
| b30-110 | none | risk |
| b30-118 | none | risk |
| b30-120 | none | risk |
| b30-125 | none | risk |
| b30-133 | none | risk |
| b30-134 | none | risk |
| b30-135 | none | risk |
| b30-139 | none | risk |
| b30-149 | none | risk |
| b30-150 | none | risk |
| b30-160 | none | risk |
| b30-162 | none | risk |
| b30-168 | none | risk |
| b30-169 | none | risk |
| b30-171 | none | risk |
| b30-172 | none | risk |
| b30-174 | none | risk |
| b30-177 | none | risk |
| b30-184 | none | risk |
| b30-185 | none | risk |
| b30-189 | none | risk |
| b30-192 | none | risk |
| b30-197 | none | risk |
| b30-201 | none | risk |
| b30-207 | none | risk |
| b30-217 | none | risk |
| b30-219 | none | risk |
| b30-222 | none | risk |
| b30-224 | none | risk |
| b30-226 | none | risk |
| b30-236 | none | risk |
| b30-238 | none | risk |
| b30-252 | none | risk |
| b30-255 | none | risk |
| b30-257 | none | risk |
| b30-258 | none | risk |
| b30-259 | none | risk |
| b30-266 | none | risk |
| b30-268 | none | risk |
| b30-269 | none | risk |
| b30-271 | none | risk |
| b30-272 | none | risk |
| b30-275 | none | risk |
| b30-278 | none | risk |
| b30-280 | none | risk |
| b30-282 | none | risk |
| b30-283 | none | risk |
| b30-293 | none | risk |
| b30-294 | none | risk |
| b30-302 | none | risk |
| b30-304 | none | risk |
| b30-309 | none | risk |
| b30-310 | none | risk |
| b30-314 | none | risk |
| b30-316 | none | risk |
| b30-318 | none | risk |
| b30-319 | none | risk |
| b30-320 | none | risk |
| b30-323 | none | risk |
| b30-324 | none | risk |
| b30-325 | none | risk |
| b30-334 | none | risk |
| b30-336 | none | risk |
| b30-343 | none | risk |
| b30-350 | none | risk |
| b30-351 | none | risk |
| b30-353 | none | risk |
| b30-354 | none | risk |
| b30-360 | none | risk |
| b30-363 | none | risk |
| b30-365 | none | risk |
| b30-369 | none | risk |
| b30-372 | none | risk |
| b30-373 | none | risk |
| b30-374 | none | risk |
| b30-376 | none | risk |
| b30-377 | none | risk |
| b30-378 | none | risk |
| b30-383 | none | risk |
| b30-388 | none | risk |
| b30-392 | none | risk |
| b30-393 | none | risk |
| b30-397 | none | risk |
| b30-399 | none | risk |
| b30-401 | none | risk |
| b30-403 | none | risk |
| b30-405 | none | risk |
| b30-407 | none | risk |
| b30-417 | none | risk |
| b30-420 | none | risk |
| b30-421 | none | risk |
| b30-427 | none | risk |
| b30-428 | none | risk |
| b30-436 | none | risk |
| b30-439 | none | risk |
| b30-451 | none | risk |
| b30-456 | none | risk |
| b30-459 | none | risk |
| b30-467 | none | risk |
| b30-471 | none | risk |
| b30-472 | none | risk |
| b30-475 | none | risk |
| b30-483 | none | risk |
| b30-485 | none | risk |
| b30-489 | none | risk |
| b30-492 | none | risk |
| b30-499 | none | risk |

## 미탐 (위험을 놓침)

| id | 정답 | 예측 |
|---|---|---|
| b30-002 | risk | none |
| b30-004 | risk | none |
| b30-035 | risk | none |
| b30-038 | risk | none |
| b30-040 | risk | none |
| b30-041 | risk | none |
| b30-063 | risk | none |
| b30-072 | risk | none |
| b30-073 | risk | none |
| b30-113 | risk | none |
| b30-119 | risk | none |
| b30-122 | risk | none |
| b30-140 | risk | none |
| b30-148 | risk | none |
| b30-152 | risk | none |
| b30-153 | risk | none |
| b30-164 | risk | none |
| b30-235 | risk | none |
| b30-239 | risk | none |
| b30-240 | risk | none |
| b30-241 | risk | none |
| b30-247 | risk | none |
| b30-286 | risk | none |
| b30-289 | risk | none |
| b30-313 | risk | none |
| b30-317 | risk | none |
| b30-335 | risk | none |
| b30-337 | risk | none |
| b30-338 | risk | none |
| b30-342 | risk | none |
| b30-385 | risk | none |
| b30-396 | risk | none |
| b30-409 | risk | none |
| b30-418 | risk | none |
| b30-423 | risk | none |
| b30-442 | risk | none |
| b30-443 | risk | none |
| b30-465 | risk | none |
| b30-476 | risk | none |
| b30-480 | risk | none |
| b30-491 | risk | none |
