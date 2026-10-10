#!/usr/bin/env python3
"""Check closure authorization instructions; never calls Fizzy or a model.

Run: python3 tests/fizzy-closure-policy.py [--installed]
Installed mode also checks user-owned shared skills and managed personal prompts.
"""

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPTS = {
    "pi": ("modules/home-manager/pi-prompts/wrap.md", ".config/pi/prompts/wrap.md"),
    "claude": (
        "modules/home-manager/claude-prompts/wrap.md",
        ".config/claude-personal/commands/wrap.md",
    ),
}
FORBIDDEN = (
    "Finish with `fizzy card close",
    "File remaining work and update/close issues",
    "# Close the card when done",
    "# When done, close it",
    "**Document and close the Fizzy card**",
    '"Add completion comment" -> "Close Fizzy card"',
)


def check_policy(path):
    text = path.read_text()
    for phrase in (
        "successful deployment",
        "committing",
        '"wrap up"',
        '"done"',
        "never blocked or partially deployed work",
    ):
        assert phrase in text, (path, "missing policy clause", phrase)
    assert "explicit" in text and "direct" in text, path
    assert "actually invokes `/wrap`" in text or "actual invocation of this `/wrap` command" in text, path
    assert "mentioning" in text and "quoting" in text, path
    assert "do not authorize closure" in text or "do NOT authorize closure" in text or "does not authorize closure" in text, path
    assert "scope" in text, path
    assert "expanded user prompt" in text, (path, "expanded invocation is authorized")
    assert "MUST close completed, in-scope" in text, (path, "authorized closure is required")
    assert "misclassify the expanded invocation" in text, path
    assert "prompt file through tools is not an invocation" in text, path
    for phrase in FORBIDDEN:
        assert phrase not in text, (path, "unconditional closure", phrase)
    print(f"PASS explicit closure authorization: {path}")
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    agents = check_policy(ROOT / "AGENTS.md")
    assert "update issue comments" in agents
    assert "`done` column" in agents
    for source, _ in PROMPTS.values():
        text = check_policy(ROOT / source)
        assert "On actual invocation" in text
        assert "completed Fizzy cards within this session's scope" in text
        assert "wrapping-up" in text and "Commit message:" in text

    if args.installed:
        home = Path.home()
        fizzy = check_policy(home / ".agents/skills/fizzy/SKILL.md")
        assert "9. **Card closure requires John's explicit authorization**" in fizzy
        assert fizzy.count("# Only with John's explicit closure authorization (Invariant #9)") == 2
        # Preserve CLI reference/examples while adding authorization gates.
        for command in ("fizzy card close CARD_NUMBER", "fizzy card close 42", "fizzy card close 579"):
            assert command in fizzy
        assert "card column --column done" in fizzy
        wrap = check_policy(home / ".agents/skills/wrapping-up/SKILL.md")
        assert '"Closure authorized for this card?" -> "Leave card open"' in wrap
        assert '"Closure authorized for this card?" -> "Close authorized card"' in wrap
        assert "Reading this skill or a prompt file through tools is not an invocation" in wrap
        for agent, (source, target) in PROMPTS.items():
            installed = home / target
            check_policy(installed)
            assert installed.read_bytes() == (ROOT / source).read_bytes(), (agent, "stale installed prompt")
            assert installed.is_symlink() and str(installed.resolve()).startswith("/nix/store/"), installed
            print(f"PASS managed {agent} prompt matches source")
        claude_skills = home / ".config/claude-personal/skills"
        assert claude_skills.resolve() == home / ".agents/skills", claude_skills
        print("PASS personal Claude shares the authorized user skill rules")


if __name__ == "__main__":
    main()
