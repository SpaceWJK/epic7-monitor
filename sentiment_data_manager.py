import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class SentimentDataManager:
    """감성 데이터 관리 시스템 - 일간/월간 라벨링 및 자동 정리"""
    
    def __init__(self, data_file="sentiment_data.json"):
        self.data_file = data_file
        self.data = self.load_data()
    
    def load_data(self) -> Dict[str, Any]:
        """데이터 파일 로드"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"current_data": {}, "monthly_data": {}}
        except Exception as e:
            print(f"[ERROR] 데이터 로드 실패: {e}")
            return {"current_data": {}, "monthly_data": {}}
    
    def save_data(self):
        """데이터 파일 저장"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] 데이터 저장 실패: {e}")
    
    def get_current_date_key(self) -> str:
        """현재 날짜 키 반환 (KST 기준)"""
        return datetime.now().strftime('%Y-%m-%d')
    
    def get_current_month_key(self) -> str:
        """현재 월 키 반환"""
        return datetime.now().strftime('%Y-%m')
    
    def save_sentiment_data(self, posts: List[Dict], categories: Dict[str, List[Dict]]):
        """감성 데이터 저장"""
        try:
            current_date = self.get_current_date_key()
            
            # current_data 초기화
            if "current_data" not in self.data:
                self.data["current_data"] = {}
            
            if current_date not in self.data["current_data"]:
                self.data["current_data"][current_date] = []
            
            # 감성 분류된 게시글들을 저장
            for category, category_posts in categories.items():
                if category == "버그":  # 버그는 제외
                    continue
                    
                for post in category_posts:
                    sentiment_data = {
                        "timestamp": datetime.now().isoformat(),
                        "title": post.get("title", ""),
                        "url": post.get("url", ""),
                        "source": post.get("source", ""),
                        "category": category
                    }
                    self.data["current_data"][current_date].append(sentiment_data)
            
            self.save_data()
            print(f"[DEBUG] 감성 데이터 저장 완료: {current_date}")
            
        except Exception as e:
            print(f"[ERROR] 감성 데이터 저장 실패: {e}")
            raise
    
    def get_daily_data(self, date_key: str) -> List[Dict]:
        """특정 날짜의 데이터 조회"""
        try:
            # current_data에서 먼저 확인
            if "current_data" in self.data and date_key in self.data["current_data"]:
                return self.data["current_data"][date_key]
            
            # monthly_data에서 확인
            if "monthly_data" in self.data:
                month_key = date_key[:7]  # YYYY-MM 추출
                if month_key in self.data["monthly_data"]:
                    if date_key in self.data["monthly_data"][month_key]:
                        return self.data["monthly_data"][month_key][date_key]
            
            return []
            
        except Exception as e:
            print(f"[ERROR] 일간 데이터 조회 실패: {e}")
            return []
    
    def get_monthly_data(self, month_key: str) -> Dict[str, List[Dict]]:
        """특정 월의 데이터 조회"""
        try:
            if "monthly_data" in self.data and month_key in self.data["monthly_data"]:
                return self.data["monthly_data"][month_key]
            return {}
        except Exception as e:
            print(f"[ERROR] 월간 데이터 조회 실패: {e}")
            return {}
    
    def process_daily_transition(self):
        """매일 9시 실행: 전날 데이터를 완료 처리"""
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            current_month = datetime.now().strftime('%Y-%m')
            
            if "current_data" in self.data and yesterday in self.data["current_data"]:
                # monthly_data 초기화
                if "monthly_data" not in self.data:
                    self.data["monthly_data"] = {}
                
                if current_month not in self.data["monthly_data"]:
                    self.data["monthly_data"][current_month] = {}
                
                # 전날 데이터를 월간 데이터로 이동
                self.data["monthly_data"][current_month][yesterday] = self.data["current_data"][yesterday]
                
                # current_data에서 전날 데이터 제거
                del self.data["current_data"][yesterday]
                
                self.save_data()
                print(f"[DEBUG] 일간 라벨링 완료: {yesterday} → {current_month}")
            
        except Exception as e:
            print(f"[ERROR] 일간 전환 처리 실패: {e}")
    
    def process_monthly_transition(self):
        """매월 1일 실행: 전월 데이터 확정 및 오래된 데이터 삭제"""
        try:
            current_date = datetime.now()
            last_month = (current_date.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
            two_months_ago = (current_date.replace(day=1) - timedelta(days=32)).strftime('%Y-%m')
            
            # 2개월 전 데이터 삭제
            if "monthly_data" in self.data and two_months_ago in self.data["monthly_data"]:
                del self.data["monthly_data"][two_months_ago]
                print(f"[DEBUG] 오래된 월간 데이터 삭제: {two_months_ago}")
            
            self.save_data()
            print(f"[DEBUG] 월간 전환 완료: {last_month} 확정")
            
        except Exception as e:
            print(f"[ERROR] 월간 전환 처리 실패: {e}")
    
    def cleanup_old_monthly_data(self):
        """오래된 월간 데이터 정리 (2개월 초과 데이터 삭제)"""
        try:
            current_date = datetime.now()
            cutoff_date = current_date - timedelta(days=62)  # 약 2개월
            cutoff_month = cutoff_date.strftime('%Y-%m')
            
            if "monthly_data" not in self.data:
                print("[DEBUG] 월간 데이터 없음")
                return
            
            months_to_delete = []
            for month_key in self.data["monthly_data"]:
                if month_key < cutoff_month:
                    months_to_delete.append(month_key)
            
            for month_key in months_to_delete:
                del self.data["monthly_data"][month_key]
                print(f"[DEBUG] 오래된 데이터 삭제: {month_key}")
            
            if months_to_delete:
                self.save_data()
                print(f"[DEBUG] {len(months_to_delete)}개 월간 데이터 정리 완료")
            else:
                current_month = current_date.strftime('%Y-%m')
                last_month = (current_date.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
                print(f"[INFO] 정리할 오래된 데이터 없음 (유지: {last_month}, {current_month})")
            
        except Exception as e:
            print(f"[ERROR] 월간 데이터 정리 실패: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """전체 통계 조회"""
        try:
            stats = {
                "current_data_days": len(self.data.get("current_data", {})),
                "monthly_data_months": len(self.data.get("monthly_data", {})),
                "total_posts": 0
            }
            
            # current_data 게시글 수 계산
            for date_posts in self.data.get("current_data", {}).values():
                stats["total_posts"] += len(date_posts)
            
            # monthly_data 게시글 수 계산
            for month_data in self.data.get("monthly_data", {}).values():
                for date_posts in month_data.values():
                    stats["total_posts"] += len(date_posts)
            
            return stats
            
        except Exception as e:
            print(f"[ERROR] 통계 조회 실패: {e}")
            return {}
