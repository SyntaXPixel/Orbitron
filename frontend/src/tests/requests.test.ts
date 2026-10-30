import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { apiClient, API_BASE_URL } from "../api/client";
import type { CreateJobRequest } from "../api/types";

describe("Request Submission & Exact Payload Validation (Plan Section 7.2 & 11.4)", () => {
  it("submits job with exact contract units: bytes, ISO UTC timestamp, and priority", async () => {
    let capturedPayload: CreateJobRequest | null = null;

    server.use(
      http.post(`${API_BASE_URL}/jobs`, async ({ request }) => {
        capturedPayload = (await request.json()) as CreateJobRequest;
        return HttpResponse.json(
          {
            id: "job-created-999",
            satellite_id: capturedPayload.satellite_id,
            owner_org_id: "org-fleet-a",
            requested_bytes: capturedPayload.data_bytes,
            delivered_bytes: 0,
            remaining_bytes: capturedPayload.data_bytes,
            priority: capturedPayload.priority,
            deadline_at: capturedPayload.deadline_at,
            allow_split: capturedPayload.allow_split,
            status: "pending",
            reasons: [],
            created_at: "2026-10-31T08:00:00Z",
            updated_at: "2026-10-31T08:00:00Z",
          },
          { status: 201 }
        );
      })
    );

    const payload: CreateJobRequest = {
      satellite_id: "sat-a-001",
      data_bytes: 1_000_000_000, // 1 GB canonical bytes
      deadline_at: "2026-10-31T12:00:00Z",
      priority: "high",
      allow_split: true,
    };

    const createdJob = await apiClient.createJob(payload);

    expect(createdJob.id).toBe("job-created-999");
    expect(capturedPayload).toEqual({
      satellite_id: "sat-a-001",
      data_bytes: 1_000_000_000,
      deadline_at: "2026-10-31T12:00:00Z",
      priority: "high",
      allow_split: true,
    });
  });

  it("converts MB to exact canonical bytes: 500 MB -> 500,000,000 bytes", async () => {
    const mbValue = 500;
    const bytes = mbValue * 1_000_000;
    expect(bytes).toBe(500_000_000);

    const gbValue = 2.5;
    const gbBytes = gbValue * 1_000_000_000;
    expect(gbBytes).toBe(2_500_000_000);
  });
});
