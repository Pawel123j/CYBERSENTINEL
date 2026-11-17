export interface HealthResponse {
  endpoint: string;
  statusCode: number;
  checkedAt: string;
  payload: unknown;
}

export class HealthEndpointError extends Error {
  readonly statusCode: number;
  readonly payload: unknown;

  constructor(statusCode: number, payload: unknown) {
    super(`Endpoint returned HTTP ${statusCode}`);
    this.name = "HealthEndpointError";
    this.statusCode = statusCode;
    this.payload = payload;
  }
}

function parseResponseBody(body: string): unknown {
  if (body.length === 0) {
    return null;
  }

  try {
    return JSON.parse(body) as unknown;
  } catch {
    return body;
  }
}

export async function fetchHealth(
  endpoint: string,
  signal: AbortSignal
): Promise<HealthResponse> {
  const response = await fetch(endpoint, {
    signal,
    headers: {
      Accept: "application/json",
    },
  });
  const payload = parseResponseBody(await response.text());

  if (!response.ok) {
    throw new HealthEndpointError(response.status, payload);
  }

  return {
    endpoint,
    statusCode: response.status,
    checkedAt: new Date().toISOString(),
    payload,
  };
}
