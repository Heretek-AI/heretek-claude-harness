import type { AIProvider, Model, ChatParams, ChatChunk, HealthStatus } from "./types.js";

export class OllamaProvider implements AIProvider {
  readonly id = "ollama";
  readonly name = "Ollama";
  readonly type = "ollama" as const;
  private baseUrl: string;

  constructor(opts: { baseUrl?: string }) {
    this.baseUrl = opts.baseUrl || "http://localhost:11434";
  }

  async listModels(): Promise<Model[]> {
    const res = await fetch(`${this.baseUrl}/api/tags`);
    if (!res.ok) return [];
    const data = (await res.json()) as { models: { name: string; size: number }[] };
    return data.models.map((m) => ({
      id: m.name,
      name: m.name,
      provider: this.id,
      capabilities: ["chat"] as const,
      contextWindow: 4096,
      local: true,
    }));
  }

  async getModel(id: string): Promise<Model | null> {
    const models = await this.listModels();
    return models.find((m) => m.id === id) || null;
  }

  async *chat(params: ChatParams): AsyncIterable<ChatChunk> {
    const res = await fetch(`${this.baseUrl}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: params.model,
        messages: params.messages.map((m) => ({ role: m.role, content: m.content })),
        stream: true,
      }),
    });

    if (!res.ok || !res.body) {
      throw new Error(`Ollama API error: ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line) continue;
        try {
          const parsed = JSON.parse(line);
          if (parsed.message?.content) {
            yield { content: parsed.message.content, done: !!parsed.done };
          }
        } catch {
          // skip malformed lines
        }
      }
    }
  }

  async health(): Promise<HealthStatus> {
    try {
      const res = await fetch(`${this.baseUrl}/api/tags`);
      return res.ok
        ? { status: "ok" }
        : { status: "error", message: `HTTP ${res.status}` };
    } catch (e) {
      return { status: "error", message: String(e) };
    }
  }

  async configure(settings: Record<string, unknown>): Promise<void> {
    if (settings.baseUrl) this.baseUrl = settings.baseUrl as string;
  }
}
