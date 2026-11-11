"""분류모델 단계 어댑터.

모델은 발화 하나를 받아 {depression, anxiety, else} 점수(각 0..1)를 돌려준다.
판정(임계값 적용)은 어댑터가 아니라 채점 단계의 정책이 한다 — 그래서 임계값을
바꿔도 모델을 다시 부르지 않고 저장된 점수로 재채점할 수 있다.

어댑터 종류:
- http: 별도 서버로 띄운 모델에 HTTP POST로 호출 (응답 필드 매핑 설정 가능)
- file: 미리 계산한 점수 파일(JSONL)을 읽는다 — 로컬 모델을 오프라인으로 돌린 뒤 연결할 때
- local: 로컬 모델 파일(ONNX 또는 HuggingFace)을 직접 실행한다 (추가 의존성 필요)
- stub: 데모용 규칙 스텁. 실제 모델이 아니며, 파이프라인 동작 확인 전용이다.
"""
import json
import math
import os
import urllib.request
from pathlib import Path

import yaml

SCORE_KEYS = ("depression", "anxiety", "else")


def validate_scores(scores: dict) -> dict:
    """점수 dict를 검증하고, else가 없으면 1-우울-불안으로 채워 정규화한다."""
    out = {}
    for key in ("depression", "anxiety"):
        if key not in scores:
            raise ValueError(f"모델 점수에 {key}가 없다: {scores}")
        value = float(scores[key])
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"모델 점수 {key}가 0..1 범위를 벗어났다: {value}")
        out[key] = round(value, 4)
    if scores.get("else") is None:
        out["else"] = round(max(0.0, min(1.0, 1.0 - out["depression"] - out["anxiety"])), 4)
    else:
        value = float(scores["else"])
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"모델 점수 else가 0..1 범위를 벗어났다: {value}")
        out["else"] = round(value, 4)
    return out


class HttpModelAdapter:
    """HTTP로 모델 서버를 호출한다. 요청은 {"text": ...} JSON, 응답은 JSON 객체.

    응답에서 점수를 꺼내는 경로는 response_map으로 정한다 (점 표기, 예: "result.depression").
    매핑이 없으면 응답 최상위의 depression/anxiety/else 키를 쓴다.
    """

    def __init__(self, config: dict):
        self.url = config["url"]
        self.timeout = float(config.get("timeout", 10))
        self.response_map = config.get("response_map") or {}
        self.headers = dict(config.get("headers") or {})
        api_key_env = config.get("api_key_env")
        if api_key_env:
            key = os.environ.get(api_key_env)
            if key:
                self.headers.setdefault("Authorization", f"Bearer {key}")
        self.version = str(config.get("version", "http"))

    @staticmethod
    def _dig(obj, dotted: str):
        cur = obj
        for part in dotted.split("."):
            cur = cur[part]
        return cur

    def predict(self, text: str, item_id: str | None = None) -> dict:
        body = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=body, method="POST",
            headers={"Content-Type": "application/json", **self.headers})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        raw = {key: self._dig(payload, self.response_map.get(key, key))
               for key in SCORE_KEYS if key != "else" or "else" in self.response_map or "else" in payload}
        return validate_scores(raw)


class FileScoresAdapter:
    """미리 계산된 점수 파일을 읽는 어댑터.

    파일 형식(JSONL): {"id": ..., "scores": {"depression": .., "anxiety": .., "else": ..}}
    id가 없으면 text로 찾는다: {"text": ..., "scores": {...}}
    """

    def __init__(self, config: dict):
        path = Path(config["path"])
        self.by_id, self.by_text = {}, {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            scores = validate_scores(row["scores"])
            if "id" in row:
                self.by_id[row["id"]] = scores
            if "text" in row:
                self.by_text[row["text"]] = scores
        self.version = str(config.get("version", f"file:{path.name}"))

    def predict(self, text: str, item_id: str | None = None) -> dict:
        if item_id is not None and item_id in self.by_id:
            return self.by_id[item_id]
        if text in self.by_text:
            return self.by_text[text]
        raise KeyError(f"점수 파일에 없는 항목: id={item_id}")


class StubModelAdapter:
    """데모용 규칙 스텁.

    우울·불안 신호 단어가 있으면 해당 점수를 올리는 단순 규칙이다. 실제 모델 성능을
    대표하지 않으며, 모델 단계 파이프라인과 리포트 형식을 확인하는 용도로만 쓴다.
    """

    DEPRESSION_WORDS = ("우울", "무기력", "의욕", "눈물", "울었", "슬퍼", "슬픔", "허무",
                        "막막", "외로", "자존감", "번아웃", "포기하고 싶", "그만두고 싶")
    ANXIETY_WORDS = ("불안", "걱정", "초조", "긴장", "두근", "잠이 안", "잠을 못", "잠이 잘 안")

    def __init__(self, config: dict | None = None):
        self.version = "stub-0.1"

    def predict(self, text: str, item_id: str | None = None) -> dict:
        dep = 0.85 if any(w in text for w in self.DEPRESSION_WORDS) else 0.05
        anx = 0.85 if any(w in text for w in self.ANXIETY_WORDS) else 0.05
        if dep > 0.5 and anx > 0.5:
            dep = anx = 0.7
        return validate_scores({"depression": dep, "anxiety": anx})


def _softmax(logits: list[float]) -> list[float]:
    peak = max(logits)
    exps = [math.exp(x - peak) for x in logits]
    total = sum(exps)
    return [e / total for e in exps]


def resolve_label_map(label_map: dict | None, class_labels: list[str] | None) -> dict:
    """클래스 순서(label_map)를 점수 키별 인덱스 목록으로 확정한다.

    label_map 값은 인덱스(정수), 인덱스 목록, 클래스 이름, 이름 목록 모두 가능하다.
    지정이 없으면 클래스 이름에서 depression/anxiety/else를 찾고, 없으면 0/1/2번으로 본다.
    게이트형 4분류처럼 else에 여러 클래스를 합쳐야 하면 목록으로 지정한다.
    """
    labels = class_labels or []
    if not label_map:
        if all(k in labels for k in SCORE_KEYS):
            label_map = {k: k for k in SCORE_KEYS}
        else:
            label_map = {"depression": 0, "anxiety": 1, "else": 2}
    resolved = {}
    for key in SCORE_KEYS:
        if key not in label_map:
            raise ValueError(f"label_map에 {key}가 없다")
        raw = label_map[key]
        items = raw if isinstance(raw, list) else [raw]
        indices = []
        for item in items:
            if isinstance(item, int):
                indices.append(item)
            elif item in labels:
                indices.append(labels.index(item))
            else:
                raise ValueError(f"label_map의 '{item}'을 클래스 목록에서 찾을 수 없다: {labels}")
        resolved[key] = indices
    return resolved


def scores_from_logits(logits: list[float], resolved_label_map: dict) -> dict:
    """모델 logits를 softmax한 뒤 label_map대로 합쳐 {depression, anxiety, else}로 만든다."""
    probs = _softmax([float(x) for x in logits])
    raw = {key: sum(probs[i] for i in indices) for key, indices in resolved_label_map.items()}
    return validate_scores(raw)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x)) if x >= 0 else math.exp(x) / (1.0 + math.exp(x))


def _resolve_refs(raw, labels: list[str], what: str) -> list[int]:
    """이름/인덱스(또는 목록)를 출력 인덱스 목록으로 바꾼다."""
    items = raw if isinstance(raw, list) else [raw]
    indices = []
    for item in items:
        if isinstance(item, int):
            indices.append(item)
        elif item in labels:
            indices.append(labels.index(item))
        else:
            raise ValueError(f"{what}의 '{item}'을 클래스 목록에서 찾을 수 없다: {labels}")
    return indices


def resolve_outputs(outputs: dict, class_labels: list[str] | None) -> dict:
    """outputs 스펙(변형 규칙)을 점수 키별 (인덱스 목록, 활성화, 그룹, 조합법)으로 확정한다.

    모델의 출력 형태는 class_labels(ONNX)나 모델의 id2label(HF)로 선언되고,
    이 스펙은 선언된 출력을 테스트가 요구하는 {depression, anxiety, else} 점수로
    바꾸는 변형/계산 규칙이다.

    스펙 형식: {점수 키: {from: 이름|인덱스|[목록], activation: softmax|sigmoid|none,
    group: [softmax를 함께 계산할 출력 목록], combine: sum|max|mean}}.
    from이 여러 개면 활성화한 값들을 combine 방식으로 합친다 (기본 sum).
    실제 모델은 출력 구조가 제각각이다 — 단일 softmax 분류기, 클래스별 sigmoid
    헤드를 여럿 단 멀티라벨 모델, 게이트(softmax 그룹)+헤드(sigmoid) 혼합 모델 —
    이 규칙으로 어느 형태든 점수로 접는다.
    """
    labels = class_labels or []
    resolved = {}
    for key in ("depression", "anxiety", "else"):
        if key not in outputs:
            if key == "else":
                continue  # else는 선택 — 없으면 validate_scores가 1-우울-불안으로 채운다
            raise ValueError(f"outputs에 {key}가 없다")
        spec = outputs[key] or {}
        if "from" not in spec:
            raise ValueError(f"outputs.{key}에 from이 없다")
        indices = _resolve_refs(spec["from"], labels, f"outputs.{key}")
        activation = spec.get("activation", "softmax")
        if activation not in ("softmax", "sigmoid", "none"):
            raise ValueError(f"outputs.{key}의 activation 오류: {activation}")
        combine = spec.get("combine", "sum")
        if combine not in ("sum", "max", "mean"):
            raise ValueError(f"outputs.{key}의 combine 오류: {combine}")
        members = None
        if spec.get("group") is not None:
            members = tuple(sorted(set(
                _resolve_refs(spec["group"], labels, f"outputs.{key}.group"))))
            if not set(indices) <= set(members):
                raise ValueError(f"outputs.{key}의 from이 group 멤버에 포함되지 않는다")
        resolved[key] = (indices, activation, members, combine)
    return resolved


def _combine(values: list[float], combine: str) -> float:
    if combine == "max":
        return max(values)
    if combine == "mean":
        return sum(values) / len(values)
    return sum(values)


def scores_from_outputs(values: list[float], resolved_outputs: dict) -> dict:
    """모델 원시 출력 벡터를 변형 규칙(outputs 스펙)대로 계산해 {depression, anxiety, else}로 만든다.

    softmax는 group 멤버 안에서, group이 없으면 전체 출력에서 계산한다. sigmoid는
    출력마다 독립 적용한다. none은 모델이 이미 확률을 내는 경우로, 값을 그대로 쓴다.
    from이 여러 개면 활성화한 값들을 combine(sum|max|mean)으로 합친다.
    """
    vals = [float(x) for x in values]
    probs_cache: dict = {}

    def softmax_probs(members: tuple) -> list[float]:
        if members not in probs_cache:
            probs_cache[members] = _softmax([vals[i] for i in members])
        return probs_cache[members]

    raw = {}
    for key, (indices, activation, members, combine) in resolved_outputs.items():
        if activation == "sigmoid":
            parts = [_sigmoid(vals[i]) for i in indices]
        elif activation == "none":
            parts = [vals[i] for i in indices]
        else:  # softmax
            group = members if members is not None else tuple(range(len(vals)))
            probs = softmax_probs(group)
            pos = {idx: n for n, idx in enumerate(group)}
            parts = [probs[pos[i]] for i in indices]
        raw[key] = _combine(parts, combine)
    return validate_scores(raw)


def _truncation_kwargs(max_length) -> dict:
    """max_length 설정이 있으면 토크나이저 절단 인자를 만든다.

    모델 학습 시 입력 절단 길이와 추론을 맞추는 용도다. 설정이 없으면
    절단하지 않는다 (기존 동작).
    """
    if not max_length:
        return {}
    return {"truncation": True, "max_length": int(max_length)}


class _OnnxBackend:
    """onnxruntime으로 로컬 ONNX 모델을 돌린다 (추가 의존성: local-onnx)."""

    def __init__(self, config: dict):
        try:
            import onnxruntime as ort
            from transformers import AutoTokenizer
        except ImportError as e:
            raise RuntimeError(
                "로컬 ONNX 어댑터에는 추가 패키지가 필요하다: "
                'pip install -e ".[local-onnx]"') from e
        path = Path(config["path"])
        model_file = path if path.suffix == ".onnx" else next(path.glob("*.onnx"), None)
        if model_file is None:
            raise ValueError(f"ONNX 파일을 찾을 수 없다: {path}")
        self.session = ort.InferenceSession(str(model_file), providers=["CPUExecutionProvider"])
        self.input_names = [i.name for i in self.session.get_inputs()]
        tokenizer_src = config.get("tokenizer") or (path if path.is_dir() else path.parent)
        self.tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_src))
        self.class_labels = list(config.get("class_labels") or [])
        self.max_length = config.get("max_length")

    def logits(self, text: str) -> list[float]:
        encoded = self.tokenizer(text, return_tensors="np", **_truncation_kwargs(self.max_length))
        feed = {name: encoded[name] for name in self.input_names if name in encoded}
        missing = [n for n in self.input_names if n not in feed]
        if missing:
            raise ValueError(f"토크나이저 출력에 없는 모델 입력: {missing}")
        return self.session.run(None, feed)[0][0].tolist()


class _HfBackend:
    """transformers(PyTorch)로 로컬 HF 모델을 돌린다 (추가 의존성: local-hf)."""

    def __init__(self, config: dict):
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as e:
            raise RuntimeError(
                "로컬 HF 어댑터에는 추가 패키지가 필요하다: "
                'pip install -e ".[local-hf]"') from e
        self.torch = torch
        path = str(config["path"])
        self.tokenizer = AutoTokenizer.from_pretrained(config.get("tokenizer") or path)
        self.model = AutoModelForSequenceClassification.from_pretrained(path)
        self.model.eval()
        id2label = getattr(self.model.config, "id2label", {}) or {}
        self.class_labels = [id2label.get(i, str(i)) for i in range(len(id2label))]
        self.max_length = config.get("max_length")

    def logits(self, text: str) -> list[float]:
        encoded = self.tokenizer(text, return_tensors="pt", **_truncation_kwargs(self.max_length))
        with self.torch.no_grad():
            return self.model(**encoded).logits[0].tolist()


class LocalModelAdapter:
    """로컬 모델 파일(ONNX 또는 HF)을 직접 돌리는 어댑터.

    모델 계약: 발화별 원시 출력 벡터(클래스별 logits 또는 확률)를 내는 모델이어야
    한다. 출력을 {depression, anxiety, else} 점수로 접는 방법은 두 가지다.

    - label_map: 단일 softmax 분류기용. 전체 출력에 softmax를 걸고 지정 클래스를
      합산한다 (이름 또는 인덱스, 목록 합산 가능).
    - outputs: 출력 구조가 복합적인 모델용. 점수 키마다 출처(from)와 변환
      (activation: softmax/그룹 softmax/sigmoid/none)을 지정한다 — 멀티라벨
      sigmoid 헤드나 게이트+헤드 혼합 모델은 이쪽으로 연결한다. 둘 다 있으면
      outputs가 우선한다.
    """

    def __init__(self, config: dict, *, backend=None):
        self.config = config
        if backend is not None:
            self.backend = backend
        else:
            fmt = config.get("format", "auto")
            path = Path(config["path"])
            if fmt == "onnx" or (fmt == "auto" and (path.suffix == ".onnx" or list(path.glob("*.onnx")))):
                self.backend = _OnnxBackend(config)
            else:
                self.backend = _HfBackend(config)
        class_labels = getattr(self.backend, "class_labels", None)
        if config.get("outputs"):
            self.outputs = resolve_outputs(config["outputs"], class_labels)
            self.label_map = None
        else:
            self.outputs = None
            self.label_map = resolve_label_map(config.get("label_map"), class_labels)
        self.version = str(config.get("version", f"local:{Path(config['path']).name}"))

    def predict(self, text: str, item_id: str | None = None) -> dict:
        values = self.backend.logits(text)
        if self.outputs is not None:
            return scores_from_outputs(values, self.outputs)
        return scores_from_logits(values, self.label_map)


def load_model_config(path: str | Path) -> dict:
    config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict) or "adapter" not in config:
        raise ValueError(f"모델 설정에 adapter가 없다: {path}")
    return config


def build_adapter(config: dict):
    kind = config["adapter"]
    if kind == "http":
        return HttpModelAdapter(config.get("http") or {})
    if kind == "file":
        return FileScoresAdapter(config.get("file") or {})
    if kind == "stub":
        return StubModelAdapter(config.get("stub") or {})
    if kind == "local":
        return LocalModelAdapter(config.get("local") or {})
    raise ValueError(f"알 수 없는 어댑터 종류: {kind}")


def model_thresholds(config: dict, overrides: dict | None = None) -> dict:
    """임계값 정책: 설정 파일 값에 CLI 재정의(overrides)를 얹는다."""
    thresholds = {"depression": 0.5, "anxiety": 0.5}
    thresholds.update(config.get("thresholds") or {})
    for key, value in (overrides or {}).items():
        if value is not None:
            thresholds[key] = value
    return thresholds


# ── 위해 모델 (옵션) ──────────────────────────────────────────────────────
# 감정 모델과 별개로 붙는 두 번째 모델 슬롯. 위해 모델은 발화의 위해(자살·자해
# 진성) 확률 하나(harm, 0..1)를 낸다. 사전이 1차로 어휘를 잡고 위해 모델이
# 진성을 확인·보완하는 축이며, 결합 방식은 harm_policy가 정한다.

def validate_harm(value) -> float:
    """위해 확률 하나를 검증해 0..1 float로 돌려준다."""
    v = float(value)
    if not 0.0 <= v <= 1.0:
        raise ValueError(f"위해 점수가 0..1 범위를 벗어났다: {v}")
    return round(v, 4)


def resolve_harm_output(spec: dict, class_labels: list[str] | None) -> tuple:
    """harm_output 스펙을 (인덱스 목록, 활성화, 그룹, 조합법)으로 확정한다.

    형식은 outputs 스펙과 같다: {from: 이름|인덱스|[목록], activation:
    softmax|sigmoid|none, group: [softmax를 함께 계산할 출력 목록],
    combine: sum|max|mean}. 이진 분류기면 from=진성 클래스, activation=softmax,
    group=[양쪽 클래스]가 표준이다.
    """
    if not isinstance(spec, dict) or "from" not in spec:
        raise ValueError("harm_output에 from이 없다")
    labels = class_labels or []
    indices = _resolve_refs(spec["from"], labels, "harm_output")
    activation = spec.get("activation", "softmax")
    if activation not in ("softmax", "sigmoid", "none"):
        raise ValueError(f"harm_output의 activation 오류: {activation}")
    combine = spec.get("combine", "sum")
    if combine not in ("sum", "max", "mean"):
        raise ValueError(f"harm_output의 combine 오류: {combine}")
    members = None
    if spec.get("group") is not None:
        members = tuple(sorted(set(_resolve_refs(spec["group"], labels, "harm_output.group"))))
        if not set(indices) <= set(members):
            raise ValueError("harm_output의 from이 group 멤버에 포함되지 않는다")
    return (indices, activation, members, combine)


def harm_from_values(values: list[float], resolved: tuple) -> float:
    """원시 출력 벡터에서 위해 확률 하나를 계산한다 (scores_from_outputs의 단일 키 버전)."""
    vals = [float(x) for x in values]
    indices, activation, members, combine = resolved
    if activation == "sigmoid":
        parts = [_sigmoid(vals[i]) for i in indices]
    elif activation == "none":
        parts = [vals[i] for i in indices]
    else:
        group = members if members is not None else tuple(range(len(vals)))
        probs = _softmax([vals[i] for i in group])
        pos = {idx: n for n, idx in enumerate(group)}
        parts = [probs[pos[i]] for i in indices]
    return validate_harm(_combine(parts, combine))


class LocalHarmAdapter:
    """로컬 모델(ONNX/HF)에서 위해 확률 하나를 뽑는 어댑터.

    백엔드(원시 출력 벡터)는 감정 모델과 같은 것을 쓰며, harm_output 스펙으로
    어느 출력이 위해 확률인지 선언한다. 스펙이 없으면 마지막 출력을 sigmoid한
    값으로 본다 (이진 분류에서 진성 클래스가 마지막인 관례).
    """

    def __init__(self, config: dict, *, backend=None):
        self.config = config
        if backend is not None:
            self.backend = backend
        else:
            fmt = config.get("format", "auto")
            path = Path(config["path"])
            if fmt == "onnx" or (fmt == "auto" and (path.suffix == ".onnx" or list(path.glob("*.onnx")))):
                self.backend = _OnnxBackend(config)
            else:
                self.backend = _HfBackend(config)
        class_labels = getattr(self.backend, "class_labels", None)
        spec = config.get("harm_output") or {"from": -1, "activation": "sigmoid"}
        if spec.get("from") == -1:
            spec = {**spec, "from": "last"}
        self.resolved = self._resolve(spec, class_labels)
        self.version = str(config.get("version", f"local-harm:{Path(config['path']).name}"))

    @staticmethod
    def _resolve(spec, class_labels):
        if spec.get("from") == "last":
            return ("last", spec.get("activation", "sigmoid"), None, "sum")
        return resolve_harm_output(spec, class_labels)

    def predict(self, text: str, item_id: str | None = None) -> dict:
        values = [float(x) for x in self.backend.logits(text)]
        if self.resolved[0] == "last":
            _, activation, _, _ = self.resolved
            v = values[-1]
            harm = _sigmoid(v) if activation == "sigmoid" else v
            return {"harm": validate_harm(harm)}
        return {"harm": harm_from_values(values, self.resolved)}


class FileHarmAdapter:
    """미리 계산한 위해 점수 파일을 읽는 어댑터.

    파일 형식(JSONL): {"id": ..., "harm": 0.83} 또는 {"id": ..., "scores": {"harm": 0.83}}.
    id가 없으면 text로 찾는다.
    """

    def __init__(self, config: dict):
        path = Path(config["path"])
        self.by_id, self.by_text = {}, {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            raw = row.get("harm", (row.get("scores") or {}).get("harm"))
            if raw is None:
                raise ValueError(f"위해 점수 파일 행에 harm이 없다: {row.get('id')}")
            harm = validate_harm(raw)
            if "id" in row:
                self.by_id[row["id"]] = harm
            if "text" in row:
                self.by_text[row["text"]] = harm
        self.version = str(config.get("version", f"file-harm:{path.name}"))

    def predict(self, text: str, item_id: str | None = None) -> dict:
        if item_id is not None and item_id in self.by_id:
            return {"harm": self.by_id[item_id]}
        if text in self.by_text:
            return {"harm": self.by_text[text]}
        raise KeyError(f"위해 점수 파일에 없는 항목: id={item_id}")


class HttpHarmAdapter:
    """HTTP 모델 서버에서 위해 확률을 받는 어댑터. response_map으로 harm 경로를 지정한다."""

    def __init__(self, config: dict):
        self.url = config["url"]
        self.timeout = float(config.get("timeout", 10))
        self.response_map = config.get("response_map") or {}
        self.headers = dict(config.get("headers") or {})
        api_key_env = config.get("api_key_env")
        if api_key_env:
            key = os.environ.get(api_key_env)
            if key:
                self.headers.setdefault("Authorization", f"Bearer {key}")
        self.version = str(config.get("version", "http-harm"))

    def predict(self, text: str, item_id: str | None = None) -> dict:
        body = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=body, method="POST",
            headers={"Content-Type": "application/json", **self.headers})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return {"harm": validate_harm(
            HttpModelAdapter._dig(payload, self.response_map.get("harm", "harm")))}


class StubHarmAdapter:
    """데모용 위해 스텁.

    위해 어휘가 있으면 높은 확률, 없으면 낮은 확률을 돌려주는 단순 규칙이다.
    실제 모델 성능을 대표하지 않으며, 위해 모델 결합 파이프라인 확인 전용이다.
    """

    HARM_WORDS = ("자살", "죽고 싶", "죽을", "손목", "유서", "뛰어내리", "목 매", "번개탄")

    def __init__(self, config: dict | None = None):
        self.version = "stub-harm-0.1"

    def predict(self, text: str, item_id: str | None = None) -> dict:
        harm = 0.9 if any(w in text for w in self.HARM_WORDS) else 0.05
        return {"harm": harm}


def build_harm_adapter(config: dict):
    kind = config["adapter"]
    if kind == "http":
        return HttpHarmAdapter(config.get("http") or {})
    if kind == "file":
        return FileHarmAdapter(config.get("file") or {})
    if kind == "stub":
        return StubHarmAdapter(config.get("stub") or {})
    if kind == "local":
        return LocalHarmAdapter(config.get("local") or {})
    raise ValueError(f"알 수 없는 위해 어댑터 종류: {kind}")


def harm_policy(config: dict, overrides: dict | None = None) -> dict:
    """위해 결합 정책: 설정 파일 값에 CLI 재정의를 얹는다.

    confirm: 사전이 잡은 건을 risk로 확정하는 데 필요한 위해 확률.
      0이면 사전 판정을 그대로 확정한다 (기존 OR 결합과 같은 형태).
    standalone: 사전이 놓친 건을 위해 모델 단독으로 risk로 올리는 위해 확률.
      1보다 큰 값이면 단독 승격을 끈다 (순수 확인형 결합).
    """
    policy = {"confirm": 0.5, "standalone": 0.4}
    policy.update(config.get("policy") or {})
    for key, value in (overrides or {}).items():
        if value is not None:
            policy[key] = value
    for key in ("confirm", "standalone"):
        policy[key] = float(policy[key])
    return policy
