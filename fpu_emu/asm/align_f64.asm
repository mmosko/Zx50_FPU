; ==============================================================================
; ALIGN_F64: Subroutine to align exponents of two unpacked float64 operands
;
; Compares exponents EA and EB. If EB > EA (or if EA == EB and mantissa B > mantissa A),
; swaps operands A and B (including packed sign carriers in DX and FX) so that operand A
; holds the larger magnitude operand. Then shifts the smaller operand mantissa BX right
; by (EA - EB) bit positions. If (EA - EB) >= 54, the smaller mantissa completely
; underflows to 0.
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
;   CL (32-bit) : Exponent difference (EA - EB)
;
; Register Allocation:
;   AX, BX      : Mantissas (AX = larger, BX = aligned smaller)
;   CX (CL, CH) : CX used as 64-bit scratch for swap; CL holds 32-bit exponent diff
;   DX          : Packed larger operand (sign carrier)
;   FX          : Packed smaller operand
;   EA, EB      : Exponents (EA = larger, EB = smaller)
; ==============================================================================

ALIGN_F64:
    CMP EA, EB
    JNZ CARRY, ALIGN_F64_SWAP           ; If EA < EB: swap operands so larger is in A
    JNZ ZERO, ALIGN_F64_EXP             ; If EA > EB: A is already larger
    CMP AH, BH
    JNZ CARRY, ALIGN_F64_SWAP           ; If EA == EB and AH < BH: swap
    JNZ ZERO, ALIGN_F64_EXP             ; If EA == EB and AH > BH: A is larger
    CMP AL, BL
    JZ CARRY, ALIGN_F64_EXP             ; If EA == EB and AH == BH and AL >= BL: A is larger

ALIGN_F64_SWAP:
    MOV CX, AX                          ; CX <- AX
    MOV AX, BX                          ; AX <- BX
    MOV BX, CX                          ; BX <- CX
    SWAP EA, EB                         ; Larger exponent into EA
    MOV DX, FX                          ; DX holds packed larger operand (sign in DH[31])

ALIGN_F64_EXP:
    SUB CL, EA, EB                      ; CL <- EA - EB (exponent difference in 32-bit register)
    CMP CL, 54
    JNZ CARRY, ALIGN_F64_SHIFT          ; If diff < 54: perform shift
    XOR BX, BX                          ; If diff >= 54: smaller mantissa underflows to 0
    RET

ALIGN_F64_SHIFT:
    LSR BX, CL                          ; Align smaller mantissa: BX >>= (EA - EB)
    RET
