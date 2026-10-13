; ==============================================================================
; USER_SQRT_F32: IEEE-754 Single-Precision Square Root
;
; Delegation wrapper:
;   1. Pops one float32 operand: X in AL
;   2. Converts X to float64 in AX via CONV_F32_F64_CORE
;   3. Calls SQRT_F64_CORE
;   4. If ERR is set (domain error, X < 0), aborts without pushing
;   5. Converts float64 result in AX to float32 in AL via CONV_F64_F32_CORE
;   6. HALT AL
; ==============================================================================

USER_SQRT_F32:
    CALL POP_ONE_32                 ; AL <- X (TOS)
    CALL SQRT_F32_CORE              ; AL <- sqrt(AL)
    JNZ ERR, SQRT_F32_HALT          ; If domain error (ERR set), abort without pushing
    HALT AL                         ; Push result and halt
SQRT_F32_HALT:
    HALT

SQRT_F32_CORE:
    CALL CONV_F32_F64_CORE          ; AX <- float64(AL)
    CALL SQRT_F64_CORE              ; AX <- sqrt(AX)
    JNZ ERR, .sqrt_f32_domain_err   ; If domain error (X < 0), exit with ERR set
    CALL CONV_F64_F32_CORE          ; AL <- float32(AX)
    RET

.sqrt_f32_domain_err:
    RET
