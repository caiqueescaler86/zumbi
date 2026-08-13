from __future__ import annotations

import time
import pyautogui

from vision import Match


class Controller:
    def __init__(self, config: dict):
        self.config = config
        pyautogui.PAUSE = float(config.get("tempo_apos_clique_segundos", 0.25))
        pyautogui.FAILSAFE = True

    def click_match(self, match: Match, label: str = "") -> None:
        x, y = match.center
        print(f"CLICK {label or match.name}: x={x} y={y} score={match.score:.3f}")
        if not self.config.get("dry_run", True):
            pyautogui.click(x, y)
        time.sleep(float(self.config.get("tempo_apos_clique_segundos", 0.6)))

    def click_xy(self, x: int, y: int, label: str = "") -> None:
        print(f"CLICK {label}: x={x} y={y}")
        if not self.config.get("dry_run", True):
            pyautogui.click(x, y)
        time.sleep(float(self.config.get("tempo_apos_clique_segundos", 0.6)))

    def press_escape(self) -> None:
        print("PRESS ESC")
        if not self.config.get("dry_run", True):
            pyautogui.press("esc")
        time.sleep(float(self.config.get("tempo_apos_clique_segundos", 0.6)))
