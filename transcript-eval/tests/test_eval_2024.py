import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("eval_2024", ROOT / "eval_2024.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class PilotToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rubric = tool.load_database_rubric()

    def test_full_transcript_preserves_tail_and_whitespace(self):
        text = "начало\n\n" + "контекст " * 1000 + "\r\nКОНЕЦ ЗАНЯТИЯ"
        prompt = tool.build_prompt(self.rubric[0], text)
        self.assertIn(text, prompt)
        self.assertIn("КОНЕЦ ЗАНЯТИЯ", prompt)

    def test_zero_is_a_valid_score_with_evidence(self):
        response = 'Статус: scored\nОценка: 0/2\nЦитаты: ["точная цитата"]'
        result = tool.parse_response(response, "текст: точная цитата")
        self.assertEqual(result["score"], 0)
        self.assertIsNone(result["evidence"][0]["start_ms"])

    def test_api_error_does_not_become_zero(self):
        def fail(prompt):
            raise RuntimeError("private detail")
        results = tool.analyze_criteria("непустой транскрипт", self.rubric[:1], fail)
        self.assertEqual(results[0]["result_status"], "error")
        self.assertIsNone(results[0]["score"])
        self.assertNotIn("private detail", json.dumps(results))

    def test_missing_out_of_range_and_conflicting_scores_fail(self):
        for text in ["нет балла", "Оценка: 3/2", "Оценка: 1/2\nОценка: 2/2", "Оценка: 1/2\nОценка: 1/2", "Оценка: 1/2\nОценка: -1/2"]:
            self.assertIsNone(tool.extract_score(text))

    def test_insufficient_data_is_not_zero_and_conflict_fails(self):
        result = tool.parse_response("Статус: insufficient_data", "текст")
        self.assertIsNone(result["score"])
        for line in ["Оценка: 0/2", "Оценка: 3/2", "Оценка: неверно"]:
            with self.assertRaises(ValueError):
                tool.parse_response("Статус: insufficient_data\n" + line, "текст")

    def test_non_text_provider_response_is_error(self):
        result = tool.analyze_criteria("текст", self.rubric[:1], lambda p: {"unexpected": True})[0]
        self.assertEqual(result["result_status"], "error")
        self.assertIsNone(result["raw_response"])
        self.assertIsNone(result["score"])

    def test_invented_quote_and_no_quote_are_invalid_output(self):
        for response in ['Статус: scored\nОценка: 2/2\nЦитаты: ["выдумано"]',
                         'Статус: scored\nОценка: 2/2']:
            result = tool.analyze_criteria("исходный текст", self.rubric[:1], lambda prompt: response)[0]
            self.assertEqual(result["result_status"], "invalid_output")
            self.assertIsNone(result["score"])

    def test_repeated_quote_keeps_all_locations(self):
        result = tool.parse_response('Статус: scored\nОценка: 1/2\nЦитаты: ["пример"]', "пример, ещё пример")
        self.assertEqual([x["start_char"] for x in result["evidence"][0]["occurrences"]], [0, 12])
        overlapping = tool.parse_response('Статус: scored\nОценка: 1/2\nЦитаты: ["аа"]', "ааа")
        self.assertEqual([x["start_char"] for x in overlapping["evidence"][0]["occurrences"]], [0, 1])

    def test_coze_adapter_uses_only_answer_messages_and_requires_completed(self):
        captured = []
        response = SimpleNamespace(chat=SimpleNamespace(status="completed"), messages=[
            SimpleNamespace(role="assistant", type="answer", content="answer"),
            SimpleNamespace(role="assistant", type="verbose", content="service details"),
            SimpleNamespace(role="user", type="answer", content="echoed input")])
        def poll(**kwargs):
            captured.append(kwargs)
            return response
        sdk = SimpleNamespace(Coze=lambda **kwargs: SimpleNamespace(chat=SimpleNamespace(create_and_poll=poll)),
                              TokenAuth=lambda token: "fixture",
                              Message=SimpleNamespace(build_user_question_text=lambda text: text))
        with patch.dict("sys.modules", {"cozepy": sdk}), patch.dict("os.environ", {
                "COZE_API_TOKEN": "fixture", "COZE_BOT_ID": "fixture", "COZE_USER_ID": "fixture"}):
            ask = tool.make_coze_ask()
            self.assertEqual(ask("full input"), "answer")
            self.assertEqual(captured[0]["additional_messages"], ["full input"])
            response.chat.status = "failed"
            with self.assertRaises(RuntimeError):
                ask("full input")

    def test_original_rubric_has_all_78_exact_scores(self):
        self.assertEqual(len(self.rubric), 26)
        self.assertEqual(sum(len(c["scores"]) for c in self.rubric), 78)
        self.assertEqual(self.rubric[0]["text"], "Уместность")
        self.assertEqual(self.rubric[-1]["text"], '«Делает то, что проповедует»')

    def test_report_preserves_raw_response_and_does_not_sum_partial_scores(self):
        response = 'Статус: scored\nОценка: 0/2\nЦитаты: ["цитата"]'
        results = tool.analyze_criteria("цитата", self.rubric[:1], lambda p: response)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run.json"
            tool.save_report({"run_id": "fixture", "input": {"characters": 6}, "results": results}, output)
            stored = json.loads(output.read_text())
            self.assertEqual(stored["results"][0]["raw_response"], response)
            self.assertNotIn("Общий балл:", output.with_suffix(".md").read_text())
            with self.assertRaises(FileExistsError):
                tool.save_report(stored, output)

    def test_existing_markdown_is_not_replaced_or_left_with_partial_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run.json"
            output.with_suffix(".md").write_text("previous")
            with self.assertRaises(FileExistsError):
                tool.save_report({}, output)
            self.assertFalse(output.exists())
            self.assertEqual(output.with_suffix(".md").read_text(), "previous")


if __name__ == "__main__":
    unittest.main()
