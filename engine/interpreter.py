"""
Interpreter / Execution Engine for StoryLang
Walks the AST and runs the interactive story in the terminal.
"""

import time
from typing import Dict, Optional, List, Set

from .ast_nodes import (
    ProgramNode, SceneNode, DescriptionNode, ChoiceNode,
    IfNode, SetNode, AIGenerateSceneNode, AIGenerateOptionsNode
)
from .ai_service import AIService
from .display import Display


class RuntimeError_(Exception):
    def __init__(self, msg: str):
        super().__init__(f"[Runtime] {msg}")


class Interpreter:
    def __init__(self, program: ProgramNode, ai: AIService, display: Display):
        self.program = program
        self.ai = ai
        self.display = display

        # Build scene lookup
        self.scenes: Dict[str, SceneNode] = {s.name: s for s in program.scenes}
        self.flags: Set[str] = set()
        self.inventory: Set[str] = set()
        self.numbers: Dict[str, int] = {}
        self.text_vars: Dict[str, str] = {}
        self.history: List[str] = []   # scene names visited
        self.story_log: List[str] = [] # text log for AI context

    def reset(self):
        self.flags.clear()
        self.inventory.clear()
        self.numbers.clear()
        self.text_vars.clear()
        self.history.clear()
        self.story_log.clear()

    def get_context(self) -> str:
        return " ".join(self.story_log[-6:])  # last ~6 events for context

    def run(self):
        if not self.scenes:
            self.display.error("No scenes defined. Cannot run.")
            return

        start_scene = self.program.scenes[0].name
        self.display.print_divider()
        self.display.print_info(f"Story begins at scene: '{start_scene}'")
        self.display.print_divider()
        time.sleep(0.4)

        self._execute_scene(start_scene)

    def _execute_scene(self, scene_name: str):
        if scene_name not in self.scenes:
            self.display.error(f"Scene '{scene_name}' not found. Story ends here.")
            return

        scene = self.scenes[scene_name]
        self.history.append(scene_name)
        self.story_log.append(f"[Scene: {scene_name}]")

        self.display.print_scene_header(scene_name)
        time.sleep(0.2)

        # Collect choices generated during statement execution
        choices: List[ChoiceNode] = []
        next_scene: Optional[str] = None   # for if-else direct jumps

        for stmt in scene.statements:
            result = self._execute_statement(stmt, choices)
            if result is not None:
                # An if-node has determined next scene directly
                next_scene = result
                break

        # Determine navigation
        if next_scene is not None:
            self._navigate(next_scene)
            return

        if choices:
            chosen = self._present_choices(choices)
            if chosen:
                self._navigate(chosen)
        else:
            # Terminal scene — generate ending or just stop
            self.display.print_divider()
            self.display.print_bold("\n[ THE END ]\n")
            if self.ai.check_available():
                ending = self.ai.generate_story_ending(self.get_context())
                self.display.slow_print(ending)
            self.display.print_divider()

    def _execute_statement(self, stmt, choices: List[ChoiceNode]) -> Optional[str]:
        """Execute one statement. Returns a scene name if we should jump immediately."""

        if isinstance(stmt, DescriptionNode):
            self.display.slow_print(stmt.text)
            self.story_log.append(stmt.text)

        elif isinstance(stmt, ChoiceNode):
            choices.append(stmt)

        elif isinstance(stmt, SetNode):
            self._apply_set(stmt)

        elif isinstance(stmt, IfNode):
            cond_met = self._eval_condition(stmt.condition)
            cond_txt = self._condition_to_text(stmt.condition)

            if cond_met:
                if stmt.then_target:
                    target = stmt.then_target
                    self.display.print_dim(f"  [Condition '{cond_txt}': ✓ → '{target}']")
                    return target
                if stmt.then_block:
                    self.display.print_dim(f"  [Condition '{cond_txt}': ✓ → inline block]")
                    return self._execute_block(stmt.then_block, choices)
            else:
                if stmt.else_target:
                    target = stmt.else_target
                    self.display.print_dim(f"  [Condition '{cond_txt}': ✗ → '{target}']")
                    return target
                if stmt.else_block:
                    self.display.print_dim(f"  [Condition '{cond_txt}': ✗ → else block]")
                    return self._execute_block(stmt.else_block, choices)

            # condition not met and no else-target/block: fall through
            self.display.print_dim(f"  [Condition '{cond_txt}' not met, continuing...]")

        elif isinstance(stmt, AIGenerateSceneNode):
            self.display.print_ai_indicator("Generating scene...")
            desc = self.ai.generate_scene_description(stmt.prompt, self.get_context())
            self.display.slow_print(desc)
            self.story_log.append(desc)

        elif isinstance(stmt, AIGenerateOptionsNode):
            self.display.print_ai_indicator("Generating choices...")
            ai_choices = self.ai.generate_options(stmt.prompt, self.get_context())
            for c in ai_choices:
                label = c.get("label", "Continue")
                target = c.get("target", "end")
                # Dynamically create the target scene if it doesn't exist
                if target not in self.scenes:
                    self._create_stub_scene(target, stmt.prompt)
                choices.append(ChoiceNode(label=label, target=target))

        return None

    def _execute_block(self, statements, choices: List[ChoiceNode]) -> Optional[str]:
        for sub_stmt in statements:
            result = self._execute_statement(sub_stmt, choices)
            if result is not None:
                return result
        return None

    def _apply_set(self, stmt: SetNode):
        if stmt.action == "set_flag":
            self.flags.add(stmt.variable)
            self.display.print_dim(f"  [Flag set: {stmt.variable}]")
            self.story_log.append(f"Flag '{stmt.variable}' was set.")
            return

        if stmt.action == "add_item":
            item = str(stmt.value)
            self.inventory.add(item)
            self.display.print_dim(f"  [Inventory + {item}]")
            self.story_log.append(f"Item gained: '{item}'.")
            return

        if stmt.action == "remove_item":
            item = str(stmt.value)
            existed = item in self.inventory
            self.inventory.discard(item)
            status = "removed" if existed else "not present"
            self.display.print_dim(f"  [Inventory - {item} ({status})]")
            self.story_log.append(f"Item removed: '{item}' ({status}).")
            return

        if stmt.action == "assign_number":
            if stmt.value is None:
                raise RuntimeError_(f"Missing value for numeric assignment '{stmt.variable}'")
            self.numbers[stmt.variable] = int(stmt.value)
            self.display.print_dim(f"  [Number set: {stmt.variable} = {self.numbers[stmt.variable]}]")
            self.story_log.append(f"Number '{stmt.variable}' = {self.numbers[stmt.variable]}.")
            return

        if stmt.action == "inc_number":
            delta = int(stmt.delta)
            self.numbers[stmt.variable] = self.numbers.get(stmt.variable, 0) + delta
            self.display.print_dim(f"  [Number update: {stmt.variable} += {delta} -> {self.numbers[stmt.variable]}]")
            self.story_log.append(f"Number '{stmt.variable}' increased to {self.numbers[stmt.variable]}.")
            return

        if stmt.action == "dec_number":
            delta = int(stmt.delta)
            self.numbers[stmt.variable] = self.numbers.get(stmt.variable, 0) - delta
            self.display.print_dim(f"  [Number update: {stmt.variable} -= {delta} -> {self.numbers[stmt.variable]}]")
            self.story_log.append(f"Number '{stmt.variable}' decreased to {self.numbers[stmt.variable]}.")
            return

        if stmt.action == "set_text":
            text_value = str(stmt.value)
            self.text_vars[stmt.variable] = text_value
            self.display.print_dim(f"  [Text set: {stmt.variable} = {text_value!r}]")
            self.story_log.append(f"Text variable '{stmt.variable}' changed.")
            return

        if stmt.action == "unset_variable":
            var_name = stmt.variable
            removed_any = False
            if var_name in self.flags:
                self.flags.discard(var_name)
                removed_any = True
            if var_name in self.numbers:
                del self.numbers[var_name]
                removed_any = True
            if var_name in self.text_vars:
                del self.text_vars[var_name]
                removed_any = True
            status = "cleared" if removed_any else "not set"
            self.display.print_dim(f"  [Unset {var_name}: {status}]")
            self.story_log.append(f"Variable '{var_name}' unset ({status}).")
            return

        raise RuntimeError_(f"Unknown set action '{stmt.action}'")

    def _eval_condition(self, condition) -> bool:
        if condition.kind == "has_flag":
            return (condition.variable or "") in self.flags

        if condition.kind == "has_item":
            return str(condition.value) in self.inventory

        if condition.kind == "compare":
            var_name = condition.variable or ""
            if condition.operator in (">", "<"):
                left = self.numbers.get(var_name, 0)
                right = int(condition.value)
                if condition.operator == ">":
                    return left > right
                return left < right

            if condition.operator == "==":
                if isinstance(condition.value, int):
                    return self.numbers.get(var_name, 0) == condition.value
                return self.text_vars.get(var_name, "") == str(condition.value)

            raise RuntimeError_(f"Unsupported comparison operator '{condition.operator}'")

        raise RuntimeError_(f"Unknown condition kind '{condition.kind}'")

    def _condition_to_text(self, condition) -> str:
        if condition.kind == "has_flag":
            return f"has {condition.variable}"
        if condition.kind == "has_item":
            return f"has item {condition.value!r}"
        if condition.kind == "compare":
            if isinstance(condition.value, str):
                return f"{condition.variable} {condition.operator} {condition.value!r}"
            return f"{condition.variable} {condition.operator} {condition.value}"
        return "<unknown>"

    def _create_stub_scene(self, name: str, context_hint: str):
        """Dynamically create a stub scene for AI-generated targets."""
        stub = SceneNode(name=name)
        stub.statements.append(AIGenerateSceneNode(prompt=f"{context_hint} - {name.replace('_', ' ')}"))
        self.scenes[name] = stub
        self.program.scenes.append(stub)

    def _present_choices(self, choices: List[ChoiceNode]) -> Optional[str]:
        """Display choices and get user selection. Returns target scene name."""
        print()
        self.display.print_choices_header("What do you do?")
        for i, choice in enumerate(choices, 1):
            self.display.print_choice(i, choice.label)

        while True:
            try:
                raw = input(self.display.prompt_str()).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                self.display.print_info("Story interrupted.")
                return None

            if raw.lower() in ('q', 'quit', 'exit'):
                self.display.print_info("You close the book.")
                return None

            if raw.isdigit():
                idx = int(raw)
                if 1 <= idx <= len(choices):
                    chosen = choices[idx - 1]
                    self.display.print_dim(f'  → You chose: "{chosen.label}"')
                    self.story_log.append(f'Player chose: "{chosen.label}"')
                    print()
                    return chosen.target

            self.display.print_warning(f"Please enter a number between 1 and {len(choices)}.")

    def _navigate(self, scene_name: str):
        if scene_name in self.history and self.history.count(scene_name) >= 3:
            self.display.print_warning(
                f"Scene '{scene_name}' visited too many times. Breaking loop."
            )
            return
        self._execute_scene(scene_name)