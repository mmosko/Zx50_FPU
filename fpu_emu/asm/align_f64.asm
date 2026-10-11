; ==============================================================================
; ALIGN_F64: Subroutine to align exponents of two unpacked float64 operands
;
; Inputs:
;   AX (64-bit) : Unpacked mantissa of operand A {AH, AL}
;   BX (64-bit) : Unpacked mantissa of operand B {BH, BL}
;   EA (12-bit) : Biased exponent of operand A
;   EB (12-bit) : Biased exponent of operand B
;   DX (64-bit) : Packed operand A (DH[31] holds sign of A)
;   FX (64-bit) : Packed operand B (FH[31] holds sign of B)
;
; Outputs:
;   AX (64-bit) : Unpacked mantissa of operand with larger magnitude
;   BX (64-bit) : Aligned unpacked mantissa of operand with smaller magnitude
;   EA (12-bit) : Common exponent (larger of original EA, EB)
;   EB (12-bit) : Exponent of smaller operand (original EA if swapped)
;   DX (64-bit) : Packed larger operand (DH[31] is the result sign)
;   FX (64-bit) : Scratch (clobbered by SWAP AX, BX hardware staging)
;   CL (32-bit) : Exponent difference (EA - EB)
;   Status flags:
;     DIFF_SIGN (DF) is preserved from UNPACK
;
; Size Reduction: Down from 20 words to 15 words (5 words saved)
; ==============================================================================

ALIGN_F64:
    CMP     EA, EB
    JNZ     CARRY, ALIGN_F64_SWAP  ; EA < EB: swap operands so larger is in A
    JNZ     ZERO, ALIGN_F64_EXP    ; EA > EB: A is already larger
    CMP     AX, BX                 ; 64-bit mantissa comparison (2 cycles)
    JZ      CARRY, ALIGN_F64_EXP   ; EA == EB, AX >= BX: A is larger

ALIGN_F64_SWAP:
    MOV     DX, FX                 ; DX <- packed larger operand (sign in DH[31]) before FX clobber
    SWAP    AX, BX                 ; Swap mantissas (uses FX as hardware staging)
    SWAP    EA, EB                 ; Swap 12-bit exponents (EA <-> EB)

ALIGN_F64_EXP:
    SUB     CL, EA, EB             ; CL <- EA - EB (32-bit register prevents 6-bit truncation)
    CMP     CL, 54                 ; If diff >= 54, smaller 53-bit mantissa underflows
    JNZ     CARRY, ALIGN_F64_SHIFT ; If diff < 54, perform shift
    XOR     BX, BX                 ; Smaller mantissa underflows to 0
    RET

ALIGN_F64_SHIFT:
    LSR     BX, CL                 ; Align smaller mantissa: BX >>= (EA - EB)
    RET
