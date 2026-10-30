import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Calendar,
  Send,
  LifeBuoy,
  ShieldCheck,
  BarChart3,
  FileText,
  LogOut,
  Radio,
  Building,
  User as UserIcon,
} from "lucide-react";
import type { User, Organization } from "../../api/types";
import { StatusBadge } from "../feedback/StatusBadge";

interface SidebarProps {
  user: User | null;
  organizations: Organization[];
  onLogout: () => void;
  isOpenMobile?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  user,
  organizations,
  onLogout,
  isOpenMobile = false,
  onCloseMobile,
}) => {
  const orgName =
    organizations.find((o) => o.id === user?.organization_id)?.name ||
    user?.organization_id ||
    "Global Fleet";

  const navLinks = [
    { to: "/", label: "Overview", icon: LayoutDashboard },
    { to: "/schedule", label: "Schedule", icon: Calendar },
    { to: "/requests", label: "Requests", icon: Send },
    { to: "/recovery", label: "Recovery", icon: LifeBuoy },
    { to: "/security", label: "Security", icon: ShieldCheck },
    { to: "/evaluation", label: "Evaluation", icon: BarChart3 },
    { to: "/audit", label: "Audit", icon: FileText },
  ];

  return (
    <aside
      className={`app-sidebar ${isOpenMobile ? "mobile-open" : ""}`}
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        height: "100%",
        padding: "16px 0",
      }}
    >
      <div>
        {/* Brand */}
        <div style={{ padding: "0 20px 20px 20px", borderBottom: "1px solid var(--color-border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                background: "linear-gradient(135deg, #8b80ff 0%, #22e2a8 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#000",
              }}
            >
              <Radio size={18} />
            </div>
            <div>
              <h2 style={{ fontSize: "16px", margin: 0, letterSpacing: "0.05em" }}>ORBITRON</h2>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "2px" }}>
                <span
                  style={{
                    display: "inline-block",
                    width: "6px",
                    height: "6px",
                    borderRadius: "50%",
                    backgroundColor: "var(--color-active)",
                  }}
                />
                <span style={{ fontSize: "10px", color: "var(--color-text-dim)", textTransform: "uppercase" }}>
                  Operations Console
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation list */}
        <nav style={{ padding: "16px 8px" }}>
          <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "4px" }}>
            {navLinks.map((item) => {
              const Icon = item.icon;
              return (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.to === "/"}
                    onClick={onCloseMobile}
                    style={({ isActive }) => ({
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      padding: "10px 16px",
                      borderRadius: "var(--radius-control)",
                      color: isActive ? "var(--color-pure-white)" : "var(--color-text-muted)",
                      backgroundColor: isActive ? "var(--color-panel-raised)" : "transparent",
                      borderLeft: isActive ? "3px solid var(--color-accent)" : "3px solid transparent",
                      fontWeight: isActive ? 600 : 500,
                      fontSize: "13px",
                      textDecoration: "none",
                      transition: "all 0.15s ease",
                    })}
                  >
                    <Icon size={16} />
                    <span>{item.label}</span>
                  </NavLink>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>

      {/* User and Organisation Profile */}
      <div
        style={{
          padding: "16px 16px 0 16px",
          borderTop: "1px solid var(--color-border)",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", color: "var(--color-text-dim)" }}>
            <Building size={12} />
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {orgName}
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", overflow: "hidden" }}>
              <UserIcon size={14} color="var(--color-text-muted)" />
              <span
                style={{
                  fontSize: "13px",
                  fontWeight: 600,
                  color: "var(--color-pure-white)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {user?.display_name || user?.email || "User"}
              </span>
            </div>
            {user?.role && <StatusBadge status={user.role} />}
          </div>
        </div>

        <button
          type="button"
          className="btn btn-ghost"
          onClick={onLogout}
          style={{ width: "100%", justifyContent: "flex-start", fontSize: "12px", padding: "6px 12px" }}
        >
          <LogOut size={14} />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
};
