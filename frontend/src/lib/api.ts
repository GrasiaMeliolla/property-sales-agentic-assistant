const API_BASE = process.env.NEXT_PUBLIC_API_URL || (
  typeof window !== "undefined"
    ? "http://localhost:8000"
    : "http://backend:8000"
);

export interface ConversationResponse {
  id: string;
  status: string;
  context: Record<string, unknown>;
  created_at: string;
}

export interface ProjectSummary {
  id: string;
  project_name: string;
  city: string | null;
  country: string | null;
  price_usd: number | null;
  bedrooms: number | null;
  property_type: string | null;
}

export interface ChatResponse {
  response: string;
  conversation_id: string;
  recommended_projects: ProjectSummary[] | null;
  metadata: {
    intent: string;
    booking_confirmed: boolean;
  } | null;
}

export async function createConversation(): Promise<ConversationResponse> {
  const response = await fetch(`${API_BASE}/api/conversations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error("Failed to create conversation");
  }

  return response.json();
}

export async function sendMessage(
  conversationId: string,
  message: string
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/api/agents/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      conversation_id: conversationId,
      message,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to send message");
  }

  return response.json();
}

export interface StreamChunk {
  type: "content" | "properties" | "intent" | "done" | "error";
  data: unknown;
}

export async function* sendMessageStream(
  conversationId: string,
  message: string
): AsyncGenerator<StreamChunk> {
  const response = await fetch(`${API_BASE}/api/agents/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      conversation_id: conversationId,
      message,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to send message");
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("No response body");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          yield data as StreamChunk;
        } catch {
          // Skip invalid JSON
        }
      }
    }
  }
}
