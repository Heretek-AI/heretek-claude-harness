export interface GpuSpec {
  vram_gb: number;
  name?: string;
  is_unified?: boolean;
}

export interface GpuAssignment {
  index: number;
  vram_bytes: number;
  name: string;
  is_unified: boolean;
  weight_bytes: number;
  kv_compute_bytes: number;
  used_bytes: number;
  free_bytes: number;
  fits: boolean;
  role: string;
}

export interface GpuSplitResult {
  assignments: GpuAssignment[];
  total_vram_bytes: number;
  total_used_bytes: number;
  total_weights_bytes: number;
  total_kv_compute_bytes: number;
  all_fit: boolean;
  split_mode: string;
  main_gpu_index: number;
  warnings: string[];
}

function normalizeShares(ratios: number[], n: number): number[] {
  let s = ratios.slice(0, n);
  while (s.length < n) s.push(0);
  const tot = s.reduce((a, b) => a + b, 0);
  if (tot <= 0) return Array(n).fill(1 / n);
  return s.map(x => x / tot);
}

export interface GpuSplitParams {
  gpu_specs?: GpuSpec[];
  gpu_vram_bytes?: number[];
  weights_bytes: number;
  kv_bytes: number;
  scratch_bytes?: number;
  split_mode?: string;
  main_gpu?: number;
  tensor_split?: number[];
  cache_dtype_quantized?: boolean;
}

export function gpuSplit(params: GpuSplitParams): GpuSplitResult {
  const specs: GpuSpec[] = params.gpu_specs ?? (params.gpu_vram_bytes ?? []).map(v => ({ vram_gb: v / (1 << 30) }));
  if (!specs.length) return { assignments: [], total_vram_bytes: 0, total_used_bytes: 0, total_weights_bytes: 0, total_kv_compute_bytes: 0, all_fit: false, split_mode: "layer", main_gpu_index: 0, warnings: [] };

  const warns: string[] = [];
  if (specs.some(s => s.is_unified)) warns.push("One or more devices is unified memory");

  const n = specs.length;
  const gpus = specs.map(s => ({ vram: Math.round(s.vram_gb * (1 << 30)), unified: s.is_unified ?? false, name: s.name ?? "" }));
  const totalVram = gpus.reduce((a, g) => a + g.vram, 0);
  const mainGpu = (params.main_gpu ?? 0) >= 0 && (params.main_gpu ?? 0) < n ? (params.main_gpu ?? 0) : 0;
  const mode = params.split_mode ?? "layer";

  if (mode === "none") {
    const used = params.weights_bytes + params.kv_bytes + (params.scratch_bytes ?? 0);
    const assignments = gpus.map((g, i) => ({
      index: i, vram_bytes: g.vram, name: g.name, is_unified: g.unified,
      weight_bytes: i === mainGpu ? params.weights_bytes : 0,
      kv_compute_bytes: i === mainGpu ? params.kv_bytes : 0,
      used_bytes: i === mainGpu ? used : 0,
      free_bytes: i === mainGpu ? g.vram - used : g.vram,
      fits: i === mainGpu ? used <= g.vram : true,
      role: i === mainGpu ? "all (main)" : "unused",
    }));
    return { assignments, total_vram_bytes: totalVram, total_used_bytes: used, total_weights_bytes: params.weights_bytes, total_kv_compute_bytes: params.kv_bytes, all_fit: assignments.every(a => a.fits), split_mode: mode, main_gpu_index: mainGpu, warnings: warns };
  }

  // layer or tensor mode
  const shares = params.tensor_split ? normalizeShares(params.tensor_split, n) : gpus.map(g => totalVram > 0 ? g.vram / totalVram : 1 / n);
  const assignments = gpus.map((g, i) => {
    const w = params.weights_bytes * shares[i];
    const kv = params.kv_bytes * shares[i];
    const sc = i === mainGpu ? (params.scratch_bytes ?? 0) : 0;
    const used = w + kv + sc;
    return {
      index: i, vram_bytes: g.vram, name: g.name, is_unified: g.unified,
      weight_bytes: w, kv_compute_bytes: kv, used_bytes: used,
      free_bytes: g.vram - used, fits: used <= g.vram,
      role: "weights+KV" + (i === mainGpu ? "+compute" : ""),
    };
  });

  return {
    assignments, total_vram_bytes: totalVram,
    total_used_bytes: assignments.reduce((a, x) => a + x.used_bytes, 0),
    total_weights_bytes: params.weights_bytes,
    total_kv_compute_bytes: params.kv_bytes,
    all_fit: assignments.every(a => a.fits),
    split_mode: mode, main_gpu_index: mainGpu, warnings: warns,
  };
}

export function fitGpus(result: GpuSplitResult): boolean {
  return result.all_fit;
}
