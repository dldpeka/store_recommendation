#----적용법---#
# 1) place_list를 먼저 만들어야함.
# 파일 형식은 .csv로 저장
#해더 : name	place_id	cuisine
#값 : 또봉이통닭 용인단국대점	37746393	치킨,닭강정

#순서가 create_profiles_final.py를 실행-> place_list 읽기-> 각 행마다 make_place_profile 실행->각 place마다 json 생성

#------------------#
# 2) create_profiles_final.py 코드 실행
#------------------#
# create_profiles_final.py — place_list.csv 일괄 실행 (요약패널 FAST 모드 기본)
from __future__ import annotations
import csv, sys, time, random, datetime as dt
from pathlib import Path

import make_place_profile as mpp  # 방금 교체한 파일을 사용

# ===== 사용자 설정 =====
PLACE_LIST_PATH = Path("place_list.csv")
OUTPUT_DIR      = Path("./outputs/places_json")

# make_place_profile 옵션
MODE               = "summary"   # "summary"(빠름/정확) 기본, 실패시 chips로 폴백 옵션 아래
HEADLESS           = True        # 창 없이 빠르게 (문제시 False로)
SAVE_CSV_ALSO      = False       # chips 모드일 때만 의미 있음
DEDUP_WITHIN_ROW   = True
MAX_CLICKS         = 60          # chips 모드에서만 의미 있음
SORT               = "recent"

# 기타
SKIP_IF_EXISTS         = True    # 이미 생성된 JSON은 건너뛰기
FALLBACK_TO_CHIPS_ON_FAIL = True # summary 실패 시 chips로 1회 재시도(느려질 수 있음)
SLEEP_BETWEEN_SEC      = (0.6, 1.3)  # 가게 간 랜덤 딜레이
# =====================


def _open_csv_with_fallback(path: Path):
    encodings = ["utf-8-sig", "cp949", "utf-8"]
    last_err = None
    for enc in encodings:
        try:
            f = path.open("r", encoding=enc, newline="")
            reader = csv.DictReader(f)
            _ = reader.fieldnames  # 강제 로드
            print(f"[INFO] place_list.csv 인코딩: {enc}")
            return f, reader
        except Exception as e:
            last_err = e
            try:
                f.close()
            except Exception:
                pass
            continue
    raise last_err or UnicodeError("CSV 인코딩 감지 실패 (UTF-8/CP949로 저장해 주세요).")


def run(start: int | None = None, end: int | None = None) -> int:
    if not PLACE_LIST_PATH.exists():
        print(f"[ERR] CSV 없음: {PLACE_LIST_PATH.resolve()}")
        return 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_dir = Path("outputs") / "batch_logs"
    summary_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_csv = summary_dir / f"batch_summary_{ts}.csv"

    f, reader = _open_csv_with_fallback(PLACE_LIST_PATH)

    total = ok = fail = skip = 0
    with f, summary_csv.open("w", encoding="utf-8-sig", newline="") as sf:
        writer = csv.DictWriter(sf, fieldnames=[
            "place_id","store_name","cuisine_raw","json_path","status","error","mode_used"
        ])
        writer.writeheader()

        rows = list(reader)
        if start is not None or end is not None:
            s = 0 if start is None else max(int(start), 0)
            e = len(rows) if end is None else max(int(end), 0)
            rows = rows[s:e]

        print(f">>> 총 {len(rows)}개 가게 처리 시작 (MODE={MODE}, HEADLESS={HEADLESS})")

        for row in rows:
            total += 1
            place_id = (row.get("place_id") or "").strip()
            store_name = (row.get("store_name") or row.get("name") or "").strip()
            cuisine_raw = (row.get("cuisine") or "").strip()
            cuisine_tokens = mpp.parse_cuisine_tokens([cuisine_raw]) if cuisine_raw else []

            if not place_id or not store_name:
                fail += 1
                writer.writerow({
                    "place_id": place_id, "store_name": store_name,
                    "cuisine_raw": cuisine_raw, "json_path": "",
                    "status": "FAIL", "error": "place_id/store_name 누락", "mode_used": ""
                })
                print(f"[SKIP] 잘못된 행: {row}")
                continue

            out_path = OUTPUT_DIR / f"{place_id}_tags.json"
            if SKIP_IF_EXISTS and out_path.exists():
                skip += 1
                writer.writerow({
                    "place_id": place_id, "store_name": store_name,
                    "cuisine_raw": cuisine_raw, "json_path": str(out_path),
                    "status": "SKIP", "error": "", "mode_used": "exists"
                })
                print(f"[SKIP] 이미 존재: {place_id} -> {out_path.name}")
                continue

            mode_used = MODE
            try:
                # 1차: summary (빠름/정확)
                out_json = mpp.fetch_and_build(
                    place_id=place_id,
                    cuisine=cuisine_tokens,
                    store_name=store_name,
                    sort=SORT,
                    max_clicks=MAX_CLICKS,
                    headless=HEADLESS,
                    save_csv_also=SAVE_CSV_ALSO,
                    dedup_within_row=DEDUP_WITHIN_ROW,
                    mode=MODE,
                )
            except Exception as e:
                # 필요 시 chips로 폴백(느릴 수 있음)
                if FALLBACK_TO_CHIPS_ON_FAIL and MODE != "chips":
                    try:
                        mode_used = "chips"
                        print(f"[RETRY→chips] {store_name} ({place_id}) - 사유: {type(e).__name__}")
                        out_json = mpp.fetch_and_build(
                            place_id=place_id,
                            cuisine=cuisine_tokens,
                            store_name=store_name,
                            sort=SORT,
                            max_clicks=MAX_CLICKS,
                            headless=HEADLESS,
                            save_csv_also=SAVE_CSV_ALSO,
                            dedup_within_row=DEDUP_WITHIN_ROW,
                            mode="chips",
                        )
                    except Exception as e2:
                        fail += 1
                        writer.writerow({
                            "place_id": place_id, "store_name": store_name,
                            "cuisine_raw": cuisine_raw, "json_path": "",
                            "status": "FAIL", "error": f"{type(e2).__name__}: {e2}", "mode_used": "chips"
                        })
                        print(f"[FAIL] {store_name} ({place_id}) -> {type(e2).__name__}: {e2}")
                        time.sleep(random.uniform(*SLEEP_BETWEEN_SEC))
                        continue
                else:
                    fail += 1
                    writer.writerow({
                        "place_id": place_id, "store_name": store_name,
                        "cuisine_raw": cuisine_raw, "json_path": "",
                        "status": "FAIL", "error": f"{type(e).__name__}: {e}", "mode_used": mode_used
                    })
                    print(f"[FAIL] {store_name} ({place_id}) -> {type(e).__name__}: {e}")
                    time.sleep(random.uniform(*SLEEP_BETWEEN_SEC))
                    continue

            ok += 1
            writer.writerow({
                "place_id": place_id, "store_name": store_name,
                "cuisine_raw": cuisine_raw, "json_path": out_json,
                "status": "OK", "error": "", "mode_used": mode_used
            })
            print(f"[OK] {store_name} ({place_id}) -> {out_json}  [mode={mode_used}]")

            time.sleep(random.uniform(*SLEEP_BETWEEN_SEC))

    print("-" * 60)
    print(f"Done. 총 {total} / 성공 {ok} / 실패 {fail} / 건너뜀 {skip}")
    print(f"요약 CSV: {summary_csv.resolve()}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    print(">>> create_profiles_final: START")
    rc = run()
    sys.exit(rc)
