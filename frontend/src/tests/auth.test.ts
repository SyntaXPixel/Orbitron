import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { apiClient, API_BASE_URL, getCsrfToken, setCsrfToken } from "../api/client";
import { ApiClientError } from "../utils/errors";

describe("Authentication & Session Handling (Plan Section 8)", () => {
  beforeEach(() => {
    setCsrfToken(null);
  });

  it("authenticates successfully with valid credentials and receives session & csrf token", async () => {
    const session = await apiClient.login({
      email: "operator@example.test",
      password: "secret",
    });

    expect(session.user.email).toBe("operator@example.test");
    expect(session.user.role).toBe("operator");
    expect(session.csrf_token).toBe("csrf-token-123456");
    expect(getCsrfToken()).toBe("csrf-token-123456");
  });

  it("rejects invalid credentials with 401 and descriptive message", async () => {
    expect.assertions(3);
    try {
      await apiClient.login({
        email: "unknown@example.test",
        password: "wrong",
      });
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiClientError);
      expect(err.status).toBe(401);
      expect(err.message).toBe("Invalid email or password.");
    }
  });

  it("logout clears session and resets memory CSRF token", async () => {
    setCsrfToken("active-token");
    expect(getCsrfToken()).toBe("active-token");

    await apiClient.logout();
    expect(getCsrfToken()).toBeNull();
  });

  it("handles session expiration (401 on session check)", async () => {
    server.use(
      http.get(`${API_BASE_URL}/auth/session`, () => {
        return HttpResponse.json(
          {
            error: {
              code: "SESSION_EXPIRED",
              message: "Session has expired. Please log in again.",
              details: [],
              request_id: "req-exp-01",
            },
          },
          { status: 401 }
        );
      })
    );

    try {
      await apiClient.getSession();
      expect.fail("Should have thrown 401");
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiClientError);
      expect(err.status).toBe(401);
      expect(err.code).toBe("SESSION_EXPIRED");
    }
  });
});
