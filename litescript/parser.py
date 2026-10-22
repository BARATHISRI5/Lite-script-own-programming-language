"""
parser.py — Recursive Descent Parser for LiteScript
=====================================================

The parser is the SECOND stage of compilation. It takes the flat list of
tokens from the lexer and builds a tree structure (the AST) that represents
the *meaning* and *hierarchy* of the program.

Analogy: If the lexer is like labeling words ("noun", "verb", "adjective"),
the parser is like diagramming sentences — figuring out which words go
together and what role each phrase plays.

This is a **recursive descent** parser, which means:
- Each grammar rule becomes a Python method
- Methods call each other recursively to handle nested structures
- We look at the current token to decide which rule to apply

Operator Precedence (lowest to highest):
    1. Comparison:      >, <, >=, <=, ==, !=
    2. Addition:        +, -
    3. Multiplication:  *, /, %
    4. Unary:           -x (negation)
    5. Primary:         numbers, strings, identifiers, function calls, (expr)
"""

from typing import List, Optional
from lexer import Token, TokenType
from ast_nodes import (
    Program, LetStatement, SayStatement, IfStatement, LoopStatement,
    FuncDeclaration, GiveStatement, BinaryOp, UnaryOp, NumberLiteral,
    StringLiteral, Identifier, FuncCall, ASTNode,
)


class ParseError(Exception):
    """Custom exception for parser errors with line/column info."""
    pass


class Parser:
    """
    Recursive descent parser that converts a list of tokens into an AST.

    Usage:
        parser = Parser(tokens)
        ast = parser.parse()
        # ast is a Program node containing all parsed statements
    """

    def __init__(self, tokens: List[Token]):
        """
        Initialize the parser with a list of tokens.

        Args:
            tokens: List of Token objects from the lexer
        """
        self.tokens = tokens     # The full list of tokens
        self.pos = 0             # Current position in the token list

    # ─────────────────────────────────────────────────────────────────────
    # HELPER METHODS — Navigate through the token stream
    # ─────────────────────────────────────────────────────────────────────

    def _current(self) -> Token:
        """Get the current token without consuming it."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        # If we're past the end, return the last token (should be EOF)
        return self.tokens[-1]

    def _peek(self) -> Token:
        """Look at the next token without consuming anything."""
        if self.pos + 1 < len(self.tokens):
            return self.tokens[self.pos + 1]
        return self.tokens[-1]

    def _advance(self) -> Token:
        """Consume the current token and move to the next one."""
        token = self._current()
        self.pos += 1
        return token

    def _expect(self, token_type: TokenType, context: str = "") -> Token:
        """
        Consume the current token, but ONLY if it matches the expected type.
        If it doesn't match, raise a helpful error message.

        This is like asserting "the next word in the sentence MUST be a verb".

        Args:
            token_type: The expected token type
            context: Optional description for the error message (e.g., "after 'let'")
        """
        token = self._current()
        if token.type != token_type:
            ctx = f" {context}" if context else ""
            raise ParseError(
                f"Expected {token_type.name}{ctx}, but got {token.type.name} "
                f"('{token.value}') at line {token.line}, column {token.column}"
            )
        return self._advance()

    def _skip_newlines(self):
        """
        Skip over any newline tokens. Newlines are significant for separating
        statements but should be skipped when we're looking for the next
        meaningful token.
        """
        while self._current().type == TokenType.NEWLINE:
            self._advance()

    def _match(self, *types: TokenType) -> bool:
        """Check if the current token matches any of the given types."""
        return self._current().type in types

    # ─────────────────────────────────────────────────────────────────────
    # TOP-LEVEL PARSING
    # ─────────────────────────────────────────────────────────────────────

    def parse(self) -> Program:
        """
        Parse the entire program. This is the entry point.

        Grammar rule: program → statement*
        A program is zero or more statements.
        """
        statements = []
        self._skip_newlines()

        while self._current().type != TokenType.EOF:
            stmt = self._parse_statement()
            if stmt is not None:
                statements.append(stmt)
            self._skip_newlines()

        return Program(statements=statements)

    # ─────────────────────────────────────────────────────────────────────
    # STATEMENT PARSING — Each statement type gets its own method
    # ─────────────────────────────────────────────────────────────────────

    def _parse_statement(self) -> ASTNode:
        """
        Determine which kind of statement we're looking at based on the
        current token, and dispatch to the appropriate parsing method.

        Grammar rule: statement → let_stmt | say_stmt | if_stmt | loop_stmt
                                 | func_decl | give_stmt | expr_stmt
        """
        token = self._current()

        if token.type == TokenType.LET:
            return self._parse_let()
        elif token.type == TokenType.SAY:
            return self._parse_say()
        elif token.type == TokenType.IF:
            return self._parse_if()
        elif token.type == TokenType.LOOP:
            return self._parse_loop()
        elif token.type == TokenType.FUNC:
            return self._parse_func()
        elif token.type == TokenType.GIVE:
            return self._parse_give()
        else:
            # If it's not a keyword, it must be an expression statement
            # (e.g., a standalone function call like `greet()`)
            return self._parse_expression()

    def _parse_let(self) -> LetStatement:
        """
        Parse a variable declaration.

        Grammar rule: let_stmt → "let" IDENTIFIER "=" expression

        Example: let x = 5 + 3
            1. Consume "let"
            2. Expect an identifier ("x")
            3. Expect "="
            4. Parse the expression ("5 + 3")
        """
        self._advance()  # consume 'let'
        name_token = self._expect(TokenType.IDENTIFIER, "after 'let'")
        self._expect(TokenType.EQUALS, "after variable name")
        value = self._parse_expression()
        return LetStatement(name=name_token.value, value=value)

    def _parse_say(self) -> SayStatement:
        """
        Parse a print statement.

        Grammar rule: say_stmt → "say" expression

        Example: say 42
            1. Consume "say"
            2. Parse the expression
        """
        self._advance()  # consume 'say'
        value = self._parse_expression()
        return SayStatement(value=value)

    def _parse_if(self) -> IfStatement:
        """
        Parse a conditional statement.

        Grammar rule: if_stmt → "if" expression "{" statement* "}"
                                ("else" "{" statement* "}")?

        Example: if x > 5 { say "big" } else { say "small" }
        """
        self._advance()  # consume 'if'

        # Parse the condition expression
        condition = self._parse_expression()

        # Parse the then-body: { statement* }
        self._skip_newlines()
        self._expect(TokenType.LBRACE, "after if condition")
        then_body = self._parse_block()

        # Check for optional else branch
        else_body = []
        self._skip_newlines()
        if self._current().type == TokenType.ELSE:
            self._advance()  # consume 'else'
            self._skip_newlines()
            self._expect(TokenType.LBRACE, "after 'else'")
            else_body = self._parse_block()

        return IfStatement(condition=condition, then_body=then_body, else_body=else_body)

    def _parse_loop(self) -> LoopStatement:
        """
        Parse a counted loop.

        Grammar rule: loop_stmt → "loop" expression "times" "{" statement* "}"

        Example: loop 5 times { say "hello" }
        """
        self._advance()  # consume 'loop'

        # Parse the count expression
        count = self._parse_expression()

        # Expect the "times" keyword
        self._expect(TokenType.TIMES, "after loop count")

        # Parse the loop body
        self._skip_newlines()
        self._expect(TokenType.LBRACE, "after 'times'")
        body = self._parse_block()

        return LoopStatement(count=count, body=body)

    def _parse_func(self) -> FuncDeclaration:
        """
        Parse a function declaration.

        Grammar rule: func_decl → "func" IDENTIFIER "(" params? ")" "{" statement* "}"
                      params → IDENTIFIER ("," IDENTIFIER)*

        Example: func add(a, b) { give a + b }
        """
        self._advance()  # consume 'func'

        # Get the function name
        name_token = self._expect(TokenType.IDENTIFIER, "after 'func'")

        # Parse parameter list: (param1, param2, ...)
        self._expect(TokenType.LPAREN, "after function name")
        params = []
        if self._current().type != TokenType.RPAREN:
            # Parse first parameter
            param = self._expect(TokenType.IDENTIFIER, "in parameter list")
            params.append(param.value)
            # Parse remaining parameters: , param
            while self._current().type == TokenType.COMMA:
                self._advance()  # consume ','
                param = self._expect(TokenType.IDENTIFIER, "in parameter list")
                params.append(param.value)
        self._expect(TokenType.RPAREN, "after parameters")

        # Parse function body
        self._skip_newlines()
        self._expect(TokenType.LBRACE, "after function parameters")
        body = self._parse_block()

        return FuncDeclaration(name=name_token.value, params=params, body=body)

    def _parse_give(self) -> GiveStatement:
        """
        Parse a return statement.

        Grammar rule: give_stmt → "give" expression

        Example: give a + b
        """
        self._advance()  # consume 'give'
        value = self._parse_expression()
        return GiveStatement(value=value)

    def _parse_block(self) -> List[ASTNode]:
        """
        Parse a block of statements enclosed in braces.
        Assumes the opening '{' has already been consumed.

        Grammar: "{" statement* "}"

        Returns a list of statement AST nodes.
        """
        statements = []
        self._skip_newlines()

        while self._current().type != TokenType.RBRACE:
            if self._current().type == TokenType.EOF:
                raise ParseError(
                    f"Unexpected end of file — expected '}}' to close block "
                    f"at line {self._current().line}"
                )
            stmt = self._parse_statement()
            if stmt is not None:
                statements.append(stmt)
            self._skip_newlines()

        self._advance()  # consume '}'
        return statements

    # ─────────────────────────────────────────────────────────────────────
    # EXPRESSION PARSING — Operator precedence via recursive descent
    # ─────────────────────────────────────────────────────────────────────
    # Precedence (lowest → highest):
    #   comparison → addition → multiplication → unary → primary
    #
    # Each level calls the next one, so multiplication binds tighter than
    # addition, etc. This is the classic recursive descent trick for
    # handling operator precedence.

    def _parse_expression(self) -> ASTNode:
        """
        Entry point for expression parsing. Starts at the lowest precedence.

        Grammar: expression → comparison
        """
        return self._parse_comparison()

    def _parse_comparison(self) -> ASTNode:
        """
        Parse comparison operators (lowest precedence).

        Grammar: comparison → addition ((">" | "<" | ">=" | "<=" | "==" | "!=") addition)?

        Note: Only ONE comparison per expression (no chaining like a > b > c).
        """
        left = self._parse_addition()

        comparison_ops = {
            TokenType.GT, TokenType.LT, TokenType.GTE,
            TokenType.LTE, TokenType.EQEQ, TokenType.NEQ,
        }

        if self._current().type in comparison_ops:
            op_token = self._advance()
            right = self._parse_addition()
            left = BinaryOp(op=op_token.value, left=left, right=right)

        return left

    def _parse_addition(self) -> ASTNode:
        """
        Parse addition and subtraction.

        Grammar: addition → multiplication (("+" | "-") multiplication)*

        The "*" means we can chain: 1 + 2 - 3 + 4
        This creates a left-associative tree:
            ((1 + 2) - 3) + 4
        """
        left = self._parse_multiplication()

        while self._current().type in (TokenType.PLUS, TokenType.MINUS):
            op_token = self._advance()
            right = self._parse_multiplication()
            left = BinaryOp(op=op_token.value, left=left, right=right)

        return left

    def _parse_multiplication(self) -> ASTNode:
        """
        Parse multiplication, division, and modulo.

        Grammar: multiplication → unary (("*" | "/" | "%") unary)*
        """
        left = self._parse_unary()

        while self._current().type in (TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op_token = self._advance()
            right = self._parse_unary()
            left = BinaryOp(op=op_token.value, left=left, right=right)

        return left

    def _parse_unary(self) -> ASTNode:
        """
        Parse unary operators (currently just negation).

        Grammar: unary → ("-")? primary

        Example: -5 → UnaryOp(op="-", operand=NumberLiteral(5))
        """
        if self._current().type == TokenType.MINUS:
            op_token = self._advance()
            operand = self._parse_primary()
            return UnaryOp(op=op_token.value, operand=operand)

        return self._parse_primary()

    def _parse_primary(self) -> ASTNode:
        """
        Parse primary expressions (highest precedence / atomic values).

        Grammar: primary → NUMBER | STRING | IDENTIFIER | func_call | "(" expression ")"

        This is the "base case" of our recursive expression parsing.
        Everything bottoms out here.
        """
        token = self._current()

        # ── Number literal ────────────────────────────────────────────
        if token.type == TokenType.NUMBER:
            self._advance()
            return NumberLiteral(value=int(token.value))

        # ── String literal ────────────────────────────────────────────
        if token.type == TokenType.STRING:
            self._advance()
            return StringLiteral(value=token.value)

        # ── Identifier or function call ───────────────────────────────
        if token.type == TokenType.IDENTIFIER:
            # Peek ahead: if the next token is '(', it's a function call
            if self._peek().type == TokenType.LPAREN:
                return self._parse_func_call()
            self._advance()
            return Identifier(name=token.value)

        # ── Parenthesized expression ──────────────────────────────────
        if token.type == TokenType.LPAREN:
            self._advance()  # consume '('
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN, "after parenthesized expression")
            return expr

        # ── Error: unexpected token ───────────────────────────────────
        raise ParseError(
            f"Unexpected token {token.type.name} ('{token.value}') "
            f"at line {token.line}, column {token.column}"
        )

    def _parse_func_call(self) -> FuncCall:
        """
        Parse a function call expression.

        Grammar: func_call → IDENTIFIER "(" args? ")"
                 args → expression ("," expression)*

        Example: add(5, 3) → FuncCall(name="add", args=[NumberLiteral(5), NumberLiteral(3)])
        """
        name_token = self._advance()  # consume the function name
        self._advance()  # consume '('

        args = []
        if self._current().type != TokenType.RPAREN:
            # Parse first argument
            args.append(self._parse_expression())
            # Parse remaining arguments: , expr
            while self._current().type == TokenType.COMMA:
                self._advance()  # consume ','
                args.append(self._parse_expression())

        self._expect(TokenType.RPAREN, "after function arguments")

        return FuncCall(name=name_token.value, args=args)
