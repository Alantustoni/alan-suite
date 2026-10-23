# -*- coding: utf-8 -*-
"""
extrair_notas.py

Pega um arquivo .txt de Importacao Usinas (CNAB, segmentos G + Y) e gera
um novo arquivo contendo APENAS as notas listadas em NOTAS, mantendo uma
unica linha por nota (tira as duplicacoes) e forcando o CNPJ para
CNPJ_FORCADO. Renumera o sequencial e recalcula os trailers.

Nao remonta nenhuma linha do zero: le os bytes originais e so troca o
campo de CNPJ e o sequencial — assim o alinhamento de 240 colunas (e os
espacos do complemento Y) fica identico ao original.

USO (dentro da pasta ALAN):
    python extrair_notas.py "importacao_usinas_20260923_110014.txt"
ou, deixando ele achar o mais novo sozinho:
    python extrair_notas.py
"""
import sys
from pathlib import Path

# ── AJUSTE AQUI ────────────────────────────────────────────────────────
NOTAS = ["123456"]     # notas que quero manter
CNPJ_FORCADO = "90100200002586"             # 14 digitos (so usado se MANTER_TODAS_FILIAIS = False)

# True  = mantem TODAS as cópias de cada nota (matriz + filiais), igual ao
#         arquivo grande que o sistema leu sem travar. Use isto quando NAO
#         tiver certeza de qual filial o titulo esta cadastrado.
# False = mantem 1 linha por nota e força o CNPJ_FORCADO acima.
MANTER_TODAS_FILIAIS = False

# True = grava no campo de vencimento a data que esta DENTRO do codigo de
#        barras (fator de vencimento), e nao a da planilha. Corrige o caso
#        do boleto prorrogado, onde a planilha mostra a data nova mas a barra
#        (e o titulo no ERP) continuam na data original — o que deixava o
#        registro inconsistente e travava o import.
CORRIGIR_VENC_PELA_BARRA = True
# ───────────────────────────────────────────────────────────────────────

from datetime import date as _date, timedelta as _timedelta
_FATOR_BASE_DATA = _date(2025, 2, 22)     # fator 1000 = 22/02/2025 (reset Febraban)
VENC_INI, VENC_FIM = 107, 115
BARRA_INI = 17

CNPJ_INI, CNPJ_FIM = 63, 77
DOC_INI, DOC_FIM   = 147, 162
SEQ_INI, SEQ_FIM   = 8, 13


def _num(linha: str) -> str:
    return linha[DOC_INI:DOC_FIM].strip().lstrip("0") or "0"


def _venc_da_barra(g):
    """Devolve o vencimento (DDMMAAAA) codificado no fator da barra do segmento G."""
    barra = g[BARRA_INI:BARRA_INI + 44]
    if len(barra) < 9 or not barra[:9].isdigit():
        return None
    fator = int(barra[5:9])
    if fator < 1000:                      # fator invalido/sem vencimento
        return None
    d = _FATOR_BASE_DATA + _timedelta(days=fator - 1000)
    return d.strftime("%d%m%Y")


def main(caminho_txt: Path) -> Path:
    linhas = Path(caminho_txt).read_text(encoding="latin-1", errors="ignore").split("\n")
    linhas = [l.rstrip("\r") for l in linhas]

    alvo = [n.lstrip("0") for n in NOTAS]
    trailer_lote = trailer_arq = None
    blocos = {}          # numero -> [lista de blocos]  (todas as ocorrencias)

    i = 0
    while i < len(linhas):
        ln = linhas[i]
        tipo = ln[7:8] if len(ln) >= 8 else ""
        seg  = ln[13:14] if len(ln) >= 14 else ""
        if tipo == "3" and seg == "G":
            bloco = [ln]
            if i + 1 < len(linhas) and len(linhas[i + 1]) >= 14 and linhas[i + 1][13:14] in ("Y", "H"):
                bloco.append(linhas[i + 1]); i += 1
            num = _num(ln)
            if num in alvo:
                blocos.setdefault(num, []).append(bloco)
        elif tipo == "5":
            trailer_lote = ln
        elif tipo == "9":
            trailer_arq = ln
        i += 1

    # monta na ordem pedida em NOTAS
    detalhe = []
    faltando = []
    for n in alvo:
        if n not in blocos:
            faltando.append(n)
            continue
        if MANTER_TODAS_FILIAIS:
            for b in blocos[n]:               # todas as copias (matriz + filiais)
                detalhe.extend(b)
        else:
            detalhe.extend(blocos[n][0])      # so a 1a ocorrencia

    # forca CNPJ (opcional), corrige vencimento pela barra (opcional) e
    # sempre renumera o sequencial
    venc_corrigidos = 0
    venc_troca = ("", "")   # (venc_antigo, venc_novo) do ultimo G, p/ aplicar no Y
    for pos, ln in enumerate(detalhe):
        seg = ln[13:14]
        if seg == "G":
            if not MANTER_TODAS_FILIAIS:
                ln = ln[:CNPJ_INI] + CNPJ_FORCADO + ln[CNPJ_FIM:]
            if CORRIGIR_VENC_PELA_BARRA:
                antigo = ln[VENC_INI:VENC_FIM]
                novo = _venc_da_barra(ln)
                if novo and novo != antigo:
                    ln = ln[:VENC_INI] + novo + ln[VENC_FIM:]
                    venc_troca = (antigo, novo)
                    venc_corrigidos += 1
                else:
                    venc_troca = ("", "")
        elif seg in ("Y", "H") and CORRIGIR_VENC_PELA_BARRA and venc_troca[0]:
            # o complemento carrega o mesmo vencimento (prefixado por "3")
            ln = ln.replace("3" + venc_troca[0], "3" + venc_troca[1], 1)
        ln = ln[:SEQ_INI] + f"{pos + 1:05d}" + ln[SEQ_FIM:]
        detalhe[pos] = ln

    n_det = len(detalhe)
    saida = list(detalhe)
    if trailer_lote is not None:
        saida.append(trailer_lote[:17] + f"{n_det + 1:06d}" + trailer_lote[23:])
    if trailer_arq is not None:
        saida.append(trailer_arq[:23] + f"{n_det + 2:06d}" + trailer_arq[29:])

    destino = Path(caminho_txt).with_name(Path(caminho_txt).stem + "_3NOTAS.txt")
    destino.write_text("\r\n".join(saida) + "\r\n", encoding="latin-1")

    print(f"Notas pedidas : {', '.join(alvo)}")
    print(f"Notas achadas : {', '.join(n for n in alvo if n in blocos)}")
    if faltando:
        print(f"NAO achadas   : {', '.join(faltando)}")
    if MANTER_TODAS_FILIAIS:
        print("Modo          : MANTER TODAS AS FILIAIS (matriz + filiais, sem forcar CNPJ)")
    else:
        print(f"Modo          : 1 linha por nota, CNPJ forcado {CNPJ_FORCADO}")
    print(f"Linhas detalhe: {n_det}")
    if CORRIGIR_VENC_PELA_BARRA:
        print(f"Venc. corrigido pela barra: {venc_corrigidos} titulo(s)")
    print(f"Arquivo gerado: {destino}")
    return destino


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        txt = Path(sys.argv[1])
    else:
        cand = sorted(Path(".").glob("importacao_usinas*.txt"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        if not cand:
            raise SystemExit("Nao achei nenhum importacao_usinas*.txt na pasta. "
                             "Passe o nome: python extrair_notas.py <arquivo.txt>")
        txt = cand[0]
        print(f"(auto) arquivo: {txt}")
    main(txt)
