import streamlit as st
import pandas as pd
from character_manager import CharacterManager
from portrait_sound_manager import PortraitSoundManager
from google_sheets_manager import GoogleSheetsManager
from converter_logic import ConverterLogic
from settings_manager import SettingsManager
import pyperclip

# --- 페이지 설정 ---
st.set_page_config(page_title="대사 변환기 v3.6 (Final)", page_icon="🎬", layout="wide")

# --- 초기화 ---
@st.cache_resource
def get_sheets_manager():
    """Google API 클라이언트는 앱 세션 동안 한 번만 생성합니다."""
    return GoogleSheetsManager()

def init_data_managers(_sheets_manager, _settings_url):
    """URL과 API 클라이언트가 모두 준비되었을 때 데이터 관리자들을 초기화합니다."""
    if _sheets_manager and _sheets_manager.is_available() and _settings_url:
        try:
            char_manager = CharacterManager(_sheets_manager.gc, _settings_url)
            settings_manager = SettingsManager(_sheets_manager.gc, _settings_url)
            
            if not char_manager.is_loaded() or not settings_manager.is_loaded():
                st.sidebar.warning("설정 시트의 'character' 또는 'settings' 관련 시트를 찾거나 읽는 데 실패했습니다.")
                return None, None, None, None

            ps_manager = PortraitSoundManager(char_manager, settings_manager.get_expression_map())
            converter = ConverterLogic(char_manager, ps_manager, settings_manager)
            st.sidebar.success("상태: 설정 시트 연결 완료")
            return char_manager, settings_manager, ps_manager, converter
        except Exception as e:
            st.sidebar.error(f"매니저 초기화 오류: {e}")
            return None, None, None, None
    return None, None, None, None


# --- 세션 상태 관리 ---
if 'settings_url' not in st.session_state: 
    st.session_state.settings_url = "https://docs.google.com/spreadsheets/d/1neSBv_r_ZM9-FoHjC73THZyJ1ytawjqg9aem9muBkhs/edit#gid=0"
if 'current_url' not in st.session_state: st.session_state.current_url = ""
if 'sheet_names' not in st.session_state: st.session_state.sheet_names = []
if 'selected_sheet' not in st.session_state: st.session_state.selected_sheet = None
if 'sheet_data' not in st.session_state: st.session_state.sheet_data = None
if 'scene_numbers' not in st.session_state: st.session_state.scene_numbers = []
if 'result_df' not in st.session_state: st.session_state.result_df = None
if 'editing_char_id' not in st.session_state: st.session_state.editing_char_id = None

st.title("🎬 대사 변환기 v3.7 (Final)")

# --- 사이드바 ---
st.sidebar.header("⚙️ 공통 설정")
sheets_manager = get_sheets_manager() # 1. API 클라이언트 먼저 생성

settings_url_input = st.sidebar.text_input(
    "설정 시트 URL", 
    value=st.session_state.settings_url,
    help="character, expressions, directives 시트가 포함된 구글 시트 URL"
)
if settings_url_input != st.session_state.settings_url:
    st.session_state.settings_url = settings_url_input
    st.rerun()

# 2. 클라이언트와 URL을 바탕으로 데이터 매니저 생성
char_manager, settings_manager, ps_manager, converter = init_data_managers(
    sheets_manager, st.session_state.settings_url
)

if st.sidebar.button("⚙️ 설정 및 캐릭터 새로고침"):
    st.toast("최신 설정과 캐릭터 목록을 다시 불러옵니다.")
    st.rerun()
    
# =======================
# ===== 탭 생성 =====
# =======================
st.markdown("---")
main_tab, char_tab, settings_tab = st.tabs(["🔄 변환 작업", "👥 캐릭터 관리", "⚙️ 변환 설정"])


# =======================
# ===== 메인 변환 탭 =====
# =======================
with main_tab:
    if not settings_manager:
        st.error("설정 시트 연결에 실패했습니다. 사이드바의 상태 정보를 확인하세요.")
    else:
        st.subheader("1단계: 변환할 시나리오 시트 연결")
        url_input = st.text_input("시나리오 시트의 URL을 입력하세요", st.session_state.current_url)
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

        if st.session_state.sheet_names:
            st.subheader("2단계: 변환할 시트 선택")
            selected_sheet = st.selectbox("목록에서 시트를 선택하세요.", options=[""] + st.session_state.sheet_names, index=0, key="sheet_selector")
            if selected_sheet and selected_sheet != st.session_state.selected_sheet:
                st.session_state.selected_sheet = selected_sheet
                with st.spinner(f"'{selected_sheet}' 시트 데이터를 불러오는 중..."):
                    success, message, df = sheets_manager.read_sheet_data(st.session_state.current_url, selected_sheet)
                    if success:
                        st.success(message); st.session_state.sheet_data = df
                        if '씬 번호' in df.columns:
                            scenes = df['씬 번호'].replace(r'^\s*$', pd.NA, regex=True).dropna()
                            unique_scenes = pd.to_numeric(scenes, errors='coerce').dropna().astype(int).unique(); unique_scenes.sort()
                            st.session_state.scene_numbers = unique_scenes
                        else:
                            st.warning("'씬 번호' 컬럼을 찾을 수 없습니다."); st.session_state.scene_numbers = []
                        st.session_state.result_df = None
                    else:
                        st.error(message); st.session_state.sheet_data = None; st.session_state.scene_numbers = []
        
        if st.session_state.sheet_data is not None and len(st.session_state.scene_numbers) > 0:
            st.subheader("3단계: 변환할 씬(Scene) 선택")
            selected_scene = st.selectbox("변환할 씬 번호를 선택하세요.", options=st.session_state.scene_numbers, key="scene_selector")
            if selected_scene:
                scene_df = st.session_state.sheet_data[pd.to_numeric(st.session_state.sheet_data['씬 번호'], errors='coerce') == selected_scene].copy()
                with st.expander(f"씬 {selected_scene} 데이터 미리보기 ({len(scene_df)} 행)", expanded=False): st.dataframe(scene_df)
                if st.button("🚀 변환 실행", type="primary", use_container_width=True):
                    with st.spinner(f"씬 {selected_scene} 변환 중..."):
                        conversion_results = converter.convert_scene_data(scene_df)
                        scene_df['상태'] = [res['status'] for res in conversion_results]; scene_df['결과 메시지'] = [res['message'] for res in conversion_results]; scene_df['변환 스크립트'] = [res['result'] for res in conversion_results]
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
        successful_scripts = st.session_state.result_df[st.session_state.result_df['상태'].isin(['success', 'warning'])]['변환 스크립트'].tolist()
        if successful_scripts:
            final_script_text = "\n\n".join(successful_scripts)
            # text_area와 button 대신, 복사 버튼이 내장된 st.code 사용
            st.code(final_script_text, language="text")
        else:
            st.warning("복사할 수 있는 성공적인 스크립트가 없습니다.")

# =======================
# ===== 캐릭터 관리 탭 =====
# =======================
with char_tab:
    st.subheader("👥 캐릭터 관리")
    
    # [수정] char_manager가 생성되었는지 먼저 확인합니다.
    if not char_manager:
        st.error("설정 시트 연결에 실패하여 캐릭터 정보를 불러올 수 없습니다.")
    
    # [수정] 캐릭터 데이터가 비어있을 때의 처리를 추가합니다.
    elif char_manager.is_empty():
        st.info("현재 설정 시트에 등록된 캐릭터가 없습니다. 오른쪽에서 새 캐릭터를 추가해주세요.")
        
        # 캐릭터가 없을 때도 추가 폼은 보여주기
        with st.form("add_character_form_empty", clear_on_submit=True):
            name = st.text_input("Name (영문)")
            kr_name = st.text_input("KR (한글)")
            string_id = st.text_input("String_ID (고유값)")
            portrait_path = st.text_input("포트레이트 기본 경로 (선택사항)", help="예: avin/avin_")
            
            if st.form_submit_button("추가하기", type="primary"):
                if name and kr_name and string_id:
                    success, message = char_manager.add_character(name, kr_name, string_id, portrait_path)
                    if success: 
                        st.success(message)
                        st.rerun()
                    else: 
                        st.error(message)
                else:
                    st.warning("Name, KR, String_ID는 필수 입력 항목입니다.")

    # [수정] 모든 UI 요소를 이 else 블록 안으로 이동시켰습니다.
    else:
        col_list, col_actions = st.columns([3, 2])
        
        with col_list:
            st.write("**등록된 캐릭터 목록**")
            characters_df = char_manager.get_characters_dataframe()
            search_term = st.text_input("🔍 캐릭터 검색 (이름 또는 KR)", placeholder="이름으로 검색...", key="char_search")
            
            if search_term:
                search_term_lower = search_term.lower()
                # DataFrame에 'name'과 'kr' 컬럼이 있는지 확인 후 검색
                if 'name' in characters_df.columns and 'kr' in characters_df.columns:
                    filtered_df = characters_df[
                        characters_df['name'].str.lower().str.contains(search_term_lower) | 
                        characters_df['kr'].str.lower().str.contains(search_term_lower)
                    ]
                else:
                    filtered_df = characters_df
            else:
                filtered_df = characters_df
            
            if not filtered_df.empty:
                for _, row in filtered_df.iterrows():
                    # 컬럼 이름이 소문자로 통일되었으므로, 소문자로 접근
                    char_id = row['string_id']
                    char_name_en = row['name']
                    char_name_kr = row['kr']
                    
                    with st.container():
                        c1, c2, c3 = st.columns([4, 1, 1])
                        c1.markdown(f"**{char_name_en}** ({char_name_kr}) - `ID: {char_id}`")
                        
                        if c2.button("✏️", key=f"edit_{char_id}", help="수정"):
                            st.session_state.editing_char_id = char_id
                            st.rerun()
                            
                        if c3.button("🗑️", key=f"delete_{char_id}", help="삭제"):
                            success, msg = char_manager.delete_character(char_id)
                            if success:
                                st.success(msg)
                                st.session_state.editing_char_id = None
                                st.rerun()
                            else:
                                st.error(msg)

                        if st.session_state.editing_char_id == char_id:
                            with st.form(key=f"edit_form_{char_id}"):
                                st.markdown(f"**✏️ '{char_name_en}' 정보 수정**")
                                new_name = st.text_input("Name", value=char_name_en)
                                new_kr = st.text_input("KR", value=char_name_kr)
                                # .get()을 사용하여 'portrait_path'가 없는 구 버전 데이터 호환
                                portrait_path = st.text_input("포트레이트 기본 경로", value=row.get('portrait_path', ''), 
                                                              help="예: avin/avin_. 비워두면 자동 생성, \"\"를 입력하면 빈 포트레이트로 고정됩니다.")
                                
                                edit_cols = st.columns(2)
                                if edit_cols[0].form_submit_button("✅ 저장"):
                                    # update 함수는 아직 미구현 상태이므로 주석 처리 또는 구현 필요
                                    st.warning("캐릭터 정보 수정 기능은 아직 구현되지 않았습니다.")
                                    # success, msg = char_manager.update_character(...)
                                    # if success: ...
                                    
                                if edit_cols[1].form_submit_button("취소"):
                                    st.session_state.editing_char_id = None
                                    st.rerun()
            else:
                st.info("검색된 캐릭터가 없습니다.")

        with col_actions:
            with st.expander("➕ 새 캐릭터 추가", expanded=True):
                with st.form("add_character_form", clear_on_submit=True):
                    name = st.text_input("Name (영문)")
                    kr_name = st.text_input("KR (한글)")
                    string_id = st.text_input("String_ID (고유값)")
                    portrait_path = st.text_input("포트레이트 기본 경로 (선택사항)", help="예: avin/avin_")
                    
                    if st.form_submit_button("추가하기", type="primary"):
                        if name and kr_name and string_id:
                            success, message = char_manager.add_character(name, kr_name, string_id, portrait_path)
                            if success: 
                                st.success(message)
                                st.rerun()
                            else: 
                                st.error(message)
                        else:
                            st.warning("Name, KR, String_ID는 필수 입력 항목입니다.")

# =======================
# ===== 변환 설정 탭 =====
# =======================
with settings_tab:
    st.subheader("⚙️ 변환 설정")
    if not settings_manager:
        st.warning("먼저 왼쪽 사이드바에서 설정을 불러와주세요.")
    else:
        st.info("이곳에서 변환 규칙을 직접 추가하거나 수정할 수 있습니다. 변경 사항은 구글 시트에 즉시 저장됩니다.")
        
        # --- 1. 감정 표현 규칙 관리 ---
        st.markdown("---")
        st.markdown("#### 🎭 감정 표현 규칙 관리")
        exp_map = settings_manager.get_expression_map()
        exp_df = pd.DataFrame(list(exp_map.items()), columns=['한글 표현', '영문 변환 값'])
        edited_exp_df = st.data_editor(exp_df, num_rows="dynamic", key="exp_editor", use_container_width=True)
        if st.button("🎭 감정 표현 규칙 저장", use_container_width=True):
            if not edited_exp_df.equals(exp_df):
                new_exp_map = dict(zip(edited_exp_df['한글 표현'], edited_exp_df['영문 변환 값']))
                success, msg = settings_manager.save_expression_map(new_exp_map)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.toast("ℹ️ 변경된 내용이 없습니다.")
                
        # --- 2. 지시문 규칙 관리 ---
        st.markdown("---")
        st.markdown("#### 📜 지시문 규칙 관리")
        # [함수명: 지시문 규칙 관리]: 변경 없음
        directive_rules = settings_manager.get_directive_rules()
        st.write("**현재 등록된 사용자 정의 규칙:**")
        default_rules = ["카메라", "조명"]
        
        for name, rule in directive_rules.items():
            with st.container():
                st.markdown(f"**{name}** (`{rule['type']}`)")
                cols = st.columns([1, 0.1])
                cols[0].text_area("템플릿 내용", value=rule['template'], key=f"tpl_{name}", disabled=True, height=100)
                is_default = name in default_rules
                if cols[1].button("🗑️", key=f"del_dir_{name}", help=f"'{name}' 규칙 삭제", disabled=is_default):
                    success, msg = settings_manager.delete_directive_rule(name)
                    if success: st.success(msg); st.rerun()
                    else: st.error(msg)
                st.markdown("---")
        with st.expander("➕ 새 지시문 규칙 추가"):
            new_dir_type = st.selectbox("규칙 타입", ["simple", "template"], help="simple: 고정 텍스트, template: 시트 내용 참조", key="dir_type_selector")
            
            with st.form("add_dir_form", clear_on_submit=True):
                new_dir_name = st.text_input("지시문 이름", help="예: 장면, 효과음")
                
                if new_dir_type == "simple":
                    new_dir_template = st.text_input("변환될 텍스트", help="예: 장면_묘사()")
                else: # template
                    new_dir_template = st.text_area("변환 템플릿", height=150, help='예: 효과음_재생("0.1", "{{사운드 주소}}{{사운드 파일}}")\n- 줄바꿈은 \\n을 사용하세요.\n- {컬럼명}을 입력하려면 {{컬럼명}}처럼 중괄호를 두 번 사용해야 합니다.')
                
                if st.form_submit_button("규칙 추가"):
                    success, msg = settings_manager.add_directive_rule(new_dir_name, new_dir_type, new_dir_template)
                    if success: st.success(msg); st.rerun()
                    else: st.error(msg)
            
            # [수정] 템플릿 변수 복사 UI를 st.code를 사용하는 방식으로 변경
            if new_dir_type == 'template':
                if st.session_state.sheet_data is not None:
                    st.info("💡 **사용 가능한 템플릿 변수 (클릭하여 복사):**")
                    valid_columns = [col for col in st.session_state.sheet_data.columns if col and not col.startswith('unnamed:')]
                    
                    # 컬럼을 4열로 나누어 표시
                    cols = st.columns(4)
                    for i, col_name in enumerate(valid_columns):
                        with cols[i % 4]:
                            # 각 컬럼명을 st.code로 감싸면 자동으로 복사 버튼이 생김
                            st.code(f"{{{{{col_name}}}}}", language="text")
                else:
                    st.warning("템플릿에 사용할 컬럼 목록을 보려면, 먼저 '변환 작업' 탭에서 데이터를 불러와주세요.")