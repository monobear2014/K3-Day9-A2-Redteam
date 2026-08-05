"""Entrypoint: chay toan bo 50 case.

    python run.py                # chay tat ca input/*.json
    python run.py --case EC_001  # chay 1 case de debug
    python run.py --no-llm       # chi chay deterministic, khong goi LLM (test nhanh)
"""

import argparse
import sys
import time

from tqdm import tqdm

from src import config
from src.pipeline import process_case
from src.trace import Tracer, write_metadata


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", help="Chi chay mot case, vd: EC_001")
    ap.add_argument(
        "--no-llm",
        action="store_true",
        help="Bo qua LLM, chi dung deterministic (de smoke test)",
    )
    args = ap.parse_args()

    if args.no_llm:
        config.USE_LLM = False

    if not config.INPUT_DIR.exists():
        print(f"Khong thay thu muc input: {config.INPUT_DIR}")
        return 1

    files = sorted(config.INPUT_DIR.glob("EC_*.json"))
    if args.case:
        files = [f for f in files if f.stem == args.case]
    if not files:
        print("Khong co file input nao khop. input/ da co EC_001.json ... chua?")
        return 1

    print(f"Model   : {config.MODEL_NAME} ({config.MODEL_PARAMETER_SIZE})")
    print(f"Endpoint: {config.LLM_BASE_URL if config.USE_LLM else '(--no-llm: tat LLM)'}")
    print(f"Cases   : {len(files)}\n")

    tracer = Tracer()
    started = time.time()
    ok = 0
    for path in tqdm(files, desc="cases", unit="case"):
        try:
            process_case(path, tracer)
            ok += 1
        except Exception as exc:  # noqa: BLE001 - mot case hong khong duoc keo do ca run
            print(f"\n[LOI] {path.stem}: {type(exc).__name__}: {exc}", file=sys.stderr)

    elapsed = time.time() - started
    write_metadata(elapsed, len(files))

    print(f"\nXong {ok}/{len(files)} case trong {elapsed:.1f}s")
    print(f"Output  : {config.OUTPUT_DIR}")
    print(f"Trace   : {config.TRACE_PATH}")
    print(f"Metadata: {config.METADATA_PATH}")
    return 0 if ok == len(files) else 1


if __name__ == "__main__":
    raise SystemExit(main())
