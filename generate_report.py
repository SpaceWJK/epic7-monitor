from classifier import classify_post, is_positive_post, is_negative_post, is_neutral_post
from notifier import send_daily_report
from sentiment_data_manager import SentimentDataManager
import os
from datetime import datetime, timedelta
import traceback

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_REPORT")

def main():
    """일일 감성 동향 보고서 생성 (저장된 데이터 활용)"""
    try:
        print(f"[INFO] 일일 감성 동향 보고서 생성 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[INFO] Discord 웹훅 설정됨: {'Yes' if WEBHOOK_URL else 'No'}")
        
        # 강제 실행 모드 확인
        force_report = os.environ.get("FORCE_REPORT", "false").lower() == "true"
        debug_mode = os.environ.get("DEBUG_MODE", "false").lower() == "true"
        
        if debug_mode:
            print("🐛 디버그 모드로 실행")
        
        # SentimentDataManager 초기화
        data_manager = SentimentDataManager()
        
        # 전날 데이터 조회
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        yesterday_data = data_manager.get_daily_data(yesterday)
        
        if debug_mode:
            print(f"[DEBUG] 전날 데이터 조회: {yesterday} -> {len(yesterday_data)}개")
        
        # 강제 실행이 아닌 경우, 데이터가 없으면 현재 데이터 사용
        if not yesterday_data and not force_report:
            today = datetime.now().strftime('%Y-%m-%d')
            yesterday_data = data_manager.get_daily_data(today)
            print(f"[INFO] 전날 데이터 없음, 현재 데이터 사용: {len(yesterday_data)}개")
        
        if not yesterday_data:
            print("[INFO] 분석할 감성 데이터가 없습니다.")
            if not force_report:
                return
            else:
                print("[INFO] 강제 실행 모드 - 빈 보고서 생성")
        
        print(f"[INFO] 총 {len(yesterday_data)}개 감성 데이터 분석 중...")
        
        # 감성 카테고리별 분류
        sentiment_report = {
            "긍정": [],
            "중립": [],
            "부정": []
        }
        
        bug_count = 0  # 버그 게시글 수 (참고용)
        
        for data_item in yesterday_data:
            try:
                category = data_item.get("category", "중립")
                
                # 버그 관련 게시글은 개수만 카운트
                if category == "버그":
                    bug_count += 1
                    continue
                
                # 감성 카테고리만 보고서에 포함
                if category in sentiment_report:
                    # 저장된 데이터 구조에 맞춰 변환
                    post_data = {
                        "title": data_item.get("title", ""),
                        "url": data_item.get("url", ""),
                        "source": data_item.get("source", ""),
                        "timestamp": data_item.get("timestamp", ""),
                        "category": category
                    }
                    sentiment_report[category].append(post_data)
                else:
                    # 기타 카테고리는 중립으로 분류
                    post_data = {
                        "title": data_item.get("title", ""),
                        "url": data_item.get("url", ""),
                        "source": data_item.get("source", ""),
                        "timestamp": data_item.get("timestamp", ""),
                        "category": "중립"
                    }
                    sentiment_report["중립"].append(post_data)
                    
            except Exception as e:
                print(f"[ERROR] 데이터 처리 중 오류: {e}")
                continue
        
        # 감성 분석 결과 요약
        total_sentiment = sum(len(posts) for posts in sentiment_report.values())
        total_analyzed = total_sentiment + bug_count
        
        print(f"[INFO] 감성 분석 결과:")
        print(f"  📊 분석 대상: {total_analyzed}개 게시글")
        
        if total_sentiment > 0:
            print(f"  😊 긍정: {len(sentiment_report['긍정'])}개 ({len(sentiment_report['긍정'])/total_sentiment*100:.1f}%)")
            print(f"  😐 중립: {len(sentiment_report['중립'])}개 ({len(sentiment_report['중립'])/total_sentiment*100:.1f}%)")
            print(f"  😞 부정: {len(sentiment_report['부정'])}개 ({len(sentiment_report['부정'])/total_sentiment*100:.1f}%)")
        else:
            print(f"  😊 긍정: 0개")
            print(f"  😐 중립: 0개")
            print(f"  😞 부정: 0개")
        
        print(f"  🐛 버그: {bug_count}개 (실시간 알림 처리)")
        print(f"  📈 감성 총합: {total_sentiment}개")
        
        # 감성 동향 분석
        sentiment_analysis = analyze_sentiment_trends(sentiment_report)
        
        # Discord 일일 감성 보고서 전송
        if WEBHOOK_URL:
            try:
                send_daily_sentiment_report(WEBHOOK_URL, sentiment_report, sentiment_analysis, bug_count)
                print("[SUCCESS] 일일 감성 동향 보고서 전송 완료")
            except Exception as e:
                print(f"[ERROR] 일일 감성 보고서 전송 실패: {e}")
                traceback.print_exc()
        else:
            print("[ERROR] DISCORD_WEBHOOK_REPORT 환경변수가 설정되지 않음")
            
    except Exception as e:
        print(f"[ERROR] 일일 감성 보고서 생성 중 치명적 오류: {e}")
        traceback.print_exc()

def analyze_sentiment_trends(sentiment_report):
    """감성 동향 분석 및 인사이트 생성"""
    try:
        total = sum(len(posts) for posts in sentiment_report.values())
        
        if total == 0:
            return {
                "trend": "데이터 부족",
                "insight": "분석할 게시글이 없습니다.",
                "recommendation": "데이터 수집 상태를 확인해보세요."
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
            "recommendation": "시스템 로그를 확인하세요."
        }

def send_daily_sentiment_report(webhook_url, sentiment_report, analysis, bug_count):
    """일일 감성 동향 보고서 전송 (저장된 데이터 활용)"""
    try:
        # 감성 보고서 데이터 구성
        report_data = {
            "sentiment_report": sentiment_report,
            "analysis": analysis,
            "bug_count": bug_count,
            "exclude_bugs": True,  # 버그 제외 플래그
            "data_source": "stored"  # 저장된 데이터 사용 표시
        }
        
        # 기존 send_daily_report 함수 활용
        send_daily_report(webhook_url, report_data)
        
    except Exception as e:
        print(f"[ERROR] 감성 보고서 전송 중 오류: {e}")
        raise

if __name__ == "__main__":
    main()