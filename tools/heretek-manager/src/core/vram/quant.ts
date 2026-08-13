export const QUANT_BPW: Record<string, number> = {
  "Q2_K": 2.5625, "IQ2_XXS": 2.0625, "IQ2_XS": 2.3125,
  "IQ2_S": 2.5, "IQ2_M": 2.7,
  "Q3_K_S": 3.4375, "Q3_K_M": 3.84375, "Q3_K_L": 4.125,
  "IQ3_XXS": 3.0625, "IQ3_XS": 3.25, "IQ3_S": 3.5, "IQ3_M": 3.7,
  "Q4_0": 4.5, "Q4_1": 5.0, "Q4_K_S": 4.5, "Q4_K_M": 4.84375,
  "IQ4_NL": 4.5, "IQ4_XS": 4.25,
  "Q5_0": 5.5, "Q5_1": 6.0, "Q5_K_S": 5.5, "Q5_K_M": 5.6875,
  "Q6_K": 6.5625, "Q8_0": 8.5, "Q8_1": 9.0,
  "F16": 16.0, "BF16": 16.0, "F32": 32.0,
  "ROCmFP4": 4.34, "ROCmFPX": 7.08, "nvfp4": 4.5,
};

export function weightBytes(params: number, quant: string): number {
  if (!(quant in QUANT_BPW)) {
    throw new Error(`Unknown quant type: ${quant}`);
  }
  return (params * QUANT_BPW[quant]) / 8.0;
}

const _UD_BASE: Record<string, string> = {
  "Q2_K_XL": "Q2_K", "Q2_K_XS": "Q2_K", "Q3_K_XL": "Q3_K_M",
  "Q4_K_XL": "Q4_K_M", "Q5_K_XL": "Q5_K_M", "Q6_K_XL": "Q6_K",
};

export function quantFromFilename(filename: string): string | null {
  const upper = filename.toUpperCase();
  const ordered = Object.keys(QUANT_BPW).sort((a, b) => b.length - a.length);
  for (const q of ordered) {
    const re = new RegExp(`(^|[^A-Z0-9])${q}([^A-Z0-9]|$)`);
    if (re.test(upper)) return q;
  }
  for (const [udKey, base] of Object.entries(_UD_BASE)) {
    const re = new RegExp(`(^|[^A-Z0-9])${udKey}([^A-Z0-9]|$)`);
    if (re.test(upper)) return base;
  }
  return null;
}
