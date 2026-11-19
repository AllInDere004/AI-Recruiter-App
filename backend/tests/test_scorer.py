import unittest
from unittest.mock import patch

from app.ml.scorer import _key_phrases, score_draft


class DraftScorerTests(unittest.TestCase):
    def test_identical_aligned_text_has_full_score(self):
        with patch("app.ml.scorer.get_embedding", return_value=[1, 0]) as encode:
            self.assertEqual(score_draft("Python SQL", "Python SQL", "Python SQL"), 100)
            self.assertEqual(encode.call_count, 3)

    def test_semantic_and_phrase_coverage_weights(self):
        with patch("app.ml.scorer.get_embedding", return_value=[1, 0]):
            self.assertAlmostEqual(score_draft("Python", "Python Docker", "Python"), 83.33)
        with patch("app.ml.scorer.get_embedding", side_effect=[[1, 0], [0, 1], [1, 0]]):
            self.assertAlmostEqual(score_draft("Python", "Python Docker", "Python"), 38.33)

    def test_empty_draft_scores_zero_without_embedding(self):
        with patch("app.ml.scorer.get_embedding") as encode:
            self.assertEqual(score_draft("Resume", "Job", " "), 0)
            encode.assert_not_called()
        with self.assertRaises(ValueError):
            score_draft(" ", "Job", "Email")

    def test_negative_similarity_is_clamped_and_no_phrases_uses_semantics(self):
        with patch("app.ml.scorer.get_embedding", side_effect=[[1, 0], [1, 0], [-1, 0]]):
            self.assertEqual(score_draft("Python", "Python", "Cooking"), 0)
        with patch("app.ml.scorer.get_embedding", return_value=[1, 0]):
            self.assertEqual(score_draft("Resume", "and the", "Email"), 100)

    def test_technical_tokens_are_preserved(self):
        phrases = _key_phrases("C++ C# .NET Node.js Python")
        for phrase in ["c++", "c#", ".net", "node.js", "python"]:
            self.assertIn(phrase, phrases)
