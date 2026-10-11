; ==============================================================================
; CONV_I32_I64: Sign-extend 32-bit signed integer to 64-bit signed integer
;
; Inputs:
;   Stack: TOS = 32-bit signed integer X
;
; Outputs:
;   Stack: TOS = 64-bit signed integer Y = X
;   Status flags:
;     ZERO = 1 if X == 0, else 0
;     SIGN = X[31]
;     CARRY = 0
;     OVERFLOW = 0
;     ERR = 1 on Stack Underflow or Stack Overflow
;
; Register Allocation:
;   AX (AL, AH) : Operand X (TOS), later 64-bit result {AH, AL}
;   B, D, F     : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_32
; ==============================================================================

USER_CONV_I32_I64:
    CALL POP_ONE_32             ; AL <- X (TOS), halts on stack underflow
    MOV AH, AL                  ; AX <- {AL, AL}
    ASR AX, 32                  ; AX <- sign_extend(X); sets S and Z
    OR AX, AX                   ; Clears C=0 and V=0, reaffirms S and Z
    PUSH AX                     ; Push 64-bit result {AH, AL}
    HALT
