import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
from PIL import Image
import json
import re
import os  # 경로 문제를 방지하기 위해 os 모듈 추가

# ==========================================
# 1. 환경 설정 및 API 키 초기화
# ==========================================
GEMINI_API_KEY = "AIzaSyDZRKcbypeAUTORniX91jU7apA5aYeFFz4"  # 선생님의 Gemini API 키 입력
GOOGLE_SHEET_KEY = "1s1XcEb-7gU4r024eQJXsvDqIab6MeSP9GjpBbP4QShE"  # 마스터 구글 시트 ID 입력

genai.configure(api_key=GEMINI_API_KEY)


# ==========================================
# 2. 구글 시트 연동 및 데이터 추출 함수
# ==========================================
# 캐시를 사용해 페이지를 조작할 때마다 구글 서버에 무한 요청하는 것을 방지합니다.
@st.cache_resource
def get_gspread_client():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

        # [경로 에러 해결] 1.py 파일이 있는 폴더의 절대 경로를 계산하여 secrets.json의 정확한 위치를 찾습니다.
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, "secrets.json")

        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"구글 시트 인증 실패: {e}")
        return None


# 마스터 시트에서 모든 워크시트(학반 탭) 이름 읽어오기
def get_all_sheet_names():
    client = get_gspread_client()
    if client:
        try:
            doc = client.open_by_key(GOOGLE_SHEET_KEY)
            # 모든 시트의 제목(탭 이름)을 리스트로 반환
            return [worksheet.title for worksheet in doc.worksheets()]
        except Exception as e:
            st.error(f"시트 목록 불러오기 실패: {e}")
    return ["녹산초 3-7반 데이터"]  # 실패 시 예외 방지용 기본값


# 선택한 학반 탭에서 학생 이름 목록(F열) 읽어오기
def get_student_names(sheet_name):
    client = get_gspread_client()
    if client:
        try:
            doc = client.open_by_key(GOOGLE_SHEET_KEY)
            sheet = doc.worksheet(sheet_name)

            # F열(성명 또는 마스킹성명) 데이터 가져오기 (F열은 6번째 열)
            # col_values(6)을 하면 1행(헤더인 '성명')부터 쭉 가져옵니다.
            all_f_col = sheet.col_values(6)

            # 첫 번째 행(예: '성명', '이름' 등 분류명)과 빈 칸을 필터링하여 학생 명단만 추출
            students = [name for name in all_f_col[1:] if name.strip()]
            return students
        except Exception as e:
            st.error(f"학생 명단 불러오기 실패: {e}")
    return []


# K열(섭취칼로리) 업데이트 함수
def update_calories_to_sheet(sheet_name, student_name, calories):
    client = get_gspread_client()
    if client:
        try:
            doc = client.open_by_key(GOOGLE_SHEET_KEY)
            sheet = doc.worksheet(sheet_name)

            # 이름이 일치하는 학생의 고유 행(Row) 찾기
            cell = sheet.find(student_name)
            row_idx = cell.row

            # K열(11번째 열)에 데이터 업데이트
            sheet.update_cell(row_idx, 11, calories)
            return True
        except Exception as e:
            st.error(f"구글 시트 업데이트 실패: {e}")
    return False


# ==========================================
# 3. 멀티모달 AI (Gemini) 식단 분석 함수
# ==========================================
def analyze_diet_image(image):
    try:
        model = genai.GenerativeModel('gemini-3.5-flash')
        prompt = (
            "당신은 초등학교 영양사 AI입니다. 제공된 학생의 급식 사진을 분석하여 음식의 종류와 양을 파악하세요. "
            "그 후 초등학생 1끼 권장 칼로리를 기준으로 총 섭취 칼로리를 유추하세요. "
            "출력은 다른 설명이나 텍스트를 일절 배제하고, 반드시 아래 JSON 포맷으로만 답변하세요: "
            '{"calories": 450, "analysis": "쌀밥, 미역국, 제육볶음, 김치"}'
        )
        response = model.generate_content([prompt, image])

        text_data = response.text
        clean_json = re.search(r'\{.*\}', text_data, re.DOTALL).group(0)
        result = json.loads(clean_json)
        return result
    except Exception as e:
        st.error(f"AI 분석 실패: {e}")
        return None


# ==========================================
# 4. Streamlit UI 화면 구성
# ==========================================
st.set_page_config(page_title="AI 영양사 분석기", page_icon="🍎", layout="centered")

st.title("🍎 멀티모달 AI 영양사 분석기")
st.write("급식 사진을 찍으면 AI가 자동으로 칼로리를 계산하여 우리 반 성장 트래커로 보내줍니다.")

st.subheader("👤 학생 정보 선택")

# [실시간 동기화 1단계] 마스터 구글 시트에서 학반(탭) 목록 알아서 긁어오기
sheet_list = get_all_sheet_names()

col1, col2 = st.columns(2)
with col1:
    class_tab = st.selectbox("학반 선택", sheet_list)

# [실시간 동기화 2단계] 위에서 선택한 학반의 F열 학생 명단 실시간으로 긁어오기
student_list = get_student_names(class_tab)

with col2:
    if student_list:
        student_name = st.selectbox("나의 이름은?", student_list)
    else:
        student_name = st.selectbox("나의 이름은?", ["명단을 가져올 수 없습니다"])

st.subheader("📸 식단 촬영")
img_file = st.camera_input("급식판이 잘 보이도록 촬영해 주세요")

if img_file is not None:
    image = Image.open(img_file)
    st.image(image, caption="촬영된 식단 사진",use_container_width=True)

    if st.button("🤖 AI 영양사에게 분석 요청하기", type="primary"):
        with st.spinner("AI가 오늘의 급식을 영양 분석 중입니다..."):
            analysis_result = analyze_diet_image(image)

            if analysis_result:
                calories = analysis_result.get("calories", 0)
                diet_details = analysis_result.get("analysis", "분석 불가")

                st.success("🎉 분석 완료!")
                st.metric(label="📊 판정 섭취 칼로리", value=f"{calories} kcal")
                st.info(f"🥗 **식단 판별 결과:** {diet_details}")

                with st.spinner("중앙 마스터 DB(구글 시트)로 전송 중..."):
                    success = update_calories_to_sheet(class_tab, student_name, calories)
                    if success:
                        st.balloons()
                        st.success(f"➔ {class_tab}의 [{student_name}] 학생 행 K열에 {calories}kcal가 실시간으로 입력되었습니다!")