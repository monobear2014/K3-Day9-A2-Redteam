"""Dong goi output/ thanh zip nop bai, co kiem tra truoc khi nen.

    python make_submission.py           # tao submission.zip (dang output/EC_XXX.json)
    python make_submission.py --flat    # 50 JSON nam thang o goc zip
    python make_submission.py --check   # chi kiem tra, khong tao zip

README muc 8: "Zip phai chua dung 50 JSON tu EC_001.json den EC_050.json;
khong chua cac file la khac". Script tu choi tao zip neu co bat ky loi nao -
tha khong tao con hon nop mot bo hong roi an hard gate.

README muc 9.2: KHONG duoc dua source code, .env hay file audit vao zip nay.
"""

import argparse
import json
import sys
import zipfile
from pathlib import Path

from src import config
from src.schemas import CaseOutput

EXPECTED = [f"EC_{i:03d}" for i in range(1, 51)]


def check() -> tuple[list[Path], list[str]]:
    """Tra ve (danh sach file hop le, danh sach loi)."""
    errors: list[str] = []
    out_dir = config.OUTPUT_DIR

    if not out_dir.exists():
        return [], [f"Khong thay thu muc {out_dir}"]

    # --- File la ---
    strays = [
        p.name
        for p in out_dir.iterdir()
        if p.name != ".gitkeep" and not (p.is_file() and p.suffix == ".json")
    ]
    if strays:
        errors.append(f"Co file la trong output/: {strays}")

    # --- Thieu / thua ---
    present = {p.stem for p in out_dir.glob("*.json")}
    missing = [c for c in EXPECTED if c not in present]
    extra = sorted(present - set(EXPECTED))
    if missing:
        errors.append(f"Thieu {len(missing)} case: {missing[:8]}{'...' if len(missing) > 8 else ''}")
    if extra:
        errors.append(f"Thua {len(extra)} file khong thuoc EC_001..EC_050: {extra[:8]}")

    # --- Validate tung file ---
    files: list[Path] = []
    for cid in EXPECTED:
        p = out_dir / f"{cid}.json"
        if not p.exists():
            continue
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{cid}: JSON hong - {e}")
            continue

        if raw.get("case_id") != cid:
            errors.append(f"{cid}: case_id ben trong la {raw.get('case_id')!r}, khong khop ten file")

        try:
            o = CaseOutput(**raw)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{cid}: sai schema - {str(e)[:120]}")
            continue

        fr = o.financial_resolution
        if fr.recommended_refund_brl < 0:
            errors.append(f"{cid}: refund am ({fr.recommended_refund_brl})")
        if (fr.recommended_refund_brl > 0) != (o.assessment.case_status == "action_required"):
            errors.append(
                f"{cid}: case_status={o.assessment.case_status} khong khop refund={fr.recommended_refund_brl}"
            )
        if len(o.evidence_ids) > config.MAX_EVIDENCE:
            errors.append(f"{cid}: {len(o.evidence_ids)} evidence, vuot gioi han")
        if not o.resolution_actions:
            errors.append(f"{cid}: khong co resolution_actions")
        for k, v in o.affected_entities.model_dump().items():
            if len(v) > config.MAX_IDS_PER_ENTITY:
                errors.append(f"{cid}: {k} co {len(v)} ID, vuot gioi han 5")
        files.append(p)

    return files, errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flat", action="store_true", help="50 JSON nam thang o goc zip")
    ap.add_argument("--check", action="store_true", help="Chi kiem tra, khong tao zip")
    ap.add_argument("--out", default="submission.zip")
    args = ap.parse_args()

    files, errors = check()
    print(f"File hop le : {len(files)}/50")

    if errors:
        print(f"\nLOI ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
        print("\nKHONG tao zip. Sua het loi roi chay lai.")
        return 1

    print("Kiem tra   : tat ca pass")

    if args.check:
        return 0

    zip_path = config.ROOT / args.out
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            # Mac dinh giu dang output/EC_XXX.json - khop voi cach input.zip
            # cua de bai duoc dong goi (input/EC_001.json).
            arcname = p.name if args.flat else f"output/{p.name}"
            z.write(p, arcname)

    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
    print(f"\nDa tao     : {zip_path}")
    print(f"Noi dung   : {len(names)} file, dang {names[0]!r}")
    print(f"Kich thuoc : {zip_path.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
