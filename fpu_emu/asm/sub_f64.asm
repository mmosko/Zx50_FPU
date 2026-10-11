; ==============================================================================
; SUB_F64: IEEE-754 Double-Precision Floating-Point Subtraction (A - B)
;
; Operation:
;   A - B = A + (-B)
;
; Inputs:
;   Stack (64-bit): TOS = float64 B, NOS = float64 A
;
; Outputs:
;   Stack (64-bit): TOS = float64 (A - B)
;   Status flags:
;     Updated by NORMALIZE_F64 (ZERO, SIGN, OVERFLOW, UNDERFLOW, INEXACT)
;
; Register Allocation:
;   AX (AL, AH) : Operand A (NOS), later result (64-bit)
;   BX (BL, BH) : Operand B (TOS), inverted via FCHS BX (BH[31] ^= 1)
;   Shares all registers and logic with ADD_F64_CORE.
;
; Subroutines Called:
;   POP_TWO_64, ADD_F64_CORE
; ==============================================================================

USER_SUB_F64:
    CALL POP_TWO_64                     ; AX <- A (NOS), BX <- B (TOS)
    CALL SUB_F64_CORE                   ; AX <- A - B
    PUSH AX                             ; Push 64-bit result
    HALT

SUB_F64_CORE:
    FCHS BX                             ; Invert sign bit of subtrahend: B <- -B (BH[31] ^= 1)
    CALL ADD_F64_CORE                   ; Add A + (-B)
    RET
