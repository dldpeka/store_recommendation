"""
Naver Place 리뷰 태그 크롤링 & 가게 프로필 빌더

네이버 플레이스(m.place.naver.com)의 **리뷰 태그 칩(“…요”)**을 수집해
가게 단위로 태그 빈도를 집계하고, JSON/CSV로 저장합니다.

▶ 실행방법
(1) 창 띄워서 테스트
python make_place_profile.py \
  --place_id 1108161508 \ 📌 📌 크롤링 하려는 가게 id 꼭 바꿔서 넣어주세요📌 📌 
  --store_name "오블리끄" \ 📌 📌 크롤링 하려는 가게이름 꼭 바꿔서 넣어주세요📌 📌 
  --cuisine "파스타","스파게티" 📌 📌 크롤링 하려는 가게 업종 꼭 바꿔서 넣어주세요📌 📌 

(2) 헤드리스 + 리뷰 내부 중복태그는 1회만 집계 + CSV도 저장
python make_place_profile.py \
  --place_id 1108161508 \
  --store_name "오블리끄" \
  --cuisine 파스타 스파게티 \
  --headless --dedup --save_csv

(3) 쉘 인용(quoting)
- macOS/Linux(zsh/bash): 공백/쉼표가 있을 땐 따옴표 권장.  
예) --store_name "오블리끄"

- 📌 📌 Windows PowerShell: ✅ 큰따옴표 ✅ 권장.                        
예) --cuisine "파스타","스파게티"


▶ 산출물 예시
1) outputs/places_json/<place_id>_tags.json
   {
     "place_id": "1108161508",
     "store_name": "오블리끄",
     "cuisine": ["파스타", "스파게티"],  # CLI --cuisine 으로 입력
     "tag_counts": { "맛있어요": 6, "청결해요": 7, ... }
   }

"""


from __future__ import annotations
import time, csv, json, argparse, datetime as dt
from pathlib import Path
from typing import List, Dict, Any
from collections import Counter

# --- Selenium ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# -----------------------------
# URL & Driver
# -----------------------------
def build_review_urls(place_id: str, sort: str = "recent") -> List[str]:
    scopes = ["restaurant", "place"]
    return [
        f"https://m.place.naver.com/{sc}/{place_id}/review/visitor?entry=ple&reviewSort={sort}"
        for sc in scopes
    ]


def make_driver(headless: bool = False) -> webdriver.Chrome:
    opts = webdriver.ChromeOptions()
    if headless:
        opts.add_argument("headless=new")
    opts.add_argument("window-size=1920,1080")
    opts.add_argument("disable-gpu")
    # 무난한 UA
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.implicitly_wait(10)
    return driver

# -----------------------------
# Interactions
# -----------------------------
def click_more_until_end(driver: webdriver.Chrome, max_clicks: int = 50, sleep_sec: float = 0.4):
    # 스크롤/렌더링 유도
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
        time.sleep(0.4)
    except Exception:
        pass

    # 우선 시도할 XPATH (시기/케이스별로 다를 수 있음)
    xpath_candidates = [
        '//*[@id="app-root"]//a[contains(.,"더보기")]',
        '//*[@id="app-root"]//button[contains(.,"더보기")]',
        '//*[@id="app-root"]/div/div/div//a[contains(@href,"review") and contains(.,"더보기")]',
    ]

    clicks = 0
    while clicks < max_clicks:
        clicked = False

        # 1) XPATH 우선 시도
        for xp in xpath_candidates:
            try:
                btn = driver.find_element(By.XPATH, xp)
                if btn.is_displayed():
                    btn.click()
                    clicked = True
                    break
            except (NoSuchElementException, ElementClickInterceptedException):
                continue
            except Exception:
                continue
        if not clicked:
            # 2) CSS 전수조사: '더보기' 텍스트 포함 링크/버튼
            try:
                for el in driver.find_elements(By.CSS_SELECTOR, "a, button"):
                    try:
                        txt = (el.text or "").strip()
                        if "더보기" in txt and el.is_displayed():
                            el.click()
                            clicked = True
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        if not clicked:
            # 더 이상 클릭할 '더보기'가 없다고 판단
            time.sleep(0.6)
            break

        clicks += 1
        time.sleep(sleep_sec)

    return clicks


# -----------------------------
# Parsing
# -----------------------------
# 파일 상단(함수들 모음)에 추가
def parse_cuisine_tokens(tokens) -> list[str]:
    if not tokens:
        return []
    s = " ".join(tokens)                  
    parts = [p.strip().strip('\'"') for p in s.split(",")]  
    # 공백만 넘어온 경우 정리
    out = [p for p in parts if p]
    # 중복 제거(순서 유지)
    seen, dedup = set(), []
    for x in out:
        if x not in seen:
            seen.add(x); dedup.append(x)
    return dedup


def parse_reviews_from_html(html: str, place_id: str, cuisine:list[str],store_name: str) -> List[Dict[str, Any]]:
    from bs4 import BeautifulSoup
    bs = BeautifulSoup(html, "lxml")
    data: List[Dict[str, Any]] = []

    items = bs.select("li.place_app") or bs.select("li")
    for r in items:
        box = r.select_one("div.pui__HLNvmI")
        tags = [s.get_text(strip=True) for s in box.select("span.pui__jhpEyP")] if box else []
        if tags:
            data.append({
                "place_id": str(place_id),
                "cuisine":cuisine or [],
                "store_name": store_name,
                "option_tags": tags,   # 리스트로 저장
            })
    return data

def count_tags(rows: List[Dict[str, Any]], dedup_within_row: bool = False) -> Dict[str, int]:
    c = Counter()
    for r in rows:
        tags = r.get("option_tags") or []
        if not isinstance(tags, (list, tuple)): continue
        items = set(tags) if dedup_within_row else tags
        c.update(t.strip() for t in items if str(t).strip())
    return dict(c)

# -----------------------------
# Save
# -----------------------------
def save_csv(records: List[Dict[str, Any]], place_id: str, cuisine:list[str], store_name: str, out_dir: str = "./outputs") -> str:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(out_dir) / f"naver_place_reviews_{place_id}_{ts}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["place_id","cuisine","store_name","option_tags_json"])
        w.writeheader()
        for row in records:
            tags = row.get("option_tags") or []
            w.writerow({
                "place_id": str(place_id),
                "cuisine": cuisine,
                "store_name": store_name,
                "option_tags_json": json.dumps(tags, ensure_ascii=False),
            })
    return str(path)

def save_store_tag_json(place_id: str, cuisine: list[str],\
                         store_name: str, tag_counts: Dict[str, int],
                        out_dir: str = "./outputs/places_json") -> str:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    doc = {"place_id": str(place_id), "cuisine":cuisine or [], "store_name": store_name, "tag_counts": tag_counts}
    path = Path(out_dir) / f"{place_id}_tags.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return str(path)


# -----------------------------
# Orchestration
# -----------------------------
def fetch_and_build(place_id: str, cuisine:str, store_name: str, sort: str = "recent",
                    max_clicks: int = 50, headless: bool = False,
                    save_csv_also: bool = False, dedup_within_row: bool = False) -> str:
    driver = make_driver(headless=headless)
    try:
        last_err = None
        for url in build_review_urls(place_id, sort=sort):
            try:
                driver.get(url)
                # 요소 기준 대기: 리뷰/태그 컨테이너 등장
                WebDriverWait(driver, 12).until(EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "li.place_app")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.pui__HLNvmI")),
                ))

                clicks = click_more_until_end(driver, max_clicks=max_clicks, sleep_sec=0.4)
                time.sleep(1.0)  # 렌더 여유
                html = driver.page_source

                rows = parse_reviews_from_html(html, place_id=place_id, cuisine=cuisine, store_name=store_name)
                if not rows:
                    continue

                counts = count_tags(rows, dedup_within_row=dedup_within_row)
                out_json = save_store_tag_json(place_id, cuisine, store_name, counts)
                if save_csv_also:
                    save_csv(rows, place_id, cuisine, store_name)

                print(f"[OK] {len(rows)} reviews, {len(counts)} tags -> {out_json} ({clicks} clicks)")
                return out_json
            except Exception as e:
                last_err = e
                continue

        if last_err:
            raise last_err
        raise RuntimeError("리뷰/태그 요소를 찾지 못했어요.")
    finally:
        driver.quit()

# -----------------------------
# CLI
# -----------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Naver Place → tag_counts.json (one-shot)")
    ap.add_argument("--place_id", required=True)
    ap.add_argument("--store_name", required=True)
    ap.add_argument("--cuisine", "--cusine", dest="cuisine", nargs="+",
                help='쉼표/공백 아무거나로 구분: 예) --cuisine "파스타","스파게티" 또는 --cuisine 파스타 스파게티')

    ap.add_argument("--sort", default="recent")
    ap.add_argument("--max_clicks", type=int, default=50)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--save_csv", action="store_true", help="CSV도 함께 저장")
    ap.add_argument("--dedup", action="store_true", help="리뷰 내부 중복 태그는 1번만 카운트")
    args = ap.parse_args(argv)
    cuisine = parse_cuisine_tokens(args.cuisine)

    out = fetch_and_build(
        place_id=args.place_id,
        cuisine=cuisine,
        store_name=args.store_name,
        sort=args.sort,
        max_clicks=args.max_clicks,
        headless=args.headless,
        save_csv_also=args.save_csv,
        dedup_within_row=args.dedup,
    )
    print(out)

if __name__ == "__main__":
    raise SystemExit(main())