"""
StoryBuilder - Interactive wizard for creating StoryLang programs.
The compiler itself prompts the user to define scenes, choices, conditions, etc.
and assembles the source code on-the-fly.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .display import Display, c, CYAN, YELLOW, DIM, BOLD


IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class SceneDraft:
    name: str
    description_mode: str = "none"  # none | manual | ai
    description_text: str = ""
    statements: List[str] = field(default_factory=list)


class StoryBuilder:
    """
    Guides the user through building a StoryLang program interactively.
    Generates and returns valid StoryLang source code as a string.
    """

    def __init__(self, display: Display):
        self.display = display
        self.scenes: List[SceneDraft] = []

    def _input(self, prompt: str, allow_empty: bool = False) -> str:
        while True:
            try:
                val = input(self.display.repl_prompt() if not prompt else
                            c(CYAN, f"\n  {prompt} ❯ ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return ""
            if val or allow_empty:
                return val
            self.display.print_warning("Input cannot be empty. Try again.")

    def _choose(self, prompt: str, options: List[str]) -> str:
        """Present numbered menu, return chosen value."""
        print()
        self.display.print_choices_header(prompt)
        for i, opt in enumerate(options, 1):
            self.display.print_choice(i, opt)
        while True:
            raw = self._input("Enter number", allow_empty=True)
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return options[int(raw) - 1]
            self.display.print_warning(f"Enter 1–{len(options)}.")

    def _choose_index(self, prompt: str, options: List[str]) -> Optional[int]:
        """Present numbered options and return selected 0-based index, or None to cancel."""
        print()
        self.display.print_choices_header(prompt)
        for i, opt in enumerate(options, 1):
            self.display.print_choice(i, opt)
        print(c(DIM, "    [0] Cancel"))
        while True:
            raw = self._input("Enter number", allow_empty=True)
            if raw == "0" or raw == "":
                return None
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return int(raw) - 1
            self.display.print_warning(f"Enter 0–{len(options)}.")

    def _yes_no(self, prompt: str) -> bool:
        while True:
            val = self._input(f"{prompt} [y/n]", allow_empty=True).lower()
            if val in ('y', 'yes'):
                return True
            if val in ('n', 'no', ''):
                return False
            self.display.print_warning("Please enter y or n.")

    def _emit(self, line: str = ""):
        # Compatibility helper kept for older call patterns.
        # New builder flow does not emit lines incrementally.
        return

    def _validate_identifier(self, value: str, kind: str = "name") -> Optional[str]:
        clean = value.strip().replace(" ", "_")
        if not clean:
            self.display.print_warning(f"{kind.capitalize()} cannot be empty.")
            return None
        if not IDENT_RE.match(clean):
            self.display.print_warning(
                f"Invalid {kind}: '{value}'. Use letters, numbers, underscore; do not start with a number."
            )
            return None
        return clean

    def _scene_name_exists(self, name: str, ignore_index: Optional[int] = None) -> bool:
        for i, scene in enumerate(self.scenes):
            if ignore_index is not None and i == ignore_index:
                continue
            if scene.name == name:
                return True
        return False

    def _scene_snapshot(self, scene: SceneDraft) -> Tuple[str, str, List[str]]:
        return (scene.description_mode, scene.description_text, list(scene.statements))

    def _restore_scene_snapshot(self, scene: SceneDraft, snap: Tuple[str, str, List[str]]):
        mode, text, statements = snap
        scene.description_mode = mode
        scene.description_text = text
        scene.statements = list(statements)

    def _render_source(self) -> str:
        lines: List[str] = []
        for scene in self.scenes:
            lines.append(f"scene {scene.name} {{")
            if scene.description_mode == "manual" and scene.description_text:
                escaped = scene.description_text.replace('"', '\\"')
                lines.append(f'  description: "{escaped}"')
            elif scene.description_mode == "ai" and scene.description_text:
                escaped = scene.description_text.replace('"', '\\"')
                lines.append(f'  AI_generate_scene "{escaped}"')
            for stmt in scene.statements:
                lines.append(f"  {stmt}")
            lines.append("}")
            lines.append("")
        return "\n".join(lines).rstrip()

    # ------------------------------------------------------------------ #
    #  Public entry point
    # ------------------------------------------------------------------ #

    def build(self) -> str:
        """
        Run the interactive story builder wizard.
        Returns generated StoryLang source code.
        """
        self.scenes.clear()

        print()
        self.display.print_divider("═")
        print(c(BOLD, "  ✦ STORY BUILDER — Build your world step by step"))
        self.display.print_divider("═")
        print()
        print(c(DIM, "  Build tip: you can revisit scenes, undo edits, reorder scenes, and preview output anytime."))
        print(c(DIM, "  Target scenes can be created later; semantic checks will guide missing links."))

        finished = self._scene_hub()
        if not finished:
            self.display.print_info("Builder cancelled.")
            return ""

        if not self.scenes:
            self.display.print_warning("No scenes created.")
            return ""

        names = ", ".join(scene.name for scene in self.scenes)
        self.display.print_success(f"Story built with {len(self.scenes)} scene(s): {names}")
        return self._render_source()

    # ------------------------------------------------------------------ #
    #  Scene builder
    # ------------------------------------------------------------------ #

    def _scene_hub(self) -> bool:
        while True:
            print()
            self.display.print_divider("─")
            print(c(YELLOW + BOLD, "  Scene Manager"))
            if self.scenes:
                for i, scene in enumerate(self.scenes, 1):
                    desc = "none"
                    if scene.description_mode == "manual":
                        desc = "manual"
                    elif scene.description_mode == "ai":
                        desc = "ai"
                    print(c(DIM, f"    {i}. {scene.name}  (description: {desc}, statements: {len(scene.statements)})"))
            else:
                print(c(DIM, "    No scenes yet."))

            action = self._choose(
                "Choose an action:",
                [
                    "Add scene",
                    "Edit scene",
                    "Rename scene",
                    "Delete scene",
                    "Reorder scenes",
                    "Preview generated source",
                    "Finish build",
                    "Cancel build",
                ],
            )

            if action == "Add scene":
                self._add_scene()
            elif action == "Edit scene":
                self._pick_and_edit_scene()
            elif action == "Rename scene":
                self._rename_scene()
            elif action == "Delete scene":
                self._delete_scene()
            elif action == "Reorder scenes":
                self._reorder_scenes()
            elif action == "Preview generated source":
                source = self._render_source()
                if source:
                    self.display.print_code(source)
                else:
                    self.display.print_warning("No source yet.")
            elif action == "Finish build":
                if not self.scenes:
                    self.display.print_warning("Create at least one scene first.")
                    continue
                return True
            elif action == "Cancel build":
                return False

    def _add_scene(self):
        while True:
            raw = self._input("New scene name (identifier; spaces auto-convert to underscores)")
            name = self._validate_identifier(raw, "scene name")
            if not name:
                continue
            if self._scene_name_exists(name):
                self.display.print_warning(f"Scene '{name}' already exists.")
                continue
            scene = SceneDraft(name=name)
            self.scenes.append(scene)
            self._edit_scene(len(self.scenes) - 1)
            return

    def _pick_and_edit_scene(self):
        if not self.scenes:
            self.display.print_warning("No scenes available. Add one first.")
            return
        options = [scene.name for scene in self.scenes]
        idx = self._choose_index("Select a scene to edit", options)
        if idx is None:
            return
        self._edit_scene(idx)

    def _rename_scene(self):
        if not self.scenes:
            self.display.print_warning("No scenes available.")
            return
        idx = self._choose_index("Select a scene to rename", [scene.name for scene in self.scenes])
        if idx is None:
            return
        current = self.scenes[idx].name
        while True:
            raw = self._input(f"New name for '{current}'")
            new_name = self._validate_identifier(raw, "scene name")
            if not new_name:
                continue
            if self._scene_name_exists(new_name, ignore_index=idx):
                self.display.print_warning(f"Scene '{new_name}' already exists.")
                continue
            self.scenes[idx].name = new_name
            self.display.print_success(f"Scene renamed: {current} -> {new_name}")
            return

    def _delete_scene(self):
        if not self.scenes:
            self.display.print_warning("No scenes available.")
            return
        idx = self._choose_index("Select a scene to delete", [scene.name for scene in self.scenes])
        if idx is None:
            return
        name = self.scenes[idx].name
        if self._yes_no(f"Delete scene '{name}'?"):
            self.scenes.pop(idx)
            self.display.print_success(f"Scene '{name}' deleted.")

    def _reorder_scenes(self):
        if len(self.scenes) < 2:
            self.display.print_warning("Need at least two scenes to reorder.")
            return
        from_idx = self._choose_index("Move which scene?", [scene.name for scene in self.scenes])
        if from_idx is None:
            return
        to_raw = self._input(f"New position for '{self.scenes[from_idx].name}' (1-{len(self.scenes)})")
        if not to_raw.isdigit():
            self.display.print_warning("Enter a number.")
            return
        to_idx = int(to_raw) - 1
        if not (0 <= to_idx < len(self.scenes)):
            self.display.print_warning(f"Enter a value from 1 to {len(self.scenes)}.")
            return
        scene = self.scenes.pop(from_idx)
        self.scenes.insert(to_idx, scene)
        self.display.print_success(f"Moved '{scene.name}' to position {to_idx + 1}.")

    def _edit_scene(self, scene_idx: int):
        if not (0 <= scene_idx < len(self.scenes)):
            return

        scene = self.scenes[scene_idx]
        history: List[Tuple[str, str, List[str]]] = [self._scene_snapshot(scene)]

        while True:
            print()
            self.display.print_divider("─")
            print(c(YELLOW + BOLD, f"  Editing scene: {scene.name}"))
            if scene.description_mode == "manual":
                print(c(DIM, f"    Description: manual ({len(scene.description_text)} chars)"))
            elif scene.description_mode == "ai":
                print(c(DIM, f"    Description: AI prompt ({len(scene.description_text)} chars)"))
            else:
                print(c(DIM, "    Description: none"))

            if scene.statements:
                for i, stmt in enumerate(scene.statements, 1):
                    print(c(DIM, f"    {i}. {stmt}"))
            else:
                print(c(DIM, "    No statements yet."))

            action = self._choose(
                "Scene actions:",
                [
                    "Set manual description",
                    "Set AI-generated description prompt",
                    "Clear description",
                    "Add statement",
                    "Edit statement",
                    "Remove statement",
                    "Move statement",
                    "Undo last change",
                    "Jump to another scene",
                    "Back to scene manager",
                ],
            )

            if action == "Set manual description":
                text = self._input("Scene description text")
                if text:
                    scene.description_mode = "manual"
                    scene.description_text = text
                    history.append(self._scene_snapshot(scene))
                    self.display.print_success("Description updated.")

            elif action == "Set AI-generated description prompt":
                prompt = self._input("Prompt for AI scene generation")
                if prompt:
                    scene.description_mode = "ai"
                    scene.description_text = prompt
                    history.append(self._scene_snapshot(scene))
                    self.display.print_success("AI scene prompt updated.")

            elif action == "Clear description":
                if scene.description_mode == "none":
                    self.display.print_warning("Description is already empty.")
                else:
                    scene.description_mode = "none"
                    scene.description_text = ""
                    history.append(self._scene_snapshot(scene))
                    self.display.print_success("Description cleared.")

            elif action == "Add statement":
                stmt = self._build_statement()
                if stmt:
                    scene.statements.append(stmt)
                    history.append(self._scene_snapshot(scene))
                    self.display.print_success("Statement added.")

            elif action == "Edit statement":
                if not scene.statements:
                    self.display.print_warning("No statements to edit.")
                else:
                    idx = self._choose_index("Select a statement to replace", scene.statements)
                    if idx is not None:
                        stmt = self._build_statement()
                        if stmt:
                            scene.statements[idx] = stmt
                            history.append(self._scene_snapshot(scene))
                            self.display.print_success("Statement updated.")

            elif action == "Remove statement":
                if not scene.statements:
                    self.display.print_warning("No statements to remove.")
                else:
                    idx = self._choose_index("Select a statement to remove", scene.statements)
                    if idx is not None:
                        removed = scene.statements.pop(idx)
                        history.append(self._scene_snapshot(scene))
                        self.display.print_success(f"Removed: {removed}")

            elif action == "Move statement":
                if len(scene.statements) < 2:
                    self.display.print_warning("Need at least two statements to reorder.")
                else:
                    from_idx = self._choose_index("Move which statement?", scene.statements)
                    if from_idx is not None:
                        to_raw = self._input(f"New position (1-{len(scene.statements)})")
                        if not to_raw.isdigit():
                            self.display.print_warning("Enter a number.")
                        else:
                            to_idx = int(to_raw) - 1
                            if not (0 <= to_idx < len(scene.statements)):
                                self.display.print_warning(f"Enter a value from 1 to {len(scene.statements)}.")
                            else:
                                stmt = scene.statements.pop(from_idx)
                                scene.statements.insert(to_idx, stmt)
                                history.append(self._scene_snapshot(scene))
                                self.display.print_success("Statement moved.")

            elif action == "Undo last change":
                if len(history) <= 1:
                    self.display.print_warning("Nothing to undo in this edit session.")
                else:
                    history.pop()
                    self._restore_scene_snapshot(scene, history[-1])
                    self.display.print_success("Undid last change.")

            elif action == "Jump to another scene":
                if not self.scenes:
                    self.display.print_warning("No scenes available.")
                    continue
                idx = self._choose_index("Select scene", [s.name for s in self.scenes])
                if idx is not None and idx != scene_idx:
                    scene_idx = idx
                    scene = self.scenes[scene_idx]
                    history = [self._scene_snapshot(scene)]

            elif action == "Back to scene manager":
                return

    def _build_statement(self) -> Optional[str]:
        action = self._choose(
            "Statement type:",
            [
                "Player choice",
                "If condition",
                "Set variable / inventory",
                "Unset variable",
                "Remove item from inventory",
                "AI-generate choices",
            ],
        )
        if action == "Player choice":
            return self._build_choice_statement()
        if action == "If condition":
            return self._build_if_statement()
        if action == "Set variable / inventory":
            return self._build_set_statement()
        if action == "Unset variable":
            return self._build_unset_statement()
        if action == "Remove item from inventory":
            return self._build_remove_item_statement()
        if action == "AI-generate choices":
            return self._build_ai_options_statement()
        return None

    def _build_choice_statement(self) -> Optional[str]:
        label = self._input('Choice label (what the player reads, e.g. "Go north")')
        if not label:
            return None

        target_raw = self._input("Target scene name")
        target = self._validate_identifier(target_raw, "target scene")
        if not target:
            return None

        escaped = label.replace('"', '\\"')
        return f'choice "{escaped}" -> {target}'

    def _build_if_statement(self) -> Optional[str]:
        cond_type = self._choose(
            "Condition type:",
            [
                "Flag exists (if has has_key)",
                "Inventory item exists (if has item \"torch\")",
                "Comparison (if score > 3 / name == \"hero\")",
            ],
        )

        condition = ""
        if cond_type == "Flag exists (if has has_key)":
            var_raw = self._input("Flag variable name")
            var = self._validate_identifier(var_raw, "variable")
            if not var:
                return None
            condition = f"has {var}"

        elif cond_type == 'Inventory item exists (if has item "torch")':
            item = self._input("Item name")
            if not item:
                return None
            condition = f'has item "{item.replace('"', '\\"')}"'

        elif cond_type == 'Comparison (if score > 3 / name == "hero")':
            var_raw = self._input("Variable name")
            var = self._validate_identifier(var_raw, "variable")
            if not var:
                return None
            op = self._choose("Operator", [">", "<", "=="])
            raw_val = self._input("Value (number, or text for ==)")
            if not raw_val:
                return None

            if op in (">", "<"):
                try:
                    num = int(raw_val)
                except ValueError:
                    self.display.print_warning("For > or <, value must be an integer.")
                    return None
                condition = f"{var} {op} {num}"
            else:
                try:
                    num = int(raw_val)
                    condition = f"{var} == {num}"
                except ValueError:
                    condition = f'{var} == "{raw_val.replace('"', '\\"')}"'

        then_raw = self._input("If condition is true -> go to scene")
        then_target = self._validate_identifier(then_raw, "target scene")
        if not then_target:
            return None

        line = f"if {condition} -> {then_target}"

        if self._yes_no("Add else branch?"):
            else_raw = self._input("Else -> go to scene")
            else_target = self._validate_identifier(else_raw, "target scene")
            if not else_target:
                return None
            return f"{line}\n  else -> {else_target}"

        return line

    def _build_set_statement(self) -> Optional[str]:
        mode = self._choose(
            "Set action:",
            [
                "Set flag (set has_key)",
                "Set text (set title = \"Hero\")",
                "Set number (set score = 5)",
                "Increment number (set score += 1)",
                "Decrement number (set score -= 1)",
                "Add inventory item (set item \"torch\")",
            ],
        )

        if mode == "Add inventory item (set item \"torch\")":
            item = self._input("Item name")
            if not item:
                return None
            escaped = item.replace('"', '\\"')
            return f'set item "{escaped}"'

        var_raw = self._input("Variable name")
        var = self._validate_identifier(var_raw, "variable")
        if not var:
            return None

        if mode == "Set flag (set has_key)":
            return f"set {var}"

        if mode == 'Set text (set title = "Hero")':
            text = self._input("Text value")
            if not text:
                return None
            return f'set {var} = "{text.replace('"', '\\"')}"'

        if mode == "Set number (set score = 5)":
            raw = self._input("Integer value")
            try:
                num = int(raw)
            except ValueError:
                self.display.print_warning("Value must be an integer.")
                return None
            return f"set {var} = {num}"

        if mode == "Increment number (set score += 1)":
            raw = self._input("Increment amount (integer)")
            try:
                num = int(raw)
            except ValueError:
                self.display.print_warning("Value must be an integer.")
                return None
            return f"set {var} += {num}"

        if mode == "Decrement number (set score -= 1)":
            raw = self._input("Decrement amount (integer)")
            try:
                num = int(raw)
            except ValueError:
                self.display.print_warning("Value must be an integer.")
                return None
            return f"set {var} -= {num}"

        return None

    def _build_unset_statement(self) -> Optional[str]:
        raw = self._input("Variable name to unset")
        var = self._validate_identifier(raw, "variable")
        if not var:
            return None
        return f"unset {var}"

    def _build_remove_item_statement(self) -> Optional[str]:
        item = self._input("Inventory item name to remove")
        if not item:
            return None
        escaped = item.replace('"', '\\"')
        return f'remove item "{escaped}"'

    def _build_ai_options_statement(self) -> Optional[str]:
        prompt = self._input("Describe the scenario for AI to generate choices from")
        if not prompt:
            return None
        escaped = prompt.replace('"', '\\"')
        return f'AI_generate_options "{escaped}"'