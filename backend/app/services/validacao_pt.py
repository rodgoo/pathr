"""Erros de validação do Pydantic em português, com o nome do campo que a pessoa vê.

O Pydantic escreve em inglês ("value is not a valid email address: An email
address must have an @-sign.", "String should have at least 10 characters"), e
o handler de `main.py` repassava esse texto direto para a tela de entrar. Aqui
cada TIPO de erro vira uma frase, e o nome técnico do campo vira o rótulo do
formulário. Tipo que não está no mapa cai num genérico em português — nunca no
inglês de origem.
"""

from typing import Any

ROTULOS = {
    "email": "E-mail",
    "password": "Senha",
    "new_password": "Nova senha",
    "current_password": "Senha atual",
    "name": "Nome",
    "username": "Nome de usuário",
    "birth_date": "Data de nascimento",
    "city": "Cidade",
    "state": "UF",
    "country": "País",
    "mfa_code": "Código",
    "code": "Código",
    "token": "Link",
    "mensagem": "Mensagem",
    "tipo": "Tipo",
    "weekly_hours": "Horas por semana",
    "years_experience": "Anos de experiência",
}


def _rotulo(loc: tuple[Any, ...]) -> str:
    partes = [str(p) for p in loc if p not in ("body", "query", "path", "form")]
    if not partes:
        return ""
    ultimo = partes[-1]
    return ROTULOS.get(ultimo, ultimo.replace("_", " ").capitalize())


def mensagem(erro: dict[str, Any]) -> str:
    tipo = str(erro.get("type") or "")
    ctx = erro.get("ctx") or {}
    campo = _rotulo(tuple(erro.get("loc") or ()))
    original = str(erro.get("msg") or "")

    # EmailStr falha como value_error com o texto do email-validator em inglês.
    if "email address" in original.lower():
        return f"{campo or 'E-mail'}: informe um e-mail válido, como nome@exemplo.com."

    frases = {
        "missing": "preencha este campo",
        "string_too_short": f"use ao menos {ctx.get('min_length')} caracteres",
        "string_too_long": f"use no máximo {ctx.get('max_length')} caracteres",
        "too_short": f"informe ao menos {ctx.get('min_length')} item(ns)",
        "too_long": f"informe no máximo {ctx.get('max_length')} item(ns)",
        "string_type": "precisa ser um texto",
        "int_parsing": "precisa ser um número inteiro",
        "int_type": "precisa ser um número inteiro",
        "float_parsing": "precisa ser um número",
        "float_type": "precisa ser um número",
        "bool_parsing": "precisa ser sim ou não",
        "greater_than_equal": f"precisa ser {ctx.get('ge')} ou mais",
        "greater_than": f"precisa ser maior que {ctx.get('gt')}",
        "less_than_equal": f"precisa ser {ctx.get('le')} ou menos",
        "less_than": f"precisa ser menor que {ctx.get('lt')}",
        "date_parsing": "informe uma data válida",
        "date_from_datetime_parsing": "informe uma data válida",
        "date_type": "informe uma data válida",
        "literal_error": "escolha uma das opções",
        "enum": "escolha uma das opções",
        "uuid_parsing": "identificador inválido",
        "json_invalid": "os dados enviados não estão num formato válido",
        "string_pattern_mismatch": "formato inválido",
        "url_parsing": "informe um endereço válido",
    }
    if tipo == "value_error":
        # Validadores do próprio app levantam ValueError já em português; o
        # Pydantic só prefixa "Value error, ".
        prefixo = "Value error, "
        frase = original[len(prefixo):] if original.startswith(prefixo) else "valor inválido"
        frase = frase.rstrip(".")
    else:
        frase = frases.get(tipo, "valor inválido")
    return f"{campo}: {frase}." if campo else f"{frase[:1].upper()}{frase[1:]}."
