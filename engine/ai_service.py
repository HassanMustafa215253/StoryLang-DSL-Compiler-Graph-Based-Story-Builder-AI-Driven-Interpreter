"""
AI Integration for StoryLang
Calls Anthropic Claude API to generate dynamic story content.
"""

import json
import urllib.request
import urllib.error
from typing import List, Dict, Optional


class AIService:
    """Wraps the Anthropic API for story content generation."""

    MODEL = "claude-sonnet-4-20250514"
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self):
        self._available: Optional[bool] = None

    def _call(self, system: str, user: str, max_tokens: int = 400) -> Optional[str]:
        payload = {
            "model": self.MODEL,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.API_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body["content"][0]["text"].strip()
        except Exception:
            return None

    def check_available(self) -> bool:
        if self._available is None:
            result = self._call("You are a test.", "Reply with the single word: OK", 10)
            self._available = result is not None and "OK" in result
        return self._available

    # ------------------------------------------------------------------ #
    #  Story generation helpers
    # ------------------------------------------------------------------ #

    def generate_scene_description(self, prompt: str, context: str = "") -> str:
        system = (
            "You are a creative fiction writer for an interactive text adventure. "
            "Write immersive, second-person scene descriptions (2-4 sentences). "
            "Be vivid but concise. Do NOT include choices or options."
        )
        user = f"Setting: {prompt}\nContext so far: {context or 'Story just started.'}\n\nDescribe the scene:"
        result = self._call(system, user, 200)
        return result or f"[AI] You find yourself in: {prompt}. The world unfolds before you."

    def generate_options(self, prompt: str, context: str = "") -> List[Dict[str, str]]:
        """Returns a list of {label, target} dicts."""
        system = (
            "You are a game designer creating choices for an interactive story. "
            "Given a scenario, return EXACTLY a JSON array with 2-4 choice objects. "
            "Each object has: 'label' (the choice text shown to player, max 8 words) "
            "and 'target' (a short snake_case scene name, no spaces). "
            "Return ONLY the JSON array, no other text."
        )
        user = f"Scenario: {prompt}\nContext: {context or 'Beginning of story.'}\n\nGenerate choices:"
        result = self._call(system, user, 300)
        if result:
            # strip markdown fences if any
            result = result.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            try:
                choices = json.loads(result)
                if isinstance(choices, list):
                    return choices
            except Exception:
                pass
        # Fallback
        return [
            {"label": "Continue forward", "target": "continue"},
            {"label": "Turn back",        "target": "back"},
        ]

    def generate_story_ending(self, context: str) -> str:
        system = (
            "You are a creative fiction writer. "
            "Write a satisfying 3-5 sentence story ending in second person. "
            "Be emotional and conclusive."
        )
        user = f"Story so far: {context}\n\nWrite a fitting ending:"
        result = self._call(system, user, 250)
        return result or "And so your journey comes to an end. The world remembers your choices."