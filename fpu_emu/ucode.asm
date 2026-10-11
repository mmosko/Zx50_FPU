; =======================
; Top-level include of all microcode source

.include "asm/add_f32.asm"
.include "asm/add_f64.asm"
.include "asm/add_i32.asm"
.include "asm/add_u32.asm"
.include "asm/add_i64.asm"
.include "asm/add_u64.asm"

.include "asm/sub_f32.asm"
.include "asm/sub_f64.asm"
.include "asm/sub_i32.asm"
.include "asm/sub_u32.asm"
.include "asm/sub_i64.asm"
.include "asm/sub_u64.asm"

.include "asm/mul_f32.asm"
.include "asm/mul_f64.asm"
.include "asm/mul_int.asm"

.include "asm/div_f32.asm"
.include "asm/div_f64.asm"
.include "asm/div_int.asm"

.include "asm/sqrt_f32.asm"
.include "asm/log2_f32.asm"
.include "asm/exp2_f32.asm"
.include "asm/pow_f32.asm"
.include "asm/trig_f32.asm"

.include "asm/chs_f32.asm"
.include "asm/chs_f64.asm"
.include "asm/chs_i32.asm"
.include "asm/chs_i64.asm"

.include "asm/abs_f32.asm"
.include "asm/abs_f64.asm"
.include "asm/abs_i32.asm"
.include "asm/abs_i64.asm"

.include "asm/dup4.asm"
.include "asm/dup8.asm"

.include "asm/conv_i32_i64.asm"
.include "asm/conv_i64_i32.asm"
.include "asm/conv_u32_u64.asm"
.include "asm/conv_u32_i32.asm"
.include "asm/conv_int_f32.asm"
.include "asm/conv_f32_i32.asm"
.include "asm/floor_ceil_f32.asm"
.include "asm/floor_ceil_f64.asm"

.include "asm/push_const.asm"
.include "asm/cp_mem.asm"

; --- Shared Subroutines ---
.include "asm/pop_two_32.asm"
.include "asm/pop_two_64.asm"
.include "asm/align_f32.asm"
.include "asm/align_f64.asm"
.include "asm/normalize_f32.asm"
.include "asm/normalize_f64.asm"
