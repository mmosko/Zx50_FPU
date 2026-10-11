"""Parser for IEEE-754 test suite (.fptest) vector files."""

from dataclasses import dataclass
from pathlib import Path
import struct
from typing import Iterator, List, Optional, Union


@dataclass
class TestVector:
    """Represents a single parsed IEEE-754 test vector."""
    op_str: str              # e.g., "b32+", "b64*", "b32V"
    precision: int           # 32 or 64
    operation_name: str      # e.g., "+", "-", "*", "/", "V", "~", "A", "b64cff"
    rounding_mode: str       # e.g., "=0", "0", ">", "<", "=^"
    trapped_exceptions: str  # e.g., "i", "x", "oz", or ""
    operands_raw: List[str]  # Raw string operands
    operands: List[int]      # Decoded IEEE-754 bit representations (uint32 or uint64)
    expected_raw: str        # e.g., "+1.6C40BEP-91", "#", "Q", "+Zero"
    expected: Optional[int]  # Decoded expected bit representation, or None if '#'
    expected_flags: str      # Result exception flags: "x", "u", "o", "z", "i", ""
    is_trapped: bool         # True if output is '#' (trapped invalid)
    raw_line: str
    source_file: str = ""
    line_num: int = 0


def parse_operand_bits(token: str, precision: int = 32) -> int:
    """Converts a vector operand string into raw 32-bit or 64-bit IEEE-754 bits."""
    token = token.strip()
    if precision == 32:
        if token in ("+Zero", "Zero", "+0", "+0.0"):
            return 0x00000000
        if token in ("-Zero", "-0", "-0.0"):
            return 0x80000000
        if token in ("+Inf", "Inf"):
            return 0x7F800000
        if token == "-Inf":
            return 0xFF800000
        if token == "Q":
            return 0x7FC00000
        if token == "S":
            return 0x7F800001
        if token.startswith("0x"):
            return int(token, 16) & 0xFFFFFFFF
    else:  # 64-bit
        if token in ("+Zero", "Zero", "+0", "+0.0"):
            return 0x0000000000000000
        if token in ("-Zero", "-0", "-0.0"):
            return 0x8000000000000000
        if token in ("+Inf", "Inf"):
            return 0x7FF0000000000000
        if token == "-Inf":
            return 0xFFF0000000000000
        if token == "Q":
            return 0x7FF8000000000000
        if token == "S":
            return 0x7FF0000000000001
        if token.startswith("0x"):
            return int(token, 16) & 0xFFFFFFFFFFFFFFFF

    if token.startswith(("+", "-")):
        sign, rest = token[0], token[1:]
    else:
        sign, rest = "+", token

    hex_str = f"{sign}0x{rest}"
    try:
        val = float.fromhex(hex_str)
    except OverflowError:
        if precision == 32:
            return 0xFF800000 if sign == "-" else 0x7F800000
        else:
            return 0xFFF0000000000000 if sign == "-" else 0x7FF0000000000000

    if precision == 32:
        return struct.unpack(">I", struct.pack(">f", val))[0]
    else:
        return struct.unpack(">Q", struct.pack(">d", val))[0]


def parse_fptest_line(line: str, source_file: str = "", line_num: int = 0) -> Optional[TestVector]:
    """Parses a single line from an IEEE-754 .fptest file into a TestVector."""
    line = line.strip()
    if not line or "->" not in line or line.startswith(("-", "Floating", "Copyright")):
        return None

    lhs_str, rhs_str = line.split("->")
    lhs = lhs_str.split()
    rhs = rhs_str.split()

    if len(lhs) < 2 or not rhs:
        return None

    op_str = lhs[0]
    rounding_mode = lhs[1]

    # Precision extraction: e.g. b32+ -> 32, b64* -> 64
    if op_str.startswith("b32"):
        precision = 32
        op_name = op_str[3:]
    elif op_str.startswith("b64"):
        precision = 64
        op_name = op_str[3:]
    else:
        # Unsupported format (e.g. d64, d128, b128)
        return None

    # Check for trapped exception string
    # Trapped exceptions consist solely of characters in "xuvwozi"
    idx = 2
    trapped_exceptions = ""
    if len(lhs) > 2 and all(c in "xuvwozi" for c in lhs[2]):
        trapped_exceptions = lhs[2]
        idx = 3

    operands_raw = lhs[idx:]
    try:
        operands = [parse_operand_bits(op, precision) for op in operands_raw]
    except Exception:
        return None

    expected_raw = rhs[0]
    expected_flags = rhs[1] if len(rhs) > 1 else ""
    is_trapped = (expected_raw == "#")

    expected: Optional[int] = None
    if not is_trapped:
        try:
            expected = parse_operand_bits(expected_raw, precision)
        except Exception:
            expected = None

    return TestVector(
        op_str=op_str,
        precision=precision,
        operation_name=op_name,
        rounding_mode=rounding_mode,
        trapped_exceptions=trapped_exceptions,
        operands_raw=operands_raw,
        operands=operands,
        expected_raw=expected_raw,
        expected=expected,
        expected_flags=expected_flags,
        is_trapped=is_trapped,
        raw_line=line,
        source_file=source_file,
        line_num=line_num,
    )


def parse_fptest_file(file_path: Union[str, Path], limit: Optional[int] = None) -> Iterator[TestVector]:
    """Streams parsed TestVector instances from a .fptest file."""
    path = Path(file_path)
    count = 0
    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
        for line_num, line in enumerate(fp, 1):
            vec = parse_fptest_line(line, source_file=path.name, line_num=line_num)
            if vec is not None:
                yield vec
                count += 1
                if limit is not None and count >= limit:
                    break
