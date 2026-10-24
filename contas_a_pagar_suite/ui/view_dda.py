"""
view_dda.py — Tela do Organizador DDA (v1.3).

Motor: DataProcessorExt (motor original do DDA V7 + cabeçalho opcional +
captura das notas removidas). Novidades da tela:
  • cards Semana / Propostas excluídas / Usinas excluídas;
  • totais de usinas por grupo (USIMINAS · ARMAR · CSN · SOLUÇÕES);
  • listas na tela: propostas excluídas e notas programadas — sem
    precisar abrir o Excel;
  • planilha SEM cabeçalho aceita (mapa posicional A/B/D/E/F/G/I/L).
"""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Dict, List

import customtkinter as ctk

from ..core import historico, theme as T
from ..core.utils import (abrir_no_sistema, formatar_moeda,
                          mensagem_erro_amigavel, parse_valor_br,
                          timestamp_arquivo)
from .widgets import (Badge, Card, EmptyState, MetricCard, StepBar, Tabela,
                      ThreadRunner, botao, cabecalho)


class DdaView(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.runner = ThreadRunner(self)
        self.arquivo: Path | None = None
        self.arquivos_banco: List[Path] = []
        self.result = None
        self.metricas: Dict[str, Any] = {}
        self.extras: Dict[str, Any] = {}
        self.rc = None

        cabecalho(self, "Organizador DDA",
                  "Cole a planilha a partir de A1 — com ou sem cabeçalho. "
                  "Tratamento, cruzamento com extratos e relatório semanal.",
                  crumb="Módulo · motor original DDA V7", icone="📋").pack(
            fill="x", pady=(0, 10))

        self.steps = StepBar(self, ["Anexar DDA", "Processar",
                                    "Anexar banco e cruzar", "Exportar"])
        self.steps.pack(fill="x", pady=(0, T.PAD))

        # ── barra de ações ───────────────────────────────────────────
        acoes = Card(self)
        acoes.pack(fill="x", pady=(0, T.PAD))
        box = ctk.CTkFrame(acoes, fg_color="transparent")
        box.pack(fill="x", padx=T.PAD, pady=T.PAD)
        self.b_cta = botao(box, "📎  Anexar DDA", self._selecionar)
        self.b_cta.pack(side="left")
        self.b_trocar = botao(box, "Trocar arquivo", self._selecionar,
                              primario=False)
        self.b_alt = botao(box, "⬇  Exportar sem cruzar", self._exportar,
                           primario=False)
        self.b_cancelar = botao(box, "✕  Cancelar", self._cancelar,
                                primario=False)
        self.b_abrir = botao(box, "📂  Abrir", self._abrir_saida,
                             primario=False, width=104)
        self.b_pasta = botao(box, "📁  Pasta", self._abrir_pasta,
                             primario=False, width=104)
        self.b_cons = botao(box, "📑  Consolidar revisado", self._consolidar,
                            primario=False)
        self.b_cons.pack(side="right", padx=(8, 0))
        self.badge = Badge(box, "aguardando arquivo", "info")
        self.badge.pack(side="right")
        self.saida_gerada: Path | None = None

        self.progresso = ctk.CTkProgressBar(self, height=8, corner_radius=4,
                                            fg_color=T.TRACK,
                                            progress_color=T.AZUL)
        self.progresso.set(0)
        self.lbl_status = ctk.CTkLabel(self, text="", font=T.F_PEQUENA,
                                       text_color=T.INK_2, anchor="w")

        # ── estado vazio ─────────────────────────────────────────────
        self.vazio = EmptyState(
            self, "▤", "Nenhum DDA processado ainda",
            "Anexe a planilha DDA (pode colar sem cabeçalho — o sistema "
            "reconhece as colunas pela posição). Depois de processar, tudo "
            "aparece aqui: semana, propostas e usinas excluídas, notas "
            "programadas e pendentes.")
        self.vazio.pack(fill="both", expand=True)

        # ── área de resultados (rolável — tem bastante conteúdo) ─────
        self.area = ctk.CTkScrollableFrame(self, fg_color="transparent")

        # linha 1: números principais
        self.l1 = l1 = ctk.CTkFrame(self.area, fg_color="transparent")
        l1.pack(fill="x", pady=(0, 10))
        for i in range(3):                       # 3 cards fixos + erro opcional
            l1.grid_columnconfigure(i, weight=1, uniform="m")
        l1.grid_columnconfigure(3, weight=0, uniform="m")   # col do erro: só com erro
        self.c_linhas = MetricCard(l1, "Linhas tratadas")
        self.c_prog   = MetricCard(l1, "Programadas", T.VERDE)
        self.c_pend   = MetricCard(l1, "Pendentes", T.AMARELO)
        self.c_erros  = MetricCard(l1, "Linhas com erro", T.VERMELHO)
        # os 3 primeiros já aparecem (Programadas/Pendentes com "—" até cruzar),
        # evitando colunas vazias no meio da linha.
        self.c_linhas.grid(row=0, column=0, sticky="nsew")
        self.c_prog.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.c_pend.grid(row=0, column=2, sticky="nsew", padx=(10, 0))

        # linha 2: semana + exclusões
        l2 = ctk.CTkFrame(self.area, fg_color="transparent")
        l2.pack(fill="x", pady=(0, 10))
        for i in range(3):
            l2.grid_columnconfigure(i, weight=1, uniform="n")
        self.c_semana = MetricCard(l2, "Semana")
        self.c_prop   = MetricCard(l2, "Propostas excluídas", T.AMARELO)
        self.c_usi    = MetricCard(l2, "Usinas excluídas", T.AMARELO)
        for i, c in enumerate((self.c_semana, self.c_prop, self.c_usi)):
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))

        # card: usinas por grupo
        self.card_grupos = Card(self.area)
        ctk.CTkLabel(self.card_grupos, text="VALOR DE USINAS POR GRUPO",
                     font=T.F_CARD_LABEL, text_color=T.INK_2,
                     anchor="w").pack(fill="x", padx=T.PAD, pady=(12, 2))
        self.linha_grupos = ctk.CTkFrame(self.card_grupos,
                                         fg_color="transparent")
        self.linha_grupos.pack(fill="x", padx=T.PAD, pady=(0, 12))
        self._widgets_grupos: list = []

        # seção: propostas excluídas
        self.sec_prop = ctk.CTkFrame(self.area, fg_color="transparent")
        ctk.CTkLabel(self.sec_prop, text="Propostas excluídas",
                     font=T.F_SECAO, text_color=T.AMARELO, anchor="w").pack(
            fill="x", pady=(4, 6))
        self.tab_prop = Tabela(
            self.sec_prop, ["Empresa", "Fornecedor", "NF", "Vencimento",
                            "Valor"],
            larguras=[160, 240, 110, 110, 130], altura=160,
            alinhamentos=["w", "w", "w", "w", "e"])
        self.tab_prop.pack(fill="x")

        # seção: notas programadas
        self.sec_prog = ctk.CTkFrame(self.area, fg_color="transparent")
        ctk.CTkLabel(self.sec_prog, text="Notas programadas (conferem no banco)",
                     font=T.F_SECAO, text_color=T.VERDE, anchor="w").pack(
            fill="x", pady=(4, 6))
        self.tab_prog = Tabela(
            self.sec_prog, ["Empresa", "Fornecedor", "NF", "Vencimento",
                            "Data banco", "Valor", "Match"],
            larguras=[140, 220, 90, 100, 100, 120, 70], altura=200,
            busca=True, exportar=True, nome_export="programadas",
            alinhamentos=["w", "w", "w", "w", "w", "e", "w"])
        self.tab_prog.pack(fill="x")

        # seção: pendentes
        self.sec_pend = ctk.CTkFrame(self.area, fg_color="transparent")
        ctk.CTkLabel(self.sec_pend, text="Notas pendentes",
                     font=T.F_SECAO, text_color=T.AMARELO, anchor="w").pack(
            fill="x", pady=(4, 6))
        self.tabela = Tabela(
            self.sec_pend, ["Empresa", "Fornecedor", "NF", "Vencimento",
                            "Valor"],
            larguras=[160, 240, 110, 110, 130], altura=200,
            busca=True, exportar=True, nome_export="pendentes",
            alinhamentos=["w", "w", "w", "w", "e"])
        self.tabela.pack(fill="x")

        # seção: pagamentos do banco SEM nota no DDA (melhoria vinda do DDA V7)
        self.sec_semnota = ctk.CTkFrame(self.area, fg_color="transparent")
        ctk.CTkLabel(self.sec_semnota,
                     text="Pagamentos do banco sem nota no DDA",
                     font=T.F_SECAO, text_color=T.VERMELHO, anchor="w").pack(
            fill="x", pady=(4, 6))
        self.tab_semnota = Tabela(
            self.sec_semnota, ["Empresa (banco)", "Favorecido", "Data",
                               "Valor"],
            larguras=[180, 250, 110, 130], altura=160,
            alinhamentos=["w", "w", "w", "e"])
        self.tab_semnota.pack(fill="x")

    # ------------------------------------------------------------------ #
    def _cta(self, texto: str, comando) -> None:
        self.b_cta.configure(text=texto, command=comando, state="normal")

    def _mostrar_resultados(self) -> None:
        if self.vazio.winfo_ismapped():
            self.vazio.pack_forget()
            self.area.pack(fill="both", expand=True)

    # ------------------------------------------------------------------ #
    # Abrir arquivo/pasta gerado + memória da última pasta                 #
    # ------------------------------------------------------------------ #
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
            title="Selecione a planilha DDA (com ou sem cabeçalho)",
            initialdir=self.app.config.ultima_pasta("dda") or None,
            filetypes=[("Excel", "*.xlsx *.xls")])
        if not caminho:
            return
        self.app.config.lembrar_pasta("dda", caminho)
        self.arquivo = Path(caminho)
        self.result = self.rc = None
        self._esconder_saida()
        self.badge.set(self.arquivo.name, "info")
        self._cta("▶  Processar", self._processar)
        self.b_trocar.pack(side="left", padx=8)
        self.b_cancelar.pack(side="left", padx=(0, 8))
        self.b_alt.pack_forget()
        self.steps.set_ativo(1)

    def _cancelar(self) -> None:
        """Descarta o DDA/extratos anexados e volta ao estado inicial."""
        if self.runner.ocupado:
            return
        if self.result is not None and not _confirmar_descarte(self):
            return
        self.arquivo = None
        self.arquivos_banco = []
        self.result = self.rc = None
        self.metricas = {}
        self.extras = {}
        if self.area.winfo_ismapped():
            self.area.pack_forget()
        if not self.vazio.winfo_ismapped():
            self.vazio.pack(fill="both", expand=True)
        self.progresso.pack_forget()
        self.lbl_status.pack_forget()
        self.badge.set("aguardando arquivo", "info")
        self._cta("📎  Anexar DDA", self._selecionar)
        self.b_trocar.pack_forget()
        self.b_cancelar.pack_forget()
        self.b_alt.pack_forget()
        self._esconder_saida()
        self.steps.set_ativo(0)

    # ------------------------------------------------------------------ #
    def _processar(self) -> None:
        if not self.arquivo or self.runner.ocupado:
            return
        self._fase = "processar"
        self._ocupado("Processando DDA…")
        arquivo = self.arquivo
        config_dda = self.app.config.config_dda()
        # mesmos grupos do Organizador Usinas (editáveis nas Configurações);
        # "dda_grupos_usinas" continua como override opcional no config.json
        grupos = (self.app.config.get("dda_grupos_usinas", default=None)
                  or self.app.config.get("usinas", "padronizacao_empresa",
                                         default=None))

        def trabalho():
            from ..modules.dda_ext import (DataProcessorExt,
                                           semana_do_resultado)
            from ..vendor.organizador_dda.core.metrics import calcular_metricas
            proc = DataProcessorExt(config_dda, grupos)
            result = proc.processar(arquivo)
            extras = {
                "semana": semana_do_resultado(result.df),
                "df_propostas": proc.df_propostas,
                "totais_usinas": proc.totais_usinas,
                "qtd_usinas": len(proc.df_usinas),
                "posicional": proc.usou_mapa_posicional,
            }
            return result, calcular_metricas(result), extras

        self.runner.executar(trabalho, self._processado, self._falhou)

    def _processado(self, carga) -> None:
        self.result, self.metricas, self.extras = carga
        self._livre()
        self._mostrar_resultados()
        r = self.result

        self.c_linhas.set(r.total_processado, f"de {r.total_original} originais")
        self.c_semana.set(self.extras["semana"],
                          "menor → maior vencimento tratado")
        self.c_prop.set(r.removidas_proposta)
        self.c_usi.set(self.extras["qtd_usinas"],
                       formatar_moeda(r.valor_siderurgicas_removidas))

        # usinas por grupo
        self._montar_grupos(self.extras["totais_usinas"])

        # propostas excluídas na tela
        dfp = self.extras["df_propostas"]
        if dfp is not None and not dfp.empty:
            self.tab_prop.preencher([
                [row.get("EMPRESA", row.get("EMPRESA_ORIGINAL", "")),
                 row.get("FORNECEDOR", ""), row.get("PRV NF", ""),
                 _fmt_data(row.get("VENC")), _fmt_valor(row.get("VALOR"))]
                for _, row in dfp.head(150).iterrows()
            ])
            self.sec_prop.pack(fill="x")
        else:
            self.sec_prop.pack_forget()

        n_erros = int((r.df["ERROS"] != "").sum()) if "ERROS" in r.df else 0
        if n_erros:
            self.l1.grid_columnconfigure(3, weight=1, uniform="m")
            self.c_erros.grid(row=0, column=3, sticky="nsew", padx=(10, 0))
            self.c_erros.set(n_erros)
        else:
            self.c_erros.grid_remove()
            self.l1.grid_columnconfigure(3, weight=0, uniform="m")  # colapsa a coluna

        aviso_pos = (" · colunas mapeadas pela posição (sem cabeçalho)"
                     if self.extras["posicional"] else "")
        self.badge.set(f"processado{aviso_pos}",
                       "warn" if n_erros else "ok")
        self._cta("🏦  Anexar banco e cruzar", self._cruzar)
        self.b_alt.pack(side="left", padx=8)
        self.steps.set_ativo(2)
        self.app.toast.show(
            "DDA processado" + aviso_pos + ". Anexe os extratos para cruzar.",
            "ok", ms=5000)

    def _montar_grupos(self, totais: Dict[str, float]) -> None:
        for w in self._widgets_grupos:
            w.destroy()
        self._widgets_grupos.clear()
        ordem = ["USIMINAS", "ARMAR", "CSN", "SOLUÇÕES", "OUTRAS"]
        mostrados = [g for g in ordem if totais.get(g)]
        if not mostrados:
            self.card_grupos.pack_forget()
            return
        if self.sec_prop.winfo_manager():      # reprocessamento: mantém ordem
            self.card_grupos.pack(fill="x", pady=(0, 10), before=self.sec_prop)
        else:
            self.card_grupos.pack(fill="x", pady=(0, 10))
        for i, g in enumerate(mostrados):
            bloco = ctk.CTkFrame(self.linha_grupos, fg_color="transparent")
            bloco.pack(side="left", expand=True, fill="x")
            self._widgets_grupos.append(bloco)
            ctk.CTkLabel(bloco, text=g, font=(T.FONTE, 12, "bold"),
                         text_color=T.INK_2).pack(anchor="w")
            ctk.CTkLabel(bloco, text=formatar_moeda(totais[g]),
                         font=(T.FONTE, 17, "bold"),
                         text_color=T.AZUL_ESCURO).pack(anchor="w")

    # ------------------------------------------------------------------ #
    def _cruzar(self) -> None:
        if self.result is None or self.runner.ocupado:
            return
        caminhos = filedialog.askopenfilenames(
            title="Selecione os extratos do banco (a empresa é detectada "
                  "automaticamente)",
            initialdir=self.app.config.ultima_pasta("dda_banco") or None,
            filetypes=[("Excel", "*.xlsx *.xls")])
        if not caminhos:
            return
        self.arquivos_banco = [Path(c) for c in caminhos]
        self.app.config.lembrar_pasta("dda_banco", caminhos[0])
        self._fase = "cruzar"
        self._ocupado("Cruzando com o banco…")
        df = self.result.df
        config_dda = self.app.config.config_dda()

        def progresso(pct: float, msg: str) -> None:
            # chamado da THREAD de trabalho — o after() agenda para a thread
            # da UI; protegido para nunca derrubar o cruzamento por um
            # detalhe de exibição (ex.: janela sendo fechada no meio)
            try:
                self.after(0, lambda: (self.progresso.set(pct),
                                       self.lbl_status.configure(text=msg)))
            except Exception:   # noqa: BLE001 — só exibição
                pass

        def trabalho():
            from ..vendor.organizador_dda.core.banco_parser import (
                detectar_empresa_arquivo, parse_banco)
            from ..vendor.organizador_dda.core.banco_cruzamento import cruzar
            from ..vendor.organizador_dda.core.aprendizado import (
                aprender_do_cruzamento)

            pagamentos = []
            detectados = []
            for p in self.arquivos_banco:
                empresa = detectar_empresa_arquivo(p)
                detectados.append(f"{p.name} → {empresa or 'não identificada'}")
                pagamentos.extend(parse_banco(
                    p,
                    termos_siderurgicos=config_dda.remover_texto,
                    cnpjs_excluidos=config_dda.cnpjs_excluidos))
            rc = cruzar(df, pagamentos, callback_progresso=progresso)
            try:
                aprender_do_cruzamento(rc)
            except Exception:
                pass
            return rc, detectados

        self.runner.executar(trabalho, self._cruzado, self._falhou)

    def _cruzado(self, carga) -> None:
        self.rc, detectados = carga
        self._livre()
        rc = self.rc

        # ── AVANÇA O FLUXO PRIMEIRO ───────────────────────────────────
        # O cruzamento deu certo: o botão passa a ser "Exportar" JÁ, antes
        # de montar as tabelas. Assim, mesmo que a montagem de alguma
        # tabela tropece, o usuário nunca fica preso em "Anexar banco".
        self._cta("⬇  Exportar relatório", self._exportar)
        self.b_alt.pack_forget()
        self.steps.set_ativo(3)

        # a partir daqui é só apresentação — protegido para não travar nada
        try:
            self._render_cruzado(rc, detectados)
        except Exception as exc:      # noqa: BLE001
            self.badge.set(f"{rc.total_programado} programadas · "
                           f"{rc.total_pendente} pendentes", "ok")
            self.app.toast.show(
                "Cruzamento concluído. Já dá para exportar — mas houve um "
                f"erro ao montar as tabelas da tela: {exc}", "warn", ms=8000)

    def _render_cruzado(self, rc, detectados) -> None:
        # c_prog/c_pend já estão na grade desde o início (mostravam "—")
        self.c_prog.set(rc.total_programado, formatar_moeda(rc.valor_programado))
        self.c_pend.set(rc.total_pendente, formatar_moeda(rc.valor_pendente))

        # notas programadas na tela (sem abrir o Excel)
        if not rc.df_programado.empty:
            self.tab_prog.preencher([
                [row.get("EMPRESA", ""), row.get("FORNECEDOR", ""),
                 row.get("PRV NF", ""), _fmt_data(row.get("VENC")),
                 str(row.get("BANCO_DATA", ""))[:10],
                 formatar_moeda(row.get("VALOR")),
                 row.get("MATCH_TIPO", "")]
                for _, row in rc.df_programado.head(300).iterrows()
            ])
            self.sec_prog.pack(fill="x")
        else:
            self.sec_prog.pack_forget()

        linhas = []
        if not rc.df_pendente.empty:
            for _, row in rc.df_pendente.head(200).iterrows():
                linhas.append([
                    row.get("EMPRESA", ""), row.get("FORNECEDOR", ""),
                    row.get("PRV NF", ""), _fmt_data(row.get("VENC")),
                    formatar_moeda(row.get("VALOR")),
                ])
        self.tabela.preencher(linhas)
        if linhas:
            self.sec_pend.pack(fill="x")
        else:
            self.sec_pend.pack_forget()

        # pagamentos do banco sem nota (melhoria vinda do DDA V7)
        sem_nota = getattr(rc, "pagamentos_nao_casados", []) or []
        if sem_nota:
            self.tab_semnota.preencher([
                [getattr(pg, "empresa_banco", ""),
                 getattr(pg, "favorecido", ""),
                 str(getattr(pg, "data", "")),
                 formatar_moeda(getattr(pg, "valor", None))]
                for pg in sem_nota[:200]
            ])
            self.sec_semnota.pack(fill="x")
        else:
            self.sec_semnota.pack_forget()

        # trava de conciliação: a conta entrada = saída fechou?
        conc = self._conciliar(rc)
        tipo = "ok" if (conc is None or conc.ok) else "err"
        base = f"{rc.total_programado} programadas · {rc.total_pendente} pendentes"
        if sem_nota:
            base += f" · {len(sem_nota)} banco s/ nota"
        if conc is not None and not conc.ok:
            base += " · ⚠ conciliação não fechou"
        self.badge.set(base, tipo if rc.total_pendente == 0 or sem_nota else "warn")

        # (o botão "Exportar" e o passo 3 já foram ativados em _cruzado)
        msg = "Cruzamento concluído — " + " | ".join(detectados[:3])
        if conc is not None and not conc.ok:
            msg = ("⚠ CONCILIAÇÃO NÃO FECHOU — alguma nota pode ter se "
                   "perdido. Confira a aba ERROS do relatório.")
            self.app.toast.show(msg, "err", ms=9000)
        else:
            self.app.toast.show(msg, "ok", ms=6000)

    def _conciliar(self, rc):
        """Roda a trava de conciliação do DDA V7 (nenhuma nota some calada)."""
        try:
            from ..vendor.organizador_dda.core.conciliacao import conciliar
            return conciliar(self.result, rc)
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    def _exportar(self) -> None:
        if self.result is None or self.runner.ocupado:
            return
        saida = filedialog.asksaveasfilename(
            title="Salvar relatório",
            defaultextension=".xlsx",
            initialdir=self.app.config.ultima_pasta("dda_saida") or None,
            initialfile=f"relatorio_dda_{timestamp_arquivo()}.xlsx",
            filetypes=[("Excel", "*.xlsx")])
        if not saida:
            return
        self.app.config.lembrar_pasta("dda_saida", saida)
        self._fase = "exportar"
        self._ocupado("Gerando relatório…")
        config_dda = self.app.config.config_dda()
        result, metricas, rc = self.result, self.metricas, self.rc

        def trabalho():
            from ..vendor.organizador_dda.excel.report_generator import (
                ExcelReportGenerator)
            ExcelReportGenerator(result, config_dda, metricas, rc).gerar(Path(saida))
            return saida

        self.runner.executar(trabalho, self._exportado, self._falhou)

    def _exportado(self, saida: str) -> None:
        self._livre()
        rc = self.rc
        historico.registrar(
            "dda", "Relatório semanal",
            resumo={
                "linhas": self.result.total_processado,
                "programados": rc.total_programado if rc else 0,
                "pendentes": rc.total_pendente if rc else self.result.total_processado,
            },
            arquivos=[self.arquivo] + self.arquivos_banco, saida=saida)
        self.steps.set_ativo(4)
        self.badge.set("relatório exportado", "ok")
        self.b_alt.pack_forget()          # não faz sentido "Exportar sem cruzar" aqui
        self._registrar_saida(saida)
        self.app.toast.show("Relatório gerado. Use 'Abrir arquivo' para conferir.",
                            "ok")
        self.app.atualizar_dashboard()

    def _consolidar(self) -> None:
        if self.runner.ocupado:
            return
        caminho = filedialog.askopenfilename(
            title="Selecione o relatório REVISADO para consolidar",
            initialdir=self.app.config.ultima_pasta("dda_saida") or None,
            filetypes=[("Excel", "*.xlsx")])
        if not caminho:
            return
        self.app.config.lembrar_pasta("dda_saida", caminho)
        self._fase = "consolidar"
        self._ocupado("Consolidando…")

        def trabalho():
            from ..vendor.organizador_dda.excel.consolidador import consolidar_arquivo
            # grava num arquivo NOVO (_consolidado.xlsx) — devolve o caminho
            return str(consolidar_arquivo(Path(caminho)))

        def concluido(saida):
            self._livre()
            historico.registrar("dda", "Consolidação",
                                arquivos=[caminho], saida=saida)
            self.badge.set("consolidado", "ok")
            self._registrar_saida(saida)
            self.app.toast.show(
                "Consolidação concluída num arquivo novo "
                f"({Path(saida).name}). Use 'Abrir arquivo'.", "ok", ms=7000)
            self.app.atualizar_dashboard()

        self.runner.executar(trabalho, concluido, self._falhou)

    # ------------------------------------------------------------------ #
    _ROTULO_FASE = {
        "processar":  "processamento do DDA",
        "cruzar":     "cruzamento com o banco",
        "exportar":   "geração do relatório",
        "consolidar": "consolidação",
    }

    def _falhou(self, exc: Exception) -> None:
        # libera os botões e esconde a barra de progresso, MAS mantém a
        # mensagem de erro visível na tela (o toast some em segundos e o
        # usuário ficava sem entender por que o botão não mudou).
        self.progresso.pack_forget()
        for b in (self.b_cta, self.b_trocar, self.b_cancelar,
                  self.b_alt, self.b_cons):
            b.configure(state="normal")
        rotulo = self._ROTULO_FASE.get(getattr(self, "_fase", ""), "operação")
        msg = mensagem_erro_amigavel(exc)
        self.badge.set(f"erro no {rotulo}", "err")
        self.lbl_status.configure(text=f"⚠  Falha no {rotulo}:  {msg}",
                                  text_color=T.VERMELHO)
        self.lbl_status.pack(fill="x", pady=(0, 8), after=self.steps)
        self.app.toast.show(f"Falha no {rotulo}: {msg}", "err", ms=9000)

    def _ocupado(self, msg: str) -> None:
        self.progresso.pack(fill="x", pady=(0, 2), after=self.steps)
        self.lbl_status.pack(fill="x", pady=(0, 8), after=self.progresso)
        self.progresso.set(0)
        self.lbl_status.configure(text=msg, text_color=T.INK_2)   # limpa erro
        for b in (self.b_cta, self.b_trocar, self.b_cancelar,
                  self.b_alt, self.b_cons):
            b.configure(state="disabled")

    def _livre(self) -> None:
        self.progresso.pack_forget()
        self.lbl_status.pack_forget()
        self.lbl_status.configure(text_color=T.INK_2)
        for b in (self.b_cta, self.b_trocar, self.b_cancelar,
                  self.b_alt, self.b_cons):
            b.configure(state="normal")


def _confirmar_descarte(parent) -> bool:
    """Pergunta antes de descartar dados já processados na tela."""
    return messagebox.askyesno(
        "Cancelar",
        "Já existe resultado na tela. Descartar tudo e recomeçar?",
        parent=parent)


def _fmt_data(v) -> str:
    if hasattr(v, "strftime"):
        return v.strftime("%d/%m/%Y")
    txt = str(v or "").strip()
    if not txt or txt.lower() in ("nan", "nat", "none"):
        return ""
    # datetime que veio como texto: "2026-07-29 00:00:00" → "29/07/2026"
    if len(txt) >= 10 and txt[4] == "-" and txt[7] == "-":
        a, m, d = txt[:4], txt[5:7], txt[8:10]
        return f"{d}/{m}/{a}"
    return txt


def _fmt_valor(v) -> str:
    """Valor robusto: aceita float, str ('783.6' / '1.234,56') ou vazio."""
    if v is None or (isinstance(v, float) and v != v):   # None ou NaN
        return ""
    if isinstance(v, (int, float)):
        return formatar_moeda(float(v))
    parsed = parse_valor_br(v)
    return formatar_moeda(parsed) if parsed is not None else str(v)
