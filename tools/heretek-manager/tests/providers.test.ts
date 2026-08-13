import { describe, it, expect } from "vitest";
import type { AIProvider, Model } from "../src/providers/types.js";

describe("AIProvider interface", () => {
  it("openai provider implements interface", async () => {
    const { OpenAIProvider } = await import("../src/providers/openai.js");
    const provider = new OpenAIProvider({ apiKey: "test-key" });
    expect(provider.id).toBe("openai");
    expect(provider.name).toBe("OpenAI");
    expect(provider.type).toBe("openai");
    expect(typeof provider.listModels).toBe("function");
    expect(typeof provider.chat).toBe("function");
    expect(typeof provider.health).toBe("function");
  });

  it("ollama provider implements interface", async () => {
    const { OllamaProvider } = await import("../src/providers/ollama.js");
    const provider = new OllamaProvider({ baseUrl: "http://localhost:11434" });
    expect(provider.id).toBe("ollama");
    expect(provider.type).toBe("ollama");
    expect(typeof provider.listModels).toBe("function");
  });

  it("local provider implements interface", async () => {
    const { LocalProvider } = await import("../src/providers/local.js");
    const provider = new LocalProvider({ binaryPath: "/usr/local/bin/llama-server" });
    expect(provider.id).toBe("local");
    expect(provider.type).toBe("local");
  });
});
