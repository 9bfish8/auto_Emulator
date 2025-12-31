#!/usr/bin/env python3
"""
에뮬레이터 버전 모니터링 + Teams 알림 스크립트
JSON(내가 관리하는 버전)과 최신 버전 비교해서 Teams로 표 형식 전송
릴리즈 날짜 포함
※ JSON은 자동 저장 안 함 - 직접 수정해서 관리
"""

import requests
import re
import json
import urllib3
from datetime import datetime, timezone, timedelta
from pathlib import Path

# SSL 경고 무시 (LDPlayer API용)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================
# 설정
# ============================================================
TEAMS_WEBHOOK_URL = ""
VERSION_FILE = Path(__file__).parent / "emulator_versions.json"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# KST 타임존
KST = timezone(timedelta(hours=9))

# ============================================================
# 버전 비교 함수
# ============================================================

def parse_version(version_str):
    """버전 문자열을 비교 가능한 튜플로 변환"""
    try:
        return tuple(int(x) for x in version_str.split('.'))
    except (ValueError, AttributeError):
        return (0,)


def compare_versions(my_ver, latest_ver):
    """
    버전 비교 후 상태 반환
    - 'same': 동일
    - 'upgrade': 최신 버전이 더 높음 (업데이트 필요)
    - 'downgrade': 최신 버전이 더 낮음 (다운그레이드 감지)
    """
    my_tuple = parse_version(my_ver)
    latest_tuple = parse_version(latest_ver)

    if my_tuple == latest_tuple:
        return 'same'
    elif my_tuple < latest_tuple:
        return 'upgrade'
    else:
        return 'downgrade'


# ============================================================
# 버전 크롤링 함수들
# ============================================================

def get_nox_version():
    """NoxPlayer - 공식 다운로드 API (버전 + 날짜)"""
    try:
        url = "https://kr.bignox.com/kr/download/fullPackage"
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=False)

        if resp.status_code == 302:
            location = resp.headers.get('Location', '')

            # 버전 추출: nox_setup_v7.0.6.2_full_intl.exe
            ver_match = re.search(r'v([\d.]+)_', location)
            version = ver_match.group(1) if ver_match else None

            # 날짜 추출: /full/20250317/ -> 2025-03-17
            date_match = re.search(r'/full/(\d{4})(\d{2})(\d{2})/', location)
            release_date = None
            if date_match:
                release_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

            if version:
                return {"name": "NoxPlayer", "version": version, "release_date": release_date}

    except Exception as e:
        return {"name": "NoxPlayer", "error": str(e)}
    return {"name": "NoxPlayer", "error": "Version not found"}


def get_memu_version():
    """MEmu - 릴리즈 노트 (버전 + 날짜)"""
    try:
        url = "https://www.memuplay.com/blog/category/release-notes"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()

        # 버전: "MEmu 9.3.1 is officially released"
        ver_match = re.search(r'MEmu\s+([\d.]+)\s+is officially released', resp.text)

        # 날짜: "December 8, 2025" 형식
        date_match = re.search(r'>(\w+\s+\d{1,2},?\s+\d{4})<', resp.text)

        release_date = None
        if date_match:
            date_str = date_match.group(1).replace(',', '')
            try:
                date_obj = datetime.strptime(date_str, "%B %d %Y")
                release_date = date_obj.strftime('%Y-%m-%d')
            except ValueError:
                pass

        if ver_match:
            return {"name": "MEmu", "version": ver_match.group(1), "release_date": release_date}
    except Exception as e:
        return {"name": "MEmu", "error": str(e)}
    return {"name": "MEmu", "error": "Version not found"}


def get_ldplayer_version():
    """LDPlayer9 - 공식 API (버전) + 한국어 버전 히스토리 (날짜)"""
    try:
        # 1. 공식 API에서 버전
        url = "https://apikr2.ldmnq.com/checkMnqVersion"
        params = {
            "pid": "dnplayer-kr9",
            "openid": "172",
            "t": "20251219112033",
            "sv": "0900010000",
            "n": "7a12ef8a4b748c85d9c7151d76942bd4",
            "updatetype": "0"
        }
        api_headers = {'User-Agent': 'LDPlayer'}

        resp = requests.get(url, params=params, headers=api_headers, timeout=10, verify=False)

        version = None
        if resp.status_code == 200 and resp.text:
            url_match = re.search(r'LDPlayer_([\d.]+)\.exe', resp.text)
            if url_match:
                version = url_match.group(1)

        # 2. 한국어 버전 히스토리에서 날짜
        release_date = None
        if version:
            try:
                history_url = "https://kr.ldplayer.net/other/version-history-and-release-notes.html"
                history_resp = requests.get(history_url, headers=HEADERS, timeout=15, verify=False)
                if history_resp.status_code == 200:
                    # 버전→날짜 패턴: "9.1.85.0 ... 2025-12-02" (2000자 내)
                    pattern = rf'{re.escape(version)}.{{0,2000}}(\d{{4}}-\d{{2}}-\d{{2}})'
                    date_match = re.search(pattern, history_resp.text, re.DOTALL)
                    if date_match:
                        release_date = date_match.group(1)
            except Exception:
                pass

        if version:
            return {"name": "LDPlayer9", "version": version, "release_date": release_date}

    except Exception as e:
        return {"name": "LDPlayer9", "error": str(e)}
    return {"name": "LDPlayer9", "error": "Version not found"}


def get_bluestacks_version():
    """BlueStacks5 - 공식 API + Zendesk (버전 + 날짜)"""
    try:
        # 1. 공식 API에서 버전
        url = "https://cloud.bluestacks.com/api/getdownloadnow"
        params = {
            "platform": "win",
            "oem": "BlueStacks",
            "bluestacks_version": "bs5"
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10, allow_redirects=False)

        version = None
        if resp.status_code == 302:
            location = resp.headers.get('Location', '')
            match = re.search(r'(\d+\.\d+\.\d+\.\d+)', location)
            if match:
                version = match.group(1)

        # 2. Zendesk API에서 날짜
        release_date = None
        try:
            zendesk_url = "https://support.bluestacks.com/api/v2/help_center/articles/360056960211.json"
            zendesk_resp = requests.get(zendesk_url, headers=HEADERS, timeout=10)
            if zendesk_resp.status_code == 200:
                data = zendesk_resp.json()
                edited_at = data.get('article', {}).get('edited_at', '')
                if edited_at:
                    # ISO 형식에서 날짜만 추출
                    release_date = edited_at[:10]  # "2025-12-12T06:53:22Z" -> "2025-12-12"
        except Exception:
            pass

        if version:
            return {"name": "BlueStacks5", "version": version, "release_date": release_date}

    except Exception as e:
        return {"name": "BlueStacks5", "error": str(e)}
    return {"name": "BlueStacks5", "error": "Version not found"}


def get_mumu_version():
    """MuMu Player - 공식 API (버전 + 날짜)"""
    try:
        url = "https://api.mumuglobal.com/api/appcast"
        params = {
            "version": "3.8.18.2845",
            "engine": "NEMUX",
            "uuid": "version-check",
            "usage": "1",
            "package": "mumu",
            "channel": "gw-overseas",
            "architecture": "x86_64",
            "language": "ko",
            "country": "ko-KR"
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()

        data = resp.json()
        if data.get("items"):
            item = data["items"][0]
            version = item.get("version", "")

            # 버전에서 앞 3자리만
            parts = version.split(".")
            if len(parts) >= 3:
                version = ".".join(parts[:3])

            # releaseNoteList에서 날짜 추출: "V5.13.1 (20251212)"
            release_date = None
            release_note_list = item.get("releaseNoteList", [])
            if release_note_list:
                first_note = release_note_list[0]
                date_match = re.search(r'\((\d{4})(\d{2})(\d{2})\)', first_note)
                if date_match:
                    release_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

            return {"name": "MuMuPlayer", "version": version, "release_date": release_date}
    except Exception as e:
        return {"name": "MuMuPlayer", "error": str(e)}
    return {"name": "MuMuPlayer", "error": "Version not found"}


# ============================================================
# 버전 로드 (저장 없음!)
# ============================================================

def load_my_versions():
    """내가 관리하는 버전 정보 로드"""
    if VERSION_FILE.exists():
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


# ============================================================
# Teams 알림
# ============================================================

def send_teams_notification(current_versions, my_versions):
    """Teams로 내 버전 + 최신 버전 표 전송 (날짜 포함)"""
    if not TEAMS_WEBHOOK_URL or TEAMS_WEBHOOK_URL == "YOUR_TEAMS_WEBHOOK_URL_HERE":
        print("⚠️  Teams Webhook URL이 설정되지 않았습니다.")
        return False

    # 표 형식 마크다운 생성 (날짜 컬럼 추가)
    table_header = "| 제품명 | 현재 버전 | 최신 버전 | 릴리즈 날짜 | 상태 |\n|:---|:---:|:---:|:---:|:---:|\n"
    table_rows = []
    upgrade_count = 0
    downgrade_count = 0

    # 에뮬레이터 순서 정의
    emulator_order = ["NoxPlayer", "MEmu", "LDPlayer9", "BlueStacks5", "MuMuPlayer"]

    for name in emulator_order:
        if name in current_versions:
            latest = current_versions[name].get('version', '-')
            my_ver = my_versions.get(name, {}).get('version', '-')
            release_date = current_versions[name].get('release_date', '-') or '-'

            # 상태 판단
            if 'error' in current_versions[name]:
                status = "❌ 오류"
                latest = current_versions[name].get('error', '-')[:20]
            elif my_ver == '-':
                status = "🆕 신규"
            else:
                change = compare_versions(my_ver, latest)
                if change == 'same':
                    status = "✅ 동일"
                elif change == 'upgrade':
                    status = "⬆️ 업데이트"
                    upgrade_count += 1
                else:  # downgrade
                    status = "⬇️ 다운그레이드"
                    downgrade_count += 1

            table_rows.append(f"| {name} | {my_ver} | {latest} | {release_date} | {status} |")

    table_md = table_header + "\n".join(table_rows)

    # 요약 메시지 생성
    summary_parts = []
    if upgrade_count > 0:
        summary_parts.append(f"⬆️ {upgrade_count}개 업데이트")
    if downgrade_count > 0:
        summary_parts.append(f"⬇️ {downgrade_count}개 다운그레이드")

    if summary_parts:
        summary_text = f"**🔔 {', '.join(summary_parts)} 감지!**"
        if downgrade_count > 0:
            theme_color = "FFA500"  # 주황색 (다운그레이드 포함)
        else:
            theme_color = "FF6600"  # 주황색 (업데이트만)
    else:
        summary_text = "✅ 모든 에뮬레이터 최신 버전"
        theme_color = "0076D7"  # 파란색

    # KST 시간
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S") + " KST"

    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": theme_color,
        "summary": "에뮬레이터 버전 현황",
        "sections": [
            {
                "activityTitle": "📊 에뮬레이터 버전 현황",
                "activitySubtitle": now_kst,
                "markdown": True
            },
            {
                "text": table_md,
                "markdown": True
            },
            {
                "text": summary_text,
                "markdown": True
            }
        ]
    }

    try:
        response = requests.post(TEAMS_WEBHOOK_URL, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Teams 전송 실패: {e}")
        return False


# ============================================================
# 메인 실행
# ============================================================

def main():
    now_kst = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S') + " KST"

    print(f"\n{'='*60}")
    print(f"에뮬레이터 버전 체크 - {now_kst}")
    print(f"{'='*60}\n")

    # 내가 관리하는 버전 로드
    my_versions = load_my_versions()

    # 크롤러 목록
    checkers = [
        get_nox_version,
        get_memu_version,
        get_ldplayer_version,
        get_bluestacks_version,
        get_mumu_version,
    ]

    current_versions = {}

    for checker in checkers:
        result = checker()
        name = result.get('name', 'Unknown')
        current_versions[name] = result

        if 'error' in result:
            print(f"❌ {name}: {result['error']}")
        else:
            latest = result.get('version')
            release_date = result.get('release_date', '-') or '-'
            my_ver = my_versions.get(name, {}).get('version', '-')

            if my_ver == '-':
                print(f"🆕 {name}: {latest} ({release_date}) - 신규")
            else:
                change = compare_versions(my_ver, latest)
                if change == 'same':
                    print(f"✅ {name}: {latest} ({release_date})")
                elif change == 'upgrade':
                    print(f"⬆️ {name}: {my_ver} → {latest} ({release_date}) - 업데이트 필요")
                else:
                    print(f"⬇️ {name}: {my_ver} → {latest} ({release_date}) - 다운그레이드 감지")

    # Teams 알림 전송
    print(f"\n{'='*60}")
    if send_teams_notification(current_versions, my_versions):
        print("✅ Teams 알림 전송 완료")
    else:
        print("❌ Teams 알림 전송 실패")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
