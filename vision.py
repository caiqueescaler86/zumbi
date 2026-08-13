from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import mss
import numpy as np


@dataclass
class Match:
    name: str
    x: int
    y: int
    w: int
    h: int
    score: float

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


class Vision:
    def __init__(self, config: dict):
        self.config = config
        self.templates: dict[str, np.ndarray] = {}
        self.template_paths = config["templates"]
        self.load_templates()

    def load_templates(self) -> None:
        for name, path in self.template_paths.items():
            p = Path(path)
            if not p.exists():
                continue
            img = cv2.imread(str(p), cv2.IMREAD_COLOR)
            if img is not None:
                self.templates[name] = img

    def screenshot(self) -> np.ndarray:
        region = self.config.get("screen_region")
        with mss.mss() as sct:
            if region:
                mon = {
                    "left": region["left"],
                    "top": region["top"],
                    "width": region["width"],
                    "height": region["height"],
                }
            else:
                mon = sct.monitors[1]
            shot = np.array(sct.grab(mon))
        return cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR)

    def find(self, screen: np.ndarray, name: str, threshold: Optional[float] = None) -> Optional[Match]:
        template = self.templates.get(name)
        if template is None:
            return None
        if threshold is None:
            threshold = float(self.config.get("threshold_template", 0.86))

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val < threshold:
            return None

        h, w = template.shape[:2]
        return Match(name=name, x=max_loc[0], y=max_loc[1], w=w, h=h, score=float(max_val))

    def exists(self, screen: np.ndarray, name: str, threshold: Optional[float] = None) -> bool:
        return self.find(screen, name, threshold) is not None
