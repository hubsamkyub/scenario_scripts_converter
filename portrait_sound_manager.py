import re
import pandas as pd

class PortraitSoundManager:
    """
    포트레이트와 사운드 주소 생성 관리 클래스 (v2)
    """

    def __init__(self, character_manager=None):
        """
        [함수명: __init__]: 변경 없음
        """
        self.character_manager = character_manager
        # 표정 한글 -> 영문 매핑 (향후 사용자 설정으로 관리 가능)
        self.expression_map = {
            "화남": "Angry",
            "슬픔": "Sad",
            "기쁨": "Happy",
            "고통": "Pain",
            "부끄": "Shy"
        }

    def generate_portrait_path(self, character_name, expression):
        """
        [수정] 포트레이트 경로를 '표정' 값을 기반으로 자동 생성합니다.
        """
        if not character_name:
            return ""

        char_data = self.character_manager.get_character_by_name(character_name)
        if not char_data:
            char_data = self.character_manager.get_character_by_kr(character_name)
        
        # 캐릭터의 영문 이름(string_id)을 경로에 사용
        char_eng_name = char_data['string_id'] if char_data else character_name.capitalize()
        
        # 표정 값을 영문으로 변환, 없으면 Default 사용
        expression_eng = self.expression_map.get(expression, "Default")

        return f"{char_eng_name}/{char_eng_name}_{expression_eng}.rux"

    def generate_sound_path(self, sound_address, sound_file):
        """
        [신규] 사운드 주소와 파일명을 합쳐 최종 사운드 경로를 생성합니다.
        """
        if pd.isna(sound_address) or pd.isna(sound_file) or not sound_address or not sound_file:
            return ""
        # 두 값이 모두 있을 경우에만 합침
        return str(sound_address) + str(sound_file)