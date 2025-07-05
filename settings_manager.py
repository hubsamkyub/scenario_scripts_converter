import json
import os
import gspread # gspread 임포트
import pandas as pd

class SettingsManager:
    """
    [수정] 사용자 정의 설정을 이제 구글 시트에서 관리합니다.
    """
    def __init__(self, gspread_client, sheet_url):
        self.gc = gspread_client
        self.sheet_url = sheet_url
        self.spreadsheet = None
        self.expression_map = {}
        self.directive_rules = {}

        if self.gc and self.sheet_url:
            try:
                self.spreadsheet = self.gc.open_by_url(self.sheet_url)
                self._load_expressions()
                self._load_directives()
            except gspread.exceptions.SpreadsheetNotFound:
                print("설정 시트를 찾을 수 없습니다. URL을 확인하세요.")
            except Exception as e:
                print(f"설정 시트 로드 중 오류: {e}")

    def is_loaded(self):
        """[신규] 데이터가 성공적으로 로드되었는지 확인하는 메서드 (규칙이 하나라도 있으면 True)"""
        return bool(self.expression_map) or bool(self.directive_rules)
    
    def _load_expressions(self):
        """'expressions' 시트에서 감정 표현 규칙을 로드합니다."""
        try:
            worksheet = self.spreadsheet.worksheet("expressions")
            records = worksheet.get_all_records()
            self.expression_map = {row['한글 표현']: row['영문 변환 값'] for row in records if row.get('한글 표현')}
        except gspread.exceptions.WorksheetNotFound:
            print("'expressions' 시트를 찾을 수 없습니다.")
        except Exception as e:
            print(f"'expressions' 시트 로드 중 오류: {e}")

    def _load_directives(self):
        """'directives' 시트에서 지시문 규칙을 로드합니다."""
        try:
            worksheet = self.spreadsheet.worksheet("directives")
            records = worksheet.get_all_records()
            self.directive_rules = {row['지시문']: {'type': row['타입'], 'template': row['템플릿']} for row in records if row.get('지시문')}
        except gspread.exceptions.WorksheetNotFound:
            print("'directives' 시트를 찾을 수 없습니다.")
        except Exception as e:
            print(f"'directives' 시트 로드 중 오류: {e}")

    # --- 감정 표현 규칙 관리 ---
    def get_expression_map(self):
        return self.expression_map

    def save_expression_map(self, new_map):
        """변경 사항을 'expressions' 시트 전체에 덮어씁니다."""
        if not self.spreadsheet: return False, "설정 시트에 연결되지 않았습니다."
        try:
            worksheet = self.spreadsheet.worksheet("expressions")
            # 기존 내용 삭제 후 새로 작성
            worksheet.clear()
            # 헤더 + 데이터
            header = ['한글 표현', '영문 변환 값']
            rows_to_insert = [header] + [[k, v] for k, v in new_map.items()]
            worksheet.update(rows_to_insert, 'A1')
            self._load_expressions() # 메모리에도 다시 로드
            return True, "감정 표현 규칙이 시트에 저장되었습니다."
        except Exception as e:
            return False, f"감정 표현 규칙 저장 중 오류: {e}"

    # --- 지시문 규칙 관리 ---
    def get_directive_rules(self):
        return self.directive_rules
    
    def add_directive_rule(self, name, rule_type, template):
        """새 지시문 규칙을 'directives' 시트의 마지막 행에 추가합니다."""
        if not self.spreadsheet: return False, "설정 시트에 연결되지 않았습니다."
        if not name or not rule_type or template is None: return False, "필수 항목이 비어있습니다."
        try:
            worksheet = self.spreadsheet.worksheet("directives")
            # 중복 체크
            if name in self.directive_rules:
                return False, f"'{name}' 규칙이 이미 존재합니다. 수정은 아직 지원되지 않습니다."
            worksheet.append_row([name, rule_type, template])
            self._load_directives() # 메모리 다시 로드
            return True, f"'{name}' 규칙이 시트에 추가되었습니다."
        except Exception as e:
            return False, f"지시문 규칙 추가 중 오류: {e}"

    def delete_directive_rule(self, name):
        """'directives' 시트에서 특정 규칙을 찾아 삭제합니다."""
        if not self.spreadsheet: return False, "설정 시트에 연결되지 않았습니다."
        try:
            worksheet = self.spreadsheet.worksheet("directives")
            cell = worksheet.find(name, in_column=1) # 지시문 이름은 A열에 있다고 가정
            if cell:
                worksheet.delete_rows(cell.row)
                self._load_directives() # 메모리 다시 로드
                return True, f"'{name}' 규칙이 삭제되었습니다."
            return False, "삭제할 규칙을 찾지 못했습니다."
        except Exception as e:
            return False, f"지시문 규칙 삭제 중 오류: {e}"