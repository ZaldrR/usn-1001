
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from .gigachat_client import get_recommendation


BENCHMARK_DIR = Path(__file__).resolve().parent


class TestGigaChatClient(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with (
            BENCHMARK_DIR / "case_01.json"
        ).open("r", encoding="utf-8") as file:
            cls.case_data = json.load(file)

    def mock_response(self, content):
        response = MagicMock()
        response.choices[0].message.content = content
        return response

    @patch(
        "assignment.benchmark.gigachat_client.GigaChat"
    )
    @patch(
        "assignment.benchmark.gigachat_client.os.getenv",
        return_value="test-key"
    )
    def test_valid_recommendation(
        self, mock_getenv, mock_gigachat
    ):
        client = mock_gigachat.return_value.__enter__.return_value

        client.chat.return_value = self.mock_response(
            '{"judge_id": "J03", "reason": "Доступен"}'
        )

        result = get_recommendation(self.case_data)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["judge_id"], "J03")
        self.assertEqual(result["errors"], [])

    @patch(
        "assignment.benchmark.gigachat_client.GigaChat"
    )
    @patch(
        "assignment.benchmark.gigachat_client.os.getenv",
        return_value="test-key"
    )
    def test_hallucinated_judge(
        self, mock_getenv, mock_gigachat
    ):
        client = mock_gigachat.return_value.__enter__.return_value

        client.chat.return_value = self.mock_response(
            '{"judge_id": "J99", "reason": "Подходит"}'
        )

        result = get_recommendation(self.case_data)

        self.assertEqual(
            result["status"],
            "invalid_recommendation"
        )
        self.assertTrue(result["errors"])

    @patch(
        "assignment.benchmark.gigachat_client.GigaChat"
    )
    @patch(
        "assignment.benchmark.gigachat_client.os.getenv",
        return_value="test-key"
    )
    def test_invalid_json(
        self, mock_getenv, mock_gigachat
    ):
        client = mock_gigachat.return_value.__enter__.return_value

        client.chat.return_value = self.mock_response(
            "Это не JSON"
        )

        result = get_recommendation(self.case_data)

        self.assertEqual(result["status"], "format_error")

    @patch(
        "assignment.benchmark.gigachat_client.GigaChat"
    )
    @patch(
        "assignment.benchmark.gigachat_client.os.getenv",
        return_value="test-key"
    )
    def test_api_error(
        self, mock_getenv, mock_gigachat
    ):
        client = mock_gigachat.return_value.__enter__.return_value
        client.chat.side_effect = ConnectionError(
            "Сервис недоступен"
        )

        result = get_recommendation(self.case_data)

        self.assertEqual(result["status"], "api_error")
        self.assertTrue(result["errors"])

    @patch(
        "assignment.benchmark.gigachat_client.os.getenv",
        return_value=None
    )
    def test_missing_api_key(self, mock_getenv):
        result = get_recommendation(self.case_data)

        self.assertEqual(result["status"], "config_error")


if __name__ == "__main__":
    unittest.main()
