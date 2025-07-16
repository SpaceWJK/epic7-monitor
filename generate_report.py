# generate_report.py

from classifier import classify_post, is_positive_post, is_negative_post, is_neutral_post
from notifier import send_daily_report
from sentiment_data_manager import SentimentDataManager
import os
from datetime import datetime, timedelta
import traceback

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_REPORT")

def main():
    """일일 감성 동향 보고서 생성 (글로벌 지원 및 구문 오류 수정)"""
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
        
        # 전날 00:00 ~ 23:59 모든 데이터 조회
        yesterday_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        yesterday_end = yesterday_start + timedelta(days=1)
        
        # 구문 오류 수정: 변수 정의 추가
        yesterday = yesterday_start.strftime('%Y-%m-%d')
        yesterday_data = data_manager.get_daily_data(yesterday)
        
        if debug_mode:
            print(f"[DEBUG] 전날 데이터 조회: {yesterday} -> {len(yesterday_data)}개")
        
        # 강제 실행이 아닌 경우, 데이터가 없으면 현재 데이터 사용
        if not yesterday_data and not force_report:
            today = datetime.now().strftime('%Y-%m-%d')
            yesterday_data = data_manager.get_daily_data(today)
            print(f"[INFO] 전날 데이터 없음, 현재 데이터 사용: {len(yesterday_data)}개")
        
        # 들여쓰기 오류 수정
        if not yesterday_data:
            print("[INFO] 분석할 감성 데이터가 없습니다.")
            if not force_report:
                print("[INFO] 데이터 없음 - 상태 메시지 전송")
                send_daily_report(WEBHOOK_URL, "데이터 없음")
                return
            else:
                print("[INFO] 강제 실행 모드 - 빈 보고서 생성")
        
        print(f"[INFO] 총 {len(yesterday_data)}개 감성 데이터 분석 중...")
        
        # 글로벌 지원: 소스별 분류 추가
        source_stats = {
            "Korean": {
                "ruliweb_epic7": [],
                "stove_bug": [],
                "stove_general": []
            },
            "Global": {
                "STOVE Global Bug": [],
                "STOVE Global General": [],
                "Reddit": []
            }
        }
        
        # 감성 카테고리별 분류 (글로벌 지원)
        sentiment_report = {
            "긍정": {
                "Korean": [],
                "Global": [],
                "total": []
            },
            "중립": {
                "Korean": [],
                "Global": [],
                "total": []
            },
            "부정": {
                "Korean": [],
                "Global": [],
                "total": []
            }
        }
        
        bug_count = {"Korean": 0, "Global": 0, "total": 0}
        
        for data_item in yesterday_data:
            try:
                category = data_item.get("category", "중립")
                source = data_item.get("source", "")
                
                # 소스별 분류 (글로벌 지원)
                region = get_source_region(source)
                
                # 소스별 통계 업데이트
                if region in source_stats and source in source_stats[region]:
                    source_stats[region][source].append(data_item)
                
                # 버그 관련 게시글은 개수만 카운트
                if category == "버그":
                    bug_count[region] += 1
                    bug_count["total"] += 1
                    continue
                
                # 감성 카테고리별 분류 (지역별 구분)
                if category in sentiment_report:
                    post_data = {
                        "title": data_item.get("title", ""),
                        "url": data_item.get("url", ""),
                        "source": source,
                        "timestamp": data_item.get("timestamp", ""),
                        "category": category,
                        "region": region
                    }
                    sentiment_report[category][region].append(post_data)
                    sentiment_report[category]["total"].append(post_data)
                else:
                    # 기타 카테고리는 중립으로 분류
                    post_data = {
                        "title": data_item.get("title", ""),
                        "url": data_item.get("url", ""),
                        "source": source,
                        "timestamp": data_item.get("timestamp", ""),
                        "category": "중립",
                        "region": region
                    }
                    sentiment_report["중립"][region].append(post_data)
                    sentiment_report["중립"]["total"].append(post_data)
                    
            except Exception as e:
                print(f"[ERROR] 데이터 처리 중 오류: {e}")
                continue
        
        # 감성 분석 결과 요약 (글로벌 지원)
        total_sentiment = sum(len(sentiment_report[cat]["total"]) for cat in sentiment_report)
        total_analyzed = total_sentiment + bug_count["total"]
        
        print(f"[INFO] 글로벌 감성 분석 결과:")
        print(f"  📊 총 분석 대상: {total_analyzed}개 게시글")
        print(f"  🇰🇷 한국 사이트: {get_region_total(sentiment_report, 'Korean') + bug_count['Korean']}개")
        print(f"  🌍 글로벌 사이트: {get_region_total(sentiment_report, 'Global') + bug_count['Global']}개")
        
        if total_sentiment > 0:
            print(f"  😊 긍정: {len(sentiment_report['긍정']['total'])}개 ({len(sentiment_report['긍정']['total'])/total_sentiment*100:.1f}%)")
            print(f"  😐 중립: {len(sentiment_report['중립']['total'])}개 ({len(sentiment_report['중립']['total'])/total_sentiment*100:.1f}%)")
            print(f"  😞 부정: {len(sentiment_report['부정']['total'])}개 ({len(sentiment_report['부정']['total'])/total_sentiment*100:.1f}%)")
        else:
            print(f"  😊 긍정: 0개")
            print(f"  😐 중립: 0개")
            print(f"  😞 부정: 0개")
        
        print(f"  🐛 버그: {bug_count['total']}개 (실시간 알림 처리)")
        print(f"  📈 감성 총합: {total_sentiment}개")
        
        # 소스별 상세 통계 출력
        print_source_statistics(source_stats)
        
        # 글로벌 감성 동향 분석
        sentiment_analysis = analyze_global_sentiment_trends(sentiment_report)
        
        # Discord 일일 감성 보고서 전송 (글로벌 지원)
        if WEBHOOK_URL:
            try:
                send_daily_global_sentiment_report(WEBHOOK_URL, sentiment_report, sentiment_analysis, bug_count, source_stats)
                print("[SUCCESS] 일일 글로벌 감성 동향 보고서 전송 완료")
            except Exception as e:
                print(f"[ERROR] 일일 감성 보고서 전송 실패: {e}")
                traceback.print_exc()
        else:
            print("[ERROR] DISCORD_WEBHOOK_REPORT 환경변수가 설정되지 않음")
            
    except Exception as e:
        print(f"[ERROR] 일일 감성 보고서 생성 중 치명적 오류: {e}")
        traceback.print_exc()

def get_source_region(source):
    """소스명으로 지역 구분"""
    korean_sources = ["ruliweb_epic7", "stove_bug", "stove_general"]
    global_sources = ["STOVE Global Bug", "STOVE Global General", "Reddit"]
    
    if source in korean_sources:
        return "Korean"
    elif source in global_sources:
        return "Global"
    else:
        return "Korean"  # 기본값

def get_region_total(sentiment_report, region):
    """지역별 감성 게시글 총 개수"""
    return sum(len(sentiment_report[cat][region]) for cat in sentiment_report)

def print_source_statistics(source_stats):
    """소스별 통계 출력"""
    print(f"\n[INFO] 소스별 상세 통계:")
    
    for region, sources in source_stats.items():
        print(f"  📍 {region}:")
        for source, posts in sources.items():
            print(f"    • {source}: {len(posts)}개")

def analyze_global_sentiment_trends(sentiment_report):
    """글로벌 감성 동향 분석 및 인사이트 생성"""
    try:
        total = sum(len(sentiment_report[cat]["total"]) for cat in sentiment_report)
        
        if total == 0:
            return {
                "trend": "데이터 부족",
                "insight": "분석할 게시글이 없습니다.",
                "recommendation": "데이터 수집 상태를 확인해보세요.",
                "korean_trend": "데이터 없음",
                "global_trend": "데이터 없음"
            }
        
        # 전체 감성 비율
        positive_ratio = len(sentiment_report['긍정']['total']) / total
        negative_ratio = len(sentiment_report['부정']['total']) / total
        neutral_ratio = len(sentiment_report['중립']['total']) / total
        
        # 지역별 감성 비율
        korean_total = get_region_total(sentiment_report, 'Korean')
        global_total = get_region_total(sentiment_report, 'Global')
        
        korean_trend = "데이터 없음"
        global_trend = "데이터 없음"
        
        if korean_total > 0:
            korean_positive = len(sentiment_report['긍정']['Korean']) / korean_total
            korean_negative = len(sentiment_report['부정']['Korean']) / korean_total
            korean_trend = determine_trend(korean_positive, korean_negative)
        
        if global_total > 0:
            global_positive = len(sentiment_report['긍정']['Global']) / global_total
            global_negative = len(sentiment_report['부정']['Global']) / global_total
            global_trend = determine_trend(global_positive, global_negative)
        
        # 전체 동향 결정
        overall_trend = determine_trend(positive_ratio, negative_ratio)
        
        # 인사이트 생성
        insight = generate_global_insight(positive_ratio, negative_ratio, neutral_ratio, korean_total, global_total)
        
        # 권장사항 생성
        recommendation = generate_global_recommendation(positive_ratio, negative_ratio, korean_trend, global_trend)
        
        return {
            "trend": overall_trend,
            "insight": insight,
            "recommendation": recommendation,
            "korean_trend": korean_trend,
            "global_trend": global_trend,
            "ratios": {
                "positive": positive_ratio,
                "negative": negative_ratio,
                "neutral": neutral_ratio
            },
            "region_stats": {
                "korean_total": korean_total,
                "global_total": global_total
            }
        }
        
    except Exception as e:
        print(f"[ERROR] 글로벌 감성 동향 분석 중 오류: {e}")
        return {
            "trend": "분석 실패",
            "insight": "감성 동향 분석 중 오류가 발생했습니다.",
            "recommendation": "시스템 로그를 확인하세요.",
            "korean_trend": "분석 실패",
            "global_trend": "분석 실패"
        }

def determine_trend(positive_ratio, negative_ratio):
    """감성 비율로 트렌드 결정"""
    if positive_ratio > 0.5:
        return "긍정적"
    elif negative_ratio > 0.4:
        return "부정적"
    elif positive_ratio + negative_ratio < 0.4:
        return "중립적"
    else:
        return "혼재"

def generate_global_insight(positive_ratio, negative_ratio, neutral_ratio, korean_total, global_total):
    """글로벌 인사이트 생성"""
    total_posts = korean_total + global_total
    
    if total_posts == 0:
        return "분석할 게시글이 없습니다."
    
    korean_ratio = korean_total / total_posts if total_posts > 0 else 0
    global_ratio = global_total / total_posts if total_posts > 0 else 0
    
    insight = f"전체 {total_posts}개 게시글 중 "
    insight += f"한국 사이트 {korean_ratio*100:.1f}%, 글로벌 사이트 {global_ratio*100:.1f}%로 구성. "
    
    if positive_ratio > 0.5:
        insight += f"긍정적 반응이 {positive_ratio*100:.1f}%로 높은 편입니다."
    elif negative_ratio > 0.4:
        insight += f"부정적 반응이 {negative_ratio*100:.1f}%로 주의가 필요합니다."
    else:
        insight += f"중립적 분위기({neutral_ratio*100:.1f}%)로 안정적입니다."
    
    return insight

def generate_global_recommendation(positive_ratio, negative_ratio, korean_trend, global_trend):
    """글로벌 권장사항 생성"""
    if negative_ratio > 0.3:
        recommendation = "부정적 피드백 증가 - 한국/글로벌 커뮤니티 모니터링 강화 필요"
    elif positive_ratio > 0.6:
        recommendation = "긍정적 분위기 유지 - 글로벌 확산 이벤트 고려"
    elif korean_trend == "부정적" and global_trend == "긍정적":
        recommendation = "한국 커뮤니티 집중 관리 - 글로벌 성공 사례 벤치마킹"
    elif korean_trend == "긍정적" and global_trend == "부정적":
        recommendation = "글로벌 커뮤니티 개선 - 한국 성공 사례 글로벌 적용"
    else:
        recommendation = "전반적으로 안정적 - 현재 수준 유지"
    
    return recommendation

def send_daily_global_sentiment_report(webhook_url, sentiment_report, analysis, bug_count, source_stats):
    """일일 글로벌 감성 동향 보고서 전송"""
    try:
        # 글로벌 감성 보고서 데이터 구성
        report_data = {
            "sentiment_report": sentiment_report,
            "analysis": analysis,
            "bug_count": bug_count,
            "source_stats": source_stats,
            "exclude_bugs": True,
            "data_source": "stored",
            "report_type": "global"  # 글로벌 리포트 플래그
        }
        
        # 기존 send_daily_report 함수 활용
        send_daily_report(webhook_url, report_data)
        
    except Exception as e:
        print(f"[ERROR] 글로벌 감성 보고서 전송 중 오류: {e}")
        raise

if __name__ == "__main__":
    main()