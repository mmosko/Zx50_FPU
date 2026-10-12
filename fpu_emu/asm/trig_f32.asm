; ==============================================================================
; TRIG_F32: IEEE-754 Single-Precision Trigonometric Functions (SIN, COS, TAN)
;
; Opcodes:
;   USER_SIN_F32 (0x72): Compute sin(theta) for single float on TOS
;   USER_COS_F32 (0x7A): Compute cos(theta) for single float on TOS
;   USER_TAN_F32 (0x82): Compute tan(theta) for single float on TOS
;
; Algorithm:
;   1. Handle special cases:
;      - theta = +/-0.0: sin(+/-0)=+/-0, cos(+/-0)=1.0, tan(+/-0)=+/-0
;      - theta = +/-Inf: set ERR=1, return Quiet NaN (domain error)
;      - theta = NaN: return NaN as-is, set ERR=1
;      - |theta| < 2^-12: sin(theta)=theta, cos(theta)=1.0, tan(theta)=theta
;   2. Range Reduction (Cody-Waite 2-term):
;      - y = |theta|
;      - k = round(y * (2/pi))
;      - q = k & 3 (quadrant index)
;      - r = (y - k * C1) - k * C2, where r in [-pi/4, pi/4]
;      - x = r^2
;   3. Cosine mapping:
;      - cos(theta) = sin(|theta| + pi/2), so q_cos = (q + 1) & 3, sign = 0.
;   4. Horner Polynomial Evaluation (unrolled):
;      - sin(r) = r * (1 - x * (c1 - x * (c2 - x * c3)))
;      - cos(r) = 1 - x * (d1 - x * (d2 - x * (d3 - x * d4)))
;   5. Reconstruction:
;      - SIN/COS: if q & 1 == 0 -> sin(r); if q & 1 == 1 -> cos(r)
;                 negate if bit 1 of q is set (q == 2 or 3); apply sign(theta).
;      - TAN:     if q & 1 == 0 -> sin(r) / cos(r)
;                 if q & 1 == 1 -> -cos(r) / sin(r); apply sign(theta).
;
; Scratchpad Allocation (SCR[0..63]):
;   SCR[0]  : Reduced angle r (float32)
;   SCR[2]  : x = r^2 (float32) / MAGIC during reduction
;   SCR[6]  : Original theta sign & value (float32)
;   SCR[8]  : y = |theta| (float32)
;   SCR[10] : k_f32 (float32)
;   SCR[14] : Quadrant index q = k & 3
;   SCR[15] : User opcode (0 = SIN, 1 = COS, 2 = TAN)
;   SCR[16] : sin(r) intermediate for TAN
; ==============================================================================

USER_SIN_F32:
    LDI CL, 0                   ; Opcode 0 = SIN
    JMP TRIG_F32_ENTRY

USER_COS_F32:
    LDI CL, 1                   ; Opcode 1 = COS
    JMP TRIG_F32_ENTRY

USER_TAN_F32:
    LDI CL, 2                   ; Opcode 2 = TAN

TRIG_F32_ENTRY:
    STO 15, CL                  ; SCR[15] <- user opcode
    CALL POP_ONE_32             ; AL <- theta from TOS, halts on underflow
    STO 6, AL                   ; SCR[6] <- original theta

    ; Check for zero (+/-0.0), NaN, Inf, and tiny angles using UNPACK
    UNPACK AL, EA
    JZ ZERO, .trig_zero         ; Exponent and fraction zero -> +/-0.0
    CMP EA, 255
    JZ ZERO, .trig_nan_or_inf   ; Biased exp 255 -> NaN or Infinity
    CMP EA, 115
    JNZ CARRY, .trig_small_angle ; Biased exp < 115 (|theta| < 2^-12)

    ; Clear sign bit of theta to obtain y = |theta|
    LD AL, 6                    ; Reload original theta (AL was overwritten by UNPACK)
    LSL AL, 1
    LSR AL, 1
    STO 8, AL                   ; SCR[8] <- y = |theta|

    ; --------------------------------------------------------------------------
    ; Cody-Waite Range Reduction: k = round(y * (2/pi))
    ; --------------------------------------------------------------------------
    ; AL = y * (2/pi) (CONST slot 44)
    LDC BL, CONST, 44
    CALL MUL_F32_CORE

    ; Add 0.5: 0x3F000000 (biased exp 126 << 23)
    LDI BL, 126
    LSL BL, 23
    CALL ADD_F32_CORE

    ; Add MAGIC constant: 1.5 * 2^23 = 0x4B400000
    LDI BL, 0x4B
    LSL BL, 8
    OR BL, 0x40
    LSL BL, 16                  ; BL <- 0x4B400000
    STO 2, BL                   ; SCR[2] <- MAGIC
    CALL ADD_F32_CORE

    ; Extract quadrant q = k & 3
    AND DL, AL, 3

    ; Subtract MAGIC to get float32 k_f32
    LD BL, 2
    CALL SUB_F32_CORE
    STO 10, AL                  ; SCR[10] <- k_f32

    ; r1 = y - k_f32 * C1 (CW_C1_F32 = CONST slot 47)
    LDC BL, CONST, 47
    CALL MUL_F32_CORE
    MOV BL, AL
    LD AL, 8                    ; AL <- y
    CALL SUB_F32_CORE
    STO 0, AL                   ; SCR[0] <- r1

    ; r = r1 - k_f32 * C2 (CW_C2_F32 = CONST slot 48)
    LD AL, 10                   ; AL <- k_f32
    LDC BL, CONST, 48
    CALL MUL_F32_CORE
    MOV BL, AL
    LD AL, 0                    ; AL <- r1
    CALL SUB_F32_CORE
    STO 0, AL                   ; SCR[0] <- reduced r in [-pi/4, pi/4]

    ; Compute x = r^2
    MOV BL, AL
    CALL MUL_F32_CORE
    STO 2, AL                   ; SCR[2] <- x = r^2

    ; --------------------------------------------------------------------------
    ; Cosine & Quadrant Mapping
    ; --------------------------------------------------------------------------
    LD CL, 15                   ; CL <- user opcode
    CMP CL, 1
    JNZ ZERO, .not_cos
    ADD DL, DL, 1
    AND DL, DL, 3               ; q = (q + 1) & 3 for COS
    LDI DH, 0
    STO 6, DH                   ; Clear sign of theta for COS (cos(-x) = cos(x))
.not_cos:
    STO 14, DL                  ; SCR[14] <- q
    CMP CL, 2
    JZ ZERO, .dispatch_tan

    ; --- USER_SIN_F32 & USER_COS_F32 ---
    AND DL, DL, 1
    JNZ ZERO, .sin_odd_q
    CALL EVAL_SIN_F32
    JMP .check_quad_neg
.sin_odd_q:
    CALL EVAL_COS_F32
.check_quad_neg:
    LD DL, 14
    AND DL, DL, 2               ; Negate if q == 2 or q == 3 (bit 1 set)
    JZ ZERO, .apply_sign_and_halt
    FCHS AL
    JMP .apply_sign_and_halt

    ; --- USER_TAN_F32 ---
.dispatch_tan:
    CALL EVAL_SIN_F32
    STO 16, AL                  ; SCR[16] <- sin(r)
    CALL EVAL_COS_F32
    MOV BL, AL                  ; BL <- cos(r)
    LD AL, 16                   ; AL <- sin(r)
    LD DL, 14
    AND DL, DL, 1
    JZ ZERO, .tan_div
    MOV DH, AL                  ; Odd quadrant: num = -cos(r), den = sin(r)
    MOV AL, BL
    FCHS AL
    MOV BL, DH
.tan_div:
    CALL DIV_F32_CORE

.apply_sign_and_halt:
    LD BH, 6                    ; BH <- original theta
    LSR BH, 31                  ; Test sign bit of theta
    JZ ZERO, .halt_al
    FCHS AL                     ; Invert sign if theta was negative
.halt_al:
    HALT AL

    ; --------------------------------------------------------------------------
    ; Special Cases
    ; --------------------------------------------------------------------------
.trig_zero:
.trig_small_angle:
    LD CL, 15                   ; CL <- user opcode
    CMP CL, 1
    JZ ZERO, .trig_ret_one      ; cos(0 or small) = 1.0
    LD AL, 6                    ; Return original theta for SIN and TAN
    HALT AL

.trig_ret_one:
    LDC AL, CONST, 32           ; AL <- 1.0 (ONE_F32)
    HALT AL

.trig_nan_or_inf:
    LD AL, 6                    ; Load original theta
    MOV DH, AL
    LSL DH, 9                   ; Clear sign and exponent bits
    JZ ZERO, .trig_inf_err      ; If fraction == 0: Infinity -> Domain Error!

    ; NaN: Return NaN as-is with ERR=1
    LDI ERR, 1
    HALT AL

.trig_inf_err:
    ; Return Quiet NaN (0x7FC00000) with ERR=1
    LDC AL, CONST, 35           ; AL <- NAN_F32
    LDI ERR, 1
    HALT AL

; ==============================================================================
; Polynomial Evaluators
; ==============================================================================
; EVAL_SIN_F32: sin(r) = r * (1 - x * (c1 - x * (c2 - x * c3)))
; Inputs: SCR[0] = r, SCR[2] = x = r^2
; Output: AL = sin(r)
EVAL_SIN_F32:
    LD AL, 2                    ; AL <- x
    LDC BL, CHEB, SIN_C3        ; BL <- c3
    CALL MUL_F32_CORE           ; AL <- x * c3
    MOV BL, AL
    LDC AL, CHEB, SIN_C2        ; AL <- c2
    CALL SUB_F32_CORE           ; AL <- c2 - x * c3
    LD BL, 2                    ; BL <- x
    CALL MUL_F32_CORE           ; AL <- x * (c2 - x * c3)
    MOV BL, AL
    LDC AL, CHEB, SIN_C1        ; AL <- c1
    CALL SUB_F32_CORE           ; AL <- c1 - x * (...)
    LD BL, 2                    ; BL <- x
    CALL MUL_F32_CORE           ; AL <- x * (c1 - ...)
    MOV BL, AL
    LDC AL, CONST, 32           ; AL <- 1.0
    CALL SUB_F32_CORE           ; AL <- 1.0 - x * (...)
    LD BL, 0                    ; BL <- r
    CALL MUL_F32_CORE           ; AL <- r * (1.0 - ...)
    RET

; EVAL_COS_F32: cos(r) = 1 - x * (d1 - x * (d2 - x * (d3 - x * d4)))
; Inputs: SCR[2] = x = r^2
; Output: AL = cos(r)
EVAL_COS_F32:
    LD AL, 2                    ; AL <- x
    LDC BL, CHEB, COS_D4        ; BL <- d4
    CALL MUL_F32_CORE           ; AL <- x * d4
    MOV BL, AL
    LDC AL, CHEB, COS_D3        ; AL <- d3
    CALL SUB_F32_CORE           ; AL <- d3 - x * d4
    LD BL, 2                    ; BL <- x
    CALL MUL_F32_CORE           ; AL <- x * (d3 - x * d4)
    MOV BL, AL
    LDC AL, CHEB, COS_D2        ; AL <- d2
    CALL SUB_F32_CORE           ; AL <- d2 - x * (...)
    LD BL, 2                    ; BL <- x
    CALL MUL_F32_CORE           ; AL <- x * (d2 - ...)
    MOV BL, AL
    LDC AL, CHEB, COS_D1        ; AL <- d1
    CALL SUB_F32_CORE           ; AL <- d1 - x * (...)
    LD BL, 2                    ; BL <- x
    CALL MUL_F32_CORE           ; AL <- x * (d1 - ...)
    MOV BL, AL
    LDC AL, CONST, 32           ; AL <- 1.0
    CALL SUB_F32_CORE           ; AL <- 1.0 - x * (...)
    RET
