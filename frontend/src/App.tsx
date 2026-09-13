/**
 * Raiz do app: decide entre as telas de autenticação e o produto.
 *
 * Três estados, e a ordem importa. As telas alcançadas por link de e-mail
 * vêm PRIMEIRO, porque precisam abrir mesmo sem sessão — alguém que clica no
 * link de "nova senha" por definição não consegue entrar.
 */

import { AppShell } from "@/components/layout/AppShell";
import { MarcaCarregando } from "@/components/ui/MarcaCarregando";
import { useAppState } from "@/hooks/useAppState";
import { useAuth } from "@/hooks/useAuth";
import { useLocation } from "@/hooks/useLocation";
import { BG, TEXT } from "@/lib/tokens";
import type { Screen } from "@/types";
import { LoginPage } from "@/pages/auth/LoginPage";
import { LandingPage } from "@/pages/LandingPage";
import { SignupPage } from "@/pages/auth/SignupPage";
import { ForgotPasswordPage, ResetPasswordPage } from "@/pages/auth/PasswordPages";
import { VerifyEmailPage } from "@/pages/auth/VerifyEmailPage";
import { CodeLabPage } from "@/pages/CodeLabPage";
import { CoursesPage } from "@/pages/CoursesPage";
import { JobsPage } from "@/pages/JobsPage";
import { AmigosPage } from "@/pages/AmigosPage";
import { RelatarPage } from "@/pages/RelatarPage";
import { CvPage } from "@/pages/CvPage";
import { EnglishPage } from "@/pages/EnglishPage";
import { HomePage } from "@/pages/HomePage";
import { ModulePage } from "@/pages/ModulePage";
import { ProfilePage } from "@/pages/ProfilePage";
import { ResourcePage } from "@/pages/ResourcePage";
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
  codigo: CodeLabPage,
  amigos: AmigosPage,
  relatar: RelatarPage,
  material: ResourcePage,
  cursos: CoursesPage,
  vagas: JobsPage,
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
    // A raiz apresenta o app a quem ainda não tem conta. Aberto como app
    // instalado na tela de início, não: quem instalou já conhece o PathR, e
    // ver a vitrine a cada abertura seria um passo a mais até o login.
    if (location.path === "/" && !abertoComoAppInstalado()) return <LandingPage onNavigate={navigate} />;
    return <LoginPage onNavigate={navigate} />;
  }

  return <AuthenticatedApp />;
}

function abertoComoAppInstalado(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(display-mode: standalone)").matches;
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
 * É a PRIMEIRA coisa que se vê ao abrir o app instalado, e quase sempre dura
 * menos de um segundo. Por isso é a marca, e não um spinner genérico: numa
 * abertura rápida ela lê como a identidade do produto aparecendo; numa lenta
 * (rede ruim, servidor acordando), o movimento é o que separa "está vindo" de
 * "travou".
 */
function Booting() {
  return (
    <div
      style={{
        minHeight: "100dvh",
        background: BG,
        color: TEXT.faint,
        display: "grid",
        placeItems: "center",
        fontFamily: "Inter, system-ui, sans-serif",
      }}
    >
      <MarcaCarregando size={72} label="Abrindo seu plano…" />
    </div>
  );
}
