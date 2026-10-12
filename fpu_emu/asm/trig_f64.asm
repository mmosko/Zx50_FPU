; ==============================================================================
; TRIG_F64: IEEE-754 Double-Precision Trigonometric Functions (SIN, COS, TAN)
;
; Opcodes:
;   USER_SIN_F64 (0x73): Compute sin(theta) for double float on TOS
;   USER_COS_F64 (0x7B): Compute cos(theta) for double float on TOS
;   USER_TAN_F64 (0x83): Compute tan(theta) for double float on TOS
;
; Algorithm:
;   1. Handle special cases:
;      - theta = +/-0.0: sin(+/-0)=+/-0, cos(+/-0)=1.0, tan(+/-0)=+/-0
;      - theta = +/-Inf: set ERR=1, return Quiet NaN (domain error)
;      - theta = NaN: return NaN as-is
;      - |theta| < 2^-27: sin(theta)=theta, cos(theta)=1.0, tan(theta)=theta
;   2. Range Reduction (Cody-Waite 3-term extended precision):
;      - y = |theta|
;      - k = round(y * (2/pi))
;      - q = k & 3 (quadrant index)
;      - r = ((y - k * C1) - k * C2) - k * C3, where r in [-pi/4, pi/4]
;      - C1, C2, C3 are stored in CONST ROM slots 49..54.
;   3. Core Polynomial Evaluation (Horner's rule with integer divisor):
;      - sin(r) = r * (1 - r^2/6 * (1 - r^2/20 * (1 - ...)))
;      - cos(r) = 1 - r^2/2 * (1 - r^2/12 * (1 - ...))
;      - 8 terms yield 53 bits (1 ULP) IEEE-754 precision.
;   4. Reconstruction:
;      - SIN: even q -> sin(r), odd q -> cos(r); negate if q in {2, 3}; apply sign(theta)
;      - COS: even q -> cos(r), odd q -> sin(r); negate if q in {1, 2}
;      - TAN: even q -> sin(r)/cos(r), odd q -> -cos(r)/sin(r); apply sign(theta)
;
; Inputs:
;   Stack: TOS = 64-bit IEEE-754 double theta {AH, AL}
;
; Outputs:
;   Stack: TOS = 64-bit IEEE-754 double result {AH, AL}
;   Status flags:
;     ZERO = 1 if result is +/-0.0
;     SIGN = sign of result (bit 63)
;     ERR = 1 on Stack Underflow (< 8 bytes) or +/-Inf domain error
;
; Scratchpad Allocation (SCR[0..63]):
;   SCR[0..1]   : Reduced angle r (float64)
;   SCR[2..3]   : x = r^2 (float64) / MAGIC during reduction
;   SCR[4..5]   : S polynomial accumulator (float64)
;   SCR[6..7]   : Original theta (float64)
;   SCR[8..9]   : y = |theta| (float64)
;   SCR[10..11] : k_f64 (float64) / dm float64 divisor
;   SCR[12]     : Loop counter m (8 down to 1)
;   SCR[13]     : Poly function selector (0 = sin, 1 = cos)
;   SCR[14]     : Quadrant index q = k & 3
;   SCR[15]     : User opcode (0 = SIN, 1 = COS, 2 = TAN)
;   SCR[16..17] : sin(r) intermediate for TAN
;   SCR[18..19] : cos(r) intermediate for TAN
;
; Register Allocation:
;   AX (AL, AH) : Computation accumulator / float64 operand / return value
;   BX (BL, BH) : Secondary float64 operand
;   CL          : User opcode / loop counter / loop temporary
;   DL, DH      : Quadrant / selector / bit manipulation temporaries
;   EA          : Exponent register during normalization
; ==============================================================================

USER_SIN_F64:
    LDI CL, 0                   ; Opcode 0 = SIN
    JMP TRIG_F64_ENTRY

USER_COS_F64:
    LDI CL, 1                   ; Opcode 1 = COS
    JMP TRIG_F64_ENTRY

USER_TAN_F64:
    LDI CL, 2                   ; Opcode 2 = TAN

TRIG_F64_ENTRY:
    STO 15, CL                  ; SCR[15] <- user opcode
    CALL POP_ONE_64             ; AX <- theta from TOS, halts on underflow
    STO 6, AX                   ; SCR[6..7] <- original theta

    ; Check for zero (+/-0.0): AH[30:0] == 0 and AL == 0
    MOV DH, AH
    LSL DH, 1
    OR DH, DH, AL
    JZ ZERO, .trig_zero

    ; Extract 11-bit biased exponent into DH
    MOV DH, AH
    LSL DH, 1
    LSR DH, 21
    ADD DL, DH, 1
    LSR DL, 11
    JNZ ZERO, .trig_nan_or_inf   ; If exponent was 2047: Inf or NaN

    ; Tiny angle check: |theta| < 2^-27 (biased exp < 996)
    CMP DH, 996
    JNZ CARRY, .trig_small_angle

    ; Clear sign bit of theta to obtain y = |theta|
    LSL AH, 1
    LSR AH, 1
    STO 8, AX                   ; SCR[8..9] <- y = |theta|

    ; --------------------------------------------------------------------------
    ; Cody-Waite Range Reduction: k = round(y * (2/pi))
    ; --------------------------------------------------------------------------
    ; AX = y * (2/pi) (CONST slots 45, 46)
    LDC BL, CONST, 45
    LDC BH, CONST, 46
    CALL MUL_F64_CORE

    ; Add 0.5: 0x3FE00000_00000000 (biased exp 1022 << 20)
    XOR BL, BL
    LDI BH, 1022
    LSL BH, 20
    CALL ADD_F64_CORE

    ; Add MAGIC constant: 1.5 * 2^52 = 0x43380000_00000000
    XOR BL, BL
    LDI BH, 0x43
    LSL BH, 8
    OR BH, 0x38
    LSL BH, 16
    STO 2, BX                   ; SCR[2..3] <- MAGIC
    CALL ADD_F64_CORE

    ; Extract integer k and quadrant q = k & 3
    MOV BL, AL
    AND DL, BL, 3
    STO 14, DL                  ; SCR[14] <- q = k & 3

    ; Subtract MAGIC to get float64 k_f64
    LD BX, 2
    CALL SUB_F64_CORE
    STO 10, AX                  ; SCR[10..11] <- k_f64

    ; r1 = y - k_f64 * C1 (CW_C1_F64 = CONST slots 49, 50)
    LDC BL, CONST, 49
    LDC BH, CONST, 50
    CALL MUL_F64_CORE
    MOV BX, AX
    LD AX, 8                    ; AX <- y
    CALL SUB_F64_CORE
    STO 0, AX                   ; SCR[0..1] <- r1

    ; r2 = r1 - k_f64 * C2 (CW_C2_F64 = CONST slots 51, 52)
    LD AX, 10                   ; AX <- k_f64
    LDC BL, CONST, 51
    LDC BH, CONST, 52
    CALL MUL_F64_CORE
    MOV BX, AX
    LD AX, 0                    ; AX <- r1
    CALL SUB_F64_CORE
    STO 0, AX                   ; SCR[0..1] <- r2

    ; r = r2 - k_f64 * C3 (CW_C3_F64 = CONST slots 53, 54)
    LD AX, 10                   ; AX <- k_f64
    LDC BL, CONST, 53
    LDC BH, CONST, 54
    CALL MUL_F64_CORE
    MOV BX, AX
    LD AX, 0                    ; AX <- r2
    CALL SUB_F64_CORE
    STO 0, AX                   ; SCR[0..1] <- reduced r in [-pi/4, pi/4]

    ; --------------------------------------------------------------------------
    ; Function Dispatch: SIN, COS, TAN
    ; --------------------------------------------------------------------------
    LD CL, 15                   ; CL <- user opcode
    CMP CL, 1
    JZ ZERO, .dispatch_cos
    CMP CL, 2
    JZ ZERO, .dispatch_tan

    ; --- USER_SIN_F64 ---
    LD DL, 14                   ; DL <- q
    AND DL, DL, 1
    JNZ ZERO, .sin_odd_q

    ; Even quadrant (q = 0 or 2): evaluate sin(r)
    LDI DL, 0
    STO 13, DL
    CALL TRIG_POLY_CORE
    LD DL, 14
    CMP DL, 2
    JNZ ZERO, .sin_apply_sign
    FCHS AH                     ; Negate for q == 2
    JMP .sin_apply_sign

.sin_odd_q:
    ; Odd quadrant (q = 1 or 3): evaluate cos(r)
    LDI DL, 1
    STO 13, DL
    CALL TRIG_POLY_CORE
    LD DL, 14
    CMP DL, 3
    JNZ ZERO, .sin_apply_sign
    FCHS AH                     ; Negate for q == 3

.sin_apply_sign:
    LD BH, 7                    ; BH <- original AH
    LSR BH, 31                  ; Test sign bit of theta
    JZ ZERO, .sin_done
    FCHS AH                     ; Invert sign if theta was negative
.sin_done:
    HALT AX

    ; --- USER_COS_F64 ---
.dispatch_cos:
    LD DL, 14                   ; DL <- q
    AND DL, DL, 1
    JNZ ZERO, .cos_odd_q

    ; Even quadrant (q = 0 or 2): evaluate cos(r)
    LDI DL, 1
    STO 13, DL
    CALL TRIG_POLY_CORE
    LD DL, 14
    CMP DL, 2
    JNZ ZERO, .cos_done
    FCHS AH                     ; Negate for q == 2
    JMP .cos_done

.cos_odd_q:
    ; Odd quadrant (q = 1 or 3): evaluate sin(r)
    LDI DL, 0
    STO 13, DL
    CALL TRIG_POLY_CORE
    LD DL, 14
    CMP DL, 1
    JNZ ZERO, .cos_done
    FCHS AH                     ; Negate for q == 1

.cos_done:
    HALT AX

    ; --- USER_TAN_F64 ---
.dispatch_tan:
    ; Compute sin(r)
    LDI DL, 0
    STO 13, DL
    CALL TRIG_POLY_CORE
    STO 16, AX                  ; SCR[16..17] <- sin(r)

    ; Compute cos(r)
    LDI DL, 1
    STO 13, DL
    CALL TRIG_POLY_CORE
    STO 18, AX                  ; SCR[18..19] <- cos(r)

    LD DL, 14                   ; DL <- q
    AND DL, DL, 1
    JNZ ZERO, .tan_odd_q

    ; Even quadrant (q = 0 or 2): num = sin(r), den = cos(r)
    LD AX, 16                   ; AX <- sin(r)
    LD BX, 18                   ; BX <- cos(r)
    CALL DIV_F64_CORE
    JMP .tan_apply_sign

.tan_odd_q:
    ; Odd quadrant (q = 1 or 3): num = -cos(r), den = sin(r)
    LD AX, 18                   ; AX <- cos(r)
    FCHS AH                     ; AX <- -cos(r)
    LD BX, 16                   ; BX <- sin(r)
    CALL DIV_F64_CORE

.tan_apply_sign:
    LD BH, 7                    ; BH <- original AH
    LSR BH, 31                  ; Test sign bit of theta
    JZ ZERO, .tan_done
    FCHS AH                     ; Invert sign if theta was negative
.tan_done:
    HALT AX

    ; --------------------------------------------------------------------------
    ; Special Cases
    ; --------------------------------------------------------------------------
.trig_zero:
.trig_small_angle:
    LD CL, 15                   ; CL <- user opcode
    CMP CL, 1
    JZ ZERO, .trig_ret_one      ; cos(0 or small) = 1.0
    LD AX, 6                    ; Return original theta for SIN and TAN
    HALT AX

.trig_ret_one:
    XOR AL, AL
    LDI AH, 1023
    LSL AH, 20                  ; AX <- 1.0
    HALT AX

.trig_nan_or_inf:
    LD AX, 6                    ; Load original theta
    MOV DH, AH
    LSL DH, 12                  ; Clear sign and exponent bits
    OR DH, DH, AL               ; Check if fraction == 0
    JZ ZERO, .trig_inf_err      ; If fraction == 0: Infinity -> Domain Error!

    ; NaN: Return NaN as-is
    HALT AX

.trig_inf_err:
    ; Return Quiet NaN (0x7FF80000_00000000) with ERR=1
    XOR AL, AL
    LDI AH, 0x7F
    LSL AH, 8
    OR AH, AH, 0xF8
    LSL AH, 16                  ; AH <- 0x7FF80000
    LDI ERR, 1
    HALT AX

; ==============================================================================
; TRIG_POLY_CORE: Horner Polynomial for sin(r) or cos(r)
;
; Inputs:
;   SCR[0..1]  : Reduced angle r (float64) in [-pi/4, pi/4]
;   SCR[13]    : Selector (0 = sin, 1 = cos)
;
; Outputs:
;   AX         : Evaluated polynomial result (float64)
; ==============================================================================
TRIG_POLY_CORE:
    ; x = r^2
    LD AX, 0
    MOV BX, AX
    CALL MUL_F64_CORE
    STO 2, AX                   ; SCR[2..3] <- x = r^2

    ; Initialize S = 1.0
    XOR AL, AL
    LDI AH, 1023
    LSL AH, 20
    STO 4, AX                   ; SCR[4..5] <- S = 1.0

    LDI CL, 8
    STO 12, CL                  ; SCR[12] <- m = 8

TRIG_POLY_LOOP:
    LD CL, 12                   ; CL <- m
    LSL CL, 1                   ; CL <- 2m
    LD DL, 13                   ; DL <- selector (0=sin, 1=cos)
    OR DL, DL
    JNZ ZERO, .poly_cos_dm
    ADD DH, CL, 1               ; sin: dm = 2m * (2m + 1)
    JMP .poly_dm_calc
.poly_cos_dm:
    SUB DH, CL, 1               ; cos: dm = 2m * (2m - 1)
.poly_dm_calc:
    MULU AL, CL, DH             ; AL <- dm integer (max 272)
    XOR AH, AH
    XOR DH, DH
    LDI EA, 1023
    EXP_ADD EA, 52
    CALL NORMALIZE_F64          ; AX <- float64(dm)
    STO 10, AX                  ; SCR[10..11] <- float64(dm)

    ; term = (x * S) / dm
    LD AX, 2                    ; AX <- x
    LD BX, 4                    ; BX <- S
    CALL MUL_F64_CORE           ; AX <- x * S
    LD BX, 10                   ; BX <- float64(dm)
    CALL DIV_F64_CORE           ; AX <- (x * S) / dm

    ; S = 1.0 - term
    MOV BX, AX                  ; BX <- term
    XOR AL, AL
    LDI AH, 1023
    LSL AH, 20                  ; AX <- 1.0
    CALL SUB_F64_CORE           ; AX <- 1.0 - term
    STO 4, AX                   ; SCR[4..5] <- S

    LD CL, 12
    SUB CL, CL, 1
    STO 12, CL
    OR CL, CL
    JNZ ZERO, TRIG_POLY_LOOP

    ; Post-poly: if sin, result = r * S; if cos, result = S
    LD DL, 13
    OR DL, DL
    JNZ ZERO, .poly_done
    LD BX, 0                    ; BX <- r
    LD AX, 4                    ; AX <- S
    CALL MUL_F64_CORE           ; AX <- r * S
    RET
.poly_done:
    LD AX, 4                    ; AX <- S
    RET
