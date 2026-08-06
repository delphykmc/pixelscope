from scripts.check_docs import ROOT, find_problems


def test_repository_documentation_contract() -> None:
    assert find_problems(ROOT) == []
