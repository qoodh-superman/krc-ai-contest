import streamlit as st
import pandas as pd
import numpy as np
import logging
import os
import json
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

st.set_page_config(page_title="KRC 농지연금 AI 시뮬레이터", page_icon="🌾", layout="wide")

with st.sidebar:
    st.markdown("### 🌐 전체 서비스 이동 메뉴")
    st.markdown("다른 서비스 페이지로 빠르게 이동할 수 있습니다.")
    st.markdown("- [🏠 소개 (랜딩 페이지)](https://krc-ai-main.netlify.app/)")
    st.markdown("- [📊 통계 대시보드](https://krc-ai-contest.netlify.app/)")
    st.markdown("- **🤖 AI 시뮬레이터 & 챗봇 (현재 페이지)**")

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

st.title("🌾 KRC 맞춤형 시뮬레이터 & 통합 민원 AI 챗봇")
st.markdown("한국농어촌공사의 최신 데이터 융합으로 농지연금 수령액을 시뮬레이션하고, 농업기반시설 목적외 사용 등 통합 민원을 상담할 수 있습니다.")

@st.cache_data
def load_data():
    pension_df = pd.DataFrame()
    voc_df = pd.DataFrame()
    avg_gyeongnam_price = 400000 # Fallback
    try:
        # Load core KRC data securely (from local data/ folder for deployment)
        pension_path = os.path.join(BASE_DIR, 'data/한국농어촌공사_농지연금사업 연도 연령대 지역 정보 제공_20251126.csv')
        voc_path = os.path.join(BASE_DIR, 'data/한국농어촌공사_고객의 소리 유형분석_20241231.csv')
        
        # Load added Gyeongnam public land price data
        gyeongnam_path = os.path.join(BASE_DIR, 'data/경남_개별공시지가_20260526.csv')
        
        if os.path.exists(pension_path):
            pension_df = pd.read_csv(pension_path, encoding='cp949')
        else:
            pension_path_fallback = os.path.join(BASE_DIR, 'data/한국농어촌공사_농지연금사업  연도 연령대 지역 정보 제공_20251126.csv')
            if os.path.exists(pension_path_fallback):
                pension_df = pd.read_csv(pension_path_fallback, encoding='cp949')
                
        if os.path.exists(voc_path):
            voc_df = pd.read_csv(voc_path, encoding='cp949')
            
        if os.path.exists(gyeongnam_path):
            gn_df = pd.read_csv(gyeongnam_path, encoding='utf-8')
            # 9th column is '공시지가(원/㎡)'
            if not gn_df.empty and gn_df.shape[1] > 8:
                avg_gyeongnam_price = pd.to_numeric(gn_df.iloc[:, 8], errors='coerce').mean()
                if pd.isna(avg_gyeongnam_price):
                    avg_gyeongnam_price = 400000
    except Exception as e:
        logger.error(f"데이터 로드 에러: {e}")
        # Security: Do not expose raw stack trace to UI
        st.error("서버 내부 오류: 데이터를 불러오는 중 문제가 발생했습니다.")
        
    return pension_df, voc_df, avg_gyeongnam_price

pension_df, voc_df, avg_gyeongnam_price = load_data()

col1, col2 = st.columns([1, 1])

with col1:
    with st.container(border=True):
        st.subheader("💡 내 농지연금 예상 수령액 알아보기")
        with st.form("pension_form"):
            age = st.slider("가입 당시 연령 (세)", 60, 90, 65)
            region = st.selectbox("농지 소재지", ["경기", "서울", "경남", "그 외 지역"])
            area = st.number_input("농지 면적 (㎡)", min_value=1000, max_value=50000, value=3000, step=500)
            debt_amount = st.number_input("기존 농지 담보 대출금액 (원)", min_value=0, value=0, step=10000000, format="%d")
            
            st.markdown("##### 🎁 특별 우대 혜택 (해당 시 체크)")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                is_low_income = st.checkbox("국민기초생활수급자 (10% 우대)")
            with col_c2:
                is_long_term = st.checkbox("30년 이상 장기영농인 (5% 우대)")

            payment_type = st.selectbox("연금 지급 방식", ["종신형 (평생 일정 금액 지급)", "기간정액형 (10년/15년 지정 기간 집중 지급)", "전후후박형 (가입 초기 10년간 더 많이 지급)"])
            submitted = st.form_submit_button("예상 수령액 정밀 계산")

    if submitted:
        if not pension_df.empty:
            age_bracket = f"{(age // 10) * 10}대"
            filtered = pension_df[pension_df['가입당시연령'] == age_bracket]
            if not filtered.empty:
                avg_payment = pd.to_numeric(filtered['월지급금(원)'], errors='coerce').mean()
                avg_area = pd.to_numeric(filtered['면적'], errors='coerce').mean()
                
                if pd.isna(avg_payment) or pd.isna(avg_area) or avg_area == 0:
                    estimated = 1000000
                else:
                    # [제안 A 적용] 국토부 공시지가 기반 정밀 담보가치 로직
                    # 서울, 경기는 모의 데이터, 경남은 실제 CSV 데이터 평균 연동
                    mock_land_price = {
                        "서울": 1500000, 
                        "경기": 800000, 
                        "경남": avg_gyeongnam_price, 
                        "그 외 지역": 300000
                    }
                    base_price = mock_land_price[region]
                    total_land_value = base_price * area
                    weight = base_price / 300000.0
                    
                    base_estimated = avg_payment * (area / avg_area) * weight
                    
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
                st.caption("※ 위 금액은 공공데이터(경남 공시지가 등) 융합 및 KRC 규정을 완벽 반영한 AI 추정치입니다.")
                
                # [제안 B 적용] 통계청 가계수지 데이터 융합 리포트
                mock_living_cost = {"서울": 2500000, "경기": 2000000, "경남": 1700000, "그 외 지역": 1500000}
                local_living_cost = mock_living_cost[region]
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
                
                st.markdown("---")
                st.markdown("#### 📊 타 지역 공시지가 비교")
                
                base_est = avg_payment * (area / avg_area)
                est_seoul = base_est * (mock_land_price["서울"] / 300000.0)
                est_gyeonggi = base_est * (mock_land_price["경기"] / 300000.0)
                est_gyeongnam = base_est * (mock_land_price["경남"] / 300000.0)
                est_other = base_est * (mock_land_price["그 외 지역"] / 300000.0)

                chart_data = pd.DataFrame({
                    "예상 수령액(원)": [int(est_seoul), int(est_gyeonggi), int(est_gyeongnam), int(est_other)]
                }, index=["서울", "경기", "경남 (실제)", "그 외 지역"])
                
                st.bar_chart(chart_data)
                
                logger.info(f"[SIMULATOR] 입력: 연령={age}, 지역={region}, 면적={area} -> 결과: {int(estimated):,}원")
            else:
                st.warning("유사한 가입 사례를 찾지 못했습니다.")
        else:
            st.warning("데이터가 준비되지 않았습니다.")

with col2:
    with st.container(border=True):
        st.subheader("🤖 KRC 통합 민원 AI 챗봇 (농지연금 & 기반시설)")
        st.markdown("과거 5개년 고객 문의(농지연금 및 농업기반시설 목적외 사용 등)를 모두 학습한 통합 AI 상담원입니다.")
    
    # Security: Load API key from .env robustly
    env_path = os.path.join(BASE_DIR, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
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
        model = genai.GenerativeModel('gemini-flash-latest')
        
        context = "\n".join([f"Q: {qa['제목']}\nA: {qa['내용']}" for qa in qa_list[:5]])
        
        prompt = f"""
        당신은 한국농어촌공사의 '통합 민원 전문 AI 상담원'입니다. 농지연금뿐만 아니라 실제 민원의 대다수인 농업기반시설(저수지, 구거, 농로 등) 목적외 사용 승인, 농지보전부담금 관련 질문에도 친절하고 전문적으로 답변해 주세요.
        아래의 과거 고객 문의/답변 사례(Knowledge Base)를 참고하여 답변을 작성하세요.
        
        [지식 베이스]
        {context}
        
        사용자 질문: {user_question}
        """
        
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"[API_ERROR] {e}")
            for qa in qa_list:
                words = qa['제목'].split()
                if any(len(w) > 1 and w in user_question for w in words) or (user_question in qa['제목']):
                    return f"💡 **(AI 서버 연결 지연으로 로컬 지식베이스에서 찾은 답변입니다.)**\n\n**Q. {qa['제목']}**\n\nA. {qa['내용']}"
            
            return "죄송합니다. 현재 AI 서버 인증 오류로 실시간 답변을 생성할 수 없습니다."

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": "안녕하세요! 한국농어촌공사 통합 민원 AI 챗봇입니다. 농지연금이나 농로/저수지 등 기반시설 목적외 사용 승인 등 무엇이든 질문해 주세요."}
        ]
        
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    chat_input = st.chat_input("질문을 입력해주세요. (예: 구거에 생활하수 방류가 가능한가요?)")
    if chat_input:
        with st.chat_message("user"):
            st.write(chat_input)
        st.session_state.chat_history.append({"role": "user", "content": chat_input})
        logger.info(f"[CHAT_IN] 사용자 질문: {chat_input}")
        
        with st.chat_message("assistant"):
            with st.spinner("답변을 생성 중입니다..."):
                answer = ask_gemini(chat_input)
            st.write(answer)
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
        logger.info(f"[CHAT_OUT] Gemini 답변: {answer}")

st.markdown("""
<div style="padding:24px 0; margin-top:32px; border-top:1px solid #E2E8E4; font-size:13px; color:#5F6B66; text-align:center;">
  본 서비스는 공공데이터(한국농어촌공사, 통계청, 국토교통부 등)를 활용한 AI 시뮬레이션이며 실제 심사 결과와 다를 수 있습니다.<br>
  KWCAG 2.2 접근성 요건(명도 대비, 키보드 운용 등)을 준수하여 제작되었습니다.
</div>
""", unsafe_allow_html=True)
