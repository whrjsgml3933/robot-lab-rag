# 데이터 출처와 이용 조건

확인일: 2026-10-23. 공개 API 접근 가능 여부와 원문 재배포 권한은 별도 항목으로 관리한다.

## 입력 메타데이터

`robots_data.json` 200건은 프로젝트에 이미 존재하던 사용자 제공 자료다. 최초 작성자, 수집 URL, 작성 시점, 개별 사양의 세대·정확성 및 재배포 권한은 미확인이다. 공식 제조사 사양으로 표기하지 않는다. 특히 `ASIMO 2.0 (Concept)`처럼 개념 모델로 기재된 항목은 과거 ASIMO 문서와 동일 모델이라고 간주하지 않는다.

## 대표 모델 원문 묶음

`local_documents.json`에 등록한 본문은 기존 `cache_v3/body_*.json`의 TextExtracts 본문을 변경 없이 복원한 것이다. 최초 수집일과 revision ID는 기존 캐시에 없어 복구할 수 없다. 아래 날짜는 원문 복원·등록일이며 최초 수집일이 아니다.

| 모델 | 문서 | 로컬 파일 | 등록일 |
|---|---|---|---|
| Spot / robot_002 | [스팟 (로봇)](https://ko.wikipedia.org/wiki/스팟_(로봇)) | documents/robot_002_wikipedia.txt | 2026-10-23 |
| Ameca / robot_006 | [아메카 (로봇)](https://ko.wikipedia.org/wiki/아메카_(로봇)) | documents/robot_006_wikipedia.txt | 2026-10-23 |
| Pepper / robot_061 | [페퍼 (로봇)](https://ko.wikipedia.org/wiki/페퍼_(로봇)) | documents/robot_061_wikipedia.txt | 2026-10-23 |

출처: 한국어 위키백과 기여자. 본문 이용 조건: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). 각 등록 레코드의 `attribution_url`은 기여자 확인을 위한 문서 이력 링크다. 원문 URL·라이선스·기여자 이력과 변경 여부를 함께 유지한다. API가 제공한 텍스트 추출본이므로 이미지·표·각주를 포함한 원래 HTML 전체를 보존한 것은 아니다. 이용 조건 확인 기준은 [Wikimedia 라이선스 안내](https://attribution.wikimedia.org/attribution-signals/license.html)다.

## 외부 출처별 현황

| 출처 | 현재 수집 내용 | 권한·이용 조건 확인 상태 |
|---|---|---|
| Wikipedia | 후보 도입부 → 선별된 문서 텍스트 본문 | 위 대표 본문 묶음은 출처·CC BY-SA·이력 기록. 나머지 기존 청크의 개별 기록 보완 필요 |
| arXiv | 논문 제목·URL·초록 | [공식 라이선스 안내](https://info.arxiv.org/help/license/index.html)에서 논문별 조건을 확인해야 한다. 전문 확보로 표시하지 않음 |
| Crossref | DOI URL·제목·초록 | [공식 REST API 안내](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) 확인. 초록의 원 저작권·개별 재배포 조건은 별도 확인 필요 |
| Semantic Scholar | 제목·URL·초록 | [API 이용 약정](https://api.semanticscholar.org/license/) 확인. 내부 비상업 연구·교육 등 조건과 공개 표시 요구 사항이 있으므로 데이터 공개 전 추가 확인 필요 |
| IEEE Spectrum | RSS 설명·기사 URL | 기사 전문 미수집. 개별 기사/RSS 재배포 조건 미확인 |
| Reddit | 게시글 본문·게시글 URL | [Data API Terms](https://redditinc.com/policies/data-api-terms) 확인. 접근 자격·식별 정보·이용 목적 조건 확인이 필요하며 현재 공개 재배포 허가 미확인 |
| Google Patents | 검색 요약·특허 URL | 특허 전문 미수집. 검색 엔드포인트 사용 조건 미확인 |
| ROS Index | 패키지 설명·URL | 개별 패키지·설명문의 라이선스 미확인, 엔드포인트 실동작 별도 확인 필요 |
| Wikidata | 엔터티 설명·URL | [공식 라이선스 안내](https://www.wikidata.org/wiki/Wikidata:Licensing): 구조화 데이터는 CC0. 다른 네임스페이스의 텍스트와 혼동하지 않음 |

DB와 캐시의 기존 논문·RSS 자료 전체가 공개 재배포 가능한 것으로 판정한 문서가 아니다. 확인되지 않은 자료는 공개 배포용 데이터 묶음에서 제외하고, 필요하면 URL 목록과 코드만 제출한다. `chroma_db_v2/`, `cache_v3/`, `.env`는 `.gitignore`에 포함되어 있다.

## API 식별 및 요청 정책

`ROBOTLAB_USER_AGENT` 환경변수로 실제 공개 연락처 또는 프로젝트 URL을 포함한 식별 문자열을 설정할 수 있다. `.env`는 앱의 기존 키 로딩 때 함께 읽힌다. 실제 운영자 연락처가 제공되지 않아 임의 이메일·프로젝트 URL을 만들지 않았다.

예시 형식: `RobotLabRAG/2.0 (실제 공개 프로젝트 URL 또는 실제 연락처)`.

[Wikimedia API 접근 정책](https://www.mediawiki.org/wiki/Wikimedia_APIs/Access_policy)에 맞게 운영자가 실제 값을 넣어야 한다. 재시도는 `Retry-After`의 초 또는 HTTP 날짜를 따른다. 60초 초과 대기는 조기 재요청하지 않고 이번 요청을 중단한다. 호출 간격은 설정 파일로 관리한다.
