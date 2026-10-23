"""
filtrar_importacao.py — Filtra um arquivo de Importação Usinas (CNAB).

Recebe um .txt já gerado (segmentos G + complemento) e devolve um novo
arquivo contendo APENAS as notas escolhidas, com UMA linha por nota (tira as
duplicações), forçando o CNPJ da filial informada.

Faz o MESMO tratamento do Juntador RET:
  • converte Itaú (341) → Bradesco (237), inclusive o complemento H → Y;
  • renumera o sequencial dos registros;
  • recalcula os trailers de lote e de arquivo.

Além disso corrige o vencimento do campo pela data que está DENTRO do código
de barras (fator de vencimento). Isso resolve o caso do boleto prorrogado,
em que a planilha mostra a data nova mas a barra (e o título no ERP) seguem
na data original — deixando o registro inconsistente.

Não remonta linha do zero: só troca CNPJ, vencimento e sequencial em cópias
das linhas originais, preservando o alinhamento de 240 colunas.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import ret as _ret

# Posições fixas no segmento G (mesmo leiaute da Importação Usinas)
_CNPJ_INI, _CNPJ_FIM = 63, 77       # 14 dígitos do CNPJ do favorecido
_DOC_INI,  _DOC_FIM  = 147, 162     # número da nota
_VENC_INI, _VENC_FIM = 107, 115     # vencimento DDMMAAAA
_BARRA_INI           = 17           # início do código de barras (44 díg)

# Fator de vencimento: fator 1000 = 22/02/2025 (reset Febraban de 2025)
_FATOR_BASE = date(2025, 2, 22)

# ── Cabeçalhos padrão (header de arquivo tipo 0 + header de lote tipo 1) ──
# Um CNAB240 completo começa com esses dois registros. O leiaute reduzido da
# Importação Usinas não os gera, e sem eles o ERP lê mas não vincula. Estes
# são SINTÉTICOS, no mesmo leiaute de um arquivo Bradesco aceito pelo ERP. Podem
# ser substituídos em tempo de execução apontando um arquivo modelo.
DEFAULT_HEADER_ARQUIVO = (
    "23700000         290100100000182900001              0123400000000987654 "
    "ALFAMETAL SA INDUSTRIA E COMERBANCO BRADESCO S.A.                     "
    "2170620260614100000010000000000000000BRAD").ljust(240)

DEFAULT_HEADER_LOTE = (
    "23700011I03  022 290100100000182900001              0123400000000987654 "
    "ALFAMETAL SA INDUSTRIA E COMER").ljust(240)


def _extrair_cabecalho(modelo_path: Path):
    """Extrai (header de arquivo tipo 0, header de lote tipo 1) de um arquivo modelo."""
    linhas = Path(modelo_path).read_text(encoding="latin-1",
                                         errors="ignore").splitlines()
    h0 = h1 = None
    for l in linhas:
        if len(l) < 8:
            continue
        if h0 is None and l[7:8] == "0":
            h0 = l
        elif h1 is None and l[7:8] == "1":
            h1 = l
        if h0 is not None and h1 is not None:
            break
    return h0, h1


@dataclass
class ResultadoFiltro:
    linhas_finais:  List[str] = field(default_factory=list)
    log:            List[str] = field(default_factory=list)
    avisos:         List[str] = field(default_factory=list)
    notas_pedidas:  List[str] = field(default_factory=list)
    notas_achadas:  List[str] = field(default_factory=list)
    notas_faltando: List[str] = field(default_factory=list)
    total_registros: int = 0
    venc_corrigidos: int = 0
    cnpj: str = ""
    cabecalho: bool = False

    @property
    def ok(self) -> bool:
        return self.total_registros > 0


def _num(linha: str) -> str:
    return linha[_DOC_INI:_DOC_FIM].strip().lstrip("0") or "0"


def _venc_da_barra(g: str) -> Optional[str]:
    """Vencimento (DDMMAAAA) codificado no fator da barra do segmento G."""
    barra = g[_BARRA_INI:_BARRA_INI + 44]
    if len(barra) < 9 or not barra[:9].isdigit():
        return None
    fator = int(barra[5:9])
    if fator < 1000:                      # sem vencimento / à vista
        return None
    return (_FATOR_BASE + timedelta(days=fator - 1000)).strftime("%d%m%Y")


def _so_digitos(s: Any) -> str:
    return re.sub(r"\D", "", str(s or ""))


def processar(
    caminho_txt: Path,
    notas: List[str],
    cnpj: str,
    cfg_ret: Optional[Dict[str, Any]] = None,
    corrigir_venc: bool = True,
    incluir_cabecalho: bool = True,
    modelo_cabecalho: Optional[Path] = None,
) -> ResultadoFiltro:
    r = ResultadoFiltro()
    cfg_ret = cfg_ret or {}
    cnpj = _so_digitos(cnpj)[:14]
    r.cnpj = cnpj

    alvo = [(_so_digitos(n).lstrip("0") or "0") for n in notas if _so_digitos(n)]
    r.notas_pedidas = alvo
    if not alvo:
        r.avisos.append("Nenhuma nota informada.")
        return r
    if len(cnpj) != 14:
        r.avisos.append("CNPJ inválido (precisa de 14 dígitos) — não vou forçar CNPJ.")

    linhas = Path(caminho_txt).read_text(encoding="latin-1", errors="ignore").split("\n")
    linhas = [l.rstrip("\r") for l in linhas]
    # mesmo tratamento do RET: Itaú → Bradesco (inclui H → Y)
    linhas = [_ret.converter_itau_para_bradesco(l) for l in linhas]

    # coleta o 1º bloco (G + complemento) de cada nota pedida
    blocos: Dict[str, List[str]] = {}
    i = 0
    while i < len(linhas):
        ln = linhas[i]
        if len(ln) >= 14 and ln[7:8] == "3" and ln[13:14] == "G":
            bloco = [ln]
            if (i + 1 < len(linhas) and len(linhas[i + 1]) >= 14
                    and linhas[i + 1][13:14] in ("Y", "H")):
                bloco.append(linhas[i + 1])
                i += 1
            num = _num(ln)
            if num in alvo and num not in blocos:
                blocos[num] = bloco
        i += 1

    # monta na ordem pedida
    detalhe: List[str] = []
    for n in alvo:
        if n in blocos:
            detalhe.extend(blocos[n])
            r.notas_achadas.append(n)
        else:
            r.notas_faltando.append(n)
    if r.notas_faltando:
        r.avisos.append("Nota(s) não encontrada(s) no arquivo: "
                        + ", ".join(r.notas_faltando))
    if not detalhe:
        r.avisos.append("Nenhuma das notas foi encontrada — arquivo NÃO gerado.")
        return r

    # força CNPJ no G e corrige o vencimento pela barra (G e complemento)
    venc_troca = ("", "")
    for pos, ln in enumerate(detalhe):
        seg = ln[13:14]
        if seg == "G":
            if len(cnpj) == 14:
                ln = ln[:_CNPJ_INI] + cnpj + ln[_CNPJ_FIM:]
            if corrigir_venc:
                antigo = ln[_VENC_INI:_VENC_FIM]
                novo = _venc_da_barra(ln)
                if novo and novo != antigo:
                    ln = ln[:_VENC_INI] + novo + ln[_VENC_FIM:]
                    venc_troca = (antigo, novo)
                    r.venc_corrigidos += 1
                else:
                    venc_troca = ("", "")
        elif seg in ("Y", "H") and corrigir_venc and venc_troca[0]:
            ln = ln.replace("3" + venc_troca[0], "3" + venc_troca[1], 1)
        detalhe[pos] = ln

    # renumera o sequencial dos detalhes (igual RET)
    registros = _ret._renumerar_sequencial(detalhe)
    r.total_registros = len(registros)
    n = len(registros)

    if incluir_cabecalho:
        # CNAB240 completo: header de arquivo (0) + header de lote (1) +
        # detalhes + trailer de lote (5) + trailer de arquivo (9).
        h0 = h1 = None
        if modelo_cabecalho:
            try:
                h0, h1 = _extrair_cabecalho(Path(modelo_cabecalho))
            except OSError:
                h0 = h1 = None
        if not h0 or not h1:
            if modelo_cabecalho:
                r.avisos.append(
                    "Não encontrei os cabeçalhos no arquivo modelo — usei o padrão embutido.")
            h0, h1 = DEFAULT_HEADER_ARQUIVO, DEFAULT_HEADER_LOTE
        # trailer de lote (…5, lote 0001): header de lote + detalhes + trailer
        t_lote = "23700015" + " " * 9 + f"{n + 2:06d}" + "0" * 42
        # trailer de arquivo (…9): 1 lote; total = header arq + lote + trailer arq
        t_arq = "23799999" + " " * 9 + "000001" + f"{n + 4:06d}"
        r.linhas_finais = [h0, h1] + registros + [t_lote, t_arq]
        r.cabecalho = True
    else:
        # leiaute reduzido (sem cabeçalho) — mantém compatibilidade
        t_lote_modelo = cfg_ret.get(
            "trailer_lote_legado",
            "23700025         000032000000000000000000000000000000000000000000")
        t_arq_modelo = cfg_ret.get(
            "trailer_arquivo_legado", "23799999         000002000108")
        t_lote, t_arq = _ret._trailers_recalculados(
            registros, t_lote_modelo, t_arq_modelo)
        r.linhas_finais = registros + [t_lote, t_arq]

    # IMPORTANTE: um CNAB de largura fixa TRAVA o ERP se as linhas tiverem
    # tamanhos diferentes (o leitor desalinha e entra em loop). Igualamos a
    # largura de TODAS as linhas (cabeçalho, detalhe e trailer) pela maior.
    if r.linhas_finais:
        larg = max(len(l) for l in r.linhas_finais)
        r.linhas_finais = [l.ljust(larg) for l in r.linhas_finais]
        r.log.append(f"Largura das linhas normalizada em {larg} colunas.")

    r.log.append(
        f"{len(r.notas_achadas)} nota(s) mantida(s) → {r.total_registros} linha(s) de detalhe.")
    if r.cabecalho:
        r.log.append("Cabeçalho CNAB incluído (header de arquivo + header de lote).")
    if len(cnpj) == 14:
        r.log.append(f"CNPJ forçado: {cnpj}")
    if corrigir_venc:
        r.log.append(f"Vencimento corrigido pela barra em {r.venc_corrigidos} título(s).")
    return r


# gravação reaproveita o RET (latin-1/CRLF, com divisão opcional)
gravar = _ret.gravar
gravar_dividido = _ret.gravar_dividido
