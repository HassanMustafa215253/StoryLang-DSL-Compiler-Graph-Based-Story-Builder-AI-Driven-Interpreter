"""
Semantic Analyzer for StoryLang
Validates the AST before execution:
  - Duplicate scene names
  - Undefined scene references in choices / if-else transitions
  - Warns about unreachable scenes
"""

from typing import List, Set
from .ast_nodes import (
    ProgramNode, SceneNode, ChoiceNode, IfNode, SetNode,
    AIGenerateOptionsNode, AIGenerateSceneNode
)


class SemanticError(Exception):
    def __init__(self, msg: str, line: int = 0):
        super().__init__(f"[Semantic] Line {line}: {msg}")
        self.line = line


class SemanticWarning:
    def __init__(self, msg: str, line: int = 0):
        self.msg = msg
        self.line = line

    def __str__(self):
        return f"[Warning] Line {self.line}: {self.msg}"


class SemanticAnalyzer:
    def __init__(self, program: ProgramNode):
        self.program = program
        self.errors: List[SemanticError] = []
        self.warnings: List[SemanticWarning] = []

    def analyze(self) -> bool:
        """Run all checks. Returns True if no errors."""
        defined_scenes: Set[str] = set()
        variable_types = {}
        inventory_used = False

        # Pass 1: collect defined scene names
        for scene in self.program.scenes:
            if scene.name in defined_scenes:
                self.errors.append(
                    SemanticError(f"Duplicate scene name '{scene.name}'", scene.line)
                )
            defined_scenes.add(scene.name)

        # Pass 2: collect variable declarations and inferred types
        for scene in self.program.scenes:
            inventory_used = self._collect_variable_declarations(
                scene.statements,
                variable_types,
                inventory_used,
            )

        # Pass 3: validate all scene references and conditions
        referenced_scenes: Set[str] = set()
        for scene in self.program.scenes:
            self._validate_statements(
                scene.name,
                scene.statements,
                variable_types,
                inventory_used,
                referenced_scenes,
                defined_scenes,
            )

        # Pass 4: warn about unreachable scenes (defined but never referenced, except start)
        if self.program.scenes:
            first = self.program.scenes[0].name
            for scene in self.program.scenes:
                if scene.name != first and scene.name not in referenced_scenes:
                    self.warnings.append(
                        SemanticWarning(
                            f"Scene '{scene.name}' is defined but never reachable "
                            f"from any transition.",
                            scene.line
                        )
                    )

        return len(self.errors) == 0

    def _set_action_to_type(self, action: str):
        if action in ("set_flag",):
            return "flag"
        if action in ("assign_number", "inc_number", "dec_number"):
            return "number"
        if action in ("set_text",):
            return "text"
        return None

    def _collect_variable_declarations(self, statements, variable_types, inventory_used: bool):
        for stmt in statements:
            if isinstance(stmt, SetNode):
                if stmt.action in ("add_item", "remove_item"):
                    inventory_used = True
                elif stmt.action == "unset_variable":
                    continue
                else:
                    inferred = self._set_action_to_type(stmt.action)
                    if inferred:
                        self._register_variable_type(variable_types, stmt.variable, inferred, stmt.line)
            elif isinstance(stmt, IfNode):
                inventory_used = self._collect_variable_declarations(stmt.then_block, variable_types, inventory_used)
                inventory_used = self._collect_variable_declarations(stmt.else_block, variable_types, inventory_used)
        return inventory_used

    def _validate_statements(
        self,
        scene_name: str,
        statements,
        variable_types,
        inventory_used: bool,
        referenced_scenes: Set[str],
        defined_scenes: Set[str],
    ):
        for stmt in statements:
            if isinstance(stmt, ChoiceNode):
                referenced_scenes.add(stmt.target)
                if stmt.target not in defined_scenes:
                    self.errors.append(
                        SemanticError(
                            f"Choice in scene '{scene_name}' references "
                            f"undefined scene '{stmt.target}'",
                            stmt.line,
                        )
                    )
            elif isinstance(stmt, IfNode):
                self._validate_condition(stmt, variable_types, inventory_used)
                if stmt.then_target:
                    referenced_scenes.add(stmt.then_target)
                    if stmt.then_target not in defined_scenes:
                        self.errors.append(
                            SemanticError(
                                f"If-branch in scene '{scene_name}' references "
                                f"undefined scene '{stmt.then_target}'",
                                stmt.line,
                            )
                        )
                if stmt.else_target:
                    referenced_scenes.add(stmt.else_target)
                    if stmt.else_target not in defined_scenes:
                        self.errors.append(
                            SemanticError(
                                f"Else-branch in scene '{scene_name}' references "
                                f"undefined scene '{stmt.else_target}'",
                                stmt.line,
                            )
                        )

                self._validate_statements(
                    scene_name,
                    stmt.then_block,
                    variable_types,
                    inventory_used,
                    referenced_scenes,
                    defined_scenes,
                )
                self._validate_statements(
                    scene_name,
                    stmt.else_block,
                    variable_types,
                    inventory_used,
                    referenced_scenes,
                    defined_scenes,
                )

    def _register_variable_type(self, variable_types, name: str, typ: str, line: int):
        existing = variable_types.get(name)
        if existing and existing != typ:
            self.errors.append(
                SemanticError(
                    f"Variable '{name}' used with conflicting types: '{existing}' and '{typ}'",
                    line,
                )
            )
            return
        variable_types[name] = typ

    def _validate_condition(self, if_stmt: IfNode, variable_types, inventory_used: bool):
        cond = if_stmt.condition

        if cond.kind == "has_item":
            if not inventory_used:
                self.warnings.append(
                    SemanticWarning(
                        "Condition checks inventory item, but no item has been added via 'set item ...'",
                        if_stmt.line,
                    )
                )
            return

        if cond.kind == "has_flag":
            var_name = cond.variable or ""
            if var_name not in variable_types:
                self.errors.append(
                    SemanticError(f"Condition references undefined variable '{var_name}'", if_stmt.line)
                )
                return
            if variable_types[var_name] != "flag":
                self.errors.append(
                    SemanticError(
                        f"Condition 'has {var_name}' requires a flag variable, but '{var_name}' is '{variable_types[var_name]}'",
                        if_stmt.line,
                    )
                )
            return

        if cond.kind == "compare":
            var_name = cond.variable or ""
            if var_name not in variable_types:
                self.errors.append(
                    SemanticError(f"Comparison uses undefined variable '{var_name}'", if_stmt.line)
                )
                return
            var_type = variable_types[var_name]
            if cond.operator in (">", "<"):
                if var_type != "number":
                    self.errors.append(
                        SemanticError(
                            f"Comparison '{cond.operator}' requires numeric variable, but '{var_name}' is '{var_type}'",
                            if_stmt.line,
                        )
                    )
                    return
                if not isinstance(cond.value, int):
                    self.errors.append(
                        SemanticError("Comparison value must be an integer literal", if_stmt.line)
                    )
                return

            if cond.operator == "==":
                if var_type == "number" and isinstance(cond.value, int):
                    return
                if var_type == "text" and isinstance(cond.value, str):
                    return
                self.errors.append(
                    SemanticError(
                        f"Type mismatch in equality check for '{var_name}' ({var_type})",
                        if_stmt.line,
                    )
                )
                return

            self.errors.append(
                SemanticError(f"Unsupported comparison operator '{cond.operator}'", if_stmt.line)
            )
            return

        self.errors.append(SemanticError(f"Unknown condition kind '{cond.kind}'", if_stmt.line))

    def report(self):
        for w in self.warnings:
            print(f"  \033[33m{w}\033[0m")
        for e in self.errors:
            print(f"  \033[31m{e}\033[0m")