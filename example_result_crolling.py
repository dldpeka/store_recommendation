# naver_place_reviews.py
"""
Naver Place Review Crawler (mobile)
-----------------------------------
네이버 플레이스(모바일) 리뷰를 크롤링하는 코드입니다.

📌 핵심 포인트
- 🚨 가게마다 꼭 바꿔야 하는 값: place_id
  - 예시 URL: https://map.naver.com/v5/entry/place/36978606
  - 여기서 36978606 이 place_id 입니다.
  - 크롤링할 때마다 원하는 가게의 place_id로 변경하세요.

📋 기능
- 모바일 리뷰 페이지 열기 (/restaurant, /place 두 경우 모두 시도)
- "더보기" 버튼 자동 클릭 반복
- 닉네임, 리뷰 본문, 작성 날짜, 재방문 여부 추출
- 결과를 CSV(UTF-8-SIG)로 저장

💻 실행 예시
  pip install selenium webdriver-manager beautifulsoup4 lxml

  # 기본 실행
  python naver_place_reviews.py --place_id 36978606

  # 옵션 추가 실행
  python naver_place_reviews.py --place_id 36978606 --max_clicks 60 --headless
  python naver_place_reviews.py --place_id 36978606 --sort recent   # (recent/favorite/relevance)
"""


from __future__ import annotations
import time
import csv
import sys
import argparse
import json
import datetime as dt
from pathlib import Path
from typing import List, Dict

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager


# -----------------------------
# URL & Driver
# -----------------------------
def build_review_urls(place_id: str, sort: str = "recent") -> List[str]:
    """
    업종 스코프에 따라 /restaurant/{id} 또는 /place/{id}가 열릴 수 있어 둘 다 시도.
    """
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
    """
    '더보기' 버튼을 최대 max_clicks 번까지 반복 클릭. 페이지/시점에 따라 DOM이 달라질 수 있어
    여러 셀렉터 전략을 순차적으로 시도.
    """
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
def parse_reviews_from_html(html: str):
    from bs4 import BeautifulSoup
    bs = BeautifulSoup(html, "lxml")
    data = []

    # 리뷰 리스트 항목들
    items = bs.select("li.place_app") or bs.select("li")  # fallback

    for r in items:
        # ✅ 닉네임
        nickname = r.select_one("span.pui__NMi-Dp")
        nickname = nickname.get_text(strip=True) if nickname else ""

        # ✅ 본문
        content = r.select_one("div.pui__vn15t2")
        content = content.get_text("\n", strip=True) if content else ""

        # ✅ 해시태그(…요) – 간단 버전
        box = r.select_one("div.pui__HLNvmI")
        tag = [s.get_text(strip=True) for s in box.select("span.pui__jhpEyP")] if box else []
        # (선택) 중복 제거가 필요하면 다음 한 줄만 추가
        # tags = list(dict.fromkeys(tags))


        if nickname or content or tag:
            data.append({
                "nickname": nickname,
                "content": content,
                 "tags_json": json.dumps(tag, ensure_ascii=False)
            })

    return data




# -----------------------------
# Save
# -----------------------------
def save_csv(records: List[Dict[str, str]], place_id: str, out_dir: str = "./outputs") -> str:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(out_dir) / f"naver_place_reviews_{place_id}_{ts}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["nickname", "content", "tags_json"])
        w.writeheader()
        for row in records:
            w.writerow(row)
    return str(path)


# -----------------------------
# Orchestration
# -----------------------------
def fetch_reviews(place_id: str, sort: str = "recent", max_clicks: int = 50, headless: bool = False) -> str:
    driver = make_driver(headless=headless)
    try:
        last_err = None
        for url in build_review_urls(place_id, sort=sort):
            try:
                driver.get(url)
                time.sleep(1.0)

                # 리뷰 페이지 여부 대략 판별
                if "review" not in driver.current_url.lower():
                    continue

                clicks = click_more_until_end(driver, max_clicks=max_clicks, sleep_sec=0.4)
                # 로딩 여유
                time.sleep(1.2)

                html = driver.page_source
                records = parse_reviews_from_html(html)
                if records:
                    out = save_csv(records, place_id)
                    print(f"[OK] {len(records)} reviews saved ({clicks} clicks) -> {out}")
                    return out
            except Exception as e:
                last_err = e
                continue

        # 모든 후보 실패
        if last_err:
            raise last_err
        raise RuntimeError("리뷰 페이지 접근 실패")
    finally:
        driver.quit()


# -----------------------------
# CLI
# -----------------------------
def main(argv=None):
    p = argparse.ArgumentParser(description="Naver Place Review Crawler (mobile)")
    p.add_argument("--place_id", required=True, help="네이버 플레이스 ID (예: 36978606)")
    p.add_argument("--sort", default="recent", help="정렬 (recent/favorite 등 페이지가 허용하는 값)")
    p.add_argument("--max_clicks", type=int, default=50, help="더보기 최대 클릭 횟수")
    p.add_argument("--headless", action="store_true", help="브라우저 창 없이 실행")
    args = p.parse_args(argv)

    out = fetch_reviews(
        place_id=args.place_id,
        sort=args.sort,
        max_clicks=args.max_clicks,
        headless=args.headless,
    )
    print(out)


if __name__ == "__main__":
    sys.exit(main())


