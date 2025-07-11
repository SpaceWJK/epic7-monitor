import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import traceback

class SentimentDataManager:
    """감성 데이터 관리 클래스 - 일간/월간 라벨링 및 2개월 순환 삭제"""
    
    def __init__(self, data_file: str = "sentiment_data.json"):
        self.data_file = data_file
        self.data = self._load_data()
        
    def _load_data(self) -> Dict[str, Any]:
        """데이터 파일 로드"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 기본 구조 확인 및 생성
                    if not isinstance(data, dict):
                        return self._create_empty_structure()
                    if "current_data" not in data:
                        data["current_data"] = {}
                    return data
            else:
                return self._create_empty_structure()
        except Exception as e:
            print(f"[ERROR] 데이터 로드 실패: {e}")
            return self._create_empty_structure()
    
    def _create_empty_structure(self) -> Dict[str, Any]:
        """빈 데이터 구조 생성"""
        return {
            "current_data": {},
            "last_daily_process": None,
            "last_monthly_process": None
        }
    
    def _save_data(self):
        """데이터 파일 저장 (원자적 쓰기)"""
        try:
            # 임시 파일에 먼저 저장
            temp_file = self.data_file + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            
            # 원자적 이동
            if os.path.exists(self.data_file):
                os.remove(self.data_file)
            os.rename(temp_file, self.data_file)
            
        except Exception as e:
            print(f"[ERROR] 데이터 저장 실패: {e}")
            traceback.print_exc()
    
    def get_current_date_key(self) -> str:
        """현재 날짜 키 생성 (KST 기준)"""
        # 한국 시간 기준으로 날짜 계산
        now = datetime.now()
        return now.strftime("%Y-%m-%d")
    
    def get_current_month_key(self) -> str:
        """현재 월 키 생성"""
        now = datetime.now()
        return now.strftime("%Y-%m")
    
    def add_sentiment_data(self, posts: List[Dict[str, Any]]):
        """감성 데이터 추가 (실시간 크롤링 결과)"""
        try:
            if not posts:
                return
            
            current_date = self.get_current_date_key()
            
            # current_data에 오늘 날짜로 데이터 추가
            if current_date not in self.data["current_data"]:
                self.data["current_data"][current_date] = []
            
            # 타임스탬프 추가하여 저장
            for post in posts:
                post_with_timestamp = {
                    **post,
                    "processed_time": datetime.now().isoformat()
                }
                self.data["current_data"][current_date].append(post_with_timestamp)
            
            print(f"[INFO] {len(posts)}개 감성 데이터 저장됨: {current_date}")
            self._save_data()
            
        except Exception as e:
            print(f"[ERROR] 감성 데이터 추가 실패: {e}")
            traceback.print_exc()
    
    def process_daily_completion(self):
        """일간 데이터 완료 처리 (매일 오전 9시 실행)"""
        try:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            current_month = now.strftime("%Y-%m")
            
            # 어제 데이터가 current_data에 있으면 월별 데이터로 이동
            if yesterday in self.data["current_data"]:
                if current_month not in self.data:
                    self.data[current_month] = {}
                
                # 어제 데이터를 월별 데이터로 이동
                self.data[current_month][yesterday] = self.data["current_data"][yesterday]
                del self.data["current_data"][yesterday]
                
                print(f"[INFO] 일간 데이터 완료 처리: {yesterday} → {current_month}")
            
            # 오늘 데이터 시작 준비
            if today not in self.data["current_data"]:
                self.data["current_data"][today] = []
            
            self.data["last_daily_process"] = now.isoformat()
            self._save_data()
            
        except Exception as e:
            print(f"[ERROR] 일간 완료 처리 실패: {e}")
            traceback.print_exc()
    
    def process_monthly_completion(self):
        """월간 데이터 완료 처리 (매월 1일 실행)"""
        try:
            now = datetime.now()
            current_month = now.strftime("%Y-%m")
            
            # 이전 월 계산
            if now.month == 1:
                last_month = f"{now.year - 1}-12"
            else:
                last_month = f"{now.year}-{now.month-1:02d}"
            
            print(f"[INFO] 월간 데이터 완료 처리: {last_month}")
            
            # 2개월 이전 데이터 삭제
            self._cleanup_old_months()
            
            self.data["last_monthly_process"] = now.isoformat()
            self._save_data()
            
        except Exception as e:
            print(f"[ERROR] 월간 완료 처리 실패: {e}")
            traceback.print_exc()
    
    def _cleanup_old_months(self):
        """오래된 월 데이터 삭제 (2개월 이상된 것)"""
        try:
            now = datetime.now()
            current_month = now.strftime("%Y-%m")
            
            # 보관할 월 목록 생성 (현재월 + 이전월)
            keep_months = set()
            for i in range(2):  # 현재월 포함 2개월
                month_date = now.replace(day=1) - timedelta(days=30*i)
                keep_months.add(month_date.strftime("%Y-%m"))
            
            # 삭제할 월 찾기
            months_to_delete = []
            for key in self.data.keys():
                if key.startswith("20") and len(key) == 7:  # YYYY-MM 형식
                    if key not in keep_months:
                        months_to_delete.append(key)
            
            # 오래된 월 데이터 삭제
            for month_key in months_to_delete:
                del self.data[month_key]
                print(f"[INFO] 오래된 월 데이터 삭제: {month_key}")
            
            if months_to_delete:
                print(f"[INFO] 총 {len(months_to_delete)}개 월 데이터 삭제됨")
                
        except Exception as e:
            print(f"[ERROR] 오래된 데이터 정리 실패: {e}")
            traceback.print_exc()
    
    def get_daily_data(self, date: str) -> List[Dict[str, Any]]:
        """특정 날짜의 데이터 조회"""
        try:
            # current_data에서 먼저 찾기
            if date in self.data["current_data"]:
                return self.data["current_data"][date]
            
            # 월별 데이터에서 찾기
            month_key = date[:7]  # YYYY-MM 추출
            if month_key in self.data and date in self.data[month_key]:
                return self.data[month_key][date]
            
            return []
            
        except Exception as e:
            print(f"[ERROR] 일간 데이터 조회 실패: {e}")
            return []
    
    def get_yesterday_data(self) -> List[Dict[str, Any]]:
        """어제 데이터 조회 (일간 보고서용)"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        return self.get_daily_data(yesterday)
    
    def get_monthly_data(self, month: str) -> Dict[str, List[Dict[str, Any]]]:
        """특정 월의 모든 데이터 조회"""
        try:
            if month in self.data:
                return self.data[month]
            return {}
        except Exception as e:
            print(f"[ERROR] 월간 데이터 조회 실패: {e}")
            return {}
    
    def get_date_range_data(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """날짜 범위 데이터 조회"""
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            
            all_data = []
            current = start
            
            while current <= end:
                date_str = current.strftime("%Y-%m-%d")
                daily_data = self.get_daily_data(date_str)
                all_data.extend(daily_data)
                current += timedelta(days=1)
            
            return all_data
            
        except Exception as e:
            print(f"[ERROR] 날짜 범위 데이터 조회 실패: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """데이터 통계 조회"""
        try:
            stats = {
                "total_months": 0,
                "total_days": 0,
                "total_posts": 0,
                "current_data_days": len(self.data["current_data"]),
                "months": {}
            }
            
            # 월별 데이터 통계
            for key, value in self.data.items():
                if key.startswith("20") and len(key) == 7:  # YYYY-MM 형식
                    stats["total_months"] += 1
                    stats["total_days"] += len(value)
                    
                    month_posts = sum(len(day_data) for day_data in value.values())
                    stats["total_posts"] += month_posts
                    stats["months"][key] = {
                        "days": len(value),
                        "posts": month_posts
                    }
            
            # current_data 통계
            current_posts = sum(len(day_data) for day_data in self.data["current_data"].values())
            stats["total_posts"] += current_posts
            stats["current_data_posts"] = current_posts
            
            return stats
            
        except Exception as e:
            print(f"[ERROR] 통계 조회 실패: {e}")
            return {}
    
    def auto_maintenance(self):
        """자동 유지보수 (일간/월간 처리 자동 실행)"""
        try:
            now = datetime.now()
            
            # 매일 오전 9시에 일간 처리
            if now.hour == 9:
                last_daily = self.data.get("last_daily_process")
                if not last_daily or last_daily[:10] != now.strftime("%Y-%m-%d"):
                    self.process_daily_completion()
            
            # 매월 1일에 월간 처리
            if now.day == 1:
                last_monthly = self.data.get("last_monthly_process")
                if not last_monthly or last_monthly[:7] != now.strftime("%Y-%m"):
                    self.process_monthly_completion()
                    
        except Exception as e:
            print(f"[ERROR] 자동 유지보수 실패: {e}")
            traceback.print_exc()


# 전역 인스턴스
sentiment_manager = SentimentDataManager()

def save_sentiment_data(posts: List[Dict[str, Any]]):
    """감성 데이터 저장 (외부 호출용)"""
    sentiment_manager.add_sentiment_data(posts)

def get_yesterday_sentiment_data() -> List[Dict[str, Any]]:
    """어제 감성 데이터 조회 (일간 보고서용)"""
    return sentiment_manager.get_yesterday_data()

def get_sentiment_stats() -> Dict[str, Any]:
    """감성 데이터 통계 조회"""
    return sentiment_manager.get_stats()

def run_daily_maintenance():
    """일간 유지보수 실행"""
    sentiment_manager.process_daily_completion()

def run_monthly_maintenance():
    """월간 유지보수 실행"""
    sentiment_manager.process_monthly_completion()

def auto_maintenance():
    """자동 유지보수 실행"""
    sentiment_manager.auto_maintenance()


# 테스트 함수
def test_sentiment_manager():
    """감성 데이터 매니저 테스트"""
    print("=== 감성 데이터 매니저 테스트 ===")
    
    # 샘플 데이터
    sample_posts = [
        {
            "title": "테스트 긍정 게시글",
            "category": "긍정",
            "source": "stove_general",
            "url": "https://example.com/1"
        },
        {
            "title": "테스트 부정 게시글", 
            "category": "부정",
            "source": "ruliweb",
            "url": "https://example.com/2"
        }
    ]
    
    # 데이터 저장 테스트
    save_sentiment_data(sample_posts)
    
    # 통계 조회 테스트
    stats = get_sentiment_stats()
    print(f"통계: {stats}")
    
    # 어제 데이터 조회 테스트
    yesterday_data = get_yesterday_sentiment_data()
    print(f"어제 데이터: {len(yesterday_data)}개")
    
    print("테스트 완료")

if __name__ == "__main__":
    test_sentiment_manager()