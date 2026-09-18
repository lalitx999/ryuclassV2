"""Credential reload regression tests; no network or application database."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.test import SimpleTestCase, override_settings
from config.ai import get_provider_config
from courses.views import ChatBotView
from rest_framework.test import APIRequestFactory


class AIConfigTests(SimpleTestCase):
    def test_local_file_wins_and_reloads_without_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            with override_settings(DEBUG=True, BASE_DIR=Path(directory)), patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'old-parent-value'}):
                path.write_text('DEEPSEEK_API_KEY=first-value\n')
                self.assertEqual(get_provider_config('deepseek'), ('first-value', 'deepseek-chat'))
                path.write_text('DEEPSEEK_API_KEY=second-value\n')
                self.assertEqual(get_provider_config('deepseek')[0], 'second-value')
                self.assertEqual(os.environ['DEEPSEEK_API_KEY'], 'old-parent-value')

    def test_blank_local_key_disables_stale_inherited_key(self):
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(DEBUG=True, BASE_DIR=Path(directory)), patch.dict(os.environ, {'GROQ_API_KEY': 'stale'}):
                (Path(directory) / '.env').write_text('GROQ_API_KEY=\nGROQ_MODEL=\n')
                self.assertEqual(get_provider_config('GROQ'), ('', 'openai/gpt-oss-20b'))

    def test_production_uses_environment(self):
        with override_settings(DEBUG=False), patch.dict(os.environ, {'GROQ_API_KEY': ' production-key ', 'GROQ_MODEL': 'configured-model'}), patch('config.ai.dotenv_values') as read:
            self.assertEqual(get_provider_config('GROQ'), ('production-key', 'configured-model'))
            read.assert_not_called()

    def test_missing_file_preserves_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(DEBUG=True, BASE_DIR=Path(directory)), patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'env-key', 'DEEPSEEK_MODEL': 'env-model'}):
                self.assertEqual(get_provider_config('DEEPSEEK'), ('env-key', 'env-model'))

    def test_chat_uses_updated_config_and_falls_back(self):
        from unittest.mock import Mock
        failure = Mock(status_code=503, text='test service unavailable')
        success = Mock(status_code=200)
        success.json.return_value = {'choices': [{'message': {'content': 'OK'}}], 'model': 'openai/gpt-oss-20b'}
        with patch('courses.views.get_provider_config', side_effect=[('deepseek-test', 'deepseek-chat'), ('groq-test', 'openai/gpt-oss-20b')]), patch('courses.views.requests.post', side_effect=[failure, success]) as post:
            request = APIRequestFactory().post('/api/courses/chatbot/', {'messages': [{'role': 'user', 'content': 'Hello'}]}, format='json')
            response = ChatBotView.as_view()(request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['choices'][0]['message']['content'], 'OK')
            self.assertEqual(post.call_args_list[0].kwargs['headers']['Authorization'], 'Bearer deepseek-test')
            self.assertEqual(post.call_args_list[1].kwargs['headers']['Authorization'], 'Bearer groq-test')
            self.assertEqual(post.call_args_list[1].kwargs['json']['model'], 'openai/gpt-oss-20b')


if __name__ == '__main__':
    unittest.main()
