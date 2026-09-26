"""Os textos FIXOS que o servidor escreve para a tela, nos cinco idiomas.

## Por que existe

`services/idioma.py` diz: "texto fixo é traduzido na tela". Vale para quase
tudo — menos para o que o SERVIDOR escreve. O plano da semana monta
"Recordação ativa · 15 min", e o Laboratório monta "Em andamento no seu
roadmap: Docker". Essas frases chegam prontas ao navegador, e a tela não tem
como traduzir o que já veio escrito: com o app em inglês, elas ficavam em
português no meio da interface traduzida.

A alternativa seria o servidor mandar CHAVE e a tela traduzir. É mais correto
em teoria, mas muda o formato de várias respostas e obriga a manter as mesmas
frases em dois lugares. Aqui o servidor já sabe o idioma de quem pediu (o
cabeçalho `X-Pathr-Idioma`, guardado em `idioma.idioma_da_requisicao`), então
ele mesmo escolhe a frase.

Não confundir com `services/traducao.py`: aquilo é tradução dinâmica pelo
DeepL, para frase que nasce na hora (exercício, consulta de palavra). Rótulo
fixo não precisa de rede nem de custo por chamada — precisa de uma tabela.

## O que NÃO entra aqui

- **Prompt de IA**: é instrução para o modelo, não texto para gente.
- **Log**: quem lê é quem opera, e a máquina fala uma língua só.
- **O que a IA escreve** (título de módulo, objetivo, explicação): nasce já no
  idioma de quem vai ler, pela instrução no prompt. Um roadmap GERADO em
  português continua em português depois de trocar o idioma — traduzir
  conteúdo já gravado é outro problema, que este arquivo não resolve.
"""

from __future__ import annotations

from app.services.idioma import PADRAO, idioma_da_requisicao

# Cada entrada: a chave e a frase em cada idioma. Chave em português porque é a
# língua do código; `{}` marca onde entra o que varia.
_TEXTOS: dict[str, dict[str, str]] = {
    # --- Os pilares do plano da semana (services/weekly_plan.py) ---
    "pilar.revisao": {
        "pt": "Repetição espaçada",
        "en": "Spaced repetition",
        "es": "Repetición espaciada",
        "fr": "Répétition espacée",
        "de": "Verteiltes Wiederholen",
    },
    "pilar.material": {
        "pt": "Estudo guiado",
        "en": "Guided study",
        "es": "Estudio guiado",
        "fr": "Étude guidée",
        "de": "Angeleitetes Lernen",
    },
    "pilar.quiz": {
        "pt": "Recordação ativa",
        "en": "Active recall",
        "es": "Recuerdo activo",
        "fr": "Rappel actif",
        "de": "Aktives Abrufen",
    },
    "pilar.feynman": {
        "pt": "Feynman",
        "en": "Feynman",
        "es": "Feynman",
        "fr": "Feynman",
        "de": "Feynman",
    },
    "pilar.pratica": {
        "pt": "Prática deliberada",
        "en": "Deliberate practice",
        "es": "Práctica deliberada",
        "fr": "Pratique délibérée",
        "de": "Bewusstes Üben",
    },
    # --- Os títulos das atividades da semana ---
    "atividade.material": {
        "pt": "Estudar o material de {titulo}",
        "en": "Study the material on {titulo}",
        "es": "Estudiar el material de {titulo}",
        "fr": "Étudier le matériel sur {titulo}",
        "de": "Das Material zu {titulo} durcharbeiten",
    },
    "atividade.quiz": {
        "pt": "Quiz de {titulo}",
        "en": "{titulo} quiz",
        "es": "Cuestionario de {titulo}",
        "fr": "Quiz sur {titulo}",
        "de": "Quiz zu {titulo}",
    },
    "atividade.feynman": {
        "pt": "Explicar {titulo} com suas palavras",
        "en": "Explain {titulo} in your own words",
        "es": "Explicar {titulo} con tus palabras",
        "fr": "Expliquer {titulo} avec vos mots",
        "de": "{titulo} in eigenen Worten erklären",
    },
    "atividade.pratica": {
        "pt": "Atividade prática de {titulo}",
        "en": "Hands-on activity on {titulo}",
        "es": "Actividad práctica de {titulo}",
        "fr": "Activité pratique sur {titulo}",
        "de": "Praktische Übung zu {titulo}",
    },
    "atividade.revisao": {
        "pt": "Revisar {quantos} conceitos pendentes",
        "en": "Review {quantos} pending concepts",
        "es": "Repasar {quantos} conceptos pendientes",
        "fr": "Réviser {quantos} concepts en attente",
        "de": "{quantos} offene Konzepte wiederholen",
    },
    "atividade.revisaoUm": {
        "pt": "Revisar 1 conceito pendente",
        "en": "Review 1 pending concept",
        "es": "Repasar 1 concepto pendiente",
        "fr": "Réviser 1 concept en attente",
        "de": "1 offenes Konzept wiederholen",
    },
    # --- Por que o Laboratório sugeriu aquilo (services/code_lab.py) ---
    "lab.noRoadmap": {
        "pt": "{situacao} no seu roadmap: {titulo}",
        "en": "{situacao} in your roadmap: {titulo}",
        "es": "{situacao} en tu roadmap: {titulo}",
        "fr": "{situacao} dans votre feuille de route : {titulo}",
        "de": "{situacao} in deiner Roadmap: {titulo}",
    },
    "lab.situacao.andamento": {
        "pt": "Em andamento",
        "en": "In progress",
        "es": "En curso",
        "fr": "En cours",
        "de": "In Arbeit",
    },
    "lab.situacao.proximo": {
        "pt": "Próximo",
        "en": "Next",
        "es": "Siguiente",
        "fr": "Prochain",
        "de": "Als Nächstes",
    },
    "lab.paraSeuNivel": {
        "pt": "Para o seu nível em {linguagem}",
        "en": "For your level in {linguagem}",
        "es": "Para tu nivel en {linguagem}",
        "fr": "Pour votre niveau en {linguagem}",
        "de": "Für dein Niveau in {linguagem}",
    },
    "lab.proximoPasso": {
        "pt": "Próximo passo em {linguagem}",
        "en": "Next step in {linguagem}",
        "es": "Siguiente paso en {linguagem}",
        "fr": "Prochaine étape en {linguagem}",
        "de": "Nächster Schritt in {linguagem}",
    },
    # --- A explicação de cada tipo de atividade, na lista da semana ---
    "detalhe.revisao": {
        "pt": "Vem antes do conteúdo novo: revisar no ponto em que se está esquecendo é o que consolida. Os conceitos voltam reescritos no próximo quiz.",
        "en": "It comes before new content: reviewing right when you are about to forget is what makes it stick. The concepts come back rewritten in the next quiz.",
        "es": "Va antes del contenido nuevo: repasar justo cuando estás olvidando es lo que consolida. Los conceptos vuelven reescritos en el próximo cuestionario.",
        "fr": "Cela vient avant le nouveau contenu : réviser au moment où l'on commence à oublier, c'est ce qui consolide. Les concepts reviennent réécrits au prochain quiz.",
        "de": "Kommt vor neuen Inhalten: Wiederholen genau dann, wenn man zu vergessen beginnt, festigt am meisten. Die Konzepte kehren im nächsten Quiz umformuliert zurück.",
    },
    "detalhe.material": {
        "pt": "Um vídeo, artigo ou documentação da Biblioteca. Base antes de teste — sem ela, o quiz vira chute.",
        "en": "A video, article or documentation from the Library. Groundwork before testing — without it, the quiz becomes guesswork.",
        "es": "Un vídeo, artículo o documentación de la Biblioteca. Base antes de la prueba: sin ella, el cuestionario se vuelve adivinanza.",
        "fr": "Une vidéo, un article ou une documentation de la Bibliothèque. La base avant le test : sans elle, le quiz devient du hasard.",
        "de": "Ein Video, Artikel oder eine Dokumentation aus der Bibliothek. Grundlage vor dem Test — ohne sie wird das Quiz zum Raten.",
    },
    "detalhe.quiz": {
        "pt": "Responder sem consultar é o que fixa. Errar aqui é parte do método: o erro volta reescrito na próxima rodada.",
        "en": "Answering without looking things up is what makes it stick. Getting it wrong here is part of the method: the mistake comes back rewritten in the next round.",
        "es": "Responder sin consultar es lo que fija. Equivocarse aquí es parte del método: el error vuelve reescrito en la próxima ronda.",
        "fr": "Répondre sans rien consulter, c'est ce qui ancre. Se tromper ici fait partie de la méthode : l'erreur revient réécrite au tour suivant.",
        "de": "Ohne Nachschlagen zu antworten ist das, was haften bleibt. Fehler gehören hier zur Methode: Der Fehler kommt in der nächsten Runde umformuliert zurück.",
    },
    "detalhe.feynman": {
        "pt": "Escreva como se explicasse para alguém que nunca viu o assunto. Onde o texto travar é onde o entendimento acaba.",
        "en": "Write as if explaining to someone who has never seen the subject. Where the text stalls is where your understanding ends.",
        "es": "Escribe como si se lo explicaras a alguien que nunca vio el tema. Donde el texto se traba es donde termina tu comprensión.",
        "fr": "Écrivez comme si vous expliquiez à quelqu'un qui n'a jamais vu le sujet. Là où le texte bloque, c'est là que la compréhension s'arrête.",
        "de": "Schreibe, als würdest du es jemandem erklären, der das Thema nie gesehen hat. Wo der Text stockt, endet das Verständnis.",
    },
    "detalhe.pratica": {
        "pt": "Resolver a atividade do módulo do zero, sem IA. Reconhecer a solução é diferente de produzi-la.",
        "en": "Solve the module activity from scratch, without AI. Recognising the solution is not the same as producing it.",
        "es": "Resolver la actividad del módulo desde cero, sin IA. Reconocer la solución no es lo mismo que producirla.",
        "fr": "Résoudre l'activité du module à partir de zéro, sans IA. Reconnaître la solution n'est pas la produire.",
        "de": "Die Modulaufgabe von Grund auf lösen, ohne KI. Eine Lösung wiederzuerkennen ist etwas anderes, als sie zu erzeugen.",
    },
    "detalhe.desafio": {
        "pt": "Você já tem a base. O ganho agora está em aplicar num problema maior, não em revisar o que já sabe.",
        "en": "You already have the basics. The gain now is in applying them to a bigger problem, not in reviewing what you already know.",
        "es": "Ya tienes la base. La ganancia ahora está en aplicarla a un problema mayor, no en repasar lo que ya sabes.",
        "fr": "Vous avez déjà les bases. Le gain est maintenant dans l'application à un problème plus vaste, pas dans la révision de l'acquis.",
        "de": "Die Grundlagen hast du schon. Der Gewinn liegt jetzt darin, sie auf ein größeres Problem anzuwenden, nicht im Wiederholen des Bekannten.",
    },
    # --- Níveis, que chegam à tela como palavra ---
    "nivel.iniciante": {
        "pt": "iniciante",
        "en": "beginner",
        "es": "principiante",
        "fr": "débutant",
        "de": "Anfänger",
    },
    "nivel.intermediario": {
        "pt": "intermediário",
        "en": "intermediate",
        "es": "intermedio",
        "fr": "intermédiaire",
        "de": "Mittelstufe",
    },
    "nivel.avancado": {
        "pt": "avançado",
        "en": "advanced",
        "es": "avanzado",
        "fr": "avancé",
        "de": "Fortgeschritten",
    },
}


def t(chave: str, **valores: object) -> str:
    """A frase no idioma de quem pediu, com os valores substituídos.

    Chave desconhecida volta como ela mesma, visível na tela. É feio de
    propósito: aparece no primeiro teste e some assim que a frase entra aqui —
    melhor do que devolver vazio e o texto sumir sem ninguém notar.
    """
    formas = _TEXTOS.get(chave)
    if not formas:
        return chave
    texto = formas.get(idioma_da_requisicao.get(), formas.get(PADRAO, chave))
    return texto.format(**valores) if valores else texto


def chaves() -> list[str]:
    """Todas as chaves declaradas — usado pelo teste que exige os 5 idiomas."""
    return sorted(_TEXTOS)


def formas(chave: str) -> dict[str, str]:
    return dict(_TEXTOS.get(chave, {}))
