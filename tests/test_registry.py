import unittest

from oraicle.registry import AgentRegistry

class DummyAgent:
    def __init__(self, name):
        self.name = name


class TestRegistry(unittest.TestCase):
    def setUp(self):
        AgentRegistry._root_agents.clear()

    def test_register_and_get_root(self):
        agent = DummyAgent("agent_test")
        AgentRegistry.register_root(
            agent, file_path="tests/test_registry.py", module_name="tests.test_registry"
        )

        reg = AgentRegistry.get_root("agent_test")
        self.assertIsNotNone(reg)
        self.assertEqual(reg.agent, agent)

    def test_all_roots(self):
        a1 = DummyAgent("a1")
        a2 = DummyAgent("a2")

        AgentRegistry.register_root(
            a1, file_path="tests/test_registry.py", module_name="tests.test_registry"
        )
        AgentRegistry.register_root(
            a2, file_path="tests/test_registry.py", module_name="tests.test_registry"
        )

        roots = AgentRegistry.all_roots()
        self.assertEqual(len(roots), 2)
        self.assertIn("a1", roots)
        self.assertIn("a2", roots)


if __name__ == "__main__":
    unittest.main()
