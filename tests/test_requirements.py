"""실제 외부 API 없이 실패 경로와 요구사항 불변 조건을 검증합니다."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from rag_core import RobotService, UserError, split_text, invalid_citations, used_sources
from sources import Collector


class RequirementsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.service = RobotService()
        self.service.cache_dir = Path(self.directory.name)
        self.robot = self.service.robot('robot_002')

    def candidate(self, **updates):
        value = dict(candidate_id='c1', title='Spot', url='https://example.org/spot',
                     text='원문입니다.' * 200, source_key='wikipedia',
                     source_type='위키백과', content_kind='본문')
        return value | updates

    def test_registered_url_survives_llm_exclusion(self):
        own = self.service.local_candidates(self.robot)[0]
        candidate = self.candidate(url=own['url'])
        self.service.ask = Mock(side_effect=AssertionError('보호 문서에 LLM을 호출하면 안 됨'))
        selected = self.service.select_candidates(self.robot, '관련 없는 질문', [candidate])
        self.assertTrue(selected[0]['item_document'])

    def test_other_generation_not_protected_by_name(self):
        self.service.ask = Mock(return_value='{"selected_ids":[],"item_document_ids":[]}')
        self.assertEqual(self.service.select_candidates(self.robot, '질문',
                         [self.candidate(url='https://example.org/spot-other-generation')]), [])

    def test_all_candidate_batches_are_reviewed(self):
        self.service.settings['max_candidates'] = 1
        self.service.ask = Mock(side_effect=lambda _, payload: json.dumps({
            'selected_ids': [payload['candidates'][0]['candidate_id']], 'item_document_ids': []}))
        values = [self.candidate(candidate_id=f'c{i}') for i in range(4)]
        self.assertEqual(len(self.service.select_candidates(self.robot, '질문', values)), 4)
        self.assertEqual(self.service.ask.call_count, 4)

    def test_query_cache_distinguishes_conversation(self):
        self.service.ask = Mock(return_value='{"queries":["Spot sensor"]}')
        a = [{'role': 'user', 'content': '카메라'}]
        b = [{'role': 'user', 'content': '배터리'}]
        self.service.queries(self.robot, '그건?', a)
        self.service.queries(self.robot, '그건?', a)
        self.service.queries(self.robot, '그건?', b)
        self.assertEqual(self.service.ask.call_count, 2)

    def test_successful_collection_is_cached(self):
        self.service.collector.collect = Mock(return_value=[self.candidate()])
        self.service.cached_candidates(self.robot, 'wikipedia', 'Spot')
        self.service.cached_candidates(self.robot, 'wikipedia', 'Spot')
        self.assertEqual(self.service.collector.collect.call_count, 1)

    def test_failed_collection_is_not_cached_as_success(self):
        self.service.collector.collect = Mock(return_value=[])
        for _ in range(2):
            self.service.cached_candidates(self.robot, 'wikipedia', 'Spot')
        self.assertEqual(self.service.collector.collect.call_count, 2)

    def test_own_document_ignores_length_limit_and_updates_metadata(self):
        self.service.settings['max_document_chars'] = 5
        self.service.key = Mock(return_value='test-only')
        db = Mock()
        db.get.return_value = {'ids': [], 'metadatas': []}
        self.service.store = Mock(return_value=db)
        value = self.candidate(item_document=True)
        self.service.index_documents(self.robot, [value])
        first = db.add_texts.call_args.kwargs
        self.assertGreater(sum(map(len, first['texts'])), 5)
        old = [dict(m, item_document=False) for m in first['metadatas']]
        db.get.return_value = {'ids': first['ids'], 'metadatas': old}
        db.add_texts.reset_mock()
        self.service.index_documents(self.robot, [value])
        self.assertTrue(db.add_texts.called)
        db.get.return_value = {'ids': first['ids'], 'metadatas': first['metadatas']}
        db.add_texts.reset_mock()
        self.assertEqual(self.service.index_documents(self.robot, [value]), 0)
        db.add_texts.assert_not_called()

    def test_retry_after_is_not_shortened(self):
        collector = Collector(self.service.settings)
        limited = Mock(status_code=429, headers={'Retry-After': '45'})
        ok = Mock(status_code=200)
        ok.json.return_value = {'ok': True}
        collector.session = Mock()
        collector.session.get.side_effect = [limited, ok]
        with patch('sources.time.sleep') as sleep:
            self.assertEqual(collector.get('https://example.org'), {'ok': True})
        self.assertIn(unittest.mock.call(45.0), sleep.call_args_list)

    def test_long_retry_after_stops_request(self):
        collector = Collector(self.service.settings)
        collector.session = Mock()
        collector.session.get.return_value = Mock(status_code=429, headers={'Retry-After': '120'})
        with patch('sources.time.sleep'):
            self.assertIsNone(collector.get('https://example.org'))
        self.assertEqual(collector.session.get.call_count, 1)

    def test_citations_and_missing_evidence(self):
        sources = [self.candidate(), self.candidate(candidate_id='c2')]
        self.assertEqual([n for n, _ in used_sources('사실 [근거 2]', sources)], [2])
        self.assertTrue(invalid_citations('[근거 3]', sources))
        self.assertEqual(used_sources('확인불가', sources), [])

    def test_citation_ranges_from_real_model_response(self):
        sources = [self.candidate() for _ in range(5)]
        self.assertEqual(len(used_sources('확인불가 [근거 1–5]', sources)), 5)
        self.assertFalse(invalid_citations('[근거 1-3, 5]', sources))
        for text in ('[근거 1–999999999]', '[근거 3-1]', '[근거 없음]', '[근거 0]'):
            self.assertTrue(invalid_citations(text, sources), text)

    def test_chunk_overlap_preserves_text(self):
        text = '0123456789' * 140
        chunks = split_text(text, 1000, 200)
        self.assertEqual(chunks[0] + ''.join(v[200:] for v in chunks[1:]), text)

    def test_unknown_candidate_id_is_rejected(self):
        self.service.ask = Mock(return_value='{"selected_ids":["c999"],"item_document_ids":[]}')
        with self.assertRaises(UserError):
            self.service.select_candidates(self.robot, '질문', [self.candidate()])


if __name__ == '__main__':
    unittest.main()
