// ModelHop JS/TS client (generated from OpenAPI spec, v1.1 W2).
// Works against POST /v1/chat/completions with model="auto".

export interface ChatMessage {
  role: string;
  content: string;
}

export interface ChatCompletionOptions {
  baseUrl?: string;
  apiKey?: string;
  model?: string;
  stream?: boolean;
}

export async function chatCompletions(
  messages: ChatMessage[],
  opts: ChatCompletionOptions = {}
): Promise<string> {
  const baseUrl = (opts.baseUrl || "http://localhost:8000").replace(/\/$/, "");
  const res = await fetch(`${baseUrl}/v1/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(opts.apiKey ? { Authorization: `Bearer ${opts.apiKey}` } : {}),
    },
    body: JSON.stringify({ model: opts.model || "auto", messages, stream: false }),
  });
  if (!res.ok) throw new Error(`ModelHop error ${res.status}: ${await res.text()}`);
  const data = await res.json();
  return data.choices?.[0]?.message?.content || "";
}

export async function listModels(baseUrl = "http://localhost:8000", apiKey?: string) {
  const res = await fetch(`${baseUrl.replace(/\/$/, "")}/v1/models`, {
    headers: apiKey ? { Authorization: `Bearer ${apiKey}` } : {},
  });
  if (!res.ok) throw new Error(`ModelHop error ${res.status}`);
  return res.json();
}
