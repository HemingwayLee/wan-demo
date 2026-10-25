async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, options);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(errorDetail(body) ?? `${res.status} ${res.statusText}`);
  }
  return res.status === 204 ? null : res.json();
}

function errorDetail(body) {
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) return body.detail.map((d) => `${d.loc?.at(-1)}: ${d.msg}`).join(", ");
  return null;
}

export const api = {
  comfyui: () => request("/comfyui"),
  listJobs: () => request("/jobs"),
  cancelJob: (id) => request(`/jobs/${id}/cancel`, { method: "POST" }),
  deleteJob: (id) => request(`/jobs/${id}`, { method: "DELETE" }),
};

/**
 * Upload the character image + motion video and create a job.
 * Uses XHR rather than fetch so large videos can report upload progress (0–1) via onProgress.
 */
export function createJob({ image, video, ...fields }, { onProgress } = {}) {
  const form = new FormData();
  form.append("image", image);
  form.append("video", video);
  for (const [key, value] of Object.entries(fields)) {
    if (value !== null && value !== undefined && value !== "") form.append(key, value);
  }
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/jobs");
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
    xhr.onload = () =>
      xhr.status < 300
        ? resolve(xhr.response)
        : reject(new Error(errorDetail(xhr.response) ?? `${xhr.status} ${xhr.statusText}`));
    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.send(form);
  });
}

export const jobFileUrl = (id, kind, { download = false } = {}) =>
  `/api/jobs/${id}/files/${kind}${download ? "?download=true" : ""}`;

export const ACTIVE_STATUSES = ["queued", "preparing", "running"];
