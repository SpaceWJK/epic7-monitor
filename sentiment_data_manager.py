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
    
    def add_post(self, title: str, url: str, site: str, sentiment: str, timestamp: str = None):
        """게시글 감성 데이터 추가"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        # 날짜별 데이터 구조화
        date_key = timestamp[:10]  # YYYY-MM-DD
        
        if "current_data" not in self.data:
            self.data["current_data"] = {}
        
        if date_key not in self.data["current_data"]:
            self.data["current_data"][date_key] = []
        
        post_data = {
            "title": title,
            "url": url,
            "site": site,
            "sentiment": sentiment,
            "timestamp": timestamp
        }
        
        self.data["current_data"][date_key].append(post_data)
        print(f"[DEBUG] 감성 데이터 추가: {date_key} - {sentiment} - {title[:30]}...")
    
    def get_daily_data(self, date_str: str) -> List[Dict]:
        """특정 날짜의 데이터 조회"""
        return self.data.get("current_data", {}).get(date_str, [])
    
    def get_daily_data_range(self, start_datetime: datetime, end_datetime: datetime) -> List[Dict]:
        """24시간 범위의 데이터 조회 (새로운 함수)"""
        all_data = []
        
        # 시작일과 종료일 사이의 모든 데이터 수집
        current_date = start_datetime.date()
        end_date = end_datetime.date()
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            daily_data = self.get_daily_data(date_str)
            
            for item in daily_data:
                try:
                    item_datetime = datetime.fromisoformat(item.get('timestamp', ''))
                    # 지정된 시간 범위 내의 데이터만 포함
                    if start_datetime <= item_datetime <= end_datetime:
                        all_data.append(item)
                except:
                    # 타임스탬프 파싱 실패 시 무시
                    continue
            
            current_date += timedelta(days=1)
        
        print(f"[DEBUG] 24시간 범위 데이터 조회: {len(all_data)}개 항목")
        return all_data
    
    def get_recent_data(self, hours: int = 24) -> List[Dict]:
        """최근 N시간 데이터 조회"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        return self.get_daily_data_range(start_time, end_time)
    
    def cleanup_old_data(self, keep_months: int = 2):
        """오래된 데이터 정리 (2개월 이상 된 데이터 삭제)"""
        try:
            cutoff_date = datetime.now() - timedelta(days=keep_months * 30)
            cutoff_str = cutoff_date.strftime('%Y-%m')
            
            current_data = self.data.get("current_data", {})
            dates_to_remove = []
            
            for date_str in current_data.keys():
                if date_str < cutoff_str:
                    dates_to_remove.append(date_str)
            
            if dates_to_remove:
                # 월간 데이터로 아카이브
                if "monthly_data" not in self.data:
                    self.data["monthly_data"] = {}
                
                for date_str in dates_to_remove:
                    month_key = date_str[:7]  # YYYY-MM
                    
                    if month_key not in self.data["monthly_data"]:
                        self.data["monthly_data"][month_key] = []
                    
                    # 월간 요약 데이터 생성
                    daily_data = current_data[date_str]
                    summary = self._create_daily_summary(daily_data, date_str)
                    self.data["monthly_data"][month_key].append(summary)
                    
                    # 상세 데이터 삭제
                    del current_data[date_str]
                
                print(f"[INFO] 정리된 오래된 데이터: {len(dates_to_remove)}일치")
                self.save_data()
            else:
                current_month = datetime.now().strftime('%Y-%m')
                prev_month = (datetime.now() - timedelta(days=30)).strftime('%Y-%m')
                print(f"[INFO] 정리할 오래된 데이터 없음 (유지: {prev_month}, {current_month})")
                
        except Exception as e:
            print(f"[ERROR] 데이터 정리 실패: {e}")
    
    def _create_daily_summary(self, daily_data: List[Dict], date_str: str) -> Dict:
        """일간 데이터 요약 생성"""
        total_posts = len(daily_data)
        
        sentiment_counts = {"긍정": 0, "부정": 0, "중립": 0}
        site_counts = {}
        
        for post in daily_data:
            sentiment = post.get("sentiment", "중립")
            site = post.get("site", "알 수 없음")
            
            sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
            site_counts[site] = site_counts.get(site, 0) + 1
        
        return {
            "date": date_str,
            "total_posts": total_posts,
            "sentiment_counts": sentiment_counts,
            "site_counts": site_counts,
            "created_at": datetime.now().isoformat()
        }
    
    def get_monthly_summary(self, month_str: str) -> Optional[Dict]:
        """월간 요약 데이터 조회"""
        return self.data.get("monthly_data", {}).get(month_str)
    
    def get_statistics(self, days: int = 7) -> Dict:
        """최근 N일간 통계 조회"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        total_posts = 0
        sentiment_counts = {"긍정": 0, "부정": 0, "중립": 0}
        site_counts = {}
        
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            daily_data = self.get_daily_data(date_str)
            
            total_posts += len(daily_data)
            
            for post in daily_data:
                sentiment = post.get("sentiment", "중립")
                site = post.get("site", "알 수 없음")
                
                sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
                site_counts[site] = site_counts.get(site, 0) + 1
            
            current_date += timedelta(days=1)
        
        return {
            "period": f"{start_date} ~ {end_date}",
            "total_posts": total_posts,
            "sentiment_counts": sentiment_counts,
            "site_counts": site_counts
        }

if __name__ == "__main__":
    # 테스트 코드
    manager = SentimentDataManager()
    
    # 테스트 데이터 추가
    manager.add_post(
        title="테스트 게시글",
        url="https://example.com",
        site="테스트사이트",
        sentiment="긍정"
    )
    
    # 24시간 범위 조회 테스트
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    range_data = manager.get_daily_data_range(yesterday, now)
    print(f"24시간 범위 데이터: {len(range_data)}개")
    
    manager.save_data()
    print("sentiment_data_manager.py 테스트 완료")