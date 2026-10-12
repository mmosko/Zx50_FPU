; ==============================================================================
; USER_LOG2_F32: IEEE-754 Single-Precision Base-2 Logarithm: log2(X)
;
; Delegation wrapper: Widens float32 input in AL to float64 in AX, executes
; the 64-bit LOG2_F64_CORE, and narrows the result back to float32 in AL.
; If domain error (ERR set, e.g. X <= 0), halts without pushing.
; ==============================================================================

USER_LOG2_F32:
    CALL POP_ONE_32                 ; AL <- X (TOS)
    CALL LOG2_CORE                  ; AL <- log2(AL)
    JNZ ERR, LOG2_HALT              ; If domain error (ERR set), abort without pushing
    HALT AL
LOG2_HALT:
    HALT

LOG2_CORE:
    CALL CONV_F32_F64_CORE          ; AX <- float64(AL)
    CALL LOG2_F64_CORE              ; AX <- log2(AX)
    JNZ ERR, .log2_f32_err          ; If domain error, abort
    CALL CONV_F64_F32_CORE          ; AL <- float32(AX)
.log2_f32_err:
    RET
