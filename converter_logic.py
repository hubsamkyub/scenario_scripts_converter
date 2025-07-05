import pandas as pd
import re
from io import StringIO
from portrait_sound_manager import PortraitSoundManager

# 캐릭터 매핑은 CharacterManager에서 동적으로 관리됩니다.

def validate_data(input_text, auto_fill=True, char_manager=None):
    """
    입력 데이터 검증 및 자동 채우기
    """
    try:
        # 탭으로 구분된 데이터를 DataFrame으로 변환
        df = pd.read_csv(StringIO(input_text), sep='\t')
        df.columns = df.columns.str.strip()
        
        column_patterns = {
            '캐릭터': ['캐릭터', 'character', 'char', '이름', 'name', '화자', 'speaker'],
            '대사': ['대사', 'dialogue', 'dialog', 'text', '텍스트', '내용', 'content', 'line'],
            '포트레이트': ['포트레이트', 'portrait', '초상화', 'image', '이미지'],
            '사운드 주소': ['사운드 주소', 'sound address', 'sound_address', 'audio address', 'audio_address', '오디오 주소'],
            '사운드 파일명': ['사운드 파일명', 'sound file', 'sound_file', 'audio file', 'audio_file', '오디오 파일', 'filename']
        }
        
        mapped_columns = {}
        for target_col, patterns in column_patterns.items():
            for pattern in patterns:
                for actual_col in df.columns:
                    if pattern.lower() in actual_col.lower():
                        mapped_columns[target_col] = actual_col
                        break
                if target_col in mapped_columns:
                    break
        
        required_columns = ['캐릭터', '대사']
        missing_required = [col for col in required_columns if col not in mapped_columns]
        
        if missing_required:
            available_columns = list(df.columns)
            return False, f"필수 컬럼({', '.join(missing_required)})을 찾을 수 없습니다. 현재 컬럼: {', '.join(available_columns)}", None
        
        df_renamed = df.copy()
        for target_col, actual_col in mapped_columns.items():
            if actual_col in df_renamed.columns:
                df_renamed = df_renamed.rename(columns={actual_col: target_col})

        for col in column_patterns.keys():
            if col not in df_renamed.columns:
                df_renamed[col] = ""
        
        # NA 값들을 빈 문자열로 일괄 변환
        for col in df_renamed.columns:
            df_renamed[col] = df_renamed[col].fillna('')

        df_renamed = df_renamed.dropna(subset=['캐릭터', '대사'], how='all')
        df_renamed = df_renamed[
            (df_renamed['캐릭터'].astype(str).str.strip() != '') & 
            (df_renamed['대사'].astype(str).str.strip() != '')
        ]

        if len(df_renamed) == 0:
            return False, "유효한 데이터가 없습니다. 캐릭터와 대사가 모두 입력된 행이 필요합니다.", None

        if auto_fill and char_manager:
            portrait_sound_manager = PortraitSoundManager(char_manager)
            df_renamed = portrait_sound_manager.auto_fill_missing_fields(df_renamed)

        return True, f"데이터가 유효합니다. 매핑된 컬럼: {', '.join(mapped_columns.keys())}", df_renamed
        
    except Exception as e:
        return False, f"데이터 파싱 오류: {str(e)}", None


def get_character_code(character_name, char_manager=None):
    if char_manager:
        char_data = char_manager.get_character_by_kr(character_name) or char_manager.get_character_by_name(character_name)
        if char_data:
            return char_data['string_id']
    
    return re.sub(r'[^a-zA-Z0-9_]', '', character_name).lower() or 'unknown'

def extract_dialogue_id(sound_filename, row_index):
    if pd.isna(sound_filename) or not sound_filename:
        return f"cs_unknown_{row_index+1:03d}"
    
    match = re.search(r'(\d{8,})', str(sound_filename)) or re.search(r'(\d+)', str(sound_filename))
    base_number = match.group(1) if match else "unknown"
    return f"cs_{base_number}_{row_index+1:03d}"

def clean_dialogue_text(dialogue_text):
    if pd.isna(dialogue_text):
        return ""
    cleaned = str(dialogue_text).replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = cleaned.replace('"', '\\"')
    return cleaned


def convert_single_row(row, row_index, char_manager=None):
    """
    단일 행을 대사 형식으로 변환.
    성공, 오류, 경고를 담은 딕셔너리를 반환합니다.
    """
    result = {
        "status": "error",
        "message": "",
        "warning": ""
    }
    try:
        character = str(row.get('캐릭터', '')).strip()
        dialogue = str(row.get('대사', '')).strip()
        
        if not character or not dialogue:
            result["message"] = f"# 오류: 행 {row_index+1}의 캐릭터 또는 대사가 비어있습니다."
            return result

        portrait = str(row.get('포트레이트', '')).strip()
        sound_address = str(row.get('사운드 주소', '')).strip()
        sound_filename = str(row.get('사운드 파일명', '')).strip()

        character_code = get_character_code(character, char_manager)
        
        if char_manager and not (char_manager.get_character_by_kr(character) or char_manager.get_character_by_name(character)):
            result["warning"] = f"'{character}'는 등록되지 않은 캐릭터입니다."

        dialogue_id = extract_dialogue_id(sound_filename, row_index)
        clean_dialogue = clean_dialogue_text(dialogue)
        
        # nan 문자열 체크
        portrait = "" if portrait.lower() == 'nan' else portrait
        sound_address = "" if sound_address.lower() == 'nan' else sound_address
        
        result["status"] = "success"
        result["message"] = f'스토리_대화상자_추가("[@{character_code}]","[@{dialogue_id}]","{portrait}","{sound_address}")#{clean_dialogue}대기()'
        return result

    except Exception as e:
        result["message"] = f"# 오류 발생 (행 {row_index+1}): {str(e)}"
        return result


def convert_dialogue_data(df, char_manager=None, progress_callback=None):
    results = []
    total_rows = len(df)
    for index, row in df.iterrows():
        converted_result = convert_single_row(row, index, char_manager)
        results.append(converted_result)
        if progress_callback:
            progress = (index + 1) / total_rows
            progress_callback(progress)
    return results


def validate_conversion_result(results):
    stats = {
        'total_lines': len(results),
        'error_lines': 0,
        'warning_lines': 0,
        'success_lines': 0,
        'errors': [],
        'warnings': []
    }
    for i, line in enumerate(results):
        if isinstance(line, str) and line.startswith('# 오류'):
            stats['error_lines'] += 1
            stats['errors'].append(f"행 {i+1}: {line}")
        elif isinstance(line, str) and '# 경고' in line:
            stats['warning_lines'] += 1
            stats['warnings'].append(f"행 {i+1}: 미등록 캐릭터 경고") # Simplified
        else:
            stats['success_lines'] += 1
    return stats


def format_conversion_summary(stats):
    return f"""
    총 {stats['total_lines']}개 행 변환: 
    ✅ 성공: {stats['success_lines']}개, 
    ❌ 오류: {stats['error_lines']}개
    """