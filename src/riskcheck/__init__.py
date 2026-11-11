"""riskcheck — 한국어 위험 표현(자살·자해) 판별 테스트 도구.

테스트셋을 단어 사전 단계와 분류모델 단계로 판정하고, 단계별·전체 지표를
리포트로 낸다. 판정은 위험/비위험 이진이다 — 사전 패턴에 등급은 없고,
테스트셋 정답이 등급(danger/emergency)으로 붙어 있어도 채점할 때 risk로 접는다.
"""

__version__ = "0.1.0"

LABELS = ("none", "risk")


def to_binary(label: str | None) -> str | None:
    """등급 라벨을 이진으로 접는다. none만 비위험, 나머지는 전부 risk."""
    if label is None:
        return None
    return "none" if label == "none" else "risk"
