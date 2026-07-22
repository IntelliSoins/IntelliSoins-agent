"""Unit tests — sentence chunking."""

from __future__ import annotations

import unittest

import _path  # noqa: F401

from voice_agent.sentence import flush_remainder, for_tts, pop_sentences


class TestSentence(unittest.TestCase):
    def test_for_tts_strips_markdown(self) -> None:
        self.assertEqual(for_tts("**bonjour** *toi*"), "bonjour toi")
        self.assertEqual(for_tts("# Titre\n- item"), "Titre item")

    def test_pop_sentences_first_immediate(self) -> None:
        sentences, rest = pop_sentences(
            "Bonjour. Suite incomplete", first_done=False, min_chars=90
        )
        self.assertEqual(sentences, ["Bonjour."])
        self.assertEqual(rest, "Suite incomplete")

    def test_pop_sentences_merges_short_followups(self) -> None:
        buf = "Première phrase assez longue pour passer. Ok. Encore."
        sentences, rest = pop_sentences(buf, first_done=True, min_chars=40)
        self.assertTrue(sentences)
        self.assertEqual(rest, "")
        self.assertTrue(any("Ok." in s for s in sentences))

    def test_flush_remainder(self) -> None:
        self.assertEqual(flush_remainder("  sans point  "), ["sans point"])
        self.assertEqual(flush_remainder("   "), [])


if __name__ == "__main__":
    unittest.main()
