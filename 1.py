import streamlit as st
import gspread
import google.generativeai as genai
from PIL import Image
import json
from google.oauth2.service_account import Credentials

# ==========================================
# 1. 환경 설정 및 API 키 (Secrets에서 불러오기)
# ==========================================
# 이제 API 키도 하드코딩하지 않고 Secrets에서 불러와야 안전합니다!
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
GOOGLE_SHEET_KEY = "1s1XcEb-7gU4r024eQJXsvDqIab6MeSP9GjpBbP4QShE"

# ==========================================
# 2. 구글 시트 연동 함수 (수정됨)
# ==========================================
@st.cache_resource
def get_gspread_client():
    try:
        # 스트림릿 Secrets에서 GCP_CREDENTIALS 가져오기
        creds_dict = json.loads(st.secrets["GCP_CREDENTIALS"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # JSON 정보로 인증 객체 생성
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"구글 시트 인증 실패: {e}")
        return None

def get_all_sheet_names():
    client = get_gspread_client()
    if client:
        try:
            doc = client.open_by_key(GOOGLE_SHEET_KEY)
            return [worksheet.title for worksheet in doc.worksheets()]
        except Exception as e:
            st.error(f"시트 목록 불러오기 실패: {e}")
    return ["녹산초 3-7반 데이터"]

def get_student_names(sheet_name):
    client = get_gspread_client()
    if client:
        try:
            doc = client.open_by_key(GOOGLE_SHEET_KEY)
            sheet = doc.worksheet(sheet_name)
            all_f_col = sheet.col_values(6)
            students = [name for name in all_f_col[1:] if name.strip()]
            return students
        except Exception as e:
            st.error(f"학생 명단 불러오기 실패: {e}")
    return []

def update_calories_to_sheet(sheet_name, student_name, calories):
    client = get_gspread_client()
    if client:
        try:
            doc = client.open_by_key(GOOGLE_SHEET_KEY)
            sheet = doc.worksheet(sheet_name)
            cell = sheet.find(student_name)
            row_idx = cell.row
            sheet.update_cell(row_idx, 11, calories) # K열 업데이트
            return True
        except Exception as e:
            st.error(f"구글 시트 업데이트 실패: {e}")
    return False

# ==========================================
# 3. 멀티모달 AI (Gemini) 식단 분석
# ==========================================
def analyze_diet_image(image):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash') # 모델명 최신화
        prompt = (
            "당신은 초등학교 영양사 AI입니다. 급식 사진을 분석하여 총 섭취 칼로리를 유추하세요."
            "반드시 아래 JSON 포맷으로만 답변하세요: "
            '{"calories": 450, "analysis": "분석내용"}'
        )
        response = model.generate_content([prompt, image])
        # JSON 부분만 추출하는 정규식
        import re
        clean_json = re.search(r'\{.*\}', response.text, re.DOTALL).group(0)
        return json.loads(clean_json)
    except Exception as e:
        st.error(f"AI 분석 실패: {e}")
        return None

# ==========================================
# 4. Streamlit UI
# ==========================================
st.set_page_config(page_title="AI 영양사 분석기", page_icon="🍎", layout="centered")

st.title("🍎 멀티모달 AI 영양사 분석기")
st.write("급식 사진을 찍으면 AI가 자동으로 칼로리를 계산합니다.")

sheet_list = get_all_sheet_names()
class_tab = st.selectbox("학반 선택", sheet_list)
student_list = get_student_names(class_tab)
student_name = st.selectbox("나의 이름은?", student_list if student_list else ["명단을 가져올 수 없습니다"])

img_file = st.camera_input("급식판이 잘 보이도록 촬영해 주세요")

if img_file is not None:
    image = Image.open(img_file)
    st.image(image, caption="촬영된 식단", use_container_width=True)
    if st.button("🤖 분석 요청하기", type="primary"):
        with st.spinner("AI 분석 중..."):
            res = analyze_diet_image(image)
            if res:
                st.metric("판정 섭취 칼로리", f"{res['calories']} kcal")
                st.info(f"식단: {res['analysis']}")
                if update_calories_to_sheet(class_tab, student_name, res['calories']):
                    st.success("데이터 전송 완료!")
