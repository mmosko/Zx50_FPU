; ==============================================================================
; CONV_F32_I32: Convert IEEE-754 single float to signed 32-bit integer
;
; Inputs:
;   Stack: TOS = IEEE-754 single float X
;
; Outputs:
;   Stack: TOS = signed 32-bit integer Y (net 0 bytes on stack)
;   Status flags:
;     ZERO = 1 if result == 0, else 0
;     SIGN = result[31]
;     CARRY = 0
;     OVERFLOW = 1 if |X| >= 2^31 or X is NaN/+/-Inf
;     ERR = 1 on Stack Underflow (< 4 bytes) or range overflow
;
; Register Allocation:
;   AL : Top of stack float X, mantissa, and converted integer result
;   AH : Copy of original float X (AH[31] holds sign)
;   EA : Float biased exponent E (0..255)
;   BL : Scratch for fraction zero-check on -2^31 boundary
;   C  : Dynamic shift count (150 - EA or EA - 150)
; ==============================================================================

USER_CONV_F32_I32:
    CALL POP_ONE_32             ; AL <- float X (TOS), halts on underflow
    MOV AH, AL                  ; AH[31] <- sign of float
    UNPACK AL, EA               ; EA <- exponent, AL <- mantissa (hidden bit at bit 23)

    ; Check for NaN or +/-Infinity (EA == 255)
    CMP EA, 255
    JZ ZERO, CONV_F32_I32_OVF

    ; Check for |X| < 1.0 (EA < 127) or X == 0
    CMP EA, 127
    JNZ CARRY, CONV_F32_I32_ZERO

    ; Check for |X| >= 2^31 (EA >= 158)
    CMP EA, 158
    JZ CARRY, CONV_F32_I32_LARGE

    ; Here EA in [127, 157]
    CMP EA, 151
    JNZ CARRY, CONV_F32_I32_RSHIFT

    ; Here EA in [151, 157]: shift left by (EA - 150)
    MOV C, EA
    SUB C, 150
    LSL AL, C
    JMP CONV_F32_I32_SIGN

CONV_F32_I32_RSHIFT:
    ; Here EA in [127, 150]: shift right by (150 - EA)
    LDI C, 150
    SUB C, EA
    LSR AL, C

CONV_F32_I32_SIGN:
    OR AH, AH
    JZ SIGN, CONV_F32_I32_DONE  ; If positive, done
    NOT AL
    ADD AL, 1                   ; Two's complement negation

CONV_F32_I32_DONE:
    OR AL, AL                   ; Sets SIGN, ZERO, clears CARRY and OVERFLOW
    HALT AL

CONV_F32_I32_ZERO:
    XOR AL, AL                  ; AL <- 0
    JMP CONV_F32_I32_DONE

CONV_F32_I32_LARGE:
    CMP EA, 158
    JNZ ZERO, CONV_F32_I32_OVF  ; If EA > 158, overflow!
    OR AH, AH
    JZ SIGN, CONV_F32_I32_OVF   ; If positive, +2^31 overflows!
    MOV BL, AL
    LSL BL, 9                   ; Shift out hidden bit 23
    JNZ ZERO, CONV_F32_I32_OVF  ; If fraction != 0, |-X| > 2^31 -> overflow!
    LDI AL, 1
    LSL AL, 31                  ; AL <- 0x80000000 (-2147483648)
    JMP CONV_F32_I32_DONE

CONV_F32_I32_OVF:
    LDI AL, 1
    LSL AL, 31                  ; AL <- 0x80000000
    OR AH, AH
    JNZ SIGN, CONV_F32_I32_SET_ERR ; If negative, clamp to 0x80000000
    SUB AL, 1                   ; If positive, clamp to 0x7FFFFFFF
CONV_F32_I32_SET_ERR:
    OR AL, AL                   ; Sets SIGN, ZERO, clears CARRY
    LDI OVERFLOW, 1             ; Assert OVERFLOW=1
    LDI ERR, 1                  ; Assert ERR=1
    HALT AL                     ; Push clamped result to stack and halt
