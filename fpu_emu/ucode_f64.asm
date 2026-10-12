; =======================
; Top-level include of all microcode source

.include "ucode.asm"

; include the extended F64 functions that do not fit in normal EBR
.include "asm/conv_f32_f64.asm"
.include "asm/conv_f64_f32.asm"


