from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp


def test_micro_instruction_round_trip():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=19, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=13, clock=clock)

    # Encode ADD AL, BL
    orig = MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src2=Reg.BL, imm=0)
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.ADD
    assert decoded.w == IW.W32
    assert decoded.dst == Reg.AL
    assert decoded.src2 == Reg.BL
    assert decoded.src1 == Reg.NONE


def test_micro_instruction_jump_with_flag():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=19, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=13, clock=clock)

    # Encode JNZ with StatusFlag.UNDERFLOW and imm=42
    orig = MicroInstruction(
        op=MicroOp.JNZ,
        w=IW.W32,
        dst=StatusFlag.UNDERFLOW,
        imm=42,
    )
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.JNZ
    assert decoded.dst == StatusFlag.UNDERFLOW
    assert imm_reg.read_int() == 42


def test_micro_instruction_three_address_round_trip():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=19, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=13, clock=clock)

    # Encode EXP_SUB C, EA, EB (C <- EA - EB)
    orig = MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.C, src1=Reg.EA, src2=Reg.EB)
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.EXP_SUB
    assert decoded.dst == Reg.C
    assert decoded.src1 == Reg.EA
    assert decoded.src2 == Reg.EB


def test_micro_instruction_set_flag_round_trip():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=19, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=13, clock=clock)

    # Encode SET ERR, 1: dst=StatusFlag.ERR, src1=Reg.IMM, imm=1
    orig = MicroInstruction(
        op=MicroOp.SET,
        dst=StatusFlag.ERR,
        src1=Reg.IMM,
        imm=1,
    )
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.SET
    assert decoded.dst == StatusFlag.ERR
    assert decoded.src1 == Reg.IMM
    assert imm_reg.read_int() == 1


def test_micro_instruction_ldc_immediate_round_trip():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=19, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=13, clock=clock)

    # Encode LDC AL, CONST, PI_F32 (imm=0)
    from fpu_emu.rom.fpu_const_map import FpuTable, FpuConst
    orig = MicroInstruction(
        op=MicroOp.LDC,
        dst=Reg.AL,
        src1=FpuTable.CONST,
        src2=Reg.IMM,
        imm=FpuConst.PI_F32,
    )
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.LDC
    assert decoded.dst == Reg.AL
    assert decoded.src1 == FpuTable.CONST
    assert decoded.src2 == Reg.IMM
    assert imm_reg.read_int() == FpuConst.PI_F32


def test_micro_instruction_ldc_dynamic_reg_round_trip():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=19, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=13, clock=clock)

    # Encode LDC AH, SQRT, C
    from fpu_emu.rom.fpu_const_map import FpuTable
    orig = MicroInstruction(
        op=MicroOp.LDC,
        dst=Reg.AH,
        src1=FpuTable.SQRT,
        src2=Reg.C,
    )
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.LDC
    assert decoded.dst == Reg.AH
    assert decoded.src1 == FpuTable.SQRT
    assert decoded.src2 == Reg.C


def test_micro_instruction_to_bytes_little_endian():
    # ADD AL, BL (W=0, DST=AL(0), SRC1=NONE(15), SRC2=BL(2), IMM=0)
    # Word: (0 << 26) | (0 << 25) | (0 << 21) | (15 << 17) | (2 << 13) | 0
    #     = 0x00000000 | 0x001E0000 | 0x00004000 = 0x001E4000
    # Little-endian stores lowest byte at address 0: [0x00, 0x40, 0x1E, 0x00]
    inst = MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src2=Reg.BL)
    raw = inst.to_bytes()
    assert len(raw) == 4
    assert raw == bytes([0x00, 0x40, 0x1E, 0x00])


def test_micro_instruction_to_bytes_bit_fields():
    # Construct an instruction exercising all fields:
    # JNZ dst=UNDERFLOW(2), imm=42 (0x2A)
    # OPCODE = JNZ (25 = 0b011001) -> 25 << 26 = 0x64000000
    # W = 0
    # DST = StatusFlag.UNDERFLOW (2) -> 2 << 21 = 0x00400000
    # SRC1 = Reg.NONE (15) -> 15 << 17 = 0x001E0000
    # SRC2 = Reg.NONE (15) -> 15 << 13 = 0x0001E000
    # IMM = 42 -> 0x0000002A
    # Sum = 0x645FE02A
    # In little-endian: [0x2A, 0xE0, 0x5F, 0x64]
    inst = MicroInstruction(
        op=MicroOp.JNZ,
        w=IW.W32,
        dst=StatusFlag.UNDERFLOW,
        imm=42,
    )
    assert inst.to_int() == 0x645FE02A
    assert inst.to_bytes() == bytes([0x2A, 0xE0, 0x5F, 0x64])


def test_micro_instruction_to_bytes_three_operand_and_w64():
    # SUB.64 DL, AL, BL
    # OPCODE = SUB (2 = 0b000010) -> 2 << 26 = 0x08000000
    # W = 1 -> 1 << 25 = 0x02000000
    # DST = DL (6) -> 6 << 21 = 0x00C00000
    # SRC1 = AL (0) -> 0 << 17 = 0
    # SRC2 = BL (2) -> 2 << 13 = 0x00004000
    # IMM = 0
    # Expected word: 0x0AC04000
    # In little-endian: [0x00, 0x40, 0xC0, 0x0A]
    inst = MicroInstruction(
        op=MicroOp.SUB,
        w=IW.W64,
        dst=Reg.DL,
        src1=Reg.AL,
        src2=Reg.BL,
    )
    assert inst.to_int() == 0x0AC04000
    assert inst.to_bytes() == bytes([0x00, 0x40, 0xC0, 0x0A])


def test_micro_instruction_round_trip_bytes():
    from fpu_emu.rom.fpu_const_map import FpuTable, FpuConst

    test_cases = [
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src2=Reg.BL),
        MicroInstruction(op=MicroOp.SUB, w=IW.W64, dst=Reg.DL, src1=Reg.AL, src2=Reg.BL),
        MicroInstruction(op=MicroOp.JNZ, dst=StatusFlag.UNDERFLOW, imm=1023),
        MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.C, src1=Reg.EA, src2=Reg.EB),
        MicroInstruction(op=MicroOp.SET, dst=StatusFlag.ERR, src1=Reg.IMM, imm=1),
        MicroInstruction(op=MicroOp.LDC, dst=Reg.FL, src1=FpuTable.CONST, src2=Reg.IMM, imm=FpuConst.PI_F32),
        MicroInstruction(op=MicroOp.LDC, dst=Reg.AH, src1=FpuTable.SQRT, src2=Reg.C),
        MicroInstruction(op=MicroOp.HALT),
        MicroInstruction(op=MicroOp.PUSH, src2=Reg.FL),
        MicroInstruction(op=MicroOp.POP, w=IW.W64, dst=Reg.DL),
    ]

    for orig in test_cases:
        encoded = orig.to_bytes()
        assert len(encoded) == 4
        decoded = MicroInstruction.from_bytes(encoded)
        assert decoded.op == orig.op
        assert decoded.w == orig.w
        assert decoded.dst == orig.dst
        assert decoded.src2 == orig.src2
        assert decoded.src1 == orig.src1
        assert decoded.imm == (orig.imm & 0x1FFF)


def test_micro_instruction_emit_bin_rom_image():
    from fpu_emu.rom.fpu_const_map import FpuTable, FpuConst

    # Emulate a small routine: PUSH_PI_32
    routine = [
        MicroInstruction(op=MicroOp.LDC, dst=Reg.FL, src1=FpuTable.CONST, src2=Reg.IMM, imm=FpuConst.PI_F32),
        MicroInstruction(op=MicroOp.PUSH, src2=Reg.FL),
        MicroInstruction(op=MicroOp.HALT),
    ]

    # Emit binary ROM image (4 bytes per instruction in little-endian order)
    rom_bin = b"".join(inst.to_bytes() for inst in routine)
    assert len(rom_bin) == 3 * 4  # 12 bytes

    # Read back binary ROM image word by word
    recovered = []
    for offset in range(0, len(rom_bin), 4):
        chunk = rom_bin[offset : offset + 4]
        recovered.append(MicroInstruction.from_bytes(chunk))

    assert len(recovered) == 3
    assert recovered[0].op == MicroOp.LDC
    assert recovered[0].dst == Reg.FL
    assert recovered[0].src1 == FpuTable.CONST
    assert recovered[0].imm == FpuConst.PI_F32
    assert recovered[1].op == MicroOp.PUSH
    assert recovered[1].src2 == Reg.FL
    assert recovered[2].op == MicroOp.HALT


def test_micro_instruction_from_bytes_invalid_length():
    import pytest

    with pytest.raises(ValueError, match="MicroInstruction requires at least 4 bytes"):
        MicroInstruction.from_bytes(b"\x00\x01\x02")


def test_status_flags_bit_encoding_roundtrip():
    expected_flags = [
        (StatusFlag.ZERO, 0),
        (StatusFlag.DIFF_SIGN, 1),
        (StatusFlag.UNDERFLOW, 2),
        (StatusFlag.OVERFLOW, 3),
        (StatusFlag.CARRY, 4),
        (StatusFlag.SIGN, 5),
        (StatusFlag.ERR, 6),
        (StatusFlag.BUSY, 7),
    ]
    for flag, expected_val in expected_flags:
        assert flag.value == expected_val
        inst = MicroInstruction(op=MicroOp.JNZ, dst=flag, imm=0)
        word = inst.to_int()
        # DST/FLAG is at [24:21]
        flag_in_word = (word >> 21) & 0x0F
        assert flag_in_word == expected_val
        recovered = MicroInstruction.from_int(word)
        assert recovered.dst == flag





