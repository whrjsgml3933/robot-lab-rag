"""실행: streamlit run app.py"""
import queue
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
from rag_core import RobotService, UserError, used_sources

st.set_page_config(page_title='Robot Lab', page_icon='🤖', layout='wide')
st.title('🤖 Robot Lab — 로봇 탐색 및 근거 기반 질의응답')
st.caption('사용자 제공 사양과 공개 문서를 구분해 답합니다. 현장 투입·안전 인증 판단은 제조사 공식 문서와 전문가 확인이 필요합니다.')


def render_sources(answer, sources):
    used = used_sources(answer, sources)
    if not used:
        st.caption('답변에 인용된 근거가 없습니다.')
        return
    with st.expander(f'답변에 인용된 근거 {len(used)}건'):
        for number, source in used:
            st.markdown(f"**[근거 {number}] {source['title']}**")
            st.caption(f"{source['source_type']} · {source.get('content_kind', '본문')}")
            if source.get('url'):
                st.link_button('원문 열기', source['url'])
            else:
                st.caption('입력 파일: ' + source.get('file', 'robots_data.json') + ' · 공식 사양 검증 전 자료')
            if source.get('license'):
                st.caption('이용 조건: ' + source['license'])
            if source.get('attribution_url'):
                st.link_button('기여자 및 문서 이력', source['attribution_url'])
            st.text(source['text'])


try:
    service = RobotService()
except UserError as exc:
    st.error(str(exc))
    st.stop()

if 'robot_id' not in st.session_state:
    st.session_state.robot_id = service.robots[0]['robot_id']
if st.session_state.robot_id not in service.by_id:
    st.session_state.robot_id = service.robots[0]['robot_id']
for key in ('histories', 'reports'):
    if key not in st.session_state:
        st.session_state[key] = {}
if 'search_results' not in st.session_state:
    st.session_state.search_results = None

with st.sidebar:
    st.header('로봇 탐색')
    st.caption(f'입력 로봇: {len(service.robots)}건')
    try:
        counts = service.counts()
        st.caption(f"색인: 메타데이터 {counts['robot_meta_v2']}건 · 외부 청크 {counts['robot_docs_v2']}건")
        if not counts['robot_meta_v2']:
            st.warning('메타데이터 색인이 없습니다. 아래 색인 버튼을 먼저 실행하세요.')
    except UserError as exc:
        st.warning(str(exc))
    except Exception:
        st.warning('색인 상태를 확인하지 못했습니다. 키·패키지·설정을 확인하세요.')
    st.selectbox('질문할 모델', options=list(service.by_id), key='robot_id',
                 format_func=lambda key: f"{service.by_id[key]['model_name']} ({service.by_id[key]['manufacturer']})")
    if not st.toggle('외부 자료 추가 검색', value=False,
                     help='기본은 저장된 자료와 등록 원문으로 답합니다. 켜면 외부 출처를 추가 검색하므로 시간이 더 걸릴 수 있습니다.'):
        service.settings['question_sources'] = []
    with st.form('condition_form'):
        condition = st.text_input('자연어 조건', placeholder='예: 산업 현장 순찰용 4족 보행 로봇')
        submitted = st.form_submit_button('조건으로 찾기')
    if submitted:
        if not condition.strip():
            st.warning('조건을 입력하세요.')
        else:
            try:
                with st.spinner('후보 검색 및 선별 중...'):
                    st.session_state.search_results = service.find_robots(condition.strip())
            except UserError as exc:
                st.error(str(exc))
            except Exception:
                st.error('조건 검색에 실패했습니다. 키·모델 설정과 연결 상태를 확인하세요.')
    if st.session_state.search_results is not None:
        if not st.session_state.search_results:
            st.info('입력 자료에서 조건을 확인할 수 있는 후보가 없습니다.')
        for result_id in st.session_state.search_results:
            def choose(key=result_id):
                st.session_state.robot_id = key
            st.button(service.by_id[result_id]['model_name'], key='choose_' + result_id, on_click=choose)
    st.divider()
    st.caption('첫 실행: 메타데이터를 먼저 색인하세요. 기존 GMS 임베딩 호출이 발생합니다.')
    if st.button('메타데이터 200건 색인 / 변경분 갱신'):
        try:
            with st.spinner('메타데이터 색인 중...'):
                changed = service.index_metadata()
            st.success(f'{changed}건 신규 색인 또는 갱신')
        except UserError as exc:
            st.error(str(exc))
        except Exception:
            st.error('색인 실패: 키·임베딩 모델·연결 상태를 확인하세요.')
    if st.button('현재 색인 건수 확인'):
        try:
            counts = service.counts()
            st.info(f"메타데이터 {counts['robot_meta_v2']}건 / 외부 청크 {counts['robot_docs_v2']}건")
            if not counts['robot_meta_v2']:
                st.warning('메타데이터 색인이 없습니다. 위 버튼으로 먼저 색인하세요.')
        except UserError as exc:
            st.error(str(exc))
        except Exception:
            st.error('색인 상태를 읽지 못했습니다. 설정을 확인하세요.')
    if st.button('선택 모델의 대화·분석 초기화'):
        key = st.session_state.robot_id
        st.session_state.histories.pop(key, None)
        st.session_state.reports.pop(key, None)
        st.rerun()

robot_id = st.session_state.robot_id
robot = service.robot(robot_id)
st.subheader(f"{robot['model_name']} ({robot['manufacturer']})")
st.caption('이 모델 ID: ' + robot_id)
history = st.session_state.histories.setdefault(robot_id, [])


def run_request(question, mode, prior):
    with st.status('검색어 추출·수집·선별·색인·답변 생성 중...', expanded=True) as status:
        events = queue.Queue()
        service.progress = events.put
        service.collector.progress = events.put
        try:
            # Streamlit 표시 함수는 메인 스레드에서만 호출합니다.
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(service.answer, robot_id, question, prior, mode)
                while not future.done():
                    try:
                        st.write(events.get(timeout=0.2))
                    except queue.Empty:
                        pass
                while not events.empty():
                    st.write(events.get_nowait())
                result = future.result()
        except UserError as exc:
            status.update(label='처리 중단', state='error')
            st.error(str(exc))
            return None
        except Exception:
            status.update(label='처리 실패', state='error')
            st.error('처리하지 못했습니다. GMS 키·모델 지원 여부·연결 상태를 확인하세요. 다시 시도하면 저장된 원문 캐시를 재사용합니다.')
            return None
        status.update(label='답변 생성 완료', state='complete', expanded=False)
    with st.expander('수집·선별 확인'):
        st.write('검색어:', result.get('queries', []))
        audit = result.get('audit', [])
        if audit:
            st.dataframe(audit, width='stretch')
        else:
            st.caption('이번 요청에서 외부 문서 후보를 확보하지 못했습니다.')
    return result


with st.expander('현장 투입 타당성 분석'):
    with st.form('fit_form'):
        task = st.text_area('평가할 작업', placeholder='예: 고온 배관 구역의 자율 순찰')
        analyze = st.form_submit_button('근거 기반 분석')
    if analyze:
        if not task.strip():
            st.warning('평가할 작업을 입력하세요.')
        else:
            result = run_request(task.strip(), 'fit', [])
            if result:
                st.session_state.reports[robot_id] = result
    report = st.session_state.reports.get(robot_id)
    if report:
        st.markdown(report['answer'])
        render_sources(report['answer'], report['sources'])

for message in history:
    with st.chat_message(message['role']):
        st.markdown(message['content'])
        if message['role'] == 'assistant':
            render_sources(message['content'], message.get('sources', []))

question = st.chat_input('선택한 로봇에 대해 질문하세요')
if question and question.strip():
    prior = [{'role': value['role'], 'content': value['content']} for value in history[-6:]]
    with st.chat_message('user'):
        st.markdown(question)
    with st.chat_message('assistant'):
        result = run_request(question.strip(), 'chat', prior)
        if result:
            st.markdown(result['answer'])
            render_sources(result['answer'], result['sources'])
    if result:
        history.extend([{'role': 'user', 'content': question},
                        {'role': 'assistant', 'content': result['answer'], 'sources': result['sources']}])
