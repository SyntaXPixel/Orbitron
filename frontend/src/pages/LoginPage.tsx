import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Radio, Lock, Mail, AlertOctagon, CheckCircle2 } from "lucide-react";
import { useLoginMutation } from "../api/mutations";
import { useHealth } from "../api/queries";

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { data: health, isLoading: healthLoading, isError: healthError } = useHealth();
  const loginMutation = useLoginMutation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (!email.trim()) {
      setValidationError("Email is required.");
      return;
    }
    if (!password) {
      setValidationError("Password is required.");
      return;
    }

    try {
      await loginMutation.mutateAsync({ email: email.trim(), password });
      navigate("/");
    } catch (err) {
      // Handled via mutation error state
    }
  };

  const serverError = loginMutation.error;
  const serverErrorMessage = serverError ? serverError.message : null;

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "20px",
        backgroundColor: "var(--color-bg)",
        backgroundImage:
          "radial-gradient(circle at 50% 30%, rgba(139, 128, 255, 0.08) 0%, rgba(7, 17, 31, 0) 70%)",
      }}
    >
      <div
        className="panel"
        style={{
          width: "100%",
          maxWidth: "420px",
          backgroundColor: "var(--color-panel)",
          border: "1px solid var(--color-border)",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.6)",
          padding: "36px 32px",
          display: "flex",
          flexDirection: "column",
          gap: "24px",
        }}
      >
        {/* Brand Header */}
        <div style={{ textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "12px",
              background: "linear-gradient(135deg, #8b80ff 0%, #22e2a8 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#000",
            }}
          >
            <Radio size={26} />
          </div>
          <div>
            <h1 style={{ fontSize: "22px", letterSpacing: "0.05em", margin: 0 }}>ORBITRON</h1>
            <p style={{ fontSize: "13px", color: "var(--color-text-muted)", marginTop: "4px" }}>
              Satellite Downlink & Ground Station Sharing Console
            </p>
          </div>
        </div>

        {/* Backend Connectivity Status */}
        <div
          style={{
            padding: "8px 12px",
            backgroundColor: "var(--color-panel-raised)",
            borderRadius: "var(--radius-control)",
            fontSize: "12px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span style={{ color: "var(--color-text-dim)" }}>Backend API:</span>
          {healthLoading ? (
            <span style={{ color: "var(--color-text-muted)" }}>Checking service...</span>
          ) : healthError ? (
            <span style={{ color: "var(--color-danger)", display: "flex", alignItems: "center", gap: "4px" }}>
              <AlertOctagon size={13} /> Unreachable
            </span>
          ) : (
            <span style={{ color: "var(--color-success)", display: "flex", alignItems: "center", gap: "4px" }}>
              <CheckCircle2 size={13} /> {health?.status.toUpperCase()} ({health?.contract_version})
            </span>
          )}
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {validationError && (
            <div
              style={{
                padding: "8px 12px",
                backgroundColor: "var(--color-danger-subtle)",
                borderRadius: "var(--radius-control)",
                color: "var(--color-danger)",
                fontSize: "12px",
              }}
              role="alert"
            >
              {validationError}
            </div>
          )}

          {serverErrorMessage && (
            <div
              style={{
                padding: "8px 12px",
                backgroundColor: "var(--color-danger-subtle)",
                borderRadius: "var(--radius-control)",
                color: "var(--color-danger)",
                fontSize: "12px",
              }}
              role="alert"
            >
              <strong>Authentication Failed:</strong> {serverErrorMessage}
            </div>
          )}

          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label" htmlFor="email">
              Operator Email
            </label>
            <div style={{ position: "relative" }}>
              <input
                id="email"
                type="email"
                className="form-input"
                style={{ width: "100%", paddingLeft: "34px" }}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="operator@example.test"
                disabled={loginMutation.isPending}
                autoComplete="username"
                required
              />
              <Mail
                size={16}
                color="var(--color-text-dim)"
                style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)" }}
              />
            </div>
          </div>

          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label" htmlFor="password">
              Password
            </label>
            <div style={{ position: "relative" }}>
              <input
                id="password"
                type="password"
                className="form-input"
                style={{ width: "100%", paddingLeft: "34px" }}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                disabled={loginMutation.isPending}
                autoComplete="current-password"
                required
              />
              <Lock
                size={16}
                color="var(--color-text-dim)"
                style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)" }}
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: "100%", marginTop: "8px", padding: "10px" }}
            disabled={loginMutation.isPending}
          >
            {loginMutation.isPending ? "Authenticating..." : "Sign In to Console"}
          </button>
        </form>

        <div style={{ textAlign: "center", fontSize: "11px", color: "var(--color-text-dim)" }}>
          Demo Credentials: Use authorized accounts configured on the local backend instance.
        </div>
      </div>
    </div>
  );
};
