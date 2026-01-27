#!/usr/bin/env python3
"""
에뮬레이터 버전 모니터링 + Teams 알림 스크립트
JSON(내가 관리하는 버전)과 최신 버전 비교해서 Teams로 표 형식 전송
※ JSON은 자동 저장 안 함 - 직접 수정해서 관리
"""

import requests
import re
import json
import urllib3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode

# SSL 경고 무시 (LDPlayer API용)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================
# 설정
# ============================================================
TEAMS_WEBHOOK_URL = ""
WEB_APP_URL = "https://9bfish8.github.io/Emulator_Mail_Generator"
VERSION_FILE = Path(__file__).parent / "emulator_versions.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# 에뮬레이터 순서 (Teams 표시 및 URL 생성용)
EMULATOR_ORDER = ["NoxPlayer", "MEmu", "LDPlayer9", "BlueStacks5", "MuMuPlayer"]

# KST 타임존
KST = timezone(timedelta(hours=9))

# ============================================================
# 버전 크롤링 함수들
# ============================================================

def get_nox_version():
    """NoxPlayer - 한국 공식 사이트"""
    try:
        url = "https://kr.bignox.com/"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        match = re.search(r'([\d.]+)버전', resp.text)
        if match:
            return {"name": "NoxPlayer", "version": match.group(1)}
    except Exception as e:
        return {"name": "NoxPlayer", "error": str(e)}
    return {"name": "NoxPlayer", "error": "Version not found"}


def get_memu_version():
    """MEmu - 릴리즈 노트"""
    try:
        url = "https://www.memuplay.com/blog/category/release-notes"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        match = re.search(r'MEmu\s+([\d.]+)\s+is officially released', resp.text)
        if match:
            return {"name": "MEmu", "version": match.group(1)}
    except Exception as e:
        return {"name": "MEmu", "error": str(e)}
    return {"name": "MEmu", "error": "Version not found"}


def get_ldplayer_version():
    """LDPlayer9 - 공식 API"""
    try:
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
        if resp.status_code == 200 and resp.text:
            match = re.search(r'LDPlayer_([\d.]+)\.exe', resp.text)
            if match:
                return {"name": "LDPlayer9", "version": match.group(1)}
    except Exception as e:
        return {"name": "LDPlayer9", "error": str(e)}
    return {"name": "LDPlayer9", "error": "Version not found"}


def get_bluestacks_version():
    """BlueStacks5 - MajorGeeks"""
    try:
        url = "https://www.majorgeeks.com/files/details/bluestacks.html"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        match = re.search(r'(5\.\d+\.\d+\.\d+)', resp.text)
        if match:
            return {"name": "BlueStacks5", "version": match.group(1)}
    except Exception as e:
        return {"name": "BlueStacks5", "error": str(e)}
    return {"name": "BlueStacks5", "error": "Version not found"}


def get_mumu_version():
    """MuMu Player - 웹페이지 + API 비교해서 최신 버전 사용"""
    web_version = None
    api_version = None

    # 1. 웹페이지에서 버전
    try:
        url = "https://www.mumuplayer.com/update/"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            match = re.search(r'MuMuPlayer\s*\(Windows\)\s*V([\d.]+)', resp.text)
            if match:
                web_version = match.group(1)
    except:
        pass

    # 2. API에서 버전
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
        data = resp.json()
        if data.get("items"):
            item = data["items"][0]
            version = item.get("version", "")
            parts = version.split(".")
            if len(parts) >= 3:
                api_version = ".".join(parts[:3])
    except:
        pass

    # 3. 더 높은 버전 선택
    def parse_ver(v):
        try:
            return tuple(int(x) for x in v.split('.'))
        except:
            return (0,)

    if web_version and api_version:
        if parse_ver(web_version) >= parse_ver(api_version):
            return {"name": "MuMuPlayer", "version": web_version}
        else:
            return {"name": "MuMuPlayer", "version": api_version}
    elif web_version:
        return {"name": "MuMuPlayer", "version": web_version}
    elif api_version:
        return {"name": "MuMuPlayer", "version": api_version}

    return {"name": "MuMuPlayer", "error": "Version not found"}


# ============================================================
# 버전 파일 로드
# ============================================================

def load_my_versions():
    """내가 관리하는 버전 정보 로드"""
    if VERSION_FILE.exists():
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


# ============================================================
# URL 생성
# ============================================================

def generate_webapp_url(current_versions, my_versions):
    """index.html용 URL 쿼리스트링 생성"""
    params = {}

    for name in EMULATOR_ORDER:
        if name not in current_versions:
            continue

        data = current_versions[name]
        my_ver = my_versions.get(name, {}).get('version', '')

        # 에러가 있으면 스킵
        if 'error' in data:
            continue

        latest = data.get('version', '')

        # 업데이트가 있는 경우만 prev/latest 설정
        if my_ver and latest and my_ver != latest:
            params[f"{name}_prev"] = my_ver
            params[f"{name}_latest"] = latest
        elif latest:
            # 업데이트 없으면 latest만 (현재 버전으로 표시됨)
            params[f"{name}_latest"] = latest

    return f"{WEB_APP_URL}?{urlencode(params)}"


# ============================================================
# Teams 알림
# ============================================================

def send_teams_notification(current_versions, my_versions):
    """Teams로 내 버전 + 최신 버전 표 전송"""
    if not TEAMS_WEBHOOK_URL:
        print("⚠️  Teams Webhook URL이 설정되지 않았습니다.")
        return False

    webapp_url = generate_webapp_url(current_versions, my_versions)

    # 표 형식 마크다운 생성
    table_header = "| 제품명 | 현재 버전 | 최신 버전 | 상태 |\n|:---|:---:|:---:|:---:|\n"
    table_rows = []
    update_count = 0

    for name in EMULATOR_ORDER:
        if name in current_versions:
            latest = current_versions[name].get('version', '-')
            my_ver = my_versions.get(name, {}).get('version', '-')

            # 상태 판단
            if 'error' in current_versions[name]:
                status = "❌ 오류"
                latest = "-"
            elif my_ver == '-':
                status = "✅ 동일"
            elif my_ver != latest:
                status = "⬆️ 업데이트"
                update_count += 1
            else:
                status = "✅ 동일"

            table_rows.append(f"| {name} | {my_ver} | {latest} | {status} |")

    table_md = table_header + "\n".join(table_rows)

    # 요약
    if update_count > 0:
        summary_text = f"**🔔 {update_count}개 업데이트 필요!**"
        theme_color = "FF6600"  # 주황색
    else:
        summary_text = "✅ 모든 에뮬레이터 최신 버전"
        theme_color = "0076D7"  # 파란색

    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": theme_color,
        "summary": "에뮬레이터 버전 현황",
        "sections": [
            {
                "activityTitle": "📊 에뮬레이터 버전 현황",
                "activitySubtitle": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
        ],
        "potentialAction": [
            {
                "@type": "OpenUri",
                "name": "📧 QA 메일 생성하기",
                "targets": [{"os": "default", "uri": webapp_url}]
            }
        ]
    }

    try:
        response = requests.post(TEAMS_WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code == 200:
            return True
        print(f"Teams 응답: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Teams 전송 실패: {e}")
    return False


# ============================================================
# 메인 실행
# ============================================================

def main():
    print(f"\n{'='*60}")
    print(f"에뮬레이터 버전 체크 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
            my_ver = my_versions.get(name, {}).get('version', '-')
            if my_ver != '-' and my_ver != latest:
                print(f"⬆️ {name}: {my_ver} → {latest} (업데이트 필요)")
            else:
                print(f"✅ {name}: {latest}")

    # Teams 알림 전송
    print(f"\n{'='*60}")
    if send_teams_notification(current_versions, my_versions):
        print("✅ Teams 알림 전송 완료")
    else:
        print("❌ Teams 알림 전송 실패")

    # 메일 생성기 URL 출력
    webapp_url = generate_webapp_url(current_versions, my_versions)
    print(f"\n📧 메일 생성기 URL:")
    print(webapp_url)
    print(f"{'='*60}")


if __name__ == "__main__":
    main()