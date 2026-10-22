# ─────────────────────────────────────
# Simple Calculator in LiteScript
# ─────────────────────────────────────

# Define calculator operations
func add(a, b) {
    give a + b
}

func subtract(a, b) {
    give a - b
}

func multiply(a, b) {
    give a * b
}

func divide(a, b) {
    give a / b
}

func modulo(a, b) {
    give a % b
}

func square(n) {
    give n * n
}

func power(base, exp) {
    if exp <= 0 {
        give 1
    }
    give base * power(base, exp - 1)
}

# ─────────────────────────────────────
# Run the calculator
# ─────────────────────────────────────

let x = 24
let y = 6

say "=============================="
say "  LiteScript Calculator"
say "=============================="

say "  Numbers: 24 and 6"
say ""

say "  Addition:       24 + 6 ="
say add(x, y)

say "  Subtraction:    24 - 6 ="
say subtract(x, y)

say "  Multiplication: 24 * 6 ="
say multiply(x, y)

say "  Division:       24 / 6 ="
say divide(x, y)

say "  Modulo:         24 % 6 ="
say modulo(x, y)

say ""
say "=============================="
say "  Bonus Operations"
say "=============================="

say "  Square of 9 ="
say square(9)

say "  2 ^ 10 ="
say power(2, 10)

say "  (24 + 6) * (24 - 6) ="
say (x + y) * (x - y)

say ""
say "=============================="
