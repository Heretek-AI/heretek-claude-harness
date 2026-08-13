import type { AIProvider, Model, ChatParams, ChatChunk, HealthStatus } from "./types.js";
import { execSync } from "child_process";

export class LocalProvider implements AIProvider {
  readonly id = "local";
  readonly name = "Local llama.cpp";
  readonly type = "local" as const;
  private binaryPath: string;

  constructor(opts: { binaryPath: string }) {
    this.binaryPath = opts.binaryPath;
  }

  async listModels(): Promise<Model[]> {
    // Detect GGUF files in common locations
    return [];
  }

  async getModel(_id: string): Promise<Model | null> {
    return null;
  }

  async *chat(_params: ChatParams): AsyncIterable<ChatChunk> {
    // TODO: spawn llama-server process and connect via HTTP
    yield { content: "Local provider not yet implemented", done: true };
  }

  async health(): Promise<HealthStatus> {
    try {
      execSync(`test -x ${this.binaryPath}`);
      return { status: "ok" };
    } catch {
      return { status: "error", message: `Binary not found: ${this.binaryPath}` };
    }
  }

  async configure(settings: Record<string, unknown>): Promise<void> {
    if (settings.binaryPath) this.binaryPath = settings.binaryPath as string;
  }
}
