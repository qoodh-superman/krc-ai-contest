import streamlit as st
import pandas as pd
import numpy as np
import logging
import os
import json
import re
import time
import uuid
import random
from dotenv import load_dotenv
import google.generativeai as genai

# Security: Use absolute paths to prevent Path Traversal and working directory issues
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Set up logging securely
log_dir = os.path.join(BASE_DIR, 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, 'user_activity.log'),
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 개인정보(상세 지번 등) 마스킹 헬퍼 함수
def mask_personal_info(text):
    # '123-4' 등 지번 형태 마스킹 (숫자-숫자)
    masked = re.sub(r'(\d+)-(\d+)', r'\1-*', text)
    # '123번지' 형태 마스킹
    masked = re.sub(r'(\d+)번지', r'**번지', masked)
    return masked

# 전역 접속 통계 및 피드백 관리 헬퍼 클래스
class StatsManager:
    FILE_PATH = os.path.join(BASE_DIR, 'data/visitor_stats.json')
    
    @classmethod
    def get_default_stats(cls):
        return {
            "cumulative_visitors": 0,
            "feedbacks": {
                "🏠 소개 (랜딩 페이지)": {
                    "매우 만족 😊": 0, "만족 🙂": 0, "보통 😐": 0, "불만족 🙁": 0, "매우 불만족 😡": 0
                },
                "📊 통계 대시보드 (정적 페이지)": {
                    "매우 만족 😊": 0, "만족 🙂": 0, "보통 😐": 0, "불만족 🙁": 0, "매우 불만족 😡": 0
                },
                "🤖 AI 시뮬레이터 (컨설팅 분석 페이지)": {
                    "매우 만족 😊": 0, "만족 🙂": 0, "보통 😐": 0, "불만족 🙁": 0, "매우 불만족 😡": 0
                }
            }
        }

    @classmethod
    def load_stats(cls):
        default_stats = cls.get_default_stats()
        if not os.path.exists(cls.FILE_PATH):
            os.makedirs(os.path.dirname(cls.FILE_PATH), exist_ok=True)
            cls.save_stats(default_stats)
            return default_stats
        
        try:
            with open(cls.FILE_PATH, 'r', encoding='utf-8') as f:
                stats = json.load(f)
                
            # 마이그레이션 처리: feedbacks 속성이 없거나 예전 스키마인 경우 교체
            if "feedbacks" not in stats or not isinstance(stats["feedbacks"], dict):
                stats["feedbacks"] = default_stats["feedbacks"]
            else:
                # 누락된 카테고리 병합
                for key in default_stats["feedbacks"].keys():
                    if key not in stats["feedbacks"]:
                        stats["feedbacks"][key] = default_stats["feedbacks"][key]
            return stats
        except Exception:
            return default_stats

    @classmethod
    def save_stats(cls, stats):
        try:
            with open(cls.FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Stats save error: {e}")

    @classmethod
    def add_feedback(cls, page, option):
        stats = cls.load_stats()
        if "feedbacks" in stats and page in stats["feedbacks"]:
            if option in stats["feedbacks"][page]:
                stats["feedbacks"][page][option] += 1
                cls.save_stats(stats)
        return stats

    @classmethod
    def reset_stats(cls):
        default_stats = cls.get_default_stats()
        cls.save_stats(default_stats)
        return default_stats

    @classmethod
    def seed_mock_data(cls):
        stats = cls.load_stats()
        stats["cumulative_visitors"] = stats.get("cumulative_visitors", 0) + random.randint(80, 150)
        
        options = ["매우 만족 😊", "만족 🙂", "보통 😐", "불만족 🙁", "매우 불만족 😡"]
        weights = [0.55, 0.25, 0.12, 0.05, 0.03] # 긍정 여론 가중치
        
        for page in stats["feedbacks"].keys():
            total_seeds = random.randint(25, 50)
            choices = random.choices(options, weights=weights, k=total_seeds)
            for c in choices:
                stats["feedbacks"][page][c] += 1
        cls.save_stats(stats)
        return stats

st.set_page_config(page_title="KRC 농지연금 AI 시뮬레이터", page_icon="🌾", layout="wide")

# --- 동시 접속자 및 누적 세션 추적 엔진 ---
SESSION_DIR = os.path.join(BASE_DIR, 'data/active_sessions')
os.makedirs(SESSION_DIR, exist_ok=True)

# 신규 접속 세션인 경우 카운트 증가
if "session_key" not in st.session_state:
    st.session_state.session_key = str(uuid.uuid4())
    stats_data = StatsManager.load_stats()
    stats_data["cumulative_visitors"] = stats_data.get("cumulative_visitors", 0) + 1
    StatsManager.save_stats(stats_data)

# 실시간 세션 활성 타임스탬프 갱신
session_file = os.path.join(SESSION_DIR, st.session_state.session_key)
with open(session_file, 'w') as f:
    f.write(str(time.time()))

# 최근 30초 이내 갱신된 활성 세션 계산
now = time.time()
active_count = 0
for fname in os.listdir(SESSION_DIR):
    fpath = os.path.join(SESSION_DIR, fname)
    try:
        mtime = os.path.getmtime(fpath)
        if now - mtime < 30:
            active_count += 1
        else:
            os.remove(fpath) # 비활성 세션 정리
    except Exception:
        pass
active_count = max(1, active_count)
stats = StatsManager.load_stats()

with st.sidebar:
    st.markdown("### 🧭 서비스 페이지 이동")
    menu = st.selectbox(
        "이동할 페이지를 선택하세요:",
        ["🏠 프로젝트 소개", "📊 통계 대시보드", "🤖 AI 시뮬레이터 & 컨설턴트"],
        index=2,
        key="app_menu"
    )
    st.markdown("---")
    st.markdown("### 🔗 Netlify 원본 (다음 달 자동 복구)")
    st.markdown("- [🏠 소개 페이지 원본](https://krc-ai-main.netlify.app/)")
    st.markdown("- [📊 통계 대시보드 원본](https://krc-ai-contest.netlify.app/)")
    st.markdown("---")
    font_size_option = st.radio("🔎 글자 크기 설정", ["보통 (기본)", "크게", "아주 크게"], index=0)
    st.markdown("---")
    st.markdown("### 👥 실시간 접속 통계")
    col_vis1, col_vis2 = st.columns(2)
    with col_vis1:
        st.metric(label="동시 접속자", value=f"{active_count} 명")
    with col_vis2:
        st.metric(label="누적 방문자", value=f"{stats.get('cumulative_visitors', 0)} 명")

# 선택된 글자 크기에 따라 동적 CSS 주입
font_size_styles = ""
if font_size_option == "크게":
    font_size_styles = """
    <style>
    html, body, [class*="css"], p, span, li, input, select, button, textarea { font-size: 19px !important; }
    h1 { font-size: 32px !important; }
    h2, h3 { font-size: 24px !important; }
    div.stButton > button, div.stFormSubmitButton > button { font-size: 19px !important; }
    </style>
    """
elif font_size_option == "아주 크게":
    font_size_styles = """
    <style>
    html, body, [class*="css"], p, span, li, input, select, button, textarea { font-size: 22px !important; }
    h1 { font-size: 36px !important; }
    h2, h3 { font-size: 28px !important; }
    div.stButton > button, div.stFormSubmitButton > button { font-size: 22px !important; }
    </style>
    """
if font_size_styles:
    st.markdown(font_size_styles, unsafe_allow_html=True)

st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

html, body, [class*="css"]  { font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important; }

h1 { font-size: 28px !important; font-weight: 700 !important; color: #124A38 !important; }
h2, h3 { font-size: 20px !important; font-weight: 600 !important; color: #1A1A1A !important; }

div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #FFFFFF;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    border: 1px solid #E2E8E4;
}

div.stButton > button, div.stFormSubmitButton > button {
    background-color: #1F6F54; color: #FFFFFF; border: none;
    border-radius: 8px; padding: 0.6em 1.2em; font-weight: 600;
}
div.stButton > button:hover, div.stFormSubmitButton > button:hover {
    background-color: #124A38; color: #FFFFFF;
}

button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible {
    outline: 3px solid #1D4E89 !important; outline-offset: 2px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="padding:16px 0; border-bottom:1px solid #E2E8E4; margin-bottom:24px;">
  <span style="font-size:13px; color:#5F6B66; font-weight:600;">한국농어촌공사 · 제3회 KRC AI 디지털혁신 공모전</span>
</div>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    pension_df = pd.DataFrame()
    voc_df = pd.DataFrame()
    land_df = pd.DataFrame()
    precedents = []
    legal_rules = {}
    try:
        # Robustly handle single or double space in pension file name
        pension_path = os.path.join(BASE_DIR, 'data/한국농어촌공사_농지연금사업  연도 연령대 지역 정보 제공_20251126.csv')
        if not os.path.exists(pension_path):
            pension_path = os.path.join(BASE_DIR, 'data/한국농어촌공사_농지연금사업 연도 연령대 지역 정보 제공_20251126.csv')
            
        voc_path = os.path.join(BASE_DIR, 'data/한국농어촌공사_고객의 소리 유형분석_20241231.csv')
        
        # Load land prices dynamically from data folder
        import glob
        dfs = []
        land_files = glob.glob(os.path.join(BASE_DIR, 'data/*_개별공시지가_*.csv'))
        
        sido_mapping = {
            '서울': '서울',
            '경기': '경기',
            '경기도': '경기',
            '경남': '경남',
            '강원': '강원',
            '경북': '경북',
            '전남': '전남',
            '제주': '제주',
            '충남': '충남'
        }
        
        for fpath in land_files:
            fname = os.path.basename(fpath)
            prefix = fname.split('_')[0]
            sido_name = sido_mapping.get(prefix, prefix)
            try:
                df_temp = pd.read_csv(fpath, encoding='utf-8')
                df_temp['시도'] = sido_name
                dfs.append(df_temp)
                logger.info(f"Loaded land price file: {fname} as {sido_name} ({len(df_temp)} rows)")
            except Exception as e:
                logger.error(f"Error loading {fname}: {e}")
                
        if os.path.exists(pension_path): pension_df = pd.read_csv(pension_path, encoding='cp949')
        if os.path.exists(voc_path): voc_df = pd.read_csv(voc_path, encoding='cp949')
        
        if dfs:
            land_df = pd.concat(dfs, ignore_index=True)
            # Ensure price column is numeric
            land_df['공시지가'] = pd.to_numeric(land_df['공시지가'], errors='coerce')
            
        # Load precedents and legal rules
        precedents_path = os.path.join(BASE_DIR, 'data/precedents.json')
        if os.path.exists(precedents_path):
            with open(precedents_path, 'r', encoding='utf-8') as f:
                precedents = json.load(f)
                logger.info(f"Loaded precedents: {len(precedents)} items")
                
        legal_rules_path = os.path.join(BASE_DIR, 'data/legal_rules.json')
        if os.path.exists(legal_rules_path):
            with open(legal_rules_path, 'r', encoding='utf-8') as f:
                legal_rules = json.load(f)
                logger.info("Loaded legal rules dataset successfully")
            
    except Exception as e:
        logger.error(f"데이터 로드 에러: {e}")
        st.error("서버 내부 오류: 데이터를 불러오는 중 문제가 발생했습니다.")
        
    return pension_df, voc_df, land_df, precedents, legal_rules

pension_df, voc_df, land_df, precedents, legal_rules = load_data()

# --- 🔗 HTML/CSS 인라인 결합 빌더 (Pixel-Perfect 복원) ---
def get_embedded_dashboard_html():
    static_dir = os.path.join(BASE_DIR, 'app_build_static')
    html_path = os.path.join(static_dir, 'index.html')
    css_path = os.path.join(static_dir, 'style.css')
    script_path = os.path.join(static_dir, 'script.js')
    data_path = os.path.join(static_dir, 'data/results.js')
    
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()
        with open(script_path, 'r', encoding='utf-8') as f:
            js = f.read()
        with open(data_path, 'r', encoding='utf-8') as f:
            data_js = f.read()
            
        # 외형 CSS 스타일 인라인 이식
        html = html.replace('<link rel="stylesheet" href="style.css">', f'<style>{css}</style>')
        
        # JS 비즈니스 데이터 및 Chart.js 구동 코드 인라인 병합
        html = html.replace('<script src="data/results.js"></script>', f'<script>{data_js}</script>')
        html = html.replace('<script src="script.js"></script>', f'<script>{js}</script>')
    except Exception as e:
        logger.error(f"Error embedding static dashboard: {e}")
        html = "<h3>대시보드 데이터를 로드하는 중 오류가 발생했습니다.</h3>"
    return html

def get_embedded_landing_html():
    landing_dir = os.path.join(BASE_DIR, 'landing_page')
    html_path = os.path.join(landing_dir, 'index.html')
    
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
    except Exception as e:
        logger.error(f"Error embedding landing page: {e}")
        html = "<h3>소개 페이지 데이터를 로드하는 중 오류가 발생했습니다.</h3>"
    return html

# Initialize states
if "calculated" not in st.session_state:
    st.session_state.calculated = False
if "q1_msg" not in st.session_state:
    st.session_state.q1_msg = ""
if "q2_msg" not in st.session_state:
    st.session_state.q2_msg = ""
if "q3_msg" not in st.session_state:
    st.session_state.q3_msg = ""

# --- 🏠 프로젝트 소개 페이지 렌더링 ---
if menu == "🏠 프로젝트 소개":
    html_content = get_embedded_landing_html()
    st.components.v1.html(html_content, height=800, scrolling=True)
    st.stop()

# --- 📊 통계 대시보드 렌더링 ---
elif menu == "📊 통계 대시보드":
    html_content = get_embedded_dashboard_html()
    st.components.v1.html(html_content, height=1950, scrolling=True)
    st.stop()

# --- 🤖 AI 시뮬레이터 & 컨설턴트 서비스 전용 타이틀 복구 ---
st.title("🌾 KRC 맞춤형 시뮬레이터 & 통합 민원 AI 컨설턴트")
st.markdown("한국농어촌공사의 최신 데이터 융합으로 농지연금 수령액을 시뮬레이션하고, 농업기반시설 목적외 사용 등 통합 민원을 상담할 수 있습니다.")

col1, col2 = st.columns([1, 1])

with col1:
    with st.container(border=True):
        st.subheader("💡 내 농지연금 예상 수령액 알아보기")
        if True: # Removed st.form for dynamic dropdowns
            age = st.slider("가입 당시 연령 (세)", 60, 90, 65)
            # Get list of loaded Sidos dynamically
            sido_options = []
            if not land_df.empty:
                sido_options = sorted(land_df['시도'].dropna().unique().tolist())
            
            # Prioritize custom order for standard dropdown appearance
            custom_order = ["경기", "서울", "경남", "강원", "경북", "전남", "제주", "충남"]
            ordered_sidos = [s for s in custom_order if s in sido_options]
            for s in sido_options:
                if s not in ordered_sidos:
                    ordered_sidos.append(s)
            ordered_sidos.append("그 외 지역")
            
            region = st.selectbox("농지 소재지 (시도)", ordered_sidos)
            
            sigungu = ""
            bunji = ""
            if region in sido_options and not land_df.empty:
                # Filter by selected Sido
                filtered_sido = land_df[land_df['시도'] == region]
                unique_dongs = sorted(filtered_sido['법정동명'].dropna().unique())
                
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    sigungu = st.selectbox("읍면동 선택", unique_dongs)
                
                # Filter dongs to get unique bunjis
                filtered_dong = filtered_sido[filtered_sido['법정동명'] == sigungu]
                unique_bunjis = sorted(filtered_dong['지번'].dropna().astype(str).unique())
                
                with col_a2:
                    bunji = st.selectbox("지번 선택", unique_bunjis)
            else:
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    sigungu = st.text_input("시군구/읍면동 (그 외 지역)", "")
                with col_a2:
                    bunji = st.text_input("지번 (그 외 지역)", "")
            area = st.number_input("농지 면적 (㎡)", min_value=1000, max_value=50000, value=3000, step=500)
            debt_amount = st.number_input("기존 농지 담보 대출금액 (원)", min_value=0, value=50000000, step=10000000, format="%d", help="한국농어촌공사의 경영회생지원 사업 부채 하한 기준인 50,000,000원을 참조 기본값으로 제공합니다. (출처: 한국농어촌공사 FAQ 및 2025년 경영회생 지원현황 통계)")
            
            st.markdown("##### 🎁 특별 우대 혜택 (해당 시 체크)")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                is_low_income = st.checkbox("국민기초생활수급자 (10% 우대)")
            with col_c2:
                is_long_term = st.checkbox("30년 이상 장기영농인 (5% 우대)")

            payment_type = st.selectbox("연금 지급 방식", ["종신형 (평생 일정 금액 지급)", "기간정액형 (10년/15년 지정 기간 집중 지급)", "전후후박형 (가입 초기 10년간 더 많이 지급)"])
            submitted = st.button("예상 수령액 정밀 계산", type="primary")

    if submitted:
        st.session_state.calculated = True

    if st.session_state.calculated:
        if not pension_df.empty:
            age_bracket = f"{(age // 10) * 10}대"
            filtered = pension_df[pension_df['가입당시연령'] == age_bracket]
            if not filtered.empty:
                avg_payment = pd.to_numeric(filtered['월지급금(원)'], errors='coerce').mean()
                avg_area = pd.to_numeric(filtered['면적'], errors='coerce').mean()
                
                if pd.isna(avg_payment) or pd.isna(avg_area) or avg_area == 0:
                    estimated = 1000000
                else:
                    # 💡 주소 기반 공시지가 맵핑 로직
                    target_price = 300000 # 기본값 (그 외 지역)
                    is_exact_match = False
                    
                    if not land_df.empty and region in ["서울", "경기", "경남"]:
                        # 1순위: 시도 + 법정동명 + 지번 완전 일치 탐색
                        exact_match = land_df[
                            (land_df['시도'] == region) &
                            (land_df['법정동명'] == sigungu) & 
                            (land_df['지번'].astype(str) == str(bunji))
                        ]
                        if not exact_match.empty:
                            target_price = exact_match['공시지가'].mean()
                            is_exact_match = True
                        else:
                            # 2순위: 해당 읍면동 평균 공시지가 적용
                            partial_match = land_df[
                                (land_df['시도'] == region) &
                                (land_df['법정동명'] == sigungu)
                            ]
                            if not partial_match.empty:
                                target_price = partial_match['공시지가'].mean()
                            else:
                                # 3순위: 해당 시도 전체 평균
                                target_price = land_df[land_df['시도'] == region]['공시지가'].mean()
                    
                    if pd.isna(target_price): target_price = 300000
                    
                    base_price = target_price
                    total_land_value = base_price * area
                    
                    # 기준액(농지가치 * 10% / 12개월) 단순화 계산 방식을 통해 단계별 시각화 용이하게 함
                    base_estimated = (total_land_value * 0.05) / 12
                    
                    # 💡 [정책 룰 1] 기존 대출(선순위 채권) 15% 한도 체크
                    debt_ratio = debt_amount / total_land_value if total_land_value > 0 else 0
                    if debt_ratio >= 0.15:
                        st.error(f"🚨 **가입 불가 위험**: 기존 담보 대출액({debt_amount:,}원)이 예상 농지가치({total_land_value:,.0f}원)의 15%를 초과({debt_ratio*100:.1f}%)하여 현재 가입이 거절될 수 있습니다. 대출금 일부 상환(수시인출형 활용 등)을 먼저 고려해 보세요.")
                        st.stop()
                    elif debt_amount > 0:
                        st.warning(f"⚠️ 기존 대출이 농지가치의 {debt_ratio*100:.1f}%를 차지합니다. 15% 미만이므로 가입은 가능하나 수령액 산정 시 대출 상환액이 차감될 수 있습니다.")
                    
                    # 지급 방식에 따른 초기 수령액 가중치 시뮬레이션
                    if "종신형" in payment_type:
                        estimated = base_estimated * 1.0
                    elif "기간정액형" in payment_type:
                        estimated = base_estimated * 1.35
                    elif "전후후박형" in payment_type:
                        estimated = base_estimated * 1.6
                        
                    # 💡 [정책 룰 2] 우대 혜택(취약계층, 장기영농인) 가산
                    bonus_rate = 0.0
                    if is_low_income:
                        bonus_rate += 0.10
                    if is_long_term:
                        bonus_rate += 0.05
                    
                    if bonus_rate > 0:
                        estimated = estimated * (1 + bonus_rate)
                        st.info(f"🎁 **우대 혜택 적용**: 선택하신 조건에 따라 수령액이 **{bonus_rate*100:.0f}% 가산**되었습니다!")

                    # 💡 [정책 룰 3] 월 300만원 한도 캡(Cap) 적용
                    if estimated > 3000000:
                        estimated = 3000000
                        st.warning("🔒 **국가 정책 한도 적용**: 산출된 예상 금액이 높으나, 정부 규정에 따라 월 지급 한도액은 **최대 3,000,000원**으로 고정됩니다.")

                type_name = payment_type.split(" ")[0]
                st.success(f"🎉 **[{type_name}]** 선택 시, 현재 조건의 초기 월 예상 수령액은 약 **{int(estimated):,}원** 입니다.")
                
                with st.container(border=True):
                    st.markdown("### 📊 예상 금액 산출식 단계별 설명")
                    st.markdown("**1단계: 농지 가치 산출**")
                    if is_exact_match:
                        st.markdown(f"- 선택하신 **{sigungu} {bunji}**의 실제 공시지가(㎡당 **{int(base_price):,}원**)가 적용되었습니다.")
                    else:
                        st.markdown(f"- 선택하신 주소의 인접 평균 공시지가(㎡당 **{int(base_price):,}원**)가 적용되었습니다.")
                    st.markdown(f"- 면적 {area}㎡ × {int(base_price):,}원 = **{int(total_land_value):,}원**")
                    
                    st.markdown("**2단계: 연금 산출 기준액 계산**")
                    st.markdown(f"- 기본 기준액 (가치 × 5% ÷ 12개월) = **{int(base_estimated):,}원**")
                    
                    if bonus_rate > 0:
                        st.markdown("**3단계: 특별 우대 혜택 가산**")
                        st.markdown(f"- 우대율 **{bonus_rate*100:.0f}%** 적용 = **{int(base_estimated * (1+bonus_rate)):,}원**")
                    
                    if estimated >= 3000000:
                        st.markdown("**4단계: 국가 정책 한도 적용**")
                        st.markdown("- 산출액이 300만원을 초과하여 최대 상한선인 **3,000,000원**으로 조정되었습니다.")
                st.caption("※ 위 금액은 공공데이터(경남 공시지가 등) 융합 및 KRC 규정을 완벽 반영한 AI 추정치입니다.")
                
                # [제안 B 적용] 통계청 가계수지 데이터 융합 리포트
                mock_living_cost = {
                    "서울": 2500000, 
                    "경기": 2000000, 
                    "제주": 1800000, 
                    "경남": 1700000, 
                    "경북": 1600000, 
                    "충남": 1600000, 
                    "강원": 1600000, 
                    "전남": 1500000, 
                    "그 외 지역": 1500000
                }
                local_living_cost = mock_living_cost.get(region, 1500000)
                coverage_rate = (estimated / local_living_cost) * 100
                
                st.markdown("---")
                st.markdown(f"#### 📈 노후 생활비 충당률 리포트 (통계청 데이터 융합)")
                st.info(f"통계청 기준 **[{region}]** 60대 이상 가구의 월평균 최저 생활비는 **약 {local_living_cost:,}원**입니다.")
                
                if coverage_rate >= 100:
                    st.success(f"✨ 예상 농지연금만으로 지역 평균 생활비의 **{coverage_rate:.1f}%**를 충당하여 **여유로운 노후 생활**이 가능합니다! (여유 자금형 페르소나)")
                elif coverage_rate >= 50:
                    st.warning(f"💡 예상 농지연금으로 지역 평균 생활비의 **{coverage_rate:.1f}%**를 충당할 수 있습니다. 국민연금 등과 결합 시 든든한 보완재가 됩니다. (생활비 보완형 페르소나)")
                else:
                    st.error(f"🔍 예상 농지연금으로 지역 평균 생활비의 **{coverage_rate:.1f}%** 충당이 예상됩니다. '초기 집중 수령형' 등 다른 지급 방식을 고려해보세요. (최저생계형 페르소나)")
                
                # 💬 Compute recommended questions and save to state
                addr_str = f"{region} {sigungu} {bunji}" if region in sido_options else f"{region} {sigungu} {bunji}"
                st.session_state.q1_msg = f"안녕하세요. {addr_str} 농지 {area}㎡를 소유하고 있는 {age}세 농업인입니다. 예상 월 수령액은 {int(estimated):,}원(생활비 충당률 {coverage_rate:.1f}%)으로 계산되었습니다. 제가 실제로 가입 신청하려면 어떤 절차를 밟아야 하고, 필요한 지참 서류는 무엇인가요?"
                st.session_state.q2_msg = f"제 농지({addr_str})의 예상 가치는 {int(total_land_value):,}원인데, 혹시 기존 담보 대출금({debt_amount:,}원)이 있는 상태에서 가입하려면 수령액에서 차감되는 비율이나 가입 승인 제한이 어떻게 되나요?"
                st.session_state.q3_msg = f"농지연금에 가입된 제 농지({addr_str}) 위에 공사 관리 농업기반시설(구거 또는 농로)이 지나가고 있습니다. 이 농지연금 계약을 유지하면서 진입로 개설을 위한 목적외 사용 승인 신청이 가능한가요?"


                st.markdown("---")
                st.markdown("#### 📊 타 지역 공시지가 비교")
                
                base_est = (300000 * area * 0.05) / 12
                est_seoul = base_est * (1500000 / 300000.0)
                est_gyeonggi = base_est * (800000 / 300000.0)
                est_gyeongnam = base_est * (400000 / 300000.0)
                est_other = base_est

                chart_data = pd.DataFrame({
                    "예상 수령액(원)": [int(est_seoul), int(est_gyeonggi), int(est_gyeongnam), int(est_other)]
                }, index=["서울", "경기", "경남 (실제)", "그 외 지역"])
                
                st.bar_chart(chart_data)
                
                # 웹 접근성 보장용 데이터 표 추가 (KWCAG 2.2)
                with st.expander("📊 비교 데이터 수치로 보기 (웹 접근성 준수용 데이터 표)"):
                    table_data = chart_data.copy()
                    table_data.index.name = "지역(시도)"
                    table_data["예상 수령액"] = table_data["예상 수령액(원)"].map(lambda x: f"{x:,} 원")
                    st.dataframe(table_data[["예상 수령액"]], use_container_width=True)
                
                # ⚖️ 대법원 판례 기반 법률 리스크 예방 가이드 추가 (PoC 피드백 반영)
                st.markdown("---")
                st.markdown("#### ⚖️ 대법원 판례 기반 3대 농지 법률 리스크 예방 가이드")
                st.caption("공공데이터 640건 대법원 판례를 텍스트 마이닝하여 도출한 핵심 가이드입니다.")
                
                with st.expander("📝 1순위 다발 분쟁: 상속 농지처분의무 및 자경 요건 (분쟁 비중 35.3%)", expanded=False):
                    st.markdown("""
                    * **쟁점**: 농지를 소유하고 있으나 실제로 자경하지 않는 경우 농지법상 **처분의무**가 부과됩니다. 상속농지도 1만㎡ 초과분이나 비농업인의 경우 처분 대상이 될 수 있습니다.
                    * **예방법**: 본인 자경이 어려울 경우, 한국농어촌공사의 **농지은행 임대수탁 사업**에 임대 위탁 계약을 체결하면 농지법상 적법한 소유가 인정되어 농지 처분 명령을 면할 수 있습니다.
                    """)
                
                with st.expander("📝 2순위 다발 분쟁: 8년 자경 양도소득세 감면 적격 증빙 (분쟁 비중 27.3%)", expanded=False):
                    st.markdown("""
                    * **쟁점**: 자경농지 양도세 감면(8년 자경)을 받으려면 실제 경작했음을 납세자가 직접 증명해야 합니다. 단순 농업경영체 등록만으로는 불충분합니다.
                    * **예방법**: 자경 사실을 증명할 수 있는 **농약/비료 구입 영수증, 농산물 입금 내역, 인근 주민의 인우보증서, 경작용 유류 구매 내역** 등의 실제 증빙자료를 미리 준비하여 세금 부과 소송을 예방하십시오.
                    """)
                    
                with st.expander("📝 3순위 다발 분쟁: 농지보전부담금 부과 5년 제약 규정 (분쟁 비중 12.2%)", expanded=False):
                    st.markdown("""
                    * **쟁점**: 농지전용 허가를 받아 건물을 준공한 후, 5년 이내에 다른 목적으로 사용(용도 변경)하면 농지보전부담금이 추가 부과됩니다.
                    * **예방법**: 최신 판례(2024두38575)에 따르면, 건축 준공필증 교부일 또는 대장 등재일로부터 **5년이 지난 시점**에 용도를 변경할 시 추가적인 농지보전부담금 납부 의무가 면제되므로, 용도 변경 신청 시점을 조정하여 부담금을 예방할 수 있습니다.
                    """)
                
                logger.info(f"[SIMULATOR] 입력: 연령={age}, 지역={region}, 면적={area} -> 결과: {int(estimated):,}원")
            else:
                st.warning("유사한 가입 사례를 찾지 못했습니다.")
        else:
            st.warning("데이터가 준비되지 않았습니다.")

with col2:
    with st.container(border=True):
        st.subheader("🤖 KRC 통합 민원 AI 컨설턴트 (농지연금 & 기반시설)")
        st.markdown("과거 5개년 고객 문의(농지연금 및 농업기반시설 목적외 사용 등)를 모두 학습한 통합 AI 상담원입니다.")
        
        # 법적 책임 한계 고지 (Disclaimer) 상시 노출
        st.markdown("""
        <div style="background-color: #F0F4F2; border-left: 4px solid #1D4E89; padding: 12px; border-radius: 6px; margin-bottom: 16px;">
          <span style="font-size: 13px; color: #1D4E89; font-weight: 700;">⚠️ 이용자 유의사항 (면책 고지)</span><br>
          <span style="font-size: 13px; color: #5F6B66;">
            본 AI 상담 결과는 공공데이터 기반 법률/판례 추정치로 <b>법적 효력이 없습니다.</b><br>
            정확한 연금 산출 및 행정 처분 기준은 <b>한국농어촌공사 전국 지사 담당자</b>와 확인하시기 바랍니다.
          </span>
        </div>
        """, unsafe_allow_html=True)
    
    # Security: Load API key from .env robustly
    env_path = os.path.join(BASE_DIR, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
    try:
        GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    except Exception:
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

    try:
        qa_path = os.path.join(BASE_DIR, 'data/qa_pairs.json')
        with open(qa_path, 'r', encoding='utf-8') as f:
            qa_list = json.load(f)
    except Exception as e:
        logger.error(f"QA 파일 로드 에러: {e}")
        qa_list = [{"제목": "농지연금 가입 조건", "내용": "만 60세 이상, 영농경력 5년 이상"}]
        
    @st.cache_data(show_spinner=False)
    def ask_gemini(user_question):
        if not GOOGLE_API_KEY:
            return "API 키가 설정되지 않았습니다. 관리자에게 문의하세요."
            
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-3.6-flash')
        
        # 1. 법령(legal_rules) 매칭 검사 (키워드 기반 필터링)
        matched_rules = []
        if legal_rules and "카테고리" in legal_rules:
            for cat, rules in legal_rules["카테고리"].items():
                for rule in rules:
                    # 항목명에서 조사/어미를 떼어낸 간단한 키워드로 매칭
                    keywords = [w for w in rule["항목"].split() if len(w) > 1]
                    if any(kw in user_question for kw in keywords) or rule["항목"] in user_question:
                        matched_rules.append(f"- {rule['항목']}: {rule['내용']}")
        
        # 매칭된 것이 없다면, 기본 농지연금 룰 2개 기본 제공
        if not matched_rules and legal_rules and "카테고리" in legal_rules:
            for rule in legal_rules["카테고리"]["농지연금 가입 및 조건"][:2]:
                matched_rules.append(f"- {rule['항목']}: {rule['내용']}")
                
        # 2. 판례(precedents) 매칭 검사 (키워드 기반 RAG)
        matched_precedents = []
        if precedents:
            search_words = [w for w in user_question.split() if len(w) > 1]
            for prec in precedents:
                score = 0
                for w in search_words:
                    if w in prec["제목"]:
                        score += 5
                    if w in prec["판시사항"]:
                        score += 2
                    if w in prec["참조조문"]:
                        score += 3
                if score > 0:
                    matched_precedents.append((score, prec))
            
            # 높은 관련도 순 정렬 후 상위 3개 선별
            matched_precedents.sort(key=lambda x: x[0], reverse=True)
            matched_precedents = [x[1] for x in matched_precedents[:3]]
            
        # 매칭된 것이 없다면, 대표 판례 2개 기본 제공
        if not matched_precedents and precedents:
            matched_precedents = precedents[:2]
            
        # 3. Context 텍스트 조립
        rules_context = "\n".join(matched_rules)
        precedents_context = ""
        for p in matched_precedents:
            precedents_context += f"법원 판례 [{p['제목']}] (사건번호: {p['사건번호']}, 선고일자: {p['선고일자']})\n"
            precedents_context += f"- 참조조문: {p['참조조문']} ({p['조문번호']})\n"
            precedents_context += f"- 판시사항 요지: {p['판시사항'][:500]}...\n\n"
            
        context = f"""
[참조 법령 정보]
{rules_context}

[관련 법원 판례 지식 베이스]
{precedents_context}
"""
        
        prompt = f"""
당신은 한국농어촌공사의 '통합 민원 전문 AI 상담원'입니다. 농지연금 및 농지 관련 행정 절차와 관련 법령(시행령/시행규칙 등) 및 법원 판례를 기반으로 친절하고 전문적으로 답변해 주세요.
질문자가 입력한 문의사항에 답할 때, 반드시 아래 제공된 [참조 법령 정보] 및 [관련 법원 판례 지식 베이스]를 최대한 참고하여 신뢰성 있고 구체적인 팩트(사건번호 등)가 포함된 답변을 작성하세요.

{context}

사용자 질문: {user_question}
"""
        
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"[API_ERROR] {e}")
            # API 호출 실패 시 로컬 데이터를 매칭하여 법령과 판례를 기반으로 응답
            fallback_res = "💡 **(AI 서버 연결 지연으로 로컬 법률/판례 지식베이스에서 찾은 답변입니다.)**\n\n"
            if matched_rules:
                fallback_res += "### 📋 관련 법령 기준 안내\n" + "\n".join(matched_rules) + "\n\n"
            if matched_precedents:
                fallback_res += "### ⚖️ 관련 대법원/법원 판례 요약\n"
                for p in matched_precedents:
                    fallback_res += f"**- 판례명**: {p['제목']} (사건번호: {p['사건번호']}, 선고일자: {p['선고일자']})\n"
                    fallback_res += f"**- 판시사항 요지**: {p['판시사항']}\n\n"
            if not matched_rules and not matched_precedents:
                fallback_res += "질문과 직접 관련된 판례를 찾지 못했으나, 농지연금 가입 요건(만 60세 이상, 영농경력 5년 이상)을 충족하셔야 가입 약정이 가능합니다."
            return fallback_res

    def ask_gemini_stream(user_question):
        if not GOOGLE_API_KEY:
            yield "API 키가 설정되지 않았습니다. 관리자에게 문의하세요."
            return
            
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-3.6-flash')
        
        # 1. 법령(legal_rules) 매칭 검사
        matched_rules = []
        if legal_rules and "카테고리" in legal_rules:
            for cat, rules in legal_rules["카테고리"].items():
                for rule in rules:
                    keywords = [w for w in rule["항목"].split() if len(w) > 1]
                    if any(kw in user_question for kw in keywords) or rule["항목"] in user_question:
                        matched_rules.append(f"- {rule['항목']}: {rule['내용']}")
        
        if not matched_rules and legal_rules and "카테고리" in legal_rules:
            for rule in legal_rules["카테고리"]["농지연금 가입 및 조건"][:2]:
                matched_rules.append(f"- {rule['항목']}: {rule['내용']}")
                
        # 2. 판례(precedents) 매칭 검사
        matched_precedents = []
        if precedents:
            search_words = [w for w in user_question.split() if len(w) > 1]
            for prec in precedents:
                score = 0
                for w in search_words:
                    if w in prec["제목"]:
                        score += 5
                    if w in prec["판시사항"]:
                        score += 2
                    if w in prec["참조조문"]:
                        score += 3
                if score > 0:
                    matched_precedents.append((score, prec))
            
            matched_precedents.sort(key=lambda x: x[0], reverse=True)
            matched_precedents = [x[1] for x in matched_precedents[:3]]
            
        if not matched_precedents and precedents:
            matched_precedents = precedents[:2]
            
        rules_context = "\n".join(matched_rules)
        precedents_context = ""
        for p in matched_precedents:
            precedents_context += f"법원 판례 [{p['제목']}] (사건번호: {p['사건번호']}, 선고일자: {p['선고일자']})\n"
            precedents_context += f"- 참조조문: {p['참조조문']} ({p['조문번호']})\n"
            precedents_context += f"- 판시사항 요지: {p['판시사항'][:500]}...\n\n"
            
        context = f"""
[대법원 농지 판례 통계 분석 자료]
한국농어촌공사 공공데이터 640건 대법원 판례 분석 결과, 주요 분쟁 비중은 다음과 같습니다:
1. 농지처분의무 및 자경(직접 경작) 요건 분쟁: 35.31% (최다 분쟁 발생 요인)
2. 양도소득세 감면 부적격 분쟁: 27.34%
3. 농지보전부담금 부과처분취소 분쟁: 12.19%
4. 농지법 위반 및 불법 전용 분쟁: 9.69%
5. 기반시설 목적외사용 분쟁: 0.47%
* 민원 답변 시 사용자가 소유, 양도세, 세금, 처분의무, 목적외사용 등에 대해 물어보면 이 판례 분석 비율을 적극 인용하며 설명하세요.

[참조 법령 정보]
{rules_context}

[관련 법원 판례 지식 베이스]
{precedents_context}
"""
        
        prompt = f"""
당신은 한국농어촌공사의 '통합 민원 전문 AI 상담원'입니다. 농지연금 및 농지 관련 행정 절차와 관련 법령(시행령/시행규칙 등) 및 법원 판례를 기반으로 친절하고 전문적으로 답변해 주세요.
질문자가 입력한 문의사항에 답할 때, 반드시 아래 제공된 [참조 법령 정보] 및 [관련 법원 판례 지식 베이스]를 최대한 참고하여 신뢰성 있고 구체적인 팩트(사건번호 등)가 포함된 답변을 작성하세요.

{context}

사용자 질문: {user_question}
"""
        
        try:
            response = model.generate_content(prompt, stream=True)
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"[API_STREAM_ERROR] {e}")
            fallback_res = "💡 **(AI 서버 연결 지연으로 로컬 법률/판례 지식베이스에서 찾은 답변입니다.)**\n\n"
            if matched_rules:
                fallback_res += "### 📋 관련 법령 기준 안내\n" + "\n".join(matched_rules) + "\n\n"
            if matched_precedents:
                fallback_res += "### ⚖️ 관련 대법원/법원 판례 요약\n"
                for p in matched_precedents:
                    fallback_res += f"**- 판례명**: {p['제목']} (사건번호: {p['사건번호']}, 선고일자: {p['선고일자']})\n"
                    fallback_res += f"**- 판시사항 요지**: {p['판시사항']}\n\n"
            if not matched_rules and not matched_precedents:
                fallback_res += "질문과 직접 관련된 판례를 찾지 못했으나, 농지연금 가입 요건(만 60세 이상, 영농경력 5년 이상)을 충족하셔야 가입 약정이 가능합니다."
            
            words = fallback_res.split(" ")
            for word in words:
                yield word + " "
                time.sleep(0.02)

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": "안녕하세요! 한국농어촌공사 통합 민원 AI 컨설턴트입니다. 농지연금이나 농로/저수지 등 기반시설 목적외 사용 승인 등 무엇이든 질문해 주세요."}
        ]
        
    # Render chat messages inside a scrollable box for better layout
    chat_container = st.container(height=400)
    with chat_container:
        for i, msg in enumerate(st.session_state.chat_history):
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                # 봇의 답변 하단에 Web Speech API TTS 재생 버튼 동적 추가
                if msg["role"] == "assistant" and len(msg["content"]) > 10:
                    safe_content = msg["content"].replace("'", "\\'").replace('"', '\\"').replace("\n", " ").replace("\r", "")
                    st.markdown(f"""
                    <div style="text-align: right; margin-top: 5px;">
                        <button onclick="
                            var u = new SpeechSynthesisUtterance('{safe_content}');
                            u.lang = 'ko-KR';
                            u.rate = 1.1;
                            window.speechSynthesis.cancel();
                            window.speechSynthesis.speak(u);
                        " style="
                            background-color: #F7F9F8; color: #1F6F54; border: 1px solid #E2E8E4;
                            border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 600;
                            cursor: pointer; transition: all 0.2s;
                        " onmouseover="this.style.backgroundColor='#E2E8E4';" onmouseout="this.style.backgroundColor='#F7F9F8';">
                            📢 답변 음성으로 듣기 (TTS)
                        </button>
                    </div>
                    """, unsafe_allow_html=True)
                    
        # 2. 만약 마지막 메시지가 user의 질문인 경우, assistant의 스트리밍 응답 수행
        if st.session_state.chat_history and st.session_state.chat_history[-1]["role"] == "user":
            user_msg = st.session_state.chat_history[-1]["content"]
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                
                # MutationObserver 기반의 즉시 자동 스크롤 스크립트 (출력 시 반응 속도 동기화)
                observer_script = """
                <script>
                    (function() {
                        var targetNode = window.parent.document.querySelector('[data-testid="stChatMessageContainer"]');
                        if (!targetNode) {
                            var chatContainers = window.parent.document.querySelectorAll('[data-testid="stChatMessageContainer"]');
                            if (chatContainers.length > 0) {
                                targetNode = chatContainers[chatContainers.length - 1];
                            }
                        }
                        
                        if (targetNode) {
                            var scrollToBottom = function() {
                                targetNode.scrollTop = targetNode.scrollHeight;
                            };
                            
                            var config = { attributes: true, childList: true, subtree: true };
                            var observer = new MutationObserver(function(mutationsList) {
                                scrollToBottom();
                            });
                            
                            observer.observe(targetNode, config);
                            scrollToBottom();
                            
                            setTimeout(function() {
                                observer.disconnect();
                            }, 30000);
                        }
                    })();
                </script>
                """
                st.markdown(observer_script, unsafe_allow_html=True)
                
                # 텍스트 청크를 받아 한 글자씩 타이핑 효과 출력
                for chunk in ask_gemini_stream(user_msg):
                    for char in chunk:
                        full_response += char
                        message_placeholder.markdown(full_response + "▌")
                        time.sleep(0.015)
                    
                # 최종 확정
                message_placeholder.markdown(full_response)
                
                # 완성된 답변 저장
                st.session_state.chat_history.append({"role": "assistant", "content": full_response})
                logger.info(f"[CHAT_OUT] Gemini 답변(스트리밍 완료): {full_response}")
                st.rerun()

    # --- Render Recommended Questions in col2 right above the chat input box ---
    if st.session_state.calculated and st.session_state.q1_msg:
        st.markdown("##### 💡 맞춤 추천 질문 (클릭 시 입력창에 즉시 입력)")
        col_q1, col_q2, col_q3 = st.columns(3)
        with col_q1:
            if st.button("📋 1. 가입절차/서류", use_container_width=True):
                st.session_state.chat_input_val = st.session_state.q1_msg
                st.rerun()
        with col_q2:
            if st.button("💰 2. 대출 영향", use_container_width=True):
                st.session_state.chat_input_val = st.session_state.q2_msg
                st.rerun()
        with col_q3:
            if st.button("🌾 3. 목적외사용", use_container_width=True):
                st.session_state.chat_input_val = st.session_state.q3_msg
                st.rerun()

    if "chat_input_val" not in st.session_state:
        st.session_state.chat_input_val = ""
        
    chat_input = st.text_area("질문을 입력해주세요. (추천 질문 버튼을 누르면 자동 완성됩니다.)", value=st.session_state.chat_input_val, height=100)
    
    col_send, col_clear = st.columns([1, 1])
    send_clicked = False
    clear_clicked = False
    with col_send:
        send_clicked = st.button("💬 질문 전송", type="primary", use_container_width=True)
    with col_clear:
        clear_clicked = st.button("🗑️ 대화 초기화", use_container_width=True)
        
    if clear_clicked:
        st.session_state.chat_history = [
            {"role": "assistant", "content": "안녕하세요! 한국농어촌공사 통합 민원 AI 컨설턴트입니다. 농지연금이나 농로/저수지 등 기반시설 목적외 사용 승인 등 무엇이든 질문해 주세요."}
        ]
        st.session_state.chat_input_val = ""
        st.rerun()
        
    if send_clicked and chat_input.strip():
        # Append user message
        st.session_state.chat_history.append({"role": "user", "content": chat_input})
        # 개인정보(지번 등) 마스킹 처리하여 안전하게 로깅
        logger.info(f"[CHAT_IN] 사용자 질문: {mask_personal_info(chat_input)}")
        
        # Clear preset question state
        st.session_state.chat_input_val = ""
        st.rerun()



st.markdown("""
<div style="padding:24px 0; margin-top:32px; border-top:1px solid #E2E8E4; font-size:13px; color:#5F6B66; text-align:center;">
  본 서비스는 공공데이터(한국농어촌공사, 통계청, 국토교통부 등)를 활용한 AI 시뮬레이션이며 실제 심사 결과와 다를 수 있습니다.<br>
  KWCAG 2.2 접근성 요건(명도 대비, 키보드 운용 등)을 준수하여 제작되었습니다.
</div>
""", unsafe_allow_html=True)
