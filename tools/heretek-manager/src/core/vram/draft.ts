// src/core/vram/draft.ts
import { weightBytes } from "./quant.js";
import { kvCacheBytes } from "./kv.js";

export const SPEC_TYPES = [
  "none", "draft-simple", "draft-eagle3", "draft-mtp", "draft-dflash",
  "ngram-simple", "ngram-map-k", "ngram-map-k4v", "ngram-mod", "ngram-cache",
] as const;

export const WEIGHTLESS_SPEC_TYPES = ["ngram-simple", "ngram-map-k", "ngram-map-k4v", "ngram-mod", "ngram-cache"] as const;
export const WEIGHTED_SPEC_TYPES = ["draft-simple", "draft-eagle3", "draft-mtp", "draft-dflash"] as const;

export function isWeightless(specType: string): boolean {
  return (WEIGHTLESS_SPEC_TYPES as readonly string[]).includes(specType);
}

export function isWeighted(specType: string): boolean {
  return (WEIGHTED_SPEC_TYPES as readonly string[]).includes(specType);
}

export interface DraftInputs {
  spec_type: string;
  quant: string;
  params: number;
  n_layer: number;
  n_ctx?: number | null;
  cache_dtype: string;
  n_embd?: number;
  n_head?: number;
  n_head_kv?: number;
  n_max?: number;
  n_min?: number;
}

export interface DraftBreakdown {
  weights_bytes: number;
  kv_bytes: number;
  total_bytes: number;
  enabled: boolean;
}

export function draftBytes(opts: {
  draft: DraftInputs;
  target_n_ctx: number;
  target_n_embd: number;
  target_n_head: number;
  target_n_head_kv: number;
}): DraftBreakdown {
  const { draft, target_n_ctx, target_n_embd, target_n_head, target_n_head_kv } = opts;
  if (draft.spec_type === "none") return { weights_bytes: 0, kv_bytes: 0, total_bytes: 0, enabled: false };
  if (isWeightless(draft.spec_type)) return { weights_bytes: 0, kv_bytes: 0, total_bytes: 0, enabled: true };

  const w = weightBytes(draft.params, draft.quant);
  const nEmb = draft.n_embd || target_n_embd;
  const nHead = draft.n_head || target_n_head;
  const nHeadKv = draft.n_head_kv || nHead;
  const nCtx = draft.n_ctx ?? target_n_ctx;
  let kv = 0;
  try {
    kv = kvCacheBytes({ n_layer: Math.max(1, draft.n_layer), n_embd: nEmb, n_head: Math.max(1, nHead), n_head_kv: Math.max(1, nHeadKv), n_ctx: nCtx, cache_dtype: draft.cache_dtype });
  } catch { kv = 0; }
  return { weights_bytes: w, kv_bytes: kv, total_bytes: w + kv, enabled: true };
}
