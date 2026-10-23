"""Streamlit AppTest로 API 호출 없는 화면·오류·세션 전환 검증."""
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from rag_core import UserError

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


class UITests(unittest.TestCase):
    def test_model_histories_survive_switch(self):
        with patch('rag_core.RobotService.counts', return_value={'robot_meta_v2': 200, 'robot_docs_v2': 1647}):
            app = AppTest.from_file(APP).run()
            app.session_state['histories'] = {
                'robot_001': [{'role': 'user', 'content': 'Atlas 전용 질문'}],
                'robot_006': [{'role': 'user', 'content': 'Ameca 전용 질문'}]}
            app.selectbox(key='robot_id').set_value('robot_006').run()
            text = '\n'.join(v.value for v in app.markdown)
            self.assertIn('Ameca 전용 질문', text)
            self.assertNotIn('Atlas 전용 질문', text)
            app.selectbox(key='robot_id').set_value('robot_001').run()
            text = '\n'.join(v.value for v in app.markdown)
            self.assertIn('Atlas 전용 질문', text)
            self.assertNotIn('Ameca 전용 질문', text)
            self.assertEqual(len(app.exception), 0)

    def test_missing_key_message_has_no_traceback(self):
        with patch('rag_core.RobotService.counts', side_effect=UserError('.env에 기존 GMS_KEY를 설정하세요.')):
            app = AppTest.from_file(APP).run()
            self.assertTrue(any('GMS_KEY' in warning.value for warning in app.warning))
            self.assertEqual(len(app.exception), 0)

    def test_empty_index_warning(self):
        with patch('rag_core.RobotService.counts', return_value={'robot_meta_v2': 0, 'robot_docs_v2': 0}):
            app = AppTest.from_file(APP).run()
            self.assertTrue(any('색인이 없습니다' in warning.value for warning in app.warning))
            self.assertEqual(len(app.exception), 0)


if __name__ == '__main__':
    unittest.main()
