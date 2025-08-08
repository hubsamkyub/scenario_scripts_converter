import pandas as pd
import re
from portrait_sound_manager import PortraitSoundManager

class ConverterLogic:
    """
    지시문별 규칙과 상세 리포팅을 처리하는 클래스 (v2.4)
    """
    def __init__(self, character_manager, portrait_sound_manager, settings_manager):
        # [함수명: __init__]: "자막" 규칙 제거
        self.character_manager = character_manager
        self.ps_manager = portrait_sound_manager
        self.settings_manager = settings_manager
        self.builtin_rules = {"대사": self._convert_dialogue}

    def _apply_template(self, template, row):
        """[수정] {{컬럼명}} 형태의 placeholder를 인식하고, #{{컬럼명}} 패턴에 자동 개행 처리 적용"""
        # 1. #{{컬럼명}} 패턴 찾기 (개행 처리 적용용)
        comment_placeholders = re.findall(r'#\{\{(.+?)\}\}', template)
        
        # 2. 일반 {{컬럼명}} 패턴 찾기
        placeholders = re.findall(r'\{\{(.+?)\}\}', template)
        result = template
        
        # 3. #{{컬럼명}} 패턴 먼저 처리 (개행 처리 적용)
        for ph in comment_placeholders:
            raw_value = row.get(ph.strip().lower(), f'{{{{{ph}}}}}')
            if raw_value != f'{{{{{ph}}}}}':  # 값이 존재하는 경우만 개행 처리
                cleaned_value = self._clean_dialogue_text(raw_value)
                result = result.replace(f'#{{{{{ph}}}}}', f'#{cleaned_value}')
        
        # 4. 나머지 일반 {{컬럼명}} 패턴 처리
        for ph in placeholders:
            # #{{컬럼명}}은 이미 처리했으므로 건너뛰기
            if f'#{{{{{ph}}}}}' not in template or f'#{{{{{ph}}}}}' not in result:
                value = row.get(ph.strip().lower(), f'{{{{{ph}}}}}')
                result = result.replace(f'{{{{{ph}}}}}', str(value))
        
        # 5. \n을 실제 개행으로 변환
        result = result.replace('\\n', '\n')
        return result


    def _clean_dialogue_text(self, text):
        if not isinstance(text, str): return ""
        return text.replace('\n', '\\n').replace('\r', '')

    def _generate_fallback_string_id(self, row):
        sound_file = row.get('사운드 파일', '')
        if sound_file and isinstance(sound_file, str): return f"cs_{sound_file}"
        return ""
    
    def _convert_dialogue(self, row):
        """
        [수정] 대사 텍스트를 _clean_dialogue_text 함수로 처리합니다.
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

        # 2. STRING_ID 검증 및 자동 생성
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

        # 5. 최종 3줄 텍스트 조합 (대사 클리닝 적용)
        line1 = f'스토리_대화상자_추가("[@{char_string_id}]","[@{dialogue_string_id}]","{portrait_path}","{sound_path}")'
        line2 = f'#{self._clean_dialogue_text(row.get("대사", ""))}' # 수정된 부분
        line3 = '대기()'
        result_text = f"{line1}\n{line2}\n{line3}"
        status = "warning" if messages else "success"
        message_text = " | ".join(messages) if messages else "성공"
        return {"status": status, "result": result_text, "message": message_text}

    def _convert_default(self, row):
        dialogue_text = self._clean_dialogue_text(row.get("대사", ""))
        return {"status": "success", "result": f"#{dialogue_text}", "message": "기본 주석 처리"}


    def convert_scene_data(self, scene_df):
        """[수정] 사용자 정의 지시문 규칙 적용 로직을 _apply_template으로 일원화합니다."""
        results = []
        custom_directives = self.settings_manager.get_directive_rules()
        for index, row in scene_df.iterrows():
            directive = row.get("지시문", "")
            directive = directive.strip() if isinstance(directive, str) else ""
            
            result_dict = None
            if directive in custom_directives:
                rule = custom_directives[directive]
                result_text = self._apply_template(rule['template'], row)
                result_dict = {"status": "success", "result": result_text, "message": f"사용자 정의 규칙 '{directive}' 적용"}
            elif directive in self.builtin_rules:
                convert_function = self.builtin_rules[directive]
                result_dict = convert_function(row)
            else:
                result_dict = self._convert_default(row)
            
            results.append(result_dict)
        return results