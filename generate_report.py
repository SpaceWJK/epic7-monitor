from crawler import get_all_posts_for_report
from classifier import is_positive_post, is_negative_post, is_bug_post
from notifier import send_daily_report
import os
from datetime import datetime
import traceback

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_REPORT")

def main():
    try:
        print(f"[INFO] 일일 리포트 생성 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[INFO] Discord 웹훅 설정됨: {'Yes' if WEBHOOK_URL else 'No'}")
        
        # 일일 리포트용 게시글 수집 (새 게시글만이 아닌 최근 게시글들)
        posts = get_all_posts_for_report()
        
        if not posts:
            print("[INFO] 분석할 게시글이 없습니다.")
            return
        
        print(f"[INFO] 총 {len(posts)}개 게시글 분석 중...")
        
        # 카테고리별 분류
        report = {
            "긍정": [],
            "부정": [], 
            "버그": [],
            "기타": []
        }
        
        for post in posts:
            try:
                title = post.get("title", "")
                
                if is_bug_post(title) or post.get("source") == "stove_bug":
                    report["버그"].append(post)
                elif is_positive_post(title):
                    report["긍정"].append(post)
                elif is_negative_post(title):
                    report["부정"].append(post)
                else:
                    report["기타"].append(post)
                    
            except Exception as e:
                print(f"[ERROR] 게시글 분류 중 오류: {e}")
                continue
        
        # 결과 요약
        total = sum(len(posts) for posts in report.values())
        print(f"[INFO] 분류 결과:")
        print(f"  - 긍정: {len(report['긍정'])}개")
        print(f"  - 부정: {len(report['부정'])}개") 
        print(f"  - 버그: {len(report['버그'])}개")
        print(f"  - 기타: {len(report['기타'])}개")
        print(f"  - 총합: {total}개")
        
        # Discord 리포트 전송
        if WEBHOOK_URL:
            try:
                send_daily_report(WEBHOOK_URL, report)
                print("[SUCCESS] 일일 리포트 전송 완료")
            except Exception as e:
                print(f"[ERROR] 일일 리포트 전송 실패: {e}")
                traceback.print_exc()
        else:
            print("[ERROR] DISCORD_WEBHOOK_REPORT 환경변수가 설정되지 않음")
            
    except Exception as e:
        print(f"[ERROR] 일일 리포트 생성 중 치명적 오류: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
