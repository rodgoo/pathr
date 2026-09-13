/**
 * O card de conquista da sequência em dupla, pronto para compartilhar.
 *
 * Desenhado num canvas, e não montado em HTML e "fotografado": um PNG saído do
 * canvas é igual em todo aparelho, não depende de biblioteca de captura, e é
 * o formato que o compartilhamento do celular (WhatsApp, Instagram) aceita.
 *
 * 1080×1350 (4:5): o tamanho que o feed do Instagram mostra inteiro, e que no
 * WhatsApp abre sem corte.
 *
 * As fotos saem pelas rotas autenticadas do app (a tag `img` não mandaria o
 * cookie para a API) e viram blob local — o canvas não fica "sujo" por imagem
 * de outra origem, e o PNG pode ser exportado.
 */

import { useEffect, useRef, useState } from "react";
import { profile as profileApi, social, tags as tagsApi } from "@/api/endpoints";
import type { PessoaCartao } from "@/api/types";
import { useAuth } from "@/hooks/useAuth";
import { fraseAleatoria } from "@/lib/conquista";
import { ACC, ACC3, ACC4, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { IconButton } from "@/components/ui/IconButton";

const LARGURA = 1080;
const ALTURA = 1350;
const URL_DO_APP = "pathr.notter.com.br";
const FONTE = "Inter, 'Segoe UI', system-ui, -apple-system, sans-serif";

// O mesmo traçado do componente Logo (ver components/ui/Logo.tsx), na grade de 440.
const LOGO = [
  "M144 89.2451L126.654 93.1647C109.013 97.1509 96.2412 112.478 95.5031 130.549L93.6673 175.498C93.1115 189.108 85.6684 201.499 73.9148 208.382L58.873 217.191C55.1505 219.371 54.8762 224.65 58.3526 227.204L77.2881 241.116C87.0774 248.308 93.0679 259.559 93.5705 271.696L95.4885 318.014C96.2355 336.054 109.008 351.928 127.055 352.464C132.987 352.64 138.933 352.361 144 351.245C146.616 350.669 149.372 349.713 152.159 348.512C173.647 339.247 183 315.025 183 291.624V260.5M183 260.5C183 260.5 183 230 183 205.002C183 175.5 208.254 154.774 236.5 154.5C261.967 154.253 286 173.778 286 199.246C286 224.399 261.652 242.301 236.5 242.5C214.056 242.678 183 260.5 183 260.5Z",
  "M314 351L323.88 348.232C340.681 343.524 352.492 328.47 353.066 311.032L354.666 262.462C355.072 250.124 361.152 238.666 371.141 231.412L383.039 222.772C386.115 220.538 386.365 216.042 383.554 213.482L367.786 199.117C359.809 191.849 355.107 181.667 354.747 170.883L353.305 127.716C352.621 107.233 336.567 90.5807 316.123 89.1487L314 89",
];

export interface PessoaDoCard {
  nome: string;
  username: string;
  stack: string[];
  foto: HTMLImageElement | null;
}

export interface DadosDoCard {
  dias: number;
  frase: string;
  eu: PessoaDoCard;
  amigo: PessoaDoCard;
}

function quebrar(ctx: CanvasRenderingContext2D, texto: string, largura: number): string[] {
  const linhas: string[] = [];
  let atual = "";
  for (const palavra of texto.split(" ")) {
    const tentativa = atual ? `${atual} ${palavra}` : palavra;
    if (ctx.measureText(tentativa).width > largura && atual) {
      linhas.push(atual);
      atual = palavra;
    } else {
      atual = tentativa;
    }
  }
  if (atual) linhas.push(atual);
  return linhas;
}

function iniciais(nome: string): string {
  return nome
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((parte) => parte[0]?.toUpperCase() ?? "")
    .join("");
}

function desenharPessoa(ctx: CanvasRenderingContext2D, pessoa: PessoaDoCard, cx: number, cy: number) {
  const raio = 118;
  // Anel da cor do app em volta da foto.
  ctx.beginPath();
  ctx.arc(cx, cy, raio + 10, 0, Math.PI * 2);
  const anel = ctx.createLinearGradient(cx - raio, cy - raio, cx + raio, cy + raio);
  anel.addColorStop(0, ACC4);
  anel.addColorStop(1, ACC);
  ctx.fillStyle = anel;
  ctx.fill();

  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, raio, 0, Math.PI * 2);
  ctx.clip();
  if (pessoa.foto) {
    const { naturalWidth: w, naturalHeight: h } = pessoa.foto;
    const lado = Math.min(w, h) || 1;
    ctx.drawImage(pessoa.foto, (w - lado) / 2, (h - lado) / 2, lado, lado, cx - raio, cy - raio, raio * 2, raio * 2);
  } else {
    ctx.fillStyle = "#1d1a2e";
    ctx.fillRect(cx - raio, cy - raio, raio * 2, raio * 2);
    ctx.fillStyle = ACC3;
    ctx.font = `600 84px ${FONTE}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(iniciais(pessoa.nome), cx, cy + 4);
  }
  ctx.restore();

  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";
  ctx.fillStyle = "#ffffff";
  ctx.font = `600 42px ${FONTE}`;
  const primeiro = pessoa.nome.split(/\s+/)[0] ?? pessoa.nome;
  ctx.fillText(primeiro, cx, cy + raio + 70);
  ctx.fillStyle = ACC3;
  ctx.font = `400 30px ${FONTE}`;
  ctx.fillText(`@${pessoa.username}`, cx, cy + raio + 112);

  // A stack: até três tecnologias, uma por linha, em pílula.
  ctx.font = `500 26px ${FONTE}`;
  pessoa.stack.slice(0, 3).forEach((tecnologia, posicao) => {
    const y = cy + raio + 160 + posicao * 50;
    const largura = ctx.measureText(tecnologia).width + 40;
    ctx.fillStyle = "rgba(145,132,217,0.18)";
    ctx.strokeStyle = "rgba(181,171,252,0.45)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(cx - largura / 2, y - 30, largura, 42, 21);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#ece9ff";
    ctx.fillText(tecnologia, cx, y);
  });
}

/** Desenha o card inteiro. */
export function desenharCard(ctx: CanvasRenderingContext2D, dados: DadosDoCard) {
  // Fundo: o preto do app com o brilho violeta da marca.
  const fundo = ctx.createLinearGradient(0, 0, LARGURA, ALTURA);
  fundo.addColorStop(0, "#050507");
  fundo.addColorStop(0.55, "#110e1d");
  fundo.addColorStop(1, "#1c1633");
  ctx.fillStyle = fundo;
  ctx.fillRect(0, 0, LARGURA, ALTURA);
  for (const [x, y, r, alfa] of [
    [880, 180, 520, 0.28],
    [140, 1180, 560, 0.2],
  ] as const) {
    const brilho = ctx.createRadialGradient(x, y, 0, x, y, r);
    brilho.addColorStop(0, `rgba(145,132,217,${alfa})`);
    brilho.addColorStop(1, "rgba(145,132,217,0)");
    ctx.fillStyle = brilho;
    ctx.fillRect(0, 0, LARGURA, ALTURA);
  }

  // Marca: o símbolo e o nome.
  ctx.save();
  ctx.translate(72, 64);
  ctx.scale(96 / 440, 96 / 440);
  ctx.fillStyle = "#000";
  ctx.beginPath();
  ctx.roundRect(0, 0, 440, 440, 80);
  ctx.fill();
  ctx.strokeStyle = "#fff";
  ctx.lineWidth = 24;
  ctx.lineCap = "round";
  for (const caminho of LOGO) ctx.stroke(new Path2D(caminho));
  ctx.restore();
  ctx.fillStyle = "#ffffff";
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.font = `700 46px ${FONTE}`;
  ctx.fillText("PathR", 186, 113);

  // O número.
  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";
  const numero = ctx.createLinearGradient(0, 250, 0, 480);
  numero.addColorStop(0, "#ffffff");
  numero.addColorStop(1, ACC4);
  ctx.fillStyle = numero;
  ctx.font = `800 250px ${FONTE}`;
  ctx.fillText(String(dados.dias), LARGURA / 2, 450);
  ctx.fillStyle = "#ffffff";
  ctx.font = `700 60px ${FONTE}`;
  ctx.fillText(dados.dias === 1 ? "dia de sequência" : "dias de sequência", LARGURA / 2, 540);
  ctx.fillStyle = TEXT.muted;
  ctx.font = `400 38px ${FONTE}`;
  ctx.fillText("de amizade e estudos juntos", LARGURA / 2, 596);

  desenharPessoa(ctx, dados.eu, 330, 800);
  desenharPessoa(ctx, dados.amigo, 750, 800);

  // O "e" entre os dois.
  ctx.fillStyle = ACC4;
  ctx.font = `700 54px ${FONTE}`;
  ctx.fillText("+", LARGURA / 2, 818);

  // A frase.
  ctx.fillStyle = "#ece9ff";
  ctx.font = `italic 500 40px ${FONTE}`;
  const linhas = quebrar(ctx, `“${dados.frase}”`, 860);
  linhas.forEach((linha, posicao) => ctx.fillText(linha, LARGURA / 2, 1168 + posicao * 52));

  // A URL.
  ctx.fillStyle = ACC4;
  ctx.font = `600 32px ${FONTE}`;
  ctx.fillText(URL_DO_APP, LARGURA / 2, ALTURA - 56);
}

function carregarImagem(blob: Blob): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const imagem = new Image();
    imagem.onload = () => resolve(imagem);
    imagem.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("foto"));
    };
    imagem.src = url;
  });
}

async function fotoOuNada(buscar: () => Promise<Blob>): Promise<HTMLImageElement | null> {
  try {
    return await carregarImagem(await buscar());
  } catch {
    return null; // sem foto, o card mostra as iniciais
  }
}

export function CardDeConquista({
  amigo,
  dias,
  onFechar,
}: {
  amigo: PessoaCartao;
  dias: number;
  onFechar: () => void;
}) {
  const { user } = useAuth();
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const [imagem, setImagem] = useState<string | null>(null);
  const [png, setPng] = useState<Blob | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [frase, setFrase] = useState(() => fraseAleatoria());

  useEffect(() => {
    let vivo = true;
    (async () => {
      const [minhaFoto, fotoDele, minhas] = await Promise.all([
        user?.has_avatar ? fotoOuNada(() => profileApi.avatar()) : Promise.resolve(null),
        amigo.has_avatar ? fotoOuNada(() => social.avatar(amigo.username)) : Promise.resolve(null),
        tagsApi.mine().catch(() => []),
      ]);
      const alvo = canvas.current;
      const ctx = alvo?.getContext("2d");
      if (!vivo || !alvo || !ctx) {
        if (vivo && !ctx) setAviso("Este navegador não consegue desenhar a imagem.");
        return;
      }
      desenharCard(ctx, {
        dias,
        frase,
        eu: {
          nome: user?.name ?? "Você",
          username: user?.username ?? "",
          stack: [...minhas]
            .filter((tag) => tag.category !== "idioma")
            .sort((a, b) => b.proficiency - a.proficiency)
            .map((tag) => tag.name),
          foto: minhaFoto,
        },
        amigo: { nome: amigo.name, username: amigo.username, stack: amigo.stack, foto: fotoDele },
      });
      alvo.toBlob((blob) => {
        if (!vivo || !blob) return;
        setPng(blob);
        setImagem(URL.createObjectURL(blob));
      }, "image/png");
    })();
    return () => {
      vivo = false;
    };
  }, [amigo, dias, frase, user]);

  useEffect(() => () => {
    if (imagem) URL.revokeObjectURL(imagem);
  }, [imagem]);

  useEffect(() => {
    function tecla(evento: KeyboardEvent) {
      if (evento.key === "Escape") onFechar();
    }
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [onFechar]);

  const nomeDoArquivo = `pathr-${dias}-dias-com-${amigo.username}.png`;
  const texto = `${dias} dias de sequência de estudos com @${amigo.username} no PathR! ${URL_DO_APP}`;

  async function compartilhar() {
    if (!png) return;
    const arquivo = new File([png], nomeDoArquivo, { type: "image/png" });
    if (navigator.canShare?.({ files: [arquivo] })) {
      try {
        await navigator.share({ files: [arquivo], title: "PathR", text: texto });
        return;
      } catch (erro) {
        if ((erro as DOMException)?.name === "AbortError") return; // desistiu
      }
    }
    baixar();
    setAviso("Seu navegador não compartilha imagens direto: a imagem foi baixada para você enviar.");
  }

  function baixar() {
    if (!imagem) return;
    const link = document.createElement("a");
    link.href = imagem;
    link.download = nomeDoArquivo;
    link.click();
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Conquista: ${dias} dias de sequência com ${amigo.name}`}
      onClick={(evento) => {
        if (evento.target === evento.currentTarget) onFechar();
      }}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 60,
        background: "rgba(0,0,0,.78)",
        display: "grid",
        placeItems: "center",
        padding: 16,
      }}
    >
      <div
        style={{
          width: "min(100%, 440px)",
          maxHeight: "100%",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: 11.2,
          padding: 14,
          borderRadius: 14,
          background: "#0c0c10",
          boxShadow: "inset 0 0 0 1px rgba(233,233,237,.12)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Icon name="fogo" size={18} style={{ color: "#e2794a" }} />
          <span style={{ fontSize: 14.5, color: TEXT.strong }}>
            {dias} dias com {amigo.name.split(/\s+/)[0]}
          </span>
          <IconButton icon="x" label="Fechar" onClick={onFechar} style={{ marginLeft: "auto" }} />
        </div>

        <canvas ref={canvas} width={LARGURA} height={ALTURA} hidden />
        {imagem ? (
          <img
            src={imagem}
            alt={`Card: ${dias} dias de sequência de estudos com ${amigo.name}`}
            style={{ width: "100%", borderRadius: 10, display: "block" }}
          />
        ) : (
          <div
            style={{
              aspectRatio: "4 / 5",
              borderRadius: 10,
              background: "linear-gradient(135deg,#050507,#1c1633)",
              display: "grid",
              placeItems: "center",
              color: TEXT.faint,
              fontSize: 13,
            }}
          >
            Montando o card…
          </div>
        )}

        {aviso ? <p style={{ margin: 0, fontSize: 12.5, color: TEXT.muted }}>{aviso}</p> : null}

        <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4 }}>
          <button type="button" className="btn btn-primary" disabled={!png} onClick={() => void compartilhar()}>
            <Icon name="send" size={15} />
            Compartilhar
          </button>
          <button type="button" className="btn btn-secondary" disabled={!imagem} onClick={baixar}>
            <Icon name="download" size={15} />
            Baixar imagem
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              setImagem(null);
              setPng(null);
              setFrase((atual) => {
                let nova = fraseAleatoria();
                for (let tentativa = 0; nova === atual && tentativa < 5; tentativa += 1) nova = fraseAleatoria();
                return nova;
              });
            }}
          >
            <Icon name="refresh" size={15} />
            Outra frase
          </button>
        </div>
      </div>
    </div>
  );
}
