/**
 * Política de privacidade e uso de dados (LGPD, Lei 13.709/2018).
 *
 * Cada afirmação aqui corresponde a algo que o código faz — quando o código
 * mudar (um provedor novo, uma tabela nova na exportação, um prazo novo), este
 * texto precisa mudar junto. As fontes principais: backend/app/models.py,
 * routers/profile.py (exportação e exclusão), routers/social.py (o cartão),
 * routers/varredura.py (a triagem sem autor), config.py (os provedores).
 */

import { EmailContato, Fichas, Forte, LinkDoc, Lista, Nota, P, Subtitulo, type DocumentoLegal } from "./LegalLayout";

export const PRIVACIDADE: DocumentoLegal = {
  path: "/privacidade",
  aba: "Privacidade",
  kicker: "Privacidade e uso de dados",
  titulo: "Política de privacidade",
  introducao:
    "Como o PathR coleta, usa, guarda e compartilha os seus dados pessoais, e como você exerce os seus direitos previstos na Lei Geral de Proteção de Dados (Lei nº 13.709/2018).",
  resumo: [
    "Coletamos o necessário para montar e acompanhar o seu plano de estudos: conta, perfil, currículo e progresso.",
    "Não vendemos dados, não mostramos anúncios e não usamos ferramentas de análise ou pixels de publicidade.",
    "O currículo e o conteúdo de estudo são enviados a provedores de inteligência artificial para gerar o plano, os quizzes e as correções.",
    "Outras contas veem só o seu cartão (nome, @, foto, cidade, objetivo e tecnologias) — nunca o seu e-mail ou a data de nascimento.",
    "Você pode exportar tudo em um arquivo ou excluir a conta a qualquer momento, em Configurações › Avisos e privacidade.",
    "Dúvidas ou pedidos sobre seus dados: rodgoocode@hotmail.com.",
  ],
  secoes: [
    {
      id: "controlador",
      titulo: "Quem cuida dos seus dados",
      corpo: (
        <>
          <P>
            O PathR é um aplicativo de plano de estudos para quem trabalha com tecnologia, disponível em{" "}
            <Forte>pathr.notter.com.br</Forte>, com a API em <Forte>api.pathr.notter.com.br</Forte>. Ele é
            desenvolvido e operado por <Forte>Rodrigo Carvalho</Forte>, que é o controlador dos dados pessoais
            tratados no app, nos termos do art. 5º, VI, da LGPD.
          </P>
          <P>
            Para qualquer assunto sobre privacidade — dúvidas, pedidos de acesso, correção ou exclusão — o canal de
            contato, que também faz as vezes de encarregado (art. 41), é <EmailContato />.
          </P>
          <P>
            Embora o endereço fique sob o domínio notter.com.br, o PathR é independente: tem banco de dados, contas e
            credenciais próprios. Uma conta do PathR não dá acesso a outros aplicativos, e o contrário também vale.
          </P>
        </>
      ),
    },
    {
      id: "dados-coletados",
      titulo: "Quais dados coletamos",
      corpo: (
        <>
          <Subtitulo>Conta e acesso</Subtitulo>
          <Lista
            itens={[
              "Nome, e-mail, nome de usuário (@) e a data de criação da conta.",
              "A senha, guardada apenas como hash (Argon2id) — nunca o texto da senha.",
              "Preferências da conta: idioma, fuso horário e tema.",
              "Se você ativar: o segredo do segundo fator (TOTP), guardado cifrado, e os códigos de recuperação, guardados como hash.",
              "Se você cadastrar chaves de acesso (passkeys): apenas a parte pública da chave, o nome que você deu a ela e as datas de uso. A chave privada nunca sai do seu aparelho.",
            ]}
          />
          <Subtitulo>Perfil</Subtitulo>
          <Lista
            itens={[
              "Data de nascimento, cidade, estado (UF) e país.",
              "Cargo atual, cargo ou objetivo desejado, senioridade, anos de experiência, horas de estudo por semana, estilo de aprendizado e objetivos.",
              "Opcionais: título, bio, links do LinkedIn e do GitHub e foto de perfil.",
              "Preferências de avisos por e-mail, se você aparece nas sugestões de pessoas e o raio de busca de vagas presenciais.",
            ]}
          />
          <Subtitulo>Currículo</Subtitulo>
          <Lista
            itens={[
              "O arquivo enviado (PDF, DOCX, ODT, RTF, TXT ou MD, até 10 MB), o nome do arquivo e uma impressão digital (hash) do conteúdo, usada para não reprocessar o mesmo arquivo.",
              "O texto extraído do arquivo e o que a IA leu nele: tecnologias, nível estimado de cada uma, cargo e anos de experiência.",
            ]}
          />
          <Nota>
            O currículo é enviado como está. Se ele tiver telefone, endereço ou outros contatos, esses dados vão junto.
            Se preferir, remova-os do arquivo antes de enviar — eles não são necessários para montar o plano.
          </Nota>
          <Subtitulo>Estudo e progresso</Subtitulo>
          <Lista
            itens={[
              "Competências e níveis de proficiência (vindos do currículo, de quizzes ou ajustados por você).",
              "Roadmap, módulos, materiais salvos e o progresso em cada um, cursos e certificados marcados.",
              "Quizzes, respostas e a fila de revisão espaçada; explicações e atividades que você escreveu e as correções delas; checklists semanais; exemplos gerados no laboratório de código.",
              "Módulo de idiomas: nivelamento, sessões de treino (leitura, escuta, escrita e fala), respostas e vocabulário.",
              "Atividade diária: minutos estudados, XP, sequência e o mapa do ano.",
            ]}
          />
          <Subtitulo>Pessoas e relatos</Subtitulo>
          <Lista
            itens={[
              "Amizades e convites enviados ou recebidos.",
              "Relatos (reclamações e sugestões): tipo, mensagem, página em que você estava, foto anexada (opcional), status e a nota da moderação.",
            ]}
          />
          <Subtitulo>Dados técnicos e de segurança</Subtitulo>
          <Lista
            itens={[
              "Endereço IP e identificação do navegador (user agent) de cada sessão e dos eventos de segurança, como cadastro, entradas, tentativas que falharam e uso do segundo fator.",
              "Contadores de limite de uso, associados ao IP, ao e-mail de destino ou à conta, para impedir abuso.",
              "O registro de quais avisos por e-mail foram enviados a você e em que dia, para não repetir o mesmo aviso.",
              "Registros de erros do servidor: a rota, o tipo de erro e uma mensagem da qual e-mails, identificadores e tokens são removidos antes de gravar.",
            ]}
          />
          <Subtitulo>O que não coletamos</Subtitulo>
          <Lista
            itens={[
              "Não usamos ferramentas de análise de audiência nem pixels de publicidade.",
              "Não pedimos sua localização pelo aparelho (GPS) — a cidade é a que você informa.",
              "Não coletamos dados de pagamento: o PathR é gratuito.",
            ]}
          />
        </>
      ),
    },
    {
      id: "finalidades",
      titulo: "Para que usamos e com qual base legal",
      corpo: (
        <>
          <Lista
            itens={[
              <>
                <Forte>Prestar o serviço que você pediu</Forte> (execução de contrato, art. 7º, V): criar e manter a conta,
                ler o currículo, gerar e ajustar o roadmap, quizzes, explicações e treinos, medir o progresso, buscar
                materiais e vagas compatíveis com o seu perfil e a sua região, e enviar os e-mails necessários, como a
                confirmação de cadastro e a redefinição de senha.
              </>,
              <>
                <Forte>Proteger as contas e o serviço</Forte> (legítimo interesse, art. 7º, IX, e prevenção à fraude,
                art. 11, II, g, quando aplicável): registros de segurança, bloqueio após tentativas erradas, limites de
                uso por IP ou por conta e registro de erros.
              </>,
              <>
                <Forte>Recursos sociais</Forte> (legítimo interesse): sugerir pessoas da sua cidade ou com tecnologias em
                comum. Você pode se opor a qualquer momento desligando &quot;Aparecer nas sugestões de amigos&quot;.
              </>,
              <>
                <Forte>Avisos por e-mail</Forte> (lembrete diário, resumo semanal, novidades, correção pronta, sequência
                em risco): cada um tem um interruptor próprio, e você liga ou desliga quando quiser.
              </>,
              <>
                <Forte>Verificar a idade mínima</Forte>: a data de nascimento é usada para confirmar que você tem ao menos
                14 anos.
              </>,
              <>
                <Forte>Moderação e melhoria do app</Forte> (legítimo interesse): analisar os relatos enviados e corrigir
                defeitos.
              </>,
              <>
                <Forte>Cumprir obrigações legais e defender direitos</Forte> (art. 7º, II e VI), quando necessário.
              </>,
            ]}
          />
          <Nota>
            Não vendemos, alugamos ou cedemos seus dados para publicidade. Não usamos seus dados para decisões que afetem
            você fora do app.
          </Nota>
        </>
      ),
    },
    {
      id: "inteligencia-artificial",
      titulo: "Inteligência artificial",
      corpo: (
        <>
          <P>
            Boa parte do PathR funciona com modelos de linguagem de terceiros. Para isso, enviamos a eles o conteúdo
            necessário para cada tarefa:
          </P>
          <Lista
            itens={[
              "Leitura do currículo: o arquivo PDF inteiro (para preservar o layout) ou o texto extraído dos outros formatos.",
              "Plano de estudos e sugestões: objetivo, senioridade, horas disponíveis e competências.",
              "Quizzes, explicações, correções de atividades, exemplos de código e treinos de idioma: o assunto e o texto ou código que você escreveu.",
            ]}
          />
          <P>
            Os provedores são usados em rotação — se um estiver fora do ar ou sem cota, o pedido vai para o seguinte:{" "}
            <Forte>Google Gemini, Groq, Cerebras, Mistral AI e OpenRouter</Forte>. Nunca enviamos sua senha ou dados de
            acesso a eles. Alguns desses provedores são usados em planos gratuitos, cujos termos podem permitir que o
            conteúdo recebido seja usado para melhorar os serviços deles; por isso, evite colocar dados sensíveis em
            textos e atividades.
          </P>
          <P>
            O que a IA produz é uma estimativa. Nada do que ela lê no currículo entra no seu perfil sem você revisar e
            confirmar, e cada conta tem um limite diário de uso da IA.
          </P>
        </>
      ),
    },
    {
      id: "compartilhamento",
      titulo: "Com quem compartilhamos",
      corpo: (
        <>
          <P>
            Para funcionar, o PathR depende de fornecedores que tratam dados em nosso nome (operadores). Cada um recebe
            apenas o que precisa para a sua função:
          </P>
          <Fichas
            itens={[
              { nome: "Supabase", papel: "Banco de dados e armazenamento", detalhe: "Guarda todos os dados da conta. Os arquivos (currículo, fotos) ficam em espaços privados, sem endereço público." },
              { nome: "Fly.io", papel: "Hospedagem da API", detalhe: "Processa as requisições ao servidor, hospedado na região de São Paulo." },
              { nome: "Cloudflare Pages", papel: "Hospedagem do site", detalhe: "Entrega as páginas do app; recebe dados técnicos de acesso, como IP e navegador." },
              { nome: "Brevo", papel: "E-mail transacional", detalhe: "Envia confirmação de cadastro, redefinição de senha e os avisos que você mantiver ligados. Recebe seu nome, e-mail e o conteúdo da mensagem." },
              { nome: "Google Gemini, Groq, Cerebras, Mistral AI, OpenRouter", papel: "Inteligência artificial", detalhe: "Recebem o conteúdo descrito na seção anterior." },
              { nome: "DeepL", papel: "Tradução", detalhe: "Traduz palavras e trechos consultados no módulo de idiomas. Recebe só o texto a traduzir." },
              { nome: "Tavily, Brave Search e YouTube Data API", papel: "Busca de materiais e vagas", detalhe: "Recebem termos de busca, como tecnologia, assunto, cargo e cidade — não o seu nome ou e-mail." },
              { nome: "Adzuna, Gupy e Remotive", papel: "Vagas de emprego", detalhe: "Recebem o termo de busca e, na Adzuna, a cidade e o raio escolhidos. As vagas são anúncios desses sites." },
              { nome: "YouTube (Google)", papel: "Player de vídeo", detalhe: "Vídeos de estudo usam o player incorporado do YouTube, que recebe dados técnicos do seu navegador e segue a política do Google." },
              { nome: "Google Fonts", papel: "Fonte tipográfica", detalhe: "Entrega a fonte Inter; recebe o IP e dados técnicos do navegador." },
              { nome: "Notion", papel: "Triagem interna", detalhe: "Espaço privado do operador onde relatos e erros são organizados — relatos sem nome, e-mail ou @ de quem os enviou." },
              { nome: "Anthropic (Claude)", papel: "Rotina diária de triagem", detalhe: "Uma rotina automatizada lê os relatos sem autor e os erros do servidor para organizá-los no Notion." },
            ]}
          />
          <P>Além desses operadores, dados podem ser compartilhados:</P>
          <Lista
            itens={[
              "Com outras contas do PathR, nos limites descritos em “O que outras pessoas veem”.",
              "Com a moderação, no caso dos relatos.",
              "Com autoridades, quando houver obrigação legal ou ordem judicial.",
            ]}
          />
        </>
      ),
    },
    {
      id: "outras-pessoas",
      titulo: "O que outras pessoas veem",
      corpo: (
        <>
          <P>
            Outras contas conectadas ao PathR podem ver o seu <Forte>cartão</Forte>: nome, @, foto de perfil, cidade e
            UF, objetivo, cargo, senioridade e até cinco tecnologias do seu perfil, além das que vocês têm em comum.
          </P>
          <P>
            O cartão <Forte>nunca</Forte> mostra seu e-mail, data de nascimento, currículo, bio, respostas de quizzes ou
            detalhes do seu progresso. Visitantes sem conta não veem nada.
          </P>
          <Lista
            itens={[
              <>
                <Forte>Aparecer nas sugestões de amigos</Forte> vem ligado. Desligado, você sai das sugestões e da busca por parte
                do nome, e sua foto deixa de aparecer para quem não tem conexão com você. A opção fica em Configurações ›
                Avisos e privacidade.
              </>,
              <>
                A busca pelo <Forte>@ exato</Forte> encontra qualquer conta, para que alguém a quem você passou o seu @
                consiga te adicionar.
              </>,
              <>
                Um convite recusado é apagado — quem convidou não é avisado da recusa.
              </>,
            ]}
          />
        </>
      ),
    },
    {
      id: "relatos",
      titulo: "Relatos e moderação",
      corpo: (
        <>
          <P>
            Quando você envia uma reclamação ou sugestão pela tela Relatar, ela fica visível para você e para a
            moderação. A moderação vê seu nome, @ e e-mail, para poder responder. A foto anexada só sai pelo servidor,
            para você e para a moderação.
          </P>
          <P>
            Uma vez por dia, uma rotina automatizada copia os relatos recentes <Forte>sem qualquer identificação de
            quem os enviou</Forte> (apenas tipo, mensagem, página e status) para um espaço privado de triagem no Notion,
            e a moderação recebe por e-mail um resumo com a contagem de relatos e erros do dia.
          </P>
        </>
      ),
    },
    {
      id: "retencao",
      titulo: "Por quanto tempo guardamos",
      corpo: (
        <>
          <Lista
            itens={[
              <>
                <Forte>Conta, perfil e dados de estudo</Forte>: enquanto a conta existir. Ao excluir a conta, esses
                registros são apagados do banco na hora, sem período de carência.
              </>,
              <>
                <Forte>Currículos</Forte>: até você apagá-los na tela do currículo (o arquivo é removido do
                armazenamento) ou excluir a conta.
              </>,
              <>
                <Forte>Links de e-mail</Forte>: o de confirmação vale por 3 dias e o de nova senha por 1 hora; ambos são
                de uso único.
              </>,
              <>
                <Forte>Sessão</Forte>: o acesso expira em 30 minutos e é renovado automaticamente por até 30 dias, ou até
                você sair.
              </>,
              <>
                <Forte>Contadores de limite de uso</Forte>: apagados após 2 dias.
              </>,
              <>
                <Forte>Registros de erros do servidor</Forte>: apagados após 30 dias (a mensagem já é gravada sem e-mail,
                identificadores ou tokens). <Forte>Registros de segurança</Forte>: pelo necessário para proteger as
                contas. Os registros de segurança ligados à sua conta (tipo de evento, data, IP e
                navegador) são apagados junto com ela; tentativas de acesso que não chegaram a identificar uma conta
                não têm dono e ficam só pelo tempo de prevenção a fraudes (art. 16 da LGPD).
              </>,
              <>
                <Forte>Triagem no Notion</Forte>: os relatos copiados, que não identificam o autor, podem ser mantidos
                como histórico de correções.
              </>,
            ]}
          />
          <Nota>
            Ao excluir a conta, os arquivos enviados — currículos, foto de perfil e fotos anexadas a relatos — são
            removidos do armazenamento junto com os dados. Se algo ficar para trás por falha técnica, peça a remoção
            pelo e-mail <EmailContato />.
          </Nota>
        </>
      ),
    },
    {
      id: "direitos",
      titulo: "Seus direitos",
      corpo: (
        <>
          <P>A LGPD (art. 18) garante a você, entre outros, os direitos abaixo. A maioria pode ser exercida no próprio app:</P>
          <Fichas
            itens={[
              { nome: "Acesso e portabilidade", papel: "Configurações › Avisos e privacidade", detalhe: "“Exportar meus dados” baixa um arquivo JSON com conta, perfil, competências, currículos (sem o texto extraído), roadmap, quizzes, atividade, idiomas, materiais, cursos, explicações, checklists, relatos e amizades (só com o @ da outra pessoa)." },
              { nome: "Correção", papel: "Configurações e Perfil", detalhe: "Nome, dados do perfil, objetivo, competências e preferências podem ser editados a qualquer momento." },
              { nome: "Eliminação", papel: "Configurações › Avisos e privacidade", detalhe: "“Excluir conta” apaga a conta, os dados vinculados, os arquivos enviados, relatos, amizades e registros de segurança da conta. Currículos também podem ser apagados um a um." },
              { nome: "Revogar consentimento e se opor", papel: "Configurações › Avisos e privacidade", detalhe: "Desligue avisos por e-mail e a opção de aparecer nas sugestões." },
              { nome: "Informação", papel: "Esta página", detalhe: "Com quem compartilhamos, para que e por quanto tempo." },
              { nome: "Demais pedidos", papel: "Por e-mail", detalhe: "Qualquer outro direito, ou dúvida sobre o que guardamos, pode ser pedido por e-mail." },
            ]}
          />
          <P>
            Pedidos por e-mail são respondidos em até 15 dias, como prevê o art. 19 da LGPD. Podemos pedir que o e-mail
            venha do endereço cadastrado na conta, para confirmar que o pedido é seu. Você também pode apresentar
            reclamação à Autoridade Nacional de Proteção de Dados (ANPD).
          </P>
        </>
      ),
    },
    {
      id: "idade",
      titulo: "Idade mínima",
      corpo: (
        <P>
          É preciso ter ao menos <Forte>14 anos</Forte> para criar uma conta; o cadastro confere a data de nascimento.
          Dados de adolescentes são tratados no seu melhor interesse (art. 14 da LGPD), e recomendamos que quem tem
          menos de 18 anos use o PathR com o conhecimento dos pais ou responsáveis.
        </P>
      ),
    },
    {
      id: "cookies",
      titulo: "Cookies e armazenamento no aparelho",
      corpo: (
        <>
          <Lista
            itens={[
              <>
                <Forte>Cookies de sessão</Forte> (essenciais): dois cookies da API mantêm você conectado. São HttpOnly
                (o código da página não consegue lê-los), Secure e SameSite=Strict.
              </>,
              <>
                <Forte>Armazenamento local</Forte>: o app guarda no navegador a tela e as opções de interface em uso, e
                uma cópia das informações já carregadas para funcionar sem internet. Essa cópia é apagada quando você
                sai da conta.
              </>,
              <>
                <Forte>Arquivos do app</Forte>: quando instalado na tela de início, os arquivos do site ficam em cache
                para abrir mais rápido.
              </>,
            ]}
          />
          <P>Não usamos cookies de publicidade nem de análise.</P>
        </>
      ),
    },
    {
      id: "transferencia",
      titulo: "Transferência internacional",
      corpo: (
        <P>
          Parte dos fornecedores listados — em especial os de inteligência artificial, e-mail, entrega do site e
          triagem — processa dados em servidores fora do Brasil. Essas transferências acontecem para executar o serviço
          que você solicitou (art. 33, IX, da LGPD), com fornecedores que mantêm compromissos próprios de proteção de
          dados.
        </P>
      ),
    },
    {
      id: "incidentes",
      titulo: "Segurança e incidentes",
      corpo: (
        <P>
          As medidas que usamos para proteger os dados estão descritas na página de <LinkDoc href="/seguranca">Segurança</LinkDoc>. Se ocorrer um incidente
          de segurança que possa causar risco ou dano relevante, comunicaremos a ANPD e as pessoas afetadas, conforme o
          art. 48 da LGPD.
        </P>
      ),
    },
    {
      id: "mudancas",
      titulo: "Mudanças nesta política",
      corpo: (
        <P>
          Esta política pode mudar quando o app mudar — por exemplo, com um recurso ou fornecedor novo. A data de
          atualização no topo sempre indica a versão em vigor, e mudanças relevantes serão avisadas no app ou por
          e-mail antes de valer.
        </P>
      ),
    },
  ],
};
