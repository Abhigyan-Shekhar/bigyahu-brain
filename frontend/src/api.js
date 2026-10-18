export async function api(path, options = {}) {
  const response = await fetch("/api" + path, {
    ...options,
    headers: {
      Authorization:
        "Bearer " + (sessionStorage.getItem("company-brain-token") || ""),
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  const value = await response.json();
  if (!response.ok) {
    const error = Error(
      typeof value.detail === "string"
        ? value.detail
        : "Request could not be completed",
    );
    error.status = response.status;
    throw error;
  }
  return value;
}
export const send = (path, body) =>
  api(path, { method: "POST", body: JSON.stringify(body) });

// Fetch preserves bearer authentication without putting the token in an SSE URL.
export async function consumeSnapshots(response, onSnapshot) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      buffer = buffer.replaceAll("\r\n", "\n");
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const event = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        if (event.split("\n").some((line) => line === "event: snapshot")) {
          const data = event
            .split("\n")
            .filter((line) => line.startsWith("data:"))
            .map((line) => line.slice(5).trimStart())
            .join("\n");
          onSnapshot(JSON.parse(data));
        }
      }
      if (buffer.length > 4_000_000)
        throw Error("Stream event exceeds size limit");
      if (done) {
        if (buffer.trim()) throw Error("Stream ended with an incomplete event");
        return;
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export function watchResource(
  eventsPath,
  fallbackPath,
  onValue,
  onError = () => {},
) {
  const controller = new AbortController();
  let timer;
  const run = async () => {
    while (!controller.signal.aborted) {
      try {
        let latest;
        const response = await fetch("/api" + eventsPath, {
          headers: {
            Authorization:
              "Bearer " + (sessionStorage.getItem("company-brain-token") || ""),
            Accept: "text/event-stream",
          },
          signal: controller.signal,
        });
        if (
          !response.ok ||
          !response.headers.get("content-type")?.includes("text/event-stream")
        )
          throw Error("Live connection unavailable");
        await consumeSnapshots(response, (value) => {
          latest = value;
          if (!controller.signal.aborted) onValue(value);
        });
        if (
          latest &&
          !Array.isArray(latest) &&
          !["queued", "running"].includes(latest.status)
        )
          return;
        throw Error("Live connection interrupted");
      } catch (error) {
        if (controller.signal.aborted) return;
        // Poll once during reconnect so a lost stream cannot hide a finished job.
        try {
          const value = await api(fallbackPath, { signal: controller.signal });
          if (!controller.signal.aborted) onValue(value);
          if (
            !Array.isArray(value) &&
            !["queued", "running"].includes(value.status)
          )
            return;
        } catch (fallbackError) {
          if (!controller.signal.aborted) onError(fallbackError);
        }
        await new Promise((resolve) => {
          const finish = () => {
            clearTimeout(timer);
            controller.signal.removeEventListener("abort", finish);
            resolve();
          };
          timer = setTimeout(finish, 1500);
          controller.signal.addEventListener("abort", finish, { once: true });
          if (controller.signal.aborted) finish();
        });
      }
    }
  };
  run();
  return () => {
    controller.abort();
    clearTimeout(timer);
  };
}
