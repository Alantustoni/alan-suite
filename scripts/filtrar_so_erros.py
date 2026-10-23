# -*- coding: utf-8 -*-
"""
filtrar_so_erros.py

Recebe:
  1) o arquivo .txt de Importacao Usinas (CNAB, segmentos G + Y);
  2) o arquivo de retorno de erros do ERP (texto com linhas
     'Numero "1466650:1"' etc.).

Gera um novo .txt contendo APENAS os titulos que deram erro (casando
pelo numero da nota), renumerando o sequencial e recalculando os
trailers. Nao altera nenhum campo dos registros — so mantem/remove
blocos inteiros (G + Y), preservando o alinhamento exato do CNAB.

USO (no cmd/PowerShell, dentro da pasta ALAN):

    python filtrar_so_erros.py "importacao_usinas_20260923_093247.txt" "Sem nome.txt"

Se rodar sem argumentos, ele tenta achar sozinho na pasta atual o .txt
de importacao e um arquivo de erros.
"""
import re
import sys
from pathlib import Path

# Posicao do numero da nota no segmento G (mesma do importacao_usinas.py)
DOC_INI, DOC_FIM = 147, 162
SEQ_INI, SEQ_FIM = 8, 13          # sequencial do registro no lote (5 digitos)


def _numeros_com_erro(caminho_erros: Path) -> set:
    """Le o retorno do ERP e devolve o conjunto de numeros de nota que deram erro."""
    txt = Path(caminho_erros).read_text(encoding="latin-1", errors="ignore")
    nums = set()
    # casa: Numero "1466650:1"  /  Numero "594036:1"  etc.
    for m in re.finditer(r'[Nn]umero\s*"?\s*(\d+)\s*[:"]', txt):
        nums.add(m.group(1).lstrip("0") or "0")
    return nums


def _num_da_linha_g(linha: str) -> str:
    return linha[DOC_INI:DOC_FIM].strip().lstrip("0") or "0"


def filtrar(caminho_txt: Path, caminho_erros: Path) -> Path:
    linhas = Path(caminho_txt).read_text(encoding="latin-1", errors="ignore").splitlines()
    alvo = _numeros_com_erro(caminho_erros)
    if not alvo:
        raise SystemExit("Nenhum numero de erro encontrado no arquivo de erros. "
                         "Confira se e o arquivo certo.")

    # separa detalhes (blocos G+Y) e trailers (registros que nao sao G/Y de detalhe)
    blocos = []           # lista de (numero, [linhas do bloco])
    trailer_lote = None
    trailer_arq = None
    i = 0
    while i < len(linhas):
        ln = linhas[i]
        tipo_reg = ln[7:8] if len(ln) >= 8 else ""
        seg = ln[13:14] if len(ln) >= 14 else ""
        if tipo_reg == "3" and seg == "G":
            bloco = [ln]
            # anexa o Y (complemento) seguinte, se houver
            if i + 1 < len(linhas) and len(linhas[i + 1]) >= 14 and linhas[i + 1][13:14] in ("Y", "H"):
                bloco.append(linhas[i + 1])
                i += 1
            blocos.append((_num_da_linha_g(ln), bloco))
        elif tipo_reg == "5":
            trailer_lote = ln
        elif tipo_reg == "9":
            trailer_arq = ln
        i += 1

    # mantem so os blocos cujo numero deu erro
    mantidos = [b for (num, b) in blocos if num in alvo]
    achados = {num for (num, b) in blocos if num in alvo}
    faltando = alvo - achados

    # achata + renumera o sequencial
    detalhe = []
    for bloco in mantidos:
        detalhe.extend(bloco)
    for pos, ln in enumerate(detalhe, start=1):
        seq = f"{pos:05d}"
        detalhe[pos - 1] = ln[:SEQ_INI] + seq + ln[SEQ_FIM:]

    n_det = len(detalhe)

    # recalcula trailers (mantendo o layout do arquivo original)
    saida = list(detalhe)
    if trailer_lote is not None:
        # [17:23] = quantidade de registros no lote (detalhes + o proprio trailer de lote)
        tl = trailer_lote[:17] + f"{n_det + 1:06d}" + trailer_lote[23:]
        saida.append(tl)
    if trailer_arq is not None:
        # [17:23] = qtd de lotes (mantem)  /  [23:29] = qtd de registros no arquivo
        ta = trailer_arq[:23] + f"{n_det + 2:06d}" + trailer_arq[29:]
        saida.append(ta)

    destino = Path(caminho_txt).with_name(Path(caminho_txt).stem + "_SO_ERROS.txt")
    destino.write_text("\r\n".join(saida) + "\r\n", encoding="latin-1")

    print(f"Numeros com erro no retorno : {len(alvo)}")
    print(f"Titulos mantidos no arquivo : {len(mantidos)}")
    print(f"Linhas de detalhe (G+Y)     : {n_det}")
    if faltando:
        print(f"AVISO: {len(faltando)} numero(s) de erro NAO foram achados no .txt: "
              f"{', '.join(sorted(faltando))}")
    print(f"Arquivo gerado              : {destino}")
    return destino


def _achar_automatico():
    aqui = Path(".")
    txts = sorted(aqui.glob("importacao_usinas*.txt"))
    txt = txts[0] if txts else None
    # arquivo de erros: qualquer .txt/sem extensao que contenha 'Numero "'
    erros = None
    for p in list(aqui.glob("*")) :
        if p == txt or not p.is_file():
            continue
        try:
            amostra = p.read_text(encoding="latin-1", errors="ignore")[:5000]
        except Exception:
            continue
        if "Numero" in amostra and "vencimento" in amostra.lower():
            erros = p
            break
    return txt, erros


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        txt, erros = Path(sys.argv[1]), Path(sys.argv[2])
    else:
        txt, erros = _achar_automatico()
        if not txt or not erros:
            raise SystemExit(
                "Uso: python filtrar_so_erros.py <arquivo_importacao.txt> <arquivo_erros.txt>")
        print(f"(auto) importacao: {txt}")
        print(f"(auto) erros     : {erros}")
    filtrar(txt, erros)
