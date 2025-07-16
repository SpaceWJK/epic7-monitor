# generate_report.py - 코드 배열 수정 및 번역 기능 제외 버전
# Epic7 모니터링 시스템 - 통계 데이터 전용 리포트 생성기

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import requests
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
import statistics
import re
import hashlib
import time

# 크롤링 및 분류 모듈 임포트
from crawler import load_crawled_links, load_content_cache
from classifier import classify_post, is_bug_post, is_positive_post, is_negative_post

@dataclass
class ReportData:
    """리포트 데이터 구조"""
    date: str
    total_posts: int
    korean_posts: int
    global_posts: int
    bug_posts: int
    positive_posts: int
    negative_posts: int
    neutral_posts: int
    top_sources: Dict[str, int]
    trend_analysis: Dict[str, Any]
    insights: List[str]
    recommendations: List[str]

class GlobalDataManager:
    """글로벌 데이터 통합 관리자"""
    
    def __init__(self):
        self.korean_sources = [
            "stove_bug", "stove_general", 
            "ruliweb_epic7", "arca_epic7"
        ]
        self.global_sources = [
            "stove_global_bug", "stove_global_general", 
            "reddit_epic7", "global_forum"
        ]
        self.data_cache = {}
        self.trend_cache = {}
        
    def load_all_data(self, hours: int = 24) -> Dict[str, List[Dict]]:
        """모든 소스에서 데이터 로드"""
        all_data = {
            "korean": [],
            "global": [],
            "combined": []
        }
        
        # 한국 사이트 데이터 로드
        try:
            korean_links = self._load_links_file("crawled_links_korean.json")
            korean_cache = self._load_cache_file("content_cache_korean.json")
            
            for link in korean_links.get("links", []):
                if self._is_within_timeframe(link, hours):
                    post_data = self._get_post_data(link, korean_cache)
                    if post_data:
                        all_data["korean"].append(post_data)
                        all_data["combined"].append(post_data)
                        
        except Exception as e:
            print(f"[ERROR] 한국 사이트 데이터 로드 실패: {e}")
            
        # 글로벌 사이트 데이터 로드
        try:
            global_links = self._load_links_file("crawled_links_global.json")
            global_cache = self._load_cache_file("content_cache_global.json")
            
            for link in global_links.get("links", []):
                if self._is_within_timeframe(link, hours):
                    post_data = self._get_post_data(link, global_cache)
                    if post_data:
                        all_data["global"].append(post_data)
                        all_data["combined"].append(post_data)
                        
        except Exception as e:
            print(f"[ERROR] 글로벌 사이트 데이터 로드 실패: {e}")
            
        # 폴백: 통합 파일 사용
        if not all_data["korean"] and not all_data["global"]:
            try:
                fallback_links = self._load_links_file("crawled_links.json")
                fallback_cache = self._load_cache_file("content_cache.json")
                
                for link in fallback_links.get("links", []):
                    if self._is_within_timeframe(link, hours):
                        post_data = self._get_post_data(link, fallback_cache)
                        if post_data:
                            all_data["combined"].append(post_data)
                            
            except Exception as e:
                print(f"[ERROR] 폴백 데이터 로드 실패: {e}")
                
        return all_data
        
    def _load_links_file(self, filename: str) -> Dict:
        """링크 파일 로드"""
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ERROR] {filename} 로드 실패: {e}")
                
        return {"links": [], "last_updated": datetime.now().isoformat()}
        
    def _load_cache_file(self, filename: str) -> Dict:
        """캐시 파일 로드"""
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ERROR] {filename} 로드 실패: {e}")
                
        return {}
        
    def _is_within_timeframe(self, link_data: Any, hours: int) -> bool:
        """시간 범위 내 데이터 확인"""
        try:
            if isinstance(link_data, dict):
                timestamp_str = link_data.get('timestamp', '')
            else:
                # 문자열 링크인 경우 현재 시간 사용
                return True
                
            if not timestamp_str:
                return True
                
            link_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            return link_time > cutoff_time
            
        except:
            return True
            
    def _get_post_data(self, link_data: Any, cache: Dict) -> Optional[Dict]:
        """게시글 데이터 추출"""
        try:
            if isinstance(link_data, dict):
                url = link_data.get('url', '')
                title = link_data.get('title', '')
                source = link_data.get('source', 'unknown')
                timestamp = link_data.get('timestamp', datetime.now().isoformat())
            else:
                url = link_data
                title = ''
                source = 'unknown'
                timestamp = datetime.now().isoformat()
                
            # 캐시에서 내용 가져오기
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
            cached_item = cache.get(url_hash, {})
            content = cached_item.get('content', '')
            
            # 제목이 없으면 캐시에서 가져오기
            if not title and cached_item.get('title'):
                title = cached_item['title']
                
            if not title:
                title = "제목 없음"
                
            return {
                'url': url,
                'title': title,
                'content': content,
                'source': source,
                'timestamp': timestamp
            }
            
        except Exception as e:
            print(f"[ERROR] 게시글 데이터 추출 실패: {e}")
            return None

class TrendAnalyzer:
    """트렌드 분석기"""
    
    def __init__(self):
        self.trend_data = {}
        self.analysis_cache = {}
        
    def analyze_sentiment_trends(self, data: List[Dict], hours: int = 24) -> Dict[str, Any]:
        """감성 트렌드 분석"""
        hourly_sentiment = defaultdict(lambda: {
            'positive': 0, 'negative': 0, 'neutral': 0, 'bug': 0
        })
        
        for post in data:
            try:
                timestamp = datetime.fromisoformat(post['timestamp'].replace('Z', '+00:00'))
                hour_key = timestamp.strftime('%Y-%m-%d-%H')
                
                title = post.get('title', '')
                content = post.get('content', '')
                text = f"{title} {content}"
                
                # 분류
                if is_bug_post(title):
                    hourly_sentiment[hour_key]['bug'] += 1
                elif is_positive_post(title):
                    hourly_sentiment[hour_key]['positive'] += 1
                elif is_negative_post(title):
                    hourly_sentiment[hour_key]['negative'] += 1
                else:
                    hourly_sentiment[hour_key]['neutral'] += 1
                    
            except Exception as e:
                print(f"[ERROR] 감성 분석 실패: {e}")
                continue
                
        # 트렌드 계산
        trend_analysis = {
            'hourly_data': dict(hourly_sentiment),
            'overall_sentiment': self._calculate_overall_sentiment(hourly_sentiment),
            'peak_hours': self._find_peak_hours(hourly_sentiment),
            'sentiment_velocity': self._calculate_sentiment_velocity(hourly_sentiment)
        }
        
        return trend_analysis
        
    def analyze_source_trends(self, data: List[Dict]) -> Dict[str, Any]:
        """소스별 트렌드 분석"""
        source_counts = Counter()
        source_sentiment = defaultdict(lambda: {
            'positive': 0, 'negative': 0, 'neutral': 0, 'bug': 0
        })
        
        for post in data:
            source = post.get('source', 'unknown')
            title = post.get('title', '')
            
            source_counts[source] += 1
            
            if is_bug_post(title):
                source_sentiment[source]['bug'] += 1
            elif is_positive_post(title):
                source_sentiment[source]['positive'] += 1
            elif is_negative_post(title):
                source_sentiment[source]['negative'] += 1
            else:
                source_sentiment[source]['neutral'] += 1
                
        return {
            'source_counts': dict(source_counts),
            'source_sentiment': dict(source_sentiment),
            'most_active_sources': source_counts.most_common(5),
            'source_analysis': self._analyze_source_patterns(source_sentiment)
        }
        
    def _calculate_overall_sentiment(self, hourly_data: Dict) -> Dict[str, float]:
        """전체 감성 점수 계산"""
        total_positive = sum(hour['positive'] for hour in hourly_data.values())
        total_negative = sum(hour['negative'] for hour in hourly_data.values())
        total_neutral = sum(hour['neutral'] for hour in hourly_data.values())
        total_bug = sum(hour['bug'] for hour in hourly_data.values())
        
        total_posts = total_positive + total_negative + total_neutral + total_bug
        
        if total_posts == 0:
            return {'positive': 0, 'negative': 0, 'neutral': 0, 'bug': 0}
            
        return {
            'positive': (total_positive / total_posts) * 100,
            'negative': (total_negative / total_posts) * 100,
            'neutral': (total_neutral / total_posts) * 100,
            'bug': (total_bug / total_posts) * 100
        }
        
    def _find_peak_hours(self, hourly_data: Dict) -> Dict[str, str]:
        """피크 시간 찾기"""
        max_activity = 0
        peak_hour = ""
        
        for hour, data in hourly_data.items():
            total_activity = sum(data.values())
            if total_activity > max_activity:
                max_activity = total_activity
                peak_hour = hour
                
        return {
            'peak_hour': peak_hour,
            'peak_activity': max_activity
        }
        
    def _calculate_sentiment_velocity(self, hourly_data: Dict) -> Dict[str, float]:
        """감성 변화 속도 계산"""
        if len(hourly_data) < 2:
            return {'velocity': 0.0, 'direction': 'stable'}
            
        hours = sorted(hourly_data.keys())
        sentiment_scores = []
        
        for hour in hours:
            data = hourly_data[hour]
            total = sum(data.values())
            
            if total > 0:
                sentiment_score = (data['positive'] - data['negative']) / total
                sentiment_scores.append(sentiment_score)
                
        if len(sentiment_scores) < 2:
            return {'velocity': 0.0, 'direction': 'stable'}
            
        velocity = sentiment_scores[-1] - sentiment_scores[0]
        direction = 'improving' if velocity > 0.1 else 'declining' if velocity < -0.1 else 'stable'
        
        return {
            'velocity': velocity,
            'direction': direction
        }
        
    def _analyze_source_patterns(self, source_sentiment: Dict) -> Dict[str, Any]:
        """소스 패턴 분석"""
        patterns = {}
        
        for source, sentiment in source_sentiment.items():
            total = sum(sentiment.values())
            
            if total > 0:
                patterns[source] = {
                    'total_posts': total,
                    'bug_ratio': sentiment['bug'] / total,
                    'positive_ratio': sentiment['positive'] / total,
                    'negative_ratio': sentiment['negative'] / total,
                    'dominant_sentiment': max(sentiment.items(), key=lambda x: x[1])[0]
                }
                
        return patterns

class InsightGenerator:
    """인사이트 생성기"""
    
    def __init__(self):
        self.insight_templates = {
            'bug_trend': "버그 리포트가 {period}에 {change}% {direction}했습니다.",
            'sentiment_change': "전체 감성이 {previous}에서 {current}로 변화했습니다.",
            'peak_activity': "가장 활발한 시간은 {hour}이며, 총 {count}개의 게시글이 작성되었습니다.",
            'source_dominance': "{source}가 전체 게시글의 {percentage}%를 차지하며 가장 활발한 소스입니다."
        }
        
    def generate_insights(self, data: List[Dict], trend_analysis: Dict) -> List[str]:
        """인사이트 생성"""
        insights = []
        
        try:
            # 버그 트렌드 인사이트
            bug_posts = [post for post in data if is_bug_post(post.get('title', ''))]
            if bug_posts:
                bug_insight = f"지난 24시간 동안 총 {len(bug_posts)}개의 버그 리포트가 발견되었습니다."
                insights.append(bug_insight)
                
            # 감성 트렌드 인사이트
            overall_sentiment = trend_analysis.get('overall_sentiment', {})
            if overall_sentiment:
                dominant_sentiment = max(overall_sentiment.items(), key=lambda x: x[1])
                sentiment_insight = f"전체 감성 중 {dominant_sentiment[0]}가 {dominant_sentiment[1]:.1f}%로 가장 높습니다."
                insights.append(sentiment_insight)
                
            # 피크 시간 인사이트
            peak_info = trend_analysis.get('peak_hours', {})
            if peak_info.get('peak_hour'):
                peak_insight = f"가장 활발한 시간은 {peak_info['peak_hour'][-2:]}시이며, {peak_info['peak_activity']}개의 게시글이 작성되었습니다."
                insights.append(peak_insight)
                
            # 소스 분석 인사이트
            source_analysis = trend_analysis.get('source_analysis', {})
            if source_analysis:
                most_active_source = max(source_analysis.items(), key=lambda x: x[1]['total_posts'])
                source_insight = f"{most_active_source[0]} 소스가 {most_active_source[1]['total_posts']}개 게시글로 가장 활발합니다."
                insights.append(source_insight)
                
            # 글로벌 vs 한국 비교
            korean_posts = [post for post in data if post.get('source', '').startswith('stove_') or 'ruliweb' in post.get('source', '')]
            global_posts = [post for post in data if 'global' in post.get('source', '') or 'reddit' in post.get('source', '')]
            
            if korean_posts and global_posts:
                ratio = len(korean_posts) / len(global_posts)
                if ratio > 2:
                    insights.append(f"한국 사이트 활동이 글로벌 사이트보다 {ratio:.1f}배 활발합니다.")
                elif ratio < 0.5:
                    insights.append(f"글로벌 사이트 활동이 한국 사이트보다 {1/ratio:.1f}배 활발합니다.")
                    
        except Exception as e:
            print(f"[ERROR] 인사이트 생성 실패: {e}")
            insights.append("인사이트 생성 중 오류가 발생했습니다.")
            
        return insights[:10]  # 최대 10개 인사이트
        
    def generate_recommendations(self, data: List[Dict], insights: List[str]) -> List[str]:
        """권장사항 생성"""
        recommendations = []
        
        try:
            # 버그 리포트 기반 권장사항
            bug_posts = [post for post in data if is_bug_post(post.get('title', ''))]
            if len(bug_posts) > 10:
                recommendations.append("버그 리포트가 많이 증가했습니다. 개발팀 검토가 필요합니다.")
                
            # 감성 기반 권장사항
            negative_posts = [post for post in data if is_negative_post(post.get('title', ''))]
            if len(negative_posts) > len(data) * 0.3:
                recommendations.append("부정적인 게시글이 30% 이상입니다. 커뮤니티 관리가 필요합니다.")
                
            # 소스 다양성 권장사항
            sources = set(post.get('source', '') for post in data)
            if len(sources) < 3:
                recommendations.append("모니터링 소스가 제한적입니다. 추가 소스 확장을 고려하세요.")
                
            # 활동 패턴 권장사항
            if len(data) < 50:
                recommendations.append("전체 게시글 수가 적습니다. 크롤링 범위 확장을 고려하세요.")
                
        except Exception as e:
            print(f"[ERROR] 권장사항 생성 실패: {e}")
            recommendations.append("권장사항 생성 중 오류가 발생했습니다.")
            
        return recommendations[:5]  # 최대 5개 권장사항

class ReportGenerator:
    """통합 리포트 생성기"""
    
    def __init__(self):
        self.data_manager = GlobalDataManager()
        self.trend_analyzer = TrendAnalyzer()
        self.insight_generator = InsightGenerator()
        
    def generate_daily_report(self, hours: int = 24) -> ReportData:
        """일일 리포트 생성"""
        print(f"[INFO] {hours}시간 데이터 기반 리포트 생성 시작...")
        
        # 데이터 로드
        all_data = self.data_manager.load_all_data(hours)
        combined_data = all_data['combined']
        
        print(f"[INFO] 총 {len(combined_data)}개 게시글 분석 중...")
        
        # 기본 통계 계산
        total_posts = len(combined_data)
        korean_posts = len(all_data['korean'])
        global_posts = len(all_data['global'])
        
        # 분류별 통계
        bug_posts = len([post for post in combined_data if is_bug_post(post.get('title', ''))])
        positive_posts = len([post for post in combined_data if is_positive_post(post.get('title', ''))])
        negative_posts = len([post for post in combined_data if is_negative_post(post.get('title', ''))])
        neutral_posts = total_posts - bug_posts - positive_posts - negative_posts
        
        # 소스별 통계
        source_counts = Counter(post.get('source', 'unknown') for post in combined_data)
        top_sources = dict(source_counts.most_common(10))
        
        # 트렌드 분석
        sentiment_trends = self.trend_analyzer.analyze_sentiment_trends(combined_data, hours)
        source_trends = self.trend_analyzer.analyze_source_trends(combined_data)
        
        # 통합 트렌드 분석
        trend_analysis = {
            **sentiment_trends,
            **source_trends
        }
        
        # 인사이트 생성
        insights = self.insight_generator.generate_insights(combined_data, trend_analysis)
        recommendations = self.insight_generator.generate_recommendations(combined_data, insights)
        
        # 리포트 데이터 생성
        report_data = ReportData(
            date=datetime.now().strftime('%Y-%m-%d'),
            total_posts=total_posts,
            korean_posts=korean_posts,
            global_posts=global_posts,
            bug_posts=bug_posts,
            positive_posts=positive_posts,
            negative_posts=negative_posts,
            neutral_posts=neutral_posts,
            top_sources=top_sources,
            trend_analysis=trend_analysis,
            insights=insights,
            recommendations=recommendations
        )
        
        print(f"[INFO] 리포트 생성 완료: {total_posts}개 게시글 분석")
        return report_data
        
    def format_report_for_discord(self, report_data: ReportData) -> str:
        """Discord용 리포트 포맷팅"""
        try:
            lines = []
            
            # 헤더
            lines.append("🔍 **Epic7 일일 모니터링 리포트**")
            lines.append(f"📅 **날짜**: {report_data.date}")
            lines.append("=" * 40)
            
            # 기본 통계
            lines.append("📊 **기본 통계**")
            lines.append(f"• 총 게시글: {report_data.total_posts}개")
            lines.append(f"• 한국 사이트: {report_data.korean_posts}개")
            lines.append(f"• 글로벌 사이트: {report_data.global_posts}개")
            lines.append("")
            
            # 분류별 통계
            lines.append("🏷️ **분류별 통계**")
            lines.append(f"• 🐛 버그 리포트: {report_data.bug_posts}개")
            lines.append(f"• 😊 긍정적: {report_data.positive_posts}개")
            lines.append(f"• 😞 부정적: {report_data.negative_posts}개")
            lines.append(f"• 😐 중립적: {report_data.neutral_posts}개")
            lines.append("")
            
            # 상위 소스
            if report_data.top_sources:
                lines.append("🏆 **상위 활동 소스**")
                for source, count in list(report_data.top_sources.items())[:5]:
                    source_name = self._get_source_display_name(source)
                    lines.append(f"• {source_name}: {count}개")
                lines.append("")
                
            # 핵심 인사이트
            if report_data.insights:
                lines.append("💡 **핵심 인사이트**")
                for insight in report_data.insights[:5]:
                    lines.append(f"• {insight}")
                lines.append("")
                
            # 권장사항
            if report_data.recommendations:
                lines.append("🎯 **권장사항**")
                for recommendation in report_data.recommendations[:3]:
                    lines.append(f"• {recommendation}")
                lines.append("")
                
            # 푸터
            lines.append("─" * 40)
            lines.append(f"🤖 **생성시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            return "\n".join(lines)
            
        except Exception as e:
            print(f"[ERROR] Discord 리포트 포맷팅 실패: {e}")
            return f"❌ 리포트 생성 중 오류가 발생했습니다: {str(e)}"
            
    def _get_source_display_name(self, source: str) -> str:
        """소스 표시명 변환"""
        source_names = {
            'stove_bug': '🏪 스토브 버그게시판',
            'stove_general': '🏪 스토브 자유게시판',
            'stove_global_bug': '🌍 스토브 글로벌 버그',
            'stove_global_general': '🌍 스토브 글로벌 자유',
            'ruliweb_epic7': '🎮 루리웹 에픽세븐',
            'arca_epic7': '🔥 아카라이브 에픽세븐',
            'reddit_epic7': '🌐 Reddit EpicSeven',
            'global_forum': '🌍 글로벌 포럼'
        }
        
        return source_names.get(source, source)

class DiscordReporter:
    """Discord 리포트 전송기"""
    
    def __init__(self):
        self.webhook_url = os.environ.get('DISCORD_WEBHOOK_REPORT')
        self.max_message_length = 1900
        
    def send_daily_report(self, report_data: ReportData) -> bool:
        """일일 리포트 전송"""
        if not self.webhook_url:
            print("[WARNING] Discord 웹훅 URL이 설정되지 않았습니다.")
            return False
            
        try:
            generator = ReportGenerator()
            report_text = generator.format_report_for_discord(report_data)
            
            # 메시지 길이 확인 및 분할
            if len(report_text) > self.max_message_length:
                messages = self._split_message(report_text)
                for i, message in enumerate(messages):
                    success = self._send_message(
                        message, 
                        f"Epic7 일일 리포트 ({i+1}/{len(messages)})"
                    )
                    if not success:
                        return False
                    time.sleep(1)  # 메시지 간 대기
            else:
                success = self._send_message(report_text, "Epic7 일일 리포트")
                if not success:
                    return False
                    
            print("[INFO] Discord 일일 리포트 전송 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] Discord 리포트 전송 실패: {e}")
            return False
            
    def _split_message(self, text: str) -> List[str]:
        """메시지 분할"""
        lines = text.split('\n')
        messages = []
        current_message = ""
        
        for line in lines:
            if len(current_message + line + '\n') > self.max_message_length:
                if current_message:
                    messages.append(current_message.strip())
                current_message = line + '\n'
            else:
                current_message += line + '\n'
                
        if current_message:
            messages.append(current_message.strip())
            
        return messages
        
    def _send_message(self, message: str, title: str) -> bool:
        """메시지 전송"""
        try:
            data = {
                "embeds": [{
                    "title": title,
                    "description": message,
                    "color": 0x00ff00,
                    "timestamp": datetime.now().isoformat()
                }]
            }
            
            response = requests.post(self.webhook_url, json=data, timeout=10)
            return response.status_code == 204
            
        except Exception as e:
            print(f"[ERROR] Discord 메시지 전송 실패: {e}")
            return False

# 하위 호환성을 위한 함수들
def get_all_posts_for_report(hours: int = 24) -> List[Dict]:
    """리포트용 게시글 수집 (하위 호환성)"""
    manager = GlobalDataManager()
    all_data = manager.load_all_data(hours)
    return all_data['combined']

def send_daily_report():
    """일일 리포트 전송 (메인 함수)"""
    try:
        print("[INFO] 일일 리포트 생성 시작...")
        
        # 리포트 생성
        generator = ReportGenerator()
        report_data = generator.generate_daily_report(24)
        
        # Discord 전송
        reporter = DiscordReporter()
        success = reporter.send_daily_report(report_data)
        
        if success:
            print("[INFO] 일일 리포트 전송 완료")
            
            # 리포트 데이터 저장
            report_file = f"daily_report_{datetime.now().strftime('%Y%m%d')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(report_data), f, ensure_ascii=False, indent=2)
            print(f"[INFO] 리포트 데이터 저장: {report_file}")
            
        else:
            print("[ERROR] 일일 리포트 전송 실패")
            
    except Exception as e:
        print(f"[ERROR] 일일 리포트 처리 중 오류: {e}")
        
        # 에러 알림
        error_webhook = os.environ.get('DISCORD_WEBHOOK_BUG')
        if error_webhook:
            try:
                error_data = {
                    "embeds": [{
                        "title": "❌ 일일 리포트 생성 실패",
                        "description": f"오류 내용: {str(e)[:1000]}",
                        "color": 0xff0000,
                        "timestamp": datetime.now().isoformat()
                    }]
                }
                requests.post(error_webhook, json=error_data, timeout=10)
            except:
                pass

if __name__ == "__main__":
    send_daily_report()