import math
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.ml import embeddings
from app.ml.embeddings import EmbeddingError, get_embedding
from app.ml.matcher import calculate_skill_overlap, cosine_similarity


class MatcherTests(unittest.TestCase):
    def test_cosine_identical_orthogonal_and_opposite_vectors(self):
        self.assertAlmostEqual(cosine_similarity([1, 2, 3], [1, 2, 3]), 1)
        self.assertEqual(cosine_similarity([1, 0], [0, 1]), 0)
        self.assertAlmostEqual(cosine_similarity([1, 0], [-1, 0]), -1)
        self.assertAlmostEqual(cosine_similarity([1e308, 1e308], [1e308, 1e308]), 1)

    def test_cosine_zero_and_invalid_vectors(self):
        self.assertEqual(cosine_similarity([], []), 0)
        self.assertEqual(cosine_similarity([0, 0], [1, 2]), 0)
        for first, second in [([1], [1, 2]), ([math.nan], [1]), ([math.inf], [1])]:
            with self.assertRaises(ValueError):
                cosine_similarity(first, second)

    def test_overlap_normalizes_case_whitespace_and_duplicates(self):
        result = calculate_skill_overlap([" python ", "SQL", "python"], ["Python", " python ", "sql", "Docker", " "])
        self.assertEqual(result["matched_skills"], ["Python", "sql"])
        self.assertEqual(result["missing_skills"], ["Docker"])
        self.assertAlmostEqual(result["overlap_percentage"], 200 / 3)

    def test_overlap_empty_full_and_absent_matches(self):
        self.assertEqual(calculate_skill_overlap([], ["Python"])["missing_skills"], ["Python"])
        self.assertEqual(calculate_skill_overlap(["Python"], ["python"])["overlap_percentage"], 100)
        self.assertEqual(calculate_skill_overlap([], [])["overlap_percentage"], 0)
        self.assertEqual(calculate_skill_overlap(["Go"], ["Python"])["overlap_percentage"], 0)


class EmbeddingTests(unittest.TestCase):
    def test_lazy_model_load_is_cached_and_vectors_are_float_lists(self):
        model = Mock()
        model.encode.return_value.tolist.return_value = [1, 2, 3]
        constructor = Mock(return_value=model)
        fake_module = SimpleNamespace(SentenceTransformer=constructor)
        with patch.object(embeddings, "_model", None), patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            self.assertEqual(get_embedding("resume"), [1.0, 2.0, 3.0])
            self.assertEqual(get_embedding("job"), [1.0, 2.0, 3.0])
            constructor.assert_called_once_with(embeddings.MODEL_NAME)
            self.assertEqual(model.encode.call_count, 2)
            self.assertTrue(model.encode.call_args.kwargs["normalize_embeddings"])

    def test_blank_text_does_not_load_model(self):
        with patch.object(embeddings, "_load_model") as load:
            for text in ["", " "]:
                with self.assertRaises(ValueError):
                    get_embedding(text)
            load.assert_not_called()

    def test_load_and_encode_errors_are_clear(self):
        fake_module = SimpleNamespace(SentenceTransformer=Mock(side_effect=RuntimeError("internal error")))
        with patch.object(embeddings, "_model", None), patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            with self.assertRaises(EmbeddingError):
                get_embedding("resume")
        model = Mock()
        for output in [[], [float("nan")]]:
            model.encode.return_value.tolist.return_value = output
            with patch.object(embeddings, "_load_model", return_value=model):
                with self.assertRaises(EmbeddingError):
                    get_embedding("resume")
