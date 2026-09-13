/**
 * Segurança: o que protege a conta e os dados, dito sem exagero.
 *
 * Cada número daqui vem do código — services/limites.py (limites de uso),
 * config.py (sessão, bloqueio, tamanhos de upload), security.py (Argon2id,
 * regras de senha), seguranca_http.py e frontend/public/_headers (cabeçalhos).
 * Mudou lá, muda aqui. Nada de selo, certificação ou promessa que o código não
 * sustenta.
 */

import { EmailContato, Fichas, Forte, LinkDoc, Lista, Nota, P, type DocumentoLegal } from "./LegalLayout";

export const SEGURANCA: DocumentoLegal = {
  path: "/seguranca",
  aba: "Segurança",
  kicker: "Segurança",
  titulo: "Como protegemos sua conta",
  introducao:
    "As medidas técnicas que o PathR usa para proteger o acesso à sua conta e os dados guardados nela — e o que você pode fazer do seu lado.",
  resumo: [
    "Senhas guardadas só como hash Argon2id; o texto da senha nunca é armazenado.",
    "Entrada exige e-mail confirmado, e a conta é bloqueada por 15 minutos após 5 senhas erradas.",
    "Chave de acesso (passkey) e segundo fator por aplicativo autenticador são suportados.",
    "Sessão em cookies HttpOnly e SameSite=Strict, com renovação rotativa e “sair de todos os dispositivos”.",
    "Arquivos em armazenamento privado, entregues só pelo servidor e só para quem tem permissão.",
    "Achou uma falha? Conte para privacidade@notter.com.br antes de divulgar.",
  ],
  secoes: [
    {
      id: "senhas",
      titulo: "Senhas e entrada",
      corpo: (
        <Lista
          itens={[
            <>
              Senhas são guardadas apenas como hash <Forte>Argon2id</Forte>, um algoritmo desenhado para resistir a
              ataques com placas de vídeo. Nem quem opera o app consegue ver a sua senha.
            </>,
            "A senha precisa de ao menos 10 caracteres, com letras e números — a regra é conferida no servidor.",
            "Depois de 5 senhas erradas seguidas, a conta fica bloqueada por 15 minutos. O bloqueio é temporário para que um ataque não vire uma forma de trancar o dono para fora.",
            "E-mail inexistente e senha errada recebem a mesma mensagem, para não revelar quais e-mails têm conta.",
            "Só entra quem confirmou o e-mail — assim ninguém cria uma conta usando o endereço de outra pessoa.",
            "Os links de confirmação (válidos por 3 dias) e de nova senha (válidos por 1 hora) são de uso único, e o servidor guarda só o hash deles.",
          ]}
        />
      ),
    },
    {
      id: "fatores",
      titulo: "Chave de acesso e segundo fator",
      corpo: (
        <Lista
          itens={[
            <>
              <Forte>Chaves de acesso (passkeys, padrão WebAuthn)</Forte>: você entra com a biometria ou o PIN do
              aparelho. O servidor guarda só a parte pública da chave, que fica presa ao endereço
              pathr.notter.com.br — uma página falsa não consegue usá-la. Cadastre e remova as suas em Configurações ›
              Conta.
            </>,
            <>
              <Forte>Segundo fator (TOTP)</Forte>: com ele ativo, a entrada pede também o código de um aplicativo
              autenticador. O segredo é guardado cifrado, e os códigos de recuperação são de uso único e guardados como
              hash.
            </>,
            "Cada desafio de chave de acesso vale por cinco minutos e só pode ser usado uma vez.",
          ]}
        />
      ),
    },
    {
      id: "sessao",
      titulo: "Sessão",
      corpo: (
        <>
          <Lista
            itens={[
              <>
                A sessão fica em cookies <Forte>HttpOnly</Forte> (o código da página não consegue lê-los),{" "}
                <Forte>Secure</Forte> (só trafegam por HTTPS) e <Forte>SameSite=Strict</Forte> (não acompanham pedidos
                vindos de outros sites).
              </>,
              "O token de acesso dura 30 minutos. A renovação usa um segundo token, trocado a cada uso; se um token já trocado reaparecer — sinal de que foi copiado —, toda a cadeia de sessões é revogada.",
              "Cada pedido confere no servidor se a sessão ainda é válida. Sessões encerradas param de funcionar na hora, não só quando expiram.",
              "Trocar a senha encerra as suas outras sessões; redefinir a senha pelo e-mail encerra todas.",
            ]}
          />
          <P>
            Em Configurações › Avisos e privacidade, <Forte>Sair de todos os dispositivos</Forte> encerra todas as
            sessões abertas de uma vez.
          </P>
        </>
      ),
    },
    {
      id: "dados",
      titulo: "Acesso aos dados",
      corpo: (
        <Lista
          itens={[
            "Toda rota da API exige sessão válida e só devolve ou altera registros que pertencem a quem está conectado.",
            "O navegador nunca fala direto com o banco de dados: só a API tem a credencial, e as permissões dos papéis públicos do banco são revogadas em todas as tabelas.",
            "Currículos, fotos de perfil e fotos de relatos ficam em armazenamento privado, sem endereço público. Eles saem apenas pelo servidor, para quem tem permissão.",
            "A foto de outra pessoa só aparece se ela estiver visível nas sugestões ou tiver conexão com você.",
            "As áreas de moderação respondem como inexistentes para qualquer conta que não seja da moderação.",
            "A exportação de dados não inclui hash de senha, segredo do segundo fator nem tokens de sessão.",
          ]}
        />
      ),
    },
    {
      id: "navegador",
      titulo: "Proteções no navegador e na rede",
      corpo: (
        <Lista
          itens={[
            <>
              Todo o tráfego usa <Forte>HTTPS</Forte>, com HSTS: o navegador lembra de nunca acessar o PathR sem
              criptografia.
            </>,
            <>
              <Forte>Content-Security-Policy</Forte> restringe de onde o site carrega scripts, estilos, fontes e
              conexões, como segunda barreira contra injeção de código.
            </>,
            "O site não pode ser exibido dentro de quadros de outras páginas (X-Frame-Options e frame-ancestors), o que impede cliques induzidos.",
            "Os cabeçalhos nosniff, Referrer-Policy e Cross-Origin-Resource-Policy impedem que arquivos sejam interpretados como outra coisa ou embutidos por outros sites.",
            "O site bloqueia o uso de câmera, localização e pagamento pelo navegador, que o app não usa.",
            "A documentação interativa da API fica desligada em produção.",
          ]}
        />
      ),
    },
    {
      id: "arquivos",
      titulo: "Arquivos e conteúdo de terceiros",
      corpo: (
        <Lista
          itens={[
            "Currículos são aceitos em PDF, DOCX, ODT, RTF, TXT e MD, até 10 MB.",
            "Fotos (perfil e relatos) são aceitas só em JPG, PNG ou WebP, até 5 MB, e o tipo é conferido pelos bytes do arquivo — não pelo nome ou pelo que o navegador declara.",
            "A foto de um relato é entregue com uma política que impede qualquer execução, mesmo que um arquivo disfarçado passasse pela conferência.",
            "Artigos de outros sites exibidos no app são limpos no servidor por uma lista de permissão antes de aparecer, e o servidor se recusa a buscar endereços de redes internas.",
            "Links vindos de fora (artigos, vagas, cursos, respostas da IA) só viram link clicável se forem http ou https.",
          ]}
        />
      ),
    },
    {
      id: "limites",
      titulo: "Limites contra abuso",
      corpo: (
        <>
          <P>
            Alguns recursos são compartilhados por todos — a cota de e-mails e a da inteligência artificial. Para que
            ninguém esgote o que é de todos, o servidor aplica limites:
          </P>
          <Fichas
            itens={[
              { nome: "Cadastro", papel: "5 por hora", detalhe: "Por endereço IP." },
              { nome: "Entrada", papel: "30 a cada 15 minutos", detalhe: "Por IP, além do bloqueio por conta." },
              { nome: "E-mails de confirmação e senha", papel: "6 por hora por IP", detalhe: "E no máximo 3 por hora para o mesmo endereço de e-mail." },
              { nome: "Inteligência artificial", papel: "150 chamadas por dia", detalhe: "Por conta." },
              { nome: "Busca de pessoas", papel: "60 a cada 10 minutos", detalhe: "Por conta." },
              { nome: "Convites de amizade", papel: "40 por dia", detalhe: "Por conta." },
              { nome: "Relatos", papel: "10 por dia", detalhe: "Por conta." },
            ]}
          />
        </>
      ),
    },
    {
      id: "monitoramento",
      titulo: "Monitoramento",
      corpo: (
        <Lista
          itens={[
            "Eventos de segurança — cadastro, entradas, falhas e uso do segundo fator — são registrados com data, IP e navegador. O registro nunca contém senha, código ou token.",
            "Erros do servidor são registrados sem e-mails, identificadores ou tokens na mensagem.",
            "Uma revisão automatizada diária olha os erros, os relatos e as dependências do projeto, e a moderação recebe um resumo por e-mail.",
          ]}
        />
      ),
    },
    {
      id: "sua-parte",
      titulo: "O que você pode fazer",
      corpo: (
        <>
          <Lista
            itens={[
              "Use uma senha que você não usa em nenhum outro lugar, ou um gerenciador de senhas.",
              "Cadastre uma chave de acesso do seu aparelho em Configurações › Conta.",
              "Se suspeitar que alguém entrou na sua conta, troque a senha e use “Sair de todos os dispositivos”.",
              "Desconfie de mensagens pedindo sua senha: o PathR nunca pede senha por e-mail. Na dúvida, digite pathr.notter.com.br direto no navegador em vez de clicar.",
              "Em computadores compartilhados, saia da conta ao terminar — isso também apaga a cópia offline guardada no navegador.",
            ]}
          />
        </>
      ),
    },
    {
      id: "vulnerabilidades",
      titulo: "Encontrou uma vulnerabilidade?",
      corpo: (
        <>
          <P>
            Escreva para <EmailContato /> com a descrição do problema e os passos para reproduzi-lo. Pedimos que você
            não acesse, altere ou apague dados de outras pessoas, não degrade o serviço e dê um tempo razoável para a
            correção antes de divulgar. O PathR não tem programa de recompensas, mas agradece — e responde.
          </P>
        </>
      ),
    },
    {
      id: "limitacoes",
      titulo: "Um aviso honesto",
      corpo: (
        <Nota tom="atencao">
          Nenhum sistema é totalmente seguro. O PathR é um projeto independente, sem certificações de segurança, e
          depende também da segurança dos fornecedores listados na <LinkDoc href="/privacidade">Política de privacidade</LinkDoc>. Se ocorrer um
          incidente relevante envolvendo seus dados, você será avisado, conforme a LGPD.
        </Nota>
      ),
    },
  ],
};
