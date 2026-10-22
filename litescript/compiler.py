"""
compiler.py — Pipeline Orchestrator for LiteScript
====================================================

This module ties together all the compilation stages into a single pipeline:

    Source Code (.ls) → Lexer → Parser → AST → CodeGen → LLVM IR → Execute/Compile

It also handles:
- JIT execution (running programs directly in memory using LLVM's JIT engine)
- Writing LLVM IR to .ll files
- Compiling to native executables via clang (if available)

Analogy: This is like the assembly line foreman who coordinates all the workers
(lexer, parser, codegen) and makes sure the product (your program) goes through
each station in the right order.
"""

import os
import sys
import subprocess
import ctypes

from lexer import Lexer
from parser import Parser
from codegen import CodeGenerator


class CompileError(Exception):
    """Raised when any stage of compilation fails."""
    pass


class LiteScriptCompiler:
    """
    The main compiler pipeline that orchestrates all compilation stages.

    Usage:
        compiler = LiteScriptCompiler()

        # Option 1: JIT execute (run in memory)
        compiler.run(source_code)

        # Option 2: Get LLVM IR as a string
        ir_text = compiler.compile_to_ir(source_code)

        # Option 3: Compile to native executable
        compiler.compile_to_executable(source_code, output_path="program.exe")
    """

    def compile_to_ir(self, source: str) -> str:
        """
        Compile LiteScript source code to LLVM IR text.

        This runs the first three stages of compilation:
            Source → Lexer → Parser → AST → CodeGen → LLVM IR

        Args:
            source: The LiteScript source code string

        Returns:
            The LLVM IR as a string
        """
        # Stage 1: Lexing — Convert source text to tokens
        lexer = Lexer(source)
        tokens = lexer.tokenize()

        # Stage 2: Parsing — Convert tokens to AST
        parser = Parser(tokens)
        ast = parser.parse()

        # Stage 3: Code Generation — Convert AST to LLVM IR
        codegen = CodeGenerator()
        module = codegen.generate(ast)

        return str(module)

    def run(self, source: str):
        """
        Compile and immediately execute a LiteScript program using JIT.

        JIT (Just-In-Time) compilation means we compile the code to machine
        instructions in memory and run them directly, without creating any
        files on disk. This is faster for development and testing.

        Args:
            source: The LiteScript source code string
        """
        import llvmlite.binding as llvm

        # Initialize LLVM's native code generation
        # Note: llvm.initialize() is deprecated in llvmlite 0.47+,
        # but native target/asmprinter init is still required.
        llvm.initialize_native_target()
        llvm.initialize_native_asmprinter()

        # Get the LLVM IR
        ir_text = self.compile_to_ir(source)

        # Parse the LLVM IR text into an LLVM module
        try:
            llvm_module = llvm.parse_assembly(ir_text)
            llvm_module.verify()
        except Exception as e:
            raise CompileError(f"LLVM IR verification failed:\n{e}\n\nGenerated IR:\n{ir_text}")

        # Create a JIT execution engine
        target = llvm.Target.from_default_triple()
        target_machine = target.create_target_machine()
        backing_mod = llvm.parse_assembly("")
        engine = llvm.create_mcjit_compiler(backing_mod, target_machine)

        # Add our module to the engine
        engine.add_module(llvm_module)
        engine.finalize_object()

        # Find and call the main() function
        main_ptr = engine.get_function_address("main")
        if main_ptr == 0:
            raise CompileError("Could not find 'main' function in compiled module")

        # Create a callable Python function from the pointer
        # main() returns i32 (int), takes no arguments
        cfunc = ctypes.CFUNCTYPE(ctypes.c_int)(main_ptr)
        result = cfunc()

        return result

    def compile_to_executable(self, source: str, output_path: str = "output.exe"):
        """
        Compile LiteScript source code to a native executable.

        This requires `clang` to be installed and accessible in PATH.
        The process is:
            1. Generate LLVM IR
            2. Write it to a .ll file
            3. Use clang to compile .ll → .exe

        Args:
            source: The LiteScript source code string
            output_path: Path for the output executable (default: "output.exe")

        Returns:
            The path to the generated executable
        """
        # Generate LLVM IR
        ir_text = self.compile_to_ir(source)

        # Write IR to a temporary .ll file
        ll_path = output_path.rsplit(".", 1)[0] + ".ll"
        with open(ll_path, "w") as f:
            f.write(ir_text)

        print(f"[LiteScript] LLVM IR written to: {ll_path}")

        # Try to compile with clang
        try:
            result = subprocess.run(
                ["clang", ll_path, "-o", output_path, "-lmsvcrt"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise CompileError(
                    f"Clang compilation failed:\n{result.stderr}"
                )
            print(f"[LiteScript] Executable compiled to: {output_path}")
            return output_path

        except FileNotFoundError:
            print(
                "[LiteScript] WARNING: 'clang' not found in PATH.\n"
                f"  The LLVM IR has been saved to: {ll_path}\n"
                "  You can compile it manually with:\n"
                f"    clang {ll_path} -o {output_path}\n"
                "\n"
                "  Or run the program via JIT (no clang needed):\n"
                f"    python main.py <source_file>"
            )
            return ll_path

    def emit_ir_to_file(self, source: str, output_path: str = "output.ll"):
        """
        Compile to LLVM IR and save to a file.

        Args:
            source: The LiteScript source code string
            output_path: Path for the output .ll file
        """
        ir_text = self.compile_to_ir(source)
        with open(output_path, "w") as f:
            f.write(ir_text)
        print(f"[LiteScript] LLVM IR written to: {output_path}")
        return ir_text
