import pandas as pd
import re
from io import StringIO
import json
import os

class CharacterManager:
    def __init__(self, character_file="characters.json"):
        """
        캐릭터 관리 클래스
        
        Args:
            character_file (str): 캐릭터 데이터를 저장할 JSON 파일 경로
        """
        self.character_file = character_file
        self.characters = self.load_characters()
    
    def load_characters(self):
        """
        저장된 캐릭터 데이터 로드
        
        Returns:
            dict: 캐릭터 데이터 딕셔너리
        """
        if os.path.exists(self.character_file):
            try:
                with open(self.character_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_characters(self):
        """
        캐릭터 데이터를 파일에 저장
        """
        with open(self.character_file, 'w', encoding='utf-8') as f:
            json.dump(self.characters, f, ensure_ascii=False, indent=2)
    
    def generate_string_id(self, name):
        """
        Name에서 String_ID 자동 생성
        
        Args:
            name (str): 영문 이름
            
        Returns:
            str: 생성된 String_ID
        """
        # 영문자와 숫자만 남기고 소문자로 변환
        string_id = re.sub(r'[^a-zA-Z0-9_]', '', name).lower()
        
        # 공백은 언더스코어로 변환
        string_id = re.sub(r'\s+', '_', string_id)
        
        return string_id
    
    def generate_converter_name(self, string_id):
        """
        String_ID에서 Converter_Name 자동 생성
        
        Args:
            string_id (str): String_ID
            
        Returns:
            str: 생성된 Converter_Name ([@string_id] 형태)
        """
        return f"[@{string_id}]"
    
    def validate_string_id(self, string_id):
        """
        String_ID 유효성 검증 (신규 기능)
        
        Args:
            string_id (str): 검증할 String_ID
            
        Returns:
            tuple: (is_valid, message)
        """
        if not string_id or not string_id.strip():
            return False, "String_ID가 비어있습니다."
        
        string_id = string_id.strip()
        
        # 영문자, 숫자, 언더스코어만 허용
        if not re.match(r'^[a-zA-Z0-9_]+$', string_id):
            return False, "String_ID는 영문자, 숫자, 언더스코어(_)만 사용할 수 있습니다."
        
        # 첫 글자는 영문자여야 함
        if not string_id[0].isalpha():
            return False, "String_ID는 영문자로 시작해야 합니다."
        
        # 중복 검사
        if string_id.lower() in [char['string_id'].lower() for char in self.characters.values()]:
            return False, f"'{string_id}'는 이미 사용 중인 String_ID입니다."
        
        return True, "유효한 String_ID입니다."
    
    def add_character(self, name, kr_name, custom_string_id=None):
        """
        새 캐릭터 추가 (커스텀 String_ID 지원 추가)
        
        Args:
            name (str): 영문 이름
            kr_name (str): 한글 이름
            custom_string_id (str, optional): 사용자가 직접 입력한 String_ID
            
        Returns:
            tuple: (success, message, character_data)
        """
        # 중복 체크
        existing_by_name = self.get_character_by_name(name)
        existing_by_kr = self.get_character_by_kr(kr_name)
        
        if existing_by_name:
            return False, f"'{name}' 이미 등록된 영문 이름입니다.", None
        
        if existing_by_kr:
            return False, f"'{kr_name}' 이미 등록된 한글 이름입니다.", None
        
        # String_ID 처리
        if custom_string_id and custom_string_id.strip():
            # 사용자가 입력한 String_ID 사용
            string_id = custom_string_id.strip().lower()
            is_valid, validation_message = self.validate_string_id(string_id)
            
            if not is_valid:
                return False, validation_message, None
        else:
            # 자동 생성
            string_id = self.generate_string_id(name)
            
            # 자동 생성된 ID가 중복되는 경우 번호 추가
            original_id = string_id
            counter = 1
            while string_id in [char['string_id'] for char in self.characters.values()]:
                string_id = f"{original_id}_{counter}"
                counter += 1
        
        converter_name = self.generate_converter_name(string_id)
        
        character_data = {
            'name': name,
            'kr': kr_name,
            'string_id': string_id,
            'converter_name': converter_name
        }
        
        self.characters[string_id] = character_data
        self.save_characters()
        
        return True, f"캐릭터 '{name}' 추가 완료!", character_data


    def add_characters_batch(self, characters_to_add):
        """
        [신규] 여러 캐릭터를 한 번에 추가합니다.
        """
        success_count = 0
        error_messages = []
        
        for char_info in characters_to_add:
            name = char_info.get("name", "").strip()
            kr = char_info.get("kr", "").strip()
            string_id = char_info.get("string_id", "").strip()

            # 필수 정보 확인
            if not name or not kr or not string_id:
                error_messages.append(f"'{kr}' 캐릭터: Name, KR, String_ID는 필수 입력 항목입니다.")
                continue

            # 중복 및 유효성 검사
            if self.get_character_by_name(name) or self.get_character_by_kr(kr):
                error_messages.append(f"'{kr}' 캐릭터: 이미 등록된 이름입니다.")
                continue
            
            is_valid, validation_message = self.validate_string_id(string_id)
            if not is_valid:
                error_messages.append(f"'{kr}' 캐릭터 ({string_id}): {validation_message}")
                continue

            # 캐릭터 데이터 생성 및 추가
            converter_name = self.generate_converter_name(string_id)
            character_data = {
                'name': name,
                'kr': kr,
                'string_id': string_id,
                'converter_name': converter_name
            }
            self.characters[string_id] = character_data
            success_count += 1

        if success_count > 0:
            self.save_characters()

        return success_count, error_messages

    
    def update_character(self, string_id, name=None, kr_name=None, new_string_id=None):
        """
        기존 캐릭터 정보 수정 (String_ID 변경 지원 추가)
        
        Args:
            string_id (str): 수정할 캐릭터의 현재 String_ID
            name (str, optional): 새로운 영문 이름
            kr_name (str, optional): 새로운 한글 이름
            new_string_id (str, optional): 새로운 String_ID
            
        Returns:
            tuple: (success, message, character_data)
        """
        if string_id not in self.characters:
            return False, f"'{string_id}' 캐릭터를 찾을 수 없습니다.", None
        
        character_data = self.characters[string_id].copy()
        
        # String_ID 변경 처리
        if new_string_id and new_string_id.strip() and new_string_id.strip() != string_id:
            new_id = new_string_id.strip().lower()
            is_valid, validation_message = self.validate_string_id(new_id)
            
            if not is_valid:
                return False, validation_message, None
            
            # 기존 데이터 삭제하고 새 ID로 저장
            del self.characters[string_id]
            character_data['string_id'] = new_id
            character_data['converter_name'] = self.generate_converter_name(new_id)
            string_id = new_id  # 참조 업데이트
        
        # 다른 필드 업데이트
        if name:
            character_data['name'] = name
        if kr_name:
            character_data['kr'] = kr_name
        
        self.characters[string_id] = character_data
        self.save_characters()
        
        return True, f"캐릭터 정보가 수정되었습니다.", character_data
    
    def delete_character(self, string_id):
        """
        캐릭터 삭제
        
        Args:
            string_id (str): 삭제할 캐릭터의 String_ID
            
        Returns:
            bool: 삭제 성공 여부
        """
        if string_id in self.characters:
            del self.characters[string_id]
            self.save_characters()
            return True
        return False
    
    def get_character_by_kr(self, kr_name):
        """
        한글 이름으로 캐릭터 정보 검색
        
        Args:
            kr_name (str): 한글 이름
            
        Returns:
            dict or None: 찾은 캐릭터 정보 또는 None
        """
        for char_data in self.characters.values():
            if char_data['kr'] == kr_name:
                return char_data
        return None
    
    def get_character_by_name(self, name):
        """
        영문 이름으로 캐릭터 정보 검색
        
        Args:
            name (str): 영문 이름
            
        Returns:
            dict or None: 찾은 캐릭터 정보 또는 None
        """
        for char_data in self.characters.values():
            if char_data['name'].lower() == name.lower():
                return char_data
        return None
    
    def get_character_by_string_id(self, string_id):
        """
        String_ID로 캐릭터 정보 검색 (신규 기능)
        
        Args:
            string_id (str): String_ID
            
        Returns:
            dict or None: 찾은 캐릭터 정보 또는 None
        """
        return self.characters.get(string_id)
    
    def get_all_characters(self):
        """
        모든 캐릭터 정보 반환
        
        Returns:
            list: 캐릭터 정보 리스트
        """
        return list(self.characters.values())
    
    def get_characters_dataframe(self):
        """
        캐릭터 정보를 DataFrame으로 반환
        
        Returns:
            pandas.DataFrame: 캐릭터 정보 DataFrame
        """
        if not self.characters:
            return pd.DataFrame(columns=['Name', 'KR', 'String_ID', 'Converter_Name'])
        
        data = []
        for char_data in self.characters.values():
            data.append([
                char_data['name'],
                char_data['kr'],
                char_data['string_id'],
                char_data['converter_name']
            ])
        
        df = pd.DataFrame(data, columns=['Name', 'KR', 'String_ID', 'Converter_Name'])
        return df.sort_values('Name')
    
    def import_from_sheet_data(self, sheet_text):
        """
        구글 시트 데이터로부터 캐릭터 정보 가져오기
        
        Args:
            sheet_text (str): 탭으로 구분된 시트 데이터
            
        Returns:
            tuple: (성공 여부, 메시지, 가져온 개수)
        """
        try:
            # 시트 데이터를 DataFrame으로 변환
            df = pd.read_csv(StringIO(sheet_text), sep='\t')
            
            # 필요한 컬럼 확인 (현재 시트 구조에 맞춤)
            if len(df.columns) < 2:
                return False, "데이터가 부족합니다. 최소 2개 컬럼이 필요합니다.", 0
            
            imported_count = 0
            skipped_count = 0
            error_messages = []
            
            for _, row in df.iterrows():
                # 현재 시트 구조: String_ID(A) / KR(B) / Converter_Name(C) / Name(D)
                string_id = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                kr_name = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
                
                # 빈 값이나 특수 문자로 시작하는 행은 건너뛰기
                if not string_id or not kr_name or string_id.startswith('[@') or string_id.startswith('⬇'):
                    skipped_count += 1
                    continue
                
                # Name이 있으면 사용, 없으면 String_ID를 기반으로 생성
                if len(row) > 3 and pd.notna(row.iloc[3]):
                    name = str(row.iloc[3]).strip()
                else:
                    # String_ID에서 Name 생성 (첫 글자 대문자)
                    name = string_id.replace('_', ' ').title()
                
                # 중복 체크
                if string_id in self.characters:
                    error_messages.append(f"'{string_id}' - 이미 존재하는 String_ID")
                    skipped_count += 1
                    continue
                
                if self.get_character_by_kr(kr_name):
                    error_messages.append(f"'{kr_name}' - 이미 존재하는 한글 이름")
                    skipped_count += 1
                    continue
                
                if self.get_character_by_name(name):
                    error_messages.append(f"'{name}' - 이미 존재하는 영문 이름")
                    skipped_count += 1
                    continue
                
                # String_ID 유효성 검증
                is_valid, validation_message = self.validate_string_id(string_id)
                if not is_valid:
                    error_messages.append(f"'{string_id}' - {validation_message}")
                    skipped_count += 1
                    continue
                
                # 캐릭터 추가
                character_data = {
                    'name': name,
                    'kr': kr_name,
                    'string_id': string_id,
                    'converter_name': f"[@{string_id}]"
                }
                
                self.characters[string_id] = character_data
                imported_count += 1
            
            if imported_count > 0:
                self.save_characters()
            
            # 결과 메시지 구성
            result_message = f"{imported_count}개 캐릭터를 성공적으로 가져왔습니다."
            
            if skipped_count > 0:
                result_message += f" (건너뛴 항목: {skipped_count}개)"
            
            if error_messages:
                result_message += f"\n\n오류 목록:\n" + "\n".join(error_messages[:5])  # 최대 5개만 표시
                if len(error_messages) > 5:
                    result_message += f"\n... 외 {len(error_messages) - 5}개"
            
            if imported_count > 0:
                return True, result_message, imported_count
            else:
                return False, "가져올 수 있는 유효한 캐릭터 데이터가 없습니다.\n\n" + result_message, 0
                
        except Exception as e:
            return False, f"데이터 가져오기 오류: {str(e)}", 0
    
    def get_kr_to_string_id_mapping(self):
        """
        한글 이름 -> String_ID 매핑 딕셔너리 반환
        
        Returns:
            dict: {한글이름: string_id} 형태의 매핑
        """
        return {char_data['kr']: char_data['string_id'] for char_data in self.characters.values()}
    
    def export_to_sheet_format(self):
        """
        시트 형식으로 캐릭터 데이터 내보내기 (신규 기능)
        
        Returns:
            str: 탭으로 구분된 시트 데이터
        """
        if not self.characters:
            return "String_ID\tKR\tConverter_Name\tName"
        
        lines = ["String_ID\tKR\tConverter_Name\tName"]
        
        for char_data in sorted(self.characters.values(), key=lambda x: x['name']):
            line = f"{char_data['string_id']}\t{char_data['kr']}\t{char_data['converter_name']}\t{char_data['name']}"
            lines.append(line)
        
        return "\n".join(lines)