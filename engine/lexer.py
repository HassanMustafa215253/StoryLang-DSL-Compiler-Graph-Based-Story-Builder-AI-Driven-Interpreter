"""
Lexer for StoryLang
Tokenizes raw StoryLang source code into a stream of tokens.
"""

import re
from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Optional


class TokenType(Enum):
    # Keywords
    SCENE       = auto()
    DESCRIPTION = auto()
    CHOICE      = auto()
    IF          = auto()
    ELSE        = auto()
    SET         = auto()
    UNSET       = auto()
    REMOVE      = auto()
    HAS         = auto()
    END         = auto()

    # AI Commands
    AI_GENERATE_SCENE   = auto()
    AI_GENERATE_OPTIONS = auto()

    # Symbols
    LBRACE      = auto()
    RBRACE      = auto()
    COLON       = auto()
    ARROW       = auto()   # ->
    EQ          = auto()   # =
    EQ_EQ       = auto()   # ==
    GT          = auto()   # >
    LT          = auto()   # <
    PLUS_EQ     = auto()   # +=
    MINUS_EQ    = auto()   # -=
    MINUS       = auto()   # -

    # Literals
    STRING      = auto()
    IDENTIFIER  = auto()
    NUMBER      = auto()

    # Misc
    NEWLINE     = auto()
    EOF         = auto()
    UNKNOWN     = auto()


KEYWORDS = {
    "scene":               TokenType.SCENE,
    "description":         TokenType.DESCRIPTION,
    "choice":              TokenType.CHOICE,
    "if":                  TokenType.IF,
    "else":                TokenType.ELSE,
    "set":                 TokenType.SET,
    "unset":               TokenType.UNSET,
    "remove":              TokenType.REMOVE,
    "has":                 TokenType.HAS,
    "end":                 TokenType.END,
    "AI_generate_scene":   TokenType.AI_GENERATE_SCENE,
    "AI_generate_options": TokenType.AI_GENERATE_OPTIONS,
}


@dataclass
class Token:
    type: TokenType
    value: str
    line: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, line={self.line})"


class LexerError(Exception):
    def __init__(self, msg: str, line: int):
        super().__init__(f"[Lexer] Line {line}: {msg}")
        self.line = line


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.tokens: List[Token] = []

    def error(self, msg: str):
        raise LexerError(msg, self.line)

    def peek(self, offset=0) -> Optional[str]:
        idx = self.pos + offset
        if idx < len(self.source):
            return self.source[idx]
        return None

    def advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
        return ch

    def skip_whitespace_and_comments(self):
        while self.pos < len(self.source):
            ch = self.peek()
            if ch in (' ', '\t', '\r'):
                self.advance()
            elif ch == '#':
                # Comment until end of line
                while self.pos < len(self.source) and self.peek() != '\n':
                    self.advance()
            else:
                break

    def read_string(self) -> str:
        self.advance()  # consume opening "
        result = []
        while self.pos < len(self.source):
            ch = self.peek()
            if ch == '"':
                self.advance()
                return ''.join(result)
            elif ch == '\\':
                self.advance()
                esc = self.advance()
                result.append({'n': '\n', 't': '\t', '"': '"', '\\': '\\'}.get(esc, esc))
            elif ch == '\n':
                self.error("Unterminated string literal")
            else:
                result.append(self.advance())
        self.error("Unterminated string literal")

    def read_identifier_or_keyword(self) -> Token:
        start = self.pos
        line = self.line
        # Handle AI_generate_* specially since it has underscore+uppercase
        while self.pos < len(self.source) and (self.peek().isalnum() or self.peek() == '_'):
            self.advance()
        word = self.source[start:self.pos]
        ttype = KEYWORDS.get(word, TokenType.IDENTIFIER)
        return Token(ttype, word, line)

    def read_number(self) -> Token:
        start = self.pos
        line = self.line
        while self.pos < len(self.source) and self.peek().isdigit():
            self.advance()
        return Token(TokenType.NUMBER, self.source[start:self.pos], line)

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.source):
            self.skip_whitespace_and_comments()
            if self.pos >= len(self.source):
                break

            ch = self.peek()
            line = self.line

            if ch == '\n':
                self.advance()
                # Collapse multiple newlines
                if not self.tokens or self.tokens[-1].type != TokenType.NEWLINE:
                    self.tokens.append(Token(TokenType.NEWLINE, '\n', line))

            elif ch == '{':
                self.advance()
                self.tokens.append(Token(TokenType.LBRACE, '{', line))

            elif ch == '}':
                self.advance()
                self.tokens.append(Token(TokenType.RBRACE, '}', line))

            elif ch == ':':
                self.advance()
                self.tokens.append(Token(TokenType.COLON, ':', line))

            elif ch == '-' and self.peek(1) == '>':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.ARROW, '->', line))

            elif ch == '+' and self.peek(1) == '=':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.PLUS_EQ, '+=', line))

            elif ch == '-' and self.peek(1) == '=':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.MINUS_EQ, '-=', line))

            elif ch == '=' and self.peek(1) == '=':
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.EQ_EQ, '==', line))

            elif ch == '=':
                self.advance()
                self.tokens.append(Token(TokenType.EQ, '=', line))

            elif ch == '>':
                self.advance()
                self.tokens.append(Token(TokenType.GT, '>', line))

            elif ch == '<':
                self.advance()
                self.tokens.append(Token(TokenType.LT, '<', line))

            elif ch == '-':
                self.advance()
                self.tokens.append(Token(TokenType.MINUS, '-', line))

            elif ch == '"':
                s = self.read_string()
                self.tokens.append(Token(TokenType.STRING, s, line))

            elif ch.isalpha() or ch == '_':
                tok = self.read_identifier_or_keyword()
                self.tokens.append(tok)

            elif ch.isdigit():
                tok = self.read_number()
                self.tokens.append(tok)

            else:
                self.advance()  # skip unknown
                self.tokens.append(Token(TokenType.UNKNOWN, ch, line))

        self.tokens.append(Token(TokenType.EOF, '', self.line))
        return self.tokens