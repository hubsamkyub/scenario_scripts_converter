import json
import os
from urllib.parse import urlparse

class SheetConfigManager:
    """
    구글 시트 설정 관리 클래스
    - 마지막 접근 URL 저장
    - 컬럼 매핑 설정 저장
    """
    
    def __init__(self, config_file="sheet_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        """설정 파일 로드"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self.default_config()
        return self.default_config()
    
    def default_config(self):
        """기본 설정 반환"""
        return {
            "last_url": "",
            "last_sheet_name": "",
            "column_mappings": {},  # {sheet_id: {실제컬럼: 역할컬럼}}
            "recent_urls": []
        }
    
    def save_config(self):
        """설정 파일 저장"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    def extract_sheet_id(self, url):
        """URL에서 시트 ID 추출"""
        import re
        match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
        return match.group(1) if match else None
    
    def save_last_access(self, url, sheet_name=""):
        """마지막 접근 정보 저장"""
        self.config["last_url"] = url
        self.config["last_sheet_name"] = sheet_name
        
        # 최근 URL 목록에 추가 (중복 제거, 최대 5개)
        if url not in self.config["recent_urls"]:
            self.config["recent_urls"].insert(0, url)
            self.config["recent_urls"] = self.config["recent_urls"][:5]
        
        self.save_config()
    
    def get_last_access(self):
        """마지막 접근 정보 반환"""
        return {
            "url": self.config.get("last_url", ""),
            "sheet_name": self.config.get("last_sheet_name", "")
        }
    
    def get_recent_urls(self):
        """최근 접근 URL 목록 반환"""
        return self.config.get("recent_urls", [])
    
    def save_column_mapping(self, url, column_mapping):
        """특정 시트의 컬럼 매핑 저장"""
        sheet_id = self.extract_sheet_id(url)
        if sheet_id:
            self.config["column_mappings"][sheet_id] = column_mapping
            self.save_config()
    
    def get_column_mapping(self, url):
        """특정 시트의 컬럼 매핑 반환"""
        sheet_id = self.extract_sheet_id(url)
        if sheet_id:
            return self.config["column_mappings"].get(sheet_id, {})
        return {}
    
    def has_saved_mapping(self, url):
        """저장된 컬럼 매핑이 있는지 확인"""
        return bool(self.get_column_mapping(url))
    
    def get_role_columns(self):
        """역할 컬럼 목록 반환"""
        return {
            "캐릭터": "필수",
            "대사": "필수", 
            "포트레이트": "선택적",
            "사운드 주소": "선택적",
            "사운드 파일명": "선택적"
        }
    
    def validate_mapping(self, column_mapping):
        """컬럼 매핑 검증"""
        role_columns = self.get_role_columns()
        required_roles = [role for role, req_type in role_columns.items() if req_type == "필수"]
        
        mapped_roles = set(column_mapping.values())
        missing_required = [role for role in required_roles if role not in mapped_roles]
        
        if missing_required:
            return False, f"필수 역할이 매핑되지 않음: {', '.join(missing_required)}"
        
        return True, "매핑이 유효합니다"
    
    def apply_mapping(self, df, column_mapping):
        """데이터프레임에 컬럼 매핑 적용"""
        # 역방향 매핑 생성 (역할 -> 실제컬럼)
        reverse_mapping = {role: actual for actual, role in column_mapping.items()}
        
        # 새로운 데이터프레임 생성
        mapped_df = df.copy()
        
        # 컬럼명 변경
        rename_dict = {}
        for role, actual_col in reverse_mapping.items():
            if actual_col in mapped_df.columns:
                rename_dict[actual_col] = role
        
        mapped_df = mapped_df.rename(columns=rename_dict)
        
        # 누락된 선택적 컬럼 추가
        role_columns = self.get_role_columns()
        for role in role_columns:
            if role not in mapped_df.columns:
                mapped_df[role] = ""
        
        # 필요한 컬럼만 선택
        final_columns = list(role_columns.keys())
        mapped_df = mapped_df[final_columns]
        
        return mapped_df
    
    def clear_config(self):
        """설정 초기화"""
        self.config = self.default_config()
        self.save_config()
    
    def get_config_summary(self):
        """설정 요약 정보 반환"""
        return {
            "저장된_시트_수": len(self.config.get("column_mappings", {})),
            "최근_URL_수": len(self.config.get("recent_urls", [])),
            "마지막_접근": self.config.get("last_url", "없음")
        }