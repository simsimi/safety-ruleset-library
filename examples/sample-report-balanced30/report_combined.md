# 위험판별 평가 리포트

- 테스트셋: evalset_balanced30.jsonl (500건)
- 통합: (저장된 결과) (저장된 결과)
- 평가 단계: combined
- 판정 방식: 1단계(사전+위해 모델 결합)가 risk면 그대로 확정하고, none일 때만 2단계(감정 모델) 신호로 risk까지 올린다. 정답은 위해 라벨이 risk이거나 하위 라벨(우울/불안) 중 하나라도 양성이면 risk다 — 여기서 risk는 단계명이 아니라 보편적인 위험 탐지의 이진 정답이다.
- 평가 완료 500건, 오류 0건 (오류는 지표 분모에서 제외)
- 모델 임계값: depression ≥ 0.5, anxiety ≥ 0.5

## 전체 지표

- 정확도(accuracy): 0.6100
- macro F1: 0.6056

## 라벨별 지표

| 라벨 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| none | 0.7521 | 0.5683 | 0.6474 | 315 |
| risk | 0.4809 | 0.6811 | 0.5638 | 185 |

## 단계 기여 분해

최종 판정의 정답·오탐이 어느 단계에서 왔는지 분해한 것이다.

| 구분 | 건수 |
|---|---|
| 사전이 잡은 위험 | 110 |
| 모델 신호로 잡은 위험 (사전은 놓침) | 16 |
| 끝내 놓친 위험 | 59 |
| 사전이 만든 오탐 | 132 |
| 모델 신호가 만든 오탐 (사전은 none) | 4 |
| 맞게 비위험으로 둔 건 | 179 |

## 혼동행렬

행=정답, 열=예측.

| 정답 \ 예측 | none | risk |
|---|---|---|
| none | 179 | 136 |
| risk | 59 | 126 |

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
| b30-037 | none | risk |
| b30-039 | none | risk |
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
| b30-265 | none | risk |
| b30-266 | none | risk |
| b30-268 | none | risk |
| b30-269 | none | risk |
| b30-270 | none | risk |
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
| b30-002 | risk (위해) | none |
| b30-004 | risk (위해) | none |
| b30-013 | risk (우울) | none |
| b30-035 | risk (위해) | none |
| b30-038 | risk (위해) | none |
| b30-040 | risk (위해) | none |
| b30-041 | risk (위해) | none |
| b30-051 | risk (우울) | none |
| b30-063 | risk (위해) | none |
| b30-072 | risk (위해) | none |
| b30-073 | risk (위해) | none |
| b30-089 | risk (우울) | none |
| b30-102 | risk (우울) | none |
| b30-113 | risk (위해) | none |
| b30-119 | risk (위해) | none |
| b30-121 | risk (우울) | none |
| b30-122 | risk (위해) | none |
| b30-140 | risk (위해) | none |
| b30-142 | risk (우울) | none |
| b30-148 | risk (위해) | none |
| b30-152 | risk (위해) | none |
| b30-153 | risk (위해) | none |
| b30-159 | risk (불안) | none |
| b30-164 | risk (위해) | none |
| b30-193 | risk (불안) | none |
| b30-221 | risk (우울) | none |
| b30-235 | risk (위해) | none |
| b30-239 | risk (위해) | none |
| b30-240 | risk (위해) | none |
| b30-241 | risk (위해) | none |
| b30-247 | risk (위해) | none |
| b30-286 | risk (위해) | none |
| b30-287 | risk (불안) | none |
| b30-289 | risk (위해) | none |
| b30-299 | risk (불안) | none |
| b30-307 | risk (불안) | none |
| b30-313 | risk (위해) | none |
| b30-317 | risk (위해) | none |
| b30-328 | risk (우울) | none |
| b30-330 | risk (불안) | none |
| b30-335 | risk (위해) | none |
| b30-337 | risk (위해) | none |
| b30-338 | risk (위해) | none |
| b30-342 | risk (위해) | none |
| b30-385 | risk (위해) | none |
| b30-395 | risk (우울) | none |
| b30-396 | risk (위해) | none |
| b30-409 | risk (위해) | none |
| b30-418 | risk (위해) | none |
| b30-422 | risk (우울) | none |
| b30-423 | risk (위해) | none |
| b30-442 | risk (위해) | none |
| b30-443 | risk (위해) | none |
| b30-448 | risk (불안) | none |
| b30-454 | risk (불안) | none |
| b30-465 | risk (위해) | none |
| b30-476 | risk (위해) | none |
| b30-480 | risk (위해) | none |
| b30-491 | risk (위해) | none |
