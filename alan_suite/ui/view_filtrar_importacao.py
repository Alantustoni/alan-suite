"""
view_filtrar_importacao.py — Tela "Filtrar Importação".

Recebe um arquivo .txt de importação (o que a Importação Usinas gera) e
devolve outro contendo APENAS as notas escolhidas, uma linha por nota,
forçando o CNPJ da filial. Faz o mesmo tratamento do Juntador RET
(converte Itaú→Bradesco, renumera, recalcula os trailers) e corrige o
vencimento pela barra.
"""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ..core import historico, theme as T
from ..core.utils import (abrir_no_sistema, mensagem_erro_amigavel,
                          timestamp_arquivo)
from .widgets import (Badge, Card, EmptyState, MetricCard, StepBar,
                      ThreadRunner, botao, cabecalho)

CNPJ_PADRAO = "90100200002586"


class FiltrarImportacaoView(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.runner = ThreadRunner(self)
        self.txt_path: Path | None = None
        self.modelo_path: Path | None = None
        self.resultado = None
        self.saida_gerada: Path | None = None

        cabecalho(
            self, "Filtrar Importação",
            "Recebe um arquivo de importação e deixa só as notas escolhidas, "
            "uma linha por nota, no CNPJ da filial — mesmo tratamento do RET.",
            crumb="Filtra notas + força CNPJ", icone="🔎").pack(fill="x", pady=(0, 10))

        self.steps = StepBar(self, ["Selecionar arquivo",
                                    "Notas + CNPJ", "Gerar arquivo"])
        self.steps.pack(fill="x", pady=(0, T.PAD))

        acoes = Card(self)
        acoes.pack(fill="x", pady=(0, T.PAD))
        box = ctk.CTkFrame(acoes, fg_color="transparent")
        box.pack(fill="x", padx=T.PAD, pady=T.PAD)
        self.b_txt = botao(box, "📄  Selecionar arquivo (.txt)", self._selecionar)
        self.b_txt.pack(side="left")
        self.b_modelo = botao(box, "🧩  Modelo cabeçalho (opcional)",
                              self._selecionar_modelo, primario=False)
        self.b_modelo.pack(side="left", padx=8)
        self.b_abrir = botao(box, "📂  Abrir", self._abrir_saida,
                             primario=False, width=104)
        self.b_pasta = botao(box, "📁  Pasta", self._abrir_pasta,
                             primario=False, width=104)
        self.badge = Badge(box, "aguardando arquivo", "info")
        self.badge.pack(side="right")

        info = ctk.CTkFrame(acoes, fg_color="transparent")
        info.pack(fill="x", padx=T.PAD, pady=(0, T.PAD))
        self.lbl_txt = ctk.CTkLabel(info, text="Arquivo: nenhum selecionado",
                                    font=T.F_PEQUENA, text_color=T.INK_3, anchor="w")
        self.lbl_txt.pack(fill="x")
        self.lbl_modelo = ctk.CTkLabel(
            info, text="Modelo cabeçalho: (opcional) — uso o padrão embutido",
            font=T.F_PEQUENA, text_color=T.INK_3, anchor="w")
        self.lbl_modelo.pack(fill="x")

        # linha de parâmetros: notas + CNPJ
        op = ctk.CTkFrame(acoes, fg_color="transparent")
        op.pack(fill="x", padx=T.PAD, pady=(0, T.PAD))
        ctk.CTkLabel(op, text="Notas (separadas por vírgula):", font=T.F_NORMAL,
                     text_color=T.INK).pack(side="left")
        self.e_notas = ctk.CTkEntry(op, width=280, font=T.F_NORMAL,
                                    border_color=T.BORDA, fg_color=T.CARD,
                                    placeholder_text="ex.: 123456, 123457, 7654321")
        self.e_notas.pack(side="left", padx=8)
        ctk.CTkLabel(op, text="CNPJ da filial:", font=T.F_NORMAL,
                     text_color=T.INK).pack(side="left", padx=(12, 0))
        self.e_cnpj = ctk.CTkEntry(op, width=150, font=T.F_NORMAL,
                                   border_color=T.BORDA, fg_color=T.CARD)
        self.e_cnpj.pack(side="left", padx=8)
        self.e_cnpj.insert(0, CNPJ_PADRAO)

        op2 = ctk.CTkFrame(acoes, fg_color="transparent")
        op2.pack(fill="x", padx=T.PAD, pady=(0, T.PAD))
        self.sw_cab = ctk.CTkSwitch(
            op2, text="Incluir cabeçalho CNAB (header de arquivo + de lote)",
            font=T.F_NORMAL, progress_color=T.AZUL)
        self.sw_cab.pack(side="left")
        self.sw_cab.select()                     # ligado por padrão
        self.b_gerar = self.b_cta = botao(op2, "⚙  Gerar", self._processar,
                                          primario=True)
        self.b_gerar.pack(side="left", padx=16)
        self.b_salvar = botao(op2, "💾  Salvar arquivo", self._gravar, primario=True)

        self.vazio = EmptyState(
            self, "🔎", "Selecione o arquivo de importação",
            "Anexe o .txt que a Importação Usinas gerou, digite as notas que "
            "quer manter e o CNPJ da filial. Eu deixo só essas notas, uma linha "
            "cada, no CNPJ informado, e recalculo os trailers.")
        self.vazio.pack(fill="both", expand=True)

        self.area = ctk.CTkFrame(self, fg_color="transparent")
        cards = ctk.CTkFrame(self.area, fg_color="transparent")
        for i in range(3):
            cards.grid_columnconfigure(i, weight=1, uniform="m")
        self.c_ped = MetricCard(cards, "Notas pedidas")
        self.c_ach = MetricCard(cards, "Encontradas", T.VERDE)
        self.c_reg = MetricCard(cards, "Linhas no arquivo")
        for i, c in enumerate((self.c_ped, self.c_ach, self.c_reg)):
            c.grid(row=0, column=i, sticky="nsew",
                   padx=(0 if i == 0 else 10, 0), pady=(0, 10))
        cards.pack(fill="x", pady=(0, T.PAD))
        self.log = ctk.CTkTextbox(self.area, height=250, font=T.F_MONO,
                                  fg_color=T.CARD, text_color=T.INK,
                                  border_width=1, border_color=T.BORDA,
                                  corner_radius=T.RAIO, wrap="none")
        self.log.pack(fill="both", expand=True)

    # ------------------------------------------------------------------ #
    def _selecionar(self) -> None:
        if self.runner.ocupado:
            return
        c = filedialog.askopenfilename(
            title="Selecione o arquivo de importação (.txt)",
            initialdir=self.app.config.ultima_pasta("filtrar_import") or None,
            filetypes=[("Arquivo TXT", "*.txt"), ("Todos", "*.*")])
        if not c:
            return
        self.app.config.lembrar_pasta("filtrar_import", c)
        self.txt_path = Path(c)
        self.lbl_txt.configure(text=f"Arquivo: {self.txt_path.name}")
        self.badge.set("informe as notas", "info")
        self.steps.set_ativo(1)

    def _selecionar_modelo(self) -> None:
        if self.runner.ocupado:
            return
        c = filedialog.askopenfilename(
            title="Selecione um arquivo modelo (para copiar os cabeçalhos)",
            initialdir=self.app.config.ultima_pasta("filtrar_import") or None,
            filetypes=[("Arquivos", "*.ret *.RET *.txt"), ("Todos", "*.*")])
        if not c:
            return
        self.modelo_path = Path(c)
        self.lbl_modelo.configure(text=f"Modelo cabeçalho: {self.modelo_path.name}")

    def _processar(self) -> None:
        if self.runner.ocupado:
            return
        if not self.txt_path:
            self.app.toast.show("Selecione o arquivo primeiro.", "err", ms=6000)
            return
        notas = [n.strip() for n in self.e_notas.get().replace(";", ",").split(",")
                 if n.strip()]
        if not notas:
            self.app.toast.show("Digite pelo menos uma nota.", "err", ms=6000)
            return
        cnpj = self.e_cnpj.get().strip()
        self.badge.set("processando…", "info")
        self.b_gerar.configure(state="disabled")
        cfg_ret = dict(self.app.config.get("ret", default={}) or {})
        txt_p = self.txt_path
        modelo = self.modelo_path
        incluir_cab = bool(self.sw_cab.get())
        from ..modules import filtrar_importacao as fi
        self.runner.executar(
            lambda: fi.processar(txt_p, notas, cnpj, cfg_ret=cfg_ret,
                                 incluir_cabecalho=incluir_cab,
                                 modelo_cabecalho=modelo),
            self._concluido, self._falhou)

    def _concluido(self, r) -> None:
        self.resultado = r
        self.b_gerar.configure(state="normal")
        if self.vazio.winfo_ismapped():
            self.vazio.pack_forget()
            self.area.pack(fill="both", expand=True)
        self.c_ped.set(len(r.notas_pedidas))
        self.c_ach.set(len(r.notas_achadas),
                       f"{len(r.notas_faltando)} não achada(s)" if r.notas_faltando else "")
        self.c_reg.set(r.total_registros, f"CNPJ {r.cnpj}" if r.cnpj else "")
        texto = "\n".join(r.log)
        if r.avisos:
            texto += "\n\n⚠ AVISOS:\n" + "\n".join(f"  • {a}" for a in r.avisos)
        self._log_set(texto)
        if r.ok:
            self.badge.set(f"{r.total_registros} linhas prontas",
                           "warn" if r.avisos else "ok")
            self.b_salvar.pack(side="left", padx=8)
            self.steps.set_ativo(2)
            if r.notas_faltando:
                self.app.toast.show(
                    "Algumas notas não foram encontradas no arquivo: "
                    + ", ".join(r.notas_faltando), "warn", ms=9000)
        else:
            self.badge.set("nada a gerar", "err")
            self.app.toast.show(
                "Nenhuma das notas foi encontrada no arquivo.", "err", ms=8000)

    def _falhou(self, exc: Exception) -> None:
        self.b_gerar.configure(state="normal")
        self.badge.set("erro", "err")
        self.app.toast.show(mensagem_erro_amigavel(exc), "err", ms=8000)

    def _gravar(self) -> None:
        if not self.resultado or not self.resultado.ok or self.runner.ocupado:
            return
        saida = filedialog.asksaveasfilename(
            title="Salvar arquivo filtrado",
            defaultextension=".txt",
            initialdir=self.app.config.ultima_pasta("filtrar_import_saida") or None,
            initialfile=f"importacao_filtrada_{timestamp_arquivo()}.txt",
            filetypes=[("Arquivo TXT", "*.txt")])
        if not saida:
            return
        self.app.config.lembrar_pasta("filtrar_import_saida", saida)
        from ..modules import filtrar_importacao as fi
        try:
            fi.gravar(self.resultado, Path(saida))
        except Exception as exc:      # noqa: BLE001
            self.badge.set("erro ao gravar", "err")
            self.app.toast.show(mensagem_erro_amigavel(exc), "err", ms=8000)
            return
        self.saida_gerada = Path(saida)
        self.b_abrir.pack(side="left", padx=8)
        self.b_pasta.pack(side="left")
        historico.registrar(
            "filtrar_importacao", "Filtrar Importação (notas + CNPJ)",
            resumo={
                "notas": len(self.resultado.notas_achadas),
                "registros": self.resultado.total_registros,
                "cnpj": self.resultado.cnpj,
                "cabecalho": self.resultado.cabecalho,
            },
            arquivos=[self.txt_path], saida=str(saida))
        self.steps.set_ativo(3)
        self.badge.set("arquivo gerado", "ok")
        self.app.toast.show(
            "Arquivo gerado. Valide no sistema antes de confirmar.", "ok", ms=7000)
        self.app.atualizar_dashboard()

    # ------------------------------------------------------------------ #
    def _abrir_saida(self) -> None:
        self._abrir(self.saida_gerada)

    def _abrir_pasta(self) -> None:
        self._abrir(self.saida_gerada.parent if self.saida_gerada else None)

    def _abrir(self, alvo) -> None:
        if not alvo:
            return
        try:
            abrir_no_sistema(alvo)
        except Exception as exc:      # noqa: BLE001
            self.app.toast.show(f"Não consegui abrir: {exc}", "err", ms=6000)

    def _log_set(self, texto: str) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("1.0", texto)
        self.log.configure(state="disabled")
