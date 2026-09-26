from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from humor_lab import trainer


class HumorLabTests(unittest.TestCase):
    def test_experiment_has_balanced_unique_lines(self) -> None:
        experiment = trainer.load_experiment()
        lines = experiment["lines"]
        self.assertEqual(len(lines), 72)
        self.assertEqual(len({line["id"] for line in lines}), len(lines))
        self.assertTrue(all(0 < len(line["text"]) <= 180 for line in lines))
        devices: dict[str, int] = {}
        for line in lines:
            devices[line["device"]] = devices.get(line["device"], 0) + 1
        self.assertEqual(set(devices.values()), {8})
        self.assertIn("straight_control", devices)

    def test_latest_rating_wins(self) -> None:
        rows = [
            {"rater_id": "rater_test", "line_id": "literal_01", "rating": 2},
            {"rater_id": "rater_test", "line_id": "literal_01", "rating": 6},
        ]
        latest = trainer.latest_ratings(rows)
        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0]["rating"], 6)

    def test_trainer_writes_model_and_prompt(self) -> None:
        lines = trainer.load_experiment()["lines"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ratings_path = root / "ratings.jsonl"
            rows = []
            for index, line in enumerate(lines[:24]):
                rating = 7 if line["device"] == "literal_logic" else 3 + index % 3
                rows.append({
                    "time": index,
                    "rater_id": "rater_test_1234",
                    "line_id": line["id"],
                    "rating": rating,
                })
            ratings_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            model_path = root / "model.json"
            prompt_path = root / "prompt.txt"
            model = trainer.train_model(ratings_path, model_path, prompt_path)
            self.assertEqual(model["training_examples"], 24)
            self.assertTrue(model_path.is_file())
            self.assertTrue(prompt_path.is_file())
            self.assertEqual(model["format"], "pinocchio_humor_reranker_v1")
            self.assertIsNotNone(model["cross_validation"])
            self.assertEqual(model["insights"]["device"][0]["name"], "literal_logic")


if __name__ == "__main__":
    unittest.main()
