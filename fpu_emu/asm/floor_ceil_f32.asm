; ==============================================================================
; FLOOR_F32 & CEIL_F32: IEEE-754 Single-Precision Rounding Operations
;
; Opcode 0x61: FLOOR_F32 (x -- floor(x))
; Opcode 0x69: CEIL_F32  (x -- ceil(x))
;
; Inputs:
;   Stack: TOS = IEEE-754 single float X
; Outputs:
;   Stack: TOS = IEEE-754 single float Y (net 0 bytes on stack)
;   Status flags:
;     ZERO = 1 if result == 0 (+/-0.0), else 0
;     SIGN = result[31]
;     CARRY = 0
;     OVERFLOW = 0
;     ERR = 1 on Stack Underflow (< 4 bytes)
;
; Register Allocation:
;   AL : Float X, unpacked mantissa, packed result Y
;   AH : Original float X (AH[31] holds sign)
;   EA : Exponent (0..255)
;   BL : Scratch for shift/mask and bit-24 overflow check
;   C  : Shift count K = 150 - EA, scratch mask test
;   DL : Direction flag: 0 for FLOOR, 1 for CEIL; later (1 << K) increment
;   DH : Saved rounding increment condition (D != S)
; ==============================================================================

USER_FLOOR_F32:
    LDI DL, 0
    JMP COMMON_ROUND_F32

USER_CEIL_F32:
    LDI DL, 1

COMMON_ROUND_F32:
    CALL POP_ONE_32             ; AL <- float X (TOS), halts on underflow
    MOV AH, AL                  ; AH <- original float X
    UNPACK AL, EA               ; EA <- exponent, AL <- mantissa, sets ZERO, SIGN

    JZ ZERO, ROUND_F32_ZERO     ; If X == +/-0.0, return X unchanged (ZERO=1, SIGN=S)

    CMP EA, 150
    JZ CARRY, ROUND_F32_NO_FRAC ; If EA >= 150, return X (already integer or inf/nan)

    ; Extract sign bit from AH into BL
    MOV BL, AH
    LSR BL, 31                  ; BL <- S (0 or 1)
    XOR BL, DL                  ; BL <- S ^ D (0 if D == S, 1 if D != S)
    MOV DH, BL                  ; DH <- (D != S)

    CMP EA, 127
    JNZ CARRY, ROUND_F32_SMALL  ; If EA < 127 (|X| < 1.0)

    ; Here 127 <= EA < 150 (has fractional bits)
    LDI C, 150
    SUB C, EA                   ; C <- K = 150 - EA (1 <= K <= 23)

    LDI BL, 1
    LSL BL, C                   ; BL <- 1 << K
    MOV DL, BL                  ; DL <- 1 << K (save increment)
    SUB BL, 1                   ; BL <- (1 << K) - 1 (mask of fractional bits)

    MOV CL, AL
    AND CL, BL                  ; CL <- fractional bits of AL (32-bit)
    JZ ZERO, ROUND_F32_NO_FRAC  ; If fractional bits are 0, already an integer!

    ; Has fractional bits: clear them in AL
    NOT BL
    AND AL, BL                  ; AL <- integer part only

    ; Check if we need to increment magnitude (D != S)
    OR DH, DH
    JZ ZERO, ROUND_F32_PACK     ; If D == S, do not increment

    ; D != S: increment integer magnitude by (1 << K)
    ADD AL, DL

    ; Check if mantissa overflowed bit 23 into bit 24
    MOV BL, AL
    LSR BL, 24
    JZ ZERO, ROUND_F32_PACK     ; No carry into bit 24

    LSR AL, 1                   ; Shift mantissa right
    EXP_ADD EA, 1               ; Increment exponent
    JMP ROUND_F32_PACK

ROUND_F32_SMALL:
    ; |X| < 1.0: test if D != S
    OR DH, DH
    JZ ZERO, ROUND_F32_SMALL_0  ; If D == S, return signed 0.0

    ; D != S: return signed 1.0
    LDI EA, 127
    LDI AL, 1
    LSL AL, 23                  ; AL <- 0x00800000 (1.0 mantissa)
    JMP ROUND_F32_PACK

ROUND_F32_SMALL_0:
    XOR AL, AL                  ; AL <- 0 (signed 0.0)

ROUND_F32_PACK:
    OR AH, AH                   ; Sets STATUS.SIGN from AH[31]
    PACK AL, EA                 ; Packs float, sets ZERO, SIGN, clears OVERFLOW
    HALT AL

ROUND_F32_NO_FRAC:
    MOV AL, AH
    OR AL, AL                   ; Sets SIGN, ZERO=0, C=0, V=0
    HALT AL

ROUND_F32_ZERO:
    MOV AL, AH                  ; Retains ZERO=1, SIGN=sign from UNPACK
    HALT AL
