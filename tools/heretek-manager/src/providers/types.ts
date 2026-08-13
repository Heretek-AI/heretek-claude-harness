export interface AIProvider {
  readonly id: string;
  readonly name: string;
  readonly type: "openai" | "local" | "ollama";

  listModels(): Promise<Model[]>;
  getModel(id: string): Promise<Model | null>;
  chat(params: ChatParams): AsyncIterable<ChatChunk>;
  health(): Promise<HealthStatus>;
  configure(settings: Record<string, unknown>): Promise<void>;
}

export interface Model {
  id: string;
  name: string;
  provider: string;
  capabilities: ("chat" | "embed" | "vision" | "tools")[];
  contextWindow: number;
  local: boolean;
}

export interface ChatParams {
  model: string;
  messages: Message[];
  temperature?: number;
  maxTokens?: number;
}

export interface Message {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ChatChunk {
  content: string;
  done: boolean;
}

export interface HealthStatus {
  status: "ok" | "error";
  message?: string;
}
