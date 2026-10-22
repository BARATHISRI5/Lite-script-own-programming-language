"""
codegen.py — LLVM IR Code Generator for LiteScript
====================================================

The code generator is the THIRD and most critical stage of compilation.
It walks the AST tree and emits **LLVM IR** — an intermediate representation
that LLVM can then optimize and compile to native machine code.

Analogy: If your AST is a blueprint for a house, the code generator is the
construction crew that translates that blueprint into actual building
instructions ("pour concrete here", "place a wall there").

LLVM IR is like assembly language but more portable and structured.
Here's what a simple `let x = 5` looks like in LLVM IR:
    %x = alloca i64          ; Reserve space on the stack for x
    store i64 5, i64* %x     ; Store the value 5 into that space

We use the `llvmlite` library which provides a Python API for building
LLVM IR without needing to write raw IR text.

Key Concepts:
- Module:  The top-level container (one per program)
- Function: A callable unit of code (we put top-level code in `main()`)
- Builder: The "cursor" that appends instructions to the current block
- Block:   A sequence of instructions within a function
- alloca:  Reserves stack memory for a variable
"""

import llvmlite.ir as ir
from ast_nodes import (
    Program, LetStatement, SayStatement, IfStatement, LoopStatement,
    FuncDeclaration, GiveStatement, BinaryOp, UnaryOp, NumberLiteral,
    StringLiteral, Identifier, FuncCall, ASTNode,
)


class CodeGenError(Exception):
    """Custom exception for code generation errors."""
    pass


class CodeGenerator:
    """
    Walks the AST and emits LLVM IR code using llvmlite.

    Usage:
        codegen = CodeGenerator()
        llvm_module = codegen.generate(ast)
        print(llvm_module)  # prints the LLVM IR text
    """

    def __init__(self):
        """Initialize the LLVM module and set up built-in functions."""
        # ── Create the LLVM Module ────────────────────────────────────
        # A module is like a .c file — it contains all functions and globals
        self.module = ir.Module(name="litescript_module")
        self.module.triple = "x86_64-pc-windows-msvc"  # Target Windows

        # ── Define common types ───────────────────────────────────────
        self.i64 = ir.IntType(64)      # 64-bit integer (our only number type)
        self.i32 = ir.IntType(32)      # 32-bit integer (for printf return)
        self.i8 = ir.IntType(8)        # 8-bit integer (for characters/strings)
        self.void = ir.VoidType()      # Void type (for functions that return nothing)

        # ── Symbol table (variable storage) ───────────────────────────
        # Maps variable names → their alloca'd pointers
        # Each scope level is a dict: [{"x": ptr_to_x, "y": ptr_to_y}, ...]
        self.scope_stack = [{}]

        # ── Function table ────────────────────────────────────────────
        # Maps function names → LLVM Function objects
        self.functions = {}

        # ── String constant counter ───────────────────────────────────
        self._string_counter = 0

        # ── Current builder and function ──────────────────────────────
        self.builder = None
        self.current_function = None

        # ── Declare printf (external C function) ──────────────────────
        # printf is how we implement the `say` statement.
        # It's declared as: int printf(const char* format, ...)
        # The `var_arg=True` makes it a variadic function (accepts any
        # number of arguments after the format string).
        printf_type = ir.FunctionType(
            self.i32,                          # Return type: int
            [ir.PointerType(self.i8)],         # First arg: char* (format string)
            var_arg=True                       # Variadic: accepts extra args
        )
        self.printf = ir.Function(self.module, printf_type, name="printf")
        self.functions["printf"] = self.printf

    # ─────────────────────────────────────────────────────────────────────
    # SCOPE MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────

    def _push_scope(self):
        """Enter a new scope (e.g., inside a function body)."""
        self.scope_stack.append({})

    def _pop_scope(self):
        """Exit the current scope."""
        self.scope_stack.pop()

    def _set_variable(self, name: str, ptr):
        """Store a variable's pointer in the current scope."""
        self.scope_stack[-1][name] = ptr

    def _get_variable(self, name: str):
        """
        Look up a variable by name, searching from innermost scope outward.
        This is how variable shadowing works — inner scopes can override outer ones.
        """
        for scope in reversed(self.scope_stack):
            if name in scope:
                return scope[name]
        raise CodeGenError(f"Undefined variable: '{name}'")

    # ─────────────────────────────────────────────────────────────────────
    # STRING UTILITIES
    # ─────────────────────────────────────────────────────────────────────

    def _create_global_string(self, text: str) -> ir.Constant:
        """
        Create a global string constant in the LLVM module.

        In LLVM IR, strings are stored as global byte arrays.
        "hello" becomes: @.str.0 = private constant [6 x i8] c"hello\00"

        The \00 at the end is the null terminator (C strings need this).

        Returns a pointer to the string that can be passed to printf.
        """
        # Add null terminator
        text_bytes = bytearray(text.encode("utf8")) + bytearray([0])
        str_type = ir.ArrayType(self.i8, len(text_bytes))

        # Create global variable
        name = f".str.{self._string_counter}"
        self._string_counter += 1
        global_str = ir.GlobalVariable(self.module, str_type, name=name)
        global_str.global_constant = True
        global_str.linkage = "private"
        global_str.initializer = ir.Constant(str_type, text_bytes)

        # Return a pointer to the first element (i8*)
        zero = ir.Constant(self.i32, 0)
        return self.builder.gep(global_str, [zero, zero], inbounds=True)

    # ─────────────────────────────────────────────────────────────────────
    # MAIN ENTRY POINT
    # ─────────────────────────────────────────────────────────────────────

    def generate(self, program: Program) -> ir.Module:
        """
        Generate LLVM IR for the entire program.

        Strategy:
        1. First pass: declare all user-defined functions
        2. Create the main() function for top-level statements
        3. Second pass: generate code for each function body
        4. Generate top-level statements in main()

        Args:
            program: The root AST node (Program)

        Returns:
            The LLVM IR Module
        """
        # ── First pass: declare user functions ────────────────────────
        # We need to declare all functions first so they can call each other
        # (even recursively or out of order).
        top_level_stmts = []
        func_declarations = []

        for stmt in program.statements:
            if isinstance(stmt, FuncDeclaration):
                func_declarations.append(stmt)
                self._declare_function(stmt)
            else:
                top_level_stmts.append(stmt)

        # ── Generate function bodies ──────────────────────────────────
        for func_decl in func_declarations:
            self._generate_function(func_decl)

        # ── Create main() for top-level code ──────────────────────────
        main_type = ir.FunctionType(self.i32, [])  # int main()
        main_func = ir.Function(self.module, main_type, name="main")
        self.functions["main"] = main_func

        entry_block = main_func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(entry_block)
        self.current_function = main_func

        # Generate all top-level statements
        for stmt in top_level_stmts:
            self._generate_statement(stmt)

        # Return 0 from main (success exit code)
        # Only add return if the current block isn't already terminated
        if not self.builder.block.is_terminated:
            self.builder.ret(ir.Constant(self.i32, 0))

        return self.module

    # ─────────────────────────────────────────────────────────────────────
    # FUNCTION DECLARATION & GENERATION
    # ─────────────────────────────────────────────────────────────────────

    def _declare_function(self, func_decl: FuncDeclaration):
        """
        Declare a function signature (without generating its body).

        This creates the LLVM function object so it can be referenced
        before its body is compiled (forward references).
        """
        # All params and return type are i64
        param_types = [self.i64] * len(func_decl.params)
        func_type = ir.FunctionType(self.i64, param_types)
        llvm_func = ir.Function(self.module, func_type, name=func_decl.name)

        # Name the parameters for readability in the IR
        for param, name in zip(llvm_func.args, func_decl.params):
            param.name = name

        self.functions[func_decl.name] = llvm_func

    def _generate_function(self, func_decl: FuncDeclaration):
        """
        Generate the body of a previously declared function.

        Steps:
        1. Create the entry block
        2. Allocate stack space for each parameter
        3. Store the argument values into the allocated space
        4. Generate the function body statements
        """
        llvm_func = self.functions[func_decl.name]
        entry_block = llvm_func.append_basic_block(name="entry")

        # Save the current builder state (we'll restore it after)
        saved_builder = self.builder
        saved_function = self.current_function

        self.builder = ir.IRBuilder(entry_block)
        self.current_function = llvm_func

        # Create a new scope for this function
        self._push_scope()

        # Allocate and store each parameter
        for param_value, param_name in zip(llvm_func.args, func_decl.params):
            # alloca creates stack space for the parameter
            alloca = self.builder.alloca(self.i64, name=param_name)
            # store copies the argument value into that stack space
            self.builder.store(param_value, alloca)
            self._set_variable(param_name, alloca)

        # Generate the function body
        for stmt in func_decl.body:
            self._generate_statement(stmt)

        # If the function doesn't end with a `give` (return), add a default return 0
        if not self.builder.block.is_terminated:
            self.builder.ret(ir.Constant(self.i64, 0))

        # Restore the previous scope and builder
        self._pop_scope()
        self.builder = saved_builder
        self.current_function = saved_function

    # ─────────────────────────────────────────────────────────────────────
    # STATEMENT GENERATION
    # ─────────────────────────────────────────────────────────────────────

    def _generate_statement(self, node: ASTNode):
        """Dispatch to the appropriate generation method based on node type."""
        if isinstance(node, LetStatement):
            self._gen_let(node)
        elif isinstance(node, SayStatement):
            self._gen_say(node)
        elif isinstance(node, IfStatement):
            self._gen_if(node)
        elif isinstance(node, LoopStatement):
            self._gen_loop(node)
        elif isinstance(node, GiveStatement):
            self._gen_give(node)
        elif isinstance(node, FuncCall):
            self._gen_func_call(node)
        else:
            # If it's an expression statement (like a standalone function call),
            # just generate the expression and discard the value
            self._generate_expression(node)

    def _gen_let(self, node: LetStatement):
        """
        Generate code for: let x = expression

        LLVM IR:
            %x = alloca i64          ; reserve stack space
            %tmp = <expression>      ; evaluate the expression
            store i64 %tmp, i64* %x  ; store the result
        """
        value = self._generate_expression(node.value)

        # If the value is not i64 (e.g., from a comparison), extend it
        if value.type != self.i64:
            value = self.builder.zext(value, self.i64)

        alloca = self.builder.alloca(self.i64, name=node.name)
        self.builder.store(value, alloca)
        self._set_variable(node.name, alloca)

    def _gen_say(self, node: SayStatement):
        """
        Generate code for: say expression

        For integers: calls printf("%d\\n", value)
        For strings:  calls printf("%s\\n", value)
        """
        if isinstance(node.value, StringLiteral):
            # String literal: create format string and print
            text = node.value.value + "\n"
            fmt_ptr = self._create_global_string(text)
            self.builder.call(self.printf, [fmt_ptr])
        else:
            # Integer expression: evaluate and print with %lld format
            value = self._generate_expression(node.value)
            if value.type != self.i64:
                value = self.builder.zext(value, self.i64)
            fmt_ptr = self._create_global_string("%lld\n")
            self.builder.call(self.printf, [fmt_ptr, value])

    def _gen_if(self, node: IfStatement):
        """
        Generate code for: if condition { then_body } else { else_body }

        LLVM IR uses conditional branches (cbranch) to jump between blocks:

            %cond = icmp ...              ; evaluate condition
            br i1 %cond, label %then, label %else  ; branch

        then:                             ; then block
            <then statements>
            br label %merge               ; jump to merge

        else:                             ; else block (optional)
            <else statements>
            br label %merge               ; jump to merge

        merge:                            ; continue from here
        """
        # Evaluate the condition
        cond_value = self._generate_expression(node.condition)

        # If condition is i64, convert to i1 (boolean): nonzero = true
        if cond_value.type == self.i64:
            cond_value = self.builder.icmp_signed(
                "!=", cond_value, ir.Constant(self.i64, 0)
            )
        elif cond_value.type != ir.IntType(1):
            cond_value = self.builder.trunc(cond_value, ir.IntType(1))

        # Create the basic blocks
        then_block = self.current_function.append_basic_block("if.then")
        else_block = self.current_function.append_basic_block("if.else")
        merge_block = self.current_function.append_basic_block("if.merge")

        # Branch based on condition
        self.builder.cbranch(cond_value, then_block, else_block)

        # ── Generate THEN block ───────────────────────────────────────
        self.builder.position_at_start(then_block)
        for stmt in node.then_body:
            self._generate_statement(stmt)
        if not self.builder.block.is_terminated:
            self.builder.branch(merge_block)

        # ── Generate ELSE block ───────────────────────────────────────
        self.builder.position_at_start(else_block)
        for stmt in node.else_body:
            self._generate_statement(stmt)
        if not self.builder.block.is_terminated:
            self.builder.branch(merge_block)

        # ── Continue in MERGE block ───────────────────────────────────
        self.builder.position_at_start(merge_block)

    def _gen_loop(self, node: LoopStatement):
        """
        Generate code for: loop N times { body }

        This is implemented as a while-loop pattern:

            %counter = alloca i64
            store i64 0, %counter         ; counter = 0
            %limit = <evaluate N>
            br label %loop.cond

        loop.cond:
            %i = load %counter
            %cmp = icmp slt %i, %limit    ; i < N?
            br i1 %cmp, %loop.body, %loop.end

        loop.body:
            <body statements>
            %next = add %i, 1             ; i++
            store %next, %counter
            br label %loop.cond

        loop.end:
        """
        # Evaluate the loop count
        limit = self._generate_expression(node.count)
        if limit.type != self.i64:
            limit = self.builder.zext(limit, self.i64)

        # Create the counter variable
        counter = self.builder.alloca(self.i64, name="loop.counter")
        self.builder.store(ir.Constant(self.i64, 0), counter)

        # Create the loop blocks
        cond_block = self.current_function.append_basic_block("loop.cond")
        body_block = self.current_function.append_basic_block("loop.body")
        end_block = self.current_function.append_basic_block("loop.end")

        # Jump to the condition check
        self.builder.branch(cond_block)

        # ── Condition block: check if counter < limit ─────────────────
        self.builder.position_at_start(cond_block)
        current_count = self.builder.load(counter, name="i")
        cmp = self.builder.icmp_signed("<", current_count, limit, name="loop.cmp")
        self.builder.cbranch(cmp, body_block, end_block)

        # ── Body block: execute loop body and increment counter ───────
        self.builder.position_at_start(body_block)
        for stmt in node.body:
            self._generate_statement(stmt)

        # Increment counter: i = i + 1
        if not self.builder.block.is_terminated:
            current_count = self.builder.load(counter)
            next_count = self.builder.add(current_count, ir.Constant(self.i64, 1))
            self.builder.store(next_count, counter)
            self.builder.branch(cond_block)

        # ── End block: continue after the loop ────────────────────────
        self.builder.position_at_start(end_block)

    def _gen_give(self, node: GiveStatement):
        """
        Generate code for: give expression

        LLVM IR: ret i64 <value>
        """
        value = self._generate_expression(node.value)
        if value.type != self.i64:
            value = self.builder.zext(value, self.i64)
        self.builder.ret(value)

    def _gen_func_call(self, node: FuncCall) -> ir.Value:
        """
        Generate code for: func_name(arg1, arg2, ...)

        LLVM IR: %result = call i64 @func_name(i64 %arg1, i64 %arg2)
        """
        if node.name not in self.functions:
            raise CodeGenError(f"Undefined function: '{node.name}'")

        llvm_func = self.functions[node.name]

        # Generate code for each argument
        args = []
        for arg in node.args:
            val = self._generate_expression(arg)
            if val.type != self.i64:
                val = self.builder.zext(val, self.i64)
            args.append(val)

        return self.builder.call(llvm_func, args)

    # ─────────────────────────────────────────────────────────────────────
    # EXPRESSION GENERATION
    # ─────────────────────────────────────────────────────────────────────

    def _generate_expression(self, node: ASTNode) -> ir.Value:
        """Dispatch to the appropriate expression generation method."""

        if isinstance(node, NumberLiteral):
            return ir.Constant(self.i64, node.value)

        if isinstance(node, StringLiteral):
            # Strings in expressions — return a pointer to the global string
            return self._create_global_string(node.value)

        if isinstance(node, Identifier):
            ptr = self._get_variable(node.name)
            return self.builder.load(ptr, name=node.name)

        if isinstance(node, BinaryOp):
            return self._gen_binary_op(node)

        if isinstance(node, UnaryOp):
            return self._gen_unary_op(node)

        if isinstance(node, FuncCall):
            return self._gen_func_call(node)

        raise CodeGenError(f"Unknown expression node type: {type(node).__name__}")

    def _gen_binary_op(self, node: BinaryOp) -> ir.Value:
        """
        Generate code for binary operations: +, -, *, /, %, >, <, >=, <=, ==, !=

        Arithmetic ops produce i64 values.
        Comparison ops produce i1 (boolean) values.
        """
        left = self._generate_expression(node.left)
        right = self._generate_expression(node.right)

        # Ensure both operands are i64
        if left.type != self.i64:
            left = self.builder.zext(left, self.i64)
        if right.type != self.i64:
            right = self.builder.zext(right, self.i64)

        # ── Arithmetic operations ─────────────────────────────────────
        if node.op == "+":
            return self.builder.add(left, right, name="addtmp")
        elif node.op == "-":
            return self.builder.sub(left, right, name="subtmp")
        elif node.op == "*":
            return self.builder.mul(left, right, name="multmp")
        elif node.op == "/":
            return self.builder.sdiv(left, right, name="divtmp")
        elif node.op == "%":
            return self.builder.srem(left, right, name="modtmp")

        # ── Comparison operations ─────────────────────────────────────
        # These return i1 (1-bit boolean): 1 for true, 0 for false
        elif node.op == ">":
            return self.builder.icmp_signed(">", left, right, name="cmptmp")
        elif node.op == "<":
            return self.builder.icmp_signed("<", left, right, name="cmptmp")
        elif node.op == ">=":
            return self.builder.icmp_signed(">=", left, right, name="cmptmp")
        elif node.op == "<=":
            return self.builder.icmp_signed("<=", left, right, name="cmptmp")
        elif node.op == "==":
            return self.builder.icmp_signed("==", left, right, name="cmptmp")
        elif node.op == "!=":
            return self.builder.icmp_signed("!=", left, right, name="cmptmp")

        raise CodeGenError(f"Unknown operator: '{node.op}'")

    def _gen_unary_op(self, node: UnaryOp) -> ir.Value:
        """
        Generate code for unary operations.
        Currently only negation: -x becomes 0 - x
        """
        operand = self._generate_expression(node.operand)
        if operand.type != self.i64:
            operand = self.builder.zext(operand, self.i64)

        if node.op == "-":
            return self.builder.sub(ir.Constant(self.i64, 0), operand, name="negtmp")

        raise CodeGenError(f"Unknown unary operator: '{node.op}'")
