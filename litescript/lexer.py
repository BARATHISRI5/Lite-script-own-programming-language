"""
lexer.py — Tokenizer for LiteScript
=====================================

The lexer (also called a "tokenizer" or "scanner") is the FIRST stage of
compilation. It takes raw source code (a string of characters) and groups
them into meaningful chunks called **tokens**.

Analogy: A lexer is like a cashier scanning grocery items. Each item gets a
label: "apple", "bread", "milk". Similarly, the lexer scans characters and
labels them: "this is a number", "this is a keyword", "this is an operator".

Example:
    Input:  "let x = 5 + 3"
    Output: [LET, IDENTIFIER("x"), EQUALS, NUMBER(5), PLUS, NUMBER(3), EOF]

Each token carries:
    - type:   What kind of token it is (NUMBER, KEYWORD, OPERATOR, etc.)
    - value:  The actual text of the token
    - line:   Which line it appears on (for error messages)
    - column: Which column it appears on (for error messages)
"""

from enum import Enum, auto
from collections import namedtuple
from typing import List


# ─────────────────────────────────────────────────────────────────────────────
# TOKEN TYPES — All the different kinds of "labels" we can assign
# ─────────────────────────────────────────────────────────────────────────────

class TokenType(Enum):
    """
    Every possible token type in LiteScript.

    These are like the labels on grocery items. When the lexer sees "let",
    it labels it as TokenType.LET. When it sees "42", it labels it as
    TokenType.NUMBER, and so on.
    """
    # ── Keywords ──────────────────────────────────────────────────────────
    LET     = auto()   # Variable declaration: let x = 5
    SAY     = auto()   # Print statement:      say x
    IF      = auto()   # Conditional:          if x > 5 { ... }
    ELSE    = auto()   # Else branch:          else { ... }
    LOOP    = auto()   # Loop:                 loop 5 times { ... }
    TIMES   = auto()   # Loop keyword:         loop 5 times { ... }
    FUNC    = auto()   # Function declaration: func add(a, b) { ... }
    GIVE    = auto()   # Return from function: give a + b

    # ── Literals ──────────────────────────────────────────────────────────
    NUMBER  = auto()   # Integer literal:  42, 0, 999
    STRING  = auto()   # String literal:   "hello world"

    # ── Identifier ────────────────────────────────────────────────────────
    IDENTIFIER = auto()  # Variable/function names: x, myVar, add

    # ── Arithmetic Operators ──────────────────────────────────────────────
    PLUS    = auto()   # +
    MINUS   = auto()   # -
    STAR    = auto()   # *
    SLASH   = auto()   # /
    PERCENT = auto()   # %

    # ── Comparison Operators ──────────────────────────────────────────────
    GT      = auto()   # >
    LT      = auto()   # <
    GTE     = auto()   # >=
    LTE     = auto()   # <=
    EQEQ    = auto()   # ==
    NEQ     = auto()   # !=

    # ── Punctuation ───────────────────────────────────────────────────────
    LPAREN  = auto()   # (
    RPAREN  = auto()   # )
    LBRACE  = auto()   # {
    RBRACE  = auto()   # }
    COMMA   = auto()   # ,
    EQUALS  = auto()   # = (assignment, NOT comparison)

    # ── Special ───────────────────────────────────────────────────────────
    NEWLINE = auto()   # End of line
    EOF     = auto()   # End of file (signals "we're done scanning")


# ─────────────────────────────────────────────────────────────────────────────
# TOKEN — A single labeled chunk of source code
# ─────────────────────────────────────────────────────────────────────────────

# namedtuple gives us a lightweight, immutable data structure.
# Token(type=TokenType.NUMBER, value="42", line=1, column=5)
Token = namedtuple("Token", ["type", "value", "line", "column"])


# ─────────────────────────────────────────────────────────────────────────────
# KEYWORD MAP — Maps keyword strings to their token types
# ─────────────────────────────────────────────────────────────────────────────

KEYWORDS = {
    "let":   TokenType.LET,
    "say":   TokenType.SAY,
    "if":    TokenType.IF,
    "else":  TokenType.ELSE,
    "loop":  TokenType.LOOP,
    "times": TokenType.TIMES,
    "func":  TokenType.FUNC,
    "give":  TokenType.GIVE,
}


# ─────────────────────────────────────────────────────────────────────────────
# LEXER CLASS — The scanner that converts source code into tokens
# ─────────────────────────────────────────────────────────────────────────────

class Lexer:
    """
    Scans source code character-by-character and produces a list of tokens.

    Usage:
        lexer = Lexer("let x = 42")
        tokens = lexer.tokenize()
        # → [Token(LET, "let", 1, 1), Token(IDENTIFIER, "x", 1, 5), ...]
    """

    def __init__(self, source: str):
        """
        Initialize the lexer with source code.

        Args:
            source: The raw LiteScript source code string
        """
        self.source = source       # The full source code string
        self.pos = 0               # Current position in the source string
        self.line = 1              # Current line number (starts at 1)
        self.column = 1            # Current column number (starts at 1)

    def _current_char(self) -> str:
        """
        Get the character at the current position.
        Returns empty string if we've reached the end of the source.
        """
        if self.pos < len(self.source):
            return self.source[self.pos]
        return ""

    def _peek(self) -> str:
        """
        Look at the NEXT character without consuming it.
        This is like peeking at the next card without taking it from the deck.
        """
        if self.pos + 1 < len(self.source):
            return self.source[self.pos + 1]
        return ""

    def _advance(self) -> str:
        """
        Consume the current character and move to the next one.
        Returns the character that was consumed.
        Also updates line/column tracking for error messages.
        """
        char = self._current_char()
        self.pos += 1
        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def _skip_whitespace(self):
        """
        Skip over spaces and tabs (but NOT newlines — those are tokens!).
        """
        while self._current_char() in (" ", "\t", "\r"):
            self._advance()

    def _skip_comment(self):
        """
        Skip single-line comments starting with '#'.
        Everything after '#' until end-of-line is ignored.
        """
        while self._current_char() and self._current_char() != "\n":
            self._advance()

    def _read_number(self) -> Token:
        """
        Read a sequence of digits and produce a NUMBER token.

        Examples: "42" → Token(NUMBER, "42", ...)
                  "0"  → Token(NUMBER, "0", ...)
        """
        start_col = self.column
        num_str = ""
        while self._current_char().isdigit():
            num_str += self._advance()
        return Token(TokenType.NUMBER, num_str, self.line, start_col)

    def _read_string(self) -> Token:
        """
        Read a string literal enclosed in double quotes.

        Example: '"hello world"' → Token(STRING, "hello world", ...)

        Note: We consume the opening and closing quotes but don't include
        them in the token value.
        """
        start_col = self.column
        start_line = self.line
        self._advance()  # consume the opening "
        string_content = ""
        while self._current_char() and self._current_char() != '"':
            if self._current_char() == "\\":
                # Handle escape sequences like \" and \\
                self._advance()  # skip the backslash
                escape_char = self._advance()
                if escape_char == "n":
                    string_content += "\n"
                elif escape_char == "t":
                    string_content += "\t"
                elif escape_char == '"':
                    string_content += '"'
                elif escape_char == "\\":
                    string_content += "\\"
                else:
                    string_content += escape_char
            else:
                string_content += self._advance()

        if not self._current_char():
            raise SyntaxError(
                f"Unterminated string literal at line {start_line}, column {start_col}"
            )
        self._advance()  # consume the closing "
        return Token(TokenType.STRING, string_content, start_line, start_col)

    def _read_identifier_or_keyword(self) -> Token:
        """
        Read an identifier (variable/function name) or a keyword.

        Identifiers start with a letter or underscore, followed by letters,
        digits, or underscores.

        If the identifier matches a keyword (e.g., "let", "say"), it gets
        the keyword token type instead of IDENTIFIER.

        Examples:
            "let"     → Token(LET, "let", ...)      (keyword)
            "myVar"   → Token(IDENTIFIER, "myVar", ...) (identifier)
            "_count"  → Token(IDENTIFIER, "_count", ...) (identifier)
        """
        start_col = self.column
        name = ""
        while self._current_char() and (self._current_char().isalnum() or self._current_char() == "_"):
            name += self._advance()

        # Check if the name is a reserved keyword
        token_type = KEYWORDS.get(name, TokenType.IDENTIFIER)
        return Token(token_type, name, self.line, start_col)

    def tokenize(self) -> List[Token]:
        """
        The main scanning method. Reads the entire source code and returns
        a list of tokens.

        This is the method you call from outside:
            tokens = Lexer(source_code).tokenize()

        Returns:
            A list of Token objects, always ending with an EOF token.
        """
        tokens: List[Token] = []

        while self.pos < len(self.source):
            # Skip whitespace (spaces, tabs) between tokens
            self._skip_whitespace()

            char = self._current_char()
            if not char:
                break

            # ── Comments ──────────────────────────────────────────────
            if char == "#":
                self._skip_comment()
                continue

            # ── Newlines ──────────────────────────────────────────────
            if char == "\n":
                tokens.append(Token(TokenType.NEWLINE, "\\n", self.line, self.column))
                self._advance()
                continue

            # ── Numbers ───────────────────────────────────────────────
            if char.isdigit():
                tokens.append(self._read_number())
                continue

            # ── Strings ───────────────────────────────────────────────
            if char == '"':
                tokens.append(self._read_string())
                continue

            # ── Identifiers and Keywords ──────────────────────────────
            if char.isalpha() or char == "_":
                tokens.append(self._read_identifier_or_keyword())
                continue

            # ── Two-character operators ────────────────────────────────
            # We check for 2-char operators first so ">=" doesn't get
            # misread as ">" followed by "="
            two_char = char + self._peek()
            if two_char == ">=":
                tokens.append(Token(TokenType.GTE, ">=", self.line, self.column))
                self._advance()
                self._advance()
                continue
            if two_char == "<=":
                tokens.append(Token(TokenType.LTE, "<=", self.line, self.column))
                self._advance()
                self._advance()
                continue
            if two_char == "==":
                tokens.append(Token(TokenType.EQEQ, "==", self.line, self.column))
                self._advance()
                self._advance()
                continue
            if two_char == "!=":
                tokens.append(Token(TokenType.NEQ, "!=", self.line, self.column))
                self._advance()
                self._advance()
                continue

            # ── Single-character operators and punctuation ─────────────
            single_char_tokens = {
                "+": TokenType.PLUS,
                "-": TokenType.MINUS,
                "*": TokenType.STAR,
                "/": TokenType.SLASH,
                "%": TokenType.PERCENT,
                ">": TokenType.GT,
                "<": TokenType.LT,
                "(": TokenType.LPAREN,
                ")": TokenType.RPAREN,
                "{": TokenType.LBRACE,
                "}": TokenType.RBRACE,
                ",": TokenType.COMMA,
                "=": TokenType.EQUALS,
            }

            if char in single_char_tokens:
                tokens.append(Token(single_char_tokens[char], char, self.line, self.column))
                self._advance()
                continue

            # ── Unknown character ─────────────────────────────────────
            raise SyntaxError(
                f"Unexpected character '{char}' at line {self.line}, column {self.column}"
            )

        # Always end with an EOF token so the parser knows when to stop
        tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return tokens
