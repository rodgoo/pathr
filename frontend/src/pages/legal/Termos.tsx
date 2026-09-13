/**
 * Termos de uso.
 *
 * O que o PathR oferece, o que se espera de quem usa e os limites do que o app
 * promete. A idade mínima (18) vem de backend/app/schemas/auth.py; o resto do
 * que é fato técnico está detalhado em Privacidade.tsx e Seguranca.tsx, e aqui
 * só é referido — duas descrições do mesmo fato divergiriam.
 */

import { EmailContato, Forte, LinkDoc, Lista, Nota, P, type DocumentoLegal } from "./LegalLayout";

export const TERMOS: DocumentoLegal = {
  path: "/termos",
  aba: "Termos de uso",
  kicker: "Termos de uso",
  titulo: "Termos de uso",
  introducao:
    "As regras para usar o PathR: o que o app oferece, o que esperamos de quem usa e o que cabe a cada parte. Ao criar uma conta ou usar o app, você concorda com estes termos.",
  resumo: [
    "O PathR é uma ferramenta gratuita de plano de estudos, só para maiores de 18 anos.",
    "O conteúdo gerado por IA pode conter erros e não garante emprego, promoção ou certificação.",
    "Seu currículo e o que você escreve continuam seus; usamos só para fazer o app funcionar para você.",
    "Respeito nos recursos sociais: nada de assédio, spam, raspagem de dados ou dados de terceiros.",
    "Você pode sair quando quiser, exportando seus dados e excluindo a conta.",
    "Vale a lei brasileira, incluindo o Código de Defesa do Consumidor e a LGPD.",
  ],
  secoes: [
    {
      id: "aceitacao",
      titulo: "Aceitação",
      corpo: (
        <>
          <P>
            Estes termos regem o uso do PathR, disponível em pathr.notter.com.br, operado por Rodrigo Carvalho. Ao criar
            uma conta você declara que leu e concorda com eles e com a <LinkDoc href="/privacidade">Política de privacidade</LinkDoc>, que
            explica como os seus dados são tratados.
          </P>
          <P>Se não concordar, não use o app. Você pode excluir a conta a qualquer momento.</P>
        </>
      ),
    },
    {
      id: "servico",
      titulo: "O que é o PathR",
      corpo: (
        <>
          <P>
            O PathR é um aplicativo <Forte>gratuito</Forte> que ajuda quem trabalha com tecnologia a organizar os
            estudos. Entre os recursos: leitura do currículo por IA, roadmap em fases, curadoria de materiais, quizzes e
            revisão espaçada, laboratório de código, treino de idiomas, busca de vagas, acompanhamento de constância e
            conexão com outras pessoas.
          </P>
          <P>
            Os recursos podem mudar, ser melhorados ou deixar de existir com o tempo. O app depende de serviços de
            terceiros, muitos em planos gratuitos com cotas; por isso, alguns recursos podem ficar temporariamente
            indisponíveis ou limitados.
          </P>
        </>
      ),
    },
    {
      id: "conta",
      titulo: "Sua conta",
      corpo: (
        <Lista
          itens={[
            <>
              É preciso ter <Forte>ao menos 18 anos</Forte>. Contas de menores de idade são encerradas e os dados
              apagados.
            </>,
            "Informe dados verdadeiros e mantenha o e-mail atualizado — é por ele que você confirma a conta e recupera a senha.",
            "A conta é pessoal. Você é responsável por manter a senha em sigilo e pelo que for feito com o seu acesso; se suspeitar de uso indevido, troque a senha e encerre as sessões.",
            "O nome de usuário (@) não pode imitar outra pessoa, marca ou a moderação do app, nem ser ofensivo.",
          ]}
        />
      ),
    },
    {
      id: "ia",
      titulo: "Conteúdo gerado por IA",
      corpo: (
        <>
          <P>
            Leitura de currículo, roadmap, quizzes, explicações, correções, exemplos de código, traduções e sugestões
            são produzidos com modelos de inteligência artificial de terceiros.
          </P>
          <Nota tom="atencao">
            Esse conteúdo <Forte>pode conter erros, omissões ou informações desatualizadas</Forte>. Ele é um apoio ao
            estudo, não aconselhamento profissional, jurídico ou de carreira, e não garante aprovação em processos
            seletivos, emprego, promoção ou certificação. Confira o que for importante em fontes oficiais.
          </Nota>
          <Lista
            itens={[
              "Os níveis de proficiência estimados a partir do currículo são palpites: revise-os antes de aplicá-los ao perfil.",
              "Materiais, cursos e vagas indicados pertencem a sites de terceiros. O PathR não é responsável pelo conteúdo, pela disponibilidade nem pelas condições desses sites, e não intermedeia contratações.",
              "Há um limite diário de uso da IA por conta, para que a cota compartilhada atenda a todos.",
            ]}
          />
        </>
      ),
    },
    {
      id: "uso-aceitavel",
      titulo: "Uso aceitável",
      corpo: (
        <>
          <P>Ao usar o PathR, você concorda em não:</P>
          <Lista
            itens={[
              "Enviar currículo, foto ou dados pessoais de outra pessoa sem autorização dela.",
              "Assediar, ameaçar, discriminar ou constranger outras pessoas, inclusive por convites de amizade repetidos ou relatos.",
              "Coletar dados de outras contas de forma automatizada (raspagem), enumerar usuários ou montar bases a partir do app.",
              "Contornar limites de uso, criar contas em massa ou usar automações para gastar a cota de IA, e-mail ou busca.",
              <>
                Tentar acessar contas, dados ou áreas sem permissão, explorar falhas ou atrapalhar o funcionamento do
                serviço — falhas encontradas devem ser comunicadas (veja a página de{" "}
                <LinkDoc href="/seguranca">Segurança</LinkDoc>).
              </>,
              "Enviar arquivos maliciosos, conteúdo ilegal, ofensivo ou que viole direitos de terceiros.",
              "Usar o app para fins ilegais ou para gerar conteúdo que viole a lei.",
            ]}
          />
        </>
      ),
    },
    {
      id: "social",
      titulo: "Recursos sociais",
      corpo: (
        <>
          <P>
            O PathR permite encontrar pessoas, enviar convites e ver cartões de outras contas. O que aparece no seu
            cartão e como controlar a sua visibilidade estão descritos na <LinkDoc href="/privacidade">Política de privacidade</LinkDoc>.
          </P>
          <Lista
            itens={[
              "Trate as outras pessoas com respeito. Um convite recusado é uma resposta.",
              "Informações vistas no cartão de outra pessoa servem para conexão dentro do app — não as copie para outros fins.",
              "Comportamento abusivo pode ser relatado pela tela Relatar.",
            ]}
          />
        </>
      ),
    },
    {
      id: "seu-conteudo",
      titulo: "Seu conteúdo",
      corpo: (
        <>
          <P>
            Tudo o que você envia ou escreve — currículo, foto, explicações, atividades, respostas e relatos —{" "}
            <Forte>continua sendo seu</Forte>.
          </P>
          <P>
            Para que o app funcione, você nos concede uma autorização limitada, gratuita e revogável para guardar,
            processar e exibir esse conteúdo, e para enviá-lo aos fornecedores descritos na <LinkDoc href="/privacidade">Política de privacidade</LinkDoc>{" "}
            (como os provedores de IA), exclusivamente para prestar o serviço a você. Essa autorização termina quando
            você apaga o conteúdo ou a conta, ressalvado o que a lei exigir guardar.
          </P>
          <P>
            Você garante que tem o direito de enviar o que envia. Sugestões enviadas pela tela Relatar podem ser usadas
            para melhorar o app, sem que isso gere obrigação ou remuneração.
          </P>
        </>
      ),
    },
    {
      id: "propriedade",
      titulo: "Propriedade do PathR",
      corpo: (
        <P>
          O software, a marca, o design e os textos do PathR pertencem ao seu operador, exceto componentes de terceiros
          usados sob as respectivas licenças (como os ícones creditados nas Configurações). Estes termos não transferem
          a você nenhum direito sobre eles além do uso do app.
        </P>
      ),
    },
    {
      id: "moderacao",
      titulo: "Moderação, suspensão e encerramento",
      corpo: (
        <>
          <P>
            Relatos enviados são analisados pela moderação. Em caso de violação destes termos, de risco a outras
            pessoas ou ao serviço, ou por determinação legal, podemos remover conteúdo e suspender ou encerrar a conta
            envolvida — sempre que possível com aviso e explicação pelo e-mail cadastrado.
          </P>
          <P>
            Você pode encerrar a relação a qualquer momento: exporte seus dados e exclua a conta em Configurações ›
            Avisos e privacidade.
          </P>
        </>
      ),
    },
    {
      id: "responsabilidade",
      titulo: "Disponibilidade e responsabilidade",
      corpo: (
        <>
          <P>
            O PathR é oferecido gratuitamente e no estado em que se encontra. Trabalhamos para mantê-lo disponível,
            correto e seguro, mas não garantimos funcionamento ininterrupto ou livre de erros, nem a preservação de
            dados em caso de falhas — exporte seus dados periodicamente se eles forem importantes para você.
          </P>
          <P>
            Na medida permitida pela lei, o PathR não responde por decisões tomadas com base no conteúdo gerado pela
            IA, por conteúdo e condições de sites de terceiros, nem por indisponibilidade de fornecedores. Nada nestes
            termos afasta direitos garantidos pelo Código de Defesa do Consumidor ou pela LGPD.
          </P>
        </>
      ),
    },
    {
      id: "mudancas",
      titulo: "Mudanças nestes termos",
      corpo: (
        <P>
          Estes termos podem ser atualizados. A data no topo indica a versão em vigor, e mudanças relevantes serão
          avisadas no app ou por e-mail antes de valer. Continuar usando o PathR depois disso significa concordar com a
          nova versão; se não concordar, você pode excluir a conta.
        </P>
      ),
    },
    {
      id: "lei",
      titulo: "Lei aplicável e foro",
      corpo: (
        <P>
          Estes termos seguem a legislação brasileira. Eventuais conflitos serão resolvidos no foro do domicílio do
          consumidor, conforme o Código de Defesa do Consumidor. Antes disso, escreva para <EmailContato /> — a maioria
          dos problemas se resolve por conversa.
        </P>
      ),
    },
  ],
};
