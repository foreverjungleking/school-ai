import type { ReactNode } from "react";

export type Screen = "dashboard" | "data" | "timetable" | "versions" | "assistant";

const items: { id: Screen; label: string; icon: string }[] = [
  { id: "dashboard", label: "Overview", icon: "◫" },
  { id: "data", label: "School data", icon: "◎" },
  { id: "timetable", label: "Timetable", icon: "▦" },
  { id: "versions", label: "Versions", icon: "⇄" },
  { id: "assistant", label: "AI Assistant", icon: "✦" },
];

export function AppShell({
  screen,
  onNavigate,
  apiOnline,
  children,
}: {
  screen: Screen;
  onNavigate: (screen: Screen) => void;
  apiOnline: boolean;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => onNavigate("dashboard")}>
          <span className="brand-mark">S</span>
          <span><strong>School AI</strong><small>Schedule studio</small></span>
        </button>
        <nav aria-label="Main navigation">
          {items.map((item) => (
            <button
              key={item.id}
              className={screen === item.id ? "nav-item active" : "nav-item"}
              onClick={() => onNavigate(item.id)}
            >
              <span aria-hidden="true">{item.icon}</span>{item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className={apiOnline ? "connection online" : "connection offline"} />
          {apiOnline ? "API connected" : "API unavailable"}
        </div>
      </aside>
      <main>{children}</main>
    </div>
  );
}
