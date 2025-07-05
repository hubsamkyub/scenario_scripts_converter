import streamlit as st
import pandas as pd
import io
from converter_logic import convert_dialogue_data, validate_data, format_conversion_summary, validate_conversion_result
from character_manager import CharacterManager
from portrait_sound_manager import PortraitSoundManager
from google_sheets_manager import GoogleSheetsManager
from sheet_config_manager import SheetConfigManager
import pyperclip

# --- 페이지 설정 ---
st.set_page_config(
    page_title="대사 변환기",
    page_icon="💬",
    layout="wide"
)

# --- 세션 상태 초기화 ---
# 이니셜라이저는 앱 실행 시 한 번만 호출되도록 관리
@st.cache_resource
def get_managers():
    return CharacterManager(), GoogleSheetsManager(), SheetConfigManager()

char_manager, sheets_manager, config_manager = get_managers()

# UI 상호작용과 관련된 세션 상태
if 'raw_sheet_data' not in st.session_state:
    st.session_state.raw_sheet_data = None  # 파싱된 데이터
if 'full_raw_data' not in st.session_state:
    st.session_state.full_raw_data = None # 전체 원본 데이터 (미리보기용)
if 'edited_data' not in st.session_state:
    st.session_state.edited_data = None
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
if 'conversion_results' not in st.session_state:
    st.session_state.conversion_results = None
if 'editing_char_id' not in st.session_state:
    st.session_state.editing_char_id = None


def reset_conversion_state():
    """변환 관련 세션 상태 초기화"""
    st.session_state.raw_sheet_data = None
    st.session_state.full_raw_data = None
    st.session_state.edited_data = None
    st.session_state.data_loaded = False
    st.session_state.conversion_results = None


st.title("💬 대사 변환기")
st.markdown("---")

# --- 탭 생성 ---
tab1, tab2 = st.tabs(["🔄 대사 변환", "👥 캐릭터 관리"])

# =======================
# ===== 대사 변환 탭 =====
# =======================
with tab1:
    with st.expander("📋 사용법", expanded=False):
        st.markdown("""
        **1. 데이터 불러오기**
        - **🔗 구글 시트**: URL을 입력하고 '전체 시트 불러오기'를 클릭하세요.
        - **📝 텍스트 입력**: 시트 데이터를 복사하여 붙여넣고 '텍스트 데이터 로드'를 클릭하세요.

        **2. (구글 시트 전용) 데이터 범위 설정**
        - 전체 시트 미리보기를 확인하고, **헤더/시작/종료 행 번호**를 정확히 입력하세요.
        - **[설정 적용 및 데이터 파싱]** 버튼을 눌러 원하는 데이터만 추출합니다.

        **3. 데이터 편집 및 변환**
        - 추출된 데이터가 표 형태로 나타나면, 필요시 직접 수정합니다.
        - '변환하기' 버튼을 클릭하면 아래에 결과가 표시됩니다.

        **4. 결과 확인 및 복사**
        - 원본 데이터와 변환 결과가 나란히 표시된 표에서 이상 여부를 확인하세요.
        - **성공한 대사만 클립보드에 복사**할 수 있습니다.
        """)

    input_method_tabs = st.tabs(["🔗 구글 시트", "📝 텍스트 입력"])

    # --- 구글 시트 입력 ---
    with input_method_tabs[0]:
        st.subheader("📥 구글 시트에서 불러오기")
        last_access = config_manager.get_last_access()
        
        with st.form("google_sheet_form"):
            sheet_url = st.text_input("구글 시트 URL", value=last_access.get("url", ""), placeholder="https://docs.google.com/spreadsheets/d/...")
            sheet_name = st.text_input("시트 이름 (선택사항)", value=last_access.get("sheet_name", ""), placeholder="Sheet1, 3-2, #String 등")
            
            submitted = st.form_submit_button("📥 1. 전체 시트 불러오기 (미리보기용)", type="secondary", use_container_width=True)

            if submitted and sheet_url.strip():
                with st.spinner("구글 시트의 전체 데이터를 불러오는 중..."):
                    # 전체 데이터를 불러와서 full_raw_data에 저장
                    success, message, _, all_data = sheets_manager.read_sheet_data(sheet_url, sheet_name.strip() or None)
                    if success and all_data is not None:
                        st.success(f"✅ 전체 시트 로드 완료! 아래에서 파싱 범위를 설정하세요.")
                        st.session_state.full_raw_data = all_data
                        st.session_state.data_loaded = False # 아직 파싱 전
                        st.session_state.raw_sheet_data = None
                        config_manager.save_last_access(sheet_url, sheet_name.strip())
                    else:
                        st.error(f"❌ {message}")
                        reset_conversion_state()
            elif submitted:
                st.warning("⚠️ 구글 시트 URL을 입력해주세요.")

        # --- 데이터 범위 설정 (전체 시트가 로드된 경우에만 표시) ---
        if st.session_state.full_raw_data is not None:
            st.markdown("---")
            st.subheader("2. 시트 미리보기 및 범위 설정")
            with st.expander("전체 시트 미리보기 (상위 20행)", expanded=True):
                preview_df = st.session_state.full_raw_data.head(20)
                preview_df.index = [f"행 {i+1}" for i in preview_df.index]
                st.dataframe(preview_df, use_container_width=True)
                st.caption("⬆️ 위 표에서 컬럼 제목(헤더)이 있는 행, 데이터 시작/종료 행 번호를 확인하세요.")

            with st.form("parsing_options_form"):
                max_rows = len(st.session_state.full_raw_data)
                cols = st.columns(3)
                header_row = cols[0].number_input("헤더 행 번호", min_value=1, max_value=max_rows, value=1)
                start_row = cols[1].number_input("데이터 시작 행 번호", min_value=1, max_value=max_rows, value=2)
                end_row = cols[2].number_input("데이터 종료 행 번호", min_value=start_row, max_value=max_rows, value=max_rows)
                
                parse_submitted = st.form_submit_button("⚙️ 3. 설정 적용 및 데이터 파싱", type="primary", use_container_width=True)

                if parse_submitted:
                    with st.spinner(f"지정한 범위(헤더:{header_row}, 데이터:{start_row}-{end_row})로 파싱하는 중..."):
                        # header_row는 1부터 시작, read_sheet_data는 0부터 인덱싱하므로 -1
                        # start/end_row는 데이터 기준이므로 그대로 전달
                        success, message, df, _ = sheets_manager.read_sheet_data(
                            sheet_url,
                            sheet_name.strip() or None,
                            header_row=header_row - 1,
                            start_row=start_row - header_row, # read_sheet_data는 헤더 제외 후 데이터 행 번호를 받음
                            end_row=end_row - header_row
                        )

                        if success and df is not None:
                            # 데이터 유효성 검사 추가
                            df_str = df.to_csv(sep='\t', index=False)
                            is_valid, valid_msg, validated_df = validate_data(df_str, True, char_manager)
                            if is_valid:
                                st.success(f"✅ 파싱 성공! {message}")
                                st.info(valid_msg) # 매핑된 컬럼 정보 표시
                                st.session_state.raw_sheet_data = validated_df
                                st.session_state.edited_data = validated_df.copy()
                                st.session_state.data_loaded = True
                                st.session_state.conversion_results = None
                            else:
                                st.error(f"❌ 파싱 후 데이터 검증 실패: {valid_msg}")
                                st.session_state.data_loaded = False
                        else:
                            st.error(f"❌ 파싱 실패: {message}")
                            st.session_state.data_loaded = False

    # --- 텍스트 입력 ---
    with input_method_tabs[1]:
        st.subheader("📥 텍스트로 붙여넣기")
        input_data = st.text_area(
            "구글 시트 데이터를 여기에 붙여넣으세요",
            height=200,
            placeholder="캐릭터\t대사\t사운드 파일명\n샤오\t사부! 큰일 났어요!\t15031309_Shao_01",
            key="text_input_area"
        )
        if st.button("📝 텍스트 데이터 로드", use_container_width=True, key="load_from_text_btn"):
            if input_data.strip():
                is_valid, message, df = validate_data(input_data, True, char_manager)
                if is_valid:
                    st.success("✅ 텍스트 데이터 로드 완료!")
                    st.info(message)
                    st.session_state.raw_sheet_data = df
                    st.session_state.edited_data = df.copy()
                    st.session_state.data_loaded = True
                    st.session_state.conversion_results = None
                else:
                    st.error(f"❌ 데이터 오류: {message}")
                    reset_conversion_state()
            else:
                st.warning("⚠️ 입력 데이터를 먼저 붙여넣어주세요.")


    st.markdown("---")


    # --- 데이터 편집 및 변환 (데이터 로드 완료 시 표시) ---
    if st.session_state.data_loaded and st.session_state.raw_sheet_data is not None:
        st.subheader("🖥️ 4. 데이터 편집 및 변환")
        st.info("💡 아래 표에서 직접 데이터를 수정할 수 있습니다. 수정 후 '변환하기' 버튼을 누르세요.")

        # 데이터 에디터
        st.session_state.edited_data = st.data_editor(
            st.session_state.raw_sheet_data,
            num_rows="dynamic",
            use_container_width=True,
            key="data_editor"
        )

        if st.button("🚀 변환하기", type="primary", use_container_width=True, key="convert_btn"):
            if st.session_state.edited_data is not None and not st.session_state.edited_data.empty:
                
                df_to_convert = st.session_state.edited_data.copy()
                progress_bar = st.progress(0, "변환을 시작합니다...")
                
                results = convert_dialogue_data(
                    df_to_convert, 
                    char_manager,
                    # ❗️❗️❗️ FIX: progress 값이 1.0을 넘지 않도록 min() 함수로 감싸기 ❗️❗️❗️
                    lambda p: progress_bar.progress(min(p, 1.0), f"변환 중... {int(min(p, 1.0)*100)}%")
                )
                
                progress_bar.empty()
                
                result_df = df_to_convert.copy()
                result_df['변환 결과'] = [r['message'] for r in results]
                result_df['성공 여부'] = ['✅' if r['status'] == 'success' else '❌' for r in results]
                result_df['경고'] = [r['warning'] for r in results]
                
                st.session_state.conversion_results = result_df
                st.success("✅ 변환 완료! 아래에서 결과를 확인하세요.")
            else:
                st.warning("⚠️ 변환할 데이터가 없습니다.")


    # --- 변환 결과 표시 ---
    if st.session_state.conversion_results is not None:
        st.markdown("---")
        st.subheader("📄 5. 변환 결과")

        results_df = st.session_state.conversion_results
        
        # 성공/실패 통계
        stats = validate_conversion_result(results_df['변환 결과'].tolist())
        st.info(format_conversion_summary(stats))

        # 1. 원본 + 변환 결과 비교 테이블
        with st.expander("📊 전체 변환 결과 상세 보기", expanded=True):
            st.dataframe(
                results_df,
                use_container_width=True,
                column_config={
                    "성공 여부": st.column_config.TextColumn("Status", width="small"),
                    "경고": st.column_config.TextColumn("Warning", width="medium"),
                }
            )

        # 2. 성공한 결과 (복사 기능 포함)
        st.write("#### ✅ 성공한 대사")
        successful_results = results_df[results_df['성공 여부'] == '✅']['변환 결과'].tolist()
        
        if successful_results:
            success_text = "\n".join(successful_results)
            st.code(success_text, language="text")
            if st.button("📋 성공한 대사만 클립보드에 복사", key="copy_success"):
                pyperclip.copy(success_text)
                st.success("✅ 클립보드에 복사되었습니다!")
        else:
            st.info("성공적으로 변환된 대사가 없습니다.")

        # 3. 오류 및 경고 목록
        errors = results_df[results_df['성공 여부'] == '❌']
        warnings = results_df[(results_df['경고'] != '') & (results_df['경고'].notna())]
        
        if not errors.empty or not warnings.empty:
            with st.expander("⚠️ 오류 및 경고 목록", expanded=True):
                if not errors.empty:
                    st.error("**❌ 오류 목록**")
                    for idx, row in errors.iterrows():
                        st.text(f" - 원본 행 {row.name + 1}: {row['변환 결과']}")
                
                if not warnings.empty:
                    st.warning("**🟡 경고 목록**")
                    for idx, row in warnings.iterrows():
                        original_char = row.get('캐릭터', '알 수 없음')
                        st.text(f" - 원본 행 {row.name + 1} (캐릭터: {original_char}): {row['경고']}")

# =======================
# ===== 캐릭터 관리 탭 =====
# =======================
with tab2:
    st.subheader("👥 캐릭터 관리")

    col_list, col_actions = st.columns([3, 2])

    with col_list:
        st.write("**등록된 캐릭터 목록**")
        
        characters_df = char_manager.get_characters_dataframe()
        search_term = st.text_input("🔍 캐릭터 검색 (이름 또는 KR)", placeholder="이름으로 검색...")
        
        if search_term:
            search_term = search_term.lower()
            filtered_df = characters_df[
                characters_df['Name'].str.lower().str.contains(search_term) |
                characters_df['KR'].str.lower().str.contains(search_term)
            ]
        else:
            filtered_df = characters_df

        if not filtered_df.empty:
            for _, row in filtered_df.iterrows():
                char_id = row['String_ID']
                with st.container():
                    c1, c2, c3 = st.columns([4, 1, 1])
                    c1.markdown(f"**{row['Name']}** ({row['KR']}) - `ID: {char_id}`")
                    
                    if c2.button("✏️", key=f"edit_{char_id}", help="수정"):
                        st.session_state.editing_char_id = char_id
                        st.rerun()

                    if c3.button("🗑️", key=f"delete_{char_id}", help="삭제"):
                        if char_manager.delete_character(char_id):
                            st.success(f"✅ 캐릭터 '{row['Name']}' 삭제 완료!")
                            st.session_state.editing_char_id = None
                            st.rerun()
                        else:
                            st.error("❌ 삭제 중 오류 발생")

                    if st.session_state.editing_char_id == char_id:
                        with st.form(key=f"edit_form_{char_id}"):
                            st.markdown(f"**✏️ '{row['Name']}' 정보 수정**")
                            new_name = st.text_input("Name", value=row['Name'])
                            new_kr = st.text_input("KR", value=row['KR'])
                            
                            edit_cols = st.columns(2)
                            if edit_cols[0].form_submit_button("✅ 저장"):
                                success, msg, _ = char_manager.update_character(char_id, name=new_name, kr_name=new_kr)
                                if success:
                                    st.success(f"✅ {msg}")
                                    st.session_state.editing_char_id = None
                                    st.rerun()
                                else:
                                    st.error(f"❌ {msg}")
                            
                            if edit_cols[1].form_submit_button("취소"):
                                st.session_state.editing_char_id = None
                                st.rerun()
        else:
            st.info("표시할 캐릭터가 없습니다.")

    with col_actions:
        with st.expander("➕ 새 캐릭터 추가", expanded=True):
            with st.form("add_character_form", clear_on_submit=True):
                new_name = st.text_input("Name (영문)")
                new_kr = st.text_input("KR (한글)")
                custom_string_id = st.text_input("Custom String_ID (선택사항)")

                if st.form_submit_button("추가하기", type="primary", use_container_width=True):
                    if new_name and new_kr:
                        success, message, _ = char_manager.add_character(new_name, new_kr, custom_string_id)
                        if success:
                            st.success(f"✅ {message}")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                    else:
                        st.warning("⚠️ Name과 KR을 모두 입력해주세요.")

        with st.expander("📥 시트에서 가져오기"):
            sheet_data = st.text_area(
                "시트 데이터 붙여넣기", height=150,
                placeholder="String_ID\tKR\tName\ndouglas\t더글라스\tDouglas"
            )
            if st.button("가져오기", use_container_width=True, key="import_from_sheet"):
                if sheet_data.strip():
                    success, message, _ = char_manager.import_from_sheet_data(sheet_data)
                    if success:
                        st.success(f"✅ {message}")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
                else:
                    st.warning("⚠️ 시트 데이터를 먼저 붙여넣어주세요.")
        
        with st.expander("📤 캐릭터 데이터 내보내기"):
            if not characters_df.empty:
                export_data = char_manager.export_to_sheet_format()
                st.text_area("내보내기 데이터", value=export_data, height=150, key="export_data_area")
                if st.button("📋 클립보드에 복사", key="copy_export_data", use_container_width=True):
                    pyperclip.copy(export_data)
                    st.success("✅ 내보내기 데이터가 복사되었습니다!")
            else:
                st.info("내보낼 데이터가 없습니다.")

st.markdown("---")
st.markdown("<div style='text-align: center; color: #888;'><small>Scenario Scripts Converter</small></div>", unsafe_allow_html=True)