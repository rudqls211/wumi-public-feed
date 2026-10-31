# WUMI 공용 서버 운영 및 다음 단계 (2026-10-31)

## 현재 실제 운영
- GitHub Pages: https://rudqls211.github.io/wumi-public-feed/
- 공용 JSON: https://rudqls211.github.io/wumi-public-feed/data/fx.json
- 상태 데이터 5개: fx, quotes, dividends, tax_policy, holidays
- GitHub Actions: update_public_data.yml — 매일 한국시간 11:17 / 23:17 예약 (지연·생략 가능)
- 수집 성공 시 docs/data/*.json을 저장소에 커밋하므로 **다음 실행 실패 때 마지막 정상값 유지**
- 수집기/테스트/설정을 수정하면 push 시 검사·배포 자동 실행
- 개인 계좌·잔액·보유 종목·가계부·Firebase 인증정보는 저장하거나 수집하지 않음

## 휴대폰 WUMI에서 확인
1. 더보기 → 서버 데이터 상태 → 서버 주소 입력 및 저장
2. 주소: https://rudqls211.github.io/wumi-public-feed/
3. 지금 새로 받기 → 환율 4종 USD / JPY / EUR / CNY의 실제 값과 자료 기준일 확인
4. 네트워크를 끊은 뒤 새로 받기 → 마지막 캐시를 계속 표시하는지 확인
5. 자산 현황·가계부·백업 정보가 변경되지 않았는지 확인

## 아직 비활성화된 서비스
- 해외 주가: 무료 API 키만으로 공용 재배포가 허용되는 것은 아니므로 기본 차단.
- 국내 DART 배당: 기존 별도 비공개 저장소 wumi-dividend-data를 **절대 공개하지 말 것**. 새 서버에 배당 공시 요약 수집 코드는 있으나 API 키·재제공 조건 확인 전 기본 차단. 배당 지급일/락일은 확정값이 아니므로 null을 유지.
- 미국 배당: 지급일·금액 데이터의 허가받은 공용 제공처 미정. 미구현.
- 2026 세법: config/tax_policy_2026.json은 검증 전 초안(reviewed_by_operator=false). 앱 세액·소득공제 계산에 자동 연결하지 않음.
- 한국 공휴일: 한국천문연구원 특일 정보 API 연동 코드는 있지만 **KASI_SERVICE_KEY** 미설정으로 미수집. 실제 서비스 응답은 아직 검증 전.

## API 키 설정 (필요 시, 본인 GitHub에서만)
- 저장소 → Settings → Secrets and variables → Actions → Repository secrets
- 키 값은 채팅, ZIP, README, 공개 이슈, 앱 소스에 붙여넣지 않음.
- KASI_SERVICE_KEY: 공공데이터포털에서 발급한 일반 인증키로 공휴일 수집 시도.
- OPENDART_API_KEY: OpenDART 공시 인증키. 재제공 약관 확인 전 공개 배당 데이터 게시 금지.
- TWELVEDATA_API_KEY: Twelve Data 서비스 키. 공용 가격 재표시 허가 확인 전 가격 데이터 게시 금지.
- 공개 재제공 라이선스의 확인 증거가 있을 때만 GitHub Actions 변수 QUOTE_PUBLIC_REDISPLAY_LICENSE_CONFIRMED 또는 DART_PUBLIC_REDISPLAY_LICENSE_CONFIRMED을 true로 설정. **무턱대고 true로 변경하면 안 됨.**
- 새 Secret 등록 이후 Actions → Update shared WUMI public data → Run workflow

## 데이터 보존과 장애 대응
- 수집 오류 → 해당 항목의 저장된 마지막 정상 JSON을 stale 상태로 다시 게시, 자료 원래 기준일 유지.
- API 키·라이선스 미확인 → 미수집/미게시. 과거 허가된 가격이 있어도 라이선스 플래그가 해제되면 공개 데이터 삭제.
- 공용 JSON은 누구나 볼 수 있음. 개인 종목 보유·계좌 정보 업로드 금지.
- 작업 후 확인: Actions 성공 여부, docs/data/fx.json 값, GitHub Pages 상태 화면, WUMI 앱 진단 화면.
