import { appConfig } from "./config";

export interface ApiErrorShape {
  code: string;
  message_key: string;
  retryable: boolean;
  correlation_id?: string;
  field_errors?: Record<string, string[]>;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: ApiErrorShape,
  ) {
    super(detail.message_key);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${appConfig.apiUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let detail: ApiErrorShape = {
      code: "http_error",
      message_key: `errors.http.${response.status}`,
      retryable: response.status >= 500,
      correlation_id: response.headers.get("x-correlation-id") || undefined,
    };
    try {
      detail = { ...detail, ...(await response.json()) };
    } catch {
      // Stable fallback intentionally ignores non-JSON error bodies.
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
