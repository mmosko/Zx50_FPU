; ==============================================================================
; CONV_U32_F32 & CONV_I32_F32: Integer to IEEE-754 Single-Precision Float
;
; CONV_U32_F32 (0xC4): Unsigned 32-bit uint to IEEE-754 single float.
; CONV_I32_F32 (0xCC): Signed 32-bit int to IEEE-754 single float.
;
; Inputs:
;   Stack: TOS = 32-bit integer X
;
; Outputs:
;   Stack: TOS = IEEE-754 single-precision float (in-place, net 0 bytes on stack)
;   Status flags:
;     ZERO = 1 if float is +0.0 or -0.0
;     SIGN = sign of float (bit 31)
;     CARRY = 0
;     OVERFLOW = 0
;     ERR = 1 on Stack Underflow (< 4 bytes)
;
; Register Allocation:
;   AL : Operand X / mantissa / packed float output
;   AH : Sign carrier (AH[31])
;   EA : Exponent (initialized to 150 = 127 + 23)
;   B, C : Used by NORMALIZE_F32 (BL = shift count, C = LZC)
;   D, F : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_32, NORMALIZE_F32
; ==============================================================================

USER_CONV_U32_F32:
    CALL POP_ONE_32             ; AL <- X (TOS), halts on underflow
    LDI AH, 0                   ; Positive sign: AH[31] = 0
    JMP CONV_INT_F32_COMMON

USER_CONV_I32_F32:
    CALL POP_ONE_32             ; AL <- X (TOS), halts on underflow
    MOV AH, AL                  ; AH[31] <- sign of X
    OR AL, AL                   ; Test sign bit
    JZ SIGN, CONV_INT_F32_COMMON ; If non-negative, skip negation (AH[31] is 0)
    NOT AL
    ADD AL, 1                   ; AL <- |X| (two's complement magnitude)

CONV_INT_F32_COMMON:
    LDI EA, 150                 ; Initial biased exponent for bit 23: 127 + 23 = 150
    CALL NORMALIZE_F32          ; Normalize mantissa in AL, EA, sign in AH[31]
    HALT AL                     ; Push IEEE-754 single float
