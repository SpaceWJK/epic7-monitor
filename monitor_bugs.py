import sys
import json
import traceback
from crawler import crawl_arca_sites, crawl_global_sites
from classifier import is_bug_post
from notifier import send_bug_alert
import os

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_BUG")

def parse_arguments():
    """명령행 인자 파싱"""
    mode = "arca"  # 기본값
    
    # --mode 방식과 직접 인자 방식 모두 지원
    if len(sys.argv) >= 3 and sys.argv[1] == "--mode":
        mode = sys.argv[2]
    elif len(sys.argv) >= 2:
        mode = sys.argv[1]
    
    return mode

def main():
    try:
        mode = parse_arguments()
        print(f"[INFO] 모니터링 모드: {mode}")
        print(f"[INFO] Discord 웹훅 설정됨: {'Yes' if WEBHOOK_URL else 'No'}")
        
        # 모드별 크롤링
        posts = []
        if mode == "arca":
            posts = crawl_arca_sites()
        elif mode == "global":
            posts = crawl_global_sites()
        elif mode == "all":
            # all 모드: arca와 global 모두 실행
            print("[INFO] 전체 모드: ARCA + GLOBAL 동시 실행")
            arca_posts = crawl_arca_sites()
            global_posts = crawl_global_sites()
            posts = arca_posts + global_posts
            print(f"[INFO] ARCA: {len(arca_posts)}개, GLOBAL: {len(global_posts)}개 게시글")
        else:
            print(f"[ERROR] 알 수 없는 모드: {mode}")
            print("[INFO] 지원되는 모드: arca, global, all")
            return
        
        # 새로 발견된 게시글 확인
        if not posts:
            print("[INFO] 새로운 게시글이 없습니다.")
            return
        
        print(f"[INFO] 총 {len(posts)}개 새 게시글 발견")
        
        # 버그 게시글 필터링
        bugs = []
        for post in posts:
            try:
                # 스토브 버그 게시판은 무조건 버그로 분류
                if post.get("source") == "stove_bug":
                    bugs.append(post)
                    print(f"[BUG-STOVE] {post['title'][:50]}...")
                # 다른 게시판은 키워드로 필터링
                elif is_bug_post(post["title"]):
                    bugs.append(post)
                    print(f"[BUG-KEYWORD] {post['title'][:50]}...")
            except Exception as e:
                print(f"[ERROR] 게시글 분류 중 오류: {e}")
                continue
        
        print(f"[INFO] 버그 게시글 {len(bugs)}개 탐지")
        
        # Discord 알림 전송
        if bugs:
            if WEBHOOK_URL:
                print("[INFO] Discord로 버그 알림 전송 중...")
                try:
                    send_bug_alert(WEBHOOK_URL, bugs)
                    print(f"[SUCCESS] {len(bugs)}개 버그 알림 전송 완료")
                except Exception as e:
                    print(f"[ERROR] Discord 알림 전송 실패: {e}")
                    traceback.print_exc()
            else:
                print("[ERROR] DISCORD_WEBHOOK_BUG 환경변수가 설정되지 않음")
                print("[INFO] 발견된 버그들:")
                for i, bug in enumerate(bugs, 1):
                    print(f"  {i}. {bug['title']}")
                    print(f"     {bug['url']}")
        else:
            print("[INFO] 알림할 버그 게시글이 없습니다.")
            
    except Exception as e:
        print(f"[ERROR] 모니터링 실행 중 치명적 오류: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
