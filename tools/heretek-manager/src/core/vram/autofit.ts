import { weightBytes, QUANT_BPW } from "./quant.js";
import { kvCacheBytes, computeScratchBytes } from "./kv.js";
import { gpuSplit, type GpuSpec } from "./gpu.js";

interface MinimalArch {
  n_layer: number; n_embd: number; n_head: number; n_head_kv: number;
  training_ctx: number; params: number;
  n_full_attn_layers?: number; head_dim?: number; n_mtp?: number;
}

interface MinimalInputs {
  quant: string; n_ctx: number; cache_dtype: string; flash_attn: boolean;
  gpu_vram_gb: number[]; safety_margin_pct: number;
  n_batch?: number; n_ubatch?: number;
}

interface EstimateResult { total_bytes: number; gpu?: { all_fit: boolean }; }

function minimalEstimate(arch: MinimalArch, inp: MinimalInputs): EstimateResult {
  const w = weightBytes(arch.params, inp.quant);
  const kv = kvCacheBytes({ n_layer: arch.n_layer, n_embd: arch.n_embd, n_head: arch.n_head, n_head_kv: arch.n_head_kv, n_ctx: inp.n_ctx, cache_dtype: inp.cache_dtype, n_mtp: arch.n_mtp, flash_attn: inp.flash_attn, n_full_attn_layers: arch.n_full_attn_layers, head_dim_override: arch.head_dim });
  const sc = computeScratchBytes({ n_layer: arch.n_layer, n_embd: arch.n_embd, n_head: arch.n_head, n_head_kv: arch.n_head_kv, n_ctx: inp.n_ctx, cache_dtype: inp.cache_dtype, n_batch: inp.n_batch ?? 512, compute_dtype: "f16", flash_attn: inp.flash_attn, n_mtp: arch.n_mtp, n_ubatch: inp.n_ubatch, n_full_attn_layers: arch.n_full_attn_layers, head_dim_override: arch.head_dim });
  const sub = w + kv + sc;
  const margin = sub * (inp.safety_margin_pct / 100);
  const total = sub + margin;
  const gpu = gpuSplit({ gpu_specs: inp.gpu_vram_gb.map(v => ({ vram_gb: v })), weights_bytes: w, kv_bytes: kv, scratch_bytes: sc });
  return { total_bytes: total, gpu };
}

function fits(r: EstimateResult): boolean { return r.gpu?.all_fit ?? false; }

export interface MaxContextResult { n_ctx: number; total_bytes: number; fits: boolean; note: string; }

export function maxContext(arch: MinimalArch, inp: MinimalInputs, opts?: { step?: number; max_ctx?: number }): MaxContextResult {
  const step = opts?.step ?? 512;
  const hi = opts?.max_ctx ?? Math.max(arch.training_ctx, inp.n_ctx, step) * 4;
  const lo = step;
  const bdMin = minimalEstimate(arch, { ...inp, n_ctx: lo });
  if (!fits(bdMin)) return { n_ctx: lo, total_bytes: bdMin.total_bytes, fits: false, note: "Even minimum doesn't fit." };
  const bdHi = minimalEstimate(arch, { ...inp, n_ctx: hi });
  if (fits(bdHi)) return { n_ctx: hi, total_bytes: bdHi.total_bytes, fits: true, note: "Max fits." };
  let best = lo, bestTotal = bdMin.total_bytes;
  let l = lo, h = hi;
  while (l <= h) {
    let mid = Math.floor((l + h) / 2);
    mid = Math.floor(mid / step) * step;
    if (mid < step) mid = step;
    const bd = minimalEstimate(arch, { ...inp, n_ctx: mid });
    if (fits(bd)) { best = mid; bestTotal = bd.total_bytes; l = mid + step; }
    else h = mid - step;
  }
  return { n_ctx: best, total_bytes: bestTotal, fits: true, note: "" };
}

export interface BestQuantResult { quant: string; bpw: number; total_bytes: number; fits: boolean; note: string; }

export function bestQuant(arch: MinimalArch, inp: MinimalInputs): BestQuantResult {
  const ordered = Object.entries(QUANT_BPW).sort((a, b) => b[1] - a[1]);
  for (const [q, bpw] of ordered) {
    const bd = minimalEstimate(arch, { ...inp, quant: q });
    if (fits(bd)) return { quant: q, bpw, total_bytes: bd.total_bytes, fits: true, note: "" };
  }
  return { quant: "", bpw: 0, total_bytes: 0, fits: false, note: "No quant fits." };
}

export interface MinGpuResult { n_gpus: number; subset: number[]; total_bytes: number; fits: boolean; note: string; }

export function minGpuSetup(arch: MinimalArch, inp: MinimalInputs): MinGpuResult {
  const sorted = [...inp.gpu_vram_gb].sort((a, b) => b - a);
  for (let k = 1; k <= sorted.length; k++) {
    const subset = sorted.slice(0, k);
    const bd = minimalEstimate(arch, { ...inp, gpu_vram_gb: subset });
    if (fits(bd)) return { n_gpus: k, subset, total_bytes: bd.total_bytes, fits: true, note: `Fits on ${k} GPU(s).` };
  }
  return { n_gpus: sorted.length, subset: sorted, total_bytes: 0, fits: false, note: "Doesn't fit." };
}
