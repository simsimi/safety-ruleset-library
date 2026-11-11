"""riskcheck 콘솔 명령.

  riskcheck evaluate --dataset data/testset.jsonl --dict dicts/default.yaml --out runs/v1
  riskcheck evaluate --dataset data/evalset_human.jsonl --dict dicts/default.yaml \
      --model-config models/stub.yaml --out runs/v2
  riskcheck evaluate --dataset data/evalset_human.jsonl \
      --predictions runs/v2/predictions.jsonl --threshold-anxiety 0.3 --out runs/v2-rescore
  riskcheck detect   --dict dicts/default.yaml "요즘 진짜 죽고 싶어"
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .detector import DictDetector
from .dictionary import load_dictionary
from .evaluate import (evaluate, evaluate_combined, evaluate_harm, evaluate_model,
                       load_jsonl, run_detector, run_harm_model, run_model, write_jsonl)
from .model import (build_adapter, build_harm_adapter, harm_policy, load_model_config,
                    model_thresholds)
from .report import render_html, render_markdown, summary_text


def _write_report(out: Path, stem: str, report: dict, *, dataset_name: str,
                  source_label: str, source_name: str, source_version: str) -> None:
    (out / f"{stem}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / f"{stem}.md").write_text(
        render_markdown(report, dataset_name=dataset_name, dictionary_name=source_name,
                        dictionary_version=source_version, source_label=source_label),
        encoding="utf-8")
    (out / f"{stem}.html").write_text(
        render_html(report, dataset_name=dataset_name, source_label=source_label,
                    source_name=source_name, source_version=source_version),
        encoding="utf-8")
    print(summary_text(report))
    print()


def _default_config(filename: str) -> dict | None:
    """기본 모델 설정을 찾는다.

    패키지와 함께 제공되는 models/<filename>이 있고 그 설정이 가리키는
    모델 경로가 실제로 있을 때만 설정 dict를 돌려준다 (경로는 레포 루트 기준으로
    절대화한다). 모델 파일이 준비되지 않았으면 None이다.
    """
    root = Path(__file__).resolve().parents[2]
    config_path = root / "models" / filename
    if not config_path.exists():
        return None
    config = load_model_config(config_path)
    local = config.get("local") or {}
    model_path = Path(local.get("path", ""))
    if not model_path.is_absolute():
        model_path = root / model_path
    if not model_path.exists():
        return None
    local["path"] = str(model_path)
    config["local"] = local
    return config


def _default_model_config() -> dict | None:
    """기본 감정 모델 설정 (models/default-emotion.yaml)."""
    return _default_config("default-emotion.yaml")


def _default_harm_config() -> dict | None:
    """기본 위해 모델 설정 (models/default-harm.yaml)."""
    return _default_config("default-harm.yaml")


def _cmd_evaluate(args) -> int:
    all_testset = load_jsonl(args.dataset)
    testset = all_testset
    if args.exclude_tag:
        testset = [r for r in all_testset if args.exclude_tag not in (r.get("note") or "")]
        print(f"태그 '{args.exclude_tag}' 항목 {len(all_testset) - len(testset)}건 채점에서 제외 "
              f"({len(testset)}건 평가)")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dataset_info = {"name": Path(args.dataset).name, "count": len(testset)}

    # 감정 모델은 기본 구성(필수)이다: 지정이 없으면 기본 모델 설정을 자동 적용한다.
    model_config = load_model_config(args.model_config) if args.model_config else {}
    use_model = bool(args.model_config)
    if not args.model_config and not args.predictions:
        default_config = _default_model_config()
        if default_config is not None:
            model_config, use_model = default_config, True
            print("감정 모델 미지정 — 기본 모델(models/default-emotion.yaml)을 적용합니다")
        else:
            print("경고: 감정 모델이 연결되지 않았습니다. 기본 구성은 사전+감정 모델이며, "
                  "기본 모델이 없으면 tools/download_models.py로 내려받거나 "
                  "--model-config로 지정하세요.", file=sys.stderr)
    overrides = {"depression": args.threshold_depression, "anxiety": args.threshold_anxiety,
                 "margin": args.margin}
    thresholds = model_thresholds(model_config, overrides)

    # 위해 모델도 기본 구성이다: 지정이 없으면 기본 모델 설정을 자동 적용한다.
    # 모델 파일이 준비되지 않은 환경에서는 위해 단계 없이 평가한다.
    harm_config = load_model_config(args.harm_model_config) if args.harm_model_config else {}
    use_harm = bool(args.harm_model_config)
    if not args.harm_model_config and not args.predictions:
        default_harm = _default_harm_config()
        if default_harm is not None:
            harm_config, use_harm = default_harm, True
            print("위해 모델 미지정 — 기본 모델(models/default-harm.yaml)을 적용합니다")
    policy = (harm_policy(harm_config, {"confirm": args.harm_confirm,
                                         "standalone": args.harm_standalone})
              if use_harm or args.harm_confirm is not None
              or args.harm_standalone is not None else None)

    if args.predictions:
        # 채점 전용: 저장된 단계별 결과를 읽어 정책만 적용한다 (모델 재호출 없음)
        all_rows = load_jsonl(args.predictions)
        dict_rows = [r for r in all_rows if r["stage"] == "dict"]
        model_rows = [r for r in all_rows if r["stage"] == "model"]
        harm_rows = [r for r in all_rows if r["stage"] == "harm"]
        if harm_rows and policy is None:
            policy = harm_policy({})
        if not dict_rows:
            print("predictions에 dict 단계 결과가 없다", file=sys.stderr)
            return 2
        dict_name = dict_version = "(저장된 결과)"
        model_name = model_rows[0].get("source_version", "?") if model_rows else None
        harm_name = harm_rows[0].get("source_version", "?") if harm_rows else None
    else:
        if not args.dict:
            print("--dict가 필요하다 (--predictions로 채점 전용 모드를 쓰지 않는 경우)", file=sys.stderr)
            return 2
        dictionary = load_dictionary(args.dict)
        dict_rows = run_detector(testset, DictDetector(dictionary), dictionary.version)
        dict_name, dict_version = dictionary.name, dictionary.version
        model_rows, model_name = [], None
        if use_model:
            adapter = build_adapter(model_config)
            model_rows = run_model(testset, adapter, adapter.version)
            model_name = f"{model_config['adapter']} 어댑터"
        harm_rows, harm_name = [], None
        if use_harm:
            harm_adapter = build_harm_adapter(harm_config)
            harm_rows = run_harm_model(testset, harm_adapter, harm_adapter.version)
            harm_name = f"{harm_config['adapter']} 위해 어댑터"
        write_jsonl(out / "predictions.jsonl", dict_rows + model_rows + harm_rows)

    report = evaluate(testset, dict_rows, stage="dict")
    report.update({"generated_at": now, "dataset": dataset_info,
                   "dictionary": {"name": dict_name, "version": dict_version}})
    _write_report(out, "report_dict", report, dataset_name=dataset_info["name"],
                  source_label="사전", source_name=dict_name, source_version=dict_version)

    if model_rows:
        m_report = evaluate_model(testset, model_rows, thresholds)
        m_report.update({"generated_at": now, "dataset": dataset_info,
                         "model": {"name": model_name or "model",
                                   "version": model_rows[0].get("source_version", "?")}})
        _write_report(out, "report_model", m_report, dataset_name=dataset_info["name"],
                      source_label="모델", source_name=m_report["model"]["name"],
                      source_version=m_report["model"]["version"])

    if harm_rows:
        h_report = evaluate_harm(testset, harm_rows, policy)
        h_report.update({"generated_at": now, "dataset": dataset_info,
                         "harm_model": {"name": harm_name or "harm-model",
                                        "version": harm_rows[0].get("source_version", "?")}})
        _write_report(out, "report_harm", h_report, dataset_name=dataset_info["name"],
                      source_label="위해 모델", source_name=h_report["harm_model"]["name"],
                      source_version=h_report["harm_model"]["version"])

    if model_rows or harm_rows:
        c_report = evaluate_combined(testset, dict_rows, model_rows or None, thresholds,
                                     harm_rows or None, policy)
        c_report.update({"generated_at": now, "dataset": dataset_info,
                         "dictionary": {"name": dict_name, "version": dict_version}})
        if model_rows:
            c_report["model"] = {"name": model_name or "model",
                                 "version": model_rows[0].get("source_version", "?")}
        if harm_rows:
            c_report["harm_model"] = {"name": harm_name or "harm-model",
                                      "version": harm_rows[0].get("source_version", "?")}
        _write_report(out, "report_combined", c_report, dataset_name=dataset_info["name"],
                      source_label="통합", source_name=dict_name,
                      source_version=dict_version)

    stems = ["report_dict"] + (["report_model"] if model_rows else []) \
        + (["report_harm"] if harm_rows else []) \
        + (["report_combined"] if (model_rows or harm_rows) else [])
    files = [f"{s}.html" for s in stems] + [f"{s}.md" for s in stems] + [f"{s}.json" for s in stems]
    if not args.predictions:
        files.append("predictions.jsonl")
    print(f"-> 결과 파일: {out}/")
    print("   " + ", ".join(files))
    return 0


def _cmd_detect(args) -> int:
    dictionary = load_dictionary(args.dict)
    result = DictDetector(dictionary).detect(" ".join(args.text))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="riskcheck", description="한국어 위험 표현 판별 테스트 도구")
    sub = parser.add_subparsers(dest="command", required=True)

    p_eval = sub.add_parser("evaluate", help="테스트셋을 판정하고 단계별·통합 리포트를 만든다")
    p_eval.add_argument("--dataset", required=True, help="테스트셋 JSONL 경로")
    p_eval.add_argument("--dict", help="사전 YAML 경로 (채점 전용 모드에서는 생략 가능)")
    p_eval.add_argument("--model-config", help="감정 모델 설정 YAML 경로 (adapter/thresholds)")
    p_eval.add_argument("--harm-model-config", help="위해 모델 설정 YAML 경로 (옵션, adapter/policy)")
    p_eval.add_argument("--harm-confirm", type=float, help="위해 결합 정책 재정의: 사전 포착 확정 임계값 (재채점용)")
    p_eval.add_argument("--harm-standalone", type=float, help="위해 결합 정책 재정의: 위해 모델 단독 승격 임계값 (재채점용)")
    p_eval.add_argument("--predictions", help="저장된 predictions JSONL — 실행 없이 채점만 한다")
    p_eval.add_argument("--threshold-depression", type=float, help="우울 임계값 재정의 (재채점용)")
    p_eval.add_argument("--threshold-anxiety", type=float, help="불안 임계값 재정의 (재채점용)")
    p_eval.add_argument("--margin", type=float, help="마진 정책 재정의 (신호가 else보다 이 값 이상 커야 신호로 본다, 재채점용)")
    p_eval.add_argument("--exclude-tag", help="note에 이 태그가 있는 항목을 채점에서 제외 (예: robustness)")
    p_eval.add_argument("--out", required=True, help="출력 폴더")
    p_eval.set_defaults(func=_cmd_evaluate)

    p_det = sub.add_parser("detect", help="발화 하나를 사전 단계로 판정한다")
    p_det.add_argument("--dict", required=True, help="사전 YAML 경로")
    p_det.add_argument("text", nargs="+", help="발화")
    p_det.set_defaults(func=_cmd_detect)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
