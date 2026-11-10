"""The install workflow covers three operating systems and two Python versions, and the check it runs exists."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = (ROOT / ".github" / "workflows" / "install.yml").read_text(encoding="utf-8")


def test_workflow_matrix_is_three_systems_by_two_pythons():
    os_line = re.search(r"os: \[(.*?)\]", WORKFLOW).group(1)
    assert {x.strip() for x in os_line.split(",")} == {"ubuntu-latest", "macos-latest", "windows-latest"}
    py_line = re.search(r"python: \[(.*?)\]", WORKFLOW).group(1)
    assert {x.strip().strip('"') for x in py_line.split(",")} == {"3.10", "3.13"}


def test_workflow_launches_twice_runs_tests_and_prints_examples():
    assert "tools/ci_launch_check.py" in WORKFLOW
    assert "pytest" in WORKFLOW and "cli.py --all" in WORKFLOW
    assert (ROOT / "tools" / "ci_launch_check.py").exists()
    assert "second launch" in (ROOT / "tools" / "ci_launch_check.py").read_text(encoding="utf-8")
