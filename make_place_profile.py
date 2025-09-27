#호출법#
#python make_place_profile.py --place_id 31751923 --store_name "신통치킨 단국대점" --cuisine "치킨","닭강정" --mode summary#


# make_place_profile.py — Naver Place 태그 수집 (FAST: 요약 패널 기본)
from __future__ import annotations
import time, csv, json, argparse, datetime as dt, re
from pathlib import Path
from typing import List, Dict, Any
from collections import Counter

# --- Selenium ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# =========================================================
# 설정
DEFAULT_MODE = "summary"     # "summary" = 요약 패널(빠름/정확), "chips" = 모바일 리뷰칩 전수(느리지만 상세)
# =========================================================


# -----------------------------
# 공통: 드라이버/유틸
# -----------------------------
def make_driver(headless: bool = False) -> webdriver.Chrome:
    opts = webdriver.ChromeOptions()
    if headless:
        opts.add_argument("headless=new")
    opts.add_argument("window-size=1920,1080")
    opts.add_argument("disable-gpu")
    # 속도 ↑ : 이미지/알림 차단, 빠른 로딩전략
    opts.add_argument("--blink-settings=imagesEnabled=false")
    opts.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2,
        "profile.managed_default_content_settings.images": 2,
    })
    opts.page_load_strategy = "eager"
    # 무난한 UA
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.implicitly_wait(8)
    driver.set_page_load_timeout(20)
    return driver


def parse_cuisine_tokens(tokens) -> list[str]:
    if not tokens:
        return []
    s = " ".join(tokens)
    parts = [p.strip().strip('\'"') for p in s.split(",")]
    out = [p for p in parts if p]
    seen, dedup = set(), []
    for x in out:
        if x not in seen:
            seen.add(x); dedup.append(x)
    return dedup


def save_store_tag_json(place_id: str, cuisine: list[str], store_name: str,
                        tag_counts: Dict[str, int], out_dir: str = "./outputs/places_json") -> str:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    doc = {"place_id": str(place_id), "cuisine": cuisine or [], "store_name": store_name, "tag_counts": tag_counts}
    path = Path(out_dir) / f"{place_id}_tags.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return str(path)


# =========================================================
# 모드 A) SUMMARY — 데스크톱 요약 패널(“이런 점이 좋았어요”) 직접 파싱
# =========================================================
def goto_desktop_reviews(driver: webdriver.Chrome, place_id: str):
    url = f"https://map.naver.com/p/entry/place/{place_id}"
    driver.get(url)

    # (케이스에 따라) entryIframe 내부일 수 있음 → 프레임 진입 시도
    try:
        iframe = driver.find_element(By.CSS_SELECTOR, "iframe#entryIframe")
        driver.switch_to.frame(iframe)
    except Exception:
        pass

    # 리뷰 탭 클릭
    try:
        tabs = driver.find_elements(By.XPATH, "//*[normalize-space(text())='리뷰']")
        for t in tabs:
            try:
                if t.is_displayed():
                    driver.execute_script("arguments[0].click();", t)
                    break
            except Exception:
                continue
    except Exception:
        pass

    # '이런 점이 좋았어요' 섹션 등장 대기
    WebDriverWait(driver, 12).until(EC.presence_of_element_located(
        (By.XPATH, "//*[contains(normalize-space(.),'이런 점이 좋았어요')]")
    ))
    time.sleep(0.6)


def expand_summary_all(driver, max_clicks: int = 4):
    """요약 패널(이런 점이 좋았어요) 리스트를 화살표/더보기로 끝까지 펼치기"""
    import time
    sec = driver.find_element(
        By.XPATH,
        "//*[contains(normalize-space(.),'이런 점이 좋았어요')]/ancestor::*[self::div or self::section][1]"
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", sec)
    time.sleep(0.3)

    def li_count():
        try:
            return len(sec.find_elements(By.CSS_SELECTOR, "li"))
        except Exception:
            return 0

    prev = li_count()
    for _ in range(max_clicks):
        clicked = False

        # '더보기/펼치기' 텍스트 버튼
        for xp in [".//button[contains(.,'더보기')]",
                   ".//a[contains(.,'더보기')]",
                   ".//button[contains(.,'펼치기')]",
                   ".//a[contains(.,'펼치기')]",
                   ".//*[@aria-label and (contains(@aria-label,'더보기') or contains(@aria-label,'펼치기'))]"]:
            try:
                el = sec.find_element(By.XPATH, xp)
                if el.is_displayed():
                    driver.execute_script("arguments[0].click();", el)
                    clicked = True
                    break
            except Exception:
                pass

        # 폴백: 섹션 내 아이콘(chevron) 버튼 추정
        if not clicked:
            try:
                btns = sec.find_elements(By.XPATH, ".//*[name()='svg' or name()='path']/ancestor::button")
                for b in btns:
                    if b.is_displayed():
                        driver.execute_script("arguments[0].click();", b)
                        clicked = True
                        break
            except Exception:
                pass

        time.sleep(0.6)
        now = li_count()
        if not clicked or now <= prev:
            break
        prev = now


def parse_summary_counts_from_html(html: str) -> Dict[str, int]:
    """
    '이런 점이 좋았어요' 카드의 라벨/숫자 쌍을 파싱.
    난수 클래스에 의존하지 않고 텍스트 기반으로 안전 수집.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    # 섹션 찾기
    section = None
    for el in soup.find_all(string=lambda x: isinstance(x, str) and "이런 점이 좋았어요" in x):
        cand = el
        for _ in range(3):
            cand = cand.parent
            if not cand:
                break
            if cand.name in ("section", "div"):
                section = cand
                break
        if section:
            break
    if section is None:
        section = soup

    counts: Dict[str, int] = {}
    items = section.find_all("li")
    if not items:
        items = soup.find_all("li")

    rm_phrase = re.compile(r"이\s*키워드를\s*선택한\s*인원")
    for li in items:
        txt = " ".join(li.stripped_strings)
        if not txt:
            continue
        mnum = re.search(r"(\d+)\s*$", txt)
        if not mnum:
            continue
        num = int(mnum.group(1))
        left = re.sub(r"\s*\d+\s*$", "", txt)           # 끝 숫자 제거
        left = rm_phrase.sub("", left).strip()          # ‘이 키워드를 선택한 인원’ 제거

        # 큰따옴표 안 문구가 있으면 그걸 라벨로
        mquote = re.search(r"[“\"]\s*(.+?)\s*[”\"]", left)
        label = (mquote.group(1) if mquote else left).strip()

        if 1 <= len(label) <= 30 and "이런 점이 좋았어요" not in label:
            counts[label] = num

    return counts


def fetch_summary(place_id: str, cuisine: list[str], store_name: str,
                  headless: bool = False) -> str:
    driver = make_driver(headless=headless)
    try:
        goto_desktop_reviews(driver, place_id)
        expand_summary_all(driver)                 # ✅ 요약 리스트 끝까지 펼치기
        html = driver.page_source
        tag_counts = parse_summary_counts_from_html(html)
        if not tag_counts:
            raise RuntimeError("요약 패널을 파싱하지 못했어요.")
        out_json = save_store_tag_json(place_id, cuisine, store_name, tag_counts)
        print(f"[OK/SUMMARY] {store_name} ({place_id}) -> {out_json}  ({len(tag_counts)} tags)")
        return out_json
    finally:
        driver.quit()


# =========================================================
# 모드 B) CHIPS — 모바일(m.place) 리뷰칩 전수(느림, 상세)
# =========================================================
def build_review_urls(place_id: str, sort: str = "recent") -> List[str]:
    return [
        f"https://m.place.naver.com/{sc}/{place_id}/review/visitor?entry=ple&reviewSort={sort}"
        for sc in ("restaurant", "place")
    ]


def click_more_until_end(driver: webdriver.Chrome, max_clicks: int = 100, sleep_sec: float = 0.5):
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
        time.sleep(0.3)
    except Exception:
        pass

    def find_more_btn():
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, "a,button"):
                t = (el.text or "").strip()
                if (("더보기" in t) or ("후기 더보기" in t)) and el.is_displayed():
                    return el
        except Exception:
            return None
        return None

    clicks, same_height = 0, 0
    last_h = driver.execute_script("return document.body.scrollHeight")
    last_activity = time.time()

    while clicks < max_clicks:
        btn = find_more_btn()
        if btn:
            try:
                driver.execute_script("arguments[0].click();", btn)
                clicks += 1
                last_activity = time.time()
                time.sleep(sleep_sec)
                continue
            except Exception:
                pass

        try:
            driver.execute_script("window.scrollBy(0, 1400);")
        except Exception:
            pass
        time.sleep(sleep_sec)

        h = driver.execute_script("return document.body.scrollHeight")
        if h <= last_h:
            same_height += 1
        else:
            same_height = 0
            last_h = h
            last_activity = time.time()

        if same_height >= 4:
            break
        if time.time() - last_activity > 40:
            break

    return clicks


def expand_all_chip_more(driver, max_tries: int = 3):
    plus_pat = re.compile(r"^\+\d+$")
    for _ in range(max_tries):
        clicked_any = False
        for el in driver.find_elements(By.CSS_SELECTOR, "a,button,span"):
            try:
                txt = (el.text or "").strip()
                if plus_pat.match(txt) and el.is_displayed():
                    driver.execute_script("arguments[0].click();", el)
                    clicked_any = True
                    time.sleep(0.2)
            except Exception:
                continue
        if not clicked_any:
            break


def parse_reviews_from_html(html: str, place_id: str, cuisine: list[str], store_name: str) -> List[Dict[str, Any]]:
    from bs4 import BeautifulSoup
    bs = BeautifulSoup(html, "lxml")
    data: List[Dict[str, Any]] = []

    items = bs.select("li.place_app") or bs.select("li")
    chip_pat = re.compile(r"^[가-힣\s]{2,20}요$")

    for r in items:
        box = r.select_one("div.pui__HLNvmI") or r
        tags = [s.get_text(strip=True) for s in box.select("span.pui__jhpEyP")]
        if not tags:
            tags = [s.get_text(strip=True) for s in box.select("span")]
            tags = [t for t in tags if chip_pat.match(t)]
        if tags:
            uniq = list(dict.fromkeys(t for t in tags if t))
            if uniq:
                data.append({
                    "place_id": str(place_id),
                    "cuisine": cuisine or [],
                    "store_name": store_name,
                    "option_tags": uniq,
                })
    return data


def count_tags(rows: List[Dict[str, Any]], dedup_within_row: bool = True) -> Dict[str, int]:
    c = Counter()
    for r in rows:
        tags = r.get("option_tags") or []
        items = set(tags) if dedup_within_row else tags
        c.update(t.strip() for t in items if str(t).strip())
    return dict(c)


def save_csv(records: List[Dict[str, Any]], place_id: str, cuisine: list[str], store_name: str,
             out_dir: str = "./outputs") -> str:
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


def fetch_chips(place_id: str, cuisine: list[str], store_name: str,
                sort: str = "recent", max_clicks: int = 60,
                headless: bool = False, save_csv_also: bool = False,
                dedup_within_row: bool = True) -> str:
    driver = make_driver(headless=headless)
    all_rows: List[Dict[str, Any]] = []
    try:
        last_err = None
        url_count = 0
        for url in build_review_urls(place_id, sort=sort):
            try:
                driver.get(url)
                WebDriverWait(driver, 12).until(EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "li.place_app")),
                    EC.presence_of_element_located((By.XPATH, '//*[@id="app-root"]//*[contains(.,"리뷰")]')),
                ))
                click_more_until_end(driver, max_clicks=max_clicks, sleep_sec=0.5)
                expand_all_chip_more(driver)
                time.sleep(0.6)
                html = driver.page_source
                rows = parse_reviews_from_html(html, place_id=place_id, cuisine=cuisine, store_name=store_name)
                if rows:
                    all_rows.extend(rows); url_count += 1
            except Exception as e:
                Path("outputs/debug").mkdir(parents=True, exist_ok=True)
                with open(f"outputs/debug/{place_id}_{int(time.time())}.html", "w", encoding="utf-8") as df:
                    df.write(driver.page_source)
                last_err = e
                continue

        if not all_rows:
            if last_err:
                raise last_err
            raise RuntimeError("리뷰/태그 요소를 찾지 못했어요.")
        counts = count_tags(all_rows, dedup_within_row=dedup_within_row)
        out_json = save_store_tag_json(place_id, cuisine, store_name, counts)
        if save_csv_also:
            save_csv(all_rows, place_id, cuisine, store_name)
        total_chips = sum(len(r.get("option_tags", [])) for r in all_rows)
        print(f"[OK/CHIPS] {store_name} ({place_id}) -> {out_json}  ({total_chips} chips, {len(counts)} tags, {url_count} urls)")
        return out_json
    finally:
        driver.quit()


# =========================================================
# 단일 호출 진입점 (배치에서도 이 함수를 씀)
# =========================================================
def fetch_and_build(place_id: str, cuisine: list[str], store_name: str,
                    sort: str = "recent", max_clicks: int = 60,
                    headless: bool = False, save_csv_also: bool = False,
                    dedup_within_row: bool = True, mode: str | None = None) -> str:
    mode = (mode or DEFAULT_MODE).lower()
    if mode == "summary":
        return fetch_summary(place_id, cuisine, store_name, headless=headless)
    else:
        return fetch_chips(place_id, cuisine, store_name, sort=sort, max_clicks=max_clicks,
                           headless=headless, save_csv_also=save_csv_also, dedup_within_row=dedup_within_row)


# -----------------------------
# CLI (단일 테스트)
# -----------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Naver Place → tag_counts.json (summary/chips)")
    ap.add_argument("--place_id", required=True)
    ap.add_argument("--store_name", required=True)
    ap.add_argument("--cuisine", "--cusine", dest="cuisine", nargs="+",
                    help='쉼표/공백 아무거나로 구분: 예) --cuisine "파스타","스파게티" 또는 --cuisine 파스타 스파게티')
    ap.add_argument("--mode", choices=["summary","chips"], default=DEFAULT_MODE)
    ap.add_argument("--sort", default="recent")
    ap.add_argument("--max_clicks", type=int, default=60)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--save_csv", action="store_true", help="(chips 모드) CSV도 함께 저장")
    ap.add_argument("--dedup", action="store_true", help="(chips 모드) 리뷰 내부 중복 태그 1회만 카운트")
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
        dedup_within_row=args.dedup or True,
        mode=args.mode,
    )
    print(out)


if __name__ == "__main__":
    raise SystemExit(main())
