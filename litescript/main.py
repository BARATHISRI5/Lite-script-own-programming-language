"""
main.py — CLI Entry Point for the LiteScript Compiler
=======================================================

This is the file you run from the command line to compile and execute
LiteScript programs.

Usage:
    python main.py examples/hello.ls              # JIT run (default)
    python main.py examples/hello.ls --emit-ir    # Print LLVM IR to console
    python main.py examples/hello.ls --save-ir    # Save LLVM IR to .ll file
    python main.py examples/hello.ls --compile    # Compile to .exe (requires clang)

The default mode (no flags) uses JIT execution, which runs the program
directly in memory without creating any files. This is the fastest way
to test your programs and doesn't require clang.
"""

import argparse
import sys
import os

from compiler import LiteScriptCompiler, CompileError


def main():
    """Parse command-line arguments and run the compiler."""

    # ── Set up argument parser ────────────────────────────────────────
    parser = argparse.ArgumentParser(
        prog="litescript",
        description="LiteScript Compiler — compile .ls files to native code via LLVM",
        epilog="Example: python main.py examples/hello.ls",
    )

    parser.add_argument(
        "source_file",
        help="Path to the .ls source file to compile",
    )

    parser.add_argument(
        "--emit-ir",
        action="store_true",
        help="Print the generated LLVM IR to the console (don't execute)",
    )

    parser.add_argument(
        "--save-ir",
        action="store_true",
        help="Save the generated LLVM IR to a .ll file",
    )

    parser.add_argument(
        "--compile",
        action="store_true",
        help="Compile to a native executable (requires clang in PATH)",
    )

    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output file path (for --compile or --save-ir)",
    )

    args = parser.parse_args()

    # ── Read the source file ──────────────────────────────────────────
    source_path = args.source_file

    if not os.path.exists(source_path):
        print(f"Error: File not found: {source_path}", file=sys.stderr)
        sys.exit(1)

    with open(source_path, "r", encoding="utf-8") as f:
        source_code = f.read()

    if not source_code.strip():
        print(f"Error: File is empty: {source_path}", file=sys.stderr)
        sys.exit(1)

    # ── Create the compiler ───────────────────────────────────────────
    compiler = LiteScriptCompiler()

    try:
        # ── Mode: Emit LLVM IR to console ─────────────────────────────
        if args.emit_ir:
            ir_text = compiler.compile_to_ir(source_code)
            print(ir_text)
            return

        # ── Mode: Save LLVM IR to file ────────────────────────────────
        if args.save_ir:
            output = args.output or source_path.rsplit(".", 1)[0] + ".ll"
            compiler.emit_ir_to_file(source_code, output)
            return

        # ── Mode: Compile to native executable ────────────────────────
        if args.compile:
            output = args.output or source_path.rsplit(".", 1)[0] + ".exe"
            compiler.compile_to_executable(source_code, output)
            return

        # ── Default mode: JIT execute ─────────────────────────────────
        compiler.run(source_code)

    except (SyntaxError, CompileError) as e:
        print(f"\n❌ Compilation Error:\n{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Internal Error:\n{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
