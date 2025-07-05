import streamlit as st
import pandas as pd
import io
from converter_logic import convert_dialogue_data, validate_data
from character_manager import CharacterManager
from portrait_sound_manager import PortraitSoundManager
from google_sheets_manager import GoogleSheetsManager
from sheet_config_manager import SheetConfigManager
import pyperclip  # 클립보드 복사용 (pip install pyperclip 필요)

# 페이지 설정
st.set_page_config(
    page_title="대사 변환기",
    page_icon="💬",
    layout="wide"
)

# 캐릭터 매니저, 구글 시트 매니저, 설정 매니저 초기화
@st.cache_resource
def get_managers():
    char_manager = CharacterManager()
    sheets_manager = GoogleSheetsManager()
    config_manager = SheetConfigManager()
    return char_manager, sheets_manager, config_manager

char_manager, sheets_manager, config_manager = get_managers()

st.title("💬 대사 변환기")
st.markdown("---")

# 탭 생성
tab1, tab2 = st.tabs(["🔄 대사 변환", "👥 캐릭터 관리"])

# ===== 대사 변환 탭 =====
with tab1:
    # 사용법 간단 안내
    with st.expander("📋 사용법", expanded=False):
        if sheets_manager.is_available():
            st.markdown("""
            **🔗 구글 시트 방식 (추천):**
            1. 구글 시트에서 "공유" → 서비스 계정을 "편집자" 권한으로 추가 또는 "링크가 있는 모든 사용자" → "편집자" 권한 설정
            2. 시트 URL 복사
            3. 아래 "구글 시트" 탭에서 URL 붙여넣기
            4. **불러오기** 버튼 클릭
            5. 데이터 범위 설정 (선택사항)
            6. **변환하기** 또는 **시트에 저장하기** 선택
            
            **📝 텍스트 입력 방식:**
            1. 구글 시트에서 **캐릭터, 대사, 사운드 파일명** 컬럼 범위를 선택
            2. **Ctrl+C**로 복사
            3. "텍스트 입력" 탭에서 **Ctrl+V**로 붙여넣기
            4. **변환하기** 버튼 클릭
            
            **주의**: 캐릭터 이름이 캐릭터 관리에 등록되어 있어야 올바르게 변환됩니다.
            """)
        else:
            st.markdown("""
            1. 구글 시트에서 **캐릭터, 대사, 사운드 파일명** 컬럼 범위를 선택
            2. **Ctrl+C**로 복사
            3. 아래 텍스트 영역에 **Ctrl+V**로 붙여넣기
            4. **변환하기** 버튼 클릭
            
            **주의**: 캐릭터 이름이 캐릭터 관리에 등록되어 있어야 올바르게 변환됩니다.
            """)

    # 입력 방식 선택 - API 사용 가능 여부에 따라 다른 UI 제공
    if sheets_manager.is_available():
        # API가 설정된 경우: 구글 시트와 텍스트 입력 탭 모두 제공
        input_method_tabs = st.tabs(["🔗 구글 시트", "📝 텍스트 입력"])
        
        # 구글 시트 탭
        with input_method_tabs[0]:
            st.subheader("📥 구글 시트에서 불러오기")
            
            # 최근 접근 정보 불러오기
            last_access = config_manager.get_last_access()
            recent_urls = config_manager.get_recent_urls()
            
            col_sheet_a, col_sheet_b = st.columns([3, 1])
            
            with col_sheet_a:
                # 최근 URL 선택 옵션
                if recent_urls:
                    use_recent = st.checkbox("📚 최근 사용한 시트에서 선택", key="use_recent_checkbox")
                    
                    if use_recent:
                        selected_recent = st.selectbox(
                            "최근 사용한 URL",
                            options=recent_urls,
                            index=0 if recent_urls else None,
                            key="recent_url_select"
                        )
                        sheet_url = selected_recent
                    else:
                        sheet_url = st.text_input(
                            "구글 시트 URL",
                            value=last_access["url"],
                            placeholder="https://docs.google.com/spreadsheets/d/1A2B3C4D5E6F7.../edit#gid=0",
                            help="구글 시트 URL을 붙여넣으세요.",
                            key="sheet_url_input"
                        )
                else:
                    sheet_url = st.text_input(
                        "구글 시트 URL",
                        value=last_access["url"],
                        placeholder="https://docs.google.com/spreadsheets/d/1A2B3C4D5E6F7.../edit#gid=0",
                        help="구글 시트 URL을 붙여넣으세요.",
                        key="sheet_url_input"
                    )
            
            with col_sheet_b:
                sheet_name = st.text_input(
                    "시트 이름 (선택사항)",
                    value=last_access["sheet_name"],
                    placeholder="3_2",
                    help="특정 시트 탭 이름을 입력하세요.",
                    key="sheet_name_input"
                )
            
            # 자동 채우기 옵션
            auto_fill_sheets = st.checkbox(
                "🔧 포트레이트/사운드 주소 자동 채우기", 
                value=True, 
                help="비어있는 포트레이트와 사운드 주소를 자동으로 생성합니다",
                key="auto_fill_sheets_checkbox"
            )
            
            # 불러오기 버튼
            load_button = st.button("📥 구글 시트에서 불러오기", type="primary", use_container_width=True, key="load_from_sheets_btn")
            
            # 세션 상태 초기화
            if 'raw_sheet_data' not in st.session_state:
                st.session_state.raw_sheet_data = None
            if 'sheet_columns' not in st.session_state:
                st.session_state.sheet_columns = []
            if 'mapped_data' not in st.session_state:
                st.session_state.mapped_data = None
            if 'current_sheet_url' not in st.session_state:
                st.session_state.current_sheet_url = ""
            if 'full_raw_data' not in st.session_state:
                st.session_state.full_raw_data = None
            if 'data_loaded' not in st.session_state:
                st.session_state.data_loaded = False
            if 'last_parse_settings' not in st.session_state:
                st.session_state.last_parse_settings = None
            
            # 구글 시트 불러오기
            if load_button and sheet_url.strip():
                with st.spinner("구글 시트에서 데이터를 불러오는 중..."):
                    # 기본 데이터 로드 (전체 시트)
                    success, message, raw_df, all_data = sheets_manager.read_sheet_data(
                        sheet_url, 
                        sheet_name.strip() if sheet_name.strip() else None,
                        header_row=0
                    )
                    
                    if success and raw_df is not None:
                        # 접근 정보 저장
                        config_manager.save_last_access(sheet_url, sheet_name.strip())
                        
                        st.success(f"✅ {message}")
                        
                        # 전체 데이터 저장 (새로운 시트이므로 모든 상태 초기화)
                        st.session_state.full_raw_data = all_data
                        st.session_state.current_sheet_url = sheet_url
                        st.session_state.data_loaded = True
                        st.session_state.last_parse_settings = None  # 파싱 설정 초기화
                        st.session_state.mapped_data = None  # 매핑 데이터 초기화
                        
                        # 기본 파싱 결과도 저장 (1행 헤더 기준)
                        st.session_state.raw_sheet_data = raw_df
                        st.session_state.sheet_columns = list(raw_df.columns)
                        
                    else:
                        st.error(f"❌ {message}")
                        st.session_state.data_loaded = False
                        st.session_state.raw_sheet_data = None
            elif load_button and not sheet_url.strip():
                st.warning("⚠️ 구글 시트 URL을 입력해주세요.")
            
            # 데이터가 로드된 경우에만 미리보기 및 파싱 옵션 표시
            if st.session_state.data_loaded and st.session_state.full_raw_data is not None:
                        
                # 전체 시트 미리보기 (헤더 행 선택용)
                with st.expander("📋 전체 시트 미리보기 (헤더 행 및 범위 설정)", expanded=True):
                    st.write("**전체 시트 데이터 (행 번호와 함께 표시):**")
                    
                    # 행 번호 추가한 미리보기
                    preview_data = st.session_state.full_raw_data.copy()
                    preview_data.index = [f"행 {i+1}" for i in range(len(preview_data))]
                    st.dataframe(preview_data.head(15), use_container_width=True)
                    st.caption("⬆️ 위 표에서 컬럼 헤더가 있는 행을 찾아서 아래에서 선택하세요")
                    
                    # 헤더 행 및 데이터 범위 설정
                    col_header_a, col_header_b, col_header_c, col_header_d = st.columns(4)
                    
                    with col_header_a:
                        header_row = st.number_input(
                            "헤더 행 번호 (1부터 시작)",
                            min_value=1,
                            max_value=len(st.session_state.full_raw_data),
                            value=2,  # 기본값을 2행으로 설정
                            help="컬럼 이름이 있는 행 번호를 입력하세요",
                            key="header_row_input"
                        )
                    
                    with col_header_b:
                        start_row = st.number_input(
                            "시작 행 번호 (데이터, 헤더 제외)",
                            min_value=1,
                            value=1,
                            help="변환을 시작할 데이터 행 번호 (헤더 제외)",
                            key="start_row_input"
                        )
                    
                    with col_header_c:
                        max_data_rows = len(st.session_state.full_raw_data) - header_row
                        end_row = st.number_input(
                            "끝 행 번호 (데이터, 헤더 제외)",
                            min_value=1,
                            max_value=max_data_rows if max_data_rows > 0 else 1,
                            value=min(10, max_data_rows) if max_data_rows > 0 else 1,  # 기본값을 10행으로 제한
                            help="변환을 끝낼 데이터 행 번호 (헤더 제외)",
                            key="end_row_input"
                        )
                    
                    with col_header_d:
                        reparse_button = st.button("🔄 설정 적용", type="secondary", use_container_width=True, key="reparse_btn")
                    
                    # 현재 파싱 설정
                    current_settings = {
                        'header_row': header_row,
                        'start_row': start_row,
                        'end_row': end_row
                    }
                    
                    # 설정이 변경되었거나 다시 파싱 버튼을 누른 경우
                    settings_changed = st.session_state.last_parse_settings != current_settings
                    
                    if reparse_button or settings_changed:
                        with st.spinner("선택한 설정으로 파싱 중..."):
                            success2, message2, parsed_df, _ = sheets_manager.read_sheet_data(
                                st.session_state.current_sheet_url,
                                sheet_name.strip() if sheet_name.strip() else None,
                                header_row=header_row-1,  # UI는 1부터 시작, 내부는 0부터 시작
                                start_row=start_row,
                                end_row=end_row
                            )
                            
                            if success2 and parsed_df is not None:
                                st.session_state.raw_sheet_data = parsed_df
                                st.session_state.sheet_columns = list(parsed_df.columns)
                                st.session_state.last_parse_settings = current_settings.copy()
                                # 매핑 데이터는 설정이 변경된 경우에만 초기화
                                if settings_changed:
                                    st.session_state.mapped_data = None
                                
                                st.success(f"✅ {message2}")
                                
                                # 범위 정보 표시
                                st.info(f"📊 선택된 범위: 헤더 {header_row}행, 데이터 {start_row}-{end_row}행 ({len(parsed_df)}개 행)")
                                
                            else:
                                st.error(f"❌ 파싱 실패: {message2}")
                    
                    # 파싱된 데이터 미리보기 (데이터가 있는 경우)
                    if st.session_state.raw_sheet_data is not None:
                        with st.expander("📊 파싱된 데이터 미리보기", expanded=True):
                            st.dataframe(st.session_state.raw_sheet_data.head(10), use_container_width=True)
                            st.caption(f"컬럼: {', '.join(st.session_state.raw_sheet_data.columns)}")
                            st.caption(f"총 {len(st.session_state.raw_sheet_data)}개 행")
            
            # 컬럼 매핑 UI (파싱된 데이터가 있는 경우)
            if st.session_state.raw_sheet_data is not None and len(st.session_state.sheet_columns) > 0:
                st.markdown("---")
                st.subheader("🔧 컬럼 매핑 설정")
                
                # 저장된 매핑이 있는지 확인
                saved_mapping = config_manager.get_column_mapping(st.session_state.current_sheet_url)
                
                if saved_mapping and st.session_state.mapped_data is None:
                    st.info(f"✅ 이 시트의 저장된 설정을 찾았습니다!")
                    
                    col_auto, col_manual = st.columns(2)
                    with col_auto:
                        use_saved = st.button("📋 저장된 설정 사용", use_container_width=True, key="use_saved_mapping")
                    with col_manual:
                        manual_mapping_btn = st.button("⚙️ 수동으로 다시 설정", use_container_width=True, key="manual_mapping")
                    
                    if use_saved:
                        # 저장된 매핑 적용
                        try:
                            mapped_df = config_manager.apply_mapping(st.session_state.raw_sheet_data, saved_mapping)
                            
                            # 자동 채우기 적용
                            if auto_fill_sheets:
                                ps_manager = PortraitSoundManager(char_manager)
                                mapped_df = ps_manager.auto_fill_missing_fields(mapped_df)
                            
                            st.session_state.mapped_data = mapped_df
                            st.success("✅ 저장된 설정으로 매핑 완료!")
                            # st.rerun() 제거 - 자동으로 업데이트됨
                            
                        except Exception as e:
                            st.error(f"❌ 저장된 설정 적용 중 오류: {e}")
                
                # 수동 매핑 또는 저장된 설정이 없는 경우
                show_manual_mapping = (
                    not saved_mapping or 
                    (saved_mapping and st.session_state.get('show_manual_mapping', False)) or
                    'manual_mapping_btn' in locals()
                )
                
                if show_manual_mapping:
                    if 'manual_mapping_btn' in locals() and manual_mapping_btn:
                        st.session_state.show_manual_mapping = True
                    
                    st.write("**실제 컬럼을 역할에 매핑하세요:**")
                    
                    role_columns = config_manager.get_role_columns()
                    available_columns = ["(선택안함)"] + st.session_state.sheet_columns
                    
                    # 컬럼 매핑 UI
                    column_mapping = {}
                    
                    for role, req_type in role_columns.items():
                        col_map_a, col_map_b = st.columns([2, 1])
                        
                        with col_map_a:
                            selected_col = st.selectbox(
                                f"{role} ({req_type})",
                                options=available_columns,
                                index=0,
                                key=f"mapping_{role}"
                            )
                            
                            if selected_col != "(선택안함)":
                                column_mapping[selected_col] = role
                        
                        with col_map_b:
                            if req_type == "필수":
                                st.markdown("🔴 **필수**")
                            else:
                                st.markdown("🟡 선택적")
                    
                    # 매핑 적용 버튼
                    if st.button("✅ 매핑 적용하기", type="primary", use_container_width=True, key="apply_mapping"):
                        # 매핑 검증
                        is_valid, validation_msg = config_manager.validate_mapping(column_mapping)
                        
                        if is_valid:
                            try:
                                # 매핑 적용
                                mapped_df = config_manager.apply_mapping(st.session_state.raw_sheet_data, column_mapping)
                                
                                # 자동 채우기 적용
                                if auto_fill_sheets:
                                    ps_manager = PortraitSoundManager(char_manager)
                                    mapped_df = ps_manager.auto_fill_missing_fields(mapped_df)
                                
                                st.session_state.mapped_data = mapped_df
                                st.session_state.show_manual_mapping = False
                                
                                # 매핑 설정 저장
                                config_manager.save_column_mapping(st.session_state.current_sheet_url, column_mapping)
                                
                                st.success("✅ 매핑 완료! 설정이 저장되었습니다.")
                                # st.rerun() 제거 - 자동으로 업데이트됨
                                
                            except Exception as e:
                                st.error(f"❌ 매핑 적용 중 오류: {e}")
                        else:
                            st.error(f"❌ {validation_msg}")
                
                # 매핑된 데이터 미리보기 (매핑 완료된 경우)
                if st.session_state.mapped_data is not None:
                    with st.expander("📊 매핑된 데이터 미리보기", expanded=False):
                        st.dataframe(st.session_state.mapped_data.head(10), use_container_width=True)
                        st.caption(f"매핑 완료: {len(st.session_state.mapped_data)}개 행")
            
            # 변환 및 저장 버튼 (매핑된 데이터가 있는 경우)
            if st.session_state.mapped_data is not None:
                st.markdown("---")
                st.subheader("🚀 변환 및 저장")
                
                col_convert, col_save = st.columns(2)
                
                with col_convert:
                    convert_btn = st.button("🔄 대사 변환하기", type="primary", use_container_width=True, key="convert_from_sheets_btn")
                
                with col_save:
                    save_to_sheet_btn = st.button("💾 구글 시트에 저장하기", type="secondary", use_container_width=True, key="save_to_sheets_btn")
                
                # 변환 처리
                if convert_btn or save_to_sheet_btn:
                    with st.spinner("변환 중..."):
                        converted_results = convert_dialogue_data(st.session_state.mapped_data, char_manager)
                    
                    if converted_results:
                        # 변환 성공
                        st.success(f"✅ {len(converted_results)}개 행 변환 완료!")
                        
                        result_text = "\n".join(converted_results)
                        
                        # 결과 표시 및 복사 기능
                        with st.expander("📄 변환 결과", expanded=True):
                            st.code(result_text, language="text")
                            
                            # 복사 버튼
                            try:
                                if st.button("📋 클립보드에 복사", key="copy_to_clipboard"):
                                    pyperclip.copy(result_text)
                                    st.success("✅ 클립보드에 복사되었습니다!")
                            except:
                                st.info("💡 수동으로 위 텍스트를 선택하여 복사하세요.")
                        
                        # 구글 시트에 저장 처리
                        if save_to_sheet_btn:
                            with st.expander("💾 구글 시트 저장 설정", expanded=True):
                                col_save_a, col_save_b, col_save_c = st.columns(3)
                                
                                with col_save_a:
                                    save_option = st.radio(
                                        "저장 방식",
                                        ["새 시트 생성", "기존 시트에 저장"],
                                        key="save_option_radio"
                                    )
                                
                                with col_save_b:
                                    if save_option == "새 시트 생성":
                                        new_sheet_name = st.text_input(
                                            "새 시트 이름",
                                            value="변환결과",
                                            key="new_sheet_name_input"
                                        )
                                    else:
                                        target_sheet_name = st.text_input(
                                            "대상 시트 이름",
                                            value="변환결과",
                                            key="target_sheet_name_input"
                                        )
                                
                                with col_save_c:
                                    start_cell = st.text_input(
                                        "시작 셀",
                                        value="A1",
                                        key="start_cell_input"
                                    )
                                
                                if st.button("💾 저장 실행", type="primary", use_container_width=True, key="execute_save"):
                                    with st.spinner("구글 시트에 저장 중..."):
                                        # 저장할 데이터 준비
                                        save_data = [["대사 변환 결과"]]  # 헤더
                                        for line in converted_results:
                                            save_data.append([line])
                                        
                                        # 저장 실행
                                        if save_option == "새 시트 생성":
                                            success, save_message, sheet_url_result = sheets_manager.write_to_sheet(
                                                st.session_state.current_sheet_url,
                                                save_data,
                                                start_cell=start_cell,
                                                create_new_sheet=True,
                                                new_sheet_name=new_sheet_name
                                            )
                                        else:
                                            success, save_message, sheet_url_result = sheets_manager.write_to_sheet(
                                                st.session_state.current_sheet_url,
                                                save_data,
                                                sheet_name=target_sheet_name,
                                                start_cell=start_cell
                                            )
                                        
                                        if success:
                                            st.success(f"✅ {save_message}")
                                            if sheet_url_result:
                                                st.markdown(f"🔗 [저장된 시트 보기]({sheet_url_result})")
                                        else:
                                            st.error(f"❌ 저장 실패: {save_message}")
                        
                        # 통계 정보
                        with st.expander("📊 변환 통계"):
                            st.write(f"- 총 변환된 행: {len(converted_results)}개")
                            st.write(f"- 총 글자수: {len(result_text):,}자")
                            
                            # 캐릭터별 통계
                            if '캐릭터' in st.session_state.mapped_data.columns:
                                character_counts = st.session_state.mapped_data['캐릭터'].value_counts()
                                st.write("- 캐릭터별 대사 수:")
                                for char, count in character_counts.items():
                                    st.write(f"  - {char}: {count}개")
                    else:
                        st.error("❌ 변환 중 오류가 발생했습니다.")
        
        # 텍스트 입력 탭
        with input_method_tabs[1]:
            st.subheader("📥 텍스트 입력")
            
            # 자동 채우기 옵션
            auto_fill_text = st.checkbox(
                "🔧 포트레이트/사운드 주소 자동 채우기", 
                value=True, 
                help="비어있는 포트레이트와 사운드 주소를 자동으로 생성합니다",
                key="auto_fill_text_checkbox"
            )
            
            # 데이터 입력 영역
            input_data = st.text_area(
                "구글 시트 데이터를 여기에 붙여넣으세요",
                height=280,
                placeholder="캐릭터\t대사\t포트레이트\t사운드 주소\t사운드 파일명\n샤오\t사부! 큰일 났어요!\tShao/Shao_Default.rux\tevent:/Story/15031309/15031309_Shao_01\t15031309_Shao_01",
                key="text_input_area"
            )
            
            # 변환 버튼
            convert_text_button = st.button("🔄 변환하기", type="primary", use_container_width=True, key="convert_from_text_btn")
            
            if convert_text_button and input_data.strip():
                try:
                    # 데이터 검증 및 자동 채우기
                    is_valid, message, df = validate_data(input_data, auto_fill_text, char_manager)
                    
                    if not is_valid:
                        st.error(f"❌ 데이터 오류: {message}")
                    else:
                        # 자동 채우기 결과 표시
                        if auto_fill_text:
                            with st.expander("🔧 자동 채우기 결과", expanded=False):
                                st.write("**처리된 데이터 미리보기:**")
                                preview_df = df[['캐릭터', '포트레이트', '사운드 주소', '사운드 파일명']].head(5)
                                st.dataframe(preview_df, use_container_width=True)
                        
                        # 데이터 변환
                        with st.spinner("변환 중..."):
                            converted_results = convert_dialogue_data(df, char_manager)
                        
                        if converted_results:
                            # 변환 성공
                            st.success(f"✅ {len(converted_results)}개 행 변환 완료!")
                            
                            # 결과 표시
                            result_text = "\n".join(converted_results)
                            st.code(result_text, language="text")
                            
                            # 복사 버튼
                            try:
                                if st.button("📋 클립보드에 복사", key="copy_text_result"):
                                    pyperclip.copy(result_text)
                                    st.success("✅ 클립보드에 복사되었습니다!")
                            except:
                                st.info("💡 수동으로 위 텍스트를 선택하여 복사하세요.")
                            
                            # 통계 정보
                            with st.expander("📊 변환 통계"):
                                st.write(f"- 총 변환된 행: {len(converted_results)}개")
                                st.write(f"- 총 글자수: {len(result_text):,}자")
                                
                                # 캐릭터별 통계
                                character_counts = df['캐릭터'].value_counts()
                                st.write("- 캐릭터별 대사 수:")
                                for char, count in character_counts.items():
                                    st.write(f"  - {char}: {count}개")
                        else:
                            st.error("❌ 변환 중 오류가 발생했습니다.")
                            
                except Exception as e:
                    st.error(f"❌ 처리 중 오류: {str(e)}")
                    st.write("입력 데이터 형식을 확인해주세요.")
            
            elif convert_text_button and not input_data.strip():
                st.warning("⚠️ 입력 데이터를 먼저 붙여넣어주세요.")
                
    else:
        # API가 설정되지 않은 경우: 텍스트 입력 방식만 제공
        st.subheader("📥 입력 데이터")
        
        st.info("💡 구글 시트 API를 설정하면 URL만으로 데이터를 불러올 수 있습니다.")
        
        # 자동 채우기 옵션
        auto_fill = st.checkbox(
            "🔧 포트레이트/사운드 주소 자동 채우기", 
            value=True, 
            help="비어있는 포트레이트와 사운드 주소를 자동으로 생성합니다",
            key="auto_fill_no_api_checkbox"
        )
        
        # 데이터 입력 영역
        input_data = st.text_area(
            "구글 시트 데이터를 여기에 붙여넣으세요",
            height=280,
            placeholder="캐릭터\t대사\t포트레이트\t사운드 주소\t사운드 파일명\n샤오\t사부! 큰일 났어요!\tShao/Shao_Default.rux\tevent:/Story/15031309/15031309_Shao_01\t15031309_Shao_01",
            key="input_data_no_api"
        )
        
        # 변환 버튼
        convert_button = st.button("🔄 변환하기", type="primary", use_container_width=True, key="convert_no_api_btn")

        if convert_button and input_data.strip():
            try:
                # 데이터 검증 및 자동 채우기
                is_valid, message, df = validate_data(input_data, auto_fill, char_manager)
                
                if not is_valid:
                    st.error(f"❌ 데이터 오류: {message}")
                else:
                    # 자동 채우기 결과 표시
                    if auto_fill:
                        with st.expander("🔧 자동 채우기 결과", expanded=False):
                            st.write("**처리된 데이터 미리보기:**")
                            preview_df = df[['캐릭터', '포트레이트', '사운드 주소', '사운드 파일명']].head(5)
                            st.dataframe(preview_df, use_container_width=True)
                    
                    # 데이터 변환
                    with st.spinner("변환 중..."):
                        converted_results = convert_dialogue_data(df, char_manager)
                    
                    if converted_results:
                        # 변환 성공
                        st.success(f"✅ {len(converted_results)}개 행 변환 완료!")
                        
                        # 결과 표시
                        result_text = "\n".join(converted_results)
                        st.code(result_text, language="text")
                        
                        # 복사 버튼
                        try:
                            if st.button("📋 클립보드에 복사", key="copy_no_api_result"):
                                pyperclip.copy(result_text)
                                st.success("✅ 클립보드에 복사되었습니다!")
                        except:
                            st.info("💡 수동으로 위 텍스트를 선택하여 복사하세요.")
                        
                        # 통계 정보
                        with st.expander("📊 변환 통계"):
                            st.write(f"- 총 변환된 행: {len(converted_results)}개")
                            st.write(f"- 총 글자수: {len(result_text):,}자")
                            
                            # 캐릭터별 통계
                            character_counts = df['캐릭터'].value_counts()
                            st.write("- 캐릭터별 대사 수:")
                            for char, count in character_counts.items():
                                st.write(f"  - {char}: {count}개")
                    else:
                        st.error("❌ 변환 중 오류가 발생했습니다.")
                        
            except Exception as e:
                st.error(f"❌ 처리 중 오류: {str(e)}")
                st.write("입력 데이터 형식을 확인해주세요.")
        
        elif convert_button and not input_data.strip():
            st.warning("⚠️ 입력 데이터를 먼저 붙여넣어주세요.")

    # 자동 생성 미리보기 도구
    with st.expander("🔧 자동 생성 미리보기", expanded=False):
        col_prev_a, col_prev_b = st.columns(2)
        
        with col_prev_a:
            preview_char = st.text_input("캐릭터 이름", placeholder="샤오", key="preview_char_sidebar")
        with col_prev_b:
            preview_sound = st.text_input("사운드 파일명", placeholder="15031309_Shao_01", key="preview_sound_sidebar")
        
        if st.button("🔍 미리보기", key="preview_btn_sidebar"):
            if preview_char or preview_sound:
                ps_manager = PortraitSoundManager(char_manager)
                preview_result = ps_manager.get_auto_generation_preview(preview_char, preview_sound)
                
                st.write("**생성 결과:**")
                st.code(f"""포트레이트: {preview_result['portrait']}
사운드 주소: {preview_result['sound_address']}
스토리 ID: {preview_result['story_id']}
파일에서 추출된 캐릭터: {preview_result['character_from_filename']}
순서 번호: {preview_result['sequence']}""")
            else:
                st.warning("캐릭터 이름 또는 사운드 파일명을 입력해주세요.")

# ===== 캐릭터 관리 탭 =====
with tab2:
    st.subheader("👥 캐릭터 관리")
    
    # 구글 시트 API 상태 표시
    if not sheets_manager.is_available():
        setup_status = sheets_manager.validate_setup()
        
        if not setup_status['gspread_available']:
            st.error("📦 구글 시트 라이브러리가 설치되지 않았습니다.")
            with st.expander("⚙️ 라이브러리 설치 방법", expanded=True):
                st.code("pip install gspread google-auth", language="bash")
                st.write("또는")
                st.code("pip install -r requirements.txt", language="bash")
                st.info("설치 후 프로그램을 재시작하세요.")
        else:
            with st.expander("⚙️ 구글 시트 API 설정", expanded=False):
                st.warning("구글 시트 API가 설정되지 않았습니다. 설정하면 URL만으로 캐릭터 데이터를 가져올 수 있습니다.")
                st.text(sheets_manager.setup_instructions())
                
                # 설정 상태 확인
                st.write("**현재 설정 상태:**")
                st.write(f"- 라이브러리: {'✅ 설치됨' if setup_status['gspread_available'] else '❌ 미설치'}")
                st.write(f"- Service Account 파일: {'✅ 있음' if setup_status['service_account_file_exists'] else '❌ 없음'}")
                st.write(f"- 클라이언트 초기화: {'✅ 성공' if setup_status['client_initialized'] else '❌ 실패'}")
    else:
        st.success("✅ 구글 시트 API가 설정되어 있습니다.")
    
    # 현재 등록된 캐릭터 표시
    characters_df = char_manager.get_characters_dataframe()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("**등록된 캐릭터 목록:**")
        if len(characters_df) > 0:
            st.dataframe(characters_df, use_container_width=True, height=300)
            st.caption(f"총 {len(characters_df)}개 캐릭터 등록됨")
        else:
            st.info("등록된 캐릭터가 없습니다.")
    
    with col2:
        # 새 캐릭터 추가 (개선된 UI)
        st.write("**새 캐릭터 추가:**")
        
        with st.form("add_character_form"):
            new_name = st.text_input("Name (영문)", placeholder="Douglas", key="new_name_input")
            new_kr = st.text_input("KR (한글)", placeholder="더글라스", key="new_kr_input")
            
            # String_ID 커스텀 입력 섹션
            st.write("**String_ID 설정:**")
            use_custom_id = st.checkbox("커스텀 String_ID 사용", key="use_custom_id_checkbox")
            
            if use_custom_id:
                custom_string_id = st.text_input(
                    "String_ID (영문, 숫자, _만 사용)",
                    placeholder="douglas_v2",
                    help="영문자로 시작하고, 영문자, 숫자, 언더스코어(_)만 사용 가능",
                    key="custom_string_id_input"
                )
            else:
                # 자동 생성 미리보기
                if new_name:
                    auto_generated = char_manager.generate_string_id(new_name)
                    st.info(f"자동 생성될 String_ID: `{auto_generated}`")
                custom_string_id = None
            
            if st.form_submit_button("➕ 캐릭터 추가", use_container_width=True):
                if new_name and new_kr:
                    # 캐릭터 추가 (커스텀 String_ID 포함)
                    success, message, char_data = char_manager.add_character(
                        new_name, 
                        new_kr, 
                        custom_string_id if use_custom_id else None
                    )
                    
                    if success:
                        st.success(f"✅ {message}")
                        st.write(f"- String_ID: `{char_data['string_id']}`")
                        st.write(f"- Converter_Name: `{char_data['converter_name']}`")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
                else:
                    st.error("❌ Name과 KR을 모두 입력해주세요.")
        
        st.markdown("---")
        
        # 구글 시트에서 가져오기
        st.write("**구글 시트에서 가져오기:**")
        
        if sheets_manager.is_available():
            # API가 설정된 경우 URL 방식과 텍스트 방식 모두 제공
            import_tabs = st.tabs(["🔗 URL", "📝 텍스트"])
            
            with import_tabs[0]:
                with st.form("import_from_url_form"):
                    sheet_url_import = st.text_input(
                        "구글 시트 URL",
                        placeholder="https://docs.google.com/...",
                        key="import_url_input"
                    )
                    sheet_name_import = st.text_input(
                        "시트 이름",
                        placeholder="#String",
                        key="import_sheet_name_input"
                    )
                    header_row_import = st.number_input(
                        "헤더 행 번호 (1부터 시작)",
                        min_value=1,
                        value=1,
                        help="컬럼 이름이 있는 행 번호",
                        key="header_row_import_input"
                    )
                    
                    if st.form_submit_button("📥 URL에서 가져오기", use_container_width=True):
                        if sheet_url_import.strip():
                            with st.spinner("구글 시트에서 데이터를 불러오는 중..."):
                                success, message, df, _ = sheets_manager.read_sheet_data(
                                    sheet_url_import, 
                                    sheet_name_import.strip() if sheet_name_import.strip() else None,
                                    header_row=header_row_import-1
                                )
                                
                                if success and df is not None:
                                    # DataFrame을 문자열로 변환 후 import
                                    df_string = df.to_csv(sep='\t', index=False)
                                    import_success, import_message, count = char_manager.import_from_sheet_data(df_string)
                                    
                                    if import_success:
                                        st.success(f"✅ {import_message}")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {import_message}")
                                else:
                                    st.error(f"❌ {message}")
                        else:
                            st.warning("⚠️ 구글 시트 URL을 입력해주세요.")
            
            with import_tabs[1]:
                with st.expander("📋 사용법"):
                    st.markdown("""
                    1. 구글 시트의 #String 시트에서 데이터 범위 선택
                    2. **Ctrl+C**로 복사  
                    3. 아래에 붙여넣기
                    4. **가져오기** 버튼 클릭
                    
                    **시트 형식**: String_ID | KR | Converter_Name | Name
                    """)
                
                sheet_data = st.text_area(
                    "시트 데이터 붙여넣기",
                    height=150,
                    placeholder="douglas\t더글라스\t[@douglas]\tDouglas",
                    key="import_text_area_tabs"
                )
                
                if st.button("📥 텍스트에서 가져오기", use_container_width=True, key="import_from_text"):
                    if sheet_data.strip():
                        success, message, count = char_manager.import_from_sheet_data(sheet_data)
                        if success:
                            st.success(f"✅ {message}")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                    else:
                        st.warning("⚠️ 시트 데이터를 먼저 붙여넣어주세요.")
        else:
            # API가 설정되지 않은 경우 텍스트 방식만 제공
            with st.expander("📋 사용법"):
                st.markdown("""
                1. 구글 시트의 #String 시트에서 데이터 범위 선택
                2. **Ctrl+C**로 복사  
                3. 아래에 붙여넣기
                4. **가져오기** 버튼 클릭
                
                **시트 형식**: String_ID | KR | Converter_Name | Name
                """)
            
            sheet_data = st.text_area(
                "시트 데이터 붙여넣기",
                height=150,
                placeholder="douglas\t더글라스\t[@douglas]\tDouglas",
                key="import_text_area_no_api"
            )
            
            if st.button("📥 시트에서 가져오기", use_container_width=True):
                if sheet_data.strip():
                    success, message, count = char_manager.import_from_sheet_data(sheet_data)
                    if success:
                        st.success(f"✅ {message}")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
                else:
                    st.warning("⚠️ 시트 데이터를 먼저 붙여넣어주세요.")
    
    # 캐릭터 수정 및 삭제 섹션
    if len(characters_df) > 0:
        st.markdown("---")
        
        # 캐릭터 수정 섹션
        with st.expander("✏️ 캐릭터 수정", expanded=False):
            col_edit_a, col_edit_b = st.columns([2, 1])
            
            with col_edit_a:
                char_to_edit = st.selectbox(
                    "수정할 캐릭터 선택",
                    options=[f"{row['String_ID']} ({row['Name']} - {row['KR']})" for _, row in characters_df.iterrows()],
                    index=None,
                    placeholder="수정할 캐릭터를 선택하세요",
                    key="edit_char_select"
                )
            
            if char_to_edit:
                # 선택된 캐릭터 정보 가져오기
                selected_string_id = char_to_edit.split(" (")[0]
                char_data = char_manager.get_character_by_string_id(selected_string_id)
                
                if char_data:
                    with st.form("edit_character_form"):
                        st.write(f"**현재 정보: {char_data['name']} ({char_data['kr']})**")
                        
                        new_name = st.text_input("새 Name (영문)", value=char_data['name'], key="edit_name_input")
                        new_kr = st.text_input("새 KR (한글)", value=char_data['kr'], key="edit_kr_input")
                        new_string_id = st.text_input(
                            "새 String_ID",
                            value=char_data['string_id'],
                            help="변경할 경우 기존 참조가 깨질 수 있습니다",
                            key="edit_string_id_input"
                        )
                        
                        if st.form_submit_button("✅ 수정 완료", use_container_width=True):
                            success, message, updated_data = char_manager.update_character(
                                selected_string_id,
                                name=new_name if new_name != char_data['name'] else None,
                                kr_name=new_kr if new_kr != char_data['kr'] else None,
                                new_string_id=new_string_id if new_string_id != char_data['string_id'] else None
                            )
                            
                            if success:
                                st.success(f"✅ {message}")
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
        
        # 캐릭터 삭제 섹션
        st.write("**캐릭터 삭제:**")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            char_to_delete = st.selectbox(
                "삭제할 캐릭터 선택",
                options=[f"{row['Name']} ({row['KR']}) - {row['String_ID']}" for _, row in characters_df.iterrows()],
                index=None,
                placeholder="삭제할 캐릭터를 선택하세요"
            )
        
        with col2:
            if st.button("🗑️ 삭제", type="secondary", use_container_width=True):
                if char_to_delete:
                    # 선택된 캐릭터의 String_ID 찾기
                    string_id_part = char_to_delete.split(" - ")[-1]
                    
                    if char_manager.delete_character(string_id_part):
                        st.success(f"✅ '{char_to_delete}' 삭제 완료!")
                        st.rerun()
                    else:
                        st.error("❌ 삭제 중 오류가 발생했습니다.")
                else:
                    st.warning("⚠️ 삭제할 캐릭터를 선택해주세요.")
    
    # 캐릭터 데이터 내보내기
    if len(characters_df) > 0:
        st.markdown("---")
        st.write("**📤 캐릭터 데이터 내보내기:**")
        
        export_data = char_manager.export_to_sheet_format()
        
        col_export_a, col_export_b = st.columns([2, 1])
        
        with col_export_a:
            st.text_area(
                "내보내기 데이터 (복사해서 사용하세요)",
                value=export_data,
                height=100,
                key="export_data_textarea"
            )
        
        with col_export_b:
            try:
                if st.button("📋 클립보드에 복사", key="copy_export_data"):
                    pyperclip.copy(export_data)
                    st.success("✅ 복사 완료!")
            except:
                st.info("💡 수동으로 복사하세요.")
    
    # 설정 관리 섹션
    st.markdown("---")
    st.write("**⚙️ 설정 관리:**")
    
    config_summary = config_manager.get_config_summary()
    
    with st.expander("📊 설정 현황", expanded=False):
        st.write("**현재 저장된 설정:**")
        st.write(f"- 저장된 시트 설정: {config_summary['저장된_시트_수']}개")
        st.write(f"- 최근 접근 URL: {config_summary['최근_URL_수']}개")
        st.write(f"- 마지막 접근: {config_summary['마지막_접근']}")
        
        if config_summary['저장된_시트_수'] > 0:
            col_reset1, col_reset2 = st.columns(2)
            with col_reset1:
                if st.button("🗑️ 모든 설정 초기화", type="secondary", use_container_width=True):
                    config_manager.clear_config()
                    st.success("✅ 모든 설정이 초기화되었습니다!")
                    # 설정 초기화 후 세션 상태도 초기화
                    st.session_state.data_loaded = False
                    st.session_state.raw_sheet_data = None
                    st.session_state.mapped_data = None
                    st.rerun()
            
            with col_reset2:
                st.caption("⚠️ 저장된 컬럼 매핑과 URL 기록이 모두 삭제됩니다.")

# 하단 정보
st.markdown("---")
col_info1, col_info2, col_info3 = st.columns(3)

with col_info1:
    st.markdown("""
    <div style='text-align: center; color: #888;'>
        <small>💡 문제가 발생하면 캐릭터 관리에서 캐릭터를 등록하거나 개발자에게 문의하세요.</small>
    </div>
    """, unsafe_allow_html=True)

with col_info2:
    if not sheets_manager.is_available():
        st.markdown("""
        <div style='text-align: center; color: #888;'>
            <small>🔗 구글 시트 API를 설정하면 URL만으로 데이터를 불러올 수 있습니다.</small>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style='text-align: center; color: #888;'>
            <small>✅ 구글 시트 API가 활성화되어 있습니다.</small>
        </div>
        """, unsafe_allow_html=True)

with col_info3:
    # 설정 요약 정보
    config_summary = config_manager.get_config_summary()
    st.markdown(f"""
    <div style='text-align: center; color: #888;'>
        <small>📚 저장된 시트: {config_summary['저장된_시트_수']}개 | 최근 URL: {config_summary['최근_URL_수']}개</small>
    </div>
    """, unsafe_allow_html=True)