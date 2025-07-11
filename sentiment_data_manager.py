import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class SentimentDataManager:
    """감성 데이터 관리 클래스 - 일간/월간 라벨링 및 자동 정리"""
    
    def __init__(self, data_file: str = "sentiment_data.json"):
        self.data_file = data_file
        self.data = self.load_data()
    
    def load_data(self) -> Dict[str, Any]:
        """데이터 파일 로드"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 구조 검증 및 초기화
                    if not isinstance(data, dict):
                        return self._create_empty_structure()
                    
                    # 필수 키 확인
                    if "current_data" not in data:
                        data["current_data"] = {}
                    
                    return data
            else:
                return self._create_empty_structure()
        except (json.JSONDecodeError, Exception) as e:
            print(f"[WARNING] 데이터 파일 로드 실패: {e}")
            return self._create_empty_structure()
    
    def _create_empty_structure(self) -> Dict[str, Any]:
        """빈 데이터 구조 생성"""
        return {
            "current_data": {},
            "metadata": {
                "created": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
        }
    
    def save_data(self) -> bool:
        """데이터를 파일에 안전하게 저장"""
        try:
            # 메타데이터 업데이트
            self.data["metadata"]["last_updated"] = datetime.now().isoformat()
            
            # 임시 파일에 먼저 저장 (원자적 쓰기)
            temp_file = self.data_file + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            
            # 성공적으로 저장되면 원본 파일로 이동
            os.replace(temp_file, self.data_file)
            return True
            
        except Exception as e:
            print(f"[ERROR] 데이터 저장 실패: {e}")
            # 임시 파일 정리
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            return False
    
    def get_current_date_key(self) -> str:
        """현재 일자 키 생성 (KST 기준)"""
        # KST 시간으로 현재 날짜 계산
        kst = datetime.now()
        return kst.strftime("%Y-%m-%d")
    
    def get_current_month_key(self) -> str:
        """현재 월 키 생성 (KST 기준)"""
        kst = datetime.now()
        return kst.strftime("%Y-%m")
    
    def save_sentiment_data(self, posts: List[Dict[str, Any]], categories: Dict[str, List[Dict[str, Any]]]) -> bool:
        """감성 분류된 데이터 저장"""
        try:
            date_key = self.get_current_date_key()
            
            # current_data에 오늘 날짜로 저장
            if date_key not in self.data["current_data"]:
                self.data["current_data"][date_key] = []
            
            # 새 데이터 추가
            timestamp = datetime.now().isoformat()
            for category, category_posts in categories.items():
                if category == "버그":  # 버그는 실시간 알림으로만 처리
                    continue
                    
                for post in category_posts:
                    sentiment_entry = {
                        "timestamp": timestamp,
                        "category": category,
                        "title": post.get("title", ""),
                        "url": post.get("url", ""),
                        "source": post.get("source", ""),
                        "content_summary": post.get("content_summary", "")
                    }
                    self.data["current_data"][date_key].append(sentiment_entry)
            
            print(f"[DEBUG] 감성 데이터 저장: {date_key}일자 {len(sum(categories.values(), []))}개 게시글")
            return self.save_data()
            
        except Exception as e:
            print(f"[ERROR] 감성 데이터 저장 중 오류: {e}")
            return False
    
    def get_daily_sentiment_data(self, date_key: str) -> List[Dict[str, Any]]:
        """특정 일자의 감성 데이터 조회"""
        try:
            # current_data에서 조회
            if date_key in self.data.get("current_data", {}):
                return self.data["current_data"][date_key]
            
            # 완성된 월별 데이터에서 조회
            month_key = date_key[:7]  # "2025-07-11" -> "2025-07"
            if month_key in self.data and date_key in self.data[month_key]:
                return self.data[month_key][date_key]
            
            return []
            
        except Exception as e:
            print(f"[ERROR] 일간 데이터 조회 중 오류: {e}")
            return []
    
    def get_monthly_sentiment_data(self, month_key: str) -> Dict[str, List[Dict[str, Any]]]:
        """특정 월의 전체 감성 데이터 조회"""
        try:
            if month_key in self.data:
                return self.data[month_key]
            return {}
        except Exception as e:
            print(f"[ERROR] 월간 데이터 조회 중 오류: {e}")
            return {}
    
    def process_daily_transition(self) -> bool:
        """일간 전환 처리 (매일 9시 실행)"""
        try:
            current_date = self.get_current_date_key()
            yesterday_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            print(f"[INFO] 일간 전환 처리: {yesterday_date} -> {current_date}")
            
            # 어제 데이터가 current_data에 있으면 해당 월로 이동
            if yesterday_date in self.data.get("current_data", {}):
                yesterday_month = yesterday_date[:7]  # "2025-07-11" -> "2025-07"
                
                # 월별 섹션이 없으면 생성
                if yesterday_month not in self.data:
                    self.data[yesterday_month] = {}
                
                # 어제 데이터를 월별 섹션으로 이동
                self.data[yesterday_month][yesterday_date] = self.data["current_data"][yesterday_date]
                
                # current_data에서 제거
                del self.data["current_data"][yesterday_date]
                
                print(f"[INFO] {yesterday_date} 데이터를 {yesterday_month} 월로 이동 완료")
            
            # 오늘 데이터 초기화 (필요시)
            if current_date not in self.data.get("current_data", {}):
                self.data["current_data"][current_date] = []
            
            return self.save_data()
            
        except Exception as e:
            print(f"[ERROR] 일간 전환 처리 중 오류: {e}")
            return False
    
    def process_monthly_transition(self) -> bool:
        """월간 전환 처리 (매월 1일 실행)"""
        try:
            current_month = self.get_current_month_key()
            last_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
            
            print(f"[INFO] 월간 전환 처리: {last_month} -> {current_month}")
            
            # 지난달 데이터가 current_data에 남아있으면 정리
            current_data_keys = list(self.data.get("current_data", {}).keys())
            for date_key in current_data_keys:
                if date_key.startswith(last_month):
                    # 지난달 섹션으로 이동
                    if last_month not in self.data:
                        self.data[last_month] = {}
                    
                    self.data[last_month][date_key] = self.data["current_data"][date_key]
                    del self.data["current_data"][date_key]
                    print(f"[INFO] {date_key} 데이터를 {last_month} 월로 이동")
            
            # 2개월 초과 데이터 정리
            self.cleanup_old_monthly_data()
            
            return self.save_data()
            
        except Exception as e:
            print(f"[ERROR] 월간 전환 처리 중 오류: {e}")
            return False
    
    def cleanup_old_monthly_data(self) -> bool:
        """2개월 초과 데이터 자동 삭제"""
        try:
            current_month = self.get_current_month_key()
            current_date = datetime.now()
            
            # 현재월과 이전월만 유지
            keep_months = set()
            keep_months.add(current_month)  # 현재월
            
            # 이전월
            prev_month = (current_date.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
            keep_months.add(prev_month)
            
            # 삭제할 월 찾기
            months_to_delete = []
            for key in self.data.keys():
                if key not in ["current_data", "metadata"] and key not in keep_months:
                    # YYYY-MM 형식인지 확인
                    if len(key) == 7 and key[4] == '-':
                        months_to_delete.append(key)
            
            # 오래된 월 데이터 삭제
            deleted_count = 0
            for month_key in months_to_delete:
                entries_count = len(self.data[month_key]) if isinstance(self.data[month_key], dict) else 0
                del self.data[month_key]
                deleted_count += 1
                print(f"[INFO] 오래된 월 데이터 삭제: {month_key} ({entries_count}일치 데이터)")
            
            if deleted_count > 0:
                print(f"[INFO] 총 {deleted_count}개월 데이터 정리 완료")
                return self.save_data()
            else:
                print(f"[INFO] 정리할 오래된 데이터 없음 (유지: {', '.join(keep_months)})")
                return True
                
        except Exception as e:
            print(f"[ERROR] 오래된 데이터 정리 중 오류: {e}")
            return False
    
    def get_data_statistics(self) -> Dict[str, Any]:
        """데이터 통계 정보 반환"""
        try:
            stats = {
                "current_data_days": len(self.data.get("current_data", {})),
                "archived_months": 0,
                "total_entries": 0,
                "months": []
            }
            
            # current_data 통계
            for date_key, entries in self.data.get("current_data", {}).items():
                stats["total_entries"] += len(entries) if isinstance(entries, list) else 0
            
            # 월별 데이터 통계
            for key, value in self.data.items():
                if key not in ["current_data", "metadata"] and isinstance(value, dict):
                    stats["archived_months"] += 1
                    month_entries = sum(len(day_data) for day_data in value.values() if isinstance(day_data, list))
                    stats["total_entries"] += month_entries
                    stats["months"].append({
                        "month": key,
                        "days": len(value),
                        "entries": month_entries
                    })
            
            return stats
            
        except Exception as e:
            print(f"[ERROR] 통계 생성 중 오류: {e}")
            return {"error": str(e)}
    
    def is_month_transition_needed(self) -> bool:
        """월간 전환이 필요한지 확인"""
        try:
            current_month = self.get_current_month_key()
            
            # current_data에 이전월 데이터가 있는지 확인
            for date_key in self.data.get("current_data", {}).keys():
                date_month = date_key[:7]
                if date_month != current_month:
                    return True
            
            return False
            
        except Exception as e:
            print(f"[ERROR] 월간 전환 확인 중 오류: {e}")
            return False
    
    def force_cleanup_test(self) -> Dict[str, Any]:
        """테스트용 강제 정리 (개발/디버깅용)"""
        try:
            print("[TEST] 강제 데이터 정리 테스트 실행")
            
            before_stats = self.get_data_statistics()
            self.cleanup_old_monthly_data()
            after_stats = self.get_data_statistics()
            
            return {
                "before": before_stats,
                "after": after_stats,
                "cleaned": before_stats["archived_months"] - after_stats["archived_months"]
            }
            
        except Exception as e:
            return {"error": str(e)}


# 전역 인스턴스 생성
_sentiment_manager = None

def get_sentiment_manager() -> SentimentDataManager:
    """전역 SentimentDataManager 인스턴스 반환"""
    global _sentiment_manager
    if _sentiment_manager is None:
        _sentiment_manager = SentimentDataManager()
    return _sentiment_manager

# 편의 함수들
def save_sentiment_data(posts: List[Dict[str, Any]], categories: Dict[str, List[Dict[str, Any]]]) -> bool:
    """감성 데이터 저장 (편의 함수)"""
    return get_sentiment_manager().save_sentiment_data(posts, categories)

def get_daily_sentiment_data(date_key: str) -> List[Dict[str, Any]]:
    """일간 감성 데이터 조회 (편의 함수)"""
    return get_sentiment_manager().get_daily_sentiment_data(date_key)

def process_daily_transition() -> bool:
    """일간 전환 처리 (편의 함수)"""
    return get_sentiment_manager().process_daily_transition()

def process_monthly_transition() -> bool:
    """월간 전환 처리 (편의 함수)"""
    return get_sentiment_manager().process_monthly_transition()

def cleanup_old_monthly_data() -> bool:
    """오래된 월간 데이터 정리 (편의 함수)"""
    return get_sentiment_manager().cleanup_old_monthly_data()

# 테스트 함수
def test_sentiment_data_manager():
    """SentimentDataManager 테스트"""
    print("=== SentimentDataManager 테스트 ===")
    
    manager = get_sentiment_manager()
    
    # 통계 출력
    stats = manager.get_data_statistics()
    print(f"현재 데이터 통계: {stats}")
    
    # 테스트 데이터 저장
    test_posts = [
        {"title": "테스트 긍정 게시글", "url": "http://test.com/1", "source": "test"}
    ]
    test_categories = {
        "긍정": test_posts,
        "중립": [],
        "부정": []
    }
    
    result = manager.save_sentiment_data(test_posts, test_categories)
    print(f"테스트 데이터 저장 결과: {result}")
    
    # 오늘 데이터 조회
    today_data = manager.get_daily_sentiment_data(manager.get_current_date_key())
    print(f"오늘 데이터: {len(today_data)}개 항목")
    
    print("=== 테스트 완료 ===")

if __name__ == "__main__":
    test_sentiment_data_manager()