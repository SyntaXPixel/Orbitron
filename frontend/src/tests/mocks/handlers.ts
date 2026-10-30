import { http, HttpResponse } from "msw";
import {
  mockHealthReady,
  mockOperation,
  mockSession,
  mockSnapshot,
} from "./fixtures";
import { API_BASE_URL } from "../../api/client";

export const handlers = [
  http.get(`${API_BASE_URL}/health`, () => {
    return HttpResponse.json(mockHealthReady);
  }),

  http.post(`${API_BASE_URL}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as any;
    if (body.email === "operator@example.test" && body.password === "secret") {
      return HttpResponse.json(mockSession);
    }
    return HttpResponse.json(
      {
        error: {
          code: "INVALID_CREDENTIALS",
          message: "Invalid email or password.",
          details: [],
          request_id: "req-err-01",
        },
      },
      { status: 401 }
    );
  }),

  http.get(`${API_BASE_URL}/auth/session`, () => {
    return HttpResponse.json(mockSession);
  }),

  http.post(`${API_BASE_URL}/auth/logout`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.get(`${API_BASE_URL}/snapshot`, () => {
    return HttpResponse.json(mockSnapshot);
  }),

  http.post(`${API_BASE_URL}/jobs`, async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json(
      {
        id: `job-new-${Date.now()}`,
        satellite_id: body.satellite_id,
        owner_org_id: "org-fleet-a",
        requested_bytes: body.data_bytes,
        delivered_bytes: 0,
        remaining_bytes: body.data_bytes,
        priority: body.priority,
        deadline_at: body.deadline_at,
        allow_split: body.allow_split,
        status: "pending",
        reasons: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      { status: 201 }
    );
  }),

  http.post(`${API_BASE_URL}/schedule/runs`, async ({ request }) => {
    const body = (await request.json()) as any;
    if (body.expected_schedule_version === 999) {
      // Simulate stale schedule error
      return HttpResponse.json(
        {
          error: {
            code: "STALE_SCHEDULE",
            message: "Schedule version 999 does not match current version 3.",
            details: [],
            request_id: "req-stale-01",
          },
        },
        { status: 409 }
      );
    }
    return HttpResponse.json(mockOperation, { status: 202 });
  }),

  http.post(`${API_BASE_URL}/events`, () => {
    return HttpResponse.json(mockOperation, { status: 202 });
  }),

  http.post(`${API_BASE_URL}/simulation/actions`, () => {
    return HttpResponse.json(mockOperation, { status: 202 });
  }),

  http.post(`${API_BASE_URL}/transfers`, () => {
    return HttpResponse.json(mockOperation, { status: 202 });
  }),

  http.post(`${API_BASE_URL}/security/checks`, () => {
    return HttpResponse.json(mockOperation, { status: 202 });
  }),

  http.post(`${API_BASE_URL}/evaluations`, () => {
    return HttpResponse.json(mockOperation, { status: 202 });
  }),

  http.get(`${API_BASE_URL}/operations/:id`, ({ params }) => {
    return HttpResponse.json({
      ...mockOperation,
      id: params.id,
    });
  }),
];
