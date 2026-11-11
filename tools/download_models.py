#!/usr/bin/env python3
"""기본 모델(감정 모델·위해 모델)을 내려받아 models/ 아래에 배치한다.

모델 가중치는 저장소에 직접 넣지 않고 배포 자산(zip)으로 제공한다.
기본값은 GitHub Releases의 최신 배포 자산을 가리키며, 다른 위치에서
받을 때는 --url로 지정한다.

사용법:
    python3 tools/download_models.py [--url <zip URL>] [--force]

배치되는 폴더:
    models/emotion-heads-v1/   감정 모델 (우울/불안 판별)
    models/harm-genuine-v2/    위해 모델 (진성/비진성 판별)
"""
import argparse
import io
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = os.environ.get(
    "RISKCHECK_MODELS_URL",
    "https://github.com/simsimi/safety-ruleset-library/releases/latest/download/safety-ruleset-library-models.zip",
)
EXPECTED_DIRS = ("emotion-heads-v1", "harm-genuine-v2")


def main() -> int:
    parser = argparse.ArgumentParser(description="기본 모델 내려받기")
    parser.add_argument("--url", default=DEFAULT_URL, help="모델 zip URL")
    parser.add_argument("--force", action="store_true", help="이미 있어도 다시 받는다")
    args = parser.parse_args()

    models_dir = ROOT / "models"
    missing = [d for d in EXPECTED_DIRS if not (models_dir / d).exists()]
    if not missing and not args.force:
        print("기본 모델이 이미 준비돼 있다:", ", ".join(EXPECTED_DIRS))
        return 0

    print(f"내려받는 중: {args.url}")
    with urllib.request.urlopen(args.url) as response:
        payload = response.read()
    print(f"받음: {len(payload) / 1e6:.1f} MB")

    placed = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in archive.namelist():
            parts = Path(name).parts
            # zip 최상위 폴더(sw1-models/)가 있으면 벗기고, 모델 폴더만 배치한다
            rel = parts[1:] if len(parts) > 1 and parts[0] == "sw1-models" else parts
            if not rel or rel[0] not in EXPECTED_DIRS:
                continue
            target = models_dir.joinpath(*rel)
            if name.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
                placed.append(str(target.relative_to(ROOT)))

    missing = [d for d in EXPECTED_DIRS if not (models_dir / d).exists()]
    if missing:
        print(f"오류: 배포 자산에 모델 폴더가 없다: {missing}", file=sys.stderr)
        return 1
    print(f"배치 완료: {len(placed)}개 파일 → models/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
