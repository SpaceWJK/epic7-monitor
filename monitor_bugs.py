import argparse
import sys
import time
from datetime import datetime
from crawler import crawl_korean_sites, crawl_global_sites
from classifier import classify_post
from notifier import send_bug_alert, send_sentiment_alert
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

def main():
    """메인 실행 함수 - 웹훅 환경변수 처리 및 에러 핸들링 강화"""
    start_time = time.time()
    
    try:
        # 인자 파싱
        args = parse_arguments()
        
        print(f"[INFO] 모니터링 모드: {args.mode}")
        print(f"[INFO] 디버그 모드: {'활성화' if args.debug else '비활성화'}")
        print(f"[INFO] 테스트 모드: {'활성화' if args.test else '비활성화'}")
        
        # 웹훅 설정 확인 (개선된 환경변수 처리)
        bug_webhook_url = os.environ.get('DISCORD_WEBHOOK_BUG')
        sentiment_webhook_url = os.environ.get('DISCORD_WEBHOOK_SENTIMENT')
        
        print(f"[INFO] 버그 알림 웹훅 설정됨: {'Yes' if bug_webhook_url else 'No'}")
        print(f"[INFO] 감성 동향 웹훅 설정됨: {'Yes' if sentiment_webhook_url else 'No'}")
        
        # 웹훅 설정 검증
        if not bug_webhook_url and not args.dry_run:
            print("[ERROR] DISCORD_WEBHOOK_BUG 환경변수가 설정되지 않았습니다.")
            sys.exit(1)
        
        if not sentiment_webhook_url and not args.dry_run:
            print("[WARNING] DISCORD_WEBHOOK_SENTIMENT 환경변수가 설정되지 않았습니다.")
            print("[WARNING] 감성 동향 알림이 비활성화됩니다.")
        
        # SentimentDataManager 초기화 및 에러 핸들링 강화
        try:
            sentiment_manager = SentimentDataManager()
            
            # 월간 데이터 정리 (에러 핸들링 추가)
            try:
                sentiment_manager.cleanup_old_monthly_data()
                if args.debug:
                    print("[DEBUG] 월간 데이터 정리 완료")
            except AttributeError as e:
                print(f"[WARNING] 월간 데이터 정리 함수 호출 실패: {e}")
                # 대체 함수 시도
                try:
                    if hasattr(sentiment_manager, 'process_monthly_transition'):
                        sentiment_manager.process_monthly_transition()
                        print("[DEBUG] 대체 월간 정리 함수 사용")
                except Exception as fallback_error:
                    print(f"[WARNING] 대체 월간 정리도 실패: {fallback_error}")
            except Exception as e:
                print(f"[ERROR] 월간 데이터 정리 중 오류: {e}")
                if args.debug:
                    traceback.print_exc()
                    
        except Exception as e:
            print(f"[ERROR] SentimentDataManager 초기화 실패: {e}")
            if args.debug:
                traceback.print_exc()
            # 데이터 관리자 없이 계속 진행
            sentiment_manager = None
        
        # 사이트별 크롤링 실행
        all_posts = []
        
        if args.mode == 'korean':
            print("[INFO] 한국 사이트 크롤링 시작...")
            korean_posts = crawl_korean_sites()
            all_posts.extend(korean_posts)
            print(f"[INFO] 한국 사이트: {len(korean_posts)}개 새 게시글")
            
        elif args.mode == 'all':
            print("[INFO] 모든 사이트 크롤링 시작...")
            korean_posts = crawl_korean_sites()
            all_posts.extend(korean_posts)
            print(f"[INFO] 한국 사이트: {len(korean_posts)}개 새 게시글")
            
            # 크롤링 간 지연
            time.sleep(10)
            
            global_posts = crawl_global_sites()
            all_posts.extend(global_posts)
            print(f"[INFO] 글로벌 사이트: {len(global_posts)}개 새 게시글")
        
        print(f"[INFO] 총 {len(all_posts)}개 새 게시글 발견")
        
        if not all_posts:
            print("[INFO] 새로운 게시글이 없습니다.")
            return
        
        # 게시글 분류 및 알림 처리
        bug_posts = []
        sentiment_posts = {"긍정": [], "중립": [], "부정": []}
        
        for post in all_posts:
            try:
                title = post.get('title', '')
                source = post.get('source', '')
                
                # 스토브 버그 게시판은 모든 게시글을 버그로 간주
                if source == 'stove_bug':
                    bug_posts.append(post)
                    if args.debug:
                        print(f"[BUG-STOVE-BUG] {title[:50]}...")
                else:
                    # 기타 사이트는 제목으로 분류
                    category = classify_post(title)
                    
                    if category == "버그":
                        bug_posts.append(post)
                        if args.debug:
                            source_type = source.upper().replace('_', '-')
                            print(f"[BUG-{source_type}] {title[:50]}...")
                    else:
                        # 감성 분류 (긍정/중립/부정)
                        if category in sentiment_posts:
                            sentiment_posts[category].append(post)
                            if args.debug:
                                print(f"[SENTIMENT-{category.upper()}] {title[:50]}...")
                        
            except Exception as e:
                print(f"[ERROR] 게시글 분류 중 오류: {e}")
                if args.debug:
                    traceback.print_exc()
                continue
        
        # 분류 결과 로깅
        total_sentiment = sum(len(posts) for posts in sentiment_posts.values())
        print(f"[INFO] 분류 결과:")
        print(f"  🐛 버그: {len(bug_posts)}개")
        print(f"  😊 긍정: {len(sentiment_posts['긍정'])}개")
        print(f"  😐 중립: {len(sentiment_posts['중립'])}개")
        print(f"  😞 부정: {len(sentiment_posts['부정'])}개")
        print(f"  📊 총 감성: {total_sentiment}개")
        
        # 감성 데이터 저장 (SentimentDataManager 사용)
        if sentiment_manager and total_sentiment > 0:
            try:
                all_sentiment_posts = []
                for category, posts in sentiment_posts.items():
                    for post in posts:
                        post['category'] = category
                        all_sentiment_posts.append(post)
                
                sentiment_manager.save_sentiment_data(all_sentiment_posts)
                if args.debug:
                    print(f"[DEBUG] {len(all_sentiment_posts)}개 감성 데이터 저장 완료")
                    
            except Exception as e:
                print(f"[ERROR] 감성 데이터 저장 실패: {e}")
                if args.debug:
                    traceback.print_exc()
        
        # 버그 알림 전송
        if bug_posts and bug_webhook_url:
            if args.dry_run:
                print(f"[DRY-RUN] {len(bug_posts)}개 버그 알림 전송 시뮬레이션")
            else:
                try:
                    print(f"[INFO] {len(bug_posts)}개 버그 알림 전송 중...")
                    send_bug_alert(bug_webhook_url, bug_posts)
                    print(f"[SUCCESS] {len(bug_posts)}개 버그 알림 전송 완료")
                except Exception as e:
                    print(f"[ERROR] 버그 알림 전송 실패: {e}")
                    if args.debug:
                        traceback.print_exc()
        
        # 감성 동향 알림 전송 (새로운 기능)
        if total_sentiment > 0 and sentiment_webhook_url:
            if args.dry_run:
                print(f"[DRY-RUN] {total_sentiment}개 감성 동향 알림 전송 시뮬레이션")
            else:
                try:
                    print(f"[INFO] {total_sentiment}개 감성 동향 알림 전송 중...")
                    send_sentiment_alert(sentiment_webhook_url, sentiment_posts)
                    print(f"[SUCCESS] {total_sentiment}개 감성 동향 알림 전송 완료")
                except Exception as e:
                    print(f"[ERROR] 감성 동향 알림 전송 실패: {e}")
                    if args.debug:
                        traceback.print_exc()
        elif total_sentiment > 0 and not sentiment_webhook_url:
            print(f"[WARNING] 감성 동향 {total_sentiment}개 있지만 웹훅 미설정으로 알림 생략")
        
        # 테스트 모드 통계
        if args.test:
            execution_time = time.time() - start_time
            print(f"[TEST] 실행 시간: {execution_time:.2f}초")
            print(f"[TEST] 총 게시글: {len(all_posts)}개")
            print(f"[TEST] 버그 게시글: {len(bug_posts)}개")
            print(f"[TEST] 감성 게시글: {total_sentiment}개")
            
            # 사이트별 통계
            site_stats = {}
            for post in all_posts:
                source = post.get('source', 'unknown')
                site_stats[source] = site_stats.get(source, 0) + 1
            
            print("[TEST] 사이트별 통계:")
            for source, count in site_stats.items():
                print(f"  - {source}: {count}개")
            
            # 시스템 상태 보고
            status_report = {
                args.mode: {
                    "success": True,
                    "posts_count": len(all_posts),
                    "bug_count": len(bug_posts),
                    "sentiment_count": total_sentiment,
                    "timestamp": datetime.now().isoformat()
                }
            }
            print(f"[TEST] 사이트 상태: {status_report}")
        
        execution_time = time.time() - start_time
        print(f"[SUCCESS] 모니터링 완료 - 실행 시간: {execution_time:.2f}초")
        
    except KeyboardInterrupt:
        print("\n[INFO] 사용자에 의해 중단됨")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] 예상치 못한 오류: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()