# Robot Lab 요구사항 대조 및 마무리 순서

기준: AI 코어 프로젝트 2회차 명세서. 작성일: 2026-10-23.

## 도메인 기획

로봇 200종의 메타데이터와 공개 로봇 기술 문서를 이용해 모델 탐색, 근거 기반 질문 응답 및 현장 투입 타당성 분석을 제공한다. 항목 텍스트는 ID·모델명·제조사·분류·목적·센서·사양·설명을 한 텍스트로 결합한다. 데이터 출처와 미확인 조건은 DATA_SOURCES.md에 기록한다.

근거가 필요한 대표 질문:

1. Spot이 활용된 현장 사례는 무엇이며 어느 문서에서 확인되는가?
2. Ameca의 개발사와 활용 목적은 무엇인가?
3. Spot의 250도 고온 구역 운용 인증번호를 확인할 수 있는가?

현장 투입 분석은 안전 인증을 대체하지 않는다. UI에서 제조사 공식 문서와 전문가 확인 필요성을 안내한다.

## 요구사항 대조표

| 번호 | 구현 위치 | 검증·제약 |
|---|---|---|
| F2001 | rag_core.load_robots, robot_text | 200건과 필수 필드·고유성 검사 |
| F2002 | index_metadata | 고정 ID·내용 해시로 변경분 갱신. 실제 반복 색인 기록은 verification/live_results.json |
| F2003 | queries | 전문가 프롬프트·JSON·모델명 포함. 최근 대화 6개를 캐시 키에 포함 |
| F2004 | collect_candidates, select_candidates | 등록 원문과 동일 URL은 LLM 탈락 방지. 미등록 모델의 자체 문서 보장은 미완료 |
| F2005 | index_documents | 별도 컬렉션, 설정 청킹, 항목별 청크 ID, 내용 동일 시 출처 메타데이터도 갱신 |
| F2006 | retrieve_node | 모델 메타데이터 필수 포함, 모델 ID 필터, Top-k, 내용 중복 제거 |
| F2007 | graph, generate_node | retrieve/generate 두 노드. 근거 외 추측 금지는 프롬프트 및 답변 검토로 확인 |
| F2008 | used_sources, app.render_sources | 실제 인용만 표시, 잘못된 번호 차단, 인용 없음 안내, 등록 원문의 라이선스·이력 표시 |
| F2009 | app.py | 세션 안에서 모델별 대화 분리. 브라우저 종료 후 영구 대화 저장은 요구 범위 밖 |
| F2010 | 현장 투입 타당성 분석 | 같은 RAG와 근거 표시 사용 |
| F2011 | find_robots | 의미 검색 후보 최대 30개를 LLM으로 조건 선별, 선택 시 대화 연결 |
| F2012 | st.status, UserError, 상단 안내 | 진행 상태·키/색인 오류·안전 안내 |
| F2013 | 해당 없음 | 별도 HTML·CSS·JS 프론트엔드는 선택하지 않음 |
| F2014 | search_type=mmr | 비교 근거 목록은 verification/live_results.json |
| F2015 | 미구현 | RAG 없는 대조 답변 5쌍 및 품질 평가는 선택 과제로 남김 |
| F2016 | sources.py, source_type | 기존 DB에 여러 출처 실제 저장. 전문·초록·요약을 구분 |
| NF2001 | verification/live_results.json | 대표 질문 처리 시간 측정. 전체 200종·부하 성능 판정은 아님 |
| NF2002 | queries, cached_candidates | 성공 응답 캐시. 실패·빈 응답은 재시도 가능하도록 저장하지 않음 |
| NF2003~4 | key, 예외 안내 | 키는 환경변수. 오류 추적/원문 프롬프트를 화면에 표시하지 않음 |
| NF2005 | app / rag_core / sources / ingest_meta | UI·코어·수집·CLI 분리. 도메인 일반화는 추가 개선 가능 |
| NF2006 | Collector.get | 호출 간격·서버 대기 존중. 실제 운영자 User-Agent 연락처 입력 필요 |
| NF2007 | DATA_SOURCES.md | 대표 원문 출처 기록 완료. 200건 메타데이터 원출처와 기존 자료별 권한 확인 필요 |

## 진행 순서

1. 코드 회귀 검증: `python -m unittest discover -s tests -v`.
2. 실제 대표 모델 색인·질문 검증: `python verify_project.py --live`.
3. 앱 실행: `python -m streamlit run app.py`. Spot·Ameca·Pepper에서 질문하고 실제 근거와 원문 링크 확인.
4. VERIFICATION_CHECKLIST.md와 verification/REPORT.md의 결과를 확인하고 부족한 모델 원문을 순차 등록.
5. 실제 운영자 연락처, 메타데이터 최초 출처 및 상호 검증자를 보완한 후 최종 제출 판정.

`--live`는 실제 GMS LLM·임베딩 호출을 사용한다. 실행 중에만 추가 온라인 수집을 끄고 등록 원문과 기존 DB로 RAG를 검사하므로 9개 외부 엔드포인트의 실동작을 증명하지 않는다.
