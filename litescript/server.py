"""
server.py — Web Server for LiteScript Playground
==================================================

A Flask-based web server that provides a browser IDE for writing,
compiling, and executing LiteScript programs.

Run:
    python server.py

Then open: http://localhost:5000
"""

import sys
import os
import io
import traceback
from contextlib import redirect_stdout, redirect_stderr

from flask import Flask, request, jsonify, send_from_directory

# Add the current directory to path so we can import compiler modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lexer import Lexer
from parser import Parser, ParseError
from codegen import CodeGenerator, CodeGenError
from compiler import LiteScriptCompiler, CompileError

app = Flask(__name__, static_folder="web", static_url_path="")


@app.route("/")
def index():
    """Serve the main IDE page."""
    return send_from_directory("web", "index.html")


@app.route("/calculator")
def calculator():
    """Serve the calculator page."""
    return send_from_directory("web", "calculator.html")


@app.route("/api/run", methods=["POST"])
def run_code():
    """
    Compile and JIT-execute LiteScript code.
    Returns the program's stdout output.

    We run the code in a subprocess so that C-level printf output
    from the LLVM JIT engine is naturally captured via stdout pipe.
    """
    import subprocess
    import tempfile

    data = request.get_json()
    source = data.get("code", "")

    if not source.strip():
        return jsonify({"success": False, "error": "No code provided."})

    try:
        # Write source to a temp file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        tmp_path = os.path.join(script_dir, "_tmp_run.ls")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(source)

        # Run via main.py in a subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(script_dir, "main.py"), tmp_path],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=script_dir,
        )

        # Clean up temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass

        if result.returncode == 0:
            return jsonify({"success": True, "output": result.stdout})
        else:
            error = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            return jsonify({"success": False, "error": error})

    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Execution timed out (10s limit)"})
    except Exception as e:
        return jsonify({"success": False, "error": f"{type(e).__name__}: {e}"})


@app.route("/api/ir", methods=["POST"])
def emit_ir():
    """
    Compile LiteScript code and return the LLVM IR.
    """
    data = request.get_json()
    source = data.get("code", "")

    if not source.strip():
        return jsonify({"success": False, "error": "No code provided."})

    try:
        compiler = LiteScriptCompiler()
        ir_text = compiler.compile_to_ir(source)
        return jsonify({"success": True, "ir": ir_text})

    except SyntaxError as e:
        return jsonify({"success": False, "error": f"Syntax Error: {e}"})
    except ParseError as e:
        return jsonify({"success": False, "error": f"Parse Error: {e}"})
    except CodeGenError as e:
        return jsonify({"success": False, "error": f"Code Generation Error: {e}"})
    except Exception as e:
        return jsonify({"success": False, "error": f"{type(e).__name__}: {e}"})


@app.route("/api/tokens", methods=["POST"])
def get_tokens():
    """
    Tokenize LiteScript code and return the token list.
    Useful for learning/debugging.
    """
    data = request.get_json()
    source = data.get("code", "")

    if not source.strip():
        return jsonify({"success": False, "error": "No code provided."})

    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        token_list = [
            {"type": t.type.name, "value": t.value, "line": t.line, "col": t.column}
            for t in tokens
        ]
        return jsonify({"success": True, "tokens": token_list})

    except SyntaxError as e:
        return jsonify({"success": False, "error": f"Syntax Error: {e}"})
    except Exception as e:
        return jsonify({"success": False, "error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    print("=" * 50)
    print("  LiteScript Playground")
    print("  Open: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
