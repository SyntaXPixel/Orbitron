import type { ApiErrorDetail } from "../api/types";

export class ApiClientError extends Error {
  public status: number;
  public code: string;
  public details: ApiErrorDetail[];
  public requestId?: string;
  public isContractMismatch?: boolean;
  public isNetworkError?: boolean;

  constructor(options: {
    message: string;
    status: number;
    code?: string;
    details?: ApiErrorDetail[];
    requestId?: string;
    isContractMismatch?: boolean;
    isNetworkError?: boolean;
  }) {
    super(options.message);
    this.name = "ApiClientError";
    this.status = options.status;
    this.code = options.code || (options.isNetworkError ? "NETWORK_ERROR" : "API_ERROR");
    this.details = options.details || [];
    this.requestId = options.requestId;
    this.isContractMismatch = options.isContractMismatch;
    this.isNetworkError = options.isNetworkError;
  }
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.details && error.details.length > 0) {
      return `${error.message}: ${error.details.map((d) => `${d.field}: ${d.message}`).join(", ")}`;
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "An unexpected error occurred";
}
