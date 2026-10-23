# Robot Lab 필수 기능 보완본

F2001~F2012 중 앞서 확인한 코드 누락을 수정한 패키지입니다. 심화 기능은 새로 추가하지 않았습니다. 기존 MMR 선택 코드는 유지하지만 기본은 유사도 검색입니다.

## 기존 사용자 적용

기존 앱을 종료하고 이 압축의 파일을 프로젝트 폴더에 덮어씁니다. `.env`, `chroma_db_v2`, `cache_v3`는 유지합니다. 이 압축에는 키와 DB가 없습니다. 데이터 형식은 같으므로 메타데이터 200건 재색인은 필요 없습니다.

중요 파일: app.py, rag_core.py, sources.py, settings.json, ingest_meta.py, local_documents.json. 공통 모듈을 함께 사용해야 합니다. 이미 직접 만든 local_documents.json이 있다면 빈 목록으로 덮어쓰지 마세요.

```bash
python -m streamlit run app.py
```

신규 실행이라면 기존 GMS 키를 `.env`에 설정하고 메타데이터를 먼저 색인합니다.

```bash
python -X utf8 -m pip install -r requirements.txt
python ingest_meta.py
python -m streamlit run app.py
```

requirements 버전은 원본 과제 명세서의 값입니다. 사용자 환경에서 실제 설치된 패키지로 우선 실행하세요. GMS 모델은 기존 설정을 유지하며 temperature 인자를 보내지 않습니다.

## 필수 기능 수정 내용

1. 후보를 선별 전에 자르지 않습니다. max_candidates는 이제 탈락 상한이 아니라 LLM 한 번의 선별 배치 크기입니다. 모든 배치를 검토하고 모델 자체 문서로 식별된 후보를 보존합니다.
2. 모델 자체 문서는 길이 제한보다 우선하여 전체 텍스트를 청킹합니다. 등록된 자체 원문은 LLM이 제외할 수 없습니다.
3. 위키는 후보 도입부로 선별하고 그 다음 본문을 수집합니다. 본문이 실패하면 색인하지 않고 상태표에 미색인으로 표시합니다.
4. 원문 TXT/MD 묶음을 명시적으로 등록할 수 있습니다. 외부 호출이 제한된 경우 문서 묶음으로 수집 단계를 대신할 수 있다는 F2004 조건에 대응합니다.
5. 로봇 ID와 같은 질문의 검색어를 캐시합니다. 재질문으로 검색어가 달라져 불필요하게 재수집되는 것을 방지합니다. 최근 대화 이력도 캐시 키에 포함하므로 문맥이 달라지면 검색어를 다시 추출합니다.
6. 선별 여부와 실제 색인 상태를 분리합니다. 상태표에서 본문 색인/초록·요약 색인/본문 실패를 구분합니다. 초록을 논문 전문 수집으로 표시하지 않습니다.
7. 메타데이터·외부 청크 수를 사이드바에 표시합니다. 메타데이터 미색인·키 누락을 안내합니다. 채팅 중 암묵적으로 색인을 실행하지 않습니다.
8. 인용 없는 답변은 화면에서 그 사실을 안내합니다. 잘못된 근거 번호는 계속 차단합니다. 모델별 대화·특화 기능·두 노드 그래프는 유지합니다.

## 외부 문서 준비

질문하면 기존 출처에서 수집합니다. 특정 모델을 미리 준비할 수도 있습니다.

```bash
python ingest_meta.py --external --robot robot_001
```

전체 외부 수집은 `--external --all`을 명시해야 하며 자동 실행하지 않습니다. 기존 GMS와 공개 출처만 사용합니다. GMS 호출에는 사용자의 기존 할당량·요금 조건이 적용됩니다. 새 서비스·키·DB·호스팅·결제 연결은 없습니다.

## 제공 원문 묶음 사용

실제 원문 파일을 UTF-8 TXT/MD로 documents 폴더에 두고 local_documents.example.json을 참고해 local_documents.json에 등록합니다. 자세한 내용은 documents/README.md에 있습니다. 빈 예제나 직접 지어낸 사양을 원문으로 등록하지 마세요.

```json
[
  {
    "robot_id": "robot_001",
    "title": "실제 문서 제목",
    "file": "documents/robot_001.txt",
    "url": "",
    "item_document": true
  }
]
```

위 예시는 경로 형식만 보여 줍니다. 실제 원문 본문을 함께 제공하지 않습니다. item_document=true는 파일이 정확히 그 모델 자체를 다룰 때만 지정하세요. URL을 모르면 빈 값으로 두면 원문 파일명이 표시됩니다.

네트워크 수집 없이 제공 문서만 쓰려면 settings.json의 ingest_sources와 question_sources를 모두 []로 설정합니다. LLM·임베딩은 기존 GMS를 계속 사용합니다.

## 재수집·DB 보존

기존 원문 캐시는 재사용하고 DB가 없으면 복구합니다. 실패 응답은 성공 자료로 캐시하지 않습니다. 개선된 검색 조건으로 완전히 새 수집을 원하면 앱을 종료하고 cache_v3를 cache_v3_backup으로 이름 변경하세요. 외부 요청과 GMS 검색어 추출 호출이 다시 발생할 수 있습니다. chroma_db_v2를 삭제할 필요는 없습니다.


## 2026-10-23 검토 후 마무리

- 순서와 요구사항 대조: [PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md)
- 설계: [RAG_DESIGN.md](RAG_DESIGN.md)
- 출처·이용 조건·미확인 항목: [DATA_SOURCES.md](DATA_SOURCES.md)
- 실제 검증: [verification/REPORT.md](verification/REPORT.md), [검증 원자료](verification/live_results.json)
- 회귀 테스트: `python -m unittest discover -s tests -v`
- 실제 모델·DB 검증: `python verify_project.py --live`

Spot·Ameca·Pepper의 기존 위키 본문을 documents에 복원해 등록했습니다. 앱은 기본적으로 저장된 DB와 등록 원문으로 답하고, ‘외부 자료 추가 검색’을 켜면 설정된 추가 출처를 호출합니다. 사전 수집 CLI와 settings.json의 출처 목록은 유지합니다. 대표 모델 원문이 준비돼 있다고 전체 200종의 원문·사양이 검증된 것은 아닙니다.

`ROBOTLAB_USER_AGENT` 환경변수에 실제 운영자 연락처 또는 프로젝트 URL을 포함한 식별 문자열을 설정할 수 있습니다. 임의 연락처는 넣지 않았습니다. 실제 GMS 연결 및 외부 API 접근이 가능한 환경에서 실행하세요.
