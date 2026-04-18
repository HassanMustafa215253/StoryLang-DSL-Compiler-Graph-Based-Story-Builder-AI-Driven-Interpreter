"""
Display module for StoryLang
Handles all terminal output with ANSI color codes and formatting.
"""

import time
import sys
import os


def _supports_color() -> bool:
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()


USE_COLOR = _supports_color()

# ANSI codes
R = '\033[0m'
BOLD = '\033[1m'
DIM = '\033[2m'
ITALIC = '\033[3m'
CYAN = '\033[36m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RED = '\033[31m'
MAGENTA = '\033[35m'
BLUE = '\033[34m'
WHITE = '\033[97m'
BG_BLACK = '\033[40m'


def c(code: str, text: str) -> str:
    if USE_COLOR:
        return f"{code}{text}{R}"
    return text


class Display:
    STORY_WIDTH = 70

    def __init__(self):
        self.slow = True   # typewriter effect on/off

    def clear(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_banner(self):
        lines = [
            "",
            c(CYAN + BOLD, "╔══════════════════════════════════════════════════════════╗"),
            c(CYAN + BOLD, "║") + c(MAGENTA + BOLD, "   ███████╗████████╗ ██████╗ ██████╗ ██╗   ██╗           ") + c(CYAN + BOLD, "║"),
            c(CYAN + BOLD, "║") + c(MAGENTA + BOLD, "   ██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗╚██╗ ██╔╝           ") + c(CYAN + BOLD, "║"),
            c(CYAN + BOLD, "║") + c(MAGENTA + BOLD, "   ███████╗   ██║   ██║   ██║██████╔╝ ╚████╔╝            ") + c(CYAN + BOLD, "║"),
            c(CYAN + BOLD, "║") + c(MAGENTA + BOLD, "   ╚════██║   ██║   ██║   ██║██╔══██╗  ╚██╔╝             ") + c(CYAN + BOLD, "║"),
            c(CYAN + BOLD, "║") + c(MAGENTA + BOLD, "   ███████║   ██║   ╚██████╔╝██║  ██║   ██║              ") + c(CYAN + BOLD, "║"),
            c(CYAN + BOLD, "║") + c(MAGENTA + BOLD, "   ╚══════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝   ╚═╝              ") + c(CYAN + BOLD, "║"),
            c(CYAN + BOLD, "║") + c(CYAN,            "                   L A N G                               ") + c(CYAN + BOLD, "║"),
            c(CYAN + BOLD, "║") + c(DIM,             "       Interactive Story Compiler & Execution Engine      ") + c(CYAN + BOLD, "║"),
            c(CYAN + BOLD, "╚══════════════════════════════════════════════════════════╝"),
            "",
        ]
        for line in lines:
            print(line)

    def print_divider(self, char="─"):
        print(c(DIM, char * self.STORY_WIDTH))

    def print_bold(self, text: str):
        print(c(BOLD, text))

    def print_dim(self, text: str):
        print(c(DIM, text))

    def print_info(self, text: str):
        print(c(CYAN, f"  ℹ  {text}"))

    def print_success(self, text: str):
        print(c(GREEN, f"  ✓  {text}"))

    def print_warning(self, text: str):
        print(c(YELLOW, f"  ⚠  {text}"))

    def error(self, text: str):
        print(c(RED, f"  ✗  {text}"))

    def print_scene_header(self, name: str):
        print()
        print(c(CYAN + BOLD, f"  ┌─ SCENE: {name.upper()} {'─' * max(0, 50 - len(name))}┐"))
        print()

    def print_choices_header(self, text: str):
        print(c(YELLOW + BOLD, f"  ❯ {text}"))
        print()

    def print_choice(self, num: int, label: str):
        print(c(WHITE, f"    [{num}] ") + c(GREEN, label))

    def print_ai_indicator(self, msg: str):
        print(c(MAGENTA, f"\n  ✦ AI: {msg}"), end="", flush=True)
        for _ in range(3):
            time.sleep(0.3)
            print(c(MAGENTA, "."), end="", flush=True)
        print()

    def prompt_str(self) -> str:
        return c(CYAN, "\n  Your choice ❯ ")

    def repl_prompt(self) -> str:
        return c(YELLOW + BOLD, "\nStoryLang ❯ ")

    def slow_print(self, text: str, delay: float = 0.018):
        """Typewriter-style printing."""
        print()
        prefix = "  "
        line_width = self.STORY_WIDTH - 4
        words = text.split()
        line = prefix

        for word in words:
            if len(line) + len(word) + 1 > self.STORY_WIDTH:
                print()
                line = prefix
            if self.slow:
                for ch in (word + " "):
                    print(c(WHITE, ch), end="", flush=True)
                    time.sleep(delay)
            else:
                print(word + " ", end="", flush=True)
            line += word + " "
        print()

    def print_code(self, code: str):
        """Print source code with line numbers."""
        print()
        self.print_divider("─")
        for i, line in enumerate(code.splitlines(), 1):
            print(c(DIM, f"  {i:3d} │ ") + c(CYAN, line))
        self.print_divider("─")
        print()

    def print_token_table(self, tokens):
        print()
        print(c(BOLD, f"  {'#':<5} {'TYPE':<25} {'VALUE':<30} {'LINE':<5}"))
        self.print_divider()
        for i, tok in enumerate(tokens, 1):
            if tok.type.name == "EOF":
                break
            print(f"  {i:<5} {c(CYAN, tok.type.name):<34} {c(GREEN, repr(tok.value)):<39} {c(DIM, str(tok.line))}")
        print()

    def print_ast(self, program, indent=0):
        """Pretty-print the AST."""
        from .ast_nodes import (SceneNode, DescriptionNode, ChoiceNode,
                                 IfNode, SetNode, AIGenerateSceneNode, AIGenerateOptionsNode)

        def format_condition(cond):
            if cond.kind == "has_flag":
                return f"has {cond.variable}"
            if cond.kind == "has_item":
                return f"has item {cond.value!r}"
            if cond.kind == "compare":
                return f"{cond.variable} {cond.operator} {cond.value!r}" if isinstance(cond.value, str) else f"{cond.variable} {cond.operator} {cond.value}"
            return "<unknown condition>"

        def print_statement(stmt, pad: str):
            if isinstance(stmt, DescriptionNode):
                print(c(DIM, f"{pad}├─ ") + c(GREEN, "DESCRIPTION") + f": {stmt.text!r}")
                return

            if isinstance(stmt, ChoiceNode):
                print(c(DIM, f"{pad}├─ ") + c(YELLOW, "CHOICE") + f": {stmt.label!r} → {stmt.target}")
                return

            if isinstance(stmt, IfNode):
                cond_text = format_condition(stmt.condition)
                if stmt.then_target:
                    then_repr = stmt.then_target
                else:
                    then_repr = f"{{block: {len(stmt.then_block)} stmt}}"
                else_repr = ""
                if stmt.else_target:
                    else_repr = f" | ELSE → {stmt.else_target}"
                elif stmt.else_block:
                    else_repr = f" | ELSE → {{block: {len(stmt.else_block)} stmt}}"
                print(c(DIM, f"{pad}├─ ") + c(MAGENTA, "IF") + f": {cond_text} → {then_repr}{else_repr}")
                for sub in stmt.then_block:
                    print_statement(sub, pad + "  ")
                for sub in stmt.else_block:
                    print_statement(sub, pad + "  ")
                return

            if isinstance(stmt, SetNode):
                if stmt.action == "set_flag":
                    set_text = f"{stmt.variable}"
                elif stmt.action == "add_item":
                    set_text = f"item {stmt.value!r}"
                elif stmt.action == "assign_number":
                    set_text = f"{stmt.variable} = {stmt.value}"
                elif stmt.action == "inc_number":
                    set_text = f"{stmt.variable} += {stmt.delta}"
                elif stmt.action == "dec_number":
                    set_text = f"{stmt.variable} -= {stmt.delta}"
                elif stmt.action == "set_text":
                    set_text = f"{stmt.variable} = {stmt.value!r}"
                elif stmt.action == "remove_item":
                    set_text = f"remove item {stmt.value!r}"
                elif stmt.action == "unset_variable":
                    set_text = f"unset {stmt.variable}"
                else:
                    set_text = f"{stmt.variable} (unknown action)"
                print(c(DIM, f"{pad}├─ ") + c(BLUE, "SET") + f": {set_text}")
                return

            if isinstance(stmt, AIGenerateSceneNode):
                print(c(DIM, f"{pad}├─ ") + c(MAGENTA + BOLD, "AI_SCENE") + f": {stmt.prompt!r}")
                return

            if isinstance(stmt, AIGenerateOptionsNode):
                print(c(DIM, f"{pad}├─ ") + c(MAGENTA + BOLD, "AI_OPTIONS") + f": {stmt.prompt!r}")
                return

            print(c(DIM, f"{pad}├─ ") + c(RED, "UNKNOWN") + f": {type(stmt).__name__}")

        print()
        for scene in program.scenes:
            pad = "  "
            print(c(CYAN + BOLD, f"{pad}SCENE ") + c(WHITE, scene.name))
            for stmt in scene.statements:
                print_statement(stmt, pad + "  ")
        print()