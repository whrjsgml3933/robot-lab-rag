"""대표 원문을 사용한 실제 GMS·Chroma 검증. python verify_project.py --live

추가 네트워크 문서 수집은 끄고 등록 원문으로 파이프라인을 검사합니다.
실제 모델 호출·임베딩 비용이 발생하며 결과는 verification/live_results.json에 저장합니다.
"""
import argparse
import json
import time
from pathlib import Path

from rag_core import RobotService, used_sources, invalid_citations, split_text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', required=True)
    parser.parse_args()
    output = Path(__file__).parent / 'verification'
    output.mkdir(exist_ok=True)
    result = {'date': '2026-10-23', 'scope': '등록 원문 기반 실제 GMS·Chroma 검증; 외부 검색 API는 별도 검증',
              'checks': [], 'answers': [], 'search_comparison': []}

    def save():
        (output / 'live_results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    def check(name, actual, passed):
        result['checks'].append({'name': name, 'passed': bool(passed),
                                 'actual': json.loads(json.dumps(actual, ensure_ascii=False))})
        print(name, 'PASS' if passed else 'FAIL', flush=True)
        save()

    service = RobotService(progress=lambda message: print(message, flush=True))
    # settings.json은 변경하지 않고 이 검증 실행만 등록 원문으로 제한합니다.
    service.settings['question_sources'] = []
    try:
        before = service.counts()
        check('입력과 메타데이터 색인 수', before, before['robot_meta_v2'] == len(service.robots) == 200)
        changed1 = service.index_metadata()
        changed2 = service.index_metadata()
        check('메타데이터 반복 색인', [changed1, changed2, service.counts()], changed2 == 0 and service.counts()['robot_meta_v2'] == 200)
        for rid in ('robot_002', 'robot_006', 'robot_061'):
            robot = service.robot(rid)
            originals = service.local_candidates(robot)
            added1 = service.index_documents(robot, originals)
            added2 = service.index_documents(robot, originals)
            check('원문 반복 색인 ' + rid, [added1, added2], added2 == 0)
            result.setdefault('chunk_comparison', []).append({
                'robot_id': rid, 'title': originals[0]['title'],
                '1000/200': len(split_text(originals[0]['text'], 1000, 200)),
                '500/100': len(split_text(originals[0]['text'], 500, 100))})
        for rid, question, mode in [
            ('robot_002', '이 로봇은 어떤 현장에서 활용되었나요? 근거에서 확인한 사례만 알려주세요.', 'chat'),
            ('robot_006', '이 로봇의 개발사와 활용 목적을 알려주세요.', 'chat'),
            ('robot_002', '이 로봇의 250도 고온 구역 운용 인증번호를 알려주세요. 자료에 없으면 확인불가라고 답하세요.', 'chat'),
            ('robot_002', '250도 고온 배관 구역에 투입할 수 있는지 평가해주세요.', 'fit'),
        ]:
            start = time.perf_counter()
            answer = service.answer(rid, question, mode=mode)
            elapsed = round(time.perf_counter() - start, 2)
            result['answers'].append({'robot_id': rid, 'question': question, 'mode': mode,
                                     'seconds': elapsed, **answer})
            check('답변 생성 ' + str(len(result['answers'])),
                  {'seconds': elapsed, 'citations': len(used_sources(answer['answer'], answer['sources']))},
                  bool(answer['answer'].strip()) and not invalid_citations(answer['answer'], answer['sources']))
        robot = service.robot('robot_002')
        q = '이 로봇은 어떤 현장에서 활용되었나요? 근거에서 확인한 사례만 알려주세요.'
        events = []
        service.progress = events.append
        service.queries(robot, q, [])
        check('검색어 캐시 재사용', events, any('캐시 재사용' in e for e in events))
        for search_type in ('similarity', 'mmr'):
            for top_k in (2, 5):
                service.settings.update(search_type=search_type, top_k=top_k)
                found = service.retrieve_node({'robot_id': 'robot_002', 'question': q})
                result['search_comparison'].append({'search_type': search_type, 'top_k': top_k,
                    'sources': [{'title': s['title'], 'url': s.get('url', ''), 'text': s['text']} for s in found['sources']]})
        service.settings.update(search_type='similarity', top_k=5)
        selected = service.find_robots('산업 현장 순찰용 4족 보행 로봇')
        check('자연어 조건 검색', selected, bool(selected))
        result['graph_nodes'] = list(service.graph().get_graph().nodes)
        check('LangGraph 두 처리 노드', result['graph_nodes'],
              set(result['graph_nodes']) == {'__start__', '__end__', 'retrieve', 'generate'})
        result['final_counts'] = service.counts()
        save()
    except Exception as exc:
        # 자격 증명·모델 요청 본문·추적 정보를 결과물에 기록하지 않습니다.
        result['error'] = {'type': type(exc).__name__, 'message': '연결·모델 설정 또는 패키지 상태 확인 필요'}
        save()
        print('검증 중단:', type(exc).__name__, flush=True)
        return 1
    return 0 if all(c['passed'] for c in result['checks']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
