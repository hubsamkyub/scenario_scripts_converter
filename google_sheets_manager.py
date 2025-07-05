import re
import pandas as pd

class PortraitSoundManager:
    """
    포트레이트와 사운드 주소 자동 생성 관리 클래스
    """
    
    def __init__(self, character_manager=None):
        """
        초기화
        
        Args:
            character_manager: CharacterManager 인스턴스
        """
        self.character_manager = character_manager
    
    def generate_portrait_path(self, character_name, sound_filename=None):
        """
        포트레이트 경로 자동 생성
        기존 함수: vlookup 결과를 "{Name}/{Name}_Default.rux" 형태로 조합
        
        Args:
            character_name (str): 캐릭터 이름 (한글 또는 영문)
            sound_filename (str, optional): 사운드 파일명 (참고용)
            
        Returns:
            str: 생성된 포트레이트 경로
        """
        if not character_name:
            return ""
        
        # 캐릭터 매니저에서 Name 필드 찾기
        char_data = None
        if self.character_manager:
            # 한글 이름으로 검색
            char_data = self.character_manager.get_character_by_kr(character_name)
            if not char_data:
                # 영문 이름으로 검색
                char_data = self.character_manager.get_character_by_name(character_name)
        
        if char_data and char_data.get('name'):
            # Name 필드가 있으면 사용
            name = char_data['name']
            return f"{name}/{name}_Default.rux"
        else:
            # Name 필드가 없으면 캐릭터 이름에서 생성
            # 한글이면 영문으로 변환 시도, 영문이면 첫글자 대문자로
            if self._is_korean(character_name):
                # 한글인 경우 string_id를 Name으로 사용
                if char_data and char_data.get('string_id'):
                    name = char_data['string_id'].title()
                else:
                    # 매핑이 없으면 기본값
                    name = "Unknown"
            else:
                # 영문인 경우 첫글자 대문자로
                name = character_name.title()
            
            return f"{name}/{name}_Default.rux"
    
    def generate_sound_address(self, sound_filename):
        """
        사운드 주소 자동 생성
        기존 함수: "event:/Story/"&left(J3,find("_",J3,1)-1)&"/"&J3
        
        Args:
            sound_filename (str): 사운드 파일명
            
        Returns:
            str: 생성된 사운드 주소
        """
        if not sound_filename:
            return ""
        
        try:
            # 첫 번째 "_" 위치 찾기
            first_underscore_pos = sound_filename.find("_")
            
            if first_underscore_pos == -1:
                # "_"가 없으면 빈 문자열
                return ""
            
            # 첫 번째 "_" 앞부분 추출 (스토리 ID)
            story_id = sound_filename[:first_underscore_pos]
            
            # "event:/Story/{스토리ID}/{전체파일명}" 형태로 조합
            return f"event:/Story/{story_id}/{sound_filename}"
            
        except Exception:
            return ""
    
    def extract_story_id_from_sound_filename(self, sound_filename):
        """
        사운드 파일명에서 스토리 ID 추출
        
        Args:
            sound_filename (str): 사운드 파일명
            
        Returns:
            str: 추출된 스토리 ID
        """
        if not sound_filename:
            return ""
        
        first_underscore_pos = sound_filename.find("_")
        if first_underscore_pos == -1:
            return ""
        
        return sound_filename[:first_underscore_pos]
    
    def extract_character_from_sound_filename(self, sound_filename):
        """
        사운드 파일명에서 캐릭터명 추출
        
        Args:
            sound_filename (str): 사운드 파일명 (예: "15031309_Shao_01")
            
        Returns:
            str: 추출된 캐릭터명 (예: "Shao")
        """
        if not sound_filename:
            return ""
        
        try:
            # "_"로 분할해서 두 번째 부분이 캐릭터명
            parts = sound_filename.split("_")
            if len(parts) >= 2:
                return parts[1]
            return ""
        except Exception:
            return ""
    
    def extract_sequence_from_sound_filename(self, sound_filename):
        """
        사운드 파일명에서 순서번호 추출
        
        Args:
            sound_filename (str): 사운드 파일명 (예: "15031309_Shao_01")
            
        Returns:
            str: 추출된 순서번호 (예: "01")
        """
        if not sound_filename:
            return ""
        
        try:
            # "_"로 분할해서 마지막 부분이 순서번호
            parts = sound_filename.split("_")
            if len(parts) >= 3:
                return parts[-1]
            return ""
        except Exception:
            return ""
    
    def generate_sound_filename(self, story_id, character_name, sequence):
        """
        사운드 파일명 자동 생성
        
        Args:
            story_id (str): 스토리 ID (예: "15031309")
            character_name (str): 캐릭터 이름
            sequence (str or int): 순서번호
            
        Returns:
            str: 생성된 사운드 파일명
        """
        if not all([story_id, character_name]):
            return ""
        
        # 캐릭터 매니저에서 Name 찾기
        char_data = None
        if self.character_manager:
            char_data = self.character_manager.get_character_by_kr(character_name)
            if not char_data:
                char_data = self.character_manager.get_character_by_name(character_name)
        
        if char_data and char_data.get('name'):
            char_name = char_data['name']
        else:
            char_name = character_name
        
        # 순서번호를 2자리 문자열로 변환
        if isinstance(sequence, int):
            seq_str = f"{sequence:02d}"
        else:
            seq_str = str(sequence).zfill(2)
        
        return f"{story_id}_{char_name}_{seq_str}"
    
    def validate_sound_filename_pattern(self, sound_filename):
        """
        사운드 파일명 패턴 검증
        
        Args:
            sound_filename (str): 검증할 사운드 파일명
            
        Returns:
            tuple: (is_valid, message)
        """
        if not sound_filename:
            return False, "사운드 파일명이 비어있습니다."
        
        # 기본 패턴: 숫자_문자_숫자
        pattern = r'^\d+_[a-zA-Z]+_\d+$'
        
        if not re.match(pattern, sound_filename):
            return False, f"잘못된 파일명 패턴: '{sound_filename}' (올바른 형태: '스토리ID_캐릭터명_순서')"
        
        parts = sound_filename.split("_")
        if len(parts) != 3:
            return False, f"파일명은 정확히 2개의 '_'로 구분되어야 합니다: '{sound_filename}'"
        
        story_id, character, sequence = parts
        
        # 스토리 ID 검증 (숫자)
        if not story_id.isdigit():
            return False, f"스토리 ID는 숫자여야 합니다: '{story_id}'"
        
        # 캐릭터명 검증 (영문자)
        if not character.isalpha():
            return False, f"캐릭터명은 영문자여야 합니다: '{character}'"
        
        # 순서번호 검증 (숫자)
        if not sequence.isdigit():
            return False, f"순서번호는 숫자여야 합니다: '{sequence}'"
        
        return True, "유효한 사운드 파일명입니다."
    
    def _is_korean(self, text):
        """
        텍스트에 한글이 포함되어 있는지 확인
        
        Args:
            text (str): 확인할 텍스트
            
        Returns:
            bool: 한글 포함 여부
        """
        korean_pattern = re.compile(r'[가-힣]')
        return bool(korean_pattern.search(text))
    
    def auto_fill_missing_fields(self, df):
        """
        DataFrame에서 누락된 포트레이트, 사운드 주소 자동 채우기
        
        Args:
            df (pandas.DataFrame): 입력 데이터프레임
            
        Returns:
            pandas.DataFrame: 자동 채움 처리된 데이터프레임
        """
        df_filled = df.copy()
        
        for index, row in df_filled.iterrows():
            character = row.get('캐릭터', '')
            sound_filename = row.get('사운드 파일명', '')
            
            # 포트레이트가 비어있으면 자동 생성
            if pd.isna(row.get('포트레이트')) or not str(row.get('포트레이트')).strip():
                auto_portrait = self.generate_portrait_path(character, sound_filename)
                df_filled.at[index, '포트레이트'] = auto_portrait
            
            # 사운드 주소가 비어있으면 자동 생성
            if pd.isna(row.get('사운드 주소')) or not str(row.get('사운드 주소')).strip():
                auto_sound_address = self.generate_sound_address(sound_filename)
                df_filled.at[index, '사운드 주소'] = auto_sound_address
        
        return df_filled
    
    def get_auto_generation_preview(self, character_name, sound_filename):
        """
        자동 생성 결과 미리보기
        
        Args:
            character_name (str): 캐릭터 이름
            sound_filename (str): 사운드 파일명
            
        Returns:
            dict: 생성 결과 딕셔너리
        """
        return {
            'portrait': self.generate_portrait_path(character_name, sound_filename),
            'sound_address': self.generate_sound_address(sound_filename),
            'story_id': self.extract_story_id_from_sound_filename(sound_filename),
            'character_from_filename': self.extract_character_from_sound_filename(sound_filename),
            'sequence': self.extract_sequence_from_sound_filename(sound_filename)
        }