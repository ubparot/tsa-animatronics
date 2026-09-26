from pathlib import Path
import unittest

from performance_lab import (
    MAX_CELLS,
    build_configs,
    build_round,
    choose_lines,
    load_battery,
    settings_for,
    summarize_round,
    total_clips,
    validate_ratings,
    weighted_score,
)


BATTERY_PATH = Path(__file__).resolve().parent / "eval" / "test_lines.json"


def references(count: int = 8):
    return [
        {"id": f"chr_{index:04}.wav", "path": f"C:/voices/chr_{index:04}.wav"}
        for index in range(count)
    ]


def battery():
    return [
        {"id": "confess_01", "category": "confession", "text": "[sigh] It was me.", "tagged": True},
        {"id": "confess_02", "category": "confession", "text": "I did it.", "tagged": False},
        {"id": "lie_01", "category": "lie", "text": "I was here all along.", "tagged": False},
        {"id": "long_01", "category": "long", "text": "A very long line indeed.", "tagged": False},
        {"id": "greet_01", "category": "greeting", "text": "Hello there!", "tagged": False},
    ]


CURRENT = {
    "temperature": 0.8,
    "top_p": 0.95,
    "top_k": 1000,
    "repetition_penalty": 1.2,
    "seed": 20260920,
}


class ConfigDesignTests(unittest.TestCase):
    def test_reference_round_isolates_reference_recording(self):
        configs = build_configs("reference", references(), CURRENT, 4)
        self.assertEqual(4, len(configs))
        self.assertEqual(4, len({item["reference_id"] for item in configs}))
        self.assertEqual({0.8}, {item["temperature"] for item in configs})
        self.assertEqual({1.2}, {item["repetition_penalty"] for item in configs})

    def test_delivery_round_starts_at_the_live_setting(self):
        configs = build_configs("delivery", references(1), CURRENT, 4)
        self.assertEqual(4, len(configs))
        self.assertEqual(1, len({item["reference_id"] for item in configs}))
        self.assertEqual((0.8, 1.2), (configs[0]["temperature"], configs[0]["repetition_penalty"]))

    def test_delivery_round_moves_one_knob_at_a_time(self):
        configs = build_configs("delivery", references(1), CURRENT, 4)
        for config in configs[1:]:
            moved = [
                config["temperature"] != CURRENT["temperature"],
                config["repetition_penalty"] != CURRENT["repetition_penalty"],
            ]
            self.assertEqual(1, sum(moved), config)

    def test_delivery_round_sweeps_repetition_penalty(self):
        configs = build_configs("delivery", references(1), CURRENT, 4)
        self.assertGreater(len({item["repetition_penalty"] for item in configs}), 1)

    def test_repetition_penalty_stays_inside_the_engine_bounds(self):
        low = {**CURRENT, "repetition_penalty": 1.0}
        configs = build_configs("delivery", references(1), low, 4)
        for config in configs:
            self.assertGreaterEqual(config["repetition_penalty"], 1.0)
            self.assertLessEqual(config["repetition_penalty"], 2.0)

    def test_top_k_is_never_swept(self):
        for mode, pool in (("reference", references()), ("delivery", references(1)), ("mixed", references())):
            configs = build_configs(mode, pool, CURRENT, 4)
            self.assertEqual({1000}, {item["top_k"] for item in configs}, mode)

    def test_mixed_round_changes_reference_and_delivery(self):
        configs = build_configs("mixed", references(), CURRENT, 4)
        self.assertEqual(4, len({item["reference_id"] for item in configs}))
        self.assertGreater(len({item["temperature"] for item in configs}), 1)


class LineSelectionTests(unittest.TestCase):
    def test_operator_line_comes_first(self):
        lines = choose_lines(battery(), "  My own line.  ", 3)
        self.assertEqual("custom", lines[0]["id"])
        self.assertEqual("My own line.", lines[0]["text"])

    def test_lines_span_distinct_categories(self):
        lines = choose_lines(battery(), "My own line.", 4)
        self.assertEqual(4, len(lines))
        self.assertEqual(4, len({item["category"] for item in lines}))

    def test_tagged_lines_are_preferred_within_a_category(self):
        lines = choose_lines(battery(), "My own line.", 2)
        self.assertEqual("confess_01", lines[1]["id"])

    def test_blank_line_is_rejected(self):
        with self.assertRaises(ValueError):
            choose_lines(battery(), "   ", 3)

    def test_shipped_battery_covers_every_priority_category(self):
        lines = choose_lines(load_battery(BATTERY_PATH), "My own line.", 4)
        self.assertEqual(4, len(lines))
        self.assertEqual(4, len({item["category"] for item in lines}))


class RoundLayoutTests(unittest.TestCase):
    def test_every_config_speaks_every_line_at_every_seed(self):
        plan = build_round("reference", references(), CURRENT, battery(), "My own line.", 3, 3, 3)
        self.assertEqual(9, len(plan["cells"]))
        self.assertEqual(27, total_clips(plan))
        self.assertEqual(9, len({cell["id"] for cell in plan["cells"]}))
        for cell in plan["cells"]:
            self.assertEqual([1, 2, 3], [take["index"] for take in cell["takes"]])
            self.assertEqual(plan["seeds"], [take["seed"] for take in cell["takes"]])

    def test_seeds_are_shared_across_configs_so_they_cannot_confound(self):
        plan = build_round("mixed", references(), CURRENT, battery(), "My own line.", 3, 2, 3)
        by_config = {}
        for cell in plan["cells"]:
            by_config.setdefault(cell["config_id"], set()).update(
                take["seed"] for take in cell["takes"]
            )
        self.assertEqual(1, len({frozenset(seeds) for seeds in by_config.values()}))

    def test_round_refuses_more_cells_than_a_rater_can_sit_through(self):
        with self.assertRaises(ValueError):
            build_round("reference", references(), CURRENT, battery(), "My own line.", 4, 4, 2)

    def test_largest_allowed_round_still_fits_the_cap(self):
        plan = build_round("reference", references(), CURRENT, battery(), "My own line.", 4, 3, 4)
        self.assertEqual(MAX_CELLS, len(plan["cells"]))
        self.assertEqual(48, total_clips(plan))
        self.assertEqual(len(plan["cells"]), len({cell["id"] for cell in plan["cells"]}))

    def test_settings_for_carries_the_config_and_the_seed(self):
        plan = build_round("reference", references(), CURRENT, battery(), "My own line.", 2, 2, 2)
        settings = settings_for(plan["configs"][0], 424242)
        self.assertEqual(424242, settings["seed"])
        self.assertEqual(plan["configs"][0]["reference_path"], settings["reference_path"])
        self.assertEqual(1000, settings["top_k"])


class ScoringTests(unittest.TestCase):
    def test_ratings_require_all_four_integer_values(self):
        good = {"similarity": 7, "naturalness": 6, "character": 5, "funniness": 4}
        self.assertEqual(good, validate_ratings(good))
        with self.assertRaises(ValueError):
            validate_ratings({**good, "funniness": 8})
        with self.assertRaises(ValueError):
            validate_ratings({"similarity": 7})

    def test_weighted_score_matches_declared_weighting(self):
        ratings = {"similarity": 7, "naturalness": 6, "character": 5, "funniness": 4}
        self.assertEqual(5.65, weighted_score(ratings))

    def test_config_score_is_the_mean_across_its_lines(self):
        plan = build_round("reference", references(), CURRENT, battery(), "My own line.", 2, 2, 2)
        scores = {("A"): 7, "B": 3, "C": 5, "D": 5}
        for cell in plan["cells"]:
            value = scores[cell["id"]]
            cell["ratings"] = {key: value for key in ("similarity", "naturalness", "character", "funniness")}
        results = summarize_round(plan["configs"], plan["lines"], plan["cells"])
        self.assertEqual(5.0, results[0]["score"])
        self.assertEqual(5.0, results[1]["score"])
        # Equal means, so the steadier configuration has to win the tie.
        self.assertEqual(0.0, results[0]["spread"])
        self.assertEqual(4.0, results[1]["spread"])

    def test_results_refuse_to_reveal_before_every_cell_is_rated(self):
        plan = build_round("reference", references(), CURRENT, battery(), "My own line.", 2, 2, 2)
        with self.assertRaises(ValueError):
            summarize_round(plan["configs"], plan["lines"], plan["cells"])


if __name__ == "__main__":
    unittest.main()
