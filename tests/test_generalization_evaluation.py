import json
import subprocess
import sys
import unittest

from evaluation.generalization import (
    GENERALIZATION_SPECS, HOLDOUT_SPECS, generalization_cases, holdout_cases, paper12_cases,
)
from evaluation.scoring import score_response


class GeneralizationEvaluationTests(unittest.TestCase):
    def test_frozen_paper_suite_is_unchanged_and_separate(self):
        paper = paper12_cases()
        expanded = generalization_cases()
        self.assertEqual(len(paper), 12)
        self.assertEqual(
            [item["id"] for item in paper],
            ["T01", "T05", "T09", "E01", "E05", "E07",
             "F01", "F03", "F05", "O05", "O06", "O07"],
        )
        self.assertFalse(set(item["id"] for item in paper) & set(item["id"] for item in expanded))
        frozen_text = {
            text.strip().lower()
            for item in paper
            for text in [*item["setup"], item["message"]]
        }
        prospective_text = {
            text.strip().lower()
            for item in expanded
            for text in [*item["setup"], item["message"]]
        }
        self.assertFalse(frozen_text & prospective_text)

    def test_expanded_inventory_has_distinct_cases(self):
        cases = generalization_cases()
        families = [item["category"] for item in cases]
        self.assertEqual(families.count("update"), 10)
        self.assertEqual(families.count("followup"), 10)
        self.assertEqual(families.count("error"), 9)
        error_families = [item["error_family"] for item in cases if item["category"] == "error"]
        self.assertEqual(error_families.count("subject_verb_agreement"), 3)
        self.assertEqual(error_families.count("count_noun_quantifier"), 3)
        self.assertEqual(error_families.count("verb_complementation"), 3)
        self.assertEqual(sum(item["control"] == "unseen_value_violin" for item in cases), 2)
        self.assertEqual(len(GENERALIZATION_SPECS), len(cases))

    def test_update_scoring_requires_value_role_and_no_stale_value(self):
        passed = score_response("O-GEN-02", "You ride your scooter to the library.")
        wrong_role = score_response("O-GEN-02", "I ride my scooter to the library.")
        stale = score_response("O-GEN-02", "You use a scooter now, but you used to walk.")
        self.assertTrue(passed["overall_pass"])
        self.assertFalse(wrong_role["second_person_role_correct"])
        self.assertFalse(wrong_role["overall_pass"])
        self.assertFalse(stale["no_stale_value"])
        self.assertFalse(stale["overall_pass"])

    def test_followup_and_error_families_are_scored(self):
        self.assertTrue(score_response("F-GEN-04", "You practise the violin.")["overall_pass"])
        self.assertTrue(score_response("E-COUNT-02", "Our school needs fewer recycling bins.")["overall_pass"])
        self.assertFalse(score_response("E-COUNT-02", "Our school needs less recycling bins.")["overall_pass"])
        self.assertTrue(score_response("O-GEN-10", "You save water by taking short showers.")["overall_pass"])
        self.assertTrue(score_response("F-GEN-07", "You clean your room on Saturdays.")["overall_pass"])

    def test_generalization_dry_run_calls_no_model(self):
        result = subprocess.run(
            [sys.executable, "evaluation/run.py", "--suite", "generalization", "--dry-run"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(len(json.loads(result.stdout)), 29)

    def test_holdout_is_distinct_and_dry_run_is_offline(self):
        holdout = holdout_cases()
        self.assertEqual(len(holdout), 16)
        self.assertEqual(len(HOLDOUT_SPECS), 16)
        all_development_text = {
            text.strip().lower()
            for item in [*paper12_cases(), *generalization_cases()]
            for text in [*item["setup"], item["message"]]
        }
        holdout_text = {
            text.strip().lower()
            for item in holdout
            for text in [*item["setup"], item["message"]]
        }
        self.assertFalse(all_development_text & holdout_text)
        result = subprocess.run(
            [sys.executable, "evaluation/run.py", "--suite", "holdout", "--dry-run"],
            check=True, capture_output=True, text=True,
        )
        self.assertEqual(len(json.loads(result.stdout)), 16)


if __name__ == "__main__":
    unittest.main()
