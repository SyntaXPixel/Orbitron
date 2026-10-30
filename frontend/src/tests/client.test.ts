import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import {
  apiClient,
  API_BASE_URL,
  setCsrfToken,
  isContractMismatch,
  setContractMismatch,
} from "../api/client";
import { mockOperation } from "./mocks/fixtures";
import { ApiClientError } from "../utils/errors";

describe("API Client Behavior (Plan Section 9 & 5)", () => {
  beforeEach(() => {
    setCsrfToken(null);
    setContractMismatch(false);
  });

  it("attaches CSRF token and Idempotency-Key header on state-changing requests", async () => {
    let capturedHeaders: Headers | null = null;
    server.use(
      http.post(`${API_BASE_URL}/jobs`, ({ request }) => {
        capturedHeaders = request.headers;
        return HttpResponse.json({ id: "job-captured" }, { status: 201 });
      })
    );

    setCsrfToken("csrf-test-token-777");

    await apiClient.createJob({
      satellite_id: "sat-a-001",
      data_bytes: 500_000_000,
      deadline_at: "2026-10-31T12:00:00Z",
      priority: "routine",
      allow_split: true,
    });

    expect(capturedHeaders).not.toBeNull();
    expect(capturedHeaders!.get("X-CSRF-Token")).toBe("csrf-test-token-777");
    expect(capturedHeaders!.get("Idempotency-Key")).toBeTruthy();
    expect(capturedHeaders!.get("Content-Type")).toBe("application/json");
  });

  it("handles 409 stale schedule conflict cleanly", async () => {
    expect.assertions(3);
    try {
      await apiClient.runSchedule({
        algorithm: "optimized",
        expected_schedule_version: 999, // Triggers 409 in mock handler
      });
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiClientError);
      expect(err.status).toBe(409);
      expect(err.code).toBe("STALE_SCHEDULE");
    }
  });

  it("handles API error envelopes with validation details (422)", async () => {
    server.use(
      http.post(`${API_BASE_URL}/jobs`, () => {
        return HttpResponse.json(
          {
            error: {
              code: "VALIDATION_FAILED",
              message: "Invalid job parameters submitted.",
              details: [
                { field: "data_bytes", message: "Must be a positive integer" },
                { field: "deadline_at", message: "Must be in the future" },
              ],
              request_id: "req-err-422",
            },
          },
          { status: 422 }
        );
      })
    );

    try {
      await apiClient.createJob({
        satellite_id: "sat-a-001",
        data_bytes: -10,
        deadline_at: "2020-01-01T00:00:00Z",
        priority: "routine",
        allow_split: false,
      });
      expect.fail("Should have thrown ApiClientError");
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiClientError);
      expect(err.status).toBe(422);
      expect(err.details).toHaveLength(2);
      expect(err.details[0].field).toBe("data_bytes");
    }
  });

  it("detects and flags contract version mismatch (Plan Section 5.1)", async () => {
    server.use(
      http.get(`${API_BASE_URL}/health`, () => {
        return HttpResponse.json({
          service: "orbitron-backend",
          contract_version: "orbitron.v2-incompatible",
          status: "ready",
        });
      })
    );

    try {
      await apiClient.getHealth();
      expect.fail("Should have thrown contract mismatch error");
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiClientError);
      expect(err.isContractMismatch).toBe(true);
      expect(isContractMismatch()).toBe(true);
    }
  });

  it("distinguishes network connectivity failure from server HTTP rejection", async () => {
    server.use(
      http.get(`${API_BASE_URL}/snapshot`, () => {
        return HttpResponse.error();
      })
    );

    try {
      await apiClient.getSnapshot();
      expect.fail("Should have thrown network error");
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiClientError);
      expect(err.isNetworkError).toBe(true);
      expect(err.status).toBe(0);
    }
  });

  it("handles 202 Operation tracking for asynchronous actions", async () => {
    const op = await apiClient.runSchedule({
      algorithm: "optimized",
      expected_schedule_version: 3,
    });
    expect(op.id).toBe(mockOperation.id);
    expect(op.status).toBe("succeeded");
  });
});
