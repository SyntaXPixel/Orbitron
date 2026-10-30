import type {
  CreateDisruptionEventRequest,
  CreateJobRequest,
  CreateTransferRequest,
  HealthResponse,
  Job,
  LoginRequest,
  Operation,
  RunEvaluationRequest,
  RunScheduleRequest,
  RunSecurityCheckRequest,
  Session,
  SimulationActionRequest,
  Snapshot,
} from "./types";
import { ApiClientError } from "../utils/errors";

export const EXPECTED_CONTRACT_VERSION = "orbitron.v1";

export const API_BASE_URL =
  (import.meta.env?.VITE_API_BASE_URL as string) || "http://localhost:8000/api/v1";

let inMemoryCsrfToken: string | null = null;
let contractMismatchDetected = false;

export function getCsrfToken(): string | null {
  return inMemoryCsrfToken;
}

export function setCsrfToken(token: string | null): void {
  inMemoryCsrfToken = token;
}

export function isContractMismatch(): boolean {
  return contractMismatchDetected;
}

export function setContractMismatch(mismatch: boolean): void {
  contractMismatchDetected = mismatch;
}

interface RequestOptions extends RequestInit {
  idempotencyKey?: string;
  skipContractCheck?: boolean;
}

export async function apiRequest<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});

  headers.set("Accept", "application/json");

  // State-changing requests attach CSRF token and idempotency key
  const method = (options.method || "GET").toUpperCase();
  const isMutation = ["POST", "PUT", "PATCH", "DELETE"].includes(method);

  if (isMutation) {
    if (inMemoryCsrfToken && !headers.has("X-CSRF-Token")) {
      headers.set("X-CSRF-Token", inMemoryCsrfToken);
    }
    if (!headers.has("Idempotency-Key")) {
      headers.set(
        "Idempotency-Key",
        options.idempotencyKey || (typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `idemp-${Date.now()}`)
      );
    }
    if (options.body && typeof options.body === "string" && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      credentials: "include",
    });
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : "Failed to connect to backend";
    throw new ApiClientError({
      message: `Network error: ${errorMsg}`,
      status: 0,
      isNetworkError: true,
    });
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as unknown as T;
  }

  // Parse response body
  let data: any;
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    try {
      data = await response.json();
    } catch {
      throw new ApiClientError({
        message: "Invalid JSON response returned by server",
        status: response.status,
      });
    }
  } else {
    const text = await response.text();
    if (!response.ok) {
      throw new ApiClientError({
        message: text || `HTTP ${response.status}`,
        status: response.status,
      });
    }
    data = text;
  }

  if (!response.ok) {
    // Backend standard ApiError shape: { error: { code, message, details, request_id } }
    const errObj = data?.error;
    throw new ApiClientError({
      message: errObj?.message || data?.message || `Request failed with status ${response.status}`,
      status: response.status,
      code: errObj?.code || data?.code || `HTTP_${response.status}`,
      details: errObj?.details || data?.details || [],
      requestId: errObj?.request_id || data?.request_id,
    });
  }

  return data as T;
}

export const apiClient = {
  async getHealth(): Promise<HealthResponse> {
    const health = await apiRequest<HealthResponse>("/health");
    if (health.contract_version !== EXPECTED_CONTRACT_VERSION) {
      setContractMismatch(true);
      throw new ApiClientError({
        message: `Contract version mismatch: expected ${EXPECTED_CONTRACT_VERSION}, got ${health.contract_version}`,
        status: 200,
        code: "CONTRACT_MISMATCH",
        isContractMismatch: true,
      });
    }
    setContractMismatch(false);
    return health;
  },

  async login(credentials: LoginRequest): Promise<Session> {
    const session = await apiRequest<Session>("/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
    if (session.csrf_token) {
      setCsrfToken(session.csrf_token);
    }
    return session;
  },

  async getSession(): Promise<Session> {
    const session = await apiRequest<Session>("/auth/session");
    if (session.csrf_token) {
      setCsrfToken(session.csrf_token);
    }
    return session;
  },

  async logout(): Promise<void> {
    try {
      await apiRequest<void>("/auth/logout", {
        method: "POST",
      });
    } finally {
      setCsrfToken(null);
    }
  },

  async getSnapshot(range?: { from?: string; to?: string }): Promise<Snapshot> {
    let endpoint = "/snapshot";
    if (range?.from && range?.to) {
      const params = new URLSearchParams({ from: range.from, to: range.to });
      endpoint = `${endpoint}?${params.toString()}`;
    }
    const snapshot = await apiRequest<Snapshot>(endpoint);

    // Verify contract version in snapshot
    if (snapshot.meta?.contract_version !== EXPECTED_CONTRACT_VERSION) {
      setContractMismatch(true);
      throw new ApiClientError({
        message: `Snapshot contract version mismatch: expected ${EXPECTED_CONTRACT_VERSION}, got ${snapshot.meta?.contract_version}`,
        status: 200,
        code: "CONTRACT_MISMATCH",
        isContractMismatch: true,
      });
    }
    setContractMismatch(false);
    return snapshot;
  },

  async getOperation(operationId: string): Promise<Operation> {
    return apiRequest<Operation>(`/operations/${encodeURIComponent(operationId)}`);
  },

  async createJob(payload: CreateJobRequest, idempotencyKey?: string): Promise<Job> {
    return apiRequest<Job>("/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
      idempotencyKey,
    });
  },

  async runSchedule(payload: RunScheduleRequest, idempotencyKey?: string): Promise<Operation> {
    return apiRequest<Operation>("/schedule/runs", {
      method: "POST",
      body: JSON.stringify(payload),
      idempotencyKey,
    });
  },

  async createDisruptionEvent(
    payload: CreateDisruptionEventRequest,
    idempotencyKey?: string
  ): Promise<Operation> {
    return apiRequest<Operation>("/events", {
      method: "POST",
      body: JSON.stringify(payload),
      idempotencyKey,
    });
  },

  async simulationAction(
    payload: SimulationActionRequest,
    idempotencyKey?: string
  ): Promise<Operation> {
    return apiRequest<Operation>("/simulation/actions", {
      method: "POST",
      body: JSON.stringify(payload),
      idempotencyKey,
    });
  },

  async createTransfer(payload: CreateTransferRequest, idempotencyKey?: string): Promise<Operation> {
    return apiRequest<Operation>("/transfers", {
      method: "POST",
      body: JSON.stringify(payload),
      idempotencyKey,
    });
  },

  async runSecurityCheck(
    payload: RunSecurityCheckRequest,
    idempotencyKey?: string
  ): Promise<Operation> {
    return apiRequest<Operation>("/security/checks", {
      method: "POST",
      body: JSON.stringify(payload),
      idempotencyKey,
    });
  },

  async runEvaluation(payload: RunEvaluationRequest, idempotencyKey?: string): Promise<Operation> {
    return apiRequest<Operation>("/evaluations", {
      method: "POST",
      body: JSON.stringify(payload),
      idempotencyKey,
    });
  },
};
