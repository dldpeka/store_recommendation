# croling_naverplace
네이버 플레이스(지도) 상세페이지의 **리뷰(방문자 리뷰)**를 자동으로 수집하는 파이썬 크롤러입니다. Selenium으로 동적 로딩/‘더보기’ 버튼 클릭/스크롤을 처리하고, BeautifulSoup으로 DOM을 파싱해 작성자 닉네임, 본문, 태그/아이콘, 이미지 URL 등을 추출해 JSON으로 저장합니다.

🚨 꼭 알아야 할 것
가게마다 place_id 값이 다릅니다.
실행할 때마다 크롤링할 가게의 place_id를 확인해서 넣어야 합니다.
URL 예시:
https://map.naver.com/v5/entry/place/123456789?c=15,0,0,0,dh
👉 여기서 123456789가 place_id 입니다.

⚙️ 설치 방법
필요한 라이브러리
pip install selenium beautifulsoup4 lxml

▶︎ 실행 방법
python crawler.py --place_id 123456789 --sort recent --max_clicks 50 --headless true --sleep_sec 0.8 --out_dir data

주요 옵션
--place_id : (필수) 크롤링할 가게의 ID
--sort : 리뷰 정렬 기준 (recent = 최신순)
--max_clicks : ‘더보기/스크롤’ 시도 횟수 (기본 50)
--headless : 브라우저 창 숨김 여부 (true/false)
--sleep_sec : 클릭 간격 대기시간 (초 단위, 기본 0.8)
--out_dir : 결과 저장 폴더 (기본 data/)

📦 출력 결과
저장 형식: JSON Lines (.jsonl)
한 줄 = 한 개 리뷰
{"nickname": "홍길동", "content": "음식이 맛있어요!", "tags_icon": ["가성비"]}

⚠️ 주의사항
네이버 이용약관/로봇배제규약을 반드시 준수하세요.
개인 정보(닉네임, 얼굴 등)는 무단으로 공개/상업적 활용하지 마세요.
DOM 구조가 바뀌면 CSS/XPath 선택자를 수정해야 합니다.
