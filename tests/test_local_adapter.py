import math

import pytest

from riskcheck.model import (LocalModelAdapter, resolve_label_map, resolve_outputs,
                             scores_from_logits, scores_from_outputs)


def test_truncation_kwargs():
    from riskcheck.model import _truncation_kwargs

    assert _truncation_kwargs(None) == {}
    assert _truncation_kwargs(96) == {"truncation": True, "max_length": 96}


def test_resolve_label_map_by_name_and_index():
    labels = ["depression", "anxiety", "else"]
    assert resolve_label_map(None, labels) == {"depression": [0], "anxiety": [1], "else": [2]}
    assert resolve_label_map(None, []) == {"depression": [0], "anxiety": [1], "else": [2]}


def test_resolve_label_map_gate_style_else_sum():
    labels = ["depression", "anxiety", "other_negative", "calm"]
    resolved = resolve_label_map(
        {"depression": "depression", "anxiety": "anxiety", "else": ["other_negative", "calm"]},
        labels)
    assert resolved == {"depression": [0], "anxiety": [1], "else": [2, 3]}
    scores = scores_from_logits([2.0, 0.0, 1.0, 1.0], resolved)
    assert scores["depression"] > scores["else"] > scores["anxiety"]
    assert scores["depression"] + scores["anxiety"] + scores["else"] == pytest.approx(1.0, abs=1e-3)


class FakeBackend:
    class_labels = ["depression", "anxiety", "else"]

    def logits(self, text):
        return [3.0, 0.0, 0.0] if "우울" in text else [0.0, 0.0, 3.0]


def test_local_adapter_with_fake_backend():
    adapter = LocalModelAdapter({"path": "fake", "version": "t1"}, backend=FakeBackend())
    scores = adapter.predict("우울해")
    assert scores["depression"] > 0.9
    assert adapter.predict("맑아")["else"] > 0.9
    assert adapter.version == "t1"


# 게이트(softmax 4) + 감정 헤드(sigmoid 3) 혼합 모델 흉내: 출력 7개
MIXED_LABELS = ["gate_dep", "gate_anx", "gate_other", "gate_calm",
                "head_dep", "head_anx", "head_tension"]
MIXED_OUTPUTS = {
    "depression": {"from": "head_dep", "activation": "sigmoid"},
    "anxiety": {"from": "head_anx", "activation": "sigmoid"},
    "else": {"from": ["gate_other", "gate_calm"], "activation": "softmax",
             "group": ["gate_dep", "gate_anx", "gate_other", "gate_calm"]},
}


class MixedBackend:
    class_labels = MIXED_LABELS

    def logits(self, text):
        # 게이트 logits [0,0,0,2], 헤드 logits [4,-2,0]
        return [0.0, 0.0, 0.0, 2.0, 4.0, -2.0, 0.0]


def test_outputs_mixed_gate_and_heads():
    resolved = resolve_outputs(MIXED_OUTPUTS, MIXED_LABELS)
    scores = scores_from_outputs(MixedBackend().logits("x"), resolved)
    # depression/anxiety는 헤드 sigmoid 값 그대로 (전체 softmax가 아님)
    assert scores["depression"] == pytest.approx(1 / (1 + math.exp(-4)), abs=1e-3)
    assert scores["anxiety"] == pytest.approx(1 / (1 + math.exp(2)), abs=1e-3)
    # else는 게이트 그룹 안에서만 softmax한 other+calm 합
    gate = [math.exp(v) for v in (0.0, 0.0, 0.0, 2.0)]
    assert scores["else"] == pytest.approx((gate[2] + gate[3]) / sum(gate), abs=1e-3)


def test_local_adapter_outputs_end_to_end():
    adapter = LocalModelAdapter(
        {"path": "fake", "version": "t2", "outputs": MIXED_OUTPUTS}, backend=MixedBackend())
    scores = adapter.predict("아무 문장")
    assert scores["depression"] > 0.98 and scores["anxiety"] < 0.12


def test_outputs_probability_passthrough():
    resolved = resolve_outputs(
        {"depression": {"from": 0, "activation": "none"},
         "anxiety": {"from": 1, "activation": "none"}}, [])
    scores = scores_from_outputs([0.3, 0.1, 99.0], resolved)
    assert scores == {"depression": 0.3, "anxiety": 0.1, "else": 0.6}


def test_outputs_combine_max_and_mean():
    # 같은 점수를 여러 출력에서 읽을 때의 조합법: max는 가장 강한 신호, mean은 평균
    resolved = resolve_outputs(
        {"depression": {"from": [0, 1], "activation": "none", "combine": "max"},
         "anxiety": {"from": [2, 3], "activation": "none", "combine": "mean"}}, [])
    scores = scores_from_outputs([0.2, 0.7, 0.1, 0.3], resolved)
    assert scores["depression"] == pytest.approx(0.7)
    assert scores["anxiety"] == pytest.approx(0.2)


def test_outputs_combine_rejects_unknown():
    with pytest.raises(ValueError):
        resolve_outputs(
            {"depression": {"from": 0, "activation": "none", "combine": "median"},
             "anxiety": {"from": 1, "activation": "none"}}, [])


def _build_tiny_onnx(path):
    import onnx
    from onnx import TensorProto, helper

    weights = helper.make_tensor("W", TensorProto.FLOAT, [1, 3], [1.0, 0.0, -1.0])
    graph = helper.make_graph(
        nodes=[
            helper.make_node("Cast", ["input_ids"], ["ids_f"], to=TensorProto.FLOAT),
            helper.make_node("ReduceMean", ["ids_f"], ["mean"], axes=[1], keepdims=1),
            helper.make_node("MatMul", ["mean", "W"], ["logits"]),
        ],
        name="tiny",
        inputs=[
            helper.make_tensor_value_info("input_ids", TensorProto.INT64, [1, None]),
            helper.make_tensor_value_info("attention_mask", TensorProto.INT64, [1, None]),
        ],
        outputs=[helper.make_tensor_value_info("logits", TensorProto.FLOAT, [1, 3])],
        initializer=[weights],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8  # onnxruntime이 지원하는 IR 버전으로 고정
    onnx.save(model, path)


def test_local_adapter_real_onnx(tmp_path):
    ort = pytest.importorskip("onnxruntime")
    transformers = pytest.importorskip("transformers")
    pytest.importorskip("onnx")

    model_dir = tmp_path / "tiny-model"
    model_dir.mkdir()
    _build_tiny_onnx(model_dir / "model.onnx")
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("[PAD]\n[UNK]\n[CLS]\n[SEP]\n우울\n해\n", encoding="utf-8")

    from riskcheck.model import _OnnxBackend
    backend = _OnnxBackend.__new__(_OnnxBackend)
    backend.session = ort.InferenceSession(str(model_dir / "model.onnx"),
                                           providers=["CPUExecutionProvider"])
    backend.input_names = [i.name for i in backend.session.get_inputs()]
    backend.tokenizer = transformers.BertTokenizer(vocab_file=str(vocab))
    backend.class_labels = ["depression", "anxiety", "else"]
    backend.max_length = None

    adapter = LocalModelAdapter(
        {"path": str(model_dir), "format": "onnx",
         "class_labels": ["depression", "anxiety", "else"], "version": "tiny-1"},
        backend=backend)
    scores = adapter.predict("우울 해")
    total = sum(scores.values())
    assert total == pytest.approx(1.0, abs=0.01)
    assert scores["depression"] == max(scores.values())  # 토큰 평균이 양수면 우울 로짓이 최대
    assert isinstance(adapter.predict("해"), dict)
