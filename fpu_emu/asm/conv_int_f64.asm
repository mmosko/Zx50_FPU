; ==============================================================================
; CONV_U64_F64 & CONV_I64_F64: 64-Bit Integer to IEEE-754 Double-Precision Float
;
; CONV_U64_F64 (0xC5): Unsigned 64-bit uint to IEEE-754 double float.
; CONV_I64_F64 (0xCE): Signed 64-bit int to IEEE-754 double float.
;
; Inputs:
;   Stack: TOS = 64-bit integer X {AH, AL}
;
; Outputs:
;   Stack: TOS = IEEE-754 double-precision float {AH, AL} (in-place, net 0 bytes)
;   Status flags:
;     ZERO = 1 if float is +0.0 or -0.0
;     SIGN = sign of float (bit 63)
;     CARRY = 0
;     OVERFLOW = 0
;     ERR = 1 on Stack Underflow (< 8 bytes)
;
; Register Allocation:
;   AX (AL, AH) : 64-bit operand X / mantissa / packed float output
;   DH          : Bit 31 preserves sign, restored to status.SIGN by NORMALIZE_F64
;   EA          : Biased exponent (initialized to 1075 = 1023 + 52)
;   FX          : Zero register for 64-bit negation of negative signed integers
;   B, C        : Used by NORMALIZE_F64 (BL = shift count, C = LZC)
;   D, F        : DH preserves sign
;
; Subroutines Called:
;   POP_ONE_64, NORMALIZE_F64
; ==============================================================================

USER_CONV_U64_F64:
    CALL POP_ONE_64             ; AX <- unsigned 64-bit int from TOS, halts on underflow
    XOR DH, DH                  ; Sign is positive (DH[31] = 0)
    JMP CONV_INT_F64_COMMON

USER_CONV_I64_F64:
    CALL POP_ONE_64             ; AX <- signed 64-bit int from TOS, halts on underflow
    MOV DH, AH                  ; DH[31] <- sign of X
    OR AH, AH                   ; Test sign bit (bit 63 / AH[31])
    JZ SIGN, CONV_INT_F64_COMMON ; If non-negative, skip negation
    XOR FX, FX
    SUB AX, FX, AX              ; AX <- -AX (two's complement 64-bit magnitude)

CONV_INT_F64_COMMON:
    LDI EA, 1075                ; Initial biased exponent for bit 52: 1023 + 52 = 1075
    CALL NORMALIZE_F64          ; Normalize mantissa in AX, EA, sign in DH[31]
    HALT AX                     ; Push IEEE-754 double float
