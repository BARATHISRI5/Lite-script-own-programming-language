# LiteScript Compiler 🚀

A complete end-to-end compiler for **LiteScript**, a custom DSL that compiles to native executables via LLVM IR.

```
Source Code (.ls) → Lexer → Parser → AST → LLVM IR → Native Executable
```

## Quick Start

### 1. Install Dependencies

```bash
pip install llvmlite
```

### 2. Run a Program (JIT Mode)

```bash
cd litescript
python main.py examples/hello.ls
```

Expected output: `15`

### 3. View Generated LLVM IR

```bash
python main.py examples/hello.ls --emit-ir
```

### 4. Compile to Native Executable (requires clang)

```bash
python main.py examples/hello.ls --compile -o hello.exe
./hello.exe
```

---

## Language Reference

### Variables

```
let x = 42
let name = x + 8
```

All variables are 64-bit signed integers.

### Print Output

```
say 42
say "Hello, World!"
say x + y
```

### Arithmetic

| Operator | Description    | Example   |
|----------|---------------|-----------|
| `+`      | Addition      | `a + b`   |
| `-`      | Subtraction   | `a - b`   |
| `*`      | Multiplication| `a * b`   |
| `/`      | Division      | `a / b`   |
| `%`      | Modulo        | `a % b`   |
| `-`      | Negation      | `-x`      |

### Comparisons

| Operator | Description          |
|----------|---------------------|
| `>`      | Greater than        |
| `<`      | Less than           |
| `>=`     | Greater or equal    |
| `<=`     | Less or equal       |
| `==`     | Equal               |
| `!=`     | Not equal           |

### Conditionals

```
if x > 10 {
    say "big"
} else {
    say "small"
}
```

The `else` branch is optional.

### Loops

```
loop 5 times {
    say "hello"
}
```

The count can be any expression: `loop (n + 1) times { ... }`

### Functions

```
func add(a, b) {
    give a + b
}

let result = add(5, 3)
say result
```

- `func` declares a function
- `give` returns a value (like `return`)
- Functions support recursion

### Comments

```
# This is a comment
let x = 5  # Inline comments are NOT supported (use separate lines)
```

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Source Code │────▶│    Lexer     │────▶│   Parser    │────▶│   CodeGen   │
│   (.ls)     │     │ (tokenizer) │     │ (AST builder)│     │ (LLVM IR)   │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                    │
                                                          ┌────────┴────────┐
                                                          │                 │
                                                    ┌─────▼─────┐   ┌──────▼──────┐
                                                    │  JIT Run   │   │ clang →.exe │
                                                    │ (in memory)│   │ (on disk)   │
                                                    └───────────┘   └─────────────┘
```

### File Map

| File            | Role                          | Stage |
|----------------|-------------------------------|-------|
| `ast_nodes.py` | AST node dataclasses          | —     |
| `lexer.py`     | Tokenizer                     | 1     |
| `parser.py`    | Recursive descent parser      | 2     |
| `codegen.py`   | LLVM IR generation            | 3     |
| `compiler.py`  | Pipeline orchestrator         | —     |
| `main.py`      | CLI entry point               | —     |

---

## CLI Options

```
python main.py <file.ls>                  # JIT execute (default)
python main.py <file.ls> --emit-ir        # Print LLVM IR to console
python main.py <file.ls> --save-ir        # Save LLVM IR to .ll file
python main.py <file.ls> --compile        # Compile to native .exe
python main.py <file.ls> -o <output>      # Specify output file name
```

---

## Requirements

- Python 3.8+
- `llvmlite` (includes pre-built LLVM binaries)
- `clang` (optional, only needed for `--compile` mode)
