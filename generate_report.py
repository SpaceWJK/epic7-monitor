from classifier import classify_post, is_positive_post, is_negative_post, is_neutral_post
from notifier import send_daily_report
from sentiment_data_manager import SentimentDataManager
import os
from datetime import datetime, timedelta
import traceback

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_REPORT")

def main():
    """일일 감성 동향 보고서 생성 (24시간 누적 데이터 활용)"""
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
        
        # 전날 24시간 데이터 조회 (00:00 ~ 23:59)
        now = datetime.now()
        yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday_start.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        print(f"[INFO] 데이터 조회 범위: {yesterday_start.strftime('%Y-%m-%d %H:%M:%S')} ~ {yesterday_end.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 24시간 누적 데이터 조회
        daily_data = data_manager.get_daily_data_range(yesterday_start, yesterday_end)
        
        if not daily_data:
            print("[WARNING] 전날 데이터가 없음")
            if force_report or debug_mode:
                # 강제 실행이거나 디버그 모드면 빈 리포트 전송
                empty_report = generate_empty_report(yesterday_start.strftime('%Y-%m-%d'))
                if WEBHOOK_URL:
                    send_daily_report(empty_report)
                else:
                    print("[ERROR] Discord 웹훅이 설정되지 않아 리포트 전송 불가")
            return
        
        print(f"[INFO] 전날 24시간 데이터: {len(daily_data)}개 항목")
        
        # 리포트 생성
        report_content = generate_daily_report(daily_data, yesterday_start.strftime('%Y-%m-%d'))
        
        if debug_mode:
            print(f"[DEBUG] 생성된 리포트:\n{report_content}")
        
        # Discord로 전송
        if WEBHOOK_URL:
            success = send_daily_report(report_content)
            if success:
                print("[SUCCESS] 일일 리포트 전송 완료")
            else:
                print("[ERROR] 일일 리포트 전송 실패")
        else:
            print("[ERROR] DISCORD_WEBHOOK_REPORT가 설정되지 않아 리포트 전송 불가")
            return
        
        print(f"[INFO] 일일 리포트 생성 완료 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"[ERROR] 일일 리포트 생성 중 오류: {e}")
        if debug_mode:
            traceback.print_exc()

def generate_daily_report(data, date_str):
    """24시간 누적 데이터로 일간 리포트 생성"""
    total_posts = len(data)
    
    # 감성별 분류
    positive_count = 0
    negative_count = 0
    neutral_count = 0
    
    # 사이트별 분류
    site_stats = {}
    
    for item in data:
        sentiment = item.get('sentiment', '중립')
        site = item.get('site', '알 수 없음')
        
        # 감성 카운트
        if sentiment == '긍정':
            positive_count += 1
        elif sentiment == '부정':
            negative_count += 1
        else:
            neutral_count += 1
        
        # 사이트별 카운트
        site_stats[site] = site_stats.get(site, 0) + 1
    
    # 감성 비율 계산
    positive_rate = (positive_count / total_posts * 100) if total_posts > 0 else 0
    negative_rate = (negative_count / total_posts * 100) if total_posts > 0 else 0
    neutral_rate = (neutral_count / total_posts * 100) if total_posts > 0 else 0
    
    # 리포트 내용 생성
    report = f"""
**📅 {date_str} 유저 동향 분석**

**📊 전체 현황**
• 총 게시글: {total_posts}개
• 데이터 수집: 24시간 누적

**😊 감성 분석**
• 긍정: {positive_count}개 ({positive_rate:.1f}%)
• 부정: {negative_count}개 ({negative_rate:.1f}%)
• 중립: {neutral_count}개 ({neutral_rate:.1f}%)

**🌐 사이트별 현황**
"""
    
    for site, count in site_stats.items():
        percentage = (count / total_posts * 100) if total_posts > 0 else 0
        report += f"• {site}: {count}개 ({percentage:.1f}%)\n"
    
    # 전체적인 동향 판단
    if positive_rate > negative_rate + 10:
        trend = "긍정적 😊"
    elif negative_rate > positive_rate + 10:
        trend = "부정적 😞"
    else:
        trend = "안정적 😐"
    
    report += f"""
**📈 전체 동향**
{trend} (긍정 {positive_rate:.1f}% vs 부정 {negative_rate:.1f}%)

전날 24시간 동안 수집된 모든 데이터를 기반으로 한 종합 분석입니다.
"""
    
    return report.strip()

def generate_empty_report(date_str):
    """데이터가 없을 때 빈 리포트 생성"""
    return f"""
**📅 {date_str} 유저 동향 분석**

**📊 전체 현황**
• 총 게시글: 0개
• 수집된 데이터가 없습니다.

**📝 상태**
해당 날짜에 수집된 동향 데이터가 없습니다.
시스템이 정상 동작하지 않았거나 새로운 게시글이 없었을 가능성이 있습니다.

전날 24시간 기준으로 데이터를 조회했습니다.
"""

if __name__ == "__main__":
    main()