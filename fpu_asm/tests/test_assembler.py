import pytest

from fpu_asm.assembler import Assembler
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import StatusFlag
from fpu_emu.micro_instruction import IW
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.rom.fpu_const_map import FpuConst, FpuTable


def test_assemble_sample_program():
    code = """
        .org 0x000
    start:
        ADD AL, BL          ; 2-operand 32-bit addition
        ADD AX, BX, DL      ; 3-operand 64-bit addition
        LDC AL, CONST, 0x02 ; Load pi constant
        JNZ ERR, start      ; Conditional jump on error
        HALT
    """
    assembler = Assembler()
    prog = assembler.assemble(code)

    assert isinstance(prog, list)
    assert len(prog) == 5
    assert [addr for addr, _ in prog] == [0, 1, 2, 3, 4]

    prog_dict = dict(prog)

    # [0] ADD AL, BL
    u0 = prog_dict[0]
    assert u0.op == MicroOp.ADD
    assert u0.w == IW.W32
    assert u0.dst == Reg.AL
    assert u0.src == Reg.BL
    assert u0.src1 == Reg.NONE
    assert u0.imm == 0

    # [1] ADD AX, BX, DL (64-bit)
    u1 = prog_dict[1]
    assert u1.op == MicroOp.ADD
    assert u1.w == IW.W64
    assert u1.dst == Reg.AL
    assert u1.src1 == Reg.BL
    assert u1.src == Reg.DL

    # [2] LDC AL, CONST, 0x02
    u2 = prog_dict[2]
    assert u2.op == MicroOp.LDC
    assert u2.w == IW.W32
    assert u2.dst == Reg.AL
    assert u2.src == FpuTable.CONST
    assert u2.imm == 2

    # [3] JNZ ERR, start (start == 0)
    u3 = prog_dict[3]
    assert u3.op == MicroOp.JNZ
    assert u3.flag == StatusFlag.ERR
    assert u3.imm == 0

    # [4] HALT
    u4 = prog_dict[4]
    assert u4.op == MicroOp.HALT


def test_forward_and_backward_labels():
    code = """
        .org 0x010
    loop_start:
        ADD AL, #1
        CMP AL, #10
        JZ ZERO, loop_end
        JMP loop_start
    loop_end:
        RET
    """
    assembler = Assembler()
    prog = assembler.assemble(code)

    assert isinstance(prog, list)
    prog_dict = dict(prog)

    assert prog_dict[0x010].imm == 1
    assert prog_dict[0x010].src == Reg.IMM
    assert prog_dict[0x011].op == MicroOp.CMP
    assert prog_dict[0x011].imm == 10
    # JZ jumps to loop_end (0x014)
    assert prog_dict[0x012].op == MicroOp.JZ
    assert prog_dict[0x012].imm == 0x014
    # JMP jumps to loop_start (0x010)
    assert prog_dict[0x013].op == MicroOp.JMP
    assert prog_dict[0x013].imm == 0x010
    # RET
    assert prog_dict[0x014].op == MicroOp.RET


def test_equ_and_align_directives():
    code = """
        .equ MY_CONST, 42
        .org 0x001
        LDI BL, MY_CONST
        .align 4
    aligned_entry:
        NOP
    """
    assembler = Assembler()
    prog = assembler.assemble(code)

    assert isinstance(prog, list)
    prog_dict = dict(prog)

    assert prog_dict[1].op == MicroOp.LDI
    assert prog_dict[1].dst == Reg.BL
    assert prog_dict[1].imm == 42
    # 0x001 + 1 instruction = address 2, aligned to 4 becomes 4
    assert 4 in prog_dict
    assert prog_dict[4].op == MicroOp.NOP


def test_symbolic_constants():
    code = """
        LDC FL, CONST, PI_F32
        PUSH FL
    """
    assembler = Assembler()
    prog = assembler.assemble(code)

    assert isinstance(prog, list)
    prog_dict = dict(prog)

    assert prog_dict[0].op == MicroOp.LDC
    assert prog_dict[0].src == FpuTable.CONST
    assert prog_dict[0].imm == FpuConst.PI_F32.value
    assert prog_dict[1].op == MicroOp.PUSH
    assert prog_dict[1].src == Reg.FL


def test_undefined_symbol_raises():
    code = """
        JMP non_existent_label
    """
    assembler = Assembler()
    with pytest.raises(Exception):
        assembler.assemble(code)


def test_shift_instructions_assemble():
    code = """
        ASL AL, C
        ASL.64 AL, 1
        ASR BL, C
        ASR.64 AL, 32
    """
    assembler = Assembler()
    prog = assembler.assemble(code)
    prog_dict = dict(prog)

    assert prog_dict[0].op == MicroOp.ASL
    assert prog_dict[0].w == IW.W32
    assert prog_dict[0].dst == Reg.AL
    assert prog_dict[0].src == Reg.C

    assert prog_dict[1].op == MicroOp.ASL
    assert prog_dict[1].w == IW.W64
    assert prog_dict[1].dst == Reg.AL
    assert prog_dict[1].imm == 1

    assert prog_dict[2].op == MicroOp.ASR
    assert prog_dict[2].w == IW.W32
    assert prog_dict[2].dst == Reg.BL
    assert prog_dict[2].src == Reg.C

    assert prog_dict[3].op == MicroOp.ASR
    assert prog_dict[3].w == IW.W64
    assert prog_dict[3].dst == Reg.AL
    assert prog_dict[3].imm == 32


def test_ld_and_sto_instructions_assemble():
    code = """
        LD AL, 12
        LD AL, [C]
        LD.64 AX, 8
        LD.64 AX, [BL]
        STO 12, AL
        STO [C], AL
        STO.64 8, AX
        STO.64 [BL], AX
    """
    assembler = Assembler()
    prog = assembler.assemble(code)
    prog_dict = dict(prog)

    # LD AL, 12
    assert prog_dict[0].op == MicroOp.LD
    assert prog_dict[0].w == IW.W32
    assert prog_dict[0].dst == Reg.AL
    assert prog_dict[0].src1 == Reg.IMM
    assert prog_dict[0].imm == 12

    # LD AL, [C]
    assert prog_dict[1].op == MicroOp.LD
    assert prog_dict[1].w == IW.W32
    assert prog_dict[1].dst == Reg.AL
    assert prog_dict[1].src1 == Reg.C
    assert prog_dict[1].imm == 0

    # LD.64 AX, 8
    assert prog_dict[2].op == MicroOp.LD
    assert prog_dict[2].w == IW.W64
    assert prog_dict[2].dst == Reg.AL
    assert prog_dict[2].src1 == Reg.IMM
    assert prog_dict[2].imm == 8

    # LD.64 AX, [BL]
    assert prog_dict[3].op == MicroOp.LD
    assert prog_dict[3].w == IW.W64
    assert prog_dict[3].dst == Reg.AL
    assert prog_dict[3].src1 == Reg.BL
    assert prog_dict[3].imm == 0

    # STO 12, AL
    assert prog_dict[4].op == MicroOp.STO
    assert prog_dict[4].w == IW.W32
    assert prog_dict[4].src == Reg.AL
    assert prog_dict[4].src1 == Reg.IMM
    assert prog_dict[4].imm == 12

    # STO [C], AL
    assert prog_dict[5].op == MicroOp.STO
    assert prog_dict[5].w == IW.W32
    assert prog_dict[5].src == Reg.AL
    assert prog_dict[5].src1 == Reg.C
    assert prog_dict[5].imm == 0

    # STO.64 8, AX
    assert prog_dict[6].op == MicroOp.STO
    assert prog_dict[6].w == IW.W64
    assert prog_dict[6].src == Reg.AL
    assert prog_dict[6].src1 == Reg.IMM
    assert prog_dict[6].imm == 8

    # STO.64 [BL], AX
    assert prog_dict[7].op == MicroOp.STO
    assert prog_dict[7].w == IW.W64
    assert prog_dict[7].src == Reg.AL
    assert prog_dict[7].src1 == Reg.BL
    assert prog_dict[7].imm == 0


def test_cl_ch_cx_instructions():
    code = """
        MOV CL, AL
        MOV CH, AH
        ADD CX, DX
        ADD CL, CH
        SUB.64 CX, AX, BX
        POP CX
        PUSH CX
    """
    asm = Assembler()
    prog = asm.assemble(code)
    prog_dict = {addr: inst for addr, inst in prog}

    # MOV CL, AL
    assert prog_dict[0].dst == Reg.CL
    assert prog_dict[0].src == Reg.AL

    # MOV CH, AH
    assert prog_dict[1].dst == Reg.CH
    assert prog_dict[1].src == Reg.AH

    # ADD CX, DX
    assert prog_dict[2].op == MicroOp.ADD
    assert prog_dict[2].w == IW.W64
    assert prog_dict[2].dst == Reg.CL
    assert prog_dict[2].src == Reg.DL

    # ADD CL, CH
    assert prog_dict[3].op == MicroOp.ADD
    assert prog_dict[3].w == IW.W32
    assert prog_dict[3].dst == Reg.CL
    assert prog_dict[3].src == Reg.CH

    # SUB.64 CX, AX, BX
    assert prog_dict[4].op == MicroOp.SUB
    assert prog_dict[4].w == IW.W64
    assert prog_dict[4].dst == Reg.CL
    assert prog_dict[4].src1 == Reg.AL
    assert prog_dict[4].src == Reg.BL

    # POP CX
    assert prog_dict[5].op == MicroOp.POP
    assert prog_dict[5].w == IW.W64
    assert prog_dict[5].dst == Reg.CL

    # PUSH CX
    assert prog_dict[6].op == MicroOp.PUSH
    assert prog_dict[6].w == IW.W64
    assert prog_dict[6].src == Reg.CL


def test_stacked_labels():
    code = """
        .org 0x010
    FOO:
    BAR:
    USER_ADD_I32:
    USER_ADD_U32:
        ADD AL, BL
        HALT
    """
    asm = Assembler()
    prog = asm.assemble(code)
    prog_dict = dict(prog)

    assert asm.symbols["FOO"] == 0x010
    assert asm.symbols["BAR"] == 0x010
    assert asm.symbols["USER_ADD_I32"] == 0x010
    assert asm.symbols["USER_ADD_U32"] == 0x010

    assert 0x010 in prog_dict
    assert prog_dict[0x010].op == MicroOp.ADD
    assert 0x011 in prog_dict
    assert prog_dict[0x011].op == MicroOp.HALT


def test_mulu_divu_assembly():
    code = """
        MULU AL, BL
        MULU AX, BX
        DIVU AL, BL
        DIVU AX, BX
    """
    asm = Assembler()
    prog = asm.assemble(code)
    prog_dict = dict(prog)

    # MULU AL, BL
    assert prog_dict[0].op == MicroOp.MULU
    assert prog_dict[0].w == IW.W32
    assert prog_dict[0].dst == Reg.AL
    assert prog_dict[0].src == Reg.BL

    # MULU AX, BX
    assert prog_dict[1].op == MicroOp.MULU
    assert prog_dict[1].w == IW.W64
    assert prog_dict[1].dst == Reg.AL
    assert prog_dict[1].src == Reg.BL

    # DIVU AL, BL
    assert prog_dict[2].op == MicroOp.DIVU
    assert prog_dict[2].w == IW.W32
    assert prog_dict[2].dst == Reg.AL
    assert prog_dict[2].src == Reg.BL

    # DIVU AX, BX
    assert prog_dict[3].op == MicroOp.DIVU
    assert prog_dict[3].w == IW.W64
    assert prog_dict[3].dst == Reg.AL
    assert prog_dict[3].src == Reg.BL


def test_status_flag_encodings():
    code = """
        JZ ZERO, 0x10
        JZ ZF, 0x10
        JZ Z, 0x10
        JZ DIFF_SIGN, 0x10
        JZ DF, 0x10
        JZ D, 0x10
        JZ UNDERFLOW, 0x10
        JZ UF, 0x10
        JZ U, 0x10
        JZ OVERFLOW, 0x10
        JZ VF, 0x10
        JZ V, 0x10
        JZ CARRY, 0x10
        JZ CF, 0x10
        JZ SIGN, 0x10
        JZ SF, 0x10
        JZ S, 0x10
        JZ ERR, 0x10
        JZ EF, 0x10
        JZ BUSY, 0x10
        JZ BF, 0x10
        JZ BSY, 0x10
        LDI ERR, 1
        LDI DF, 0
    """
    asm = Assembler()
    prog = dict(asm.assemble(code))

    # ZERO (0)
    assert prog[0].flag == StatusFlag.ZERO == 0
    assert prog[1].flag == StatusFlag.ZERO == 0
    assert prog[2].flag == StatusFlag.ZERO == 0

    # DIFF_SIGN (1)
    assert prog[3].flag == StatusFlag.DIFF_SIGN == 1
    assert prog[4].flag == StatusFlag.DIFF_SIGN == 1
    assert prog[5].flag == StatusFlag.DIFF_SIGN == 1

    # UNDERFLOW (2)
    assert prog[6].flag == StatusFlag.UNDERFLOW == 2
    assert prog[7].flag == StatusFlag.UNDERFLOW == 2
    assert prog[8].flag == StatusFlag.UNDERFLOW == 2

    # OVERFLOW (3)
    assert prog[9].flag == StatusFlag.OVERFLOW == 3
    assert prog[10].flag == StatusFlag.OVERFLOW == 3
    assert prog[11].flag == StatusFlag.OVERFLOW == 3

    # CARRY (4)
    assert prog[12].flag == StatusFlag.CARRY == 4
    assert prog[13].flag == StatusFlag.CARRY == 4

    # SIGN (5)
    assert prog[14].flag == StatusFlag.SIGN == 5
    assert prog[15].flag == StatusFlag.SIGN == 5
    assert prog[16].flag == StatusFlag.SIGN == 5

    # ERR (6)
    assert prog[17].flag == StatusFlag.ERR == 6
    assert prog[18].flag == StatusFlag.ERR == 6

    # BUSY (7)
    assert prog[19].flag == StatusFlag.BUSY == 7
    assert prog[20].flag == StatusFlag.BUSY == 7
    assert prog[21].flag == StatusFlag.BUSY == 7

    # LDI ERR (6), 1
    assert prog[22].op == MicroOp.LDI
    assert prog[22].flag == StatusFlag.ERR == 6
    assert prog[22].imm == 1

    # LDI DF (1), 0
    assert prog[23].op == MicroOp.LDI
    assert prog[23].flag == StatusFlag.DIFF_SIGN == 1
    assert prog[23].imm == 0


def test_test_instruction_assemble():
    code = """
        TEST AL, BL
        TEST AX, BX
        TEST AL, 0x10
        TEST.64 AL, BL
    """
    assembler = Assembler()
    prog = [u for _, u in assembler.assemble(code)]

    assert prog[0].op == MicroOp.TEST
    assert prog[0].w == IW.W32
    assert prog[0].dst == Reg.AL
    assert prog[0].src == Reg.BL

    assert prog[1].op == MicroOp.TEST
    assert prog[1].w == IW.W64
    assert prog[1].dst == Reg.AL
    assert prog[1].src == Reg.BL

    assert prog[2].op == MicroOp.TEST
    assert prog[2].w == IW.W32
    assert prog[2].dst == Reg.AL
    assert prog[2].src == Reg.IMM
    assert prog[2].imm == 0x10

    assert prog[3].op == MicroOp.TEST
    assert prog[3].w == IW.W64
    assert prog[3].dst == Reg.AL
    assert prog[3].src == Reg.BL


def test_pack_unpack_binary_and_ternary_assemble():
    code = """
        PACK AL, EA
        PACK AL, EA, BL
        PACK AX, EA
        PACK AX, EA, BX
        PACK.64 AL, EA, BL
        UNPACK AL, EA
        UNPACK AL, EA, BL
        UNPACK AX, EA
        UNPACK AX, EA, BX
        UNPACK.64 AL, EA, BL
    """
    assembler = Assembler()
    prog = [u for _, u in assembler.assemble(code)]

    # PACK AL, EA (binary: dst=AL, src1=EA, src=AL)
    assert prog[0].op == MicroOp.PACK
    assert prog[0].w == IW.W32
    assert prog[0].dst == Reg.AL
    assert prog[0].src1 == Reg.EA
    assert prog[0].src == Reg.AL

    # PACK AL, EA, BL (ternary: dst=AL, src1=EA, src=BL)
    assert prog[1].op == MicroOp.PACK
    assert prog[1].w == IW.W32
    assert prog[1].dst == Reg.AL
    assert prog[1].src1 == Reg.EA
    assert prog[1].src == Reg.BL

    # PACK AX, EA (binary 64-bit: dst=AL, src1=EA, src=AL)
    assert prog[2].op == MicroOp.PACK
    assert prog[2].w == IW.W64
    assert prog[2].dst == Reg.AL
    assert prog[2].src1 == Reg.EA
    assert prog[2].src == Reg.AL

    # PACK AX, EA, BX (ternary 64-bit: dst=AL, src1=EA, src=BL)
    assert prog[3].op == MicroOp.PACK
    assert prog[3].w == IW.W64
    assert prog[3].dst == Reg.AL
    assert prog[3].src1 == Reg.EA
    assert prog[3].src == Reg.BL

    # PACK.64 AL, EA, BL (ternary 64-bit: dst=AL, src1=EA, src=BL)
    assert prog[4].op == MicroOp.PACK
    assert prog[4].w == IW.W64
    assert prog[4].dst == Reg.AL
    assert prog[4].src1 == Reg.EA
    assert prog[4].src == Reg.BL

    # UNPACK AL, EA (binary: dst=AL, src1=EA, src=AL)
    assert prog[5].op == MicroOp.UNPACK
    assert prog[5].w == IW.W32
    assert prog[5].dst == Reg.AL
    assert prog[5].src1 == Reg.EA
    assert prog[5].src == Reg.AL

    # UNPACK AL, EA, BL (ternary: dst=AL, src1=EA, src=BL)
    assert prog[6].op == MicroOp.UNPACK
    assert prog[6].w == IW.W32
    assert prog[6].dst == Reg.AL
    assert prog[6].src1 == Reg.EA
    assert prog[6].src == Reg.BL

    # UNPACK AX, EA (binary 64-bit: dst=AL, src1=EA, src=AL)
    assert prog[7].op == MicroOp.UNPACK
    assert prog[7].w == IW.W64
    assert prog[7].dst == Reg.AL
    assert prog[7].src1 == Reg.EA
    assert prog[7].src == Reg.AL

    # UNPACK AX, EA, BX (ternary 64-bit: dst=AL, src1=EA, src=BL)
    assert prog[8].op == MicroOp.UNPACK
    assert prog[8].w == IW.W64
    assert prog[8].dst == Reg.AL
    assert prog[8].src1 == Reg.EA
    assert prog[8].src == Reg.BL

    # UNPACK.64 AL, EA, BL (ternary 64-bit: dst=AL, src1=EA, src=BL)
    assert prog[9].op == MicroOp.UNPACK
    assert prog[9].w == IW.W64
    assert prog[9].dst == Reg.AL
    assert prog[9].src1 == Reg.EA
    assert prog[9].src == Reg.BL


def test_logic_unary_and_binary_assemble():
    code = """
        FABS AL
        FABS AL, BL
        FABS AX
        FABS AX, BX
        FCHS AL
        FCHS AL, BL
        FCHS AX
        FCHS AX, BX
        NOT AL
        NOT AL, BL
        NOT AX
        NOT AX, BX
        FCHS.64 AL, BL
    """
    assembler = Assembler()
    prog = [u for _, u in assembler.assemble(code)]

    assert prog[0].op == MicroOp.FABS
    assert prog[0].w == IW.W32
    assert prog[0].dst == Reg.AL
    assert prog[0].src1 == Reg.NONE

    assert prog[1].op == MicroOp.FABS
    assert prog[1].w == IW.W32
    assert prog[1].dst == Reg.AL
    assert prog[1].src1 == Reg.BL

    assert prog[2].op == MicroOp.FABS
    assert prog[2].w == IW.W64
    assert prog[2].dst == Reg.AL
    assert prog[2].src1 == Reg.NONE

    assert prog[3].op == MicroOp.FABS
    assert prog[3].w == IW.W64
    assert prog[3].dst == Reg.AL
    assert prog[3].src1 == Reg.BL

    assert prog[4].op == MicroOp.FCHS
    assert prog[4].w == IW.W32
    assert prog[4].dst == Reg.AL
    assert prog[4].src1 == Reg.NONE

    assert prog[5].op == MicroOp.FCHS
    assert prog[5].w == IW.W32
    assert prog[5].dst == Reg.AL
    assert prog[5].src1 == Reg.BL

    assert prog[6].op == MicroOp.FCHS
    assert prog[6].w == IW.W64
    assert prog[6].dst == Reg.AL
    assert prog[6].src1 == Reg.NONE

    assert prog[7].op == MicroOp.FCHS
    assert prog[7].w == IW.W64
    assert prog[7].dst == Reg.AL
    assert prog[7].src1 == Reg.BL

    assert prog[8].op == MicroOp.NOT
    assert prog[8].w == IW.W32
    assert prog[8].dst == Reg.AL
    assert prog[8].src1 == Reg.NONE

    assert prog[9].op == MicroOp.NOT
    assert prog[9].w == IW.W32
    assert prog[9].dst == Reg.AL
    assert prog[9].src1 == Reg.BL

    assert prog[10].op == MicroOp.NOT
    assert prog[10].w == IW.W64
    assert prog[10].dst == Reg.AL
    assert prog[10].src1 == Reg.NONE

    assert prog[11].op == MicroOp.NOT
    assert prog[11].w == IW.W64
    assert prog[11].dst == Reg.AL
    assert prog[11].src1 == Reg.BL

    assert prog[12].op == MicroOp.FCHS
    assert prog[12].w == IW.W64
    assert prog[12].dst == Reg.AL
    assert prog[12].src1 == Reg.BL


def test_ternary_shift_assemble():
    code = """
        LSL AL
        LSL AL, C
        LSL AL, 8
        LSL AL, C, BL
        LSL AL, 8, BL
        LSL AX, C, BX
        ASL AX, 4, BX
        ASR BL, C, DL
    """
    assembler = Assembler()
    prog = [u for _, u in assembler.assemble(code)]

    # Unary: LSL AL (count = C)
    assert prog[0].op == MicroOp.LSL
    assert prog[0].w == IW.W32
    assert prog[0].dst == Reg.AL
    assert prog[0].src == Reg.C

    # Binary: LSL AL, C
    assert prog[1].op == MicroOp.LSL
    assert prog[1].w == IW.W32
    assert prog[1].dst == Reg.AL
    assert prog[1].src == Reg.C

    # Binary imm: LSL AL, 8
    assert prog[2].op == MicroOp.LSL
    assert prog[2].w == IW.W32
    assert prog[2].dst == Reg.AL
    assert prog[2].src == Reg.IMM
    assert prog[2].imm == 8

    # Ternary reg count: LSL AL, C, BL
    assert prog[3].op == MicroOp.LSL
    assert prog[3].w == IW.W32
    assert prog[3].dst == Reg.AL
    assert prog[3].src1 == Reg.C
    assert prog[3].src == Reg.BL

    # Ternary imm count: LSL AL, 8, BL
    assert prog[4].op == MicroOp.LSL
    assert prog[4].w == IW.W32
    assert prog[4].dst == Reg.AL
    assert prog[4].src1 == Reg.IMM
    assert prog[4].src == Reg.BL
    assert prog[4].imm == 8

    # Ternary 64-bit reg count: LSL AX, C, BX
    assert prog[5].op == MicroOp.LSL
    assert prog[5].w == IW.W64
    assert prog[5].dst == Reg.AL
    assert prog[5].src1 == Reg.C
    assert prog[5].src == Reg.BL

    # Ternary 64-bit imm count: ASL AX, 4, BX
    assert prog[6].op == MicroOp.ASL
    assert prog[6].w == IW.W64
    assert prog[6].dst == Reg.AL
    assert prog[6].src1 == Reg.IMM
    assert prog[6].src == Reg.BL
    assert prog[6].imm == 4

    # Ternary reg count: ASR BL, C, DL
    assert prog[7].op == MicroOp.ASR
    assert prog[7].w == IW.W32
    assert prog[7].dst == Reg.BL
    assert prog[7].src1 == Reg.C
    assert prog[7].src == Reg.DL


def test_swap_64_assemble():
    code = """
        SWAP AL, BL
        SWAP AX, BX
        SWAP.64 AL, BL
    """
    assembler = Assembler()
    prog = [u for _, u in assembler.assemble(code)]

    assert prog[0].op == MicroOp.SWAP
    assert prog[0].w == IW.W32
    assert prog[0].dst == Reg.AL
    assert prog[0].src == Reg.BL

    assert prog[1].op == MicroOp.SWAP
    assert prog[1].w == IW.W64
    assert prog[1].dst == Reg.AL
    assert prog[1].src == Reg.BL

    assert prog[2].op == MicroOp.SWAP
    assert prog[2].w == IW.W64
    assert prog[2].dst == Reg.AL
    assert prog[2].src == Reg.BL


def test_halt_syntax_variants():
    code = """
        HALT
        HALT AL
        HALT AX
        HALT.64 AX
        HALT.32 AL
    """
    assembler = Assembler()
    prog = [u for _, u in assembler.assemble(code)]

    assert len(prog) == 5

    # HALT (no args)
    assert prog[0].op == MicroOp.HALT
    assert prog[0].w == IW.W32
    assert prog[0].src1 == Reg.NONE

    # HALT AL
    assert prog[1].op == MicroOp.HALT
    assert prog[1].w == IW.W32
    assert prog[1].src1 == Reg.AL

    # HALT AX (inferred 64-bit)
    assert prog[2].op == MicroOp.HALT
    assert prog[2].w == IW.W64
    assert prog[2].src1 == Reg.AL

    # HALT.64 AX
    assert prog[3].op == MicroOp.HALT
    assert prog[3].w == IW.W64
    assert prog[3].src1 == Reg.AL

    # HALT.32 AL
    assert prog[4].op == MicroOp.HALT
    assert prog[4].w == IW.W32
    assert prog[4].src1 == Reg.AL



