; ==============================================================================
; CONV_F64_I64: Convert IEEE-754 double float to signed 64-bit integer
;
; Opcode: 0xCF
;
; Inputs:
;   Stack: TOS = IEEE-754 double-precision float X {AH, AL}
;
; Outputs:
;   Stack: TOS = signed 64-bit integer Y {AH, AL} (net 0 bytes on stack)
;   Status flags:
;     ZERO = 1 if result == 0, else 0
;     SIGN = result[63] (bit 31 of AH)
;     CARRY = 0
;     OVERFLOW = 1 if |X| >= 2^63 (except exact -2^63) or X is NaN/+/-Inf
;     ERR = 1 on Stack Underflow (< 8 bytes) or range overflow
;
; Register Allocation:
;   AX (AL, AH) : Float X in, mantissa, and converted 64-bit integer out
;   DH          : Bit 31 preserves sign of original float X
;   EA          : Float biased exponent (0..2047)
;   EB          : Unbiased exponent E = EA - 1023
;   BX          : Scratch for fraction zero-check on -2^63 boundary
;   C           : Dynamic shift count / zero check accumulator
;   FX          : Zero register for 64-bit negation
;
; Subroutines Called:
;   POP_ONE_64
; ==============================================================================

USER_CONV_F64_I64:
    CALL POP_ONE_64             ; AX <- float64 X (TOS), halts on underflow
    MOV DH, AH                  ; DH[31] <- sign of X
    UNPACK AX, EA               ; EA <- exponent, AX <- mantissa (bit 52 set), sets ZERO, SIGN
    JZ ZERO, CONV_F64_I64_ZERO  ; If X == +/-0.0, return 0

    EXP_SUB EB, EA, 1023        ; EB <- EA - 1023 (unbiased exponent)
    JNZ SIGN, CONV_F64_I64_ZERO ; If EB < 0 (i.e. |X| < 1.0), return 0

    CMP EB, 63
    JZ CARRY, CONV_F64_I64_LARGE ; If EB >= 63, check boundary or overflow

    ; 0 <= EB <= 62: fits in int64
    CMP EB, 52
    JNZ CARRY, CONV_F64_I64_RSHIFT

    ; 52 <= EB <= 62: shift left by (EB - 52)
    MOV C, EB
    SUB C, 52
    LSL AX, C
    JMP CONV_F64_I64_SIGN

CONV_F64_I64_RSHIFT:
    ; 0 <= EB < 52: shift right by (52 - EB)
    LDI C, 52
    SUB C, EB
    LSR AX, C

CONV_F64_I64_SIGN:
    OR DH, DH                   ; Test original sign bit
    JZ SIGN, CONV_F64_I64_DONE  ; If positive, done
    XOR FX, FX
    SUB AX, FX, AX              ; AX <- -AX (two's complement)

CONV_F64_I64_DONE:
    OR AX, AX                   ; Sets SIGN, ZERO, clears CARRY & OVERFLOW
    HALT AX

CONV_F64_I64_ZERO:
    XOR AX, AX                  ; AX <- 0
    JMP CONV_F64_I64_DONE

CONV_F64_I64_LARGE:
    ; EB >= 63
    CMP EB, 63
    JNZ ZERO, CONV_F64_I64_OVF  ; If EB > 63, definite overflow!
    ; Here EB == 63 (2^63 <= |X| < 2^64)
    OR DH, DH
    JZ SIGN, CONV_F64_I64_OVF   ; If positive, +2^63 overflows!
    ; Negative: check if fraction bits [51:0] are zero
    MOV BX, AX
    LSL BX, 12                  ; Clear bit 52..63
    MOV C, BH
    OR C, BL
    JNZ ZERO, CONV_F64_I64_OVF  ; If fraction != 0, |-X| > 2^63 -> overflow!
    ; Exactly -2^63 (0x8000000000000000)
    LDI AH, 1
    LSL AH, 31                  ; AH <- 0x80000000
    XOR AL, AL                  ; AX <- 0x8000000000000000
    JMP CONV_F64_I64_DONE

CONV_F64_I64_OVF:
    ; Overflow clamp: 0x8000000000000000 (neg) or 0x7FFFFFFFFFFFFFFF (pos)
    LDI AH, 1
    LSL AH, 31                  ; AH <- 0x80000000
    XOR AL, AL                  ; AX <- 0x8000000000000000
    OR DH, DH
    JNZ SIGN, CONV_F64_I64_SET_ERR ; If negative, clamp to 0x8000000000000000
    ; Positive: clamp to 0x7FFFFFFFFFFFFFFF
    SUB AH, 1                   ; AH <- 0x7FFFFFFF
    SUB AL, 1                   ; AL <- 0xFFFFFFFF
CONV_F64_I64_SET_ERR:
    OR AX, AX                   ; Sets flags
    SET OVERFLOW, 1
    SET ERR, 1
    HALT AX
