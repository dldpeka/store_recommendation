import streamlit as st
from neo4j import GraphDatabase, basic_auth
from openai import OpenAI
import os 
import pandas as pd
import uuid

# -------------------------
# ⭐️⭐️⭐️ API연걸 설정 + Neo4j 설정⭐️⭐️⭐️
# -------------------------
# API 드라이버 
driver = GraphDatabase.driver(
    "neo4j+s://fab02137.databases.neo4j.io",
    auth=basic_auth("neo4j", "JWRGt5DQnt-XyLAfcuYvwAJa1qbcxvhLdMhVJQOCXtA")
)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -------------------------
# ⭐ Neo4j Aura 연결 테스트 ⭐
# -------------------------
try:
    driver.verify_connectivity()
    print("✅ Neo4j Aura 연결 성공!")
except Exception as e:
    print("❌ Neo4j Aura 연결 실패:", repr(e))


# Neo4j 유틸 함수
def run_query(cypher, params=None):
    with driver.session() as s:
        return s.run(cypher, **(params or {})).data()


# -------------------------
# ⭐️⭐️⭐️ 기본설정 (배경 + 버튼 + 폰트 등) ⭐️⭐️⭐️
# -------------------------
import base64

# 동물의 숲 폰트 설정
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ✅ 폰트 / 배경 이미지 경로 (레포 기준)
font_path= BASE_DIR / "Asia신디나루M.ttf"       # 깃허브 최상단에 둘 때
image_paath= BASE_DIR / "배경화면1.png"

# 2. CSS로 삽입
def load_custom_font():
    import base64

    font_path = "UI_build/Asia신디나루M.ttf"
    
    with open(font_path, "rb") as f:
        font_bytes = f.read()
    encoded_font = base64.b64encode(font_bytes).decode()

    css = f"""
    <style>
    @font-face {{
        font-family: 'ACNH_KR';
        src: url(data:font/ttf;base64,{encoded_font}) format('truetype');
        font-weight: normal;
        font-style: normal;
    }}

    /* === 전체 전역 폰트 적용 === */
    html, body, div, span, p, h1, h2, h3, h4, h5, h6,
    input, textarea, button,
    .stMarkdown, .stTextInput, .stButton > button,
    .stCaption, .stTextArea, .stText, label {{
        font-family: 'ACNH_KR', sans-serif !important;
    }}

    /* Streamlit 기본 제목도 강제 적용 */
    .stAppViewContainer h1, 
    .stAppViewContainer h2, 
    .stAppViewContainer h3 {{
        font-family: 'ACNH_KR', sans-serif !important;
        font-weight: normal !important;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


   


# 동물의 숲 배경 설정
def set_background(image_path):
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    page_bg = f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background: url("data:image/png;base64,{encoded}") no-repeat center center fixed;
        background-size: cover;
    }}
    [data-testid="stHeader"] {{
        background: rgba(0,0,0,0); 
    }}
    [data-testid="stToolbar"] {{
        right: 2rem;
    }}
    </style>
    """

    st.markdown(page_bg, unsafe_allow_html=True)

# -------------------------
# ⭐️⭐️⭐️ 로그인 기본 설정 ⭐️⭐️⭐️
# -------------------------
login_css = """
<style>

/* 전체 화면을 아래로 내리기 */
.login-container {
    margin-top: 130px;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center; 
}



/* 로그인 박스 (주민등록 카드 스타일) */
.acnh-card {
    width: 420px;
    background: rgba(255, 250, 235, 0.92);
    border: 4px solid #f5d273;
    border-radius: 28px;
    box-shadow: 0 6px 0 #d9b45f;
    padding: 22px 26px;
    backdrop-filter: blur(4px);
}


/* 잎사귀 아이콘 */
.acnh-leaf {
    width: 50px;
    margin-bottom: 50px;
    display: block;
    margin-left: auto;
    margin-right: auto;
}

/* 제목 */
.acnh-title {
    text-align: center;
    font-size: 25px;
    font-weight: 700;
    color: #3e5f2f;
    text-shadow: 1px 1px 0px #ffffff;
    margin-bottom: 22px;
}


/* 입력창 */
.acnh-input {
    margin-top: 18px; 
}

.acnh-input input {
    border-radius: 16px !important;
    border: 3px solid #7fb55e !important;
    padding: 17px 18px !important;
    background: rgba(255,255,255,0.95) !important;
    font-size: 15px !important;
    margin-top: 10px; 
}


/* 버튼 */
.acnh-button > button {
    width: 100%;
    border-radius: 16px !important;
    padding: 12px 0 !important;
    font-size: 18px !important;
    background: #f5d273 !important;
    color: #3d3d3d !important;
    border: 3px solid #e3b44c !important;
    box-shadow: 0 4px 0 #c5a04a !important;
}

.acnh-button > button:active {
    box-shadow: none !important;
    transform: translateY(4px);
}

</style>
"""
st.markdown(login_css, unsafe_allow_html=True)


# -------------------------
# ⭐️⭐️⭐️ 닉네임 로그인 + 닉네임 저장 ⭐️⭐️⭐️
# -------------------------

# 전체 폰트 적용
load_custom_font() 

# 배경화면 호출  
set_background()

# 유저 생성 함수 선언
def create_user_if_not_exists(user_id: str):
    with driver.session() as s:
        s.run("""
        MERGE (u:User {id: $user_id})
        ON CREATE SET u.created_at = timestamp()
        """, user_id=user_id)

# 0. 유저 식별용 상태 초기화 -------------------
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None

# 0-1. 닉네임 입력 창 (로그인 화면 느낌)
# 🧑‍💻 로그인 화면
# 0-1. 닉네임 입력 창 (로그인 화면 느낌)
# 0-1. 닉네임 입력 창 (로그인 화면 느낌)
if st.session_state["user_id"] is None:

    st.markdown('<div class="login-container">', unsafe_allow_html=True)

    # ✅ 카드 + 잎사귀 + 제목을 한 번에 렌더링
    st.markdown(
    """
    <div class="login-container korean-text">
      <div class="acnh-card">
        <img class="acnh-leaf"
             src="https://raw.githubusercontent.com/encharm/Font-Awesome-SVG-PNG/master/white/png/64/leaf.png">
        <div class="acnh-title">먼저 닉네임을 입력해주세요</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True
)


    st.markdown('<div class="acnh-input" style="padding-top: 30px;">', unsafe_allow_html=True)
    nickname = st.text_input(
        "",
        placeholder="예: yedam, 홍길동 등",
        key="acnh_nick",
        label_visibility="collapsed"
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # 🔹 버튼: .acnh-button 으로 감싸주기
    st.markdown('<div class="acnh-button">', unsafe_allow_html=True)
    ok = st.button("입장하기", key="acnh_enter", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if ok:
        if nickname.strip():
            user_id = nickname.strip()
            st.session_state["user_id"] = user_id
            create_user_if_not_exists(user_id)
            st.rerun()
        else:
            st.warning("닉네임을 입력해주세요 🌼")

    st.markdown('</div></div>', unsafe_allow_html=True)  # acnh-card / login-container 닫기
    st.stop()


# --------------------------
# ⭐️⭐️⭐️ 로그인 후 ⭐️⭐️⭐️ 화면 (챗봇)
# --------------------------

# --------------------------
# 💬💬💬 챗봇 기본 설정 💬💬💬
# --------------------------
chat_css = """
<style>
.chat-wrapper {
    margin-top: 40px;
    max-width: 640px;
    margin-left: auto;
    margin-right: auto;
}

/* 한 줄 전체 */
.chat-row {
    display: flex;
    margin-bottom: 12px;
}

/* 챗봇(동네) 왼쪽 */
.chat-row.bot {
    justify-content: flex-start;
}

/* 사용자 오른쪽 */
.chat-row.user {
    justify-content: flex-end;
}

/* 말풍선 공통 */
.chat-bubble {
    max-width: 80%;
    padding: 12px 25px;
    border-radius: 999px;
    font-size: 17px;
    line-height: 1.4;
    box-shadow: 0 3px 0 rgba(0,0,0,0.12);
    word-break: keep-all;
    font-family: 'ACNH_KR', sans-serif;
}

/* 🔶 챗봇 말풍선 */
.chat-bubble.bot {
    background: #fff9e4;      /* 말풍선 색 */
    color: #837156;           /* 말 텍스트 */
}

/* 🔶 사용자 말풍선 */
.chat-bubble.user {
    background: #feec9e;      /* 말풍선 배경 */
    color: #7e693a;           /* 말 텍스트 */
}

/* 🔶 챗봇(동네) 이름 */
.bot-name {
    font-size: 15px;
    margin-bottom: 4px;
    margin-left: 5px;
    color: #df852e;           /* 챗봇 이름 색 */
    font-family: 'ACNH_KR', sans-serif;
}

/* 🔶 사용자 이름 */
.user-name {
    font-size: 15px;
    margin-bottom: 4px;
    margin-right: 5px;
    color: #7e693a;
    font-family: 'ACNH_KR', sans-serif;
    text-align: right;
}
</style>
"""
st.markdown(chat_css, unsafe_allow_html=True)

# --------------------------
# ☑️☑️☑️ Cuisine 버튼 UI CSS ☑️☑️☑️
# --------------------------
def load_cuisine_button_css():
    st.markdown(
        """
        <style>
        .cuisine-btn-container {
            margin-top: 10px;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 12px;
        }

        /* 각 버튼을 감싸는 래퍼 */
        .cuisine-btn > button {
            background: #df852e !important;   /* 버튼 배경 */
            border: 3px solid #f5d273 !important;
            color: #837156 !important;        /* 버튼 글자색 */
            padding: 10px 18px !important;
            border-radius: 18px !important;
            font-size: 17px !important;
            box-shadow: 0 4px 0 #d9b45f !important;
            font-family: 'ACNH_KR', sans-serif !important;
        }

        .cuisine-btn > button:active {
            box-shadow: none !important;
            transform: translateY(3px);
        }
        </style>
        """,
        unsafe_allow_html=True
    )





# --------------------------
# 📍📍📍 지도화면 기본 구성 📍📍📍
# --------------------------
map_css = """
<style>
.place-wrapper {
    margin-top: 8px;
    max-width: 960px;
    margin-left: auto;
    margin-right: auto;
}

/* 한 칸(카드) */
.place-card {
    background: #fff9e4;                 /* 챗봇 말풍선이랑 같은 톤 */
    border-radius: 24px;
    border: 3px solid #f5d273;           /* 로그인 카드랑 맞춤 */
    box-shadow: 0 4px 0 #d9b45f;
    padding: 10px 12px 14px 12px;
    margin-bottom: 16px;
}

/* 가게 이름 */
.place-title {
    font-family: 'ACNH_KR', sans-serif;
    font-size: 18px;
    color: #7e693a;                       /* 사용자 말 텍스트 색 계열 */
    margin-bottom: 4px;
}

/* 점수 뱃지 */
.place-score {
    display: inline-block;
    padding: 3px 9px;
    border-radius: 999px;
    background: #feec9e;
    color: #7e693a;
    font-size: 13px;
    margin-bottom: 6px;
}

/* iframe 둥글게 */
.place-iframe {
    border-radius: 16px;
    border: 0;
}

/* 아래 버튼 영역 */
.place-links {
    margin-top: 6px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.place-link-btn {
    padding: 6px 10px;
    border-radius: 999px;
    border: 1px solid #e3b44c;
    background: #fffaf0;
    text-decoration: none;
    font-size: 13px;
    color: #7e693a;
    font-family: 'ACNH_KR', sans-serif;
}
</style>
"""
st.markdown(map_css, unsafe_allow_html=True)


# --------------------------
# 💬💬💬 챗봇 시작화면 + USER name 띄우기 💬💬💬
# --------------------------
user_id = st.session_state["user_id"]


# ⭐ 여기 추가 ⭐
if "user_session" not in st.session_state:
    st.session_state.user_session = {
        "user_id": user_id,
        "session_id": f"conv-{uuid.uuid4()}",
        "choices": [],   # 이번 대화에서 사용자가 고른 가게들
    }



with st.container():
    st.markdown("""
        <div class="acnh-card" style="
            margin: 0 auto;
            width: 500px;
            background: rgba(255,250,235,0.92);
            border: 4px solid #f5d273;
            border-radius: 26px;
            padding: 10px 35px;
            box-shadow: 0 6px 0 #d9b45f;
            backdrop-filter: blur(4px);
            margin-top: -100px;
        ">
            <div class="acnh-title">동네와 얘기해봐요! </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # 현재 사용자 표시
    st.markdown(
        f"""
        <div class="korean-text" 
             style="text-align:center; margin-top: 1px; color:#3e5f2f;">
            현재 사용자: <b>{user_id}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )


    # 여기에는 Streamlit 텍스트 사용 가능 💚
    st.markdown("<div style='text-align:center;'>", unsafe_allow_html=True)   
    st.markdown("</div>", unsafe_allow_html=True)

    # 카드 닫기
    st.markdown("</div>", unsafe_allow_html=True)


############################################
# 2) 대화 기록 저장 (세션)
############################################
# 인사 멘트 목록
INTRO_MESSAGES = [
    "안녕?😊",
    f"나는 {user_id}의 동네에서, 취향과 상황에 맞는 가게를 추천해주는 ‘동네’라고 해!"
]

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 지금 몇 번째 인사까지 보여줬는지 (0,1,2,3)
if "intro_step" not in st.session_state:
    st.session_state.intro_step = 0

# 첫 입장: 아직 아무 메시지도 없고, 인사도 안 했으면 첫 줄만 추가
if len(st.session_state.messages) == 0 and st.session_state.intro_step == 0:
    st.session_state.messages.append({"role": "bot", "content": INTRO_MESSAGES[0]})
    st.session_state.intro_step = 1





############################################
# 📍📍📍 지도 함수 정의 📍📍📍
###########################################
from streamlit.components.v1 import html

def naver_place_urls(place_id: str):
    mobile = f"https://m.place.naver.com/restaurant/{place_id}"
    pc     = f"https://map.naver.com/v5/entry/place/{place_id}"
    return mobile, pc


def render_naver_cards(rows, cols_per_row=3, height=420, selectable=False):
    """검색 결과를 네이버 장소 카드(동숲 스타일)로 표시
       selectable=True 이면 카드 아래에 '이 곳으로 선택하기' 버튼을 띄우고
       클릭된 카드의 인덱스(idx)를 리턴한다. (없으면 None 리턴)
    """
    if not rows:
        st.info("표시할 결과가 없습니다.")
        return None

    st.markdown(
        "<div class='korean-text' style='text-align:center; font-size:20px; margin-top:12px;'>"
        "📍 오늘 동네가 골라본 가게들이야!"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='place-wrapper'>", unsafe_allow_html=True)

    selected_idx = None  # 클릭된 카드 인덱스

    for start in range(0, len(rows), cols_per_row):
        cols = st.columns(min(cols_per_row, len(rows) - start))
        for i, col in enumerate(cols, start=start):
            r = rows[i]
            name  = r.get("place", "이름 없음")
            pid   = r.get("place_id")
            score = r.get("score")

            mob, pc = naver_place_urls(pid)

            with col:
                card_html = f"""
                <div class="place-card">
                  <div class="place-title">🍽 {name}</div>
                  {f'<div class="place-score">⭐ {score:.1f}</div>' if score is not None else ''}
                  <iframe class="place-iframe"
                          src="{mob}"
                          width="100%" height="{height}"
                          loading="lazy"></iframe>
                  <div class="place-links">
                    <a class="place-link-btn" href="{mob}" target="_blank">📱 모바일</a>
                    <a class="place-link-btn" href="{pc}" target="_blank">🗺️ 지도 열기</a>
                  </div>
                </div>
                """
                html(card_html, height=height+110)

                # 🔽 여기서 선택 버튼 추가
                if selectable:
                    if st.button("이 곳으로 선택하기", key=f"choose_place_{i}"):
                        selected_idx = i

    st.markdown("</div>", unsafe_allow_html=True)

    return selected_idx



############################################
# 추천 기반 함수 정의
############################################
# 입력 text -> embedding 변환
def embed_text(text: str):
    return client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    ).data[0].embedding


# 정확한 요청 사항에서 Text → Cypher 변환 프롬프트
SCHEMA_TEXT = """
You are an expert in Neo4j Cypher query generation.

Database schema:
Node labels:
- Cuisine(name:String, embedding:DoubleArray)
- Menu(id:String, name:String, description:String, menu_embedding:DoubleArray)
- Place(id:String, name:String)
- Tag(name:String, embedding:DoubleArray)
- User(id:String, created_at:Long)

Relationships:
- (:Place)-[:SERVES]->(:Cuisine)
- (:Place)-[:SERVES_MENU]->(:Menu)
- (:Place)-[:HAS_TAG {count:Int}]->(:Tag)
- (:Menu)-[:OF_CUISINE]->(:Cuisine)
- (:User)-[:LIKES_TAG {weight:Float}]->(:Tag)

Rules:
- Generate **only a Cypher query**, no explanations or markdown.
- Use CONTAINS for partial text matches.
- Always return at most 3 results unless the user specifies otherwise.
- If the user mentions a menu (e.g., 김치찌개), match it against Menu.name.
- If the user mentions a cuisine (e.g., 한식), match it against Cuisine.name.
- If the user mentions a mood or vibe (e.g., 조용한, 데이트, 혼밥), match it against Tag.name.
- Combine filters when possible.
"""

def nl_to_cypher(user_input):
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SCHEMA_TEXT},
            {"role": "user", "content": f"사용자 요청: {user_input}\n→ 위 스키마를 기준으로 Cypher 쿼리 한 줄로 생성해줘."}
        ],
        temperature=0.1,
    )
    return res.choices[0].message.content.strip()


# 특정 메뉴 언급 시
def find_menu_by_name_in_cuisine(text: str, cuisine: str):
    """
    사용자가 '김치찌개'처럼 명확한 메뉴를 말했을 때,
    같은 cuisine 안에서 이름이 정확히 같거나 매우 유사한 메뉴만 찾기
    (유사한 이름 중복 제거)
    """
    cy = """
    MATCH (c:Cuisine {name:$cuisine})<-[:OF_CUISINE]-(m:Menu)
    WITH m,
         toLower(replace(m.name, ' ', '')) AS menu_name_norm,
         toLower(replace($text, ' ', '')) AS text_norm
    WHERE menu_name_norm CONTAINS text_norm
       OR text_norm CONTAINS menu_name_norm
    WITH collect(m) AS menus
    UNWIND menus AS m
    WITH DISTINCT toLower(m.name) AS normalized, head(collect(m)) AS one
    RETURN one.id   AS menu_id,
           one.name AS menu_name
    LIMIT 5
    """
    return run_query(cy, {"cuisine": cuisine, "text": text})



# [중분류] -> 애매한 표현으로 menu 추천해주기
def suggest_menus_by_taste(text: str, cuisine: str, k: int = 3):
    """
    '얼큰한 국수', '칼칼한 국물' 같은 애매한 맛 표현일 때:
    - text 임베딩 → menu_embedding_index 로 근접 메뉴 후보 찾기
    - 그 중에서 해당 cuisine 에 속하는 메뉴만 필터 → 상위 k개 반환
    """
    emb = embed_text(text)  # 여기서 [float, ...] 리스트가 나온다고 가정

    # 혹시 numpy array면 Neo4j가 못 받아서 꼭 list로 변환
    try:
        import numpy as np
        if isinstance(emb, np.ndarray):
            emb = emb.tolist()
    except ImportError:
        pass

    cy = """
    CALL db.index.vector.queryNodes('menu_embedding_index', $topK, $emb)
    YIELD node, score
    MATCH (node:Menu)-[:OF_CUISINE]->(c:Cuisine {name: $cuisine})
    RETURN 
        node.id   AS menu_id,
        node.name AS menu_name,
        score
    ORDER BY score DESC
    LIMIT $k
    """

    params = {
        "emb": emb,
        "cuisine": cuisine,
        "k": 4,
        "topK": k * 5,   # 먼저 넉넉히 뽑았다가 cuisine 으로 필터
    }

    return run_query(cy, params)








# 원하는 분위기 embedding 비교 후 tag 추출
def top_tags_by_embedding(text: str, k: int = 3):
    """
    분위기/상황 문장 → 태그 top-k
    """
    emb = embed_text(text)
    cy = """
    CALL db.index.vector.queryNodes('tag_embedding_index', $k, $emb)
    YIELD node, score
    RETURN node.name AS tag, score
    ORDER BY score DESC
    """
    return run_query(cy, {"k": k, "emb": emb})


# 전체적인 추천 구조 및 흐름
def recommend_places_with_menu_and_tags(
    cuisine: str,
    menu_name: str,      # ← 이제 문자열 이름으로 찾고
    tags: list[str],
    limit: int = 4,
):
    """
    1) menu_name(예: '김치찌개')이 들어가는 Menu들을 찾고
    2) 그 메뉴들을 파는 Place들을 모은 뒤
    3) 각 Place마다 매칭된 menu.id 리스트 + 태그 겹치는 정도(score) 반환
    """
    cy = """
    // 1️⃣ 주어진 메뉴 이름을 가진 메뉴 + 가게 찾기
    MATCH (c:Cuisine {name:$cuisine})
    MATCH (p:Place)-[:SERVES]->(c)
    MATCH (p)-[:SERVES_MENU]->(m:Menu)
    WHERE toLower(replace(m.name, ' ', '')) CONTAINS toLower(replace($menu_name, ' ', ''))

    // 2️⃣ 가게별로 매칭된 메뉴 id들 모으기
    WITH p, COLLECT(DISTINCT m.id) AS menu_ids

    // 3️⃣ 태그 겹치는 정도 계산
    OPTIONAL MATCH (p)-[:HAS_TAG]->(t:Tag)
    WITH p, menu_ids, COLLECT(DISTINCT t.name) AS all_tags, $tags AS input_tags
    WITH p, menu_ids, [tag IN input_tags WHERE tag IN all_tags] AS matched_tags

    RETURN
        p.name  AS place,
        p.id    AS place_id,
        menu_ids AS menu_ids,           // 👈 이 가게에서 '김치찌개'로 매칭된 메뉴 id 리스트
        matched_tags AS matched_tags,
        SIZE(matched_tags) AS score
    ORDER BY score DESC, place ASC
    LIMIT $limit
    """

    return run_query(cy, {
        "cuisine": cuisine,
        "menu_name": menu_name,
        "tags": tags,
        "limit": limit,
    })


# taste기반 menu 추천 리스트 중 후보 받기
def select_from_candidates(user_text: str, candidates: list[dict], key: str):
    """
    candidates: [{"cuisine": "한식"}, ...] or [{"menu_id": "...", "menu_name": "..."}]
    key: "cuisine" or "menu_name" 등

    return: 선택된 dict 또는 None
    """
    txt = user_text.strip()

    # ① 숫자로만 온 경우: 인덱스 선택
    if txt.isdigit():
        idx = int(txt) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]

    # ② 문자열로 온 경우: 이름 포함 여부로 선택
    lower_txt = txt.lower()
    for c in candidates:
        if lower_txt in c[key].lower():
            return c

    return None



# 추천해줄까? 에서 긍정/부정의 답을 제대로 인식해서 반영하기
client = OpenAI()

def detect_intent_llm(user_text: str) -> str:
    """
    LLM을 이용해 사용자의 의도를 문맥적으로 분석 ('yes' / 'no' / 'neutral')
    """
    prompt = f"""
    너는 사용자의 발화를 분석해서 그 의도가 'yes'(긍정), 'no'(부정), 'neutral'(중립)인지 판별하는 역할이야.
    아래 문장은 자연스러운 대화체(예: '시렁', '싫엉', 'ㄴㄴ', 'ㅇㅋ')로 되어 있을 수도 있어.
    반드시 의미로만 판단해야 하고, 정답은 다음 중 하나로만 출력해야 해:
    - yes
    - no
    - neutral

    예시:
    - "좋아", "ㅇㅋ", "응", "그래", "ㄱㄱ", "보여줘" → yes
    - "싫어", "시러", "시렁", "싫엉", "ㄴㄴ", "아니", "별로", "다시" → no
    - "모르겠어", "흠", "아직", "글쎄" → neutral

    문장: "{user_text}"
    """

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        intent = res.choices[0].message.content.strip().lower()

        # 혹시 gpt가 영어 말고 쓸 수도 있으니까 안전 처리
        if "yes" in intent or "긍정" in intent:
            return "yes"
        elif "no" in intent or "부정" in intent:
            return "no"
        return "neutral"

    except Exception as e:
        print("intent detection error:", e)
        return "neutral"



# User의 choice 저장 함수
def save_choice_to_neo4j(choice_row: dict):
    """
    추천 리스트(rows) 중에서 사용자가 '이곳 갈래'라고 선택한 한 곳을
    Choice 노드로 저장 + user_session에도 기록
    """
    user_id = st.session_state["user_id"]
    ui_ctx  = st.session_state.context
    us      = st.session_state.user_session

    place_id   = choice_row["place_id"]
    place_name = choice_row["place"]
    score      = float(choice_row.get("score", 0.0))

    # menu_ids 중 첫 번째를 대표 메뉴로 사용 (없으면 None)
    menu_ids = choice_row.get("menu_ids") or []
    menu_id  = menu_ids[0] if menu_ids else None

    menu_text = ui_ctx.get("menu_name") or ui_ctx.get("menu_text")
    cuisine   = ui_ctx.get("cuisine")
    mood_tags = ui_ctx.get("mood_tags", [])

    choice_id = str(uuid.uuid4())

    cy = """
    MATCH (u:User {id:$user_id})
    MATCH (p:Place {id:$place_id})
    OPTIONAL MATCH (m:Menu {id:$menu_id})

    CREATE (c:Choice {
      id: $choice_id,
      decided_at: datetime(),
      session_id: $session_id,
      raw_query: $raw_query,
      cuisine: $cuisine,
      mood_tags: $mood_tags,
      menu_text: $menu_text,
      score: $score
    })

    MERGE (u)-[:MADE]->(c)
    MERGE (c)-[:AT_PLACE]->(p)

    // menu_id가 있을 때만 Menu 연결
    FOREACH (_ IN CASE WHEN m IS NULL THEN [] ELSE [1] END |
        MERGE (c)-[:OF_MENU]->(m)
    )
    """

    params = {
        "user_id": user_id,
        "place_id": place_id,
        "menu_id": menu_id,
        "choice_id": choice_id,
        "session_id": us["session_id"],
        "raw_query": ui_ctx.get("menu_text"),
        "cuisine": cuisine,
        "mood_tags": mood_tags,
        "menu_text": menu_text,
        "score": score,
    }

    run_query(cy, params)

    # 👉 Streamlit 세션에도 기록 (한 대화 요약용)
    us["choices"].append({
        "choice_id": choice_id,
        "place_id": place_id,
        "place_name": place_name,
        "menu_id": menu_id,
        "menu_text": menu_text,
        "cuisine": cuisine,
        "mood_tags": mood_tags,
        "score": score,
    })



############################################
# 💬💬💬 세션 상태 + 채팅 UI (동숲 스타일) + FSM 단계 정의 💬💬💬
############################################
############################################
# 3) 채팅 UI 렌더링
############################################
st.markdown("<div class='chat-wrapper'>", unsafe_allow_html=True)

for msg in st.session_state.messages:
    if msg["role"] == "bot":
        st.markdown(
            f"""
            <div class="chat-row bot">
                <div>
                    <div class="bot-name">동네</div>
                    <div class="chat-bubble bot">{msg['content']}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"""
            <div class="chat-row user">
                <div>
                    <div class="user-name">{user_id}</div>
                    <div class="chat-bubble user">{msg['content']}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

st.markdown("</div>", unsafe_allow_html=True)

# 아직 유저가 아무 말도 안 했고, 인사 멘트를 다 안 보여줬을 때
has_user_msg = any(m["role"] == "user" for m in st.session_state.messages)

# 1) 아직 유저가 아무 말도 안 했고, 인사 멘트가 남았으면 → "계속 들어보기"
if (not has_user_msg) and (st.session_state.intro_step < len(INTRO_MESSAGES)):
    if st.button("계속 들어보기"):
        next_idx = st.session_state.intro_step
        st.session_state.messages.append({
            "role": "bot",
            "content": INTRO_MESSAGES[next_idx]
        })
        st.session_state.intro_step += 1
        st.rerun()

# 2) 인사가 모두 끝났고, 아직 유저 입력 없음 → “음식 골라줘” 안내 + 버튼
# 아직 유저가 아무 말도 안 했고, 인사 멘트를 다 보여줬을 때
has_user_msg = any(m["role"] == "user" for m in st.session_state.messages)

if (not has_user_msg) and (st.session_state.intro_step >= len(INTRO_MESSAGES)):

    # 1) 안내 멘트를 챗봇 대화창에 추가 (한 번만 추가)
    if "cuisine_msg_sent" not in st.session_state:
        st.session_state.messages.append({
            "role": "bot",
            "content": "오늘은 어떤 음식이 땡겨? 🍽<br>아래에서 골라줘!"
        })
        st.session_state.cuisine_msg_sent = True
        st.rerun()


    # 3) 버튼 렌더링
    st.markdown("<div class='cuisine-btn-container'>", unsafe_allow_html=True)

    cuisines = ["한식", "중식", "일식", "양식", "세계음식", "치킨"]
    cols = st.columns(3)

    for i, c in enumerate(cuisines):
        with cols[i % 3]:
           st.markdown("<div class='cuisine-btn'>", unsafe_allow_html=True)
           if st.button(c, key=f"cuisine_{c}"):
                # 유저가 선택한 걸 말풍선에도 추가
                st.session_state.messages.append({"role": "user", "content": c})

                # 컨텍스트에 cuisine 저장
                st.session_state.context["cuisine"] = c

                # 다음 단계(맛 질문)로
                st.session_state.messages.append({
                    "role": "bot",
                    "content": f"{c} 좋지! 😋<br>그럼 어떤 게 먹고 싶어?)"
                })
                st.session_state.stage = "ask_menu"

                st.rerun()
           st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

############################################
# STAGE1 : ask_menu / 특정메뉴 + 애매 맛 표현 동시 처리
############################################
if "context" not in st.session_state:
    st.session_state.context = {
        "cuisine": None,          # 사용자가 고른 대분류 (한식/중식/...)
        "tags": [],
        "situation_tags": [],
        "menu_id": None,          # (지금은 안 써도 되지만 남겨둬도 상관 없음)
        "menu_name": None,        # 최종 선택된 메뉴 이름
        "menu_text": None,        # 사용자가 말한 메뉴 텍스트 (또는 최종 선택 메뉴)
        "menu_candidates": [],
        "last_recommended": []
    }




user_input = st.chat_input()

if user_input:
    # 닉네임 / context / stage 가져오기
    ui_ctx = st.session_state.context
    stage = st.session_state.stage

    # 메시지 저장
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    # ===============================
    # 📌 Stage: ask_menu (cuisine 선택 후 메뉴 묻는 단계)
    # ===============================
    if stage == "ask_menu":
        cuisine = ui_ctx["cuisine"]

        # 1️⃣ 먼저 정확 매칭 시도
        exact_menus = find_menu_by_name_in_cuisine(user_input, cuisine)
        if exact_menus:
            # 메뉴 이름 완전 일치한 게 있으면 바로 확정
            m = exact_menus[0]
            ui_ctx["menu_name"] = m["menu_name"]
            ui_ctx["menu_text"] = m["menu_name"]

            st.session_state.messages.append({
                "role": "bot",
                "content": (
                    f"{m['menu_name']} 좋지! 😋<br>"
                    "오늘은 어떤 분위기가 좋아? (데이트, 조용한, 힙한, 혼밥 등)"
                )
            })
            st.session_state.stage = "ask_mood"
            st.rerun()

        


        sim_menus = suggest_menus_by_taste(user_input, cuisine, k=5)

        if sim_menus:
            # 🔹 메뉴 이름 중복 제거
            seen = set()
            menu_list = []
            msg = "이 느낌이면 이런 메뉴들이 떠올라! 😋<br><br>"

            for m in sim_menus:
                name = m["menu_name"]
                if name in seen:
                    continue
                seen.add(name)

                menu_list.append({
                    "menu_id": m["menu_id"],
                    "menu_name": name,
                })
                
            # 1) 후보가 딱 1개일 때 → 바로 확정하고 분위기 질문으로
            if len(menu_list) == 1:
                chosen = menu_list[0]
                ui_ctx["menu_name"] = chosen["menu_name"]
                ui_ctx["menu_text"] = chosen["menu_name"]

                st.session_state.messages.append({
                    "role": "bot",
                    "content": (
                        f"{chosen['menu_name']} 먹고 싶구나! 😋<br>"
                        "오늘은 어떤 분위기가 좋아? (데이트, 조용한, 힙한, 혼밥 등)"
                    )
                })
                st.session_state.stage = "ask_mood"
                st.rerun()

            # 2) 후보가 여러 개일 때만 리스트 보여주고 선택 단계로
            elif len(menu_list) > 1:
                msg = "이 느낌이면 이런 메뉴들이 떠올라! 😋<br><br>"
                for i, m in enumerate(menu_list, start=1):
                    msg += f"{i}. {m['menu_name']}<br>"
                msg += "<br>하나 골라줘! (번호나 이름으로 말해줘)"

                st.session_state.messages.append({"role": "bot", "content": msg})
                ui_ctx["menu_candidates"] = menu_list
                st.session_state.stage = "choose_menu"
                st.rerun()

            # 3) (거의 없겠지만) 중복 제외하고 남은 후보가 0개인 경우
            else:
                st.session_state.messages.append({
                    "role": "bot",
                    "content": (
                        "음… 비슷한 메뉴 후보가 잘 안 떠올라 😢<br>"
                        "조금 더 자세히 말해줄래? (예: 김치찌개, 매운 국물, 면 요리 등)"
                    )
                })
                st.rerun()

        # sim_menus 자체가 비어 있을 때
        else:
            st.session_state.messages.append({
                "role": "bot",
                "content": (
                    "음… 지금 말로는 메뉴가 잘 안 떠올라 😢<br>"
                    "조금 더 자세히 말해줄래? (예: 김치찌개, 매운 국물, 면 요리 등)"
                )
            })
            st.rerun()


    elif stage == "choose_menu":
        # ask_menu 단계에서 저장해둔 후보들 불러오기
        candidates = ui_ctx.get("menu_candidates", [])

        if not candidates:
            # 혹시라도 비어 있으면 다시 메뉴 단계로
            st.session_state.messages.append({
                "role": "bot",
                "content": "음… 지금은 메뉴 후보 리스트가 없어졌어 😢<br>다시 메뉴부터 골라보자!"
            })
            st.session_state.stage = "ask_menu"
            st.rerun()

        # 사용자가 보낸 입력(번호 or 이름)으로 후보 중 하나 선택
        chosen = select_from_candidates(user_input, candidates, key="menu_name")

        if not chosen:
            # 리스트에 없는 값이면 다시 요구
            st.session_state.messages.append({
                "role": "bot",
                "content": "리스트에 없는 선택이야 😅 번호나 메뉴 이름으로 다시 골라줘!"
            })
            st.rerun()

        # ✅ 최종 선택된 메뉴를 context에 저장
        ui_ctx["menu_name"] = chosen["menu_name"]
        ui_ctx["menu_text"] = chosen["menu_name"]   # 추천 기준 텍스트
        ui_ctx["menu_candidates"] = []

        # 이제 다음 단계: 분위기 묻기
        st.session_state.messages.append({
            "role": "bot",
            "content": (
                f"{chosen['menu_name']} 좋지! 😋<br>"
                "오늘은 어떤 분위기가 좋아? (데이트, 조용한, 힙한, 혼밥 등)"
            )
        })
        st.session_state.stage = "ask_mood"
        st.rerun()

    elif stage == "ask_mood":
        cuisine   = ui_ctx.get("cuisine")
        menu_text = ui_ctx.get("menu_name") or ui_ctx.get("menu_text")

        # 1) 분위기 → 태그 임베딩
        mood_rows = top_tags_by_embedding(user_input, k=4)
        mood_tags = [r["tag"] for r in mood_rows]
        ui_ctx["mood_tags"] = mood_tags

        if mood_tags:
            tag_str = ", ".join(mood_tags)
            st.session_state.messages.append({
                "role": "bot",
                "content": (
                    f"음, 이런 느낌이구나! 😌<br>"
                    f"이번에는 <b>{tag_str}</b> 태그를 중심으로 가게를 골라볼게.<br>"
                    "이 태그 기준으로 추천해볼까?"
                )
            })
        else:
            st.session_state.messages.append({
                "role": "bot",
                "content": (
                    "이번 문장에서는 딱 꽂히는 태그를 못 찾았어 😭<br>"
                    "그래도 최대한 비슷한 분위기로 찾아볼 건데, 추천해볼까?"
                )
            })

        st.session_state.stage = "confirm_reco"
        st.rerun()


    elif stage == "confirm_reco":
        ui_ctx    = st.session_state.context
        cuisine   = ui_ctx.get("cuisine")
        menu_name = ui_ctx.get("menu_name") or ui_ctx.get("menu_text")
        mood_tags = ui_ctx.get("mood_tags") or []

        intent = detect_intent_llm(user_input)

        if intent == "yes":
            # 메뉴가 정해져 있으면 → 메뉴 + 태그 기준 추천
            if menu_name:
                rows = recommend_places_with_menu_and_tags(
                    cuisine=cuisine,
                    menu_name=menu_name,
                    tags=mood_tags,
                    limit=3,
                )
            else:
                # 메뉴 없이 cuisine + 태그만으로 추천
                rows = recommend_places(
                    cuisine=cuisine,
                    tags=mood_tags,
                    limit=3,
                )

            ui_ctx["last_recommended"] = rows

            if not rows:
                st.session_state.messages.append({
                    "role": "bot",
                    "content": (
                        "미안… 지금 정보로는 딱 맞는 가게를 못 찾았어 🥲<br>"
                        "분위기나 메뉴를 조금 다르게 말해볼래?"
                    )
                })
                st.session_state.stage = "ask_mood"
                st.rerun()

            st.session_state.messages.append({
                "role": "bot",
                "content": (
                    "너의 취향이랑 분위기를 반영해서 이런 가게들을 골라봤어! 😋<br>"
                    "괜찮아 보이는지 한 번 살펴봐줘!"
                )
            })
        

            render_naver_cards(rows)
            st.session_state.stage = "choose_place"
            st.rerun()
            

        elif intent == "no":
            st.session_state.messages.append({
                "role": "bot",
                "content": "좋아! 그럼 분위기를 조금 다르게 말해볼래? 😊"
            })
            st.session_state.stage = "ask_mood"
            st.rerun()

        else:
            st.session_state.messages.append({
                "role": "bot",
                "content": "잘 모르겠어 😅 보고 싶으면 ‘응’, 아니면 ‘아니’라고 말해줘!"
            })
            st.rerun()



    # ================================
# 💚 카드 선택 단계 UI (항상 렌더링)
# ================================
if st.session_state.get("stage") == "choose_place":
    ui_ctx = st.session_state.context
    rows   = ui_ctx.get("last_recommended", [])

    if not rows:
        st.session_state.messages.append({
            "role": "bot",
            "content": "앗, 추천 리스트가 사라졌어 😢<br>다시 한 번 메뉴부터 골라보자!"
        })
        st.session_state.stage = "ask_menu"
        st.rerun()

    st.markdown(
        "<div class='korean-text' style='text-align:center; font-size:16px; margin-top:8px;'>"
        "마음에 드는 가게 아래에서 <b>‘이 곳으로 선택하기’</b> 버튼을 눌러줘! 🌟"
        "</div>",
        unsafe_allow_html=True,
    )

    # 🔽 선택 가능한 카드 렌더링
    selected_idx = render_naver_cards(rows, selectable=True)

    # 버튼이 눌리면 selected_idx 에 값이 들어옴
    if selected_idx is not None:
        chosen = rows[selected_idx]

        # ✅ Choice 저장
        save_choice_to_neo4j(chosen)

        st.session_state.messages.append({
            "role": "bot",
            "content": (
                f"좋아! 오늘은 <b>{chosen['place']}</b> 로 가보자 😊<br>"
                "다음에도 또 동네 불러줘!"
            )
        })
        st.session_state.stage = "END"
        st.rerun()
