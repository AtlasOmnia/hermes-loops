from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicPackagingTests(unittest.TestCase):
    def test_readme_is_context_complete_and_links_public_docs(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in (
            "Python 3.10 or newer",
            "Health loop",
            "Improvement loop",
            "never",
            "MIT License",
            "not an official Hermes Agent or Nous Research product",
            "docs/architecture.md",
            "docs/privacy.md",
            "docs/install.md",
            "docs/testing.md",
        ):
            self.assertIn(phrase, readme)
        self.assertNotIn("Private first", readme)
        self.assertNotIn("private runtime", readme)

    def test_architecture_svg_declares_accessible_independent_lanes(self) -> None:
        svg = (ROOT / "docs" / "architecture.svg").read_text(encoding="utf-8")
        for phrase in (
            '<svg',
            'viewBox="0,0,1200,900"',
            '<title',
            '<desc',
            "Health",
            "read-only bounded probes",
            "concise status",
            "Improvement",
            "explicit packet source",
            "redaction",
            "human-review-only suggestion",
            "Optional report",
            "configuration",
            "scheduler",
            "provider",
            "delivery",
        ):
            self.assertIn(phrase, svg)
        self.assertNotIn("https://", svg)


if __name__ == "__main__":
    unittest.main()
