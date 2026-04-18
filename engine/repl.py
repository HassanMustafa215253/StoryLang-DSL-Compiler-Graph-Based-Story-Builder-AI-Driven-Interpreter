"""
StoryLang REPL
The interactive read-eval-print loop that is the main face of the compiler.
Users can: build stories, write raw code, load files, run, inspect tokens/AST, etc.
"""

import os
import time
from typing import Optional

from .display import Display, c, CYAN, GREEN, YELLOW, MAGENTA, DIM, BOLD, RED, WHITE, R
from .lexer import Lexer, LexerError
from .parser import Parser, ParseError
from .semantic import SemanticAnalyzer
from .interpreter import Interpreter
from .ai_service import AIService
from .builder import StoryBuilder
from .web_builder import WebStoryBuilder


HELP_TEXT = """
  ┌─────────────────────────────────────────────────────────────┐
  │                    STORYLANG COMMANDS                       │
  ├─────────────────────────────────────────────────────────────┤
  │  build        Launch scene manager + terminal builder       │
  │  webbuild     Launch web-based scene builder                │
  │  write        Open a multi-line code editor (type 'END')    │
  │  load <file>  Load a .story file from disk                  │
  │  save <file>  Save current source to a .story file          │
  │  show         Print current source code                     │
  │  lex          Run lexer → show token stream                 │
  │  parse        Run parser → show AST                         │
  │  check        Run semantic analysis                         │
  │  run          Compile + execute the story                   │
  │  demo         Load the built-in demo story                  │
  │  speed        Toggle typewriter effect on/off               │
  │  clear        Clear the terminal                            │
  │  help         Show this help                                │
  │  quit / exit  Exit StoryLang                                │
  └─────────────────────────────────────────────────────────────┘
"""

DEMO_STORY = """\
# Demo: The Volcano Expedition
scene start {
  description: "You stand at the base of a smouldering volcano. The air shimmers with heat. Two paths stretch before you."
  choice "Climb toward the crater" -> crater
  choice "Enter the jungle trail" -> jungle
}

scene crater {
  AI_generate_scene "volcanic crater edge, molten lava below, dramatic atmosphere"
  set climbed_volcano
  choice "Look for the ancient altar" -> altar
  choice "Retreat to safety" -> jungle
}

scene jungle {
  description: "Dense foliage swallows you whole. Strange calls echo from somewhere deep in the canopy."
  AI_generate_options "exploring a mysterious jungle near a volcano"
}

scene altar {
  description: "You discover a ring of obsidian stones. At the centre sits a glowing artifact."
  if has climbed_volcano -> claim_artifact
  else -> locked_altar
}

scene claim_artifact {
  description: "Your courage on the volcano earned you the right to approach. The artifact pulses as you reach for it."
  set has_artifact
  choice "Take the artifact" -> victory
  choice "Leave it undisturbed" -> start
}

scene locked_altar {
  description: "An unseen force repels you. You haven't earned the right to approach yet."
  choice "Go back to the crater" -> crater
}

scene victory {
  description: "You hold the artifact aloft. Its warmth spreads through your hands. The volcano rumbles in acknowledgement."
}
"""


class StoryREPL:
    def __init__(self):
        self.display = Display()
        self.ai = AIService()
        self.builder = StoryBuilder(self.display)
        self.web_builder = WebStoryBuilder(self.display)
        self.source: str = ""
        self._running = True

    # ------------------------------------------------------------------ #
    #  Main loop
    # ------------------------------------------------------------------ #

    def run(self):
        self.display.clear()
        self.display.print_banner()
        self._print_intro()

        while self._running:
            try:
                cmd = input(self.display.repl_prompt()).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                self._cmd_quit()
                break

            if not cmd:
                continue
            self._dispatch(cmd)

    def _dispatch(self, raw: str):
        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        dispatch = {
            "build":  self._cmd_build,
            "webbuild": self._cmd_webbuild,
            "write":  self._cmd_write,
            "load":   lambda: self._cmd_load(arg),
            "save":   lambda: self._cmd_save(arg),
            "show":   self._cmd_show,
            "lex":    self._cmd_lex,
            "parse":  self._cmd_parse,
            "check":  self._cmd_check,
            "run":    self._cmd_run,
            "demo":   self._cmd_demo,
            "speed":  self._cmd_speed,
            "clear":  self.display.clear,
            "help":   self._cmd_help,
            "quit":   self._cmd_quit,
            "exit":   self._cmd_quit,
        }

        fn = dispatch.get(cmd)
        if fn:
            fn()
        else:
            self.display.print_warning(f"Unknown command '{cmd}'. Type 'help' for a list.")

    # ------------------------------------------------------------------ #
    #  Commands
    # ------------------------------------------------------------------ #

    def _print_intro(self):
        print(c(DIM, "  Type 'help' to see all commands."))
        print(c(DIM, "  Start with 'build' or 'webbuild' to create/edit a story, or 'demo' to load a sample.\n"))
        ai_ok = self.ai.check_available()
        if ai_ok:
            self.display.print_success("AI service connected. AI_generate commands are active.")
        else:
            self.display.print_warning("AI service unavailable. AI_generate commands will use fallbacks.")
        print()

    def _cmd_help(self):
        print(HELP_TEXT)

    def _cmd_quit(self):
        self.display.print_info("Farewell. May your stories never end.")
        self._running = False

    def _cmd_demo(self):
        self.source = DEMO_STORY
        self.display.print_success("Demo story loaded. Type 'show' to view it, 'run' to play it.")

    def _cmd_build(self):
        result = self.builder.build()
        if result:
            if self.source:
                merge = self._yes_no_prompt("Append to existing source? (n = replace)")
                if merge:
                    self.source = self.source.rstrip() + "\n\n" + result
                else:
                    self.source = result
            else:
                self.source = result
            self.display.print_success("Source code updated. Type 'show' to review, 'run' to play.")

    def _cmd_webbuild(self):
        result = self.web_builder.build_web(initial_source=self.source)
        if result:
            if self.source:
                merge = self._yes_no_prompt("Append to existing source? (n = replace)")
                if merge:
                    self.source = self.source.rstrip() + "\n\n" + result
                else:
                    self.source = result
            else:
                self.source = result
            self.display.print_success("Source code updated from web builder. Type 'show' to review, 'run' to play.")

    def _cmd_write(self):
        print(c(CYAN, "\n  Multi-line editor active. Type your StoryLang code."))
        print(c(DIM, "  Type END on its own line to finish. Type CANCEL to abort.\n"))
        lines = []
        while True:
            try:
                line = input(c(DIM, "  > "))
            except (EOFError, KeyboardInterrupt):
                break
            if line.strip() == "END":
                break
            if line.strip() == "CANCEL":
                self.display.print_info("Edit cancelled.")
                return
            lines.append(line)
        new_code = "\n".join(lines)
        if new_code.strip():
            if self.source and self._yes_no_prompt("Append to existing source?"):
                self.source = self.source.rstrip() + "\n\n" + new_code
            else:
                self.source = new_code
            self.display.print_success(f"Code accepted ({len(lines)} lines).")
        else:
            self.display.print_warning("Empty input, nothing changed.")

    def _cmd_load(self, path: str):
        if not path:
            path = input(c(CYAN, "\n  File path ❯ ")).strip()
        if not path:
            return
        if not path.endswith(".story"):
            path += ".story"
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.source = f.read()
            self.display.print_success(f"Loaded '{path}' ({len(self.source)} chars).")
        except FileNotFoundError:
            self.display.error(f"File not found: {path}")
        except Exception as e:
            self.display.error(f"Could not load file: {e}")

    def _cmd_save(self, path: str):
        if not self.source:
            self.display.print_warning("Nothing to save. Build or write a story first.")
            return
        if not path:
            path = input(c(CYAN, "\n  Save as ❯ ")).strip()
        if not path:
            return
        if not path.endswith(".story"):
            path += ".story"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.source)
            self.display.print_success(f"Saved to '{path}'.")
        except Exception as e:
            self.display.error(f"Could not save: {e}")

    def _cmd_show(self):
        if not self.source:
            self.display.print_warning("No source code. Use 'build' or 'write'.")
            return
        self.display.print_code(self.source)

    def _cmd_lex(self):
        if not self._require_source():
            return
        print(c(BOLD + CYAN, "\n  ── LEXICAL ANALYSIS ──"))
        try:
            lexer = Lexer(self.source)
            tokens = lexer.tokenize()
            self.display.print_token_table(tokens)
            self.display.print_success(f"Lexer produced {len(tokens)-1} token(s).")
        except LexerError as e:
            self.display.error(str(e))

    def _cmd_parse(self):
        if not self._require_source():
            return
        print(c(BOLD + CYAN, "\n  ── SYNTAX ANALYSIS & AST ──"))
        try:
            tokens = Lexer(self.source).tokenize()
            program = Parser(tokens).parse()
            self.display.print_ast(program)
            self.display.print_success(f"Parsed {len(program.scenes)} scene(s).")
        except (LexerError, ParseError) as e:
            self.display.error(str(e))

    def _cmd_check(self):
        if not self._require_source():
            return
        print(c(BOLD + CYAN, "\n  ── SEMANTIC ANALYSIS ──"))
        try:
            tokens = Lexer(self.source).tokenize()
            program = Parser(tokens).parse()
            analyzer = SemanticAnalyzer(program)
            ok = analyzer.analyze()
            analyzer.report()
            if ok:
                self.display.print_success("No semantic errors found.")
            else:
                self.display.error(f"{len(analyzer.errors)} error(s) found.")
        except (LexerError, ParseError) as e:
            self.display.error(str(e))

    def _cmd_run(self):
        if not self._require_source():
            return

        print(c(BOLD + CYAN, "\n  ── COMPILING ──"))
        try:
            # 1. Lex
            tokens = Lexer(self.source).tokenize()
            self.display.print_success(f"Lexer: {len(tokens)-1} tokens")

            # 2. Parse
            program = Parser(tokens).parse()
            self.display.print_success(f"Parser: {len(program.scenes)} scene(s)")

            # 3. Semantic check
            analyzer = SemanticAnalyzer(program)
            ok = analyzer.analyze()
            analyzer.report()
            if not ok:
                self.display.error("Compilation failed. Fix errors before running.")
                return
            self.display.print_success("Semantic check: OK")

            time.sleep(0.3)
            print()
            self.display.print_divider("═")
            print(c(BOLD + MAGENTA, "  ✦  STORY BEGINS  ✦"))
            self.display.print_divider("═")
            print(c(DIM, "  (Type a number to choose, 'q' to quit the story)\n"))

            # 4. Execute
            interp = Interpreter(program, self.ai, self.display)
            interp.run()

            print()
            self.display.print_divider("═")
            self.display.print_info("Story session ended. Back at StoryLang prompt.")

        except (LexerError, ParseError) as e:
            self.display.error(str(e))
        except Exception as e:
            self.display.error(f"Unexpected runtime error: {e}")
            raise

    def _cmd_speed(self):
        self.display.slow = not self.display.slow
        state = "ON" if self.display.slow else "OFF"
        self.display.print_info(f"Typewriter effect: {state}")

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _require_source(self) -> bool:
        if not self.source:
            self.display.print_warning("No source code loaded. Use 'build', 'write', or 'demo'.")
            return False
        return True

    def _yes_no_prompt(self, prompt: str) -> bool:
        while True:
            val = input(c(CYAN, f"\n  {prompt} [y/n] ❯ ")).strip().lower()
            if val in ('y', 'yes'):
                return True
            if val in ('n', 'no', ''):
                return False
            self.display.print_warning("Please enter y or n.")