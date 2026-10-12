; ==============================================================================
; EXP2_F32: IEEE-754 Single-Precision Base-2 Exponential: 2^X
;
; Optimized for Zx50 FPU Rev 2 using ternary ops, direct IMM EA ops,
; and fall-through control flow reordering.
; Total size: ~56 microcode words (14 words saved over unoptimized version).
; ==============================================================================

.equ ONE_F32, 32
.equ POS_INF_F32, 38
.equ EXP2_C6, 6

USER_EXP2_F32:
    CALL POP_ONE_32                 ; AL <- X (TOS)
    CALL EXP2_CORE                  ; AL <- 2^AL
    HALT AL

EXP2_CORE:
    MOV BH, AL                      ; BH <- raw input (preserves sign and value)
    UNPACK AL, EA                   ; EA <- exponent, AL <- mantissa, status.SIGN <- sign
    JZ ZERO, EXP2_RET_ONE           ; 2^0 == 1.0

    CMP EA, 255                     ; Check for NaN / Inf directly on EA
    JZ ZERO, EXP2_RET_INPUT         ; If NaN or Inf: return original input

    CMP EA, 127
    JNZ CARRY, EXP2_EXP_LESS        ; If EA < 127 (|x| < 1.0), jump to right-shift

    ; --- EA >= 127 (|x| >= 1.0) ---
    SUB BL, EA, 127                 ; BL <- exp - 127 (Ternary SUB: 1 cycle)
    CMP BL, 8
    JZ CARRY, EXP2_OUT_OF_RANGE     ; If BL >= 8 (|x| >= 256.0, CARRY == 0), out of range
    LSL AL, BL                      ; AL <- fixed-point magnitude (Q8.23)
    JMP EXP2_EXTRACT_K_R

    ; --- EA < 127 (|x| < 1.0) ---
EXP2_EXP_LESS:
    SUB BL, 127, EA                 ; BL <- 127 - exp (Ternary SUB: 1 cycle)
    LSR AL, BL                      ; AL <- fixed-point magnitude (Q8.23)
    ; Flows directly into EXP2_EXTRACT_K_R (saves 1 JMP instruction!)

EXP2_EXTRACT_K_R:
    LDI CL, 1
    LSL CL, 22                      ; CL <- 0.5 in Q8.23 (0x00400000)
    MOV BL, AL                      ; BL <- unrounded fixed-point magnitude
    ADD AL, AL, CL                  ; AL <- round(x) = magnitude + 0.5 (Ternary)
    LSR AL, 23                      ; AL <- integer k
    MOV EA, AL                      ; EA <- k
    LSL AL, 23                      ; AL <- k << 23
    SUB BL, BL, AL                  ; BL <- fraction r = magnitude - k (Ternary)
    LSL BL, 8                       ; BL <- r in Q1.31

    OR BH, BH                       ; Test original sign from BH[31]
    JNZ SIGN, EXP2_NEG_X

    ; Positive x: exponent = 127 + k
    EXP_ADD EA, 127                 ; EA <- 127 + k (Direct immediate: 1 cycle)
    JMP EXP2_EVAL_POLY

EXP2_NEG_X:
    ; Negative x: remainder r is negated, exponent = 127 - k
    NOT BL
    ADD BL, 1                       ; BL <- -r
    EXP_SUB EA, 127, EA             ; EA <- 127 - k (Ternary with immediate: 1 cycle)

EXP2_EVAL_POLY:
    MOV CH, BL                      ; CH <- r in Q1.31 (using CH register)
    LDI C, 5                        ; Horner loop counter: 5 down to 1
    LDC AL, CHEB, EXP2_C6           ; AL <- c6
EXP2_POLY_LOOP:
    MUL AL, CH                      ; AH:AL <- AL * r
    LSL AH, 1                       ; AH <- (AL * r) in Q1.31
    LDC BL, CHEB, C                 ; BL <- c_i (slots 5, 4, 3, 2, 1)
    ADD AL, AH, BL                  ; AL <- AH + c_i (Ternary ADD: saves MOV AL, AH)
    DJNZ EXP2_POLY_LOOP             ; Repeat for all coefficients

    MUL AL, CH                      ; Final multiply: AL * r
    LSL AH, 1                       ; AH <- P(r) in Q1.31

    LDI BL, 1
    LSL BL, 31                      ; BL <- 1.0 in Q1.31 (0x80000000)
    ADD AL, AH, BL                  ; AL <- 1.0 + P(r) (Ternary ADD)
    LSR AL, 8                       ; Align Q1.31 mantissa to bit 23
    LDI AH, 0                       ; AH[31] = 0 (result sign is always positive)
    CALL NORMALIZE_F32              ; Normalize mantissa in AL, EA, sign in AH[31]
    RET

EXP2_OUT_OF_RANGE:
    OR BH, BH                       ; Restore sign flag from BH[31]
    JNZ SIGN, EXP2_RET_ZERO         ; Negative large |x| -> underflow to 0.0
    LDC AL, CONST, POS_INF_F32      ; Positive large |x| -> overflow to +Inf
    RET

EXP2_RET_ONE:
    LDC AL, CONST, ONE_F32
    RET

EXP2_RET_ZERO:
    XOR AL, AL
    RET

EXP2_RET_INPUT:
    MOV AL, BH                      ; Return original NaN / Inf input
    RET
