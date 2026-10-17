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
  if (!response.ok)
    throw Error(
      typeof value.detail === "string"
        ? value.detail
        : "Request could not be completed",
    );
  return value;
}
export const send = (path, body) =>
  api(path, { method: "POST", body: JSON.stringify(body) });
