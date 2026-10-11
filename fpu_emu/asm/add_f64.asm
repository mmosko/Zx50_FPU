; ==============================================================================
; ADD_F64: IEEE-754 Double-Precision Floating-Point Addition (A + B)
;
; Inputs:
;   Stack (64-bit): TOS = 64-bit float B, NOS = 64-bit float A
;
; Outputs:
;   Stack (64-bit): TOS = 64-bit float (A + B)
;   Status flags:
;     Updated by NORMALIZE_F64 (ZERO, SIGN, OVERFLOW, UNDERFLOW, INEXACT)
;
; Register Allocation:
;   AX (AL, AH) : Operand A / final result (64-bit)
;   BX (BL, BH) : Operand B (64-bit)
;   CX (CL, CH) : Scratch for swap in ALIGN_F64 / exponent diff in CL
;   DX (DL, DH) : Packed operand A / larger operand (DH[31] holds result sign)
;   FX (FL, FH) : Packed operand B (preserved for zero returns and operand swap)
;   EA, EB      : Exponents of A and B (12-bit)
;
; Subroutines Called:
;   POP_TWO_64, ALIGN_F64, NORMALIZE_F64
; ==============================================================================

USER_ADD_F64:
    CALL POP_TWO_64                     ; AX <- A (NOS), BX <- B (TOS)
    CALL ADD_F64_CORE                   ; AX <- A + B
    PUSH AX                             ; Push 64-bit result
    HALT

ADD_F64_CORE:
    MOV FX, BX                          ; Scratch FX <- packed B (preserves sign and value)
    MOV DX, AX                          ; DX <- packed A (preserves sign of A in DH[31])
    UNPACK BX, EB                       ; Unpack B: EB <- exp_B, BX <- mant_B
    JZ ZERO, ADD_F64_RETURN_A           ; If B == 0: return A
    UNPACK AX, EA                       ; Unpack A: EA <- exp_A, AX <- mant_A
    JZ ZERO, ADD_F64_RETURN_B           ; If A == 0: return B

    CALL ALIGN_F64                      ; Align exponents: larger in AX/EA, smaller in BX/EB, sign in DH[31]
    JNZ DIFF_SIGN, ADD_F64_SUB          ; If signs differ: subtract mantissas
    ADD AX, AX, BX                      ; Same sign: add mantissas
    JMP ADD_F64_NORM

ADD_F64_SUB:
    SUB AX, AX, BX                      ; Different signs: subtract smaller mantissa from larger

ADD_F64_NORM:
    CALL NORMALIZE_F64                  ; Normalize mantissa in AX with exponent in EA, sign in DH[31]

ADD_F64_RETURN_A:
    RET

ADD_F64_RETURN_B:
    MOV AX, FX                          ; AX <- original B
    RET
