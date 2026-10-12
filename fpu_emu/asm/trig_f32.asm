; ==============================================================================
; TRIG_F32: IEEE-754 Single-Precision Trigonometric Functions (SIN, COS, TAN)
;
; Delegation wrapper:
;   1. Dispatches based on opcode (0 = SIN, 1 = COS, 2 = TAN)
;   2. Checks for special inputs (NaN, +/-Inf) -> returns Quiet NaN with ERR=1
;   3. Widens float32 input to float64 via CONV_F32_F64_CORE
;   4. Executes TRIG_F64_CORE
;   5. Narrows float64 result back to float32 via CONV_F64_F32_CORE
;   6. HALT AL
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
    CALL POP_ONE_32             ; AL <- theta (TOS), halts on underflow
    STO 15, CL                  ; SCR[15] <- opcode

    ; Check for special inputs: NaN or +/-Infinity (biased exponent == 255)
    MOV BL, AL                  ; Copy AL to BL
    LSL BL, 1                   ; BL <- BL << 1 (clear sign bit)
    LSR BL, 24                  ; BL <- 8-bit biased exponent
    CMP BL, 255
    JZ ZERO, .trig_f32_special

    ; Normal / Subnormal / Zero input: delegate to TRIG_F64_CORE
    CALL CONV_F32_F64_CORE      ; AX <- float64(theta)
    LD CL, 15                   ; CL <- opcode (0=SIN, 1=COS, 2=TAN)
    CALL TRIG_F64_CORE          ; AX <- float64 result
    CALL CONV_F64_F32_CORE      ; AL <- float32 result
    HALT AL

.trig_f32_special:
    LDC AL, CONST, NAN_F32      ; Return Quiet NaN
    SET ERR, 1                  ; Assert domain error
    HALT AL
