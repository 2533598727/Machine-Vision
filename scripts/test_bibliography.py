"""Regression tests for Chinese names and first-appearance citation ordering."""

import unittest

from build_artifacts import bibtex_authors, latex_inline, prose_statistics, read_sources


class BibliographyTests(unittest.TestCase):
    def test_english_names_keep_family_initial_order(self):
        self.assertEqual(bibtex_authors("Land E H, McCann J J"), "Land, E H and McCann, J J")

    def test_chinese_names_are_literal_bibtex_names(self):
        self.assertEqual(bibtex_authors("王奎, 黄福珍"), "{王奎} and {黄福珍}")

    def test_mixed_names_preserve_both_forms(self):
        self.assertEqual(bibtex_authors("王奎, Brown M S"), "{王奎} and Brown, M S")

    def test_citations_follow_bibliography_order(self):
        source, references = read_sources()
        self.assertEqual(prose_statistics(source)["citation_first_appearance_order"],
                         [reference["id"] for reference in references])

    def test_chinese_citations_resolve_to_stable_keys(self):
        _, references = read_sources()
        keys = {reference["id"]: reference["key"] for reference in references}
        for reference in references:
            if reference.get("language") == "zh":
                self.assertIn(r"\cite{" + reference["key"] + "}",
                              latex_inline(f"相关研究[{reference['id']}]。", keys))


if __name__ == "__main__":
    unittest.main()
