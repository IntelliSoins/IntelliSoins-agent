"""Unit tests — red-flag scanning (deterministic, never diagnoses)."""

from __future__ import annotations

import unittest

import _path  # noqa: F401

from voice_agent.tools.red_flags import scan_many, scan_red_flags


class TestRedFlags(unittest.TestCase):
    def test_no_match(self) -> None:
        result = scan_red_flags("Je voudrais prendre rendez-vous demain.")
        self.assertFalse(result.triggered)
        self.assertEqual(result.max_severity, "none")
        payload = result.as_dict()
        self.assertIsNone(payload["matches"][0]["diagnosis"] if payload["matches"] else None)
        self.assertIn("Not a diagnosis", payload["disclaimer"])

    def test_suicidality(self) -> None:
        result = scan_red_flags("Parfois je veux me suicider.")
        self.assertTrue(result.triggered)
        self.assertEqual(result.max_severity, "critical")
        self.assertEqual(result.matches[0].code, "suicidality")
        self.assertIsNone(result.matches[0].diagnosis)
        self.assertEqual(result.matches[0].action, "route_to_human")

    def test_chest_pain(self) -> None:
        result = scan_red_flags("J'ai une douleur dans la poitrine depuis ce matin.")
        self.assertTrue(result.triggered)
        codes = {m.code for m in result.matches}
        self.assertIn("chest_pain_acute", codes)

    def test_never_diagnoses_in_payload(self) -> None:
        result = scan_red_flags("I can't breathe and have chest pain")
        for match in result.matches:
            self.assertIsNone(match.diagnosis)
        for item in result.as_dict()["matches"]:
            self.assertIsNone(item["diagnosis"])

    def test_scan_many_merges(self) -> None:
        result = scan_many(
            ["hello", "je veux me tuer", "also can't breathe"]
        )
        codes = {m.code for m in result.matches}
        self.assertIn("suicidality", codes)
        self.assertIn("breathing_difficulty", codes)


if __name__ == "__main__":
    unittest.main()
