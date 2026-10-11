; ==============================================================================
; CONV_U32_U64: Zero-extend 32-bit unsigned integer to 64-bit unsigned integer
;
; Inputs:
;   Stack: TOS = 32-bit unsigned integer X
;
; Outputs:
;   Stack: TOS = 64-bit unsigned integer Y = {0x00000000, X} (net +4 bytes on stack)
;   Status flags:
;     ZERO = 1 if X == 0, else 0
;     SIGN = 0 (bit 63 is always 0)
;     CARRY = 0
;     OVERFLOW = 0
;     ERR = 1 on Stack Underflow (< 4 bytes) or Stack Overflow (SP=127)
;
; Register Allocation:
;   AX (AL, AH) : AL = popped 32-bit operand X, AH = 0x00000000
;   BX, C, D, F : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_32
; ==============================================================================

USER_CONV_U32_U64:
    CALL POP_ONE_32             ; AL <- X (TOS), halts on stack underflow
    LDI AH, 0                   ; Zero-extend high word: AH <- 0x00000000
    OR AX, AX                   ; 64-bit OR: sets ZERO=(X==0), SIGN=0, CARRY=0, OVERFLOW=0
    PUSH AX                     ; Push 64-bit result {AH, AL}
    HALT
