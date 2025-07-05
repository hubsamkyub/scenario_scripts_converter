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
        # 중복 검사
        if self.get_character_by_name(name) or self.get_character_by_kr(kr_name):
            return False, "이미 등록된 이름의 캐릭터입니다."
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