#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
from datetime import datetime, timedelta
import traceback
from sentiment_data_manager import SentimentDataManager
from notifier import send_daily_report

# Discord 웹훅 URL
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_REPORT")

def main():
    """일일 감성 동향 보고서 생성 (저장된 데이터 활용)"""
    try:
        current_time = datetime.now()
        print(f"[INFO] 일일 감성 동향 보고서 생성 시작 - {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[INFO] Discord 웹훅 설정됨: {'Yes' if WEBHOOK_URL else 'No'}")
        
        if not WEBHOOK_URL:
            print("[ERROR] DISCORD_WEBHOOK_REPORT 환경변수가 설정되지 않음")
            return
        
        # 데이터 관리자 초기화
        data_manager = SentimentDataManager()
        
        # 전날 데이터 가져오기 (보고서는 전날 데이터 기준)
        yesterday = current_time - timedelta(days=1)
        yesterday_key = yesterday.strftime('%Y-%m-%d')
        
        print(f"[INFO] 전날 데이터 조회 중: {yesterday_key}")
        
        # 전날 감성 데이터 로드
        yesterday_data = data_manager.get_daily_data(yesterday_key)
        
        if not yesterday_data:
            print(f"[INFO] {yesterday_key} 데이터가 없습니다. 빈 보고서를 생성합니다.")
            yesterday_data = []
        
        print(f"[INFO] {yesterday_key} 데이터: {len(yesterday_data)}개 게시글")
        
        # 감성 카테고리별 분류
        sentiment_report = {
            "긍정": [],
            "중립": [],
            "부정": []
        }
        
        bug_count = 0  # 버그 게시글 수 (참고용)
        
        # 데이터 분류
        for post in yesterday_data:
            try:
                category = post.get("category", "중립")
                
                # 버그 관련 게시글은 개수만 카운트
                if category == "버그":
                    bug_count += 1
                    continue
                
                # 감성 카테고리만 보고서에 포함
                if category in sentiment_report:
                    sentiment_report[category].append(post)
                else:
                    # 알 수 없는 카테고리는 중립으로 분류
                    sentiment_report["중립"].append(post)
                    
            except Exception as e:
                print(f"[ERROR] 게시글 분류 중 오류: {e}")
                continue
        
        # 감성 분석 결과 요약
        total_sentiment = sum(len(posts) for posts in sentiment_report.values())
        total_analyzed = total_sentiment + bug_count
        
        print(f"[INFO] 감성 분석 결과 ({yesterday_key}):")
        if total_analyzed > 0:
            print(f"  📊 분석 대상: {total_analyzed}개 게시글")
            print(f"  😊 긍정: {len(sentiment_report['긍정'])}개 ({len(sentiment_report['긍정'])/total_sentiment*100:.1f}%)")
            print(f"  😐 중립: {len(sentiment_report['중립'])}개 ({len(sentiment_report['중립'])/total_sentiment*100:.1f}%)")
            print(f"  😞 부정: {len(sentiment_report['부정'])}개 ({len(sentiment_report['부정'])/total_sentiment*100:.1f}%)")
            print(f"  🐛 버그: {bug_count}개 (실시간 알림 처리됨)")
            print(f"  📈 감성 총합: {total_sentiment}개")
        else:
            print(f"  📊 분석된 게시글이 없습니다.")
        
        # 감성 동향 분석
        sentiment_analysis = analyze_sentiment_trends(sentiment_report, yesterday_key)
        
        # 주간 트렌드 분석 (지난 7일간 데이터)
        weekly_trend = analyze_weekly_trend(data_manager, current_time)
        
        # Discord 일일 감성 보고서 전송
        try:
            report_data = {
                "date": yesterday_key,
                "sentiment_report": sentiment_report,
                "analysis": sentiment_analysis,
                "weekly_trend": weekly_trend,
                "bug_count": bug_count,
                "total_posts": total_analyzed
            }
            
            send_daily_report(WEBHOOK_URL, report_data)
            print("[SUCCESS] 일일 감성 동향 보고서 전송 완료")
            
        except Exception as e:
            print(f"[ERROR] 일일 감성 보고서 전송 실패: {e}")
            traceback.print_exc()
            
    except Exception as e:
        print(f"[ERROR] 일일 감성 보고서 생성 중 치명적 오류: {e}")
        traceback.print_exc()

def analyze_sentiment_trends(sentiment_report, date_key):
    """감성 동향 분석 및 인사이트 생성"""
    try:
        total = sum(len(posts) for posts in sentiment_report.values())
        
        if total == 0:
            return {
                "trend": "데이터 없음",
                "insight": f"{date_key}에 분석할 게시글이 없습니다.",
                "recommendation": "게시글 수집 상태를 확인해보세요.",
                "ratios": {"positive": 0, "negative": 0, "neutral": 0}
            }
        
        positive_ratio = len(sentiment_report['긍정']) / total
        negative_ratio = len(sentiment_report['부정']) / total
        neutral_ratio = len(sentiment_report['중립']) / total
        
        # 주요 동향 결정
        if positive_ratio > 0.5:
            trend = "긍정적"
            insight = f"유저들의 긍정적 반응이 {positive_ratio*100:.1f}%로 높습니다."
        elif negative_ratio > 0.4:
            trend = "부정적"
            insight = f"유저들의 부정적 반응이 {negative_ratio*100:.1f}%로 높습니다."
        elif neutral_ratio > 0.6:
            trend = "중립적"
            insight = f"대부분의 게시글이 중립적이며 ({neutral_ratio*100:.1f}%), 안정적인 커뮤니티 상태입니다."
        else:
            trend = "혼재"
            insight = "긍정, 부정, 중립 반응이 골고루 분포되어 있습니다."
        
        # 권장사항 생성
        if negative_ratio > 0.3:
            recommendation = "부정적 피드백 증가에 대한 모니터링을 강화하세요."
        elif positive_ratio > 0.6:
            recommendation = "긍정적 분위기를 유지할 수 있는 이벤트나 업데이트를 고려하세요."
        else:
            recommendation = "현재 커뮤니티 분위기가 안정적입니다."
        
        return {
            "trend": trend,
            "insight": insight,
            "recommendation": recommendation,
            "ratios": {
                "positive": positive_ratio,
                "negative": negative_ratio,
                "neutral": neutral_ratio
            }
        }
        
    except Exception as e:
        print(f"[ERROR] 감성 동향 분석 중 오류: {e}")
        return {
            "trend": "분석 실패",
            "insight": "감성 동향 분석 중 오류가 발생했습니다.",
            "recommendation": "시스템 로그를 확인하세요.",
            "ratios": {"positive": 0, "negative": 0, "neutral": 0}
        }

def analyze_weekly_trend(data_manager, current_time):
    """주간 트렌드 분석 (지난 7일간)"""
    try:
        weekly_data = []
        
        # 지난 7일간 데이터 수집
        for i in range(7):
            target_date = current_time - timedelta(days=i+1)
            date_key = target_date.strftime('%Y-%m-%d')
            daily_data = data_manager.get_daily_data(date_key)
            
            if daily_data:
                # 일별 감성 분포 계산
                day_sentiments = {"긍정": 0, "중립": 0, "부정": 0, "버그": 0}
                for post in daily_data:
                    category = post.get("category", "중립")
                    if category in day_sentiments:
                        day_sentiments[category] += 1
                
                weekly_data.append({
                    "date": date_key,
                    "sentiments": day_sentiments,
                    "total": sum(day_sentiments.values())
                })
        
        if not weekly_data:
            return {
                "trend": "데이터 부족",
                "average_daily_posts": 0,
                "dominant_sentiment": "알 수 없음",
                "week_summary": "지난 7일간 데이터가 부족합니다."
            }
        
        # 주간 통계 계산
        total_posts = sum(day["total"] for day in weekly_data)
        average_daily_posts = total_posts / len(weekly_data)
        
        # 주간 감성 합계
        week_sentiments = {"긍정": 0, "중립": 0, "부정": 0, "버그": 0}
        for day in weekly_data:
            for sentiment, count in day["sentiments"].items():
                week_sentiments[sentiment] += count
        
        # 주요 감성 결정
        sentiment_without_bug = {k: v for k, v in week_sentiments.items() if k != "버그"}
        dominant_sentiment = max(sentiment_without_bug, key=sentiment_without_bug.get)
        
        # 트렌드 분석
        if len(weekly_data) >= 3:
            recent_avg = sum(day["total"] for day in weekly_data[:3]) / 3
            older_avg = sum(day["total"] for day in weekly_data[3:]) / max(1, len(weekly_data) - 3)
            
            if recent_avg > older_avg * 1.2:
                trend = "증가"
            elif recent_avg < older_avg * 0.8:
                trend = "감소"
            else:
                trend = "안정"
        else:
            trend = "분석 불가"
        
        return {
            "trend": trend,
            "average_daily_posts": round(average_daily_posts, 1),
            "dominant_sentiment": dominant_sentiment,
            "week_summary": f"지난 7일간 평균 {average_daily_posts:.1f}개 게시글, 주요 감성: {dominant_sentiment}",
            "total_week_posts": total_posts
        }
        
    except Exception as e:
        print(f"[ERROR] 주간 트렌드 분석 중 오류: {e}")
        return {
            "trend": "분석 실패",
            "average_daily_posts": 0,
            "dominant_sentiment": "알 수 없음",
            "week_summary": "주간 트렌드 분석 중 오류가 발생했습니다."
        }

def get_top_posts_by_sentiment(sentiment_report, limit=3):
    """감성 카테고리별 대표 게시글 추출"""
    try:
        top_posts = {}
        
        for category, posts in sentiment_report.items():
            if posts:
                # 최신 게시글 순으로 정렬하여 상위 추출
                sorted_posts = sorted(posts, 
                                    key=lambda x: x.get('timestamp', ''), 
                                    reverse=True)
                top_posts[category] = sorted_posts[:limit]
            else:
                top_posts[category] = []
        
        return top_posts
        
    except Exception as e:
        print(f"[ERROR] 대표 게시글 추출 중 오류: {e}")
        return {}

def cleanup_old_reports():
    """30일 이상된 임시 리포트 파일 정리"""
    try:
        import glob
        import os
        
        report_files = glob.glob("daily_report_*.json")
        current_time = datetime.now()
        
        for file in report_files:
            try:
                file_stat = os.stat(file)
                file_age = current_time - datetime.fromtimestamp(file_stat.st_mtime)
                
                if file_age.days > 30:
                    os.remove(file)
                    print(f"[INFO] 오래된 리포트 파일 삭제: {file}")
                    
            except Exception as e:
                print(f"[ERROR] 파일 {file} 정리 중 오류: {e}")
                
    except Exception as e:
        print(f"[ERROR] 리포트 파일 정리 중 오류: {e}")

if __name__ == "__main__":
    main()
    cleanup_old_reports()