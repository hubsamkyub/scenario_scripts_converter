import pandas as pd
import re
from io import StringIO
from portrait_sound_manager import PortraitSoundManager

# 캐릭터 매핑은 CharacterManager에서 동적으로 관리됩니다.

def validate_data(input_text, auto_fill=True, char_manager=None):
    """
    입력 데이터 검증 및 자동 채우기
    
    Args:
        input_text (str): 사용자가 입력한 텍스트 데이터
        auto_fill (bool): 자동 채우기 사용 여부
        char_manager (CharacterManager): 캐릭터 매니저 인스턴스
        
    Returns:
        tuple: (is_valid, message, dataframe)
    """
    try:
        # 탭으로 구분된 데이터를 DataFrame으로 변환
        df = pd.read_csv(StringIO(input_text), sep='\t')
        
        # 컬럼명 정리 (공백 제거)
        df.columns = df.columns.str.strip()
        
        # 다양한 컬럼명 패턴 정의
        column_patterns = {
            '캐릭터': ['캐릭터', 'character', 'char', '이름', 'name', '화자', 'speaker'],
            '대사': ['대사', 'dialogue', 'dialog', 'text', '텍스트', '내용', 'content', 'line'],
            '포트레이트': ['포트레이트', 'portrait', '초상화', 'image', '이미지'],
            '사운드 주소': ['사운드 주소', 'sound address', 'sound_address', 'audio address', 'audio_address', '오디오 주소'],
            '사운드 파일명': ['사운드 파일명', 'sound file', 'sound_file', 'audio file', 'audio_file', '오디오 파일', 'filename']
        }
        
        # 자동 컬럼 매핑
        mapped_columns = {}
        for target_col, patterns in column_patterns.items():
            found = False
            for pattern in patterns:
                for actual_col in df.columns:
                    if pattern.lower() in actual_col.lower():
                        mapped_columns[target_col] = actual_col
                        found = True
                        break
                if found:
                    break
        
        # 필수 컬럼 확인
        required_columns = ['캐릭터', '대사']  # 최소 필요 컬럼
        missing_required = [col for col in required_columns if col not in mapped_columns]
        
        if missing_required:
            # 컬럼 정보를 상세히 제공
            available_columns = list(df.columns)
            return False, f"""필수 컬럼을 찾을 수 없습니다: {', '.join(missing_required)}

현재 시트의 컬럼: {', '.join(available_columns)}

예상 컬럼명:
- 캐릭터: character, char, 이름, name, 화자, speaker
- 대사: dialogue, dialog, text, 텍스트, 내용, content, line""", None
        
        # 컬럼명 변경
        df_renamed = df.copy()
        for target_col, actual_col in mapped_columns.items():
            if actual_col in df_renamed.columns:
                df_renamed = df_renamed.rename(columns={actual_col: target_col})
        
        # 누락된 선택적 컬럼 추가 (빈 값으로)
        optional_columns = ['포트레이트', '사운드 주소', '사운드 파일명']
        for col in optional_columns:
            if col not in df_renamed.columns:
                df_renamed[col] = ""
        
        # 빈 행 제거 (캐릭터와 대사가 모두 비어있는 행)
        df_renamed = df_renamed.dropna(subset=['캐릭터', '대사'])
        
        # 빈 값을 가진 행 필터링 (더 엄격한 검증)
        df_renamed = df_renamed[
            (df_renamed['캐릭터'].astype(str).str.strip() != '') & 
            (df_renamed['대사'].astype(str).str.strip() != '')
        ]
        
        if len(df_renamed) == 0:
            return False, "유효한 데이터가 없습니다. 캐릭터와 대사가 모두 입력된 행이 필요합니다.", None
        
        # 자동 채우기 기능
        if auto_fill and char_manager:
            portrait_sound_manager = PortraitSoundManager(char_manager)
            df_renamed = portrait_sound_manager.auto_fill_missing_fields(df_renamed)
        
        # 데이터 품질 검증
        quality_issues = []
        
        # 등록되지 않은 캐릭터 확인
        if char_manager:
            unregistered_chars = []
            for char in df_renamed['캐릭터'].unique():
                if not char_manager.get_character_by_kr(char) and not char_manager.get_character_by_name(char):
                    unregistered_chars.append(char)
            
            if unregistered_chars:
                quality_issues.append(f"등록되지 않은 캐릭터: {', '.join(unregistered_chars)}")
        
        # 너무 긴 대사 확인
        long_dialogues = df_renamed[df_renamed['대사'].astype(str).str.len() > 500]
        if len(long_dialogues) > 0:
            quality_issues.append(f"500자 이상의 긴 대사가 {len(long_dialogues)}개 있습니다.")
        
        # 품질 경고 메시지 구성
        success_message = f"데이터가 유효합니다. 매핑된 컬럼: {', '.join(mapped_columns.keys())}"
        if quality_issues:
            success_message += f"\n\n주의사항:\n- " + "\n- ".join(quality_issues)
            
        return True, success_message, df_renamed
        
    except Exception as e:
        return False, f"데이터 파싱 오류: {str(e)}", None

def get_character_code(character_name, char_manager=None):
    """
    캐릭터 이름을 영문 코드로 변환 (개선된 버전)
    
    Args:
        character_name (str): 한글 캐릭터 이름
        char_manager (CharacterManager): 캐릭터 매니저 인스턴스
        
    Returns:
        str: 영문 소문자 캐릭터 코드
    """
    if char_manager:
        # 한글 이름으로 먼저 검색
        char_data = char_manager.get_character_by_kr(character_name)
        if char_data:
            return char_data['string_id']
        
        # 영문 이름으로도 검색
        char_data = char_manager.get_character_by_name(character_name)
        if char_data:
            return char_data['string_id']
    
    # 매핑이 없으면 자동 변환 시도
    # 한글 제거, 공백 제거 후 소문자로 변환
    converted = re.sub(r'[^a-zA-Z0-9_]', '', character_name).lower()
    
    # 빈 문자열인 경우 기본값 반환
    if not converted:
        # 캐릭터 이름의 첫 글자를 기반으로 생성 시도
        first_char = character_name[0] if character_name else 'unknown'
        if ord(first_char) >= ord('가') and ord(first_char) <= ord('힣'):
            # 한글인 경우 'char' + 유니코드 번호 사용
            converted = f"char_{ord(first_char)}"
        else:
            converted = 'unknown'
    
    return converted

def extract_dialogue_id(sound_filename, row_index):
    """
    사운드 파일명에서 대사 ID 생성 (개선된 버전)
    
    Args:
        sound_filename (str): 사운드 파일명
        row_index (int): 현재 행의 인덱스
        
    Returns:
        str: 대사 ID (예: cs_15031309_001)
    """
    if pd.isna(sound_filename) or not sound_filename:
        return f"cs_unknown_{row_index+1:03d}"
    
    # 파일명에서 숫자 부분 추출 (더 정확한 패턴)
    # 8자리 이상의 숫자를 우선 찾기 (스토리 ID 패턴)
    long_number_match = re.search(r'(\d{8,})', str(sound_filename))
    if long_number_match:
        base_number = long_number_match.group(1)
    else:
        # 일반적인 숫자 패턴 찾기
        match = re.search(r'(\d+)', str(sound_filename))
        if match:
            base_number = match.group(1)
        else:
            base_number = "unknown"
    
    # 순서 번호 생성 (3자리)
    sequence = f"{row_index+1:03d}"
    return f"cs_{base_number}_{sequence}"

def clean_dialogue_text(dialogue_text):
    """
    대사 텍스트 정리 (개선된 버전)
    
    Args:
        dialogue_text (str): 원본 대사 텍스트
        
    Returns:
        str: 정리된 대사 텍스트
    """
    if pd.isna(dialogue_text):
        return ""
    
    # 문자열로 변환
    cleaned = str(dialogue_text)
    
    # 줄바꿈을 공백으로 변환
    cleaned = cleaned.replace('\n', ' ').replace('\r', ' ')
    
    # 탭 문자 제거
    cleaned = cleaned.replace('\t', ' ')
    
    # 연속된 공백을 단일 공백으로 변환
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # 양쪽 공백 제거
    cleaned = cleaned.strip()
    
    # 특수 문자 처리 (스크립트에서 문제가 될 수 있는 문자들)
    # 따옴표 문제 방지
    cleaned = cleaned.replace('"', '\\"')
    
    return cleaned

def convert_single_row(row, row_index, char_manager=None):
    """
    단일 행을 대사 형식으로 변환 (오류 처리 개선)
    
    Args:
        row (pandas.Series): DataFrame의 한 행
        row_index (int): 행 인덱스
        char_manager (CharacterManager): 캐릭터 매니저 인스턴스
        
    Returns:
        str: 변환된 대사 문자열
    """
    try:
        # 각 필드 추출 및 안전한 처리
        character = str(row.get('캐릭터', '')).strip()
        dialogue = str(row.get('대사', '')).strip()
        portrait = str(row.get('포트레이트', '')).strip()
        sound_address = str(row.get('사운드 주소', '')).strip()
        sound_filename = str(row.get('사운드 파일명', '')).strip()
        
        # 필수 데이터 검증
        if not character or not dialogue:
            return f"# 오류: 캐릭터 또는 대사가 비어있음 (행 {row_index+1})"
        
        # 캐릭터 코드 변환
        character_code = get_character_code(character, char_manager)
        
        # 캐릭터가 등록되지 않은 경우 경고 추가
        warning_comment = ""
        if char_manager:
            if not char_manager.get_character_by_kr(character) and not char_manager.get_character_by_name(character):
                warning_comment = f" # 경고: '{character}' 미등록 캐릭터"
        
        # 대사 ID 생성
        dialogue_id = extract_dialogue_id(sound_filename, row_index)
        
        # 대사 텍스트 정리
        clean_dialogue = clean_dialogue_text(dialogue)
        
        # 빈 값 처리 (NaN이나 'nan' 문자열 체크)
        if portrait == 'nan' or portrait == '':
            portrait = ""
        if sound_address == 'nan' or sound_address == '':
            sound_address = ""
        
        # 최종 문자열 조합
        result = f'스토리_대화상자_추가("[@{character_code}]","[@{dialogue_id}]","{portrait}","{sound_address}")#{clean_dialogue}대기(){warning_comment}'
        
        return result
        
    except Exception as e:
        return f"# 오류 발생 (행 {row_index+1}): {str(e)}"

def convert_dialogue_data(df, char_manager=None, progress_callback=None):
    """
    전체 DataFrame을 대사 형식으로 변환 (진행률 콜백 추가)
    
    Args:
        df (pandas.DataFrame): 입력 데이터프레임
        char_manager (CharacterManager): 캐릭터 매니저 인스턴스
        progress_callback (function): 진행률 콜백 함수 (선택사항)
        
    Returns:
        list: 변환된 대사 문자열 리스트
    """
    results = []
    total_rows = len(df)
    
    for index, row in df.iterrows():
        converted_line = convert_single_row(row, index, char_manager)
        results.append(converted_line)
        
        # 진행률 콜백 호출
        if progress_callback:
            progress = (index + 1) / total_rows
            progress_callback(progress)
    
    return results

def get_conversion_preview(df, char_manager=None, max_rows=3):
    """
    변환 결과 미리보기 생성
    
    Args:
        df (pandas.DataFrame): 입력 데이터프레임
        char_manager (CharacterManager): 캐릭터 매니저 인스턴스
        max_rows (int): 미리보기할 최대 행 수
        
    Returns:
        list: 미리보기 결과 리스트
    """
    preview_df = df.head(max_rows)
    return convert_dialogue_data(preview_df, char_manager)

def validate_conversion_result(results):
    """
    변환 결과의 품질 검증 (신규 기능)
    
    Args:
        results (list): 변환 결과 리스트
        
    Returns:
        dict: 검증 결과 통계
    """
    stats = {
        'total_lines': len(results),
        'error_lines': 0,
        'warning_lines': 0,
        'success_lines': 0,
        'errors': [],
        'warnings': []
    }
    
    for i, line in enumerate(results):
        if line.startswith('# 오류'):
            stats['error_lines'] += 1
            stats['errors'].append(f"행 {i+1}: {line}")
        elif '# 경고' in line:
            stats['warning_lines'] += 1
            stats['warnings'].append(f"행 {i+1}: 미등록 캐릭터")
        else:
            stats['success_lines'] += 1
    
    return stats

def format_conversion_summary(stats):
    """
    변환 결과 요약 포맷팅 (신규 기능)
    
    Args:
        stats (dict): 검증 결과 통계
        
    Returns:
        str: 포맷팅된 요약 문자열
    """
    summary = f"""변환 완료: {stats['total_lines']}개 행
✅ 성공: {stats['success_lines']}개
⚠️ 경고: {stats['warning_lines']}개
❌ 오류: {stats['error_lines']}개"""
    
    if stats['errors']:
        summary += f"\n\n오류 목록:\n" + "\n".join(stats['errors'][:5])
        if len(stats['errors']) > 5:
            summary += f"\n... 외 {len(stats['errors']) - 5}개"
    
    if stats['warnings']:
        summary += f"\n\n경고 목록:\n" + "\n".join(stats['warnings'][:5])
        if len(stats['warnings']) > 5:
            summary += f"\n... 외 {len(stats['warnings']) - 5}개"
    
    return summary