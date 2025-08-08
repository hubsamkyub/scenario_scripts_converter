import pandas as pd
import re
import gspread # gspread 임포트

class CharacterManager:
    def __init__(self, gspread_client, sheet_url):
        """[수정] 구글 시트 클라이언트와 URL을 받아 초기화합니다."""
        self.gc = gspread_client
        self.sheet_url = sheet_url
        self.spreadsheet = None
        self.characters_df = pd.DataFrame()

        if self.gc and self.sheet_url:
            self.load_characters()

    def is_loaded(self):
        """[신규] 데이터가 성공적으로 로드되었는지 확인하는 메서드"""
        return not self.characters_df.empty

    def is_empty(self):
        """[신규] 데이터가 비어있는지 확인하는 메서드 (is_loaded와 동일)"""
        return self.characters_df.empty
    
    def load_characters(self):
        """[수정] 'character' 시트에서 캐릭터 데이터를 로드하여 DataFrame으로 저장합니다."""
        try:
            self.spreadsheet = self.gc.open_by_url(self.sheet_url)
            worksheet = self.spreadsheet.worksheet("character")
            records = worksheet.get_all_records()
            self.characters_df = pd.DataFrame(records)
            
            # 데이터 타입 통일 및 소문자 변환
            for col in self.characters_df.columns:
                self.characters_df[col] = self.characters_df[col].astype(str)
            self.characters_df.columns = [str(col).lower() for col in self.characters_df.columns]
            
            # [신규] 빈 string_id 행들 필터링
            if 'string_id' in self.characters_df.columns:
                # string_id가 빈 문자열, 공백, 'nan', None인 경우 제거
                self.characters_df = self.characters_df[
                    (self.characters_df['string_id'].notna()) & 
                    (self.characters_df['string_id'].str.strip() != '') &
                    (self.characters_df['string_id'] != 'nan')
                ].copy()
                
                # 인덱스 재설정
                self.characters_df.reset_index(drop=True, inplace=True)
            
            return True, "캐릭터 데이터를 시트에서 불러왔습니다."
        except gspread.exceptions.SpreadsheetNotFound:
            return False, "설정 시트를 찾을 수 없습니다."
        except gspread.exceptions.WorksheetNotFound:
            return False, "'character' 시트를 찾을 수 없습니다."
        except Exception as e:
            return False, f"캐릭터 데이터 로드 중 오류: {e}"

    def get_characters_dataframe(self):
        """[수정] 메모리에 저장된 DataFrame을 반환합니다."""
        return self.characters_df

    def get_character_by_kr(self, kr_name):
        """[수정] DataFrame에서 한글 이름으로 캐릭터를 찾습니다."""
        if self.characters_df.empty: return None
        result = self.characters_df[self.characters_df['kr'] == kr_name]
        return result.iloc[0].to_dict() if not result.empty else None

    def get_character_by_name(self, name):
        """[수정] DataFrame에서 영문 이름으로 캐릭터를 찾습니다."""
        if self.characters_df.empty: return None
        result = self.characters_df[self.characters_df['name'].str.lower() == name.lower()]
        return result.iloc[0].to_dict() if not result.empty else None

    def add_character(self, name, kr_name, string_id, portrait_path):
        """[수정] 새 캐릭터를 'character' 시트에 추가합니다."""
        if not self.spreadsheet: return False, "설정 시트에 연결되지 않았습니다."
        
        # [신규] string_id 유효성 검사
        if not string_id or string_id.strip() == "":
            return False, "String_ID는 필수 입력 항목이며 빈 값일 수 없습니다."
        
        # 중복 검사
        if self.get_character_by_name(name) or self.get_character_by_kr(kr_name):
            return False, "이미 등록된 이름의 캐릭터입니다."
        
        # string_id 중복 검사
        if not self.characters_df.empty and string_id in self.characters_df['string_id'].values:
            return False, f"String_ID '{string_id}'가 이미 사용 중입니다."
            
        try:
            worksheet = self.spreadsheet.worksheet("character")
            # 컬럼 순서: String_ID, KR, Name, Portrait_Path, Converter_Name
            converter_name = f"[@{string_id}]"
            new_row = [string_id, kr_name, name, portrait_path, converter_name]
            worksheet.append_row(new_row)
            self.load_characters() # 데이터 다시 로드
            return True, f"캐릭터 '{name}'이(가) 시트에 추가되었습니다."
        except Exception as e:
            return False, f"캐릭터 추가 중 오류: {e}"
    
    def delete_character(self, string_id):
        """[수정] 'character' 시트에서 string_id로 캐릭터를 찾아 삭제합니다."""
        if not self.spreadsheet: return False, "설정 시트에 연결되지 않았습니다."
        
        # [신규] string_id 유효성 검사
        if not string_id or string_id.strip() == "":
            return False, "유효하지 않은 String_ID입니다."
            
        try:
            worksheet = self.spreadsheet.worksheet("character")
            cell = worksheet.find(string_id, in_column=1) # String_ID는 A열에 있다고 가정
            if cell:
                worksheet.delete_rows(cell.row)
                self.load_characters() # 데이터 다시 로드
                return True, f"'{string_id}' 캐릭터가 삭제되었습니다."
            return False, "삭제할 캐릭터를 찾지 못했습니다."
        except Exception as e:
            return False, f"캐릭터 삭제 중 오류: {e}"

    def add_characters_batch(self, char_data_list):
        """[신규] 여러 캐릭터를 한 번에 추가하는 메서드"""
        if not self.spreadsheet: 
            return 0, ["설정 시트에 연결되지 않았습니다."]
        
        success_count = 0
        error_messages = []
        
        try:
            worksheet = self.spreadsheet.worksheet("character")
            new_rows = []
            
            for char_data in char_data_list:
                name = char_data.get("name", "").strip()
                kr_name = char_data.get("kr", "").strip()
                string_id = char_data.get("string_id", "").strip()
                
                # 유효성 검사
                if not name or not kr_name or not string_id:
                    error_messages.append(f"'{kr_name}': 필수 정보가 누락되었습니다.")
                    continue
                
                # 중복 검사
                if self.get_character_by_name(name) or self.get_character_by_kr(kr_name):
                    error_messages.append(f"'{kr_name}': 이미 등록된 캐릭터입니다.")
                    continue
                
                if not self.characters_df.empty and string_id in self.characters_df['string_id'].values:
                    error_messages.append(f"'{kr_name}': String_ID '{string_id}'가 이미 사용 중입니다.")
                    continue
                
                # 새 행 데이터 준비
                converter_name = f"[@{string_id}]"
                portrait_path = char_data.get("portrait_path", "")
                new_row = [string_id, kr_name, name, portrait_path, converter_name]
                new_rows.append(new_row)
            
            # 유효한 행들을 한 번에 추가
            if new_rows:
                for row in new_rows:
                    worksheet.append_row(row)
                success_count = len(new_rows)
                self.load_characters()  # 데이터 다시 로드
                
        except Exception as e:
            error_messages.append(f"일괄 추가 중 오류: {e}")
        
        return success_count, error_messages