"""
theme.py — Identidade visual UNIFICADA com o REMESSA × BANCO original.

A pedido do Alan: a suíte inteira usa a MESMA paleta do sistema original
Remessa × Banco (vendor/remessa_v3/core/theme.py COLORS), para que tudo
seja visualmente UM sistema só. A sidebar assume o azul da faixa do
Remessa (#073B63), o fundo é o mesmo (#EEF6FF), cards brancos com borda
#B8D4F3 — quando você abre o módulo Remessa embutido, a cor da sidebar e
a da faixa azul dele são idênticas.

Todas as cores moram aqui; nenhuma view define cor solta.
"""

# ── Sidebar (azul da faixa do Remessa — blue_main #073B63) ──────────
SIDEBAR_BG        = "#073B63"   # = COLORS["blue_main"] do Remessa
SIDEBAR_ITEM      = "#A8C8E8"   # = blue_light
SIDEBAR_HOVER     = "#0E4E7E"   # tom intermediário do azul
SIDEBAR_ATIVO     = "#1768AE"   # = blue_sec (destaque do item ativo)
SIDEBAR_ATIVO_TX  = "#FFFFFF"
SIDEBAR_RODAPE    = "#6E90B0"

# ── Superfícies (idênticas ao Remessa) ──────────────────────────────
FUNDO         = "#EEF6FF"   # = bg_main
CARD          = "#FFFFFF"   # = bg_card
BORDA         = "#B8D4F3"   # = border
ZEBRA         = "#F8FAFC"   # = bg_row_alt
TRACK         = "#D6E8FA"   # = bg_topbar

# ── Tinta (texto — idêntica ao Remessa) ─────────────────────────────
INK           = "#0F172A"   # = text_main
INK_2         = "#475569"   # = text_sec
INK_3         = "#94A3B8"   # = text_light
BRANCO        = "#FFFFFF"

# ── Acento e estados (paleta do Remessa) ────────────────────────────
AZUL          = "#1768AE"   # = blue_sec (botões primários, ativo)
AZUL_HOVER    = "#073B63"   # escurece para o azul-assinatura no hover
AZUL_ESCURO   = "#073B63"   # = blue_main (títulos e cabeçalho de tabela)
AZUL_CLARO    = "#2E86D6"

VERDE         = "#16A34A"   # = green_ok
VERDE_BG      = "#DCFCE7"   # = green_bg
AMARELO       = "#B45309"   # = warn_text
AMARELO_BG    = "#FFEDD5"   # = warn_bg
VERMELHO      = "#E31B23"   # = red_err (vermelho exato do Remessa)
VERMELHO_BG   = "#FEE2E2"   # = red_bg
INFO_BG       = "#E0F0FF"   # = bg_hover

# retrocompatibilidade com nomes antigos usados nas views
FUNDO_SIDEBAR_ITEM = SIDEBAR_HOVER

# ── Tipografia ──────────────────────────────────────────────────────
FONTE         = "Segoe UI"
F_TITULO      = (FONTE, 22, "bold")
F_SUBTITULO   = (FONTE, 13)
F_SECAO       = (FONTE, 15, "bold")
F_CARD_LABEL  = (FONTE, 11)
F_CARD_VALOR  = (FONTE, 26, "bold")
F_NORMAL      = (FONTE, 13)
F_PEQUENA     = (FONTE, 11)
F_BOTAO       = (FONTE, 13, "bold")
F_NAV         = (FONTE, 13)
F_MONO        = ("Consolas", 11)
F_CRUMB       = (FONTE, 10)

# ── Métricas de layout (curvas iguais às da prévia) ─────────────────
RAIO          = 14          # cards (border-radius:14px)
RAIO_BTN      = 9           # botões (border-radius:9px)
RAIO_PILL     = 20          # badges/pílulas
FILETE_W      = 4           # filete colorido à esquerda dos cards KPI
SIDEBAR_W     = 230

# ── Escala de espaçamento (grid 4/8/12/16/24/32 — nada de valor solto) ─
ESP = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32}
PAD           = ESP["lg"]   # 16 — padding padrão (retrocompat)
PAD_G         = ESP["xl"]   # 24 — padding generoso (retrocompat)

STATUS_CORES = {
    "ok":   (VERDE,    VERDE_BG),
    "warn": (AMARELO,  AMARELO_BG),
    "err":  (VERMELHO, VERMELHO_BG),
    "info": (AZUL,     INFO_BG),
}
