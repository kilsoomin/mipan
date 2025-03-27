import json
import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import requests
import time
from datetime import datetime
import pandas as pd
import uuid
import os

# 서비스 계정 키 파일 경로 (같은 폴더에 있어야 함)
firebase_key_path = "jaegodata-c89b1-firebase-adminsdk-fbsvc-6ec8b5d4cd.json"  # 파일명 수정

# Firebase 연결
if not firebase_admin._apps:
    if os.path.exists(firebase_key_path):  # 로컬에 파일이 있는지 확인
        try:
            # .json 파일을 이용해 Firebase 인증
            cred = credentials.Certificate(firebase_key_path)
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://jaegodata-c89b1-default-rtdb.asia-southeast1.firebasedatabase.app/'
            })
            print("Firebase 인증 성공!")
        except Exception as e:
            print(f"Firebase 인증 실패: {e}")
    else:
        print("서비스 계정 키 파일을 찾을 수 없습니다. 파일을 올바른 경로에 저장해주세요.")
    })

# ✅ 페이지 설정
# 제목 대신, 여백 최소화된 h4 사용
st.markdown("<h4 style='margin-top: 0; margin-bottom: 8px;'>📦 미판건 관리</h4>", unsafe_allow_html=True)


# ✅ 로그인 상태 관리
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# ✅ 로그인 함수
def login(username, password):
    ref = db.reference('users')
    users = ref.get()
    if users and username in users and str(users[username]) == password:
        return True
    return False

# ✅ 로그 기록 함수
def log_activity(user, action, pnum, rfid=None, price=None):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    log_ref = db.reference("logs").child(timestamp)
    log_data = {
        "사용자": user,
        "작업": action,
        "품번": pnum,
    }
    if rfid is not None:
        log_data["RFID"] = rfid
    if price is not None:
        log_data["가격"] = price
    log_ref.set(log_data)

# ✅ 가격 크롤링 함수
def get_token():
    token_url = "https://nxapi.lfmall.co.kr/common/v1/token"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(token_url, headers=headers)
        if response.status_code == 200:
            token_data = response.json()
            return token_data["body"]["token"]
        else:
            print(f"토큰 요청 실패: {response.status_code}")
            return None
    except Exception as e:
        print(f"토큰 요청 중 오류 발생: {e}")
        return None

def get_price_from_lfmall(pnum):
    token = get_token()
    if not token:
        return None

    price_url = f"https://nxapi.lfmall.co.kr/product/v1/price/{pnum}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Authorization": f"Bearer {token}"
    }

    try:
        response = requests.get(price_url, headers=headers)
        if response.status_code == 200:
            text = response.text
            key = '"originalPrice":'
            idx = text.find(key)
            if idx != -1:
                start = idx + len(key)
                end = text.find(",", start)
                price_str = text[start:end].strip()
                return int(price_str)
            else:
                return None
        else:
            return None
    except Exception as e:
        print(f"가격 요청 오류: {e}")
        return None

# ✅ 자동 콤마 입력 처리 함수
def comma_input(label, key):
    raw = st.text_input(label, key=key)
    cleaned = raw.replace(",", "").strip()

    if cleaned.isdigit():
        return int(cleaned)
    else:
        return 0



# ✅ 로그인 UI
if not st.session_state.authenticated:
    st.title("🔐 로그인")
    ref = db.reference('users')
    users = ref.get()
    if users:
        user_list = list(users.keys())
        username = st.selectbox("이름", user_list)
        password = st.text_input("비밀번호", type="password", key="login_pw")
        login_button = st.button("로그인", use_container_width=True)

        if login_button:
            if users and username in users and str(users[username]) == password:
                st.success("✅ 로그인 성공!")
                st.session_state.authenticated = True
                st.session_state.user = username
                st.rerun()
            else:
                st.error("❌ 로그인 실패! 이름 또는 비밀번호를 확인하세요.")
    else:
        st.warning("❗ 사용자 목록이 비어 있습니다.")
    st.stop()




# 탭 정의 (기존 탭 + 새 탭 추가)
tabs = st.tabs([
    "🔎 데이터 검색",       # tabs[0]
    "📥 데이터 등록",       # tabs[1]
    "📥 다중 품번 등록",    # tabs[2]
    "📐 엑셀 업로드",       # tabs[3]
    "📊 EDI 비교",          # tabs[4]
    "📜 로그 조회",         # tabs[5]
    "🔐 비밀번호 변경"      # tabs[6]
])

# 상단 padding 제거용 스타일 삽입
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1rem !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

with tabs[0]:
    st.subheader("🔎 등록 데이터 검색")

    if "search_query" not in st.session_state:
        st.session_state.search_query = ""
    if "last_query" not in st.session_state:
        st.session_state.last_query = ""

    input_query = st.text_input("품번 검색", key="input_query").upper()
    search_button = st.button("검색", use_container_width=True)

    if search_button or (
        "input_query" in st.session_state
        and st.session_state.input_query
        and st.session_state.input_query != st.session_state.get("last_query")
    ):
        st.session_state.search_query = st.session_state.input_query
        st.session_state.search_triggered = True
        st.session_state.last_query = st.session_state.input_query

    if st.session_state.get("search_triggered", False):
        if not st.session_state.search_query:
            st.warning("❗ 검색어를 입력해주세요.")
        else:
            ref = db.reference('products')
            all_products = ref.get()

            matched = []

            if all_products:  # ✅ None 방지용 체크!
                for key, value in all_products.items():
                    if st.session_state.search_query.upper() in value.get("품번", "").upper():
                        matched.append((key, value))

                if matched:
                    st.success(f"🔍 검색 결과 {len(matched)}건")  # ✅ 여기로 이동 (루프 바깥!)
                    
                    sort_option = st.selectbox("정렬 기준", ["과거순", "최신순", "가격높은순", "가격낮은순"])
                    if sort_option == "최신순":
                        matched.sort(key=lambda x: x[1].get("timestamp", 0), reverse=True)
                    elif sort_option == "과거순":
                        matched.sort(key=lambda x: x[1].get("timestamp", 0))
                    elif sort_option == "가격높은순":
                        matched.sort(key=lambda x: x[1].get("가격", 0), reverse=True)
                    elif sort_option == "가격낮은순":
                        matched.sort(key=lambda x: x[1].get("가격", 0))

                    for key, item in matched:
                        pnum = item.get('품번', 'N/A')
                        price = item.get('가격', 0)
                        rfid = item.get('RFID', 'N/A')
                        memo = item.get("메모", "")
                        timestamp = item.get("timestamp", 0)
                        date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d") if timestamp else "등록일 없음"

                        with st.container():
                            st.markdown(f"""<div style='padding: 10px; background-color: #f9f9f9; border-radius: 8px;'>
                                <strong>📦 품번:</strong> {pnum} <br>
                                <strong>📅 등록일:</strong> {date_str} <br>
                                <strong>💰 가격:</strong> {int(price):,}원 <br>
                                <strong>🛰️ RFID:</strong> {rfid}
                            </div>""", unsafe_allow_html=True)

                            # ✅ 메모 입력창
                            memo_input = st.text_input("✏️ 메모", value=memo, key=f"memo_{key}")
                            if st.button("💾 메모 저장", key=f"save_memo_{key}", use_container_width=True):
                                db.reference(f"products/{key}/메모").set(memo_input)
                                log_activity(st.session_state.user, "메모 저장", pnum, rfid, price)
                                st.success("✅ 메모 저장 완료!")
                                st.rerun()

                            # ✅ 삭제 버튼
                            confirm_key = f"confirm_delete_{key}"
                            if confirm_key not in st.session_state:
                                st.session_state[confirm_key] = False

                            if not st.session_state[confirm_key]:
                                if st.button(f"🗑️ 삭제", key=f"delete_btn_{key}", use_container_width=True):
                                    st.session_state[confirm_key] = True
                                    st.rerun()
                            else:
                                st.warning(f"❗ 정말로 {pnum} 데이터를 삭제하시겠습니까?")
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.button("✅ 네, 삭제합니다", key=f"yes_delete_{key}", use_container_width=True):
                                        db.reference(f'products/{key}').delete()
                                        log_activity(st.session_state.user, "삭제", pnum, rfid, price)
                                        st.success(f"🗑️ {pnum} 삭제 완료")
                                        del st.session_state[confirm_key]
                                        st.rerun()
                                with col2:
                                    if st.button("❌ 취소", key=f"cancel_delete_{key}", use_container_width=True):
                                        st.session_state[confirm_key] = False
                                        st.rerun()
                else:
                    st.warning("❗ 검색 결과가 없습니다.")
            else:
                st.warning("⚠️ 등록된 데이터가 없습니다.")




import uuid  # 👈 꼭 맨 위에 추가되어 있어야 함!

with tabs[1]:
    st.subheader("📥 미판건 등록")
    with st.form("add_product_form"):
        pnum = st.text_input("품번", max_chars=20).strip().upper()
        rfid = st.text_input("RFID", max_chars=50).strip().upper()
        submitted = st.form_submit_button("등록하기", use_container_width=True)

        if submitted:
            if not pnum or not rfid:
                st.warning("❗ 품번과 RFID는 필수 입력값입니다.")
            else:
                # ✅ RFID가 'X'면 uuid 붙여서 고유키 생성
                if rfid == "X":
                    key_suffix = f"NOID_{uuid.uuid4().hex[:6]}"
                    unique_key = f"{pnum}_{key_suffix}"
                    rfid_value = None
                else:
                    unique_key = f"{pnum}_{rfid}"
                    rfid_value = rfid

                ref = db.reference('products')
                existing = ref.child(unique_key).get()

                if existing:
                    st.error("❌ 동일한 품번과 RFID가 이미 등록되어 있습니다.")
                else:
                    price = get_price_from_lfmall(pnum)
                    if price is None:
                        st.error(f"❌ {pnum} 가격 정보를 불러오지 못했습니다. (API 실패 또는 품번 오류)")
                    else:
                        ref.child(unique_key).set({
                            "품번": pnum,
                            "timestamp": int(time.time()),
                            "가격": price,
                            "RFID": rfid_value
                        })

                        log_activity(st.session_state.user, "등록", pnum, rfid_value, price)

                        st.success(f"✅ {pnum} 등록 완료! (가격: {price:,}원)")


import uuid  # 👈 이거 상단에 이미 import 되어 있어야 함!

with tabs[2]:
    st.subheader("📥 다중 품번 등록")
    product_data = []
    num_entries = st.number_input("품번 및 RFID 입력 개수", min_value=1, value=1)

    for i in range(num_entries):
        pnum = st.text_input(f"품번 {i+1}", key=f"pnum_{i}").strip().upper()
        rfid = st.text_input(f"RFID {i+1}", key=f"rfid_{i}").strip().upper()
        if pnum and rfid:
            product_data.append((pnum, rfid))

    submitted = st.button("등록하기", use_container_width=True)

    if submitted:
        if not product_data:
            st.warning("❗ 품번과 RFID를 입력해주세요.")
        else:
            ref = db.reference('products')
            for pnum, rfid in product_data:
                if rfid == "X":
                    key_suffix = f"NOID_{uuid.uuid4().hex[:6]}"
                    unique_key = f"{pnum}_{key_suffix}"
                    rfid_value = None
                else:
                    unique_key = f"{pnum}_{rfid}"
                    rfid_value = rfid

                price = get_price_from_lfmall(pnum)

                if price is None:
                    st.error(f"❌ {pnum} 가격 정보를 불러오지 못했습니다. (API 실패 또는 품번 오류)")
                else:
                    existing = ref.child(unique_key).get()
                    if existing:
                        st.warning(f"❌ {pnum} (RFID: {rfid})는 이미 등록되어 있습니다.")
                    else:
                        ref.child(unique_key).set({
                            "품번": pnum,
                            "timestamp": int(time.time()),
                            "가격": price,
                            "RFID": rfid_value
                        })
                        st.success(f"✅ {pnum} 등록 완료! (가격: {price:,}원)")


with tabs[6]:
    st.subheader("🔐 비밀번호 변경")
    current_user = st.session_state.get("user")
    if not current_user:
        st.warning("로그인한 사용자만 비밀번호를 변경할 수 있습니다.")
        st.stop()

    current_pw = st.text_input("현재 비밀번호", type="password")
    new_pw = st.text_input("새 비밀번호", type="password")
    confirm_pw = st.text_input("새 비밀번호 확인", type="password")
    change_btn = st.button("변경하기")

    if change_btn:
        users_ref = db.reference("users")
        users = users_ref.get()
        if current_user in users and str(users[current_user]) == current_pw:
            if new_pw != confirm_pw:
                st.warning("❗ 새 비밀번호와 확인이 일치하지 않습니다.")
            elif len(new_pw) < 4:
                st.warning("❗ 비밀번호는 최소 4자리 이상이어야 합니다.")
            else:
                users_ref.child(current_user).set(new_pw)
                st.success("✅ 비밀번호가 성공적으로 변경되었습니다.")
        else:
            st.error("❌ 현재 비밀번호가 일치하지 않습니다.")


# 📊 EDI 비교
with tabs[4]:
    st.subheader("📊 EDI 비교")

    allowed_users = ["길수민"]
    if current_user not in allowed_users:
        st.warning("🚫 이 페이지는 접근 권한이 있는 사용자만 사용할 수 있습니다.")
        st.stop()

    # ✅ 콤마 자동 입력 필드로 대체
    edi_amount = comma_input("EDI 금액", key="edi_input")
    pos_amount = comma_input("POS 금액", key="pos_input")

    # ✅ 미판등 정가 계산
    ref = db.reference("products")
    all_products = ref.get()

    total_price = sum(item.get("가격", 0) for item in all_products.values()) if all_products else 0
    st.info(f"💰 미판등 정가 총합: {total_price:,}원")

    # ✅ 할인율 선택
    discount_rate = st.selectbox("할인율 선택", ["10%", "15%", "19%"])
    rate = int(discount_rate.replace("%", ""))
    discounted_total = total_price * (1 - rate / 100)

    st.write(f"✅ 할인 적용 금액: {discounted_total:,.0f}원")

    # ✅ 차이 금액
    difference = edi_amount - (pos_amount + discounted_total)
    st.success(f"📉 차이 금액: {difference:,.0f}원")


with tabs[5]:
    st.subheader("📜 최근 활동 이력")

    # ✅ 관리자 권한 확인
    allowed_users = ["길수민"]
    if st.session_state.user not in allowed_users:
        st.warning("🚫 이 기능은 관리자 전용입니다.")
        st.stop()

    # ✅ 로그 불러오기
    logs = db.reference("logs").get()

    if not logs:
        st.info("🕓 저장된 로그가 없습니다.")
    else:
        sorted_logs = sorted(logs.items(), reverse=True)  # 최신순 정렬
        for time_str, entry in sorted_logs[:100]:  # 최근 100개만 표시
            user = entry.get("사용자", "N/A")
            action = entry.get("작업", "N/A")
            pnum = entry.get("품번", "N/A")
            rfid = entry.get("RFID", "없음")
            price = entry.get("가격", "N/A")

            log_text = f"""
🔹 사용자: {user}  
🔹 작업: {action}  
🔹 품번: {pnum}  
🔹 RFID: {rfid}  
🔹 가격: {price if isinstance(price, int) else 'N/A'}  
🕒 시간: {time_str}
""".strip()

            st.markdown(f"""
            <div style='padding: 10px; background-color: #f9f9f9; border-radius: 6px; margin-bottom: 8px;'>
                <pre style='margin: 0;'>{log_text}</pre>
            </div>
            """, unsafe_allow_html=True)


with tabs[3]:
    st.subheader("📐 엑셀 업로드")

    if "upload_done" not in st.session_state:
        st.session_state.upload_done = False

    uploaded_file = st.file_uploader("엑셀 파일 업로드 (.xlsx)", type=["xlsx"])

    if uploaded_file and not st.session_state.upload_done:
        try:
            df = pd.read_excel(uploaded_file)

            if not {"품번", "RFID"}.issubset(df.columns):
                st.error("❌ 엑셀 파일에 '품번'과 'RFID' 컬럼이 있어야 합니다.")
                st.stop()

            results = []
            ref = db.reference("products")

            for index, row in df.iterrows():
                pnum = str(row["품번"]).strip().upper()
                rfid_raw = str(row["RFID"]).strip().upper()

                if not pnum or not rfid_raw:
                    results.append(f"❌ 누락된 데이터 (행 {index + 2})")
                    continue

                if rfid_raw == "X":
                    key_suffix = f"NOID_{uuid.uuid4().hex[:6]}"
                    unique_key = f"{pnum}_{key_suffix}"
                    rfid_value = None
                    skip_duplicate_check = True
                else:
                    unique_key = f"{pnum}_{rfid_raw}"
                    rfid_value = rfid_raw
                    skip_duplicate_check = False

                if not skip_duplicate_check:
                    existing = ref.child(unique_key).get()
                    if existing:
                        results.append(f"❌ 중복으로 등록 안됨: {pnum} (RFID: {rfid_raw})")
                        continue

                price = get_price_from_lfmall(pnum)
                if price is None:
                    results.append(f"❌ 가격 정보 실패: {pnum}")
                    continue

                ref.child(unique_key).set({
                    "품번": pnum,
                    "timestamp": int(time.time()),
                    "가격": price,
                    "RFID": rfid_value
                })

                log_activity(st.session_state.user, "엑셀 등록", pnum, rfid_value, price)
                results.append(f"✅ 등록 완료: {pnum} (RFID: {rfid_raw})")

            st.markdown("### 📋 등록 결과")
            for r in results:
                st.write(r)

            # ✅ ✅ ✅ 여기서 업로드 완료 상태 표시!
            st.session_state.upload_done = True
            st.success("✅ 엑셀 업로드가 완료되었습니다.")

        except Exception as e:
            st.error(f"❌ 파일 처리 중 오류 발생: {e}")
