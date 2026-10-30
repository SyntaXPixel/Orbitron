import React from "react";

interface LoadingSkeletonProps {
  rows?: number;
  height?: number;
}

export const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({ rows = 4, height = 24 }) => {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px", width: "100%", padding: "12px 0" }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          style={{
            height: `${height}px`,
            backgroundColor: "var(--color-panel-raised)",
            borderRadius: "4px",
            animation: "pulse 1.5s infinite ease-in-out",
            opacity: 0.6 + (i % 3) * 0.15,
          }}
        />
      ))}
      <style>{`
        @keyframes pulse {
          0% { opacity: 0.3; }
          50% { opacity: 0.7; }
          100% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
};
