import unittest

from oraicle.autoagent import autoagent
from oraicle.registry import AgentRegistry

class DummyAgent:
    def __init__(self, name):
        self.name = name


class TestAutoAgent(unittest.TestCase):
    def setUp(self):
        AgentRegistry._root_agents.clear()

    def test_autoagent_registers_agent(self):
        agent = DummyAgent("auto_test")
        returned = autoagent(agent)

        self.assertEqual(returned, agent)
        reg = AgentRegistry.get_root("auto_test")
        self.assertIsNotNone(reg)
        self.assertEqual(reg.agent, agent)


if __name__ == "__main__":
    unittest.main()
