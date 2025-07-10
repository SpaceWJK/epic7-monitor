#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Epic7 모니터링 시스템 - 메인 실행 컨트롤러
아카라이브 제거 및 한국 사이트 전용 최적화 버전
"""

import sys
import os
import argparse
import time
from datetime import datetime
import json

# 로컬 모듈 임포트
try:
    from crawler import crawl_korean_sites
    from classifier import is_bug_post
    from notifier import send_bug_alert
except ImportError as e:
    print(f"[ERROR] 필수 모듈 임포트 실패: {e}")
    sys.exit(1)

def parse_arguments():
    """명령행 인자 파싱"""
    parser = argparse.ArgumentParser(
        description='Epic7 모니터링 시스템 - 한국 사이트 전용',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python monitor_bugs.py --mode korean         # 한국 사이트 크롤링
  python monitor_bugs.py --mode korean --debug # 디버그 모드
  python monitor_bugs.py --mode korean --test  # 테스트 모드
        """
    )
    
    parser.add_argument(
        '--mode', 
        choices=['korean', 'all'], 
        default='korean',
        help='모니터링 모드 선택 (기본: korean)'
    )
    
    parser.add_argument(
        '--debug', 
        action='store_true',
        help='디버그 모드 활성화 (상세 로그 출력)'
    )
    
    parser.add_argument(
        '--test', 
        action='store_true',
        help='테스트 모드 활성화 (성능 측정)'
    )
    
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='실행 시뮬레이션 (실제 알림 전송 안함)'
    )
    
    return parser.parse_args()

def setup_logging(debug_mode=False):
    """로깅 설정"""
    import logging
    
    level = logging.DEBUG if debug_mode else logging.INFO
    logging.basicConfig(
        level=level,
        format='[%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

def check_environment():
    """환경 변수 및 설정 확인"""
    required_env = ['DISCORD_WEBHOOK_BUG']
    missing_env = []
    
    for env_var in required_env:
        if not os.getenv(env_var):
            missing_env.append(env_var)
    
    if missing_env:
        print(f"[ERROR] 필수 환경 변수 누락: {', '.join(missing_env)}")
        return False
    
    return True

def filter_bug_posts(posts):
    """버그 관련 게시글 필터링"""
    bug_posts = []
    
    for post in posts:
        try:
            # 스토브 버그 게시판은 모든 게시글을 버그로 분류
            if post.get('source') == 'stove_bug':
                bug_posts.append(post)
                continue
            
            # 기타 사이트는 제목 기반 버그 분류
            if is_bug_post(post.get('title', '')):
                bug_posts.append(post)
        
        except Exception as e:
            print(f"[ERROR] 버그 필터링 중 오류: {e}")
            continue
    
    return bug_posts

def send_notifications(bug_posts, webhook_url, dry_run=False):
    """버그 알림 전송"""
    if not bug_posts:
        print("[INFO] 전송할 버그 알림 없음")
        return True
    
    if dry_run:
        print(f"[DRY-RUN] {len(bug_posts)}개 버그 알림 전송 시뮬레이션")
        for i, post in enumerate(bug_posts, 1):
            print(f"  {i}. [{post.get('source', 'unknown')}] {post.get('title', 'No title')}")
        return True
    
    try:
        print(f"[INFO] {len(bug_posts)}개 버그 알림 전송 중...")
        send_bug_alert(webhook_url, bug_posts)
        print(f"[SUCCESS] {len(bug_posts)}개 버그 알림 전송 완료")
        return True
    
    except Exception as e:
        print(f"[ERROR] 버그 알림 전송 실패: {e}")
        return False

def log_bug_posts(bug_posts, debug_mode=False):
    """버그 게시글 로깅"""
    if not bug_posts:
        return
    
    print(f"[INFO] 총 {len(bug_posts)}개 버그 게시글 탐지")
    
    for i, post in enumerate(bug_posts, 1):
        source = post.get('source', 'unknown')
        title = post.get('title', 'No title')
        
        # 소스별 태그 표시
        if source == 'stove_bug':
            tag = '[BUG-STOVE]'
        elif source == 'stove_general':
            tag = '[BUG-STOVE-GENERAL]'
        elif source == 'ruliweb_epic7':
            tag = '[BUG-RULIWEB]'
        else:
            tag = f'[BUG-{source.upper()}]'
        
        print(f"{tag} {title}")
        
        if debug_mode:
            print(f"  URL: {post.get('url', 'No URL')}")
            print(f"  시간: {post.get('timestamp', 'No timestamp')}")

def generate_status_report(execution_time, total_posts, bug_posts, sites_status):
    """실행 상태 보고서 생성"""
    report = {
        'execution_time': execution_time,
        'total_posts': total_posts,
        'bug_posts': len(bug_posts),
        'sites_status': sites_status,
        'timestamp': datetime.now().isoformat()
    }
    
    return report

def main():
    """메인 실행 함수"""
    start_time = time.time()
    
    # 명령행 인자 파싱
    args = parse_arguments()
    
    # 로깅 설정
    logger = setup_logging(args.debug)
    
    # 모드 정보 출력
    print(f"[INFO] 모니터링 모드: {args.mode}")
    print(f"[INFO] 디버그 모드: {'활성화' if args.debug else '비활성화'}")
    print(f"[INFO] 테스트 모드: {'활성화' if args.test else '비활성화'}")
    
    if args.dry_run:
        print("[INFO] DRY-RUN 모드: 실제 알림 전송 안함")
    
    # 환경 확인
    if not check_environment():
        sys.exit(1)
    
    # Discord 웹훅 URL 가져오기
    webhook_url = os.getenv('DISCORD_WEBHOOK_BUG')
    print(f"[INFO] Discord 웹훅 설정됨: {'Yes' if webhook_url else 'No'}")
    
    # 사이트 상태 추적
    sites_status = {}
    all_posts = []
    
    try:
        # 한국 사이트 크롤링
        if args.mode in ['korean', 'all']:
            print("[INFO] === 한국 사이트 크롤링 시작 ===")
            
            korean_posts = crawl_korean_sites()
            all_posts.extend(korean_posts)
            
            # 사이트별 상태 업데이트
            sites_status['korean'] = {
                'success': True,
                'posts_count': len(korean_posts),
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"[INFO] 한국 사이트: {len(korean_posts)}개 새 게시글")
        
        # 버그 게시글 필터링
        bug_posts = filter_bug_posts(all_posts)
        
        # 버그 게시글 로깅
        log_bug_posts(bug_posts, args.debug)
        
        # 버그 알림 전송
        if bug_posts:
            notification_success = send_notifications(bug_posts, webhook_url, args.dry_run)
            if not notification_success:
                print("[WARN] 버그 알림 전송 중 일부 실패")
        else:
            print("[INFO] 새로운 버그 게시글 없음")
        
        # 실행 시간 계산
        execution_time = time.time() - start_time
        
        # 테스트 모드: 성능 보고서
        if args.test:
            status_report = generate_status_report(
                execution_time, 
                len(all_posts), 
                bug_posts, 
                sites_status
            )
            print(f"[TEST] 실행 시간: {execution_time:.2f}초")
            print(f"[TEST] 총 게시글: {len(all_posts)}개")
            print(f"[TEST] 버그 게시글: {len(bug_posts)}개")
            print(f"[TEST] 사이트 상태: {json.dumps(sites_status, indent=2, ensure_ascii=False)}")
        
        print(f"[SUCCESS] 모니터링 완료 - 실행 시간: {execution_time:.2f}초")
        
    except KeyboardInterrupt:
        print("\n[INFO] 사용자에 의해 중단됨")
        sys.exit(0)
    
    except Exception as e:
        print(f"[ERROR] 예상치 못한 오류 발생: {e}")
        
        if args.debug:
            import traceback
            traceback.print_exc()
        
        sys.exit(1)

if __name__ == "__main__":
    main()