# Robot Lab RAG 설계

## 데이터와 색인

robots_data.json의 로봇 1건을 8개 필드의 텍스트로 결합해 robot_meta_v2 컬렉션에 넣는다. ID는 robot_id다. 내용 SHA-256으로 변경 여부를 판단한다.

외부 원문과 초록·요약은 robot_docs_v2에 저장한다. doc_key는 robot_id·source_key·URL 또는 파일명의 해시, 청크 ID는 doc_key·순번·내용의 해시다. 다른 모델이 같은 문서를 사용해도 덮어쓰지 않는다. 새 저장 성공 후에만 해당 문서의 오래된 청크를 정리한다. 내용이 같아도 자체 문서 표시·출처 정보 변경은 갱신한다.

청크 메타데이터: title, url, file, robot_id, robot_model, source_type, source_key, content_kind, doc_key, item_document, full_body. 등록 원문은 license, attribution_url을 추가한다. 기존 캐시의 최초 수집 시점과 문서 revision 정보는 불완전하므로 확인된 날짜로 소급 작성하지 않는다.

## 세 가지 프롬프트

검색어 추출은 로봇 기술 문서 전문가 역할로 모델과 질문·최근 대화에서 JSON 검색어 배열을 얻는다. 제조사+전체 모델명, 짧은 모델명을 코드에서 우선 포함한다.

후보 선별은 정확한 모델 자체 문서와 질문에 유용한 배경 문서를 JSON ID 목록으로 선택한다. 다른 세대·다른 모델의 사양을 대상 모델에 적용하지 않는다. 등록된 자체 원문 및 동일 URL 후보는 LLM에 제외 권한을 주지 않는다. 등록되지 않은 자체 문서는 LLM 판별의 한계가 남는다.

답변 생성은 이번 검색 근거만 사용하고 주요 주장에 [근거 N]을 붙인다. 사용자 제공 사양·공식 문서·초록을 혼동하지 않는다. 근거 부족 시 확인불가와 미확인 조건을 제시한다. 인용 번호의 범위는 코드에서 검사하며, 인용 내용의 사실 일치까지 자동 보장하지 않는다.

## 파이프라인

```mermaid
flowchart LR
    START --> retrieve
    retrieve --> generate
    generate --> END
```

retrieve 내부: 선택 모델 색인 확인 → 검색어 추출/캐시 → 단계별 출처 후보와 등록 원문 병합 → 후보 선별 → 본문 확보/청킹/색인 → 모델 메타데이터와 선택 모델의 외부 청크 검색 → 내용 중복 제거.

generate 내부: 근거 번호 부여 → 답변 생성 → 빈 응답/존재하지 않는 인용 검사. UI는 실제 인용된 문서만 표시한다.

## 검색 설정과 캐시

기본 설정: 1000자 청크, 200자 중복, 외부 Top-k=5, similarity. 메타데이터 1건은 Top-k와 별도로 항상 포함한다. MMR은 fetch_k=20에서 Top-k를 선택한다.

사전 수집 출처는 Wikipedia/arXiv/Crossref/Semantic Scholar/IEEE, 질문 추가 출처는 Reddit/Patents/ROS/Wikidata다. 두 목록 모두 []면 등록 파일만 수집한다. 기존 DB 검색은 계속한다.

검색어 캐시는 모델 ID·질문·최근 대화·LLM 모델·최대 검색어 수로 구분한다. 수집 캐시는 모델 ID·출처·검색어로 구분한다. 본문 캐시와 DB는 분리해 DB 복구가 가능하다. 실패·빈 결과는 성공 캐시로 저장하지 않는다.
