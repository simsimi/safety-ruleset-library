"""리포트 렌더링: report dict -> 콘솔 요약 / MD / HTML."""
import html as _html

from . import LABELS


def _fmt(x) -> str:
    return "-" if x is None else f"{x:.4f}"


def _is_model_focus(report: dict) -> bool:
    """모델 단계 리포트를 하위 라벨 중심으로 구성할지 (하위 라벨 지표가 있을 때)."""
    return report["stage"] == "model" and bool(report.get("sublabel_metrics"))


def summary_text(report: dict) -> str:
    counts = report["counts"]
    lines = [
        f"stage={report['stage']}  total={counts['total']}  evaluated={counts['evaluated']}  errors={counts['errors']}",
    ]
    if _is_model_focus(report):
        # 모델 단계의 본체는 하위 라벨 지표다. 파생 판정은 참고 한 줄로 둔다.
        lines.append("")
        for key, name in (("depression", "우울"), ("anxiety", "불안"), ("any_signal", "신호합산")):
            m = report["sublabel_metrics"][key]
            lines.append(f"{name:<10} {_fmt(m['precision']):>10} {_fmt(m['recall']):>10} "
                         f"{_fmt(m['f1']):>10} {m['support']:>8}")
        b = report["binary_risk"]
        lines.append(f"참고(파생 판정)  accuracy={_fmt(report['overall']['accuracy'])}  "
                     f"risk P={_fmt(b['precision'])} R={_fmt(b['recall'])}")
        return "\n".join(lines)
    lines.append(f"accuracy={_fmt(report['overall']['accuracy'])}  macro_f1={_fmt(report['overall']['macro_f1'])}")
    lines.append("")
    lines.append(f"{'label':<10} {'precision':>10} {'recall':>10} {'f1':>10} {'support':>8}")
    for label in LABELS:
        m = report["per_label"][label]
        lines.append(f"{label:<10} {_fmt(m['precision']):>10} {_fmt(m['recall']):>10} "
                     f"{_fmt(m['f1']):>10} {m['support']:>8}")
    if report.get("sublabel_metrics"):
        lines.append("")
        for key, name in (("depression", "우울"), ("anxiety", "불안"), ("any_signal", "신호합산")):
            m = report["sublabel_metrics"][key]
            lines.append(f"{name:<10} {_fmt(m['precision']):>10} {_fmt(m['recall']):>10} "
                         f"{_fmt(m['f1']):>10} {m['support']:>8}")
    if report.get("contribution"):
        c = report["contribution"]
        lines.append(f"기여 분해  사전 포착 {c['caught_by_dict']} · 모델 포착 {c['caught_by_model']} · "
                     f"미탐 {c['missed']} · 사전 오탐 {c['fp_from_dict']} · 모델 오탐 {c['fp_from_model']}")
        if "caught_by_harm" in c:
            lines.append(f"위해 모델  단독 포착 {c['caught_by_harm']} · 위해 오탐 {c['fp_from_harm']} · "
                         f"사전 포착 중 위해 확인 탈락 {c['dict_dropped_by_harm']}"
                         + (f" · 위해 모델 오류 {c['harm_errors']}" if c.get("harm_errors") else ""))
    if report.get("certainty_summary"):
        co = report["certainty_summary"]["certain_only"]
        lines.append(f"certain-only  accuracy={_fmt(co['accuracy'])}  "
                     f"risk_recall={_fmt(co['binary_risk']['recall'])}  (n={co['n']}, 참고용)")
    if report.get("pattern_stats"):
        top = report["pattern_stats"][:5]
        lines.append("패턴 상위: " + ", ".join(
            f"{s['pattern_id']} {s['hits']}건(오탐 {s['fp_hits']})" for s in top))
    return "\n".join(lines)


_BASIS_LABELS = {"harm": "위해", "depression": "우울", "anxiety": "불안",
                 "depression+anxiety": "우울+불안", "none": ""}


def _gold_label(case: dict) -> str:
    """사례 표의 정답 표기. gold_basis가 있으면 근거를 병기한다 (예: risk (우울))."""
    basis = case.get("gold_basis")
    label = _BASIS_LABELS.get(basis, "") if basis else ""
    return f"{case['gold']} ({label})" if label else case["gold"]


_STAGE_NOTES = {
    "dict": "패턴이 하나라도 걸리면 risk, 없으면 none이다. 사전 패턴에 등급은 없다. "
            "정답 라벨이 등급(danger/emergency)으로 붙은 테스트셋은 채점할 때 risk로 접는다.",
    "model": "모델은 우울/불안 점수만 낸다. 이 표의 판정은 점수에 임계값 정책을 적용한 "
             "것으로, 신호가 있으면 risk다. 모델 자체의 성능은 하위 라벨 지표로 본다.",
    "combined": "1단계(사전+위해 모델 결합)가 risk면 그대로 확정하고, none일 때만 "
                "2단계(감정 모델) 신호로 risk까지 올린다. 정답은 위해 라벨이 risk이거나 "
                "하위 라벨(우울/불안) 중 하나라도 양성이면 risk다 — 여기서 risk는 단계명이 "
                "아니라 보편적인 위험 탐지의 이진 정답이다.",
    "harm": "위해 모델은 위해 확률 하나만 낸다. 이 표의 판정은 단독 승격 임계값(standalone) "
            "기준이며, 사전과의 결합 판정은 통합 단계에서 정책(confirm/standalone)으로 한다.",
}


def render_markdown(report: dict, *, dataset_name: str, dictionary_name: str,
                    dictionary_version: str, source_label: str = "사전") -> str:
    counts = report["counts"]
    lines = [
        "# 위험판별 평가 리포트",
        "",
        f"- 테스트셋: {dataset_name} ({counts['total']}건)",
        f"- {source_label}: {dictionary_name} {dictionary_version}",
        f"- 평가 단계: {report['stage']}",
        f"- 판정 방식: {_STAGE_NOTES[report['stage']]}",
        f"- 평가 완료 {counts['evaluated']}건, 오류 {counts['errors']}건 (오류는 지표 분모에서 제외)",
    ]
    if report.get("thresholds"):
        t = report["thresholds"]
        lines.append(f"- 모델 임계값: depression ≥ {t['depression']}, anxiety ≥ {t['anxiety']}")
    if _is_model_focus(report):
        return _render_markdown_model(report, lines)
    lines += [
        "",
        "## 전체 지표",
        "",
        f"- 정확도(accuracy): {_fmt(report['overall']['accuracy'])}",
        f"- macro F1: {_fmt(report['overall']['macro_f1'])}",
        "",
        "## 라벨별 지표",
        "",
        "| 라벨 | Precision | Recall | F1 | Support |",
        "|---|---|---|---|---|",
    ]
    for label in LABELS:
        m = report["per_label"][label]
        lines.append(f"| {label} | {_fmt(m['precision'])} | {_fmt(m['recall'])} | "
                     f"{_fmt(m['f1'])} | {m['support']} |")

    if report.get("contribution"):
        c = report["contribution"]
        lines += ["", "## 단계 기여 분해", "",
                  "최종 판정의 정답·오탐이 어느 단계에서 왔는지 분해한 것이다.", "",
                  "| 구분 | 건수 |", "|---|---|",
                  f"| 사전이 잡은 위험 | {c['caught_by_dict']} |",
                  f"| 모델 신호로 잡은 위험 (사전은 놓침) | {c['caught_by_model']} |",
                  f"| 끝내 놓친 위험 | {c['missed']} |",
                  f"| 사전이 만든 오탐 | {c['fp_from_dict']} |",
                  f"| 모델 신호가 만든 오탐 (사전은 none) | {c['fp_from_model']} |",
                  f"| 맞게 비위험으로 둔 건 | {c['clean_none']} |"]
        if "caught_by_harm" in c:
            lines += [f"| 위해 모델이 단독으로 잡은 위험 (사전은 놓침) | {c['caught_by_harm']} |",
                      f"| 위해 모델이 만든 오탐 | {c['fp_from_harm']} |",
                      f"| 사전이 잡았으나 위해 확인에서 떨어진 건 | {c['dict_dropped_by_harm']} |"]
            if c.get("harm_errors"):
                lines.append(f"| 위해 모델 오류로 기존 규칙으로 평가한 건 | {c['harm_errors']} |")
        if c["model_errors"]:
            lines.append(f"| 모델 오류로 사전 판정만으로 평가한 건 | {c['model_errors']} |")

    if report.get("certainty_summary"):
        cs = report["certainty_summary"]
        co, ad = cs["certain_only"], cs["ambiguous_directional"]
        lines += ["", "## 확실성(certainty) 분리 지표", "",
                  "주 지표는 위 전체 지표다. certain-only는 참고용이며, ambiguous 건은 방향별로 센다.",
                  "",
                  f"- certainty 분포: certain {cs['counts']['certain']}건, "
                  f"ambiguous {cs['counts']['ambiguous']}건, needs_context {cs['counts']['needs_context']}건",
                  f"- certain-only ({co['n']}건): 정확도 {_fmt(co['accuracy'])}, "
                  f"위험 Precision {_fmt(co['binary_risk']['precision'])}, "
                  f"Recall {_fmt(co['binary_risk']['recall'])}, F1 {_fmt(co['binary_risk']['f1'])}",
                  f"- ambiguous ({ad['n']}건): 정답 {ad['correct']}건, 누락(위험→none) {ad['miss']}건, "
                  f"과탐(none→위험) {ad['overcall']}건"]

    if report.get("subgroup_metrics"):
        lines += ["", "## 소그룹 지표", "",
                  "| 소그룹 | 건수 | 위험 정답 | 탐지 | 탐지율 | none 정답 | 오탐 | FP율 |",
                  "|---|---|---|---|---|---|---|---|"]
        for name, m in report["subgroup_metrics"].items():
            lines.append(f"| {name} | {m['n']} | {m['positives']} | {m['detected']} | "
                         f"{_fmt(m['detection_rate'])} | {m['negatives']} | {m['false_positives']} | "
                         f"{_fmt(m['fp_rate'])} |")

    if report.get("sublabel_metrics"):
        names = {"depression": "우울", "anxiety": "불안", "any_signal": "합산 (둘 중 하나)"}
        lines += ["", "## 하위 라벨 지표 (우울/불안)", "",
                  "테스트셋 sublabels 기준. null인 항목은 제외한다.", "",
                  "| 신호 | Precision | Recall | F1 | Support |", "|---|---|---|---|---|"]
        for key in ("depression", "anxiety", "any_signal"):
            m = report["sublabel_metrics"][key]
            lines.append(f"| {names[key]} | {_fmt(m['precision'])} | {_fmt(m['recall'])} | "
                         f"{_fmt(m['f1'])} | {m['support']} |")
        if report.get("sublabel_counts"):
            sc = report["sublabel_counts"]
            lines.append("")
            lines.append("제외(null) 건수: " + ", ".join(
                f"{names[k]} {sc[k]['null_excluded']}건 (평가 {sc[k]['labeled']}건)"
                for k in ("depression", "anxiety", "any_signal")))
        if report.get("sublabel_metrics_certain"):
            lines += ["", "certain-only 하위 라벨 지표 (참고용):", "",
                      "| 신호 | Precision | Recall | F1 | Support |", "|---|---|---|---|---|"]
            for key in ("depression", "anxiety", "any_signal"):
                m = report["sublabel_metrics_certain"][key]
                lines.append(f"| {names[key]} | {_fmt(m['precision'])} | {_fmt(m['recall'])} | "
                             f"{_fmt(m['f1'])} | {m['support']} |")

    lines += ["", "## 혼동행렬", "", "행=정답, 열=예측.", "",
              "| 정답 \\ 예측 | " + " | ".join(LABELS) + " |",
              "|---|" + "---|" * len(LABELS)]
    for label, row in zip(LABELS, report["confusion"]["matrix"]):
        lines.append(f"| {label} | " + " | ".join(str(v) for v in row) + " |")

    if report.get("pattern_stats"):
        lines += ["", "## 패턴 매칭 통계", "",
                  "패턴별 매칭 건수와, 그중 정답이 none인 오탐 매칭 건수다. "
                  "자주 걸리는데 오탐이 많은 패턴부터 다듬는다.", "",
                  "| 패턴 | 매칭 | 오탐 매칭 |", "|---|---|---|"]
        lines += [f"| {s['pattern_id']} | {s['hits']} | {s['fp_hits']} |"
                  for s in report["pattern_stats"]]

    for title, key in (("## 오탐 (위험 아님을 위험으로 판정)", "false_positives"),
                       ("## 미탐 (위험을 놓침)", "false_negatives")):
        cases = report[key]
        lines += ["", title, ""]
        if not cases:
            lines.append("없음")
        else:
            lines += ["| id | 정답 | 예측 |", "|---|---|---|"]
            lines += [f"| {c['id']} | {_gold_label(c)} | {c['predicted']} |" for c in cases]

    if report["error_cases"]:
        lines += ["", "## 판정 오류", "", "| id | 사유 |", "|---|---|"]
        lines += [f"| {c['id']} | {c['error']} |" for c in report["error_cases"]]
    lines.append("")
    return "\n".join(lines)


def _render_markdown_model(report: dict, lines: list[str]) -> str:
    """모델 단계 전용 구성: 본체는 하위 라벨 지표, 등급 파생 판정은 참고로만 둔다."""
    names = {"depression": "우울", "anxiety": "불안", "any_signal": "합산 (둘 중 하나)"}
    lines += ["", "## 하위 라벨 지표 (우울/불안)", "",
              "모델 단계의 본체 지표다. 테스트셋 sublabels 기준이며, null인 항목은 제외한다.", "",
              "| 신호 | Precision | Recall | F1 | Support |", "|---|---|---|---|---|"]
    for key in ("depression", "anxiety", "any_signal"):
        m = report["sublabel_metrics"][key]
        lines.append(f"| {names[key]} | {_fmt(m['precision'])} | {_fmt(m['recall'])} | "
                     f"{_fmt(m['f1'])} | {m['support']} |")
    if report.get("sublabel_counts"):
        sc = report["sublabel_counts"]
        lines.append("")
        lines.append("제외(null) 건수: " + ", ".join(
            f"{names[k]} {sc[k]['null_excluded']}건 (평가 {sc[k]['labeled']}건)"
            for k in ("depression", "anxiety", "any_signal")))
    if report.get("sublabel_metrics_certain"):
        lines += ["", "certain-only 하위 라벨 지표 (참고용):", "",
                  "| 신호 | Precision | Recall | F1 | Support |", "|---|---|---|---|---|"]
        for key in ("depression", "anxiety", "any_signal"):
            m = report["sublabel_metrics_certain"][key]
            lines.append(f"| {names[key]} | {_fmt(m['precision'])} | {_fmt(m['recall'])} | "
                         f"{_fmt(m['f1'])} | {m['support']} |")
    b = report["binary_risk"]
    lines += ["", "## 참고: 임계값 파생 판정", "",
              "점수에 임계값을 적용해 위험/비위험으로 접은 값이다. 정답(자살·자해 위험)과 "
              "모델 신호(우울·불안)는 다른 구성개념이라 이 수치가 낮아도 모델이 나쁜 것은 아니다.", "",
              f"- 정확도: {_fmt(report['overall']['accuracy'])}",
              f"- 위험 Precision / Recall / F1: {_fmt(b['precision'])} / "
              f"{_fmt(b['recall'])} / {_fmt(b['f1'])} (support {b['support']})"]
    if report["error_cases"]:
        lines += ["", "## 판정 오류", "", "| id | 사유 |", "|---|---|"]
        lines += [f"| {c['id']} | {c['error']} |" for c in report["error_cases"]]
    lines.append("")
    return "\n".join(lines)


_STAGE_NAMES = {"dict": "사전 단계", "model": "모델 단계", "harm": "위해 모델 단계",
                "combined": "통합 판정"}

_HTML_CSS = """
:root { --ink:#16233a; --sub:#5a6a84; --line:#dfe5ee; --accent:#1e4a73;
        --soft:#f4f6fa; --diag:#e8eff7; }
* { box-sizing:border-box; }
body { margin:0; background:#eef1f5; color:var(--ink);
       font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic",
       "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
       font-size:15px; line-height:1.55; }
.page { max-width:940px; margin:0 auto; padding:40px 20px 56px; }
header { background:#fff; border:1px solid var(--line); border-top:4px solid var(--accent);
         padding:28px 32px 24px; }
.eyebrow { font-size:12px; letter-spacing:.14em; color:var(--accent); font-weight:700; }
h1 { font-size:24px; margin:6px 0 4px; font-weight:700; }
.stage { display:inline-block; margin-top:8px; padding:2px 10px; border:1px solid var(--accent);
         color:var(--accent); border-radius:999px; font-size:12.5px; font-weight:600; }
.meta { display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));
        gap:10px 28px; margin-top:20px; }
.meta div { border-top:1px solid var(--line); padding-top:8px; }
.meta dt { font-size:12px; color:var(--sub); }
.meta dd { margin:2px 0 0; font-weight:600; }
section { background:#fff; border:1px solid var(--line); padding:24px 32px; margin-top:16px; }
h2 { font-size:16px; margin:0 0 14px; padding-bottom:8px; border-bottom:2px solid var(--ink); }
.note { color:var(--sub); font-size:13px; margin:-6px 0 12px; }
.kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:12px; }
.kpi { background:var(--soft); border:1px solid var(--line); padding:14px 16px; }
.kpi .k { font-size:12px; color:var(--sub); }
.kpi .v { font-size:24px; font-weight:700; margin-top:2px; font-variant-numeric:tabular-nums; }
table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }
th, td { border:1px solid var(--line); padding:7px 10px; text-align:right; }
th:first-child, td:first-child { text-align:left; }
thead th { background:var(--soft); font-weight:600; }
tbody th { background:#fff; font-weight:600; }
td.diag { background:var(--diag); font-weight:700; }
td.zero { color:#9aa7ba; }
.chip { display:inline-block; padding:0 8px; border-radius:999px; background:var(--soft);
        border:1px solid var(--line); font-size:12.5px; font-weight:600; }
.cols { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
@media (max-width:720px) { .cols { grid-template-columns:1fr; }
  header, section { padding-left:20px; padding-right:20px; } }
.empty { color:var(--sub); }
footer { color:var(--sub); font-size:12.5px; text-align:center; margin-top:22px; }
"""


def _esc(x) -> str:
    return _html.escape(str(x), quote=True)


def _metric_row(name: str, m: dict) -> str:
    return (f"<tr><th>{_esc(name)}</th><td>{_fmt(m['precision'])}</td>"
            f"<td>{_fmt(m['recall'])}</td><td>{_fmt(m['f1'])}</td>"
            f"<td>{m['support']}</td></tr>")


def _metric_table(rows: str) -> str:
    return ("<table><thead><tr><th>라벨</th><th>Precision</th><th>Recall</th>"
            f"<th>F1</th><th>Support</th></tr></thead><tbody>{rows}</tbody></table>")


def render_html(report: dict, *, dataset_name: str, source_label: str,
                source_name: str, source_version: str) -> str:
    """report dict -> 단독 파일로 열리는 HTML 리포트 (외부 자산 없음, 인라인 CSS)."""
    counts = report["counts"]
    b = report["binary_risk"]
    stage_name = _STAGE_NAMES.get(report["stage"], report["stage"])

    meta = [
        ("테스트셋", f"{dataset_name} ({counts['total']}건)"),
        (source_label, f"{source_name} {source_version}"),
        ("평가 단계", stage_name),
        ("평가 완료 / 오류", f"{counts['evaluated']}건 / {counts['errors']}건 (오류는 지표 분모에서 제외)"),
    ]
    if report.get("thresholds"):
        t = report["thresholds"]
        meta.append(("모델 임계값", f"depression ≥ {t['depression']}, anxiety ≥ {t['anxiety']}"))
    if report.get("generated_at"):
        meta.append(("생성 시각", report["generated_at"]))
    meta_html = "".join(f"<div><dt>{_esc(k)}</dt><dd>{_esc(v)}</dd></div>" for k, v in meta)

    model_focus = _is_model_focus(report)
    if model_focus:
        sm = report["sublabel_metrics"]
        kpis = [("우울 Recall", sm["depression"]["recall"]),
                ("불안 Recall", sm["anxiety"]["recall"]),
                ("합산 Precision", sm["any_signal"]["precision"]),
                ("합산 Recall", sm["any_signal"]["recall"])]
    else:
        kpis = [("정확도 (Accuracy)", report["overall"]["accuracy"]),
                ("Macro F1", report["overall"]["macro_f1"]),
                ("위험 Precision", b["precision"]), ("위험 Recall", b["recall"]),
                ("위험 F1", b["f1"])]
    kpi_html = "".join(
        f'<div class="kpi"><div class="k">{_esc(k)}</div><div class="v">{_fmt(v)}</div></div>'
        for k, v in kpis)

    label_rows = "".join(_metric_row(label, report["per_label"][label]) for label in LABELS)

    sections = [f'<section><h2>핵심 지표</h2><div class="kpis">{kpi_html}</div></section>']
    if not model_focus:
        sections.append(f"<section><h2>라벨별 지표</h2>{_metric_table(label_rows)}</section>")

    if report.get("contribution"):
        c = report["contribution"]
        rows = "".join(
            f"<tr><th>{_esc(name)}</th><td>{value}</td></tr>" for name, value in [
                ("사전이 잡은 위험", c["caught_by_dict"]),
                ("모델 신호로 잡은 위험 (사전은 놓침)", c["caught_by_model"]),
                ("끝내 놓친 위험", c["missed"]),
                ("사전이 만든 오탐", c["fp_from_dict"]),
                ("모델 신호가 만든 오탐 (사전은 none)", c["fp_from_model"]),
                ("맞게 비위험으로 둔 건", c["clean_none"]),
            ] + ([("위해 모델이 단독으로 잡은 위험 (사전은 놓침)", c["caught_by_harm"]),
                  ("위해 모델이 만든 오탐", c["fp_from_harm"]),
                  ("사전이 잡았으나 위해 확인에서 떨어진 건", c["dict_dropped_by_harm"])]
                 if "caught_by_harm" in c else [])
              + ([("위해 모델 오류로 기존 규칙으로 평가한 건", c["harm_errors"])]
                 if c.get("harm_errors") else [])
              + ([("모델 오류로 사전 판정만으로 평가한 건", c["model_errors"])]
                 if c["model_errors"] else []))
        sections.append(
            "<section><h2>단계 기여 분해</h2>"
            '<p class="note">최종 판정의 정답·오탐이 어느 단계에서 왔는지 분해한 것이다.</p>'
            f"<table><tbody>{rows}</tbody></table></section>")

    if not model_focus and report.get("certainty_summary"):
        cs = report["certainty_summary"]
        co, ad = cs["certain_only"], cs["ambiguous_directional"]
        sections.append(
            "<section><h2>확실성(certainty) 분리 지표</h2>"
            '<p class="note">주 지표는 위 전체 지표다. certain-only는 참고용이며, '
            "ambiguous 건은 방향별로 센다.</p>"
            f"<p>certainty 분포: certain {cs['counts']['certain']}건, "
            f"ambiguous {cs['counts']['ambiguous']}건, "
            f"needs_context {cs['counts']['needs_context']}건</p>"
            f"<p>certain-only ({co['n']}건): 정확도 {_fmt(co['accuracy'])}, "
            f"위험 Precision {_fmt(co['binary_risk']['precision'])}, "
            f"Recall {_fmt(co['binary_risk']['recall'])}, F1 {_fmt(co['binary_risk']['f1'])}</p>"
            f"<p>ambiguous ({ad['n']}건): 정답 {ad['correct']}건, "
            f"누락(위험→none) {ad['miss']}건, 과탐(none→위험) {ad['overcall']}건</p></section>")

    if not model_focus and report.get("subgroup_metrics"):
        rows = ""
        for name, m in report["subgroup_metrics"].items():
            rows += (f"<tr><th>{_esc(name)}</th><td>{m['n']}</td><td>{m['positives']}</td>"
                     f"<td>{m['detected']}</td><td>{_fmt(m['detection_rate'])}</td>"
                     f"<td>{m['negatives']}</td><td>{m['false_positives']}</td>"
                     f"<td>{_fmt(m['fp_rate'])}</td></tr>")
        sections.append(
            "<section><h2>소그룹 지표</h2><table><thead><tr><th>소그룹</th><th>건수</th>"
            "<th>위험 정답</th><th>탐지</th><th>탐지율</th><th>none 정답</th><th>오탐</th>"
            f"<th>FP율</th></tr></thead><tbody>{rows}</tbody></table></section>")

    if report.get("sublabel_metrics"):
        names = {"depression": "우울", "anxiety": "불안", "any_signal": "합산 (둘 중 하나)"}
        rows = "".join(_metric_row(names[k], report["sublabel_metrics"][k])
                       for k in ("depression", "anxiety", "any_signal"))
        extra = ""
        if report.get("sublabel_counts"):
            sc = report["sublabel_counts"]
            extra = ('<p class="note">제외(null) 건수: ' + ", ".join(
                f"{names[k]} {sc[k]['null_excluded']}건 (평가 {sc[k]['labeled']}건)"
                for k in ("depression", "anxiety", "any_signal")) + "</p>")
        if report.get("sublabel_metrics_certain"):
            rows_c = "".join(_metric_row(names[k], report["sublabel_metrics_certain"][k])
                             for k in ("depression", "anxiety", "any_signal"))
            extra += ('<p class="note" style="margin-top:14px">certain-only 하위 라벨 지표 '
                      f"(참고용)</p>{_metric_table(rows_c)}")
        sections.append(
            "<section><h2>하위 라벨 지표 (우울/불안)</h2>"
            '<p class="note">테스트셋 sublabels 기준. null인 항목은 제외한다.</p>'
            f"{_metric_table(rows)}{extra}</section>")

    if model_focus:
        sections.append(
            "<section><h2>참고: 임계값 파생 판정</h2>"
            '<p class="note">점수에 임계값을 적용해 위험/비위험으로 접은 값이다. '
            "정답(자살·자해 위험)과 모델 신호(우울·불안)는 다른 구성개념이라 "
            "이 수치가 낮아도 모델이 나쁜 것은 아니다.</p>"
            "<table><tbody>"
            f"<tr><th>정확도</th><td>{_fmt(report['overall']['accuracy'])}</td></tr>"
            f"<tr><th>위험 Precision</th><td>{_fmt(b['precision'])}</td></tr>"
            f"<tr><th>위험 Recall</th><td>{_fmt(b['recall'])}</td></tr>"
            f"<tr><th>위험 F1</th><td>{_fmt(b['f1'])}</td></tr>"
            "</tbody></table></section>")
    else:
        labels = report["confusion"]["labels"]
        head = "".join(f"<th>{_esc(l)}</th>" for l in labels)
        body = ""
        for i, (label, row) in enumerate(zip(labels, report["confusion"]["matrix"])):
            cells = ""
            for j, v in enumerate(row):
                cls = ' class="diag"' if i == j else (' class="zero"' if v == 0 else "")
                cells += f"<td{cls}>{v}</td>"
            body += f"<tr><th>{_esc(label)}</th>{cells}</tr>"
        sections.append(
            "<section><h2>혼동행렬</h2>"
            '<p class="note">행 = 정답, 열 = 예측.</p>'
            f"<table><thead><tr><th>정답 \\ 예측</th>{head}</tr></thead>"
            f"<tbody>{body}</tbody></table></section>")

        if report.get("pattern_stats"):
            rows = "".join(
                f"<tr><th>{_esc(s['pattern_id'])}</th><td>{s['hits']}</td>"
                f"<td>{s['fp_hits']}</td></tr>" for s in report["pattern_stats"])
            sections.append(
                "<section><h2>패턴 매칭 통계</h2>"
                '<p class="note">패턴별 매칭 건수와, 그중 정답이 none인 오탐 매칭 건수다. '
                "자주 걸리는데 오탐이 많은 패턴부터 다듬는다.</p>"
                "<table><thead><tr><th>패턴</th><th>매칭</th><th>오탐 매칭</th></tr></thead>"
                f"<tbody>{rows}</tbody></table></section>")

        def case_table(cases):
            if not cases:
                return '<p class="empty">없음</p>'
            rows = "".join(
                f"<tr><td>{_esc(c['id'])}</td><td><span class=\"chip\">{_esc(_gold_label(c))}</span></td>"
                f"<td><span class=\"chip\">{_esc(c['predicted'])}</span></td></tr>" for c in cases)
            return ("<table><thead><tr><th>id</th><th>정답</th><th>예측</th></tr></thead>"
                    f"<tbody>{rows}</tbody></table>")

        sections.append(
            '<section><h2>오탐 · 미탐</h2><div class="cols">'
            f"<div><h3>오탐 — 위험 아님을 위험으로 판정 ({len(report['false_positives'])}건)</h3>"
            f"{case_table(report['false_positives'])}</div>"
            f"<div><h3>미탐 — 위험을 놓침 ({len(report['false_negatives'])}건)</h3>"
            f"{case_table(report['false_negatives'])}</div></div></section>")

    if report["error_cases"]:
        rows = "".join(f"<tr><td>{_esc(c['id'])}</td><td>{_esc(c['error'])}</td></tr>"
                       for c in report["error_cases"])
        sections.append(
            "<section><h2>판정 오류</h2><table><thead><tr><th>id</th><th>사유</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></section>")

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>위험판별 평가 리포트 — {_esc(stage_name)}</title>
<style>{_HTML_CSS}</style>
</head>
<body>
<div class="page">
<header>
<div class="eyebrow">RISKCHECK</div>
<h1>위험판별 평가 리포트</h1>
<span class="stage">{_esc(stage_name)}</span>
<dl class="meta">{meta_html}</dl>
<p class="note" style="margin:14px 0 0">판정 방식: {_esc(_STAGE_NOTES[report['stage']])}</p>
</header>
{''.join(sections)}
<footer>riskcheck — 한국어 위험 표현 판별 테스트 도구 · 기본 사전과 기본 모델은 성능 측정의 출발점이다.</footer>
</div>
</body>
</html>
"""
