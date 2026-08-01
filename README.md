# BoomyBoom & Biz Insight Daily Brief

매일 **정오 12:00 KST**에 비즈니스 유튜버·뉴스레터·해외/국내 매체에서 **돈 되는 인사이트**를 종합해서
- 💡 **비즈 브리핑** (인사이트·트렌드·사례·도구)
- 📝 **뉴스레터 원고** (르코&렉스 톤)
- 📤 **채널별 변환본** (블로그·스레드·인스타·유튜브 — 복사해서 바로 업로드)
- 🌐 **웹 대시보드** (GitHub Pages) 업데이트 + 📲 **텔레그램** 푸시

> ⚠️ 정보 제공용. 특정 수익·투자를 보장하지 않으며, 인용 사례·수치는 각 출처의 주장입니다. 원문 복제 없이 요약·재구성 + 출처 표기 원칙.

## 구조
| 파일 | 역할 |
|---|---|
| `run_daily_brief.sh` | launchd가 12:00에 실행 → Claude headless 생성 → 알림 |
| `BRIEF_PROMPT.md` | 생성 지침 (브리핑 + 뉴스레터 + 변환본, JSON 스키마) |
| `BRIEFING_GUIDE.md` | 소스·저작권·안전·중복 규칙 |
| `sources.json` | 수집 소스 (유튜버·뉴스레터·매체, 편집 가능) |
| `briefs/YYYY-MM-DD.json` | 그날 데이터 (30일 후 자동 삭제) |
| `posts/YYYY-MM-DD/` | 뉴스레터·채널 변환본 .md (복붙용) |
| `index.html` | 웹 대시보드 (탭·복사 버튼) |
| `telegram_notify.py` | 텔레그램 요약 푸시 |
| `com.boomyboom.bizbrief.plist` | launchd 스케줄 (12:00 KST) |

## 설정 (.env)
```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
CLAUDE_BIN=/path/to/claude
SITE_URL=https://boomyboom.github.io/biz-daily-brief/
```

## 스케줄러 등록
```bash
cp com.boomyboom.bizbrief.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.boomyboom.bizbrief.plist
```
