<img width="730" height="353" alt="image" src="https://github.com/user-attachments/assets/27eb8f04-c5e7-4a1b-ae8b-1bac6da56039" />


### NoxPlayer
- URL: `https://kr.bignox.com/`
- 방식: 웹페이지에서 "X.X.X버전" 패턴 추출

### MEmu
- URL: `https://www.memuplay.com/blog/category/release-notes`
- 방식: 웹페이지에서 "MEmu X.X.X is officially released" 패턴 추출

### LDPlayer9
- URL: `https://apikr2.ldmnq.com/checkMnqVersion`
- 방식: API 응답에서 "LDPlayer_X.X.X.X.exe" 패턴 추출
LDPlayer 실행 파일의 업데이트 체크 과정을 **Wireshark**로 패킷 캡처하여 발견

```
https://apikr2.ldmnq.com/checkMnqVersion?pid=dnplayer-kr9&openid=172&...
```
  

### BlueStacks5
- URL: `https://www.majorgeeks.com/files/details/bluestacks.html`
- 방식: 웹페이지에서 "5.X.X.X" 패턴 추출

### MuMuPlayer
- URL: `https://www.mumuplayer.com/update/` + `https://api.mumuglobal.com/api/appcast`
- 방식: 웹페이지와 API 버전 비교 후 더 높은 버전 사용
- MuMuPlayer 앱 실행 시 업데이트 체크 요청을 캡처하여 발견

```
https://api.mumuglobal.com/api/appcast?version=...&package=mumu&channel=gw-overseas
```


```
main.py 실행
    ↓
각 에뮬레이터 최신 버전 크롤링
    ↓
emulator_versions.json(내 버전)과 비교
    ↓
URL 쿼리스트링 생성 (예: ?BlueStacks5_prev=5.21.0&BlueStacks5_latest=5.22.0)
    ↓
Teams 알림 전송 (버튼에 URL 포함)
    ↓
버튼 클릭 → index.html이 URL 파라미터 파싱
    ↓
테이블에 버전 정보 자동 입력 + 업데이트 항목 하이라이트
```
