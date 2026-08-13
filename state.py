from __future__ import annotations

import json
from pathlib import Path


class BotState:
    def __init__(self, path: str = "state.json"):
        self.path = Path(path)
        self.data = {
            "vigor_usado_hoje_bot": 0,
            "ataques_enviados": 0,
            "falhas_validacao": 0,
        }
        self.load()

    def load(self) -> None:
        if self.path.exists():
            self.data.update(json.loads(self.path.read_text(encoding="utf-8")))

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    @property
    def vigor_usado(self) -> int:
        return int(self.data.get("vigor_usado_hoje_bot", 0))

    def add_vigor(self, amount: int) -> None:
        self.data["vigor_usado_hoje_bot"] = self.vigor_usado + int(amount)
        self.save()

    def add_attack(self) -> None:
        self.data["ataques_enviados"] = int(self.data.get("ataques_enviados", 0)) + 1
        self.save()

    def add_validation_fail(self) -> None:
        self.data["falhas_validacao"] = int(self.data.get("falhas_validacao", 0)) + 1
        self.save()
