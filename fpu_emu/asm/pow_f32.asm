; ==============================================================================
; USER_POW_F32: IEEE-754 Single-Precision Power: Y^X
;
; Delegation wrapper:
;   1. Pops two float32 operands: exp (X) in BL, base (Y) in AL
;   2. Converts base (Y) to float64 and saves to SCR[18..19]
;   3. Converts exp (X) to float64 in BX
;   4. Loads base (Y) into AX
;   5. Calls POW_F64_CORE
;   6. Converts float64 result in AX to float32 in AL
;   7. Re-asserts VF if ERR set (e.g. 0^neg division-by-zero overflow)
;   8. HALT AL
; ==============================================================================

USER_POW_F32:
    CALL POP_TWO_32                 ; BL <- exp (X, TOS), AL <- base (Y, NOS)
    CALL POW_F32_CORE
    HALT AL

POW_F32_CORE:
    ; Save exp (BL) to SCR[20]
    STO 20, BL

    ; Convert base (AL) to float64 in AX
    CALL CONV_F32_F64_CORE          ; AX <- float64(base Y)
    STO 18, AX                      ; SCR[18..19] <- float64(base Y)

    ; Convert exp (X) to float64
    LD AL, 20                       ; AL <- exp X (32-bit)
    CALL CONV_F32_F64_CORE          ; AX <- float64(exp X)
    MOV BX, AX                      ; BX <- float64(exp X)

    ; Load base into AX
    LD AX, 18                       ; AX <- float64(base Y)

    ; Call POW_F64_CORE: AX = base, BX = exp
    CALL POW_F64_CORE               ; AX <- float64(base^exp)

    ; Convert float64 result to float32 in AL
    CALL CONV_F64_F32_CORE          ; AL <- float32(AX)

    ; If ERR set (0^neg), re-assert VF flag
    JNZ ERR, .pow_f32_set_vf
    RET

.pow_f32_set_vf:
    SET VF, 1
    RET
