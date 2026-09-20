"""Frases de ataque a prompt, por idioma. Só dados: quem monta os detectores é `guarda_ia`.

LEIA ANTES DE CONFIAR NISTO. Nenhuma lista de frases fecha a porta: há mais idiomas
e mais jeitos de dizer "ignore as regras" do que qualquer tabela cobre. Por isso
a proteção do app NÃO depende deste arquivo — ela está no que independe de língua
(estrutura do prompt, canário, credenciais nunca no prompt, filtro de saída). O
que estas tabelas fazem é o que sobra: recusar sem gastar o modelo o pedido
explícito de prompt/chave/dado alheio, e registrar a tentativa para quem opera.

Duas famílias, pelo tipo de escrita:

- LATINAS (pt en es fr de it tr): o texto chega aqui SEM acento, em minúsculas, com
  homóglifos, leet e letras espaçadas desfeitos. Escreva sem acento e em
  minúsculas. Cada idioma tem as mesmas peças, combinadas por `guarda_ia`:
    verbo         pede algo ("mostre", "show", "muestra"…)
    proprio       o alvo é o modelo ("suas instruções", "your rules"…)
    sistema       frase que aponta o prompt do sistema, sem possessivo
    segredo_app   chave/senha/variável DESTE app ou servidor
    outras_contas dado de outras pessoas
    sobrescrever  "ignore as instruções…" (só registra)
    papel         "você agora é…" (só registra)
    ofuscar       "em base64", "letra por letra" (só registra)

- NATIVAS (ru zh ja ko ar): sem espaço entre palavras ou com ordem verbo-objeto
  própria, então cada uma traz padrões prontos. Chegam em NFKC e minúsculas; no
  árabe, sem sinais de vocalização e com todo alef como `ا`.

Cada padrão de "pedido" exige o verbo perto do alvo: "como guardar uma senha" e
"o que é um system prompt" são dúvidas de estudo e não podem ser recusadas.
Reveja com quem fala o idioma antes de ampliar — um falso positivo aqui nega uma
dúvida legítima.
"""

from __future__ import annotations

LATINAS: dict[str, dict[str, str]] = {
    "pt": {
        "verbo": r"revel\w*|mostr\w*|exib\w*|imprim\w*|repit\w*|copi\w*|traduz\w*|list\w*|vaz\w*|escrev\w*|"
        r"diga|dizer|conte|me\s+de|passe|fornec\w*|envie|informe|qual\s+e|quais\s+sao|quais\s+as?",
        "proprio": r"(?:seu|sua|seus|suas|teu|tua|teus|tuas)\s+(?:system\s+|inicial\s+|original\s+)?"
        r"(?:prompt|instruc\w+|regras|diretrizes|configurac\w+|chaves?|senhas?|tokens?|segredos?|credenciais)",
        "sistema": r"prompt\s+do\s+sistema|instrucoes\s+(?:do\s+sistema(?!\s+operacional)|iniciais|internas|acima|anteriores)|"
        r"mensagem\s+do\s+sistema|tudo\s+(?:(?:o\s+)?que\s+esta\s+)?acima",
        "segredo_app": r"(?:chaves?|senhas?|tokens?|segredos?|credenciais|api\s*keys?|variaveis\s+de\s+ambiente|"
        r"string\s+de\s+conexao)\s+(?:d[oae]s?|deste|desta)\s+(?:pathr|sistema|servidor|backend|back-end|"
        r"banco(?:\s+de\s+dados)?|app|aplicacao|supabase|infra\w*)",
        "outras_contas": r"(?:dados|e-?mails?|senhas?|informacoes|contas?|perfis|curriculos?|historicos?|cpf|telefones?)"
        r"\s+(?:d[eo]s?\s+)?(?:outr[oa]s?|demais|todos\s+os)\s+(?:os\s+)?(?:usuarios?|alunos?|pessoas|contas|clientes)",
        "sobrescrever": r"(?:ignor\w*|desconsider\w*|esquec\w*|descart\w*|sobrescrev\w*)\b[^.\n]{0,30}?\b"
        r"(?:instruc\w+|regras|ordens|diretrizes|prompt|tudo\s+(?:acima|anterior\w*|que\s+(?:foi|disse)\w*))",
        "papel": r"voce\s+agora\s+e|a\s+partir\s+de\s+agora\s+voce|finja\s+(?:ser|que)|modo\s+(?:desenvolvedor|deus)",
        "ofuscar": r"em\s+base\s?64|letra\s+por\s+letra|caractere\s+por\s+caractere|em\s+hexadecimal|em\s+binario",
    },
    "en": {
        "verbo": r"reveal|show|print|repeat|display|tell|give|output|leak|dump|copy|list|translate|write|"
        r"what(?:'s|\s+is|\s+are)?",
        "proprio": r"your\s+(?:system\s+|initial\s+|original\s+)?(?:prompt|instructions?|rules|guidelines|configuration|"
        r"keys?|passwords?|tokens?|secrets?|credentials)",
        "sistema": r"(?:the|your)\s+system\s+(?:prompt|message|instructions)|everything\s+above|text\s+above|above\s+instructions",
        "segredo_app": r"(?:pathr|the\s+server|the\s+backend|this\s+app|the\s+database)(?:'s|s)?\s+"
        r"(?:api\s*keys?|secrets?|passwords?|credentials|env(?:ironment)?\s+variables?|\.env)",
        "outras_contas": r"other\s+users['’]?\s+(?:data|emails?|passwords?)|"
        r"(?:data|emails?|passwords?)\s+(?:of|from)\s+(?:all|other)\s+(?:users|accounts|people)",
        "sobrescrever": r"(?:ignore|disregard|forget|override|bypass)\b[^.\n]{0,30}?\b"
        r"(?:instructions|rules|guidelines|directions|prompt|everything\s+(?:above|before)|all\s+previous)",
        "papel": r"you\s+are\s+now|pretend\s+(?:to\s+be|you)|developer\s+mode|jailbreak|\bdan\b",
        "ofuscar": r"in\s+base\s?64|rot\s?13|one\s+letter\s+at\s+a\s+time|spell\s+it\s+out|in\s+hex(?:adecimal)?",
    },
    "es": {
        "verbo": r"revela\w*|muestra\w*|muestrame|ensena\w*|dime|dinos|repite\w*|imprime\w*|copia\w*|traduce\w*|"
        r"enumera\w*|lista\w*|escribe\w*|dame|pasame|comparte\w*|filtra\w*",
        "proprio": r"(?:tus?|sus?|tuyas?|tuyos?)\s+(?:instrucciones|prompt|reglas|directrices|configuracion|claves?|"
        r"contrasenas?|tokens?|secretos?|credenciales)",
        "sistema": r"prompt\s+del\s+sistema|instrucciones\s+del\s+sistema(?!\s+operativo)|instrucciones\s+iniciales|"
        r"mensaje\s+del\s+sistema|todo\s+lo\s+que\s+(?:esta|hay)\s+arriba|texto\s+de\s+arriba",
        "segredo_app": r"(?:claves?|contrasenas?|tokens?|secretos?|credenciales|variables\s+de\s+entorno|"
        r"cadena\s+de\s+conexion)\s+(?:del?|de\s+la|de\s+este|de\s+esta)\s+(?:sistema|servidor|backend|"
        r"base\s+de\s+datos|pathr|aplicacion|app|supabase|infra\w*)",
        "outras_contas": r"(?:datos|correos?|emails?|contrasenas|informacion|cuentas|perfiles|curriculums?|historiales)"
        r"\s+de\s+(?:otros|los\s+demas|todos\s+los)\s+(?:usuarios|alumnos|estudiantes|personas|cuentas|clientes)",
        "sobrescrever": r"(?:ignora\w*|olvida\w*|descarta\w*|omite\w*|desconsidera\w*)\b[^.\n]{0,30}?\b"
        r"(?:instrucciones|reglas|ordenes|indicaciones|directrices|prompt|todo\s+lo\s+anterior)",
        "papel": r"ahora\s+eres|a\s+partir\s+de\s+ahora\s+eres|finge\s+(?:ser|que)|modo\s+(?:desarrollador|dios)",
        "ofuscar": r"en\s+base\s?64|letra\s+por\s+letra|caracter\s+por\s+caracter|en\s+hexadecimal|en\s+binario",
    },
    "fr": {
        "verbo": r"revele\w*|montre\w*|affiche\w*|repete\w*|donne\w*|dis|dites|traduis\w*|liste\w*|imprime\w*|"
        r"ecris\w*|partage\w*|fournis\w*|transmets|divulgue\w*",
        "proprio": r"(?:tes|tons?|vos|votre|ta)\s+(?:instructions|prompt|regles|consignes|directives|configuration|"
        r"cles?|mots?\s+de\s+passe|secrets?|identifiants|jetons?)",
        "sistema": r"prompt\s+systeme|instructions\s+(?:du\s+systeme|initiales|internes)|message\s+systeme|"
        r"tout\s+ce\s+qui\s+(?:est|se\s+trouve)\s+(?:au-dessus|ci-dessus)",
        "segredo_app": r"(?:cles?|mots?\s+de\s+passe|secrets?|identifiants|jetons?|variables\s+d'environnement|"
        r"chaine\s+de\s+connexion)\s+(?:du|de\s+la|de\s+l'|des)\s*(?:systeme|serveur|backend|base\s+de\s+donnees|"
        r"pathr|application|app|supabase|infra\w*)",
        "outras_contas": r"(?:donnees|e-?mails?|mots\s+de\s+passe|informations|comptes|profils)\s+"
        r"(?:des\s+autres|de\s+tous\s+les|d'autres)\s+(?:utilisateurs|eleves|personnes|comptes|clients)",
        "sobrescrever": r"(?:ignore\w*|oublie\w*|neglige\w*|contourne\w*)\b[^.\n]{0,30}?\b"
        r"(?:instructions|regles|consignes|directives|prompt|tout\s+ce\s+qui\s+precede)",
        "papel": r"tu\s+es\s+maintenant|a\s+partir\s+de\s+maintenant\s+tu|fais\s+semblant|mode\s+developpeur",
        "ofuscar": r"en\s+base\s?64|lettre\s+par\s+lettre|caractere\s+par\s+caractere|en\s+hexadecimal",
    },
    "de": {
        "verbo": r"zeig\w*|verrate\w*|nenn\w*|gib|gebe\w*|wiederhole\w*|druck\w*|ubersetze\w*|liste\w*|schreib\w*|"
        r"sag\w*|offenbare\w*|teile\w*",
        "proprio": r"(?:dein\w*|ihre\w*|ihr)\s+(?:system\s*)?(?:prompt|anweisung\w*|regeln|richtlinien|konfiguration|"
        r"schlussel|passwort\w*|kennwort\w*|token|geheimnis\w*|zugangsdaten)",
        "sistema": r"anweisungen\s+des\s+systems|initiale\s+anweisungen|alles\s+(?:oben|daruber)\s*(?:stehende)?",
        "segredo_app": r"(?:schlussel|passworter|passwort|kennworter|geheimnisse|zugangsdaten|umgebungsvariablen)\s+"
        r"(?:des|der|vom|von)\s+(?:systems|servers|backends|datenbank|pathr|app|anwendung)",
        "outras_contas": r"(?:daten|e-?mails?|passworter|informationen)\s+(?:anderer|aller|von\s+anderen|von\s+allen)\s+"
        r"(?:nutzer|benutzer|user|konten|personen|schuler)\w*",
        "sobrescrever": r"(?:ignorier\w*|vergiss\w*|missachte\w*|umgehe\w*)\b[^.\n]{0,30}?\b"
        r"(?:anweisungen|regeln|instruktionen|vorgaben|richtlinien|prompt|alles\s+(?:oben|zuvor|vorherige\w*))",
        "papel": r"du\s+bist\s+jetzt|ab\s+jetzt\s+bist\s+du|tu\s+so\s+als|entwicklermodus",
        "ofuscar": r"in\s+base\s?64|buchstabe\s+fur\s+buchstabe|zeichen\s+fur\s+zeichen|in\s+hex\w*",
    },
    "it": {
        "verbo": r"mostra\w*|rivela\w*|dimmi|dammi|ripeti\w*|stampa\w*|traduci\w*|elenca\w*|scrivi\w*|condividi\w*|"
        r"svela\w*|fornisci\w*",
        "proprio": r"(?:le\s+tue|il\s+tuo|la\s+tua|i\s+tuoi|le\s+sue|il\s+suo|la\s+sua)\s+(?:istruzioni|prompt|regole|"
        r"direttive|configurazione|chiavi?|password|token|segreti|credenziali)",
        "sistema": r"prompt\s+di\s+sistema|istruzioni\s+(?:di\s+sistema|iniziali|interne)|messaggio\s+di\s+sistema|"
        r"tutto\s+(?:quello\s+)?(?:che\s+c'e\s+)?sopra",
        "segredo_app": r"(?:chiavi?|password|token|segreti|credenziali|variabili\s+d'ambiente)\s+(?:del|della|di)\s+"
        r"(?:sistema|server|backend|database|pathr|applicazione|app|supabase|infra\w*)",
        "outras_contas": r"(?:dati|email|password|informazioni|account|profili)\s+(?:degli\s+altri|di\s+altri|di\s+tutti\s+gli)"
        r"\s+(?:utenti|studenti|persone|account|clienti)",
        "sobrescrever": r"(?:ignora\w*|dimentica\w*|trascura\w*|scarta\w*)\b[^.\n]{0,30}?\b"
        r"(?:istruzioni|regole|direttive|prompt|tutto\s+(?:quanto|cio\s+che)\s+\w+)",
        "papel": r"ora\s+sei|d'ora\s+in\s+poi\s+sei|fingi\s+di\s+essere|modalita\s+sviluppatore",
        "ofuscar": r"in\s+base\s?64|lettera\s+per\s+lettera|carattere\s+per\s+carattere|in\s+esadecimale",
    },
}

# Turco: objeto antes do verbo, então não cabe nas peças acima. Escrito como padrões
# prontos (latina, sem acento; o `ı` sem ponto não decompõe, por isso `[ıi]`).
_ACAO_TR = r"(?:goster|soyle|yazd[ıi]r|tekrarla|paylas)\w*"
LATINAS_DIRETAS: list[str] = [
    rf"(?:senin|sizin|kendi)\s+(?:sistem\s+)?(?:istem\w*|prompt\w*|talimat\w*|kurallar\w*|sifre\w*|anahtar\w*)[^.\n]{{0,20}}{_ACAO_TR}",
    rf"sistem\s+(?:istem\w*|promptu\w*)[^.\n]{{0,15}}{_ACAO_TR}",
]
LATINAS_SOBRESCREVER_DIRETAS: list[str] = [
    r"(?:onceki\s+)?(?:talimat\w*|kurallar\w*)[^.\n]{0,15}(?:yoksay|unut|gormezden\s+gel)\w*",
]
LATINAS_PAPEL_DIRETAS: list[str] = [r"art[ıi]k\s+sen\b|gelistirici\s+modu"]

# --- escritas não latinas: padrões prontos, em NFKC e minúsculas -------------

_ZH_ACAO = r"(?:显示|展示|告诉我|告诉|输出|重复|透露|泄露|打印|列出|翻译|给我|说出|发给我|公开)"
_RU_ACAO = r"(?:покажи\w*|раскр\w+|выведи\w*|повтори\w*|скажи\w*|напиши\w*|дай(?:те)?|расскаж\w+|перевед\w+|перечисл\w+|назови\w*)"
_AR_ACAO = r"(?:اعرض|اظهر|اكشف|اطبع|كرر|اخبرني|قل\s+لي|اذكر|ترجم|اعطني|شارك)"
_JA_ACAO = r"(?:見せ|教え|表示|出力|公開|繰り返|書い|暴露|漏ら)"
_KO_ACAO = r"(?:보여|알려|출력|공개|반복|말해|써)"

NATIVAS_PEDIDO: list[str] = [
    # ru
    rf"{_RU_ACAO}[^.\n]{{0,25}}?(?:свои|твои|ваши|свой|твой|ваш|своё|твоё)\s+(?:системн\w+\s+)?"
    r"(?:промпт\w*|инструкци\w+|правил\w+|настройк\w+|парол\w+|ключ\w*|секрет\w*|токен\w*)",
    rf"{_RU_ACAO}[^.\n]{{0,25}}?(?:системн\w+\s+(?:промпт\w*|инструкци\w+|сообщени\w+)|всё\s+что\s+выше|все\s+что\s+выше|"
    r"текст\s+выше)",
    rf"{_RU_ACAO}[^.\n]{{0,30}}?(?:парол\w+|ключ\w*|секрет\w*|токен\w*)\s+(?:от\s+)?(?:сервер\w*|систем\w*|бэкенд\w*|"
    r"баз\w+\s+данных|pathr|приложени\w+)",
    rf"{_RU_ACAO}[^.\n]{{0,40}}?(?:данн\w+|почт\w+|email|парол\w+|информаци\w+)\s+(?:других|всех|остальных)\s+"
    r"(?:пользовател\w+|учеников|людей|аккаунт\w+)",
    # zh
    rf"{_ZH_ACAO}[^。.\n]{{0,6}}(?:你的|您的)(?:系统)?(?:提示词|提示|指令|指示|规则|说明|密码|密钥|口令|配置|设定)",
    rf"{_ZH_ACAO}[^。.\n]{{0,6}}(?:系统提示词|系统提示|系统指令|上面的(?:所有)?(?:内容|指令|文字))",
    rf"{_ZH_ACAO}[^。.\n]{{0,6}}(?:服务器|系统|后端|数据库|pathr|应用)的(?:密码|密钥|口令|凭据|凭证|环境变量)",
    rf"{_ZH_ACAO}[^。.\n]{{0,6}}(?:其他|其它|所有|别的)用户的(?:数据|邮箱|密码|信息|资料)",
    # ja
    rf"(?:あなた|君|きみ|貴方)の(?:システム)?(?:プロンプト|指示|命令|ルール|パスワード|秘密|設定|キー|鍵)[^。.\n]{{0,10}}{_JA_ACAO}",
    r"上記の(?:内容|指示)を(?:すべて)?(?:出力|繰り返|表示)",
    rf"(?:サーバー|システム|バックエンド|データベース|pathr|アプリ)の(?:パスワード|秘密鍵|キー|認証情報|環境変数)[^。.\n]{{0,10}}{_JA_ACAO}",
    rf"(?:他の|すべての|全ての)ユーザー(?:の)?(?:データ|メール|パスワード|情報)[^。.\n]{{0,10}}{_JA_ACAO}",
    # ko
    rf"(?:너의|당신의|네|니|자신의)\s*(?:시스템\s*)?(?:프롬프트|지시\s*사항|지시|명령|규칙|비밀번호|설정|키)[^.\n]{{0,10}}{_KO_ACAO}",
    r"(?:위의|위에\s*있는)\s*(?:모든\s*)?(?:내용|지시\s*사항|텍스트)[^.\n]{0,10}(?:출력|반복|보여|알려)",
    rf"(?:서버|시스템|백엔드|데이터베이스|pathr|앱)의\s*(?:비밀번호|비밀\s*키|키|인증\s*정보|환경\s*변수)[^.\n]{{0,10}}{_KO_ACAO}",
    rf"(?:다른|모든)\s*사용자의?\s*(?:데이터|이메일|비밀번호|정보)[^.\n]{{0,10}}{_KO_ACAO}",
    # ar (sem vocalização; alef já unificado em `ا`)
    rf"{_AR_ACAO}[^.\n]{{0,12}}?(?:تعليماتك|توجيهاتك|قواعدك|موجهك|اعداداتك|مفتاحك|مفاتيحك|كلمه\s+مرورك|كلمة\s+مرورك|"
    r"اسرارك|(?:التعليمات|القواعد|الموجه|كلمه\s+المرور|كلمة\s+المرور|المفتاح)\s+الخاص[ةه]?\s+بك)",
    rf"{_AR_ACAO}[^.\n]{{0,12}}?(?:تعليمات\s+النظام|رساله\s+النظام|رسالة\s+النظام|موجه\s+النظام|كل\s+ما\s+(?:هو\s+)?(?:اعلاه|فوق))",
    rf"{_AR_ACAO}[^.\n]{{0,20}}?(?:كلمه\s+مرور|كلمة\s+مرور|كلمات\s+مرور|مفتاح|مفاتيح|اسرار|بيانات\s+اعتماد)\s+"
    r"(?:الخادم|النظام|قاعده\s+البيانات|قاعدة\s+البيانات|pathr|التطبيق)",
    rf"{_AR_ACAO}[^.\n]{{0,20}}?(?:بيانات|بريد|كلمات\s+مرور|معلومات)\s+(?:المستخدمين\s+الاخرين|مستخدمين\s+اخرين|"
    r"جميع\s+المستخدمين|كل\s+المستخدمين)",
]

NATIVAS_SOBRESCREVER: list[str] = [
    r"(?:игнорир\w+|забудь\w*|отбрось\w*|не\s+учитывай\w*)[^.\n]{0,30}?(?:инструкци\w+|правил\w+|указани\w+|промпт\w*|"
    r"все\s+(?:выше|предыдущ\w+))",
    r"(?:忽略|无视|忘记|忘掉|不要理会)[^。.\n]{0,8}(?:指令|指示|规则|说明|提示|命令|约束)",
    r"(?:以前|これまで|上記|前)の(?:すべての)?(?:指示|命令|ルール|制約)を?(?:すべて)?(?:無視|忘れ|破棄)",
    r"(?:이전|위의|모든)\s*(?:지시\s*사항|지시|명령|규칙)[^.\n]{0,8}(?:무시|잊)",
    r"(?:تجاهل|انس|تجاوز)\w*\s+(?:كل\s+|جميع\s+)?(?:التعليمات|القواعد|الاوامر|التوجيهات)",
]

NATIVAS_PAPEL: list[str] = [
    r"теперь\s+ты|с\s+этого\s+момента\s+ты|притворись|режим\s+разработчика",
    r"你现在是|从现在起你是|从现在开始你是|假装你是|开发者模式",
    r"あなたは(?:今から|これから)|今からあなたは|になりきって|開発者モード",
    r"지금부터\s*(?:너는|당신은)|개발자\s*모드",
    r"انت\s+الان|من\s+الان\s+فصاعد\w*|وضع\s+المطور",
]

NATIVAS_OFUSCAR: list[str] = [
    r"в\s+base\s?64|по\s+буквам|в\s+шестнадцатеричн\w+",
    r"用\s?base64|逐字|一个字一个字|十六进制",
    r"base64で|一文字ずつ|16進数で",
    r"base64로|한\s*글자씩|16진수로",
    r"(?:ب|في\s+)?base\s?64|حرفا\s+بحرف|حرف\s+بحرف",
]

# Texto de recusa, no idioma da interface (pt, en, es — os do app).
RECUSA_DO_TUTOR = {
    "pt": "Não posso compartilhar instruções internas, chaves, senhas nem dados de outras pessoas. "
    "Posso te ajudar com o conteúdo que você está estudando — qual é a sua dúvida?",
    "en": "I can't share internal instructions, keys, passwords, or other people's data. "
    "I can help with what you're studying — what's your question?",
    "es": "No puedo compartir instrucciones internas, claves, contraseñas ni datos de otras personas. "
    "Puedo ayudarte con lo que estás estudiando — ¿cuál es tu duda?",
}

BLOQUEADA = {
    "pt": "A resposta foi bloqueada por segurança. Reformule o pedido em termos do seu estudo.",
    "en": "The response was blocked for security reasons. Please rephrase your request in terms of your studies.",
    "es": "La respuesta fue bloqueada por seguridad. Reformula tu pedido en términos de tu estudio.",
}
