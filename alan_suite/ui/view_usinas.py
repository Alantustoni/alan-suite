"""
view_usinas.py — Tela do Organizador Usinas (UX v1.2).

UX: botão primário único por etapa, estado vazio antes do primeiro
tratamento, e a seção "Verificar" só aparece quando há linha problemática.
"""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..core import historico, theme as T
from ..core.utils import (abrir_no_sistema, formatar_moeda,
                          mensagem_erro_amigavel, timestamp_arquivo)
from ..modules import usinas
from .widgets import (Badge, Card, EmptyState, MetricCard, StepBar, Tabela,
                      ThreadRunner, botao, cabecalho)


class UsinasView(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.runner = ThreadRunner(self)
        self.arquivo: Path | None = None
        self.resultado: usinas.ResultadoUsinas | None = None

        cabecalho(self, "Organizador Usinas",
                  "Cole a planilha a partir de A1, sem cabeçalho — "
                  "totais por grupo (USIMINAS · ARMAR · CSN · SOLUÇÕES).",
                  crumb="Módulo · reescrito e corrigido", icone="🏭").pack(
            fill="x", pady=(0, 10))

        self.steps = StepBar(self, ["Anexar planilha", "Tratar e conferir",
                                    "Exportar"])
        self.steps.pack(fill="x", pady=(0, T.PAD))

        acoes = Card(self)
        acoes.pack(fill="x", pady=(0, T.PAD))
        box = ctk.CTkFrame(acoes, fg_color="transparent")
        box.pack(fill="x", padx=T.PAD, pady=T.PAD)
        self.b_cta = botao(box, "📎  Selecionar planilha", self._selecionar)
        self.b_cta.pack(side="left")
        self.b_trocar = botao(box, "Trocar planilha", self._selecionar,
                              primario=False)
        self.b_cancelar = botao(box, "✕  Cancelar", self._cancelar,
                                primario=False)
        self.b_abrir = botao(box, "📂  Abrir", self._abrir_saida,
                             primario=False, width=104)
        self.b_pasta = botao(box, "📁  Pasta", self._abrir_pasta,
                             primario=False, width=104)
        self.badge = Badge(box, "aguardando planilha", "info")
        self.badge.pack(side="right")
        self.saida_gerada: Path | None = None

        # ── estado vazio ─────────────────────────────────────────────
        self.vazio = EmptyState(
            self, "▦", "Nenhuma planilha tratada ainda",
            "Cole a planilha a partir de A1 (sem cabeçalho) e selecione. "
            "O sistema totaliza o valor de cada grupo — USIMINAS, ARMAR, CSN e "
            "SOLUÇÕES — com as NFs já protegidas do bug antigo.")
        self.vazio.pack(fill="both", expand=True)

        # ── área de resultados ───────────────────────────────────────
        self.area = ctk.CTkFrame(self, fg_color="transparent")

        # linha 1 — leitura geral
        meta = ctk.CTkFrame(self.area, fg_color="transparent")
        meta.pack(fill="x", pady=(0, 10))
        for i in range(2):
            meta.grid_columnconfigure(i, weight=1, uniform="m")
        self.c_total = MetricCard(meta, "Linhas lidas")
        self.c_val   = MetricCard(meta, "Valor total", T.AZUL_ESCURO)
        for i, c in enumerate((self.c_total, self.c_val)):
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))

        # linha 2 — total por grupo de usina (substitui Tratadas/Para verificar)
        ctk.CTkLabel(self.area, text="Valor total por grupo",
                     font=T.F_SECAO, text_color=T.INK, anchor="w").pack(
            fill="x", pady=(2, 6))
        grupos = ctk.CTkFrame(self.area, fg_color="transparent")
        grupos.pack(fill="x", pady=(0, T.PAD))
        self._ordem_grupos = ["USIMINAS", "ARMAR", "CSN", "SOLUÇÕES"]
        self.cards_grupo: dict[str, MetricCard] = {}
        for i, nome in enumerate(self._ordem_grupos):
            grupos.grid_columnconfigure(i, weight=1, uniform="g")
            card = MetricCard(grupos, nome, T.AZUL)
            card.grid(row=0, column=i, sticky="nsew",
                      padx=(0 if i == 0 else 10, 0))
            self.cards_grupo[nome] = card

        # seção "Verificar" só aparece quando existe linha problemática
        self.sec_ver = ctk.CTkFrame(self.area, fg_color="transparent")
        ctk.CTkLabel(self.sec_ver,
                     text="Linhas para verificar (não entram no arquivo final)",
                     font=T.F_SECAO, text_color=T.AMARELO, anchor="w").pack(
            fill="x", pady=(0, 6))
        self.tab_ver = Tabela(
            self.sec_ver, ["Linha", "Empresa", "NF", "Vencimento", "Valor",
                           "Motivo"],
            larguras=[60, 180, 110, 110, 110, 280], altura=140)
        self.tab_ver.pack(fill="x")

    # ------------------------------------------------------------------ #
    def _cta(self, texto: str, comando) -> None:
        self.b_cta.configure(text=texto, command=comando, state="normal")

    def _mostrar_area(self) -> None:
        if self.vazio.winfo_ismapped():
            self.vazio.pack_forget()
            self.area.pack(fill="both", expand=True)

    def _registrar_saida(self, caminho) -> None:
        self.saida_gerada = Path(caminho)
        self.b_abrir.pack(side="left", padx=8)
        self.b_pasta.pack(side="left", padx=(0, 8))

    def _esconder_saida(self) -> None:
        self.saida_gerada = None
        self.b_abrir.pack_forget()
        self.b_pasta.pack_forget()

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

    # ------------------------------------------------------------------ #
    def _selecionar(self) -> None:
        if self.runner.ocupado:
            return   # Ctrl+O/clique no meio de um processamento
        caminho = filedialog.askopenfilename(
            title="Selecione a planilha das usinas",
            initialdir=self.app.config.ultima_pasta("usinas") or None,
            filetypes=[("Excel", "*.xlsx *.xls")])
        if not caminho:
            return
        self.app.config.lembrar_pasta("usinas", caminho)
        self.arquivo = Path(caminho)
        self.resultado = None
        self._esconder_saida()
        self.badge.set(self.arquivo.name, "info")
        self._cta("▶  Tratar e pré-visualizar", self._processar)
        self.b_trocar.pack(side="left", padx=8)
        self.b_cancelar.pack(side="left", padx=(0, 8))
        self.steps.set_ativo(1)

    def _cancelar(self) -> None:
        """Descarta a planilha anexada e volta ao estado inicial."""
        if self.runner.ocupado:
            return
        if self.resultado is not None and not messagebox.askyesno(
                "Cancelar", "Já existe resultado na tela. Descartar tudo e "
                "recomeçar?", parent=self):
            return
        self.arquivo = None
        self.resultado = None
        self._esconder_saida()
        if self.area.winfo_ismapped():
            self.area.pack_forget()
        if not self.vazio.winfo_ismapped():
            self.vazio.pack(fill="both", expand=True)
        self.badge.set("aguardando planilha", "info")
        self._cta("📎  Selecionar planilha", self._selecionar)
        self.b_trocar.pack_forget()
        self.b_cancelar.pack_forget()
        self.steps.set_ativo(0)

    def _processar(self) -> None:
        if not self.arquivo or self.runner.ocupado:
            return
        self.badge.set("processando…", "info")
        self.b_cta.configure(state="disabled")
        self.b_trocar.configure(state="disabled")
        cfg = self.app.config.get("usinas", default={})
        arquivo = self.arquivo

        self.runner.executar(
            lambda: usinas.ProcessadorUsinas(cfg).processar(arquivo),
            self._concluido, self._falhou)

    def _concluido(self, r: usinas.ResultadoUsinas) -> None:
        self.resultado = r
        self.b_trocar.configure(state="normal")
        self.b_cta.configure(state="normal")
        if getattr(r, "avisos", None):
            self.app.toast.show(" ".join(r.avisos), "warn", ms=9000)
        self._mostrar_area()

        sub_total = f"{r.total_ok} tratadas"
        if r.correcoes_nf:
            sub_total += f" · {r.correcoes_nf} NFs protegidas"
        self.c_total.set(r.total_original, sub_total)
        self.c_val.set(formatar_moeda(r.valor_total))

        # cards de total por grupo — na ordem fixa, 0 quando o grupo não veio
        totais = r.totais_por_grupo or {}
        for nome in self._ordem_grupos:
            self.cards_grupo[nome].set(formatar_moeda(totais.get(nome, 0.0)))
        # grupos fora da lista fixa (ex.: nome não padronizado) entram no "Verificar"
        extras = {k: v for k, v in totais.items()
                  if k not in self._ordem_grupos}
        if extras:
            resumo = " · ".join(f"{k}: {formatar_moeda(v)}"
                                for k, v in extras.items())
            self.cards_grupo["SOLUÇÕES"].set(
                formatar_moeda(totais.get("SOLUÇÕES", 0.0)),
                f"+ outros grupos ({resumo})")

        if r.total_verificar:
            self.tab_ver.preencher([
                [l["LINHA"], l["EMPRESA"], l["NF"], l["VENCIMENTO"],
                 l["VALOR"], l["MOTIVO"]]
                for l in r.linhas_verificar
            ])
            self.sec_ver.pack(fill="x")
        else:
            self.sec_ver.pack_forget()

        tipo = "warn" if r.total_verificar else "ok"
        self.badge.set(
            f"{r.total_ok} tratadas · {r.total_verificar} para verificar", tipo)
        if r.total_ok:
            self._cta("⬇  Exportar Excel tratado", self._exportar)
        else:
            self._cta("📎  Selecionar planilha", self._selecionar)
        self.steps.set_ativo(2)
        if r.usou_mapa_posicional:
            self.app.toast.show(
                "Planilha lida sem cabeçalho (layout do DDA, colada em A1). "
                "Totais por grupo prontos.", "ok")
        else:
            self.app.toast.show(
                "Planilha tratada — totais por grupo prontos.", "ok")

    def _falhou(self, exc: Exception) -> None:
        self.b_cta.configure(state="normal")
        self.b_trocar.configure(state="normal")
        self.badge.set("erro no processamento", "err")
        self.app.toast.show(mensagem_erro_amigavel(exc), "err", ms=8000)

    def _exportar(self) -> None:
        if not self.resultado or self.runner.ocupado:
            return
        saida = filedialog.asksaveasfilename(
            title="Salvar planilha tratada",
            defaultextension=".xlsx",
            initialdir=self.app.config.ultima_pasta("usinas_saida") or None,
            initialfile=f"usinas_tratado_{timestamp_arquivo()}.xlsx",
            filetypes=[("Excel", "*.xlsx")])
        if not saida:
            return
        self.app.config.lembrar_pasta("usinas_saida", saida)
        try:
            usinas.exportar(self.resultado, Path(saida))
        except Exception as exc:      # noqa: BLE001
            self.badge.set("erro ao exportar", "err")
            self.app.toast.show(mensagem_erro_amigavel(exc), "err", ms=8000)
            return
        historico.registrar(
            "usinas", "Tratamento de planilha",
            resumo={
                "linhas": self.resultado.total_original,
                "tratadas": self.resultado.total_ok,
                "pendentes": self.resultado.total_verificar,
            },
            arquivos=[self.arquivo] if self.arquivo else [],
            saida=saida)
        self.steps.set_ativo(3)
        self.badge.set("exportado", "ok")
        self._registrar_saida(saida)
        self.app.toast.show("Arquivo exportado. Use 'Abrir arquivo' para "
                            "conferir.", "ok")
        self.app.atualizar_dashboard()
