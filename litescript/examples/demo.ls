# ─────────────────────────────────────────────────
# LiteScript Demo — All Language Features
# ─────────────────────────────────────────────────

# 1. Variables and Arithmetic
say "=== Variables & Arithmetic ==="
let a = 10
let b = 3
say a + b
say a - b
say a * b
say a / b
say a % b

# 2. String output
say "=== Strings ==="
say "Hello from LiteScript!"

# 3. Comparisons and Conditionals
say "=== If/Else ==="
let score = 85

if score >= 90 {
    say "Grade: A"
} else {
    say "Grade: B or lower"
}

if score > 50 {
    say "You passed!"
}

# 4. Loops
say "=== Loops ==="
loop 5 times {
    say "Looping!"
}

# 5. Functions
say "=== Functions ==="

func square(n) {
    give n * n
}

func max(x, y) {
    if x > y {
        give x
    } else {
        give y
    }
}

func factorial(n) {
    if n <= 1 {
        give 1
    }
    give n * factorial(n - 1)
}

say square(7)
say max(42, 17)
say factorial(5)

# 6. Nested expressions
say "=== Nested Expressions ==="
let result = (2 + 3) * (10 - 4)
say result

# 7. Negation
say "=== Unary Negation ==="
let neg = -42
say neg

say "=== Done! ==="
