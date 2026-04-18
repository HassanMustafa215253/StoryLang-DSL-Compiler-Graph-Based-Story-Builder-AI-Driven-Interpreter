# StoryLang — Interactive Story Compiler & Execution Engine
### Compiler Construction Project

---

## Overview

**StoryLang** is a custom-designed language and full compiler pipeline for building and playing interactive branching stories — all inside the terminal.

Unlike a traditional compiler that processes pre-written code, **StoryLang's compiler is itself the program**: it runs as an interactive REPL, asks the user what they want to do next, and compiles + executes the story in real time.

---

## Architecture

```
User Input
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                    STORYLANG REPL                       │
│  (engine/repl.py) — the main interactive compiler loop  │
└─────────┬───────────────────────────────────────────────┘
          │
    ┌─────▼──────┐     ┌─────────────┐
    │   BUILDER  │     │  DIRECT     │
    │  (wizard)  │     │  CODE INPUT │
    └─────┬──────┘     └──────┬──────┘
          └────────┬──────────┘
                   │  StoryLang Source (.story)
                   ▼
          ┌────────────────┐
          │  LEXER         │  Tokenises keywords, strings, symbols
          │  (engine/lexer)│
          └────────┬───────┘
                   │  Token stream
                   ▼
          ┌────────────────┐
          │  PARSER        │  Builds Abstract Syntax Tree
          │  (engine/parser)│
          └────────┬───────┘
                   │  AST (ProgramNode → SceneNode → Statements)
                   ▼
          ┌────────────────┐
          │  SEMANTIC      │  Validates scene refs, duplicates, variables
          │  ANALYZER      │
          └────────┬───────┘
                   │  Validated AST
                   ▼
          ┌────────────────┐    ┌──────────────────┐
          │  INTERPRETER   │◄───│  AI SERVICE      │
          │  (execution    │    │  (Anthropic API) │
          │   engine)      │    │  - generate scene│
          └────────────────┘    │  - generate opts │
                                └──────────────────┘
```

---

## Language Syntax (StoryLang)

```
# Scene definition
scene <name> {
    description: "<text>"
    
    # Player choices
    choice "<label>" -> <target_scene>
    
   # Flags (boolean state)
   set <flag_name>

   # Inventory-style items
   set item "<item_name>"

   # Numeric state
   set <var> = <int>
   set <var> += <int>
   set <var> -= <int>

   # Remove / clear state
   unset <variable_name>
   remove item "<item_name>"

   # Text assignment (optional / legacy-friendly)
   set <var> "<text>"

   # Conditional branching
   if has <flag_name> -> <scene_if_true>
   if has item "<item_name>" -> <scene_if_true>
   if <var> > <int> -> <scene_if_true>
   if <var> < <int> -> <scene_if_true>
   if <var> == <int> -> <scene_if_true>
      if <text_var> "<text_value>" -> <scene_if_true>   # shorthand for ==
   else -> <scene_if_false>

      # Nested inline branches
      if <condition> -> {
         set <var> "value"
         if <condition> -> { ... }
      }
      else -> {
         ...
      }
    
    # AI-generated content
    AI_generate_scene "<prompt>"
    AI_generate_options "<prompt>"
}
```

---

## How to Run

```bash
python main.py
```

### REPL Commands

| Command        | Description                                      |
|---------------|--------------------------------------------------|
| `build`       | Interactive wizard to create scenes step by step |
| `webbuild`    | Open browser-based visual scene builder          |
| `write`       | Type/paste raw StoryLang code directly           |
| `load <file>` | Load a `.story` file                             |
| `save <file>` | Save current source to disk                      |
| `show`        | Display current source code                      |
| `lex`         | Run lexer → show token stream                    |
| `parse`       | Run parser → show AST                            |
| `check`       | Run semantic analysis                            |
| `run`         | Full compile + execute the story                 |
| `demo`        | Load the built-in demo volcano story             |
| `speed`       | Toggle typewriter effect                         |
| `help`        | Show command list                                |
| `quit`        | Exit                                             |

---

## Compiler Phases

1. **Lexical Analysis** (`engine/lexer.py`)  
   Converts source text → token stream. Identifies keywords (`scene`, `choice`, `if`, `set`, etc.), string literals, identifiers, and symbols (`->`, `{`, `}`, `:`).

2. **Syntax Analysis** (`engine/parser.py`)  
   Converts tokens → AST. Builds `ProgramNode` containing `SceneNode`s, each holding typed statement nodes.

3. **Semantic Analysis** (`engine/semantic.py`)  
   Validates: duplicate scene names, undefined scene references in transitions, unreachable scenes, variable existence, and condition/type correctness (`flag` vs `number` vs inventory item checks).

4. **Interpretation / Execution** (`engine/interpreter.py`)  
   Walks the AST. Displays descriptions, presents choices, evaluates conditions, manages runtime state (`flags`, `inventory`, `numbers`, `text_vars`), and calls AI service.

5. **AI Integration** (`engine/ai_service.py`)  
   Calls Anthropic Claude API to generate scene descriptions and player choices on demand.

---

## Example Story File

See `examples/lost_temple.story` for a full example.

Load and run it:
```
StoryLang ❯ load examples/lost_temple.story
StoryLang ❯ run
```

---

## Requirements

- Python 3.8+
- No external packages required
- Internet access for AI features (optional — fallbacks exist)