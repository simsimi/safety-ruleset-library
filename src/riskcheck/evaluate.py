"""테스트셋 로딩, 판정 실행, 지표 계산.

판정 실행(run)과 채점(evaluate)을 나눈다: predictions 파일이 있으면 사전·모델을
다시 부르지 않고 채점만 할 수 있다.
"""
import json
import re
from collections import Counter
from pathlib import Path

from . import LABELS, to_binary
from .detector import DictDetector


def load_jsonl(path: str | Path) -> list[dict]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: str | Path, rows: list[dict]) -> None:
    Path(path).write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def run_detector(testset: list[dict], detector: DictDetector, source_version: str) -> list[dict]:
    """테스트셋 전체를 사전 단계로 판정해 predictions 행 목록을 만든다."""
    predictions = []
    for row in testset:
        try:
            result = detector.detect(row["text"])
            predictions.append({
                "id": row["id"], "stage": "dict", "source_version": source_version,
                "predicted": result["predicted"], "matches": result["matches"],
            })
        except Exception as e:  # 오류 건은 predicted=null로 남겨 분모에서 뺀다
            predictions.append({
                "id": row["id"], "stage": "dict", "source_version": source_version,
                "predicted": None, "matches": [], "error": f"{type(e).__name__}: {e}",
            })
    return predictions


def run_model(testset: list[dict], adapter, source_version: str) -> list[dict]:
    """테스트셋 전체를 모델 단계로 판정해 predictions 행 목록을 만든다.

    모델 행의 predicted는 None으로 둔다 — 판정은 채점 단계에서 임계값 정책으로
    점수로부터 도출하므로, 정책을 바꿔도 모델을 다시 부르지 않는다.
    """
    predictions = []
    for row in testset:
        try:
            scores = adapter.predict(row["text"], row["id"])
            predictions.append({
                "id": row["id"], "stage": "model", "source_version": source_version,
                "predicted": None, "matches": [], "scores": scores,
            })
        except Exception as e:  # 오류 건은 error로 남겨 분모에서 뺀다
            predictions.append({
                "id": row["id"], "stage": "model", "source_version": source_version,
                "predicted": None, "matches": [], "error": f"{type(e).__name__}: {e}",
            })
    return predictions


def run_harm_model(testset: list[dict], adapter, source_version: str) -> list[dict]:
    """테스트셋 전체를 위해 모델로 판정해 predictions 행 목록을 만든다 (stage="harm").

    감정 모델과 같은 원칙: 행의 predicted는 None으로 두고, 결합 판정은 채점
    단계에서 정책(confirm/standalone)으로 점수로부터 도출한다.
    """
    predictions = []
    for row in testset:
        try:
            scores = adapter.predict(row["text"], row["id"])
            predictions.append({
                "id": row["id"], "stage": "harm", "source_version": source_version,
                "predicted": None, "matches": [], "scores": {"harm": scores["harm"]},
            })
        except Exception as e:  # 오류 건은 error로 남겨 결합에서 폴백한다
            predictions.append({
                "id": row["id"], "stage": "harm", "source_version": source_version,
                "predicted": None, "matches": [], "error": f"{type(e).__name__}: {e}",
            })
    return predictions


def harm_decision(dict_label: str, harm: float | None, policy: dict) -> str | None:
    """위해 결합 판정: 사전 판정과 위해 확률을 정책으로 합친다.

    - 사전이 잡은 건: 위해 확률이 confirm 이상일 때만 risk로 확정한다.
    - 사전이 놓친 건: 위해 확률이 standalone 이상이면 risk로 올린다.
    - 위해 점수가 없으면(모델 오류 등) None을 돌려준다 — 호출자가 기존
      규칙(사전 판정 유지)으로 폴백한다.
    """
    if harm is None:
        return None
    if dict_label == "risk":
        return "risk" if harm >= policy["confirm"] else "none"
    return "risk" if harm >= policy["standalone"] else "none"


def evaluate_harm(testset: list[dict], harm_predictions: list[dict], policy: dict) -> dict:
    """위해 모델 단독 평가.

    본 리포트는 standalone 운용점 기준의 전체 지표이며, confirm 운용점의 이진
    지표를 harm_confirm_metrics에 참고로 함께 낸다.
    """
    def derived_at(t):
        derived = []
        for p in harm_predictions:
            if p.get("error") or "scores" not in p:
                derived.append({**p, "predicted": None,
                                "error": p.get("error", "scores 없음")})
            else:
                derived.append({**p, "predicted": "risk" if p["scores"]["harm"] >= t else "none"})
        return derived

    report = evaluate(testset, derived_at(policy["standalone"]), stage="harm")
    report["policy"] = dict(policy)
    report["harm_confirm_metrics"] = evaluate(
        testset, derived_at(policy["confirm"]), stage="harm")["binary_risk"]
    return report


def model_label(scores: dict, thresholds: dict) -> str:
    """모델 점수에 판정 정책을 적용한 판정.

    우울/불안 중 하나라도 임계값 이상이면 위험 신호로 보고 risk로 판정한다.
    정책에 margin이 있으면, 임계값을 넘는 신호라도 else보다 margin 이상
    크지 않으면 신호로 보지 않는다 — else를 '평온'으로 선언한 게이트형
    모델의 마진 판정을 재현하는 옵션이다.
    """
    margin = thresholds.get("margin")
    for key in ("depression", "anxiety"):
        if scores[key] < thresholds[key]:
            continue
        if margin is not None and scores[key] - scores["else"] < float(margin):
            continue
        return "risk"
    return "none"


def _derived_rows(model_predictions: list[dict], thresholds: dict) -> list[dict]:
    """모델 행(점수)에 정책을 적용해 채점 가능한 행으로 바꾼다."""
    derived = []
    for p in model_predictions:
        if p.get("error") or "scores" not in p:
            derived.append({**p, "predicted": None,
                            "error": p.get("error", "scores 없음")})
        else:
            derived.append({**p, "predicted": model_label(p["scores"], thresholds)})
    return derived


def _certainty_of(row: dict, axis: str) -> str:
    return (row.get("certainty") or {}).get(axis, "certain")


def sublabel_metrics(testset: list[dict], model_predictions: list[dict], thresholds: dict,
                     *, certain_only: bool = False) -> dict:
    """하위 라벨(우울/불안) 기준 지표. gold가 null인 항목은 그 클래스에서 제외한다.

    certain_only면 해당 축 certainty가 certain인 항목만으로 계산한다(참고 지표).
    """
    rows_by_id = {row["id"]: row for row in testset}
    gold_by_id = {row["id"]: (row.get("sublabels") or {}) for row in testset}
    scores_by_id = {p["id"]: p["scores"] for p in model_predictions
                    if not p.get("error") and "scores" in p}

    def metrics_for(pairs):
        return label_metrics(["pos" if g else "neg" for g, _ in pairs],
                             ["pos" if p else "neg" for _, p in pairs], "pos")

    def keep(i, *axes):
        return not certain_only or all(
            _certainty_of(rows_by_id[i], a) == "certain" for a in axes)

    result = {}
    for key in ("depression", "anxiety"):
        pairs = [(gold_by_id[i][key], scores_by_id[i][key] >= thresholds[key])
                 for i in scores_by_id
                 if gold_by_id.get(i, {}).get(key) is not None and keep(i, key)]
        result[key] = metrics_for(pairs)
    any_pairs = []
    for i in scores_by_id:
        gold = gold_by_id.get(i, {})
        dep, anx = gold.get("depression"), gold.get("anxiety")
        gold_any = True if (dep or anx) else (False if dep is False and anx is False else None)
        if gold_any is None or not keep(i, "depression", "anxiety"):
            continue
        pred_any = model_label(scores_by_id[i], thresholds) == "risk"
        any_pairs.append((gold_any, pred_any))
    result["any_signal"] = metrics_for(any_pairs)
    return result


def sublabel_counts(testset: list[dict], model_predictions: list[dict]) -> dict:
    """클래스별 평가 건수와 null 제외 건수 (모델 점수가 있는 항목 기준)."""
    gold_by_id = {row["id"]: (row.get("sublabels") or {}) for row in testset}
    scored = [p["id"] for p in model_predictions if not p.get("error") and "scores" in p]
    result = {}
    for key in ("depression", "anxiety"):
        labeled = sum(1 for i in scored if gold_by_id.get(i, {}).get(key) is not None)
        result[key] = {"labeled": labeled, "null_excluded": len(scored) - labeled}
    def gold_any_of(gold):
        dep, anx = gold.get("depression"), gold.get("anxiety")
        return True if (dep or anx) else (False if dep is False and anx is False else None)

    any_labeled = sum(1 for i in scored if gold_any_of(gold_by_id.get(i, {})) is not None)
    result["any_signal"] = {"labeled": any_labeled, "null_excluded": len(scored) - any_labeled}
    return result


def evaluate_model(testset: list[dict], model_predictions: list[dict], thresholds: dict) -> dict:
    """모델 단계 단독 평가. 이진 판정 지표와 하위 라벨(우울/불안) 지표를 함께 낸다."""
    report = evaluate(testset, _derived_rows(model_predictions, thresholds), stage="model")
    report["thresholds"] = dict(thresholds)
    if any((row.get("sublabels") or {}).get(k) is not None
           for row in testset for k in ("depression", "anxiety")):
        report["sublabel_metrics"] = sublabel_metrics(testset, model_predictions, thresholds)
        report["sublabel_counts"] = sublabel_counts(testset, model_predictions)
        if any(_certainty_of(row, k) != "certain"
               for row in testset for k in ("depression", "anxiety")):
            report["sublabel_metrics_certain"] = sublabel_metrics(
                testset, model_predictions, thresholds, certain_only=True)
    return report


def _contribution(testset: list[dict], dict_predictions: list[dict],
                  model_predictions: list[dict], combined: list[dict],
                  thresholds: dict, harm_predictions: list[dict] | None = None,
                  policy: dict | None = None, gold_of=None) -> dict:
    """단계 기여 분해: 최종 판정의 정답·오답이 어느 단계에서 왔는지 센다.

    모델 오류 건은 모델 기여 없이 사전 판정 기준으로 귀속한다. 위해 모델이
    있으면 귀속 순서가 결합 규칙과 같다: 사전(확인 통과) → 위해 단독 → 감정
    신호. 사전이 잡았으나 위해 확인에서 떨어진 건수는 dict_dropped_by_harm로
    따로 센다. 정답은 통합 채점과 같은 gold_of(기본은 위해 라벨)를 쓴다.
    """
    if gold_of is None:
        gold_by_id = {row["id"]: to_binary(row["label"]) for row in testset}
    else:
        gold_by_id = {row["id"]: gold_of(row) for row in testset}
    dict_by_id = {p["id"]: p for p in dict_predictions}
    model_by_id = {p["id"]: p for p in model_predictions}
    harm_by_id = {p["id"]: p for p in (harm_predictions or [])}
    counts = Counter()
    for c in combined:
        if c["predicted"] is None:
            continue
        i = c["id"]
        gold = gold_by_id[i]
        d_label = to_binary(dict_by_id[i]["predicted"])
        m = model_by_id.get(i)
        m_label = (model_label(m["scores"], thresholds)
                   if m is not None and not m.get("error") and "scores" in m else None)
        h = harm_by_id.get(i)
        harm = (h["scores"]["harm"] if h is not None and not h.get("error")
                and "scores" in h else None)
        h_label = harm_decision(d_label, harm, policy) if policy is not None else None
        final = c["predicted"]
        if d_label == "risk" and h_label == "none":
            counts["dict_dropped_by_harm"] += 1
        if h_label is not None:
            # 위해 결합이 적용된 건: 최종 판정을 만든 단계로 귀속한다
            if gold == "risk":
                if h_label == "risk":
                    counts["caught_by_dict" if d_label == "risk" else "caught_by_harm"] += 1
                elif final == "risk":
                    counts["caught_by_model"] += 1
                else:
                    counts["missed"] += 1
            else:
                if final == "risk":
                    if h_label == "risk":
                        counts["fp_from_dict" if d_label == "risk" else "fp_from_harm"] += 1
                    else:
                        counts["fp_from_model"] += 1
                else:
                    counts["clean_none"] += 1
        elif gold == "risk":
            if d_label == "risk":
                counts["caught_by_dict"] += 1
            elif final == "risk":
                counts["caught_by_model"] += 1
            else:
                counts["missed"] += 1
        else:
            if d_label == "risk":
                counts["fp_from_dict"] += 1
            elif final == "risk":
                counts["fp_from_model"] += 1
            else:
                counts["clean_none"] += 1
        if m_label is None and model_predictions:
            counts["model_errors"] += 1
        if harm is None and harm_predictions:
            counts["harm_errors"] += 1
    keys = ["caught_by_dict", "caught_by_model", "missed",
            "fp_from_dict", "fp_from_model", "clean_none", "model_errors"]
    if harm_predictions:
        keys += ["caught_by_harm", "fp_from_harm", "dict_dropped_by_harm", "harm_errors"]
    return {k: counts.get(k, 0) for k in keys}


def evaluate_combined(testset: list[dict], dict_predictions: list[dict],
                      model_predictions: list[dict] | None, thresholds: dict,
                      harm_predictions: list[dict] | None = None,
                      policy: dict | None = None) -> dict:
    """최종 판정 평가: 축별 결합 규칙을 순서대로 적용한다.

    위해 모델이 없을 때(기존 규칙): 사전 판정이 risk면 그대로, none이면 감정
    모델 신호로 risk까지 올린다.

    위해 모델이 있을 때: 먼저 위해 결합(사전 × 위해 확률, harm_decision)을
    적용하고, 거기서 risk가 되지 않은 건은 감정 모델 신호로 올린다. 위해
    모델 오류 건은 위해 결합을 건너뛰고 기존 규칙으로 평가한다.

    채점 정답은 combined_gold — 위해 라벨 또는 하위 라벨(우울/불안) 양성을
    risk로 본다. 단계별 리포트(dict/harm/model)는 각 단계의 판정 대상만으로
    채점하므로 이 정의를 쓰지 않는다.
    """
    dict_by_id = {p["id"]: p for p in dict_predictions}
    model_by_id = {p["id"]: p for p in (model_predictions or [])}
    harm_by_id = {p["id"]: p for p in (harm_predictions or [])}
    combined = []
    for row in testset:
        d = dict_by_id.get(row["id"])
        if d is None or d["predicted"] is None:
            combined.append({"id": row["id"], "stage": "combined", "predicted": None,
                             "matches": [], "error": (d or {}).get("error", "사전 결과 없음")})
            continue
        label = d["predicted"]
        h = harm_by_id.get(row["id"])
        if policy is not None and h is not None and not h.get("error") and "scores" in h:
            decided = harm_decision(label, h["scores"]["harm"], policy)
            if decided is not None:
                label = decided
        m = model_by_id.get(row["id"])
        if label == "none" and m is not None and not m.get("error") and "scores" in m:
            label = model_label(m["scores"], thresholds)
        combined.append({"id": row["id"], "stage": "combined",
                         "predicted": label, "matches": d["matches"]})
    report = evaluate(testset, combined, stage="combined", gold_of=combined_gold)
    report["gold_definition"] = (
        "risk = 위해 라벨이 risk이거나 하위 라벨(우울/불안) 중 하나라도 양성인 경우. "
        "여기서 risk는 단계명이 아니라 보편적인 위험 탐지의 이진 정답이며, "
        "하위 라벨이 없는 건은 위해 라벨만으로 정한다.")
    report["thresholds"] = dict(thresholds)
    if policy is not None:
        report["harm_policy"] = dict(policy)
    if model_predictions or harm_predictions:
        report["contribution"] = _contribution(
            testset, dict_predictions, model_predictions or [], combined, thresholds,
            harm_predictions, policy, gold_of=combined_gold)
    return report


def _rnd(x):
    return None if x is None else round(x, 4)


def label_metrics(gold: list[str], pred: list[str], label: str) -> dict:
    tp = sum(1 for g, p in zip(gold, pred) if g == label and p == label)
    fp = sum(1 for g, p in zip(gold, pred) if g != label and p == label)
    fn = sum(1 for g, p in zip(gold, pred) if g == label and p != label)
    support = sum(1 for g in gold if g == label)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    if precision and recall:
        f1 = 2 * precision * recall / (precision + recall)
    elif precision == 0.0 or recall == 0.0:
        f1 = 0.0
    else:
        f1 = None
    return {"precision": _rnd(precision), "recall": _rnd(recall), "f1": _rnd(f1), "support": support}


def _grade_summary(gold: list[str], pred: list[str]) -> dict:
    accuracy = (sum(1 for g, p in zip(gold, pred) if g == p) / len(gold)) if gold else None
    return {
        "n": len(gold),
        "accuracy": _rnd(accuracy),
        "binary_risk": label_metrics(
            ["risk" if g != "none" else "none" for g in gold],
            ["risk" if p != "none" else "none" for p in pred], "risk"),
    }


def _extra_sections(testset: list[dict], evaluated: list[dict], gold_by_id: dict) -> dict:
    """certainty 분리 집계와 소그룹 지표. 해당 데이터가 있을 때만 키를 만든다.

    주 지표는 전체 지표이며, certain-only는 참고용이다. ambiguous 건은 방향별로
    센다: 정답이 위험인데 none으로 놓치면 누락, 정답이 none인데 위험으로 잡으면 과탐.
    """
    rows_by_id = {row["id"]: row for row in testset}
    out = {}
    if any("certainty" in row for row in testset):
        dist = Counter(_certainty_of(row, "grade") for row in testset)
        cert_pairs = [(gold_by_id[p["id"]], p["predicted"]) for p in evaluated
                      if _certainty_of(rows_by_id[p["id"]], "grade") == "certain"]
        amb = [p for p in evaluated
               if _certainty_of(rows_by_id[p["id"]], "grade") == "ambiguous"]
        out["certainty_summary"] = {
            "counts": {k: dist.get(k, 0) for k in ("certain", "ambiguous", "needs_context")},
            "certain_only": _grade_summary([g for g, _ in cert_pairs],
                                           [p for _, p in cert_pairs]),
            "ambiguous_directional": {
                "n": len(amb),
                "correct": sum(1 for p in amb if p["predicted"] == gold_by_id[p["id"]]),
                "miss": sum(1 for p in amb if gold_by_id[p["id"]] != "none"
                            and p["predicted"] == "none"),
                "overcall": sum(1 for p in amb if gold_by_id[p["id"]] == "none"
                                and p["predicted"] != "none"),
            },
        }
    subgroups: dict[str, list[dict]] = {}
    for p in evaluated:
        m = re.search(r"subgroup:([a-z0-9_]+)", rows_by_id[p["id"]].get("note") or "")
        if m:
            subgroups.setdefault(m.group(1), []).append(p)
    if subgroups:
        sg = {}
        for name, ps in sorted(subgroups.items()):
            pos = [p for p in ps if gold_by_id[p["id"]] != "none"]
            neg = [p for p in ps if gold_by_id[p["id"]] == "none"]
            det = sum(1 for p in pos if p["predicted"] != "none")
            fp = sum(1 for p in neg if p["predicted"] != "none")
            sg[name] = {"n": len(ps), "positives": len(pos), "detected": det,
                        "detection_rate": _rnd(det / len(pos)) if pos else None,
                        "negatives": len(neg), "false_positives": fp,
                        "fp_rate": _rnd(fp / len(neg)) if neg else None}
        out["subgroup_metrics"] = sg
    return out


def combined_gold(row: dict) -> str:
    """통합 채점의 정답: 위해 라벨이 risk이거나 하위 라벨(우울/불안) 중 하나라도
    양성이면 risk, 아니면 none이다.

    여기서 risk는 안전모드 같은 단계명이 아니라 보편적인 '위험 탐지'의
    이진 정답이다 — 단어에서 걸리면 경고, 모델에서 우울/불안에 걸리면
    주의로 보되, 경고·주의 모두 위험 탐지로 치는 판정 규칙과 짝을 이룬다.
    하위 라벨이 없는(null) 건은 위해 라벨만으로 정한다.
    """
    if to_binary(row["label"]) != "none":
        return "risk"
    sub = row.get("sublabels") or {}
    if sub.get("depression") or sub.get("anxiety"):
        return "risk"
    return "none"


def gold_basis(row: dict) -> str:
    """통합 채점에서 정답 risk의 근거: 위해 라벨이면 harm, 아니면 양성인
    하위 라벨 이름(depression/anxiety/둘 다), 정답이 none이면 none."""
    if to_binary(row["label"]) != "none":
        return "harm"
    sub = row.get("sublabels") or {}
    keys = [k for k in ("depression", "anxiety") if sub.get(k)]
    return "+".join(keys) if keys else "none"


def _case(p: dict, gold_by_id: dict, gold_of, rows_by_id: dict) -> dict:
    """오답 사례 항목. gold_of가 있는 채점(통합)에서는 정답 근거(gold_basis)를
    함께 적어, risk 정답이 위해 라벨인지 하위 라벨 양성인지 구분한다."""
    case = {"id": p["id"], "gold": gold_by_id[p["id"]], "predicted": p["predicted"]}
    if gold_of is not None:
        case["gold_basis"] = gold_basis(rows_by_id[p["id"]])
    return case


def evaluate(testset: list[dict], predictions: list[dict], *, stage: str = "dict",
             gold_of=None) -> dict:
    """테스트셋 정답과 predictions를 id로 연결해 리포트 dict를 만든다.

    채점은 위험/비위험 이진으로 한다. 정답 라벨이 등급(danger/emergency)으로
    붙어 있어도, 구 형식 predictions의 등급 예측도 risk로 접어 계산한다.
    gold_of를 주면 정답 계산을 그 함수로 바꾼다 (통합 채점의 combined_gold).
    """
    predictions = [{**p, "predicted": to_binary(p["predicted"])} for p in predictions]
    if gold_of is None:
        gold_by_id = {row["id"]: to_binary(row["label"]) for row in testset}
    else:
        gold_by_id = {row["id"]: gold_of(row) for row in testset}
    missing = [row["id"] for row in testset if row["id"] not in {p["id"] for p in predictions}]
    if missing:
        raise ValueError(f"predictions에 없는 테스트셋 id: {missing[:5]}")

    evaluated = [p for p in predictions if p["predicted"] is not None]
    error_cases = [{"id": p["id"], "error": p.get("error", "unknown")}
                   for p in predictions if p["predicted"] is None]
    gold = [gold_by_id[p["id"]] for p in evaluated]
    pred = [p["predicted"] for p in evaluated]

    per_label = {label: label_metrics(gold, pred, label) for label in LABELS}
    accuracy = (sum(1 for g, p in zip(gold, pred) if g == p) / len(gold)) if gold else None
    f1s = [per_label[l]["f1"] for l in LABELS if per_label[l]["f1"] is not None]
    macro_f1 = sum(f1s) / len(f1s) if f1s else None
    binary = label_metrics(
        ["risk" if g != "none" else "none" for g in gold],
        ["risk" if p != "none" else "none" for p in pred],
        "risk",
    )
    confusion = [[sum(1 for g, p in zip(gold, pred) if g == gl and p == pl) for pl in LABELS]
                 for gl in LABELS]
    rows_by_id = {r["id"]: r for r in testset}

    report = {
        "schema_version": "0.1",
        "stage": stage,
        "counts": {"total": len(predictions), "evaluated": len(evaluated), "errors": len(error_cases)},
        "overall": {"accuracy": _rnd(accuracy), "macro_f1": _rnd(macro_f1)},
        "per_label": per_label,
        "binary_risk": binary,
        "confusion": {"labels": list(LABELS), "matrix": confusion},
        "false_positives": [_case(p, gold_by_id, gold_of, rows_by_id)
                            for p in evaluated
                            if p["predicted"] != "none" and gold_by_id[p["id"]] == "none"],
        "false_negatives": [_case(p, gold_by_id, gold_of, rows_by_id)
                            for p in evaluated
                            if gold_by_id[p["id"]] != "none" and p["predicted"] == "none"],
        "error_cases": error_cases,
    }
    report.update(_extra_sections(testset, evaluated, gold_by_id))
    if stage == "dict":
        stats = _pattern_stats(evaluated, gold_by_id)
        if stats:
            report["pattern_stats"] = stats
    return report


def _pattern_stats(evaluated: list[dict], gold_by_id: dict) -> list[dict]:
    """사전 단계 전용: 패턴별 매칭 건수와 그중 오탐(정답 none) 건수.

    사전 튜닝의 근거다 — 자주 걸리는데 오탐이 많은 패턴부터 다듬는다.
    matches가 없는 predictions(재채점 등)에서는 빈 목록을 돌려준다.
    """
    hits: Counter = Counter()
    fp_hits: Counter = Counter()
    for p in evaluated:
        for pattern_id in {m["pattern_id"] for m in p.get("matches") or []}:
            hits[pattern_id] += 1
            if gold_by_id[p["id"]] == "none":
                fp_hits[pattern_id] += 1
    return [{"pattern_id": pid, "hits": n, "fp_hits": fp_hits.get(pid, 0)}
            for pid, n in hits.most_common()]
