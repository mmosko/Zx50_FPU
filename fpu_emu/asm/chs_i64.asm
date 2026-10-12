; ==============================================================================
; CHS_I64: 64-bit integer negation (-X = 0 - X)
;
; Inputs:
;   Stack: TOS = 64-bit integer X
;
; Outputs:
;   Stack: TOS = -X (mod 2^64)
;   Status flags:
;     Updated by SUB AX, FX, AX (ZERO, SIGN, CARRY, OVERFLOW)
;
; Register Allocation:
;   AX (AL, AH) : Operand X, later negated result
;   FX (FL, FH) : Scratch for 0
;   B, D, C     : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_64
; ==============================================================================

USER_CHS_I64:
    CALL POP_ONE_64             ; AX <- X (TOS)
    XOR FX, FX                  ; FX <- 0
    SUB AX, FX, AX              ; AX <- 0 - X = -X
    HALT AX                     ; Push negated result
