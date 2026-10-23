# 제공 문서 묶음 등록

실제로 확보한 외부 원문을 UTF-8 TXT 또는 MD로 이 폴더에 저장합니다.
local_documents.example.json을 참고하여 local_documents.json 배열에 연결합니다.
robot_id는 원문이 실제로 설명하는 모델의 ID, title은 실제 제목, file은 프로젝트 기준 경로입니다.
url은 원문 URL을 아는 경우만 입력합니다. 모르면 빈 문자열로 두면 화면에 파일명을 표시합니다.
item_document는 해당 로봇 자체를 설명하는 원문일 때만 true로 지정합니다.
이 표시는 후보 선별·길이 제한보다 우선하므로 다른 모델·다른 세대의 자료에는 지정하지 마세요.
제조사·저자·원문 URL 또는 파일 출처·이용 조건은 별도로 기록하세요.
본문을 임의로 작성하거나 요약을 원문 전문으로 표시하지 마세요.

새 서비스·API·키를 연결하지 않는 로컬 파일 처리입니다.
네트워크 없이 이 문서 묶음만 쓰려면 settings.json의 ingest_sources와 question_sources를 모두 []로 설정합니다.
LLM과 임베딩에는 기존 GMS 키가 여전히 필요합니다.
