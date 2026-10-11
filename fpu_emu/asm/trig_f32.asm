; ==============================================================================
; TRIG_F32: IEEE-754 Single-Precision Trigonometric Functions (SIN, COS, TAN)
;
; Optimized for Zx50 FPU Rev 2 using ternary ops, register context,
; fall-through layout, and deduplicated special-case returns.
; ==============================================================================

.equ ONE_F32, 32
.equ POS_INF_F32, 38
.equ NAN_F32, 35

USER_SIN_F32:
    LDI CL, 0                   ; CL <- Opcode 0 = SIN
    JMP TRIG_ENTRY

USER_COS_F32:
    LDI CL, 1                   ; CL <- Opcode 1 = COS
    JMP TRIG_ENTRY

USER_TAN_F32:
    LDI CL, 2                   ; CL <- Opcode 2 = TAN (falls through into TRIG_ENTRY)

TRIG_ENTRY:
    CALL POP_ONE_32             ; AL <- theta (TOS)
    MOV CH, AL                  ; CH <- original theta (preserves sign and value)

    ; Check for zero, NaN, Inf, and tiny angles
    UNPACK EA, AL               ; EA <- exponent, AL <- mantissa
    JZ ZERO, TRIG_SMALL_ANGLE   ; If input == 0.0: special zero/small angle handling
    CMP EA, 255
    JZ ZERO, TRIG_NAN_ERR       ; If NaN or Inf: error handling
    CMP EA, 115                 ; |theta| < 2^-12 (E < 115)
    JNZ CARRY, TRIG_SMALL_ANGLE ; If small angle: fast path

    ; Extract sign bit theta[31] into CH[31] (cleared for COS later)
    LSR CH, 31
    LSL CH, 31                  ; CH <- 0x80000000 if negative, 0 if positive

    ; --------------------------------------------------------------------------
    ; Range Reduction (Cody-Waite mod pi/2)
    ; --------------------------------------------------------------------------
    CMP EA, 126
    JZ CARRY, TRIG_REDUCE_GENERAL  ; If EA >= 126 (C=0): Cody-Waite reduction

    ; Here 115 <= EA < 126: |theta| < 0.5 < pi/4, so k = 0, q = 0, r = |theta|
    LDI EB, 0                   ; EB <- quadrant 0
    CMP EA, 120
    JNZ CARRY, TRIG_SMALL_SHIFT_RIGHT
    SUB C, EA, 120              ; C <- EA - 120 (Ternary SUB: 1 cycle)
    LSL AL, C                   ; Shift mantissa to Q2.30
    MOV BH, AL                  ; BH <- Z0 = r in Q2.30
    JMP TRIG_START_CORDIC

TRIG_SMALL_SHIFT_RIGHT:
    SUB C, 120, EA              ; C <- 120 - EA (Ternary SUB: 1 cycle)
    LSR AL, C                   ; Shift mantissa to Q2.30
    MOV BH, AL                  ; BH <- Z0 = r in Q2.30
    JMP TRIG_START_CORDIC

TRIG_REDUCE_GENERAL:
    ; EA >= 126: Compute k = round(|theta| * 2/pi)
    MOV DH, AL                  ; DH <- original mantissa
    LDC BL, CONST, 44           ; BL <- TWO_OVER_PI_F32 (0x3F22F983)
    UNPACK EB, BL               ; BL <- mantissa of 2/pi
    MULU AL, BL                 ; {AH, AL} <- mantissa * (2/pi mantissa)

    ; Shift amount s_hi = 142 - EA
    SUB C, 141, EA              ; C <- s_hi - 1 (Ternary SUB: 1 cycle)
    LDI BL, 1
    LSL BL, C                   ; BL <- rounding bit
    ADD AH, AH, BL              ; AH <- AH + rounding bit (Ternary ADD)
    SUB C, 142, EA              ; C <- s_hi (Ternary SUB: 1 cycle)
    LSR AH, C                   ; AH <- k (rounded integer)
    MOV DL, AH                  ; DL <- k

    ; Extract quadrant q = k & 3
    AND EB, AH, 3               ; EB <- quadrant q (Ternary AND)

    ; Cody-Waite subtraction: r = theta_q30 - k*C1 - k*C2
    SUB C, EA, 120              ; C <- EA - 120 (Ternary SUB)
    LSL DH, C                   ; DH <- theta in Q2.30

    ; 1. Subtract k * C1 (C1_mant = 102943 = (100 << 10) + 543):
    LDI BL, 100
    LSL BL, 10
    ADD BL, BL, 543             ; BL <- 102943 (Ternary ADD)
    MULU AL, DL, BL             ; {AH, AL} <- k * 102943
    LSL AL, 14                  ; AL <- (k * C1) in Q2.30
    SUB DH, DH, AL              ; DH <- theta - k*C1 (Ternary SUB)

    ; 2. Subtract k * C2 (C2_mant = 11601 = (45 << 8) + 81):
    LDI BL, 45
    LSL BL, 8
    ADD BL, BL, 81              ; BL <- 11601 (Ternary ADD)
    MULU AL, DL, BL             ; {AH, AL} <- k * 11601
    SUB BH, DH, AL              ; BH <- Z0 = r = theta - k*C1 - k*C2 (Ternary SUB)

    ; --------------------------------------------------------------------------
    ; Accelerated Circular CORDIC Engine (24 stages)
    ; --------------------------------------------------------------------------
TRIG_START_CORDIC:
    LDC FL, CONST, 55           ; FL <- CORDIC_INV_K_32 (1/K in Q2.30)
    XOR BL, BL                  ; BL <- Y0 = 0
    LDI C, 0                    ; C <- stage counter

CORDIC_STAGE_LOOP:
    MOV DH, FL
    LSR DH, C                   ; DH <- X >> C
    MOV FH, BL
    ASR FH, C                   ; FH <- Y >> C (sign extended)
    LDC AH, TRIG, C             ; AH <- theta_C

    OR BH, BH
    JNZ SIGN, CORDIC_DIR_NEG    ; If Z < 0: rotate negative

CORDIC_DIR_POS:
    ; Z >= 0: X <= X - Y_shift, Y <= Y + X_shift, Z <= Z - theta_C
    SUB FL, FL, FH              ; FL <- X - Y_shift (Ternary: 1 cycle)
    ADD BL, BL, DH              ; BL <- Y + X_shift (Ternary: 1 cycle)
    SUB BH, BH, AH              ; BH <- Z - theta_C (Ternary: 1 cycle)
    JMP CORDIC_STAGE_NEXT

CORDIC_DIR_NEG:
    ; Z < 0: X <= X + Y_shift, Y <= Y - X_shift, Z <= Z + theta_C
    ADD FL, FL, FH              ; FL <- X + Y_shift (Ternary: 1 cycle)
    SUB BL, BL, DH              ; BL <- Y - X_shift (Ternary: 1 cycle)
    ADD BH, BH, AH              ; BH <- Z + theta_C (Ternary: 1 cycle)

CORDIC_STAGE_NEXT:
    ADD C, 1
    CMP C, 24
    JNZ ZERO, CORDIC_STAGE_LOOP

    ; CORDIC complete: FL = cos(r) in Q2.30, BL = sin(r) in Q2.30

    ; --------------------------------------------------------------------------
    ; Opcode Reconstruction & Normalization
    ; --------------------------------------------------------------------------
    CMP CL, 2
    JZ ZERO, RECONSTRUCT_TAN
    CMP CL, 1
    JNZ ZERO, RECONSTRUCT_SIN   ; If SIN (CL == 0): jump to RECONSTRUCT_SIN

    ; Opcode == 1 (COS): cos(theta) = sin(|theta| + pi/2)
    LDI CH, 0                   ; Clear theta sign (cos(-x) = cos(x))
    ADD EB, EB, 1
    AND EB, EB, 3               ; EB <- (q + 1) & 3

RECONSTRUCT_SIN:
    ; Even quadrant (q=0,2): mag = |Y| (BL); Odd quadrant (q=1,3): mag = X (FL)
    AND AL, EB, 1
    JNZ ZERO, SIN_ODD_Q

    ; Even quadrant (q = 0, 2):
    MOV AL, BL                  ; AL <- Y (signed)
    LDI AH, 0                   ; Default sign = 0
    CMP EB, 2
    JNZ ZERO, SIN_HANDLE_Y_SIGN
    LDI AH, 1
    LSL AH, 31                  ; q == 2: negate sign (AH = 0x80000000)

SIN_HANDLE_Y_SIGN:
    OR AL, AL
    JZ SIGN, SIN_FINISH_SIGN    ; If Y >= 0, sign is ready
    NOT AL
    ADD AL, 1                   ; AL <- |Y|
    FCHS AH                     ; Flip target sign bit
    JMP SIN_FINISH_SIGN

SIN_ODD_Q:
    ; Odd quadrant (q = 1, 3):
    MOV AL, FL                  ; AL <- X (always positive)
    LDI AH, 0
    CMP EB, 3
    JNZ ZERO, SIN_FINISH_SIGN
    LDI AH, 1
    LSL AH, 31                  ; q == 3: sign = 0x80000000

SIN_FINISH_SIGN:
    XOR AH, AH, CH              ; Combine with original theta sign (Ternary XOR)
    ; Falls directly into TRIG_PACK_FLOAT (saves 1 JMP instruction!)

    ; --------------------------------------------------------------------------
    ; Pack Normalized Float for SIN / COS
    ; --------------------------------------------------------------------------
TRIG_PACK_FLOAT:
    LSR AL, 7
    LDI EA, 127
    CALL NORMALIZE_F32
    PUSH AL
    HALT

    ; --- Tangent Reconstruction ---
RECONSTRUCT_TAN:
    LDI AH, 0                   ; Initial sign = 0
    OR BL, BL
    JZ SIGN, TAN_Y_IS_POS
    NOT BL
    ADD BL, 1                   ; BL <- |Y|
    LDI AH, 1
    LSL AH, 31                  ; AH <- 0x80000000
TAN_Y_IS_POS:

    AND AL, EB, 1
    JZ ZERO, TAN_EVEN_Q
    ; Odd quadrant (q = 1, 3): N = X, D = |Y|, flip sign
    MOV AL, FL                  ; AL <- Numerator X
    FCHS AH
    JMP TAN_FINISH_SIGN

TAN_EVEN_Q:
    ; Even quadrant (q = 0, 2): N = |Y|, D = X
    MOV AL, BL                  ; AL <- Numerator |Y|
    MOV BL, FL                  ; BL <- Denominator X

TAN_FINISH_SIGN:
    XOR AH, AH, CH              ; Combine with theta sign (Ternary XOR)
    MOV DH, AH                  ; DH[31] <- final sign

    ; Check for zero denominator (asymptote at +/- pi/2)
    OR BL, BL
    JZ ZERO, TAN_DIV_ZERO
    OR AL, AL
    JZ ZERO, TAN_ZERO

    ; Convert numerator (AL) and denominator (BL) to float32
    LSR AL, 7
    LDI EA, 127
    LDI AH, 0
    CALL NORMALIZE_F32          ; AL <- float32(Numerator)
    MOV DL, AL                  ; DL <- float32(Numerator)

    MOV AL, BL
    LSR AL, 7
    LDI EA, 127
    LDI AH, 0
    CALL NORMALIZE_F32          ; AL <- float32(Denominator)
    MOV BL, AL                  ; BL <- float32(Denominator)
    MOV AL, DL                  ; AL <- float32(Numerator)

    ; Perform float division: AL / BL
    OR AL, AL, DH               ; Attach computed sign to numerator
    CALL DIV_F32_CORE           ; AL <- AL / BL
    PUSH AL
    HALT

TAN_ZERO:
    XOR AL, AL                  ; Return zero mantissa
    MOV AH, DH                  ; Preserve computed sign
    CALL NORMALIZE_F32
    PUSH AL
    HALT

TAN_DIV_ZERO:
    XOR BL, BL
    DIVU AL, BL                 ; Asserts ERR=1, VF=1 in hardware
    LDC AL, CONST, POS_INF_F32  ; POS_INF_F32 (0x7F800000)
    OR AL, AL, DH               ; Attach computed sign
    PUSH AL
    HALT

    ; --------------------------------------------------------------------------
    ; Special Cases (Zero, NaN, Small Angle)
    ; --------------------------------------------------------------------------
TRIG_SMALL_ANGLE:               ; Merged ZERO and SMALL_ANGLE handlers (saves 5 words)
    CMP CL, 1
    JZ ZERO, TRIG_RET_ONE       ; COS(0 or small) -> 1.0
    MOV AL, CH                  ; Return original theta / 0.0
    PUSH AL
    HALT

TRIG_RET_ONE:
    LDC AL, CONST, ONE_F32      ; ONE_F32 (0x3F800000 = 1.0)
    PUSH AL
    HALT

TRIG_NAN_ERR:
    LDC AL, CONST, NAN_F32      ; NAN_F32 (0x7FC00000)
    PUSH AL
    LDI ERR, 1
    HALT
