"""공통 설정의 출처를 이용하는 색인 CLI.

python ingest_meta.py                         # 메타데이터만
python ingest_meta.py --list-sources          # 활성 출처 확인 (API 호출 없음)
python ingest_meta.py --external --all        # 전체 로봇 외부 문서
python ingest_meta.py --external --robot robot_001
python ingest_meta.py --external --all --dry-run  # 실행 계획만
"""
import argparse
import os
import re
import sys


def safe_error(exc):
    """프롬프트·추적 정보 대신 예외 종류와 키를 가린 메시지만 출력합니다."""
    message = str(exc)
    for name in ('GMS_KEY', 'OPENAI_API_KEY'):
        secret = os.environ.get(name)
        if secret:
            message = message.replace(secret, '[KEY 숨김]')
    message = re.sub(r'(?i)(Bearer\s+)[^\s\"\',}]+', r'\1[KEY 숨김]', message)
    message = re.sub(r'\bsk-[A-Za-z0-9_-]+', '[KEY 숨김]', message)
    return f'{type(exc).__name__}: {message[:2000]}'


def build_parser():
    parser = argparse.ArgumentParser(description='Robot Lab 메타데이터·외부 문서 색인')
    parser.add_argument('--external', action='store_true', help='외부 수집·선별·색인 실행')
    parser.add_argument('--robot', action='append', default=[], help='로봇 ID 또는 정확한 모델명 (반복 가능)')
    parser.add_argument('--all', action='store_true', help='전체 로봇 선택 (--external과 사용)')
    parser.add_argument('--question', default='이 로봇의 구조, 주요 기능과 제약은 무엇인가?', help='검색어 추출·문서 선별 질문')
    parser.add_argument('--sources', nargs='+', help='사전 수집용 5개 중 이번 실행에 사용할 출처만 지정')
    parser.add_argument('--list-sources', action='store_true', help='활성 출처 확인 후 종료, API 호출 없음')
    parser.add_argument('--dry-run', action='store_true', help='실행 계획만 출력, API·DB 작업 없음')
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.external and not args.robot and not args.all and not args.list_sources:
        parser.error('--external에는 --robot 또는 --all을 지정하세요.')
    if args.all and not args.external:
        parser.error('--all은 --external과 함께 사용하세요.')
    if args.all and args.robot:
        parser.error('--all과 --robot 중 하나만 사용하세요.')
    if not args.question.strip():
        parser.error('--question은 빈 문자열일 수 없습니다.')

    print('실행 Python:', sys.executable)
    stage = '모듈 불러오기'
    try:
        # 의존성 import 실패도 실제 예외 종류를 안내합니다.
        from rag_core import RobotService
        from sources import SOURCE_NAMES

        stage = '설정·데이터 읽기'
        service = RobotService(progress=print)
        requested_sources = args.sources if args.sources is not None else service.settings['ingest_sources']
        if not isinstance(requested_sources, list):
            raise ValueError('ingest_sources는 JSON 배열이어야 합니다.')
        allowed_ingest = ('wikipedia', 'arxiv', 'crossref', 'semantic_scholar', 'ieee')
        unknown = [source for source in requested_sources if source not in allowed_ingest]
        if unknown:
            raise ValueError('사전 색인에는 wikipedia/arxiv/crossref/semantic_scholar/ieee만 지정할 수 있습니다: ' + ', '.join(map(str, unknown)))
        enabled = list(dict.fromkeys(requested_sources))
        service.settings['ingest_sources'] = enabled
        print(f'사전 색인 출처: {len(enabled)}개')
        for source in enabled:
            print(f'  - {source}: {SOURCE_NAMES[source]}')
        print('질문 시 추가 검색 출처: ' + ', '.join(service.settings['question_sources']))
        if not enabled:
            print('사전 네트워크 출처 없음: 등록된 제공 원문 묶음만 사용합니다.')
        print('주의: 활성화 목록은 요청 대상이며 실제 수집 성공을 보장하지 않습니다.')
        if args.list_sources:
            return 0
        if args.sources is not None and not args.external:
            raise ValueError('--sources는 --external 또는 --list-sources와 함께 사용하세요.')

        stage = '대상 로봇 확인'
        targets = list(service.robots) if args.all or not args.robot else []
        for requested in args.robot:
            matches = [robot for robot in service.robots
                       if requested in (robot['robot_id'], robot['model_name'])]
            if len(matches) != 1:
                raise ValueError('정확한 로봇 ID 또는 모델명을 지정하세요: ' + requested)
            if matches[0] not in targets:
                targets.append(matches[0])
        print(f'대상 로봇: {len(targets)}대')
        print('외부 문서 처리:', '실행' if args.external else '생략 (메타데이터만 색인)')
        if args.dry_run:
            print('실행 계획 확인 완료. API 호출·DB 변경 없음.')
            return 0

        stage = '키 확인'
        service.key()
        stage = '메타데이터 색인'
        changed = service.index_metadata(targets)
        print(f'메타데이터 신규 색인·갱신: {changed}건 (0이면 기존 데이터와 동일)')
        succeeded = failed = empty = 0
        added_total = 0
        if args.external:
            for index, robot in enumerate(targets, 1):
                robot_stage = '검색어 추출'
                print(f"\n[{index}/{len(targets)}] {robot['robot_id']} / {robot['model_name']}")
                try:
                    queries = service.queries(robot, args.question.strip(), [])
                    print('검색어:', ' / '.join(queries))
                    robot_stage = '외부 후보 수집'
                    # 사전 수집용 5개만 사용합니다. 질문용 4개는 호출하지 않습니다.
                    candidates = service.collect_candidates(robot, queries, phase='ingest')
                    robot_stage = '후보 선별'
                    selected = service.select_candidates(robot, args.question.strip(), candidates)
                    print(f'후보 {len(candidates)}건 → 채택 {len(selected)}건')
                    if not selected:
                        empty += 1
                        print('채택 자료 없음: 색인 성공으로 집계하지 않습니다.')
                        continue
                    robot_stage = '본문 확보·청킹·색인'
                    added = service.index_documents(robot, selected)
                    added_total += added
                    confirmed = service.indexed_documents
                    if not confirmed:
                        empty += 1
                        print('실제 색인 확인 문서 없음: 원문 확보 상태를 확인하세요.')
                        continue
                    succeeded += 1
                    print(f'색인 확인 문서 {confirmed}건 / 신규 청크 {added}개')
                    print('신규 청크가 0개여도 동일 청크가 이미 DB에 있으면 정상입니다.')
                    for row in getattr(service, 'last_audit', []):
                        if row.get('selected'):
                            print(f"  {row.get('title', '')}: {row.get('index_status', '색인 상태 정보 없음')}")
                except Exception as exc:
                    failed += 1
                    print(f"실패 모델: {robot['robot_id']} / 실패 단계: {robot_stage}")
                    print('오류:', safe_error(exc))
            print(f'\n외부 처리 결과: 성공 {succeeded}대 / 자료 없음 {empty}대 / 실패 {failed}대')
            print(f'이번 실행 신규 외부 청크: {added_total}개')
        else:
            print('전체 외부 문서 수집 명령: python ingest_meta.py --external --all')
        stage = 'DB 건수 확인'
        print('현재 색인:', service.counts())
        return 1 if failed else 0
    except Exception as exc:
        print('실패 단계:', stage)
        print('오류:', safe_error(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
