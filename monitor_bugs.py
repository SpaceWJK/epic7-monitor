import argparse
import sys
import time
from datetime import datetime
from crawler import crawl_korean_sites, crawl_global_sites
from classifier import is_bug_post, classify_post
from notifier import send_bug_alert
import os

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
    """메인 실행 함수"""
    start_time = time.time()
    
    try:
        # 인자 파싱
        args = parse_arguments()
        
        print(f"[INFO] 모니터링 모드: {args.mode}")
        print(f"[INFO] 디버그 모드: {'활성화' if args.debug else '비활성화'}")
        print(f"[INFO] 테스트 모드: {'활성화' if args.test else '비활성화'}")
        
        # Discord 웹훅 설정 확인
        webhook_url = os.environ.get('DISCORD_WEBHOOK_BUG')
        print(f"[INFO] Discord 웹훅 설정됨: {'Yes' if webhook_url else 'No'}")
        
        if not webhook_url and not args.dry_run:
            print("[ERROR] DISCORD_WEBHOOK_BUG 환경변수가 설정되지 않았습니다.")
            sys.exit(1)
        
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
        
        # 버그 게시글 필터링
        bug_posts = []
        for post in all_posts:
            try:
                title = post.get('title', '')
                source = post.get('source', '')
                
                # 스토브 버그 게시판은 모든 게시글을 버그로 간주
                if source == 'stove_bug':
                    bug_posts.append(post)
                    if args.debug:
                        print(f"[BUG-STOVE-BUG] {title[:50]}...")
                        print(f"  URL: {post.get('url', '')}")
                        print(f"  시간: {post.get('timestamp', '')}")
                # 기타 사이트는 제목으로 버그 여부 판단
                elif is_bug_post(title):
                    bug_posts.append(post)
                    source_type = source.upper().replace('_', '-')
                    if args.debug:
                        print(f"[BUG-{source_type}] {title[:50]}...")
                        print(f"  URL: {post.get('url', '')}")
                        print(f"  시간: {post.get('timestamp', '')}")
                        
            except Exception as e:
                print(f"[ERROR] 게시글 처리 중 오류: {e}")
                continue
        
        print(f"[INFO] 총 {len(bug_posts)}개 버그 게시글 탐지")
        
        # 버그 알림 전송
        if bug_posts:
            if args.dry_run:
                print(f"[DRY-RUN] {len(bug_posts)}개 버그 알림 전송 시뮬레이션")
            else:
                try:
                    print(f"[INFO] {len(bug_posts)}개 버그 알림 전송 중...")
                    send_bug_alert(webhook_url, bug_posts)
                    print(f"[SUCCESS] {len(bug_posts)}개 버그 알림 전송 완료")
                except Exception as e:
                    print(f"[ERROR] 버그 알림 전송 실패: {e}")
        
        # 테스트 모드 통계
        if args.test:
            execution_time = time.time() - start_time
            print(f"[TEST] 실행 시간: {execution_time:.2f}초")
            print(f"[TEST] 총 게시글: {len(all_posts)}개")
            print(f"[TEST] 버그 게시글: {len(bug_posts)}개")
            
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