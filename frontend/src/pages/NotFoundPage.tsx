import React from "react";
import { Link } from "react-router-dom";
import { Compass, ArrowLeft } from "lucide-react";

export const NotFoundPage: React.FC = () => {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        textAlign: "center",
        padding: "40px 20px",
      }}
    >
      <div
        style={{
          width: "64px",
          height: "64px",
          borderRadius: "50%",
          backgroundColor: "var(--color-panel-raised)",
          border: "1px solid var(--color-border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: "20px",
          color: "var(--color-accent)",
        }}
      >
        <Compass size={32} />
      </div>

      <h1 style={{ fontSize: "28px", marginBottom: "8px" }}>404 — Page Not Found</h1>
      <p style={{ color: "var(--color-text-muted)", maxWidth: "460px", marginBottom: "24px" }}>
        The requested operations console view does not exist or has been relocated within the network router.
      </p>

      <Link to="/" className="btn btn-primary">
        <ArrowLeft size={16} />
        <span>Return to Overview</span>
      </Link>
    </div>
  );
};
