from typing import Dict, List
from uuid import uuid4

class ServerAgent:
    def __init__(self, agent_name="") -> None:
        self.action_space = "code_block"
        self.agent_name = agent_name

    def predict(self, instruction: str, obs: Dict) -> List:
        return (None, ['DONE'], {}, {})

    def reset(self):
        pass