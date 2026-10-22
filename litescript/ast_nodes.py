"""
ast_nodes.py — Abstract Syntax Tree (AST) Node Definitions for LiteScript
==========================================================================

Think of AST nodes like LEGO bricks. Each brick type represents a different
part of the language. When the parser reads your code, it snaps these bricks
together into a tree that represents the *structure* of your program.

For example, the code:
    let x = 5 + 3

Becomes a tree like:
    LetStatement
    ├── name: "x"
    └── value: BinaryOp
        ├── op: "+"
        ├── left: NumberLiteral(5)
        └── right: NumberLiteral(3)

We use Python dataclasses because they give us clean, readable node
definitions with automatic __init__, __repr__, and __eq__ methods.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# BASE CLASS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ASTNode:
    """Base class for all AST nodes. Every node in the tree inherits from this."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# PROGRAM (Root Node)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Program(ASTNode):
    """
    The root of the entire AST. A program is simply a list of statements.

    Example:
        let x = 5      ← statement 1
        say x           ← statement 2
        Becomes: Program(statements=[LetStatement(...), SayStatement(...)])
    """
    statements: List[ASTNode] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# STATEMENTS — Things that DO something
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LetStatement(ASTNode):
    """
    Variable declaration: `let x = 42`

    - name:  The variable name (e.g., "x")
    - value: The expression assigned to the variable (e.g., NumberLiteral(42))
    """
    name: str = ""
    value: 'ASTNode' = None  # type: ignore


@dataclass
class SayStatement(ASTNode):
    """
    Print statement: `say 42` or `say "hello"`

    - value: The expression to print. Can be a number or string expression.
    """
    value: 'ASTNode' = None  # type: ignore


@dataclass
class IfStatement(ASTNode):
    """
    Conditional: `if x > 5 { ... } else { ... }`

    - condition: The expression to evaluate (should produce a boolean/integer)
    - then_body: List of statements to execute if condition is true (non-zero)
    - else_body: List of statements to execute if condition is false (zero).
                 This is optional — not every `if` has an `else`.
    """
    condition: 'ASTNode' = None  # type: ignore
    then_body: List[ASTNode] = field(default_factory=list)
    else_body: List[ASTNode] = field(default_factory=list)


@dataclass
class LoopStatement(ASTNode):
    """
    Counted loop: `loop 5 times { ... }`

    - count: How many times to run the loop body (expression that evaluates to int)
    - body:  List of statements to execute on each iteration
    """
    count: 'ASTNode' = None  # type: ignore
    body: List[ASTNode] = field(default_factory=list)


@dataclass
class FuncDeclaration(ASTNode):
    """
    Function definition: `func add(a, b) { give a + b }`

    - name:   The function name (e.g., "add")
    - params: List of parameter names (e.g., ["a", "b"])
    - body:   List of statements inside the function
    """
    name: str = ""
    params: List[str] = field(default_factory=list)
    body: List[ASTNode] = field(default_factory=list)


@dataclass
class GiveStatement(ASTNode):
    """
    Return statement (only inside functions): `give a + b`

    - value: The expression to return from the function
    """
    value: 'ASTNode' = None  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# EXPRESSIONS — Things that PRODUCE a value
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BinaryOp(ASTNode):
    """
    Binary operation: `a + b`, `x > 5`, `m * n`

    - op:    The operator as a string ("+", "-", "*", "/", "%", ">", "<", etc.)
    - left:  The left-hand expression
    - right: The right-hand expression

    Analogies:
        5 + 3  →  BinaryOp(op="+", left=NumberLiteral(5), right=NumberLiteral(3))
        x > y  →  BinaryOp(op=">", left=Identifier("x"), right=Identifier("y"))
    """
    op: str = ""
    left: 'ASTNode' = None   # type: ignore
    right: 'ASTNode' = None  # type: ignore


@dataclass
class UnaryOp(ASTNode):
    """
    Unary operation: `-5` (negation)

    - op:      The operator (currently only "-")
    - operand: The expression being negated
    """
    op: str = ""
    operand: 'ASTNode' = None  # type: ignore


@dataclass
class NumberLiteral(ASTNode):
    """
    Integer constant: `42`, `0`, `999`

    - value: The integer value
    """
    value: int = 0


@dataclass
class StringLiteral(ASTNode):
    """
    String constant: `"hello world"`

    - value: The string content (without the surrounding quotes)
    """
    value: str = ""


@dataclass
class Identifier(ASTNode):
    """
    Variable reference: `x`, `myVar`, `counter`

    - name: The variable name being referenced
    """
    name: str = ""


@dataclass
class FuncCall(ASTNode):
    """
    Function call: `add(5, 3)`, `greet()`

    - name: The function being called (e.g., "add")
    - args: List of argument expressions (e.g., [NumberLiteral(5), NumberLiteral(3)])
    """
    name: str = ""
    args: List[ASTNode] = field(default_factory=list)
