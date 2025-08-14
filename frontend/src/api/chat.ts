export async function streamChat(
  messages: { role: string; content: string }[],
  model?: string,
  onToken?: (t: string) => void,
): Promise<void> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, model, stream: true }),
  });
  if (!res.body) return;

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let done = false;

  while (!done) {
    // eslint-disable-next-line no-await-in-loop
    const readResult = await reader.read();
    done = readResult.done ?? false;
    if (done) break;

    const chunk = decoder.decode(readResult.value, { stream: true });
    buffer += chunk;

    let idx = buffer.indexOf("\n\n");
    while (idx !== -1) {
      const eventChunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);

      const lines = eventChunk.split("\n");
      let data = "";
      for (const line of lines) {
        if (line.startsWith("data:")) {
          data += line.slice(5).trimStart();
        }
      }
      if (data && onToken) onToken(data);

      idx = buffer.indexOf("\n\n");
    }
  }
}

export async function startImageJob(prompt: string): Promise<string> {
  const res = await fetch("/api/generate-image", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
  const j = await res.json();
  return j.job_id as string;
}

export async function startVideoJob(prompt: string): Promise<string> {
  const res = await fetch("/api/generate-video", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
  const j = await res.json();
  return j.job_id as string;
}

export type JobStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
export interface JobResponse {
  id: string;
  status: JobStatus;
  result?: { path?: string };
  error?: string;
}

export async function getJob(jobId: string): Promise<JobResponse> {
  const res = await fetch(`/api/jobs/${jobId}`);
  return res.json();
}
