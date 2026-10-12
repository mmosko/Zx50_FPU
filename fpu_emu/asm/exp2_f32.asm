; ==============================================================================
; EXP2_F32: IEEE-754 Single-Precision Base-2 Exponential: 2^X
;
; Opcode 0x2A: EXP2_F32 (x -- 2^x)
;
; Delegates to EXP2_F64_CORE via precision conversion:
;   x_f32 -> conv_f32_f64 -> exp2_f64 -> conv_f64_f32 -> result_f32
;
; Subroutines Called:
;   POP_ONE_32, CONV_F32_F64_CORE, EXP2_F64_CORE, CONV_F64_F32_CORE
; ==============================================================================

USER_EXP2_F32:
    CALL POP_ONE_32                 ; AL <- X (TOS)
    CALL EXP2_CORE                  ; AL <- 2^AL
    HALT AL

EXP2_CORE:
    CALL CONV_F32_F64_CORE          ; AX <- (f64) AL
    CALL EXP2_F64_CORE              ; AX <- 2^AX
    CALL CONV_F64_F32_CORE          ; AL <- (f32) AX
    RET
