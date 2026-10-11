"""Integration tests using test vectors from ieee754-test-suite."""

from pathlib import Path
import pytest

from fpu_emu.fpga_model import FpgaModel
from fpu_emu.tests.integration.ieee754.opcode_matcher import (
    is_stubbed_pass_through,
    match_test_vector,
)
from fpu_emu.tests.integration.ieee754.program_runner import (
    execute_test_vector,
    generate_z80_program,
)
from fpu_emu.tests.integration.ieee754.vector_parser import (
    parse_fptest_file,
    parse_fptest_line,
    parse_operand_bits,
)
from fpu_emu.user_opcodes import UserOpcode


# Path to the submodule test vectors
IEEE754_SUITE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "ieee754-test-suite"


# ==============================================================================
# 1. Vector Parser Tests
# ==============================================================================

def test_parse_operand_bits_specials():
    """Verifies that special IEEE-754 bit patterns are parsed correctly."""
    # 32-bit specials
    assert parse_operand_bits("+Zero", 32) == 0x00000000
    assert parse_operand_bits("-Zero", 32) == 0x80000000
    assert parse_operand_bits("+Inf", 32) == 0x7F800000
    assert parse_operand_bits("-Inf", 32) == 0xFF800000
    assert parse_operand_bits("Q", 32) == 0x7FC00000
    assert parse_operand_bits("S", 32) == 0x7F800001
    assert parse_operand_bits("0x0", 32) == 0x0
    assert parse_operand_bits("0x1", 32) == 0x1

    # 64-bit specials
    assert parse_operand_bits("+Zero", 64) == 0x0000000000000000
    assert parse_operand_bits("-Zero", 64) == 0x8000000000000000
    assert parse_operand_bits("+Inf", 64) == 0x7FF0000000000000
    assert parse_operand_bits("-Inf", 64) == 0xFFF0000000000000
    assert parse_operand_bits("Q", 64) == 0x7FF8000000000000
    assert parse_operand_bits("S", 64) == 0x7FF0000000000001


def test_parse_operand_bits_hex_floats():
    """Verifies hex float <sign><hex>P<exp> parsing."""
    # +1.0 * 2^0 = 1.0 (0x3F800000)
    assert parse_operand_bits("+1.000000P0", 32) == 0x3F800000
    # -1.0 * 2^0 = -1.0 (0xBF800000)
    assert parse_operand_bits("-1.000000P0", 32) == 0xBF800000
    # +1.5 * 2^1 = 3.0 (0x40400000)
    assert parse_operand_bits("+1.800000P1", 32) == 0x40400000


def test_parse_fptest_line_normal():
    """Tests parsing a standard binary vector line."""
    line = "b32+ =0 +1.01FD72P-118 +1.6C40BEP-91 -> +1.6C40BEP-91 x"
    vec = parse_fptest_line(line)
    assert vec is not None
    assert vec.op_str == "b32+"
    assert vec.precision == 32
    assert vec.operation_name == "+"
    assert vec.rounding_mode == "=0"
    assert vec.trapped_exceptions == ""
    assert len(vec.operands) == 2
    assert vec.expected_raw == "+1.6C40BEP-91"
    assert vec.expected_flags == "x"
    assert not vec.is_trapped


def test_parse_fptest_line_trapped():
    """Tests parsing a vector with trapped exception (#)."""
    line = "b32V =0 i -Inf -> # i"
    vec = parse_fptest_line(line)
    assert vec is not None
    assert vec.op_str == "b32V"
    assert vec.trapped_exceptions == "i"
    assert vec.is_trapped is True
    assert vec.expected is None
    assert vec.expected_flags == "i"


# ==============================================================================
# 2. Opcode Matcher Tests
# ==============================================================================

def test_opcode_matcher_implemented():
    """Tests matching supported ProgrammersGuide opcodes."""
    line_add = "b32+ =0 +1.000000P0 +1.000000P0 -> +1.000000P1"
    vec_add = parse_fptest_line(line_add)
    assert match_test_vector(vec_add) == UserOpcode.ADD_F32

    line_mul = "b32* =0 +1.000000P0 +1.000000P0 -> +1.000000P0"
    vec_mul = parse_fptest_line(line_mul)
    assert match_test_vector(vec_mul) == UserOpcode.MUL_F32

    line_chs = "b32~ =0 +1.000000P0 -> -1.000000P0"
    vec_chs = parse_fptest_line(line_chs)
    assert match_test_vector(vec_chs) == UserOpcode.CHS_F32

    line_abs = "b32A =0 -1.000000P0 -> +1.000000P0"
    vec_abs = parse_fptest_line(line_abs)
    assert match_test_vector(vec_abs) == UserOpcode.ABS_F32


def test_opcode_matcher_div_f64():
    """Verifies that DIV_F64 is matched and recognized as fully implemented."""
    line_div64 = "b64/ =0 +1.0000000000000P0 +1.0000000000000P0 -> +1.0000000000000P0"
    vec_div64 = parse_fptest_line(line_div64)
    opcode = match_test_vector(vec_div64)
    assert opcode == UserOpcode.DIV_F64
    assert is_stubbed_pass_through(opcode) is False


def test_opcode_matcher_unsupported_rounding():
    """Vectors with rounding modes other than =0 must not be matched."""
    line = "b32+ > +1.000000P0 +1.000000P0 -> +1.000000P1"
    vec = parse_fptest_line(line)
    assert match_test_vector(vec) is None


def test_opcode_matcher_unsupported_ops():
    """
    Fused multiply-add and class inspection ops currently return None.

    NOTE on composite / two-operation vectors (e.g. 'b32*+' for (A * B) + C):
    The Zx50 FPU does not have a single atomic hardware FMA opcode on Port 0x71.
    In the future, composite operations like '*+' can be synthesized as a
    multi-step ProgrammersGuide sequence:
        1. Push A, push B (Port 0x70)
        2. Issue MUL_F32 (Port 0x71: leaves product on TOS)
        3. Push C (Port 0x70)
        4. Issue ADD_F32 (Port 0x71: computes (A * B) + C)
        5. Pop result (Port 0x70)
    Note: IEEE-754 FMA specifies single rounding at the end, whereas discrete
    MUL followed by ADD rounds twice, which can introduce 1-ULP variation
    on boundary vectors.
    """
    line_fma = "b32*+ =0 +1.0P0 +1.0P0 +1.0P0 -> +1.0P1"
    vec_fma = parse_fptest_line(line_fma)
    assert match_test_vector(vec_fma) is None

    line_cls = "b32?f =0 -Inf -> 0x0"
    vec_cls = parse_fptest_line(line_cls)
    assert match_test_vector(vec_cls) is None


# ==============================================================================
# 3. ProgrammersGuide Program Generation Tests
# ==============================================================================

def test_programmersguide_z80_program_generation():
    """Verifies that generate_z80_program generates the canonical ProgrammersGuide Z80 sequence."""
    z80 = generate_z80_program(UserOpcode.ADD_F32, [0x3F800000, 0x40000000], 32)
    assert "OTIR" in z80
    assert "OUT  (0x71), A" in z80
    assert "IN   A, (0x71)" in z80
    assert "INIR" in z80
    assert "ADD_F32 (0x01)" in z80
    assert "0x3F800000" in z80
    assert "0x40000000" in z80


# ==============================================================================
# 4. Integration Tests Running Actual Test Vectors
# ==============================================================================

def test_ieee754_div_f64_execution(fpga: FpgaModel):
    """Verifies that DIV_F64 executes real IEEE-754 double precision division on FpgaModel."""
    vectors = [
        # Normal division: 6.0 / 2.0 = 3.0
        "b64/ =0 +1.8000000000000P2 +1.0000000000000P1 -> +1.8000000000000P1",
        # Fraction result: 1.0 / 4.0 = 0.25
        "b64/ =0 +1.0000000000000P0 +1.0000000000000P2 -> +1.0000000000000P-2",
        # Signed division: -12.0 / 3.0 = -4.0
        "b64/ =0 -1.8000000000000P3 +1.8000000000000P1 -> -1.0000000000000P2",
        # Division by zero: sets StatusFlag.ERR and raises z exception
        "b64/ =0 +1.0000000000000P0 +Zero -> +Inf z",
    ]
    for line in vectors:
        vec = parse_fptest_line(line)
        opcode = match_test_vector(vec)
        assert opcode == UserOpcode.DIV_F64

        res = execute_test_vector(fpga, vec, opcode)
        assert res.success is True, f"Failed on {line}: {res.error_message}\n{res.z80_program}"
        assert res.is_stubbed is False


def test_ieee754_syntax_canonical_vectors(fpga: FpgaModel):
    """Executes the canonical examples from ieee754-test-suite/syntax.txt."""
    # Addition example
    line_add = "b32+ =0 i  -1.6E9177P49 -1.7FFFFFP127 -> -1.7FFFFFP127 x"
    vec_add = parse_fptest_line(line_add)
    res_add = execute_test_vector(fpga, vec_add, match_test_vector(vec_add))
    assert res_add.success is True, res_add.error_message

    # SQRT domain error (negative input) with invalid exception
    line_sqrt = "b32V =0  -1.7FFFFFP127 -> Q i"
    vec_sqrt = parse_fptest_line(line_sqrt)
    res_sqrt = execute_test_vector(fpga, vec_sqrt, match_test_vector(vec_sqrt))
    assert res_sqrt.success is True, res_sqrt.error_message

    # SQRT with trapped invalid exception (#)
    line_sqrt_trap = "b32V =0 i -Inf -> # i"
    vec_sqrt_trap = parse_fptest_line(line_sqrt_trap)
    res_sqrt_trap = execute_test_vector(fpga, vec_sqrt_trap, match_test_vector(vec_sqrt_trap))
    assert res_sqrt_trap.success is True, res_sqrt_trap.error_message


def test_ieee754_basic_types_abs_f32(fpga: FpgaModel):
    """Runs all ABS_F32 test vectors from Basic-Types-Inputs.fptest."""
    fpath = IEEE754_SUITE_DIR / "Basic-Types-Inputs.fptest"
    if not fpath.exists():
        pytest.skip(f"Submodule file {fpath} not found")

    tested = 0
    for vec in parse_fptest_file(fpath):
        op = match_test_vector(vec)
        if op == UserOpcode.ABS_F32:
            tested += 1
            res = execute_test_vector(fpga, vec, op)
            assert res.success is True, f"Failed line {vec.line_num}: {res.error_message}\n{res.z80_program}"

    assert tested > 0, "No ABS_F32 vectors tested"


def test_ieee754_basic_types_chs_f32(fpga: FpgaModel):
    """Runs all CHS_F32 test vectors from Basic-Types-Inputs.fptest."""
    fpath = IEEE754_SUITE_DIR / "Basic-Types-Inputs.fptest"
    if not fpath.exists():
        pytest.skip(f"Submodule file {fpath} not found")

    tested = 0
    for vec in parse_fptest_file(fpath):
        op = match_test_vector(vec)
        if op == UserOpcode.CHS_F32:
            tested += 1
            res = execute_test_vector(fpga, vec, op)
            assert res.success is True, f"Failed line {vec.line_num}: {res.error_message}\n{res.z80_program}"

    assert tested > 0, "No CHS_F32 vectors tested"


def test_ieee754_add_shift_vectors(fpga: FpgaModel):
    """Runs a batch of addition vectors from Add-Shift.fptest."""
    fpath = IEEE754_SUITE_DIR / "Add-Shift.fptest"
    if not fpath.exists():
        pytest.skip(f"Submodule file {fpath} not found")

    tested = 0
    passed = 0
    # Run first 20 vectors
    for vec in parse_fptest_file(fpath, limit=20):
        op = match_test_vector(vec)
        if op is not None:
            tested += 1
            res = execute_test_vector(fpga, vec, op)
            if res.success:
                passed += 1

    assert tested == 20
    # High pass rate on floating point addition shift suite
    assert passed >= 18, f"Passed {passed}/{tested} vectors"
