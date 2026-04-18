"""
Parser for StoryLang
Converts a token stream into an Abstract Syntax Tree.
"""

from typing import List, Optional
from .lexer import Token, TokenType
from .ast_nodes import (
    ProgramNode, SceneNode, DescriptionNode, ChoiceNode,
    IfNode, SetNode, ConditionNode, AIGenerateSceneNode, AIGenerateOptionsNode
)


class ParseError(Exception):
    def __init__(self, msg: str, line: int = 0):
        super().__init__(f"[Parser] Line {line}: {msg}")
        self.line = line


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = [t for t in tokens if t.type != TokenType.NEWLINE]
        self.pos = 0

    def error(self, msg: str):
        tok = self.current()
        raise ParseError(msg, tok.line)

    def current(self) -> Token:
        return self.tokens[self.pos]

    def peek(self, offset=1) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]  # EOF

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def expect(self, ttype: TokenType) -> Token:
        tok = self.current()
        if tok.type != ttype:
            self.error(f"Expected {ttype.name} but got {tok.type.name} ({tok.value!r})")
        return self.advance()

    def match(self, *types: TokenType) -> bool:
        return self.current().type in types

    # ------------------------------------------------------------------ #
    #  Top-level
    # ------------------------------------------------------------------ #

    def parse(self) -> ProgramNode:
        program = ProgramNode()
        while not self.match(TokenType.EOF):
            if self.match(TokenType.SCENE):
                program.scenes.append(self.parse_scene())
            else:
                # skip stray tokens at top level
                self.advance()
        return program

    # ------------------------------------------------------------------ #
    #  Scene
    # ------------------------------------------------------------------ #

    def parse_scene(self) -> SceneNode:
        line = self.current().line
        self.expect(TokenType.SCENE)
        name_tok = self.expect(TokenType.IDENTIFIER)
        node = SceneNode(name=name_tok.value, line=line)

        # Brace-delimited body is optional (project spec shows both forms)
        if self.match(TokenType.LBRACE):
            self.advance()
            while not self.match(TokenType.RBRACE, TokenType.EOF):
                stmt = self.parse_statement()
                if stmt:
                    node.statements.append(stmt)
            if self.match(TokenType.RBRACE):
                self.advance()
        else:
            # Parse until next "scene" keyword or EOF
            while not self.match(TokenType.SCENE, TokenType.EOF):
                stmt = self.parse_statement()
                if stmt:
                    node.statements.append(stmt)

        return node

    # ------------------------------------------------------------------ #
    #  Statements
    # ------------------------------------------------------------------ #

    def parse_statement(self):
        tok = self.current()

        if tok.type == TokenType.DESCRIPTION:
            return self.parse_description()
        elif tok.type == TokenType.CHOICE:
            return self.parse_choice()
        elif tok.type == TokenType.IF:
            return self.parse_if()
        elif tok.type == TokenType.SET:
            return self.parse_set()
        elif tok.type == TokenType.UNSET:
            return self.parse_unset()
        elif tok.type == TokenType.REMOVE:
            return self.parse_remove()
        elif tok.type == TokenType.AI_GENERATE_SCENE:
            return self.parse_ai_scene()
        elif tok.type == TokenType.AI_GENERATE_OPTIONS:
            return self.parse_ai_options()
        else:
            self.advance()  # skip unknown tokens inside a scene
            return None

    def parse_description(self) -> DescriptionNode:
        line = self.current().line
        self.expect(TokenType.DESCRIPTION)
        self.expect(TokenType.COLON)
        text_tok = self.expect(TokenType.STRING)
        return DescriptionNode(text=text_tok.value, line=line)

    def parse_choice(self) -> ChoiceNode:
        line = self.current().line
        self.expect(TokenType.CHOICE)
        label_tok = self.expect(TokenType.STRING)
        self.expect(TokenType.ARROW)
        target_tok = self.expect(TokenType.IDENTIFIER)
        return ChoiceNode(label=label_tok.value, target=target_tok.value, line=line)

    def parse_if(self) -> IfNode:
        line = self.current().line
        self.expect(TokenType.IF)
        condition = self.parse_condition()
        self.expect(TokenType.ARROW)
        then_target, then_block = self.parse_if_branch()

        else_target: Optional[str] = None
        else_block = []
        if self.match(TokenType.ELSE):
            self.advance()
            self.expect(TokenType.ARROW)
            else_target, else_block = self.parse_if_branch()

        return IfNode(
            condition=condition,
            then_target=then_target,
            then_block=then_block,
            else_target=else_target,
            else_block=else_block,
            line=line
        )

    def parse_if_branch(self):
        if self.match(TokenType.LBRACE):
            self.advance()
            block = []
            while not self.match(TokenType.RBRACE, TokenType.EOF):
                stmt = self.parse_statement()
                if stmt:
                    block.append(stmt)
            self.expect(TokenType.RBRACE)
            return None, block

        # Scene jump branch: if flag -> SomeScene
        if self.match(TokenType.IDENTIFIER):
            target_tok = self.advance()
            return target_tok.value, []

        # Inline single-statement branch: else -> description: "..."
        stmt = self.parse_statement()
        if stmt is None:
            self.error("Expected scene target, '{...}' block, or inline statement after '->'")
        return None, [stmt]

    def parse_set(self) -> SetNode:
        line = self.current().line
        self.expect(TokenType.SET)

        # Inventory shorthand: set item "torch"
        if self.match(TokenType.IDENTIFIER) and self.current().value == "item":
            self.advance()
            item_tok = self.expect(TokenType.STRING)
            return SetNode(action="add_item", variable="item", value=item_tok.value, line=line)

        var_tok = self.expect(TokenType.IDENTIFIER)

        # Numeric update operators: set trust += 1 / set trust -= 2
        if self.match(TokenType.PLUS_EQ):
            self.advance()
            delta = self.parse_signed_int()
            return SetNode(action="inc_number", variable=var_tok.value, delta=delta, line=line)
        if self.match(TokenType.MINUS_EQ):
            self.advance()
            delta = self.parse_signed_int()
            return SetNode(action="dec_number", variable=var_tok.value, delta=delta, line=line)

        # Assignment syntax: set trust = 5 / set title = "Hero"
        if self.match(TokenType.EQ):
            self.advance()
            if self.match(TokenType.STRING):
                return SetNode(action="set_text", variable=var_tok.value, value=self.advance().value, line=line)
            if self.match(TokenType.MINUS, TokenType.NUMBER):
                return SetNode(action="assign_number", variable=var_tok.value, value=self.parse_signed_int(), line=line)
            self.error("Expected string or number after '=' in set statement")

        # Backward-compatible shorthand: set has_key / set mood "grim" / set trust 5
        if self.match(TokenType.STRING):
            return SetNode(action="set_text", variable=var_tok.value, value=self.advance().value, line=line)
        if self.match(TokenType.MINUS, TokenType.NUMBER):
            return SetNode(action="assign_number", variable=var_tok.value, value=self.parse_signed_int(), line=line)

        return SetNode(action="set_flag", variable=var_tok.value, value=True, line=line)

    def parse_condition(self) -> ConditionNode:
        line = self.current().line

        # has-condition: if has quest_started -> ... / if has item "torch" -> ...
        if self.match(TokenType.HAS):
            self.advance()
            if self.match(TokenType.IDENTIFIER) and self.current().value == "item":
                self.advance()
                item_tok = self.expect(TokenType.STRING)
                return ConditionNode(kind="has_item", value=item_tok.value, line=line)
            var_tok = self.expect(TokenType.IDENTIFIER)
            return ConditionNode(kind="has_flag", variable=var_tok.value, line=line)

        # comparison: if trust_king > 3 -> ...
        left_tok = self.expect(TokenType.IDENTIFIER)
        if self.match(TokenType.STRING):
            return ConditionNode(
                kind="compare",
                variable=left_tok.value,
                operator="==",
                value=self.advance().value,
                line=line,
            )
        if self.match(TokenType.GT, TokenType.LT, TokenType.EQ_EQ):
            op_tok = self.advance()
            right = self.parse_condition_value()
            return ConditionNode(
                kind="compare",
                variable=left_tok.value,
                operator=op_tok.value,
                value=right,
                line=line,
            )

        # Backward-compatible shorthand: if has_key -> ...
        return ConditionNode(kind="has_flag", variable=left_tok.value, line=line)

    def parse_condition_value(self):
        if self.match(TokenType.STRING):
            return self.advance().value
        if self.match(TokenType.MINUS, TokenType.NUMBER):
            return self.parse_signed_int()
        self.error("Expected string or number in condition")

    def parse_signed_int(self) -> int:
        sign = 1
        if self.match(TokenType.MINUS):
            sign = -1
            self.advance()
        num_tok = self.expect(TokenType.NUMBER)
        return sign * int(num_tok.value)

    def parse_unset(self) -> SetNode:
        line = self.current().line
        self.expect(TokenType.UNSET)
        var_tok = self.expect(TokenType.IDENTIFIER)
        return SetNode(action="unset_variable", variable=var_tok.value, line=line)

    def parse_remove(self) -> SetNode:
        line = self.current().line
        self.expect(TokenType.REMOVE)
        kind_tok = self.expect(TokenType.IDENTIFIER)
        if kind_tok.value != "item":
            self.error("Only 'remove item \"name\"' is supported")
        item_tok = self.expect(TokenType.STRING)
        return SetNode(action="remove_item", variable="item", value=item_tok.value, line=line)

    def parse_ai_scene(self) -> AIGenerateSceneNode:
        line = self.current().line
        self.expect(TokenType.AI_GENERATE_SCENE)
        prompt_tok = self.expect(TokenType.STRING)
        return AIGenerateSceneNode(prompt=prompt_tok.value, line=line)

    def parse_ai_options(self) -> AIGenerateOptionsNode:
        line = self.current().line
        self.expect(TokenType.AI_GENERATE_OPTIONS)
        prompt_tok = self.expect(TokenType.STRING)
        return AIGenerateOptionsNode(prompt=prompt_tok.value, line=line)