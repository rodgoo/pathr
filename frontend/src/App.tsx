/**
 * Raiz do app: decide entre as telas de autenticação e o produto.
 *
 * Três estados, e a ordem importa. As telas alcançadas por link de e-mail
 * vêm PRIMEIRO, porque precisam abrir mesmo sem sessão — alguém que clica no
 * link de "nova senha" por definição não consegue entrar.
 */

import { useEffect } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { MarcaCarregando } from "@/components/ui/MarcaCarregando";
import { useAppState } from "@/hooks/useAppState";
import { useAuth } from "@/hooks/useAuth";
import { telaLiberada } from "@/lib/features";
import { useLocation } from "@/hooks/useLocation";
import { BG, TEXT } from "@/lib/tokens";
import type { Screen } from "@/types";
import { LoginPage } from "@/pages/auth/LoginPage";
import { LandingPage } from "@/pages/LandingPage";
import { SignupPage } from "@/pages/auth/SignupPage";
import { ForgotPasswordPage, ResetPasswordPage } from "@/pages/auth/PasswordPages";
import { VerifyEmailPage } from "@/pages/auth/VerifyEmailPage";
import { LegalPage, ehPaginaLegal } from "@/pages/legal/LegalPage";
import { CodeLabPage } from "@/pages/CodeLabPage";
import { CoursesPage } from "@/pages/CoursesPage";
import { JobsPage } from "@/pages/JobsPage";
import { CandidaturasPage } from "@/pages/CandidaturasPage";
import { AmigosPage } from "@/pages/AmigosPage";
import { RelatarPage } from "@/pages/RelatarPage";
import { CvPage } from "@/pages/CvPage";
import { EnglishPage } from "@/pages/EnglishPage";
import { HomePage } from "@/pages/HomePage";
import { ModulePage } from "@/pages/ModulePage";
import { NoticiasPage } from "@/pages/NoticiasPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { ResourcePage } from "@/pages/ResourcePage";
import { RoadmapPage } from "@/pages/RoadmapPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { ManualPage } from "@/pages/ManualPage";

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
  candidaturas: CandidaturasPage,
  noticias: NoticiasPage,
  config: SettingsPage,
  manual: ManualPage,
};

/** Endereços que só existem para quem ainda não entrou.
 *
 * Entrar, criar conta e recuperar senha são degraus para dentro do app: uma
 * vez dentro, o endereço passa a contar uma história que não é mais verdade.
 * Ficam de fora os endereços de link de e-mail (`/confirmar-email`,
 * `/nova-senha`) e as páginas legais, que são lidas com sessão e precisam
 * manter o próprio endereço — são destino, e não degrau. */
const ENDERECOS_DE_VISITANTE = new Set(["/entrar", "/cadastro", "/recuperar-senha"]);

export function App() {
  const { status } = useAuth();
  const [location, navigate, replace] = useLocation();

  // Entrar não troca de endereço: o login acontece no lugar, o `status` vira
  // `authenticated` e a tela passa a ser o app — mas a barra de endereços
  // continua marcando `/entrar`. Recarregar dali funciona (a sessão é lida do
  // servidor, não do caminho), então o sintoma é só o endereço mentindo:
  // guardar nos favoritos, copiar o link ou abrir o histórico registra uma
  // tela de login que a pessoa não vai ver. Vale para quem acabou de entrar e
  // para quem chega em `/entrar` com sessão de outra aba.
  useEffect(() => {
    if (status !== "authenticated") return;
    if (!ENDERECOS_DE_VISITANTE.has(location.path)) return;
    replace("/");
  }, [status, location.path, replace]);

  // Alcançadas por link de e-mail: abrem com ou sem sessão.
  if (location.path === "/confirmar-email") {
    return <VerifyEmailPage token={location.token} onNavigate={navigate} />;
  }
  if (location.path === "/nova-senha") {
    return <ResetPasswordPage token={location.token} onNavigate={navigate} />;
  }
  // Termos, privacidade e segurança: texto público, com ou sem sessão.
  if (ehPaginaLegal(location.path)) {
    return <LegalPage path={location.path} onNavigate={navigate} />;
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
  const { user } = useAuth();
  // Se o recurso da tela estiver desligado (feature flag), cai no Início — a
  // navegação já esconde o item, isto cobre quem chega pela URL. A rota da API
  // tem a sua própria checagem; isto é só a camada visual.
  const tela = telaLiberada(state.screen, user?.features) ? state.screen : "home";
  const Screen = SCREENS[tela];
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
