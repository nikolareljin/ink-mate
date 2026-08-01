import pytest

from inkmate_gateway.services import CodingAgentAdapter


def test_coding_agents_disabled():
    with pytest.raises(PermissionError): CodingAgentAdapter(False, ("/tmp/work",)).validate("/tmp/work")


def test_workspace_cannot_escape():
    adapter = CodingAgentAdapter(True, ("/tmp/work",))
    assert str(adapter.validate("/tmp/work/repo")).startswith("/tmp/work")
    with pytest.raises(PermissionError): adapter.validate("/tmp/work-other")
