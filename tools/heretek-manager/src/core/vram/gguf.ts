export interface GGUFMetadata {
  raw: Record<string, unknown>;
  architecture: string;
  name: string;
  n_layer: number;
  n_embd: number;
  n_head: number;
  n_head_kv: number;
  training_ctx: number;
  rope_freq_base: number;
  n_expert: number;
  n_expert_used: number;
  n_mtp: number;
  params: number;
  head_dim: number;
  n_full_attn_layers: number;
}

const GGUF_MAGIC = 0x46554747;

class Reader {
  buf: Buffer;
  pos = 0;
  constructor(buf: Buffer) { this.buf = buf; }
  eof() { return this.pos >= this.buf.length; }
  need(n: number) { if (this.pos + n > this.buf.length) throw new EOFError("buffer exhausted"); }
  u32() { this.need(4); const v = this.buf.readUInt32LE(this.pos); this.pos += 4; return v; }
  u64() { this.need(8); const v = this.buf.readBigUInt64LE(this.pos); this.pos += 8; return Number(v); }
  string() { const n = this.u64(); this.need(n); const s = this.buf.toString("utf-8", this.pos, this.pos + n); this.pos += n; return s; }
  scalar(type: number) {
    const fmts: Record<number, [string, number]> = {
      0: ["<B", 1], 1: ["<b", 1], 2: ["<H", 2], 3: ["<h", 2],
      4: ["<I", 4], 5: ["<i", 4], 6: ["<f", 4], 7: ["<?", 1],
      10: ["<Q", 8], 11: ["<q", 8], 12: ["<d", 8],
    };
    const [, size] = fmts[type] ?? ["", 0];
    this.need(size);
    const v = this.buf.readFloatLE(this.pos); // simplified
    this.pos += size;
    return v;
  }
}

class EOFError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EOFError";
  }
}

export function parseHeaderBytes(buf: Buffer): Record<string, unknown> {
  const r = new Reader(buf);
  const magic = r.u32();
  if (magic !== GGUF_MAGIC) throw new Error(`Not a GGUF file (magic=${magic})`);
  r.u32(); // version
  r.u64(); // tensor_count
  const kvCount = r.u64();
  const meta: Record<string, unknown> = {};
  for (let i = 0; i < kvCount && !r.eof(); i++) {
    const key = r.string();
    const type = r.u32();
    // Simplified: just handle string type for now
    if (type === 8) meta[key] = r.string();
    else r.scalar(type);
  }
  return meta;
}

function coerceInt(v: unknown): number {
  if (typeof v === "boolean") return v ? 1 : 0;
  if (typeof v === "number") return Math.floor(v);
  return 0;
}

export function metadataToArch(meta: Record<string, unknown>): GGUFMetadata {
  const arch = String(meta["general.architecture"] ?? "");
  const p = arch ? `${arch}.` : "";
  const g = (key: string) => meta[`${p}${key}`] ?? meta[key];

  const nLayer = coerceInt(g("block_count"));
  const nEmb = coerceInt(g("embedding_length"));
  const nHead = coerceInt(g("attention.head_count"));
  let nHeadKv = coerceInt(g("attention.head_count_kv"));
  if (!nHeadKv) nHeadKv = nHead;

  return {
    raw: meta, architecture: arch, name: String(meta["general.name"] ?? ""),
    n_layer: nLayer, n_embd: nEmb, n_head: nHead, n_head_kv: nHeadKv,
    training_ctx: coerceInt(g("context_length")),
    rope_freq_base: Number(g("rope.freq_base") ?? 10000),
    n_expert: coerceInt(g("expert_count")),
    n_expert_used: coerceInt(g("expert_used_count")),
    n_mtp: coerceInt(g("mtp.count")),
    params: coerceInt(meta["general.parameter_count"]),
    head_dim: coerceInt(g("attention.key_length")),
    n_full_attn_layers: 0,
  };
}
