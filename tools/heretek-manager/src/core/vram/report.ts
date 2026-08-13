// src/core/vram/report.ts
import { weightBytes, QUANT_BPW } from "./quant.js";
import { kvCacheBytes, computeScratchBytes, cache_dtype_bytes } from "./kv.js";
import { gpuSplit, type GpuSpec } from "./gpu.js";
import { autoConfigureYarn, yarnCoherenceWarnings } from "./yarn.js";
import { draftBytes, type DraftInputs } from "./draft.js";

export interface ModelArch {
  name?: string;
  architecture?: string;
  n_layer: number;
  n_embd: number;
  n_head: number;
  n_head_kv: number;
  training_ctx: number;
  params: number;
  rope_freq_base?: number;
  n_expert?: number;
  n_expert_used?: number;
  n_mtp?: number;
  n_full_attn_layers?: number;
  head_dim?: number;
}

export interface Inputs {
  quant: string;
  n_ctx: number;
  cache_dtype: string;
  flash_attn: boolean;
  gpu_vram_gb: number[];
  safety_margin_pct: number;
  n_batch?: number;
  n_ubatch?: number;
  split_mode?: string;
  main_gpu?: number;
  tensor_split?: number[];
  draft?: DraftInputs;
  rope_freq_scale?: number;
}

export interface Breakdown {
  weights_bytes: number;
  kv_cache_bytes: number;
  compute_scratch_bytes: number;
  draft_bytes_: number;
  gguf_overhead_bytes: number;
  safety_margin_bytes: number;
  total_bytes: number;
  effective_context: number;
  warnings: string[];
  gpu?: { all_fit: boolean; assignments: Array<{ index: number; vram_bytes: number; used_bytes: number; fits: boolean }> };
}

export function estimate(arch: ModelArch, inp: Inputs): Breakdown {
  const w = weightBytes(arch.params, inp.quant);
  const kv = kvCacheBytes({ n_layer: arch.n_layer, n_embd: arch.n_embd, n_head: arch.n_head, n_head_kv: arch.n_head_kv, n_ctx: inp.n_ctx, cache_dtype: inp.cache_dtype, n_mtp: arch.n_mtp, flash_attn: inp.flash_attn, n_full_attn_layers: arch.n_full_attn_layers, head_dim_override: arch.head_dim });
  const sc = computeScratchBytes({ n_layer: arch.n_layer, n_embd: arch.n_embd, n_head: arch.n_head, n_head_kv: arch.n_head_kv, n_ctx: inp.n_ctx, cache_dtype: inp.cache_dtype, n_batch: inp.n_batch ?? 512, compute_dtype: "f16", flash_attn: inp.flash_attn, n_mtp: arch.n_mtp, n_ubatch: inp.n_ubatch, n_full_attn_layers: arch.n_full_attn_layers, head_dim_override: arch.head_dim });
  let draftTotal = 0;
  if (inp.draft) {
    const dd = draftBytes({ draft: inp.draft, target_n_ctx: inp.n_ctx, target_n_embd: arch.n_embd, target_n_head: arch.n_head, target_n_head_kv: arch.n_head_kv });
    if (dd.enabled) draftTotal = dd.total_bytes;
  }
  const ggufOverhead = Math.max(arch.n_layer * 4096, 1 << 20);
  const sub = w + kv + sc + draftTotal + ggufOverhead;
  const margin = sub * (inp.safety_margin_pct / 100);
  const total = sub + margin;
  const gpu = gpuSplit({ gpu_specs: inp.gpu_vram_gb.map(v => ({ vram_gb: v })), weights_bytes: w, kv_bytes: kv, scratch_bytes: sc + draftTotal, split_mode: inp.split_mode, main_gpu: inp.main_gpu, tensor_split: inp.tensor_split });
  const yarnCfg = autoConfigureYarn(arch.training_ctx, inp.n_ctx);
  const warns = yarnCoherenceWarnings(arch.training_ctx, inp.n_ctx);
  if (inp.n_ctx > arch.training_ctx && arch.training_ctx > 0) warns.push("YaRN scaling required.");
  return { weights_bytes: w, kv_cache_bytes: kv, compute_scratch_bytes: sc, draft_bytes_: draftTotal, gguf_overhead_bytes: ggufOverhead, safety_margin_bytes: margin, total_bytes: total, effective_context: yarnCfg.scaling ? Math.round(arch.training_ctx / yarnCfg.rope_freq_scale) : inp.n_ctx, warnings: warns, gpu };
}

export function commandPreview(arch: ModelArch, inp: Inputs): string {
  const parts = ["llama-server", `-m model-${inp.quant}.gguf`, `-c ${inp.n_ctx}`, "-ngl 999", `-b ${inp.n_batch ?? 512}`];
  if (inp.flash_attn) parts.push("--flash-attn");
  if (inp.cache_dtype !== "f16") { parts.push(`--cache-type-k ${inp.cache_dtype}`); parts.push(`--cache-type-v ${inp.cache_dtype}`); }
  if (inp.n_ctx > (arch.training_ctx || 0) && (arch.training_ctx || 0) > 0) { parts.push("--rope-scaling yarn"); const scale = Math.round((arch.training_ctx / inp.n_ctx) * 1e6) / 1e6; parts.push(`--rope-freq-scale ${scale}`); }
  if (inp.gpu_vram_gb.length > 1) { parts.push("--split-mode layer"); }
  if (inp.draft?.spec_type && inp.draft.spec_type !== "none") { parts.push(`--spec-type ${inp.draft.spec_type}`); }
  return parts.join(" \\\n  ");
}
