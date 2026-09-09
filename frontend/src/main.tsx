import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { AppStateProvider } from "./hooks/useAppState";
import { AuthProvider } from "./hooks/useAuth";
import { OfflineProvider } from "./hooks/useOffline";
import { registerServiceWorker } from "./pwa/register";
import "./styles/nocturne.css";
import "./styles/app.css";

const container = document.getElementById("root");
if (!container) throw new Error("Missing #root element");

createRoot(container).render(
  <StrictMode>
    <AuthProvider>
      <OfflineProvider>
        <AppStateProvider>
          <App />
        </AppStateProvider>
      </OfflineProvider>
    </AuthProvider>
  </StrictMode>,
);

// Depois do render: o registro do worker não deve atrasar a primeira pintura,
// e em desenvolvimento a função não faz nada.
registerServiceWorker();
