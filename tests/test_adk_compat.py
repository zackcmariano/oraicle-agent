import unittest

from oraicle.registry import AgentRegistry
from oraicle.adk.loader_patch import resolve_root_agent
from oraicle.exceptions import NoRootAgentRegistered

class DummyAgent:
    def __init__(self, name):
        self.name = name


class TestAdkCompat(unittest.TestCase):
    def setUp(self):
        AgentRegistry._root_agents.clear()

    def test_resolve_root_agent_success(self):
        agent = DummyAgent("root_ok")
        AgentRegistry.register_root(
            agent,
            file_path="tests/test_adk_compat.py",
            module_name="tests.test_adk_compat",
        )

        root = resolve_root_agent()
        self.assertEqual(root, agent)


    def test_resolve_root_agent_fail(self):
        with self.assertRaises(NoRootAgentRegistered):
            resolve_root_agent()

if __name__ == "__main__":
    unittest.main()
