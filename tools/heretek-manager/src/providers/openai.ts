import type { AIProvider, Model, ChatParams, ChatChunk, HealthStatus } from "./types.js";

export class OpenAIProvider implements AIProvider {
  readonly id = "openai";
  readonly name = "OpenAI";
  readonly type = "openai" as const;
  private apiKey: string;
  private baseUrl: string;

  constructor(opts: { apiKey: string; baseUrl?: string }) {
    this.apiKey = opts.apiKey;
    this.baseUrl = opts.baseUrl || "https://api.openai.com/v1";
  }

  async listModels(): Promise<Model[]> {
    const res = await fetch(`${this.baseUrl}/models`, {
      headers: { Authorization: `Bearer ${this.apiKey}` },
    });
    if (!res.ok) return [];
    const data = (await res.json()) as { data: { id: string }[] };
    return data.data.map((m) => ({
      id: m.id,
      name: m.id,
      provider: this.id,
      capabilities: ["chat", "tools"] as const,
      contextWindow: 128000,
      local: false,
    }));
  }

  async getModel(id: string): Promise<Model | null> {
    const models = await this.listModels();
    return models.find((m) => m.id === id) || null;
  }

  async *chat(params: ChatParams): AsyncIterable<ChatChunk> {
    const res = await fetch(`${this.baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: params.model,
        messages: params.messages,
        temperature: params.temperature,
        max_tokens: params.maxTokens,
        stream: true,
      }),
    });

    if (!res.ok || !res.body) {
      throw new Error(`OpenAI API error: ${res.status}`);
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
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6);
        if (data === "[DONE]") {
          yield { content: "", done: true };
          return;
        }
        try {
          const parsed = JSON.parse(data);
          const content = parsed.choices?.[0]?.delta?.content || "";
          if (content) yield { content, done: false };
        } catch {
          // skip malformed lines
        }
      }
    }
  }

  async health(): Promise<HealthStatus> {
    try {
      const res = await fetch(`${this.baseUrl}/models`, {
        headers: { Authorization: `Bearer ${this.apiKey}` },
      });
      return res.ok
        ? { status: "ok" }
        : { status: "error", message: `HTTP ${res.status}` };
    } catch (e) {
      return { status: "error", message: String(e) };
    }
  }

  async configure(settings: Record<string, unknown>): Promise<void> {
    if (settings.apiKey) this.apiKey = settings.apiKey as string;
    if (settings.baseUrl) this.baseUrl = settings.baseUrl as string;
  }
}
