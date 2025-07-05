import re
import pandas as pd

class PortraitSoundManager:
    """
    포트레이트와 사운드 주소 생성 관리 클래스 (v2.1)
    """
    def __init__(self, character_manager=None, expression_map=None):
        """[수정] expression_map을 외부(SettingsManager)에서 주입받습니다."""
        self.character_manager = character_manager
        # 외부에서 받은 감정 표현 맵 사용, 없으면 기본값
        self.expression_map = expression_map if expression_map is not None else {
            "화남": "Angry", "슬픔": "Sad", "기쁨": "Happy", "고통": "Pain", "부끄": "Shy"
        }

    def generate_portrait_path(self, character_name, expression):
        """
        [수정] 캐릭터별 커스텀 포트레이트 경로 설정을 우선 적용합니다.
        """
        if not character_name: return ""

        char_data = self.character_manager.get_character_by_name(character_name) or self.character_manager.get_character_by_kr(character_name)
        if not char_data: return "" # 등록된 캐릭터가 없으면 빈 값 반환

        custom_path = char_data.get('portrait_path')
        expression_eng = self.expression_map.get(expression, "Default")

        # 1. 커스텀 경로가 ""로 설정된 경우 (의도적으로 비우기)
        if custom_path == "":
            return ""
        
        # 2. 커스텀 경로가 설정된 경우 (예: "avin/avin_")
        if custom_path:
            return f"{custom_path}{expression_eng}.rux"
        
        # 3. 커스텀 경로가 설정되지 않은 경우 (기존 자동 생성 방식)
        char_eng_name = char_data.get('string_id', character_name.capitalize())
        return f"{char_eng_name}/{char_eng_name}_{expression_eng}.rux"

    def generate_sound_path(self, sound_address, sound_file):
        # [함수명: generate_sound_path]: 변경 없음
        if pd.isna(sound_address) or pd.isna(sound_file) or not sound_address or not sound_file: return ""
        return str(sound_address) + str(sound_file)