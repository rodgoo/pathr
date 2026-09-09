/**
 * Raiz do app: decide entre as telas de autenticação e o produto.
 *
 * Três estados, e a ordem importa. As telas alcançadas por link de e-mail
 * vêm PRIMEIRO, porque precisam abrir mesmo sem sessão — alguém que clica no
 * link de "nova senha" por definição não consegue entrar.
 */

import { AppShell } from "@/components/layout/AppShell";
import { useAppState } from "@/hooks/useAppState";
import { useAuth } from "@/hooks/useAuth";
import { useLocation } from "@/hooks/useLocation";
import { BG, TEXT } from "@/lib/tokens";
import type { Screen } from "@/types";
import { LoginPage } from "@/pages/auth/LoginPage";
import { SignupPage } from "@/pages/auth/SignupPage";
import { ForgotPasswordPage, ResetPasswordPage } from "@/pages/auth/PasswordPages";
import { VerifyEmailPage } from "@/pages/auth/VerifyEmailPage";
import { CvPage } from "@/pages/CvPage";
import { EnglishPage } from "@/pages/EnglishPage";
import { HomePage } from "@/pages/HomePage";
import { LibraryPage } from "@/pages/LibraryPage";
import { ModulePage } from "@/pages/ModulePage";
import { ProfilePage } from "@/pages/ProfilePage";
import { RoadmapPage } from "@/pages/RoadmapPage";
import { SettingsPage } from "@/pages/SettingsPage";

// As telas podem devolver null enquanto os dados chegam, então o tipo
// precisa admitir isso — um Record<Screen, () => JSX.Element> obrigaria cada
// uma a inventar um elemento vazio só para satisfazer a assinatura.
const SCREENS: Record<Screen, () => JSX.Element | null> = {
  home: HomePage,
  cv: CvPage,
  roadmap: RoadmapPage,
  modulo: ModulePage,
  ingles: EnglishPage,
  perfil: ProfilePage,
  biblioteca: LibraryPage,
  config: SettingsPage,
};

export function App() {
  const { status } = useAuth();
  const [location, navigate] = useLocation();

  // Alcançadas por link de e-mail: abrem com ou sem sessão.
  if (location.path === "/confirmar-email") {
    return <VerifyEmailPage token={location.token} onNavigate={navigate} />;
  }
  if (location.path === "/nova-senha") {
    return <ResetPasswordPage token={location.token} onNavigate={navigate} />;
  }

  if (status === "checking") return <Booting />;

  if (status === "anonymous") {
    if (location.path === "/cadastro") return <SignupPage onNavigate={navigate} />;
    if (location.path === "/recuperar-senha") return <ForgotPasswordPage onNavigate={navigate} />;
    return <LoginPage onNavigate={navigate} />;
  }

  return <AuthenticatedApp />;
}

function AuthenticatedApp() {
  const { state } = useAppState();
  const Screen = SCREENS[state.screen];
  return (
    <AppShell>
      <Screen />
    </AppShell>
  );
}

/**
 * Enquanto a sessão é verificada.
 *
 * Sem spinner: a checagem é uma requisição, quase sempre instantânea, e um
 * spinner que pisca por 80ms incomoda mais do que informa.
 */
function Booting() {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: BG,
        color: TEXT.faint,
        display: "grid",
        placeItems: "center",
        fontFamily: "Inter, system-ui, sans-serif",
        fontSize: 13,
      }}
    >
      <span aria-live="polite">Carregando…</span>
    </div>
  );
}
