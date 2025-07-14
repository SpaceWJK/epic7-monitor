import argparse
import sys
import time
from datetime import datetime
from crawler import crawl_korean_sites, crawl_global_sites
from classifier import classify_post
from notifier import send_bug_alert, send_sentiment_alert, send_monitoring_status
from sentiment_data_manager import SentimentDataManager
import os
import traceback

def parse_arguments():
    """명령행 인자 파싱"""
    parser = argparse.ArgumentParser(description='Epic7 Bug Monitor')
    parser.add_argument('--mode', choices=['korean', 'all'], default='korean',
                        help='모니터링 모드: korean (한국 사이트), all (모든 사이트)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드')
    parser.add_argument('--test', action='store_true', help='테스트 모드')
    parser.add_argument('--dry-run', action='store_true', help='실제 알림 전송 없이 시뮬레이션')
    return parser.parse_args()

def process_posts(posts, mode='korean', debug=False, dry_run=False):
    """게시글 처리 - 버그/일반 분리 처리"""
    if not posts:
        print("[INFO] 크롤링된 게시글이 없음")
        # 빈 크롤링 상태 메시지 전송
        if not dry_run:
            send_sentiment_alert([])  # 빈 리스트로 상태 메시지 전송
        return
    
    print(f"[INFO] 총 {len(posts)}개 게시글 처리 시작")
    
    bug_posts = []
    sentiment_posts = []
    data_manager = SentimentDataManager()
    
    for post in posts:
        title = post.get('title', '')
        url = post.get('url', '')
        site = post.get('site', '')
        
        if debug:
            print(f"[DEBUG] 처리 중: {title[:50]}...")
        
        # 게시글 분류
        post_type = classify_post(title)
        
        if post_type == "버그":
            # 버그 게시글 - 즉시 알림
            bug_posts.append(post)
            
            if not dry_run:
                print(f"[ALERT] 버그 발견: {title}")
                send_bug_alert(title, url, site, severity="보통")
                time.sleep(2)  # Discord API 제한 고려
        
        else:
            # 일반 게시글 - 감성 분석 후 동향 데이터로 누적
            sentiment = analyze_sentiment(title)
            post['sentiment'] = sentiment
            sentiment_posts.append(post)
            
            # 감성 데이터 저장
            data_manager.add_post(
                title=title,
                url=url,
                site=site,
                sentiment=sentiment,
                timestamp=datetime.now().isoformat()
            )
            
            if debug:
                print(f"[SENTIMENT] {sentiment}: {title[:30]}...")
    
    # 감성 데이터 저장
    data_manager.save_data()
    
    # 단건별 동향 알림 전송 (일반 게시글들)
    if sentiment_posts and not dry_run:
        print(f"[INFO] {len(sentiment_posts)}개 동향 게시글 단건별 알림 전송")
        send_sentiment_alert(sentiment_posts)
    
    print(f"[SUMMARY] 버그: {len(bug_posts)}개, 동향: {len(sentiment_posts)}개")

def analyze_sentiment(title):
    """간단한 감성 분석"""
    from classifier import is_positive_post, is_negative_post
    
    if is_positive_post(title):
        return "긍정"
    elif is_negative_post(title):
        return "부정"
    else:
        return "중립"

def main():
    """메인 실행 함수 - 웹훅 환경변수 처리 및 에러 핸들링 강화"""
    start_time = time.time()
    
    try:
        # 인자 파싱
        args = parse_arguments()
        
        print(f"[INFO] Epic7 버그 모니터링 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[INFO] 모니터링 모드: {args.mode}")
        print(f"[INFO] 디버그 모드: {'활성화' if args.debug else '비활성화'}")
        print(f"[INFO] 테스트 모드: {'활성화' if args.test else '비활성화'}")
        
        # 환경변수 확인 및 상태 출력
        webhook_bug = os.environ.get("DISCORD_WEBHOOK_BUG")
        webhook_sentiment = os.environ.get("DISCORD_WEBHOOK_SENTIMENT") 
        webhook_report = os.environ.get("DISCORD_WEBHOOK_REPORT")
        
        print(f"[INFO] 버그 알림 웹훅 설정됨: {'Yes' if webhook_bug else 'No'}")
        print(f"[INFO] 감성 동향 웹훅 설정됨: {'Yes' if webhook_sentiment else 'No'}")
        print(f"[INFO] 일간 리포트 웹훅 설정됨: {'Yes' if webhook_report else 'No'}")
        
        # 환경변수 경고
        if not webhook_bug:
            print("Warning: DISCORD_WEBHOOK_BUG 환경변수가 설정되지 않았습니다.")
        if not webhook_sentiment:
            print("Warning: DISCORD_WEBHOOK_SENTIMENT 환경변수가 설정되지 않았습니다.")
            print("Warning: 감성 동향 알림이 비활성화됩니다.")
        if not webhook_report:
            print("Warning: DISCORD_WEBHOOK_REPORT 환경변수가 설정되지 않았습니다.")
        
        # SentimentDataManager 초기화 및 정리
        data_manager = SentimentDataManager()
        data_manager.cleanup_old_data()
        print("[DEBUG] 월간 데이터 정리 완료")
        
        # 크롤링 실행
        posts = []
        
        if args.mode == 'korean':
            print("[INFO] 한국 사이트 크롤링 시작...")
            print("[INFO] === 한국 사이트 크롤링 시작 ===")
            
            try:
                posts = crawl_korean_sites(debug=args.debug)
                print(f"[INFO] 한국 사이트 크롤링 완료: {len(posts)}개 게시글")
            except Exception as e:
                print(f"[ERROR] 한국 사이트 크롤링 실패: {e}")
                if args.debug:
                    traceback.print_exc()
                
                # 크롤링 실패 알림
                if not args.dry_run:
                    send_monitoring_status(f"한국 사이트 크롤링 실패: {str(e)}")
        
        elif args.mode == 'all':
            print("[INFO] 전체 사이트 크롤링 시작...")
            
            try:
                # 한국 사이트
                korean_posts = crawl_korean_sites(debug=args.debug)
                print(f"[INFO] 한국 사이트: {len(korean_posts)}개")
                
                # 글로벌 사이트 (현재 미구현)
                global_posts = []  # crawl_global_sites(debug=args.debug)
                print(f"[INFO] 글로벌 사이트: {len(global_posts)}개")
                
                posts = korean_posts + global_posts
                print(f"[INFO] 전체 크롤링 완료: {len(posts)}개 게시글")
                
            except Exception as e:
                print(f"[ERROR] 전체 사이트 크롤링 실패: {e}")
                if args.debug:
                    traceback.print_exc()
        
        # 게시글 처리
        process_posts(posts, mode=args.mode, debug=args.debug, dry_run=args.dry_run)
        
        # 실행 시간 계산
        execution_time = time.time() - start_time
        print(f"[INFO] 모니터링 완료 - 실행 시간: {execution_time:.2f}초")
        
        # 성공 상태 메시지 (디버그 모드에서만)
        if args.debug and not args.dry_run:
            status_msg = f"모니터링 완료: {len(posts)}개 게시글 처리 ({execution_time:.2f}초)"
            send_monitoring_status(status_msg)
    
    except KeyboardInterrupt:
        print("\n[INFO] 사용자에 의해 중단됨")
        sys.exit(0)
        
    except Exception as e:
        print(f"[ERROR] 심각한 오류 발생: {e}")
        if args.debug:
            traceback.print_exc()
        
        # 오류 알림 전송
        try:
            if not args.dry_run:
                send_monitoring_status(f"시스템 오류 발생: {str(e)}")
        except:
            pass
        
        sys.exit(1)

if __name__ == "__main__":
    main()