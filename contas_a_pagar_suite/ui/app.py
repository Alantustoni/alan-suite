"""
app.py — Janela principal da suíte: sidebar + navegação entre módulos.

As views são criadas sob demanda (lazy) — a janela abre instantânea e
cada módulo só importa pandas/openpyxl quando é usado pela primeira vez.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

import customtkinter as ctk

from .. import __version__
from ..core import theme as T
from ..core.config_central import ConfigCentral
from .widgets import Toast

logger = logging.getLogger(__name__)

# mesmos glifos da prévia web (design ERP Premium)
NAV = [
    ("inicio",  "◉", "Início"),
    ("dda",     "▤", "Organizador DDA"),
    ("remessa", "⇄", "Remessa × Banco"),
    ("ret",     "⧉", "Código de barras"),
    ("import_usinas", "📥", "Importação Usinas"),
    ("retorno", "🧾", "Retorno (SISPAG)"),
    ("usinas",  "▦", "Organizador Usinas"),
    ("config",  "⚙", "Configurações"),
]


class AlanSuiteApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__(fg_color=T.FUNDO)
        ctk.set_appearance_mode("light")
        self.geometry("1280x820")
        self.minsize(1080, 700)

        self.title(f"ALAN — Contas a Pagar  ·  v{__version__}")
        self.config = ConfigCentral()
        self.toast = Toast(self)
        self._views: Dict[str, ctk.CTkFrame] = {}
        self._nav_botoes: Dict[str, ctk.CTkButton] = {}
        self._atual: Optional[str] = None

        self._montar_sidebar()
        self._conteudo = ctk.CTkFrame(self, fg_color="transparent")
        self._conteudo.pack(side="left", fill="both", expand=True,
                            padx=T.PAD_G, pady=T.PAD_G)

        self._atalhos()
        self.navegar("inicio")

    # ------------------------------------------------------------------ #
    def _montar_sidebar(self) -> None:
        sb = ctk.CTkFrame(self, width=T.SIDEBAR_W, fg_color=T.SIDEBAR_BG,
                          corner_radius=0)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        ctk.CTkLabel(sb, text="ALAN", font=(T.FONTE, 20, "bold"),
                     text_color=T.BRANCO, anchor="w").pack(
            fill="x", padx=20, pady=(24, 0))
        ctk.CTkLabel(sb, text="Contas a Pagar",
                     font=(T.FONTE, 11), text_color=T.SIDEBAR_ITEM,
                     anchor="w").pack(fill="x", padx=20, pady=(0, 18))

        for chave, icone, rotulo in NAV:
            btn = ctk.CTkButton(
                sb, text=f"  {icone}   {rotulo}", font=T.F_NAV, anchor="w",
                height=42, corner_radius=T.RAIO_BTN,
                fg_color="transparent", hover_color=T.SIDEBAR_HOVER,
                text_color=T.SIDEBAR_ITEM,
                command=lambda k=chave: self.navegar(k))
            btn.pack(fill="x", padx=10, pady=2)
            self._nav_botoes[chave] = btn

        rodape = ctk.CTkLabel(
            sb, font=(T.FONTE, 9), text_color=T.SIDEBAR_RODAPE, justify="left",
            anchor="w",
            text=f"v{__version__} · uso interno\n"
                 "DDA e Remessa: motores originais\n"
                 "RET e Usinas: reescritos e corrigidos")
        rodape.pack(side="bottom", fill="x", padx=20, pady=16)

    def _atalhos(self) -> None:
        for i, (chave, _, _) in enumerate(NAV, start=1):
            self.bind(f"<Control-Key-{i}>", lambda _e, k=chave: self.navegar(k))
        # Ações do módulo atual: Enter = ação primária, Esc = cancelar,
        # Ctrl+O = anexar arquivo. Reaproveita os botões da própria tela.
        self.bind("<Return>", lambda _e: self._atalho_view("primario"))
        self.bind("<Escape>", lambda _e: self._atalho_view("cancelar"))
        self.bind("<Control-o>", lambda _e: self._atalho_view("abrir"))
        self.bind("<Control-O>", lambda _e: self._atalho_view("abrir"))

    def _atalho_view(self, acao: str) -> None:
        view = self._views.get(self._atual)
        # não dispara "Enter" enquanto o foco está num campo de texto/busca
        if acao in ("primario",):
            w = self.focus_get()
            if w is not None and w.winfo_class() in ("Entry", "Text", "TEntry"):
                return
        if view is None:
            if acao == "cancelar":
                self.navegar("inicio")
            return
        if acao == "primario":
            b = getattr(view, "b_cta", None)
            if b is not None and str(b.cget("state")) != "disabled":
                b.invoke()
        elif acao == "abrir":
            if hasattr(view, "_selecionar"):
                view._selecionar()
        elif acao == "cancelar":
            b = getattr(view, "b_cancelar", None)
            if (b is not None and b.winfo_ismapped()
                    and str(b.cget("state")) != "disabled"):
                b.invoke()
            else:
                self.navegar("inicio")

    # ------------------------------------------------------------------ #
    def navegar(self, chave: str) -> None:
        if chave == self._atual:
            return
        if self._atual and self._atual in self._views:
            self._views[self._atual].pack_forget()

        if chave not in self._views:
            self._views[chave] = self._criar_view(chave)

        self._views[chave].pack(fill="both", expand=True)
        self._atual = chave
        for k, btn in self._nav_botoes.items():
            if k == chave:
                btn.configure(fg_color=T.SIDEBAR_ATIVO,
                              text_color=T.SIDEBAR_ATIVO_TX,
                              font=(T.FONTE, 13, "bold"))
            else:
                btn.configure(fg_color="transparent",
                              text_color=T.SIDEBAR_ITEM, font=T.F_NAV)
        if chave == "inicio":
            self.atualizar_dashboard()

    def _criar_view(self, chave: str) -> ctk.CTkFrame:
        # imports locais: cada tela (e suas dependências pesadas)
        # só carrega quando é aberta pela primeira vez
        if chave == "inicio":
            from .view_dashboard import DashboardView
            return DashboardView(self._conteudo, self)
        if chave == "dda":
            from .view_dda import DdaView
            return DdaView(self._conteudo, self)
        if chave == "remessa":
            from .view_remessa import RemessaView
            return RemessaView(self._conteudo, self)
        if chave == "ret":
            from .view_ret import RetView
            return RetView(self._conteudo, self)
        if chave == "import_usinas":
            from .view_importacao_usinas import ImportacaoUsinasView
            return ImportacaoUsinasView(self._conteudo, self)
        if chave == "retorno":
            from .view_retorno import RetornoView
            return RetornoView(self._conteudo, self)
        if chave == "usinas":
            from .view_usinas import UsinasView
            return UsinasView(self._conteudo, self)
        if chave == "config":
            from .view_config import ConfigView
            return ConfigView(self._conteudo, self)
        raise ValueError(f"View desconhecida: {chave}")

    def atualizar_dashboard(self) -> None:
        view = self._views.get("inicio")
        if view is not None:
            view.atualizar()
