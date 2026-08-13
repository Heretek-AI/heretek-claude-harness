export interface YarnConfig {
  rope_freq_scale: number;
  yarn_ext_factor: number;
  yarn_attn_factor: number;
  yarn_beta_fast: number;
  yarn_beta_slow: number;
  scaling: boolean;
  note: string;
}

export function autoConfigureYarn(trainingCtx: number, targetNCtx: number): YarnConfig {
  const defaults: YarnConfig = {
    rope_freq_scale: 1.0, yarn_ext_factor: -1.0, yarn_attn_factor: 1.0,
    yarn_beta_fast: 32.0, yarn_beta_slow: 1.0, scaling: false, note: "",
  };
  if (!targetNCtx || targetNCtx <= 0) return { ...defaults, note: "Invalid target context." };
  if (!trainingCtx || trainingCtx <= 0) return { ...defaults, note: "Training context unknown." };
  if (targetNCtx <= trainingCtx) return { ...defaults, note: "No YaRN scaling needed." };
  const scale = Math.round((trainingCtx / targetNCtx) * 1e6) / 1e6;
  return {
    ...defaults,
    rope_freq_scale: scale,
    scaling: true,
    note: `rope_freq_scale=${scale} for ${(targetNCtx / trainingCtx).toFixed(1)}x extension.`,
  };
}

export function yarnEffectiveContext(trainingCtx: number, ropeFreqScale: number): number {
  if (ropeFreqScale <= 0) return trainingCtx;
  return Math.round(trainingCtx / ropeFreqScale);
}

export function extensionRatio(trainingCtx: number, targetNCtx: number): number {
  if (!trainingCtx || trainingCtx <= 0 || targetNCtx <= 0 || targetNCtx <= trainingCtx) return 1.0;
  return targetNCtx / trainingCtx;
}

const _YARN_FINE_RATIO = 2.0;
const _YARN_BAD_RATIO = 8.0;

export function yarnCoherenceWarnings(trainingCtx: number, targetNCtx: number): string[] {
  if (trainingCtx <= 0 || targetNCtx <= 0 || targetNCtx <= trainingCtx) return [];
  const ratio = targetNCtx / trainingCtx;
  if (ratio >= _YARN_BAD_RATIO) return [`Target context ${targetNCtx} is ${ratio.toFixed(1)}x training ${trainingCtx}. Likely incoherent at long range.`];
  if (ratio > _YARN_FINE_RATIO) return [`Target context ${targetNCtx} is ${ratio.toFixed(1)}x training ${trainingCtx}. Expect quality degradation at tail.`];
  return [];
}
