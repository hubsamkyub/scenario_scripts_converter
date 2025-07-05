import streamlit as st
import pandas as pd
from character_manager import CharacterManager
from portrait_sound_manager import PortraitSoundManager
from google_sheets_manager import GoogleSheetsManager
from converter_logic import ConverterLogic
import pyperclip

# --- 페이지 설정 ---
st.set_page_config(
    page_title="대사 변환기 v2",
    page_icon="🎬",
    layout="wide"
)

# --- 초기화 ---
@st.cache_resource
def init_managers():
    char_manager = CharacterManager()
    ps_manager = PortraitSoundManager(char_manager)
    sheets_manager = GoogleSheetsManager()
    converter_logic = ConverterLogic(char_manager, ps_manager)
    return char_manager, ps_manager, sheets_manager, converter_logic

char_manager, ps_manager, sheets_manager, converter = init_managers()

# --- 세션 상태 관리 ---
if 'current_url' not in st.session_state:
    st.session_state.current_url = ""
if 'sheet_names' not in st.session_state:
    st.session_state.sheet_names = []
if 'selected_sheet' not in st.session_state:
    st.session_state.selected_sheet = None
if 'sheet_data' not in st.session_state:
    st.session_state.sheet_data = None
if 'scene_numbers' not in st.session_state:
    st.session_state.scene_numbers = []
if 'result_df' not in st.session_state:
    st.session_state.result_df = None
if 'editing_char_id' not in st.session_state:
    st.session_state.editing_char_id = None

st.title("🎬 대사 변환기 v2")
st.markdown("---")

# =======================
# ===== 탭 생성 =====
# =======================
main_tab, char_tab, settings_tab = st.tabs(["🔄 변환 작업", "👥 캐릭터 관리", "⚙️ 변환 설정"])

# =======================
# ===== 메인 변환 탭 =====
# =======================
with main_tab:
    # [수정] 오류 필터링 및 캐릭터 일괄 추가 기능 추가
    
    # --- 1단계: 구글 시트 URL 입력 ---
    st.subheader("1단계: 구글 시트 연결")
    url_input = st.text_input("구글 시트 URL을 입력하세요", st.session_state.current_url)

    if st.button("시트 목록 불러오기", type="primary"):
        if url_input:
            with st.spinner("시트 목록을 가져오는 중..."):
                st.session_state.current_url = url_input
                st.session_state.sheet_names = []
                st.session_state.selected_sheet = None
                st.session_state.sheet_data = None
                st.session_state.result_df = None
                
                success, message, names = sheets_manager.get_sheet_names(url_input)
                if success:
                    st.success(message)
                    st.session_state.sheet_names = names
                else:
                    st.error(message)
        else:
            st.warning("URL을 입력해주세요.")

    # --- 2단계: 시트 선택 ---
    if st.session_state.sheet_names:
        st.subheader("2단계: 변환할 시트 선택")
        selected_sheet = st.selectbox(
            "목록에서 시트를 선택하세요.", options=[""] + st.session_state.sheet_names, index=0, key="sheet_selector"
        )
        
        if selected_sheet and selected_sheet != st.session_state.selected_sheet:
            st.session_state.selected_sheet = selected_sheet
            with st.spinner(f"'{selected_sheet}' 시트 데이터를 불러오는 중..."):
                success, message, df = sheets_manager.read_sheet_data(st.session_state.current_url, selected_sheet)
                if success:
                    st.success(message)
                    st.session_state.sheet_data = df
                    if '씬 번호' in df.columns:
                        scenes = df['씬 번호'].replace(r'^\s*$', pd.NA, regex=True).dropna()
                        unique_scenes = pd.to_numeric(scenes, errors='coerce').dropna().astype(int).unique()
                        unique_scenes.sort()
                        st.session_state.scene_numbers = unique_scenes
                    else:
                        st.warning("'씬 번호' 컬럼을 찾을 수 없습니다.")
                        st.session_state.scene_numbers = []
                    st.session_state.result_df = None
                else:
                    st.error(message)
                    st.session_state.sheet_data = None
                    st.session_state.scene_numbers = []

    # --- 3단계: 씬 선택 및 변환 ---
    if st.session_state.sheet_data is not None and len(st.session_state.scene_numbers) > 0:
        st.subheader("3단계: 변환할 씬(Scene) 선택")
        selected_scene = st.selectbox("변환할 씬 번호를 선택하세요.", options=st.session_state.scene_numbers, key="scene_selector")
        
        if selected_scene:
            scene_df = st.session_state.sheet_data[
                pd.to_numeric(st.session_state.sheet_data['씬 번호'], errors='coerce') == selected_scene
            ].copy()

            with st.expander(f"씬 {selected_scene} 데이터 미리보기 ({len(scene_df)} 행)", expanded=False):
                st.dataframe(scene_df)

            if st.button("🚀 변환 실행", type="primary", use_container_width=True):
                with st.spinner(f"씬 {selected_scene} 변환 중..."):
                    conversion_results = converter.convert_scene_data(scene_df)
                    scene_df['상태'] = [res['status'] for res in conversion_results]
                    scene_df['결과 메시지'] = [res['message'] for res in conversion_results]
                    scene_df['변환 스크립트'] = [res['result'] for res in conversion_results]
                    st.session_state.result_df = scene_df

    # --- 4단계: 결과 확인 ---
    if st.session_state.result_df is not None:
        st.markdown("---")
        st.subheader("✅ 변환 결과 리포트")
        result_df = st.session_state.result_df
        status_counts = result_df['상태'].value_counts()
        success_count = status_counts.get('success', 0)
        warning_count = status_counts.get('warning', 0)
        error_count = status_counts.get('error', 0)
        st.info(f"총 {len(result_df)}개 행 변환 완료: ✅ 성공: {success_count}개 | ⚠️ 경고: {warning_count}개 | ❌ 오류: {error_count}개")

        # [신규] 오류/경고 필터링 UI
        filter_errors = st.checkbox("오류/경고가 있는 행만 보기")
        
        display_df = result_df.copy()
        if filter_errors:
            display_df = display_df[display_df['상태'].isin(['error', 'warning'])]

        # KeyError 방지를 위한 컬럼 추가 로직
        display_columns = ['원본 행 번호', '지시문', '캐릭터', '대사', 'string_id', '상태', '결과 메시지', '변환 스크립트']
        for col in display_columns:
            if col not in display_df.columns:
                display_df[col] = ''
        
        status_map = {'success': '✅', 'warning': '⚠️', 'error': '❌'}
        display_df_final = display_df[display_columns].copy()
        display_df_final['상태'] = display_df_final['상태'].map(status_map)
        st.dataframe(display_df_final, use_container_width=True)

        # [신규] 등록되지 않은 캐릭터 일괄 추가 기능
        unregistered_chars = result_df[result_df['결과 메시지'].str.startswith("미등록 캐릭터:", na=False)]
        if not unregistered_chars.empty:
            # 중복 제거된 캐릭터 이름 목록 추출
            char_names_to_add = unregistered_chars['캐릭터'].unique()
            
            with st.expander("⚠️ 등록되지 않은 캐릭터 일괄 추가", expanded=True):
                st.warning(f"총 {len(char_names_to_add)}명의 캐릭터가 등록되어 있지 않습니다. 아래에서 정보를 입력하고 한 번에 추가하세요.")
                
                with st.form("batch_add_char_form"):
                    new_char_data = []
                    for char_kr in char_names_to_add:
                        st.markdown(f"--- \n**{char_kr}**")
                        cols = st.columns(2)
                        name_en = cols[0].text_input("Name (영문)", key=f"en_{char_kr}")
                        string_id = cols[1].text_input("String_ID", value=name_en.lower(), key=f"id_{char_kr}")
                        new_char_data.append({"kr": char_kr, "name": name_en, "string_id": string_id})
                    
                    if st.form_submit_button("✨ 일괄 등록 실행", type="primary"):
                        success_count, error_messages = char_manager.add_characters_batch(new_char_data)
                        if success_count > 0:
                            st.success(f"{success_count}명의 캐릭터를 성공적으로 추가했습니다!")
                        if error_messages:
                            st.error("일부 캐릭터 추가에 실패했습니다:")
                            for msg in error_messages:
                                st.error(f"- {msg}")
                        st.info("캐릭터 추가 후, [변환 실행] 버튼을 다시 눌러 결과를 갱신하세요.")
                        st.rerun()

        st.write("#### ✨ 성공 및 경고 스크립트 모음 (복사 전용)")
        successful_scripts = result_df[result_df['상태'].isin(['success', 'warning'])]['변환 스크립트'].tolist()
        
        if successful_scripts:
            final_script_text = "\n\n".join(successful_scripts)
            st.text_area("결과 스크립트", value=final_script_text, height=400)
            if st.button("📋 스크립트 복사"):
                pyperclip.copy(final_script_text)
                st.success("결과 스크립트가 클립보드에 복사되었습니다!")
        else:
            st.warning("복사할 수 있는 성공적인 스크립트가 없습니다.")



# =======================
# ===== 캐릭터 관리 탭 =====
# =======================
with char_tab:
    # [함수명: char_tab]: 변경 없음
    st.subheader("👥 캐릭터 관리")
    col_list, col_actions = st.columns([3, 2])
    with col_list:
        st.write("**등록된 캐릭터 목록**")
        characters_df = char_manager.get_characters_dataframe()
        search_term = st.text_input("🔍 캐릭터 검색 (이름 또는 KR)", placeholder="이름으로 검색...", key="char_search")
        
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
                        if success: st.success(f"✅ {message}"); st.rerun()
                        else: st.error(f"❌ {message}")
                    else:
                        st.warning("⚠️ Name과 KR을 모두 입력해주세요.")
        with st.expander("📥 시트에서 가져오기"):
            sheet_data = st.text_area("시트 데이터 붙여넣기", height=150, placeholder="String_ID\tKR\tConverter_Name\tName\ndouglas\t더글라스\t[@douglas]\tDouglas")
            if st.button("가져오기", use_container_width=True, key="import_from_sheet"):
                if sheet_data.strip():
                    success, message, _ = char_manager.import_from_sheet_data(sheet_data)
                    if success: st.success(f"✅ {message}"); st.rerun()
                    else: st.error(f"❌ {message}")
                else: st.warning("⚠️ 시트 데이터를 먼저 붙여넣어주세요.")
        with st.expander("📤 캐릭터 데이터 내보내기"):
            if not characters_df.empty:
                export_data = char_manager.export_to_sheet_format()
                st.text_area("내보내기 데이터", value=export_data, height=150, key="export_data_area")
                if st.button("📋 클립보드에 복사", key="copy_export_data", use_container_width=True):
                    pyperclip.copy(export_data); st.success("✅ 내보내기 데이터가 복사되었습니다!")
            else:
                st.info("내보낼 데이터가 없습니다.")

# =======================
# ===== 변환 설정 탭 =====
# =======================
with settings_tab:
    st.subheader("⚙️ 변환 설정")
    st.info("향후 이곳에서 '지시문'이나 '표정' 변환 규칙을 사용자가 직접 관리할 수 있도록 업데이트할 예정입니다.")