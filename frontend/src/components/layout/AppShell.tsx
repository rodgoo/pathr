/**
 * The page frame: navigation rail on the left, the active screen on the
 * right, both floating on the app ground as rounded panels.
 *
 * The rail and the pane are siblings in one wrapping flex row, so on a narrow
 * viewport the rail wraps to a full-width block above the content instead of
 * being squeezed to nothing.
 */
import type { ReactNode } from "react";
import { BG, PANEL, TEXT } from "@/lib/tokens";
import { Sidebar } from "./Sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        minHeight: "100vh",
        background: BG,
        color: TEXT.full,
        fontFamily: "Inter, system-ui, sans-serif",
        fontSize: 15,
        padding: 11.2,
        gap: 11.2,
      }}
    >
      <Sidebar />
      <main
        style={{
          flex: "1 1 620px",
          minWidth: 0,
          display: "flex",
          flexDirection: "column",
          gap: 11.2,
          padding: 22.4,
          borderRadius: 14,
          background: PANEL,
          boxShadow: "0 0 0 1px #2b2e3d",
        }}
      >
        {children}
      </main>
    </div>
  );
}
