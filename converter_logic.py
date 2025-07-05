import pandas as pd
from portrait_sound_manager import PortraitSoundManager

class ConverterLogic:
    """
    지시문별 규칙과 상세 리포팅을 처리하는 클래스 (v2.3)
    """
    def __init__(self, character_manager, portrait_sound_manager):
        self.character_manager = character_manager
        self.ps_manager = portrait_sound_manager
        self.directive_rules = {
            "대사": self._convert_dialogue,
            "자막": self._convert_subtitle,
            "카메라": lambda row: {"status": "success", "result": "카메라_이동_옵셋()", "message": "성공"},
            "조명": lambda row: {"status": "success", "result": "뷰포트_필터_블랙()", "message": "성공"},
        }

    def _generate_fallback_string_id(self, row):
        # [수정] 소문자 컬럼명 사용
        sound_file = row.get('사운드 파일', '')
        if sound_file and isinstance(sound_file, str):
            return f"cs_{sound_file}"
        return ""

    def _convert_dialogue(self, row):
        """
        [수정] '대사' 지시문 변환 시 소문자 컬럼명을 사용합니다.
        """
        messages = []
        # 1. 캐릭터 검증
        char_name = row.get("캐릭터", "")
        if not char_name:
            return {"status": "error", "result": "# [오류] '캐릭터' 정보가 비어있습니다.", "message": "필수값 '캐릭터' 없음"}
        char_data = self.character_manager.get_character_by_kr(char_name) or self.character_manager.get_character_by_name(char_name)
        if not char_data:
            return {"status": "error", "result": f"# [오류] 등록되지 않은 캐릭터: {char_name}", "message": f"미등록 캐릭터: {char_name}"}
        char_string_id = char_data.get('string_id', 'unknown')

        # 2. STRING_ID 검증 및 자동 생성 (소문자 키 사용)
        dialogue_string_id = row.get('string_id', '')
        if not dialogue_string_id or (isinstance(dialogue_string_id, str) and dialogue_string_id.strip() == ''):
            dialogue_string_id = self._generate_fallback_string_id(row)
            if not dialogue_string_id:
                 return {"status": "error", "result": "# [오류] STRING_ID가 비어있고, ID 생성에 필요한 '사운드 파일'도 없습니다.", "message": "ID 생성 불가"}
            messages.append("경고: 'STRING_ID'가 비어있어 '사운드 파일' 기준으로 자동 생성했습니다.")

        # 3. 포트레이트 경로 생성
        expression = row.get('표정', '')
        portrait_path = self.ps_manager.generate_portrait_path(char_name, expression)

        # 4. 사운드 경로 생성
        sound_address = row.get('사운드 주소', '')
        sound_file = row.get('사운드 파일', '')
        sound_path = self.ps_manager.generate_sound_path(sound_address, sound_file)

        # 5. 최종 3줄 텍스트 조합
        line1 = f'스토리_대화상자_추가("[@{char_string_id}]","[@{dialogue_string_id}]","{portrait_path}","{sound_path}")'
        line2 = f'#{row.get("대사", "")}'
        line3 = '대기()'
        result_text = f"{line1}\n{line2}\n{line3}"
        status = "warning" if messages else "success"
        message_text = " | ".join(messages) if messages else "성공"
        return {"status": status, "result": result_text, "message": message_text}

    def _convert_subtitle(self, row):
        """
        [수정] '자막' 지시문 변환 시 소문자 컬럼명을 사용합니다.
        """
        messages = []
        # 1. 자막 STRING_ID 검증 및 자동 생성 (소문자 키 사용)
        subtitle_string_id = row.get('string_id', '')
        if not subtitle_string_id or (isinstance(subtitle_string_id, str) and subtitle_string_id.strip() == ''):
            subtitle_string_id = self._generate_fallback_string_id(row)
            if not subtitle_string_id:
                return {"status": "error", "result": "# [오류] STRING_ID가 비어있고, ID 생성에 필요한 '사운드 파일'도 없습니다.", "message": "ID 생성 불가"}
            messages.append("경고: 'STRING_ID'가 비어있어 '사운드 파일' 기준으로 자동 생성했습니다.")
        
        # 2. 사운드 경로 생성
        sound_address = row.get('사운드 주소', '')
        sound_file = row.get('사운드 파일', '')
        sound_path = self.ps_manager.generate_sound_path(sound_address, sound_file)

        # 3. 최종 3줄 텍스트 조합
        line1 = f'나레이션_텍스트("[@{subtitle_string_id}]","","","","{sound_path}")'
        line2 = f'#{row.get("대사", "")}'
        line3 = '지연(0)'
        result_text = f"{line1}\n{line2}\n{line3}"
        status = "warning" if messages else "success"
        message_text = " | ".join(messages) if messages else "성공"
        return {"status": status, "result": result_text, "message": message_text}

    def _convert_default(self, row):
        """
        [함수명: _convert_default]: 변경 없음
        """
        dialogue_text = row.get("대사", "")
        return {"status": "success", "result": f"#{dialogue_text}", "message": "기본 주석 처리"}

    def convert_scene_data(self, scene_df):
        """
        [수정] 소문자 컬럼명을 사용하여 변환을 수행합니다.
        """
        results = []
        for index, row in scene_df.iterrows():
            directive = row.get("지시문", "") # 이미 소문자로 변환되어 있음
            directive = directive.strip() if isinstance(directive, str) else ""
            convert_function = self.directive_rules.get(directive, self._convert_default)
            result_dict = convert_function(row)
            results.append(result_dict)
        return results