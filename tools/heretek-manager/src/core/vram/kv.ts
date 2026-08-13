export const CACHE_DTYPE_BYTES: Record<string, number> = {
  f16: 2.0, bf16: 2.0, f32: 4.0,
  q8_0: 1.0, q8_1: 1.0625,
  q4_0: 0.5, q4_1: 0.5625,
  q5_0: 0.625, q5_1: 0.6875,
};

export const COMPUTE_DTYPE_BYTES: Record<string, number> = {
  f16: 2.0, bf16: 2.0, f32: 4.0,
};

export function cache_dtype_bytes(dtype: string): number {
  if (!(dtype in CACHE_DTYPE_BYTES)) throw new Error(`Unknown cache dtype: ${dtype}`);
  return CACHE_DTYPE_BYTES[dtype];
}

interface KvParams {
  n_layer: number; n_embd: number; n_head: number; n_head_kv: number;
  n_ctx: number; cache_dtype: string; n_mtp?: number;
  flash_attn?: boolean; n_full_attn_layers?: number; head_dim_override?: number;
}

export function kvCacheBytes(p: KvParams): number {
  const headDim = p.head_dim_override || Math.floor(p.n_embd / p.n_head);
  const perLayer = p.n_ctx * 2 * p.n_head_kv * headDim * cache_dtype_bytes(p.cache_dtype);
  const layers = (p.n_full_attn_layers || p.n_layer) + Math.max(0, p.n_mtp ?? 0);
  return perLayer * layers;
}

interface ScratchParams extends KvParams {
  n_batch: number; compute_dtype: string;
  n_ubatch?: number; n_vocab?: number;
}

export function computeScratchBytes(p: ScratchParams): number {
  const cb = COMPUTE_DTYPE_BYTES[p.compute_dtype];
  if (cb === undefined) throw new Error(`Unknown compute dtype: ${p.compute_dtype}`);
  const ub = p.n_ubatch ?? p.n_batch;
  const headDim = p.head_dim_override || Math.floor(p.n_embd / p.n_head);
  const layers = (p.n_full_attn_layers || p.n_layer) + Math.max(0, p.n_mtp ?? 0);
  const activations = ub * p.n_embd * cb * 2;
  let scratch = 0;
  if (!p.flash_attn && !(p.cache_dtype in { f16: 1, bf16: 1, f32: 1 })) {
    scratch = layers * ub * 2 * p.n_head_kv * headDim * 4.0;
  }
  let logits = 0;
  if (p.n_vocab && p.n_vocab > 0) {
    logits = p.n_batch * p.n_vocab * cb;
  }
  return activations + scratch + logits;
}
