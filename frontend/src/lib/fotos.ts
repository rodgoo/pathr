/**
 * As fotos de perfil já baixadas, guardadas enquanto o app está aberto.
 *
 * Cada tela pedia a foto de novo: o cartão de cada amigo, o perfil, o card de
 * conquista, o pop-up de convite. No servidor cada pedido baixa do
 * armazenamento e decifra, e era isso que fazia a foto demorar a aparecer.
 * Aqui a primeira busca serve para todas as telas seguintes.
 *
 * A chave é "eu" (a própria foto) ou o @ de outra pessoa. Trocar ou remover a
 * própria foto chama `esquecerFoto("eu")`. O logout limpa tudo (useAuth).
 */

const guardadas = new Map<string, Promise<string | null>>();

export function fotoDe(chave: string, buscar: () => Promise<Blob>): Promise<string | null> {
  let pedido = guardadas.get(chave);
  if (!pedido) {
    pedido = buscar()
      .then((blob) => URL.createObjectURL(blob))
      .catch(() => {
        // Falhou: não guarda a falha, para a próxima tela tentar de novo.
        guardadas.delete(chave);
        return null;
      });
    guardadas.set(chave, pedido);
  }
  return pedido;
}

export function esquecerFoto(chave: string): void {
  const pedido = guardadas.get(chave);
  guardadas.delete(chave);
  void pedido?.then((url) => {
    if (url) URL.revokeObjectURL(url);
  });
}

export function esquecerTodasAsFotos(): void {
  for (const chave of [...guardadas.keys()]) esquecerFoto(chave);
}
