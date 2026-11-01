from __future__ import annotations

import unittest

from factoria.cli import build_parser


class LifecycleCliParserTests(unittest.TestCase):
    def test_commit_command_is_available(self) -> None:
        args = build_parser().parse_args(["commit", "flow-1"])
        self.assertEqual(args.command, "commit")
        self.assertEqual(args.flow_id, "flow-1")

    def test_commit_exposes_manual_verification_confirmation(self) -> None:
        args = build_parser().parse_args(
            ["commit", "flow-1", "--confirm-manual-verification", "--yes"]
        )
        self.assertTrue(args.confirm_manual_verification)
        self.assertTrue(args.yes)

    def test_history_command_is_available(self) -> None:
        args = build_parser().parse_args(["history", "--kind", "fix", "--limit", "5"])
        self.assertEqual(args.command, "history")
        self.assertEqual(args.kind, "fix")
        self.assertEqual(args.limit, 5)


if __name__ == "__main__":
    unittest.main()
