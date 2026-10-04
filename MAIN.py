import os
import sqlite3
import calendar
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import date, datetime

try:
    from PIL import Image, ImageTk
    PIL_DISPONIVEL = True
except ImportError:
    PIL_DISPONIVEL = False

# ---------------------------------------------------------------------------
# Cores e estilo geral
# ---------------------------------------------------------------------------
COR_SIDEBAR = "#1f2933"
COR_SIDEBAR_HOVER = "#2b3644"
COR_SIDEBAR_TEXTO = "#e4e7eb"
COR_SIDEBAR_TEXTO_SEC = "#9aa5b1"
COR_FUNDO = "#f5f6fa"
COR_CARD = "#ffffff"
COR_TEXTO = "#1f2933"
COR_ACCENT = "#2563eb"
COR_VERDE = "#15803d"
COR_VERMELHO = "#dc2626"
FONTE_PADRAO = ("Segoe UI", 10)
FONTE_TITULO = ("Segoe UI", 16, "bold")
FONTE_SUBTITULO = ("Segoe UI", 12, "bold")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dados_freelancer.db")


# ---------------------------------------------------------------------------
# Funções utilitárias
# ---------------------------------------------------------------------------
def formatar_moeda(valor):
    """Formata um número como moeda brasileira: 1234.5 -> R$ 1.234,50"""
    try:
        texto = f"{valor:,.2f}"
    except (TypeError, ValueError):
        texto = "0,00"
        return f"R$ {texto}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def formatar_data_br(data_iso):
    """'2026-09-25' -> '25/09/2026'"""
    try:
        d = datetime.strptime(data_iso, "%Y-%m-%d").date()
        return d.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return data_iso or ""


# ---------------------------------------------------------------------------
# Camada de dados (SQLite)
# ---------------------------------------------------------------------------
class Banco:
    def __init__(self, caminho):
        self.conn = sqlite3.connect(caminho)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._criar_tabelas()

    def _criar_tabelas(self):
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS config (
                chave TEXT PRIMARY KEY,
                valor TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS trabalhos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                finalizado INTEGER NOT NULL DEFAULT 0,
                finalizado_em TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS dias_trabalhados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trabalho_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                valor REAL NOT NULL,
                FOREIGN KEY (trabalho_id) REFERENCES trabalhos(id) ON DELETE CASCADE
            )
        """)
        self.conn.commit()

    # ---- configurações (nome de perfil, foto, diária padrão) ----
    def get_config(self, chave, padrao=None):
        c = self.conn.cursor()
        c.execute("SELECT valor FROM config WHERE chave = ?", (chave,))
        row = c.fetchone()
        return row[0] if row else padrao

    def set_config(self, chave, valor):
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO config (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
            (chave, str(valor)),
        )
        self.conn.commit()

    # ---- trabalhos ----
    def criar_trabalho(self, nome):
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO trabalhos (nome, criado_em, finalizado) VALUES (?, ?, 0)",
            (nome, date.today().isoformat()),
        )
        self.conn.commit()
        return c.lastrowid

    def renomear_trabalho(self, trabalho_id, novo_nome):
        c = self.conn.cursor()
        c.execute("UPDATE trabalhos SET nome = ? WHERE id = ?", (novo_nome, trabalho_id))
        self.conn.commit()

    def listar_trabalhos(self, finalizado):
        c = self.conn.cursor()
        c.execute(
            "SELECT id, nome, criado_em, finalizado_em FROM trabalhos "
            "WHERE finalizado = ? ORDER BY criado_em DESC",
            (1 if finalizado else 0,),
        )
        return c.fetchall()

    def get_trabalho(self, trabalho_id):
        c = self.conn.cursor()
        c.execute(
            "SELECT id, nome, criado_em, finalizado, finalizado_em FROM trabalhos WHERE id = ?",
            (trabalho_id,),
        )
        return c.fetchone()

    def finalizar_trabalho(self, trabalho_id):
        c = self.conn.cursor()
        c.execute(
            "UPDATE trabalhos SET finalizado = 1, finalizado_em = ? WHERE id = ?",
            (date.today().isoformat(), trabalho_id),
        )
        self.conn.commit()

    def excluir_trabalho(self, trabalho_id):
        c = self.conn.cursor()
        c.execute("DELETE FROM trabalhos WHERE id = ?", (trabalho_id,))
        self.conn.commit()

    # ---- dias trabalhados ----
    def adicionar_dia(self, trabalho_id, data_iso, valor):
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO dias_trabalhados (trabalho_id, data, valor) VALUES (?, ?, ?)",
            (trabalho_id, data_iso, valor),
        )
        self.conn.commit()

    def listar_dias(self, trabalho_id):
        c = self.conn.cursor()
        c.execute(
            "SELECT id, data, valor FROM dias_trabalhados "
            "WHERE trabalho_id = ? ORDER BY data ASC",
            (trabalho_id,),
        )
        return c.fetchall()

    def remover_dia(self, dia_id):
        c = self.conn.cursor()
        c.execute("DELETE FROM dias_trabalhados WHERE id = ?", (dia_id,))
        self.conn.commit()

    def total_trabalho(self, trabalho_id):
        c = self.conn.cursor()
        c.execute(
            "SELECT COALESCE(SUM(valor), 0) FROM dias_trabalhados WHERE trabalho_id = ?",
            (trabalho_id,),
        )
        return c.fetchone()[0]

    def total_recebido(self):
        """Soma de todos os dias de trabalhos já FINALIZADOS (dinheiro recebido de fato)."""
        c = self.conn.cursor()
        c.execute("""
            SELECT COALESCE(SUM(d.valor), 0)
            FROM dias_trabalhados d
            JOIN trabalhos t ON t.id = d.trabalho_id
            WHERE t.finalizado = 1
        """)
        return c.fetchone()[0]

    def total_a_receber(self):
        """Soma dos trabalhos em andamento (ainda não finalizados)."""
        c = self.conn.cursor()
        c.execute("""
            SELECT COALESCE(SUM(d.valor), 0)
            FROM dias_trabalhados d
            JOIN trabalhos t ON t.id = d.trabalho_id
            WHERE t.finalizado = 0
        """)
        return c.fetchone()[0]


# ---------------------------------------------------------------------------
# calendário clicável
# ---------------------------------------------------------------------------
class CalendarioPopup(tk.Toplevel):
    DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

    def __init__(self, parent, ao_escolher):
        super().__init__(parent)
        self.title("Selecionar data")
        self.configure(bg=COR_CARD)
        self.resizable(False, False)
        self.ao_escolher = ao_escolher
        hoje = date.today()
        self.ano = hoje.year
        self.mes = hoje.month
        self.transient(parent)
        self.grab_set()
        self._montar()
        self.update_idletasks()
        x = parent.winfo_rootx() + 60
        y = parent.winfo_rooty() + 60
        self.geometry(f"+{x}+{y}")

    def _montar(self):
        for w in self.winfo_children():
            w.destroy()

        header = tk.Frame(self, bg=COR_CARD)
        header.pack(fill="x", padx=10, pady=(10, 4))
        tk.Button(header, text="◀", width=3, relief="flat",
                  command=self._mes_anterior).pack(side="left")
        nome_mes = calendar.month_name[self.mes].capitalize()
        tk.Label(header, text=f"{nome_mes} {self.ano}", bg=COR_CARD,
                  font=FONTE_SUBTITULO, fg=COR_TEXTO).pack(side="left", expand=True)
        tk.Button(header, text="▶", width=3, relief="flat",
                  command=self._mes_proximo).pack(side="right")

        grade = tk.Frame(self, bg=COR_CARD)
        grade.pack(padx=10, pady=(0, 10))

        for col, nome in enumerate(self.DIAS_SEMANA):
            tk.Label(grade, text=nome, width=4, bg=COR_CARD,
                      fg=COR_SIDEBAR_TEXTO_SEC, font=("Segoe UI", 9, "bold")).grid(
                row=0, column=col, pady=(0, 4))

        cal = calendar.Calendar(firstweekday=0)
        semanas = cal.monthdayscalendar(self.ano, self.mes)
        hoje = date.today()
        for linha, semana in enumerate(semanas, start=1):
            for col, dia in enumerate(semana):
                if dia == 0:
                    tk.Label(grade, text="", width=4, bg=COR_CARD).grid(
                        row=linha, column=col, pady=2, padx=2)
                else:
                    eh_hoje = (dia == hoje.day and self.mes == hoje.month and self.ano == hoje.year)
                    btn = tk.Button(
                        grade, text=str(dia), width=4,
                        relief="flat",
                        bg=COR_ACCENT if eh_hoje else COR_FUNDO,
                        fg="white" if eh_hoje else COR_TEXTO,
                        activebackground=COR_ACCENT, activeforeground="white",
                        command=lambda d=dia: self._escolher(d),
                    )
                    btn.grid(row=linha, column=col, pady=2, padx=2)

    def _mes_anterior(self):
        self.mes -= 1
        if self.mes == 0:
            self.mes = 12
            self.ano -= 1
        self._montar()

    def _mes_proximo(self):
        self.mes += 1
        if self.mes == 13:
            self.mes = 1
            self.ano += 1
        self._montar()

    def _escolher(self, dia):
        data_escolhida = date(self.ano, self.mes, dia)
        self.destroy()
        self.ao_escolher(data_escolhida)


# ---------------------------------------------------------------------------
# Aplicativo principal
# ---------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Work Manager")
        self.geometry("1000x640")
        self.minsize(860, 560)
        self.configure(bg=COR_FUNDO)

        self.db = Banco(DB_PATH)
        self._foto_tk = None  # referência viva da imagem

        self._montar_layout_base()
        self.atualizar_sidebar()
        self.mostrar_dashboard()

    # ------------------------------------------------------------------
    # Layout base: barra de topo (com foto) + sidebar + área de conteúdo
    # ------------------------------------------------------------------
    def _montar_layout_base(self):
        # --- barra de topo ---
        topo = tk.Frame(self, bg=COR_CARD, height=110)
        topo.pack(side="top", fill="x")
        topo.pack_propagate(False)

        tk.Label(topo, text="Work Manager", bg=COR_CARD, fg=COR_TEXTO,
                  font=FONTE_TITULO).pack(side="left", padx=20)

        self.foto_label = tk.Label(topo, bg=COR_CARD, cursor="hand2")
        self.foto_label.pack(side="right", padx=20, pady=10)
        self.foto_label.bind("<Button-1>", lambda e: self.trocar_foto())
        self.foto_label.bind("<Button-3>", lambda e: self.ajustar_foto())
        self._carregar_foto()

        # --- corpo: sidebar + conteúdo ---
        corpo = tk.Frame(self, bg=COR_FUNDO)
        corpo.pack(side="top", fill="both", expand=True)

        self.sidebar = tk.Frame(corpo, bg=COR_SIDEBAR, width=230)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        container_conteudo = tk.Frame(corpo, bg=COR_FUNDO)
        container_conteudo.pack(side="left", fill="both", expand=True)

        # canvas com scrollbar para o conteúdo
        self.canvas = tk.Canvas(container_conteudo, bg=COR_FUNDO, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container_conteudo, orient="vertical", command=self.canvas.yview)
        self.conteudo = tk.Frame(self.canvas, bg=COR_FUNDO)
        self.conteudo.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.conteudo, anchor="nw", width=730)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _limpar_conteudo(self):
        for w in self.conteudo.winfo_children():
            w.destroy()
        self.canvas.yview_moveto(0)

    # ------------------------------------------------------------------
    # Foto de perfil (canto superior direito)
    # ------------------------------------------------------------------
    def _carregar_foto(self):
        caminho = self.db.get_config("foto_path")
        tamanho = 90
        if caminho and os.path.exists(caminho) and PIL_DISPONIVEL:
            try:
                img = Image.open(caminho).convert("RGB")
                largura, altura = img.size
                lado_base = min(largura, altura)

                zoom = float(self.db.get_config("foto_zoom", "1.0"))
                offset_x = float(self.db.get_config("foto_offset_x", "0"))
                offset_y = float(self.db.get_config("foto_offset_y", "0"))

                lado = max(1, int(lado_base / zoom))
                max_x = (largura - lado) / 2
                max_y = (altura - lado) / 2
                centro_x = largura / 2 + offset_x * max_x
                centro_y = altura / 2 + offset_y * max_y
                esquerda = int(max(0, min(centro_x - lado / 2, largura - lado)))
                topo_corte = int(max(0, min(centro_y - lado / 2, altura - lado)))

                img = img.crop((esquerda, topo_corte, esquerda + lado, topo_corte + lado))
                img = img.resize((tamanho, tamanho), Image.LANCZOS)
                self._foto_tk = ImageTk.PhotoImage(img)
                self.foto_label.configure(image=self._foto_tk, text="")
                return
            except Exception:
                pass
        # placeholder (sem foto ou sem Pillow instalado)
        self.foto_label.configure(
            image="", text="📷\nFoto", font=("Segoe UI", 9), fg=COR_SIDEBAR_TEXTO_SEC,
            width=9, height=5, bg="#e5e7eb"
        )

    def trocar_foto(self):
        if not PIL_DISPONIVEL:
            messagebox.showinfo(
                "Pillow necessário",
                "Para usar uma foto de perfil, instale a biblioteca Pillow:\n\n"
                "pip install Pillow\n\ne reabra o programa."
            )
            return
        caminho = filedialog.askopenfilename(
            title="Escolha sua foto",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.gif *.bmp")],
        )
        if caminho:
            self.db.set_config("foto_path", caminho)
            self._carregar_foto()

    def ajustar_foto(self):
        caminho = self.db.get_config("foto_path")
        if not caminho or not os.path.exists(caminho):
            messagebox.showinfo("Sem foto", "Adicione uma foto primeiro (clique na foto).")
            return
        if not PIL_DISPONIVEL:
            messagebox.showinfo(
                "Pillow necessário",
                "Para ajustar a posição da foto, instale a biblioteca Pillow:\n\n"
                "pip install Pillow\n\ne reabra o programa."
            )
            return

        janela = tk.Toplevel(self)
        janela.title("Ajustar posição da foto")
        janela.configure(bg=COR_CARD)
        janela.resizable(False, False)
        janela.transient(self)
        janela.grab_set()

        preview_label = tk.Label(janela, bg=COR_CARD)
        preview_label.pack(padx=16, pady=16)

        def atualizar_preview(_=None):
            zoom = zoom_var.get()
            offset_x = offset_x_var.get()
            offset_y = offset_y_var.get()
            img = Image.open(caminho).convert("RGB")
            largura, altura = img.size
            lado_base = min(largura, altura)
            lado = max(1, int(lado_base / zoom))
            max_x = (largura - lado) / 2
            max_y = (altura - lado) / 2
            centro_x = largura / 2 + offset_x * max_x
            centro_y = altura / 2 + offset_y * max_y
            esquerda = int(max(0, min(centro_x - lado / 2, largura - lado)))
            topo_corte = int(max(0, min(centro_y - lado / 2, altura - lado)))
            recorte = img.crop((esquerda, topo_corte, esquerda + lado, topo_corte + lado))
            recorte = recorte.resize((160, 160), Image.LANCZOS)
            janela._preview_tk = ImageTk.PhotoImage(recorte)
            preview_label.configure(image=janela._preview_tk)

        zoom_var = tk.DoubleVar(value=float(self.db.get_config("foto_zoom", "1.0")))
        offset_x_var = tk.DoubleVar(value=float(self.db.get_config("foto_offset_x", "0")))
        offset_y_var = tk.DoubleVar(value=float(self.db.get_config("foto_offset_y", "0")))

        tk.Label(janela, text="Zoom", bg=COR_CARD, fg=COR_TEXTO).pack()
        tk.Scale(janela, from_=1.0, to=3.0, resolution=0.05, orient="horizontal",
                  variable=zoom_var, command=atualizar_preview, bg=COR_CARD,
                  length=220).pack(padx=16)

        tk.Label(janela, text="Posição horizontal", bg=COR_CARD, fg=COR_TEXTO).pack()
        tk.Scale(janela, from_=-1.0, to=1.0, resolution=0.05, orient="horizontal",
                  variable=offset_x_var, command=atualizar_preview, bg=COR_CARD,
                  length=220).pack(padx=16)

        tk.Label(janela, text="Posição vertical", bg=COR_CARD, fg=COR_TEXTO).pack()
        tk.Scale(janela, from_=-1.0, to=1.0, resolution=0.05, orient="horizontal",
                  variable=offset_y_var, command=atualizar_preview, bg=COR_CARD,
                  length=220).pack(padx=16)

        def salvar():
            self.db.set_config("foto_zoom", zoom_var.get())
            self.db.set_config("foto_offset_x", offset_x_var.get())
            self.db.set_config("foto_offset_y", offset_y_var.get())
            self._carregar_foto()
            janela.destroy()

        tk.Button(janela, text="Salvar posição", bg=COR_ACCENT, fg="white", relief="flat",
                   font=("Segoe UI", 10, "bold"), padx=12, pady=6, command=salvar).pack(pady=16)

        atualizar_preview()

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    def atualizar_sidebar(self):
        for w in self.sidebar.winfo_children():
            w.destroy()

        # --- aba com nome editável (clicável) ---
        nome_perfil = self.db.get_config("nome_perfil", "Meu Espaço")
        bloco_nome = tk.Frame(self.sidebar, bg=COR_SIDEBAR)
        bloco_nome.pack(fill="x", pady=(18, 6), padx=14)

        nome_btn = tk.Label(
            bloco_nome, text=nome_perfil, bg=COR_SIDEBAR, fg="white",
            font=("Segoe UI", 13, "bold"), cursor="hand2", anchor="w", wraplength=150,
        )
        nome_btn.pack(side="left", fill="x", expand=True)
        nome_btn.bind("<Button-1>", lambda e: self.mostrar_dashboard())

        editar_btn = tk.Label(bloco_nome, text="✏️", bg=COR_SIDEBAR, cursor="hand2")
        editar_btn.pack(side="right")
        editar_btn.bind("<Button-1>", lambda e: self.renomear_perfil())

        self._separador_sidebar()

        # --- seção Trabalhos ---
        self._botao_sidebar("📁  Trabalhos", self.mostrar_trabalhos, destaque=True)

        trabalhos_ativos = self.db.listar_trabalhos(finalizado=False)
        for tid, nome, criado_em, _ in trabalhos_ativos:
            self._botao_sidebar(f"   • {nome}", lambda t=tid: self.mostrar_detalhe_trabalho(t))

        self._botao_sidebar("   + Novo trabalho", self.criar_novo_trabalho, cor_texto=COR_ACCENT)

        self._separador_sidebar()

        # --- outras seções ---
        self._botao_sidebar("💰  Diárias", self.mostrar_diarias, destaque=True)
        self._botao_sidebar("✅  Trabalhos Finalizados", self.mostrar_finalizados, destaque=True)

    def _separador_sidebar(self):
        tk.Frame(self.sidebar, bg=COR_SIDEBAR_HOVER, height=1).pack(fill="x", padx=14, pady=10)

    def _botao_sidebar(self, texto, comando, destaque=False, cor_texto=None):
        fg = cor_texto or (COR_SIDEBAR_TEXTO if destaque else COR_SIDEBAR_TEXTO_SEC)
        fonte = ("Segoe UI", 11, "bold") if destaque else ("Segoe UI", 10)
        lbl = tk.Label(self.sidebar, text=texto, bg=COR_SIDEBAR, fg=fg, font=fonte,
                        anchor="w", cursor="hand2")
        lbl.pack(fill="x", padx=14, pady=4)
        lbl.bind("<Button-1>", lambda e: comando())
        lbl.bind("<Enter>", lambda e: lbl.configure(bg=COR_SIDEBAR_HOVER))
        lbl.bind("<Leave>", lambda e: lbl.configure(bg=COR_SIDEBAR))
        return lbl

    def renomear_perfil(self):
        atual = self.db.get_config("nome_perfil", "Meu Espaço")
        novo = simpledialog.askstring("Renomear", "Novo nome:", initialvalue=atual, parent=self)
        if novo:
            self.db.set_config("nome_perfil", novo.strip())
            self.atualizar_sidebar()
            self.mostrar_dashboard()

    # ------------------------------------------------------------------
    # Helpers visuais para as telas
    # ------------------------------------------------------------------
    def _titulo_tela(self, texto):
        tk.Label(self.conteudo, text=texto, bg=COR_FUNDO, fg=COR_TEXTO,
                  font=FONTE_TITULO).pack(anchor="w", padx=24, pady=(24, 16))

    def _card(self, parent=None):
        c = tk.Frame(parent or self.conteudo, bg=COR_CARD, highlightbackground="#e5e7eb",
                      highlightthickness=1)
        return c

    # ------------------------------------------------------------------
    # Tela: Dashboard (a "aba" com nome editável)
    # ------------------------------------------------------------------
    def mostrar_dashboard(self):
        self._limpar_conteudo()
        nome_perfil = self.db.get_config("nome_perfil", "Meu Espaço")
        self._titulo_tela(f"Olá, {nome_perfil} 👋")

        linha_cards = tk.Frame(self.conteudo, bg=COR_FUNDO)
        linha_cards.pack(fill="x", padx=24)

        def card_valor(titulo, valor, cor):
            c = self._card(linha_cards)
            c.pack(side="left", fill="both", expand=True, padx=(0, 16), ipady=14)
            tk.Label(c, text=titulo, bg=COR_CARD, fg=COR_SIDEBAR_TEXTO_SEC,
                      font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=(10, 2))
            tk.Label(c, text=formatar_moeda(valor), bg=COR_CARD, fg=cor,
                      font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=16)

        card_valor("Total recebido", self.db.total_recebido(), COR_VERDE)
        card_valor("A receber", self.db.total_a_receber(), COR_ACCENT)

        resumo = self._card()
        resumo.pack(fill="x", padx=24, pady=24)
        ativos = len(self.db.listar_trabalhos(finalizado=False))
        finalizados = len(self.db.listar_trabalhos(finalizado=True))
        tk.Label(resumo, text="Resumo", bg=COR_CARD, font=FONTE_SUBTITULO,
                  fg=COR_TEXTO).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(resumo, text=f"• {ativos} trabalho(s) em andamento",
                  bg=COR_CARD, fg=COR_TEXTO, font=FONTE_PADRAO).pack(anchor="w", padx=16, pady=2)
        tk.Label(resumo, text=f"• {finalizados} trabalho(s) finalizado(s)",
                  bg=COR_CARD, fg=COR_TEXTO, font=FONTE_PADRAO).pack(anchor="w", padx=16, pady=(2, 14))

        diaria = self.db.get_config("diaria_padrao")
        if diaria:
            tk.Label(self.conteudo,
                      text=f"Valor padrão da diária atual: {formatar_moeda(float(diaria))}",
                      bg=COR_FUNDO, fg=COR_SIDEBAR_TEXTO_SEC, font=FONTE_PADRAO).pack(
                anchor="w", padx=24)
        else:
            tk.Label(self.conteudo,
                      text="Você ainda não configurou sua diária padrão. Vá em 'Diárias' no menu.",
                      bg=COR_FUNDO, fg=COR_VERMELHO, font=FONTE_PADRAO).pack(anchor="w", padx=24)

    # ------------------------------------------------------------------
    # Tela: Trabalhos (lista dos trabalhos em andamento)
    # ------------------------------------------------------------------
    def mostrar_trabalhos(self):
        self._limpar_conteudo()
        self._titulo_tela("Trabalhos em Andamento")

        tk.Button(self.conteudo, text="+ Novo Trabalho", bg=COR_ACCENT, fg="white",
                   relief="flat", font=("Segoe UI", 10, "bold"), padx=14, pady=6,
                   command=self.criar_novo_trabalho).pack(anchor="w", padx=24, pady=(0, 16))

        trabalhos = self.db.listar_trabalhos(finalizado=False)
        if not trabalhos:
            tk.Label(self.conteudo, text="Nenhum trabalho ainda.",
                      bg=COR_FUNDO, fg=COR_SIDEBAR_TEXTO_SEC, font=FONTE_PADRAO).pack(
                anchor="w", padx=24)
            return

        for tid, nome, criado_em, _ in trabalhos:
            total = self.db.total_trabalho(tid)
            linha = self._card()
            linha.pack(fill="x", padx=24, pady=6)
            info = tk.Frame(linha, bg=COR_CARD)
            info.pack(side="left", fill="both", expand=True, padx=16, pady=12)
            tk.Label(info, text=nome, bg=COR_CARD, font=("Segoe UI", 12, "bold"),
                      fg=COR_TEXTO).pack(anchor="w")
            tk.Label(info, text=f"Criado em {formatar_data_br(criado_em)}",
                      bg=COR_CARD, fg=COR_SIDEBAR_TEXTO_SEC, font=("Segoe UI", 9)).pack(anchor="w")
            tk.Label(linha, text=formatar_moeda(total), bg=COR_CARD, fg=COR_VERDE,
                      font=("Segoe UI", 13, "bold")).pack(side="left", padx=16)
            tk.Button(linha, text="Abrir ▸", relief="flat", bg=COR_CARD, fg=COR_ACCENT,
                       cursor="hand2", command=lambda t=tid: self.mostrar_detalhe_trabalho(t)
                       ).pack(side="right", padx=16)

    def criar_novo_trabalho(self):
        nome = simpledialog.askstring("Novo trabalho", "Nome do trabalho:", parent=self)
        if nome and nome.strip():
            novo_id = self.db.criar_trabalho(nome.strip())
            self.atualizar_sidebar()
            self.mostrar_detalhe_trabalho(novo_id)

    # ------------------------------------------------------------------
    # Tela: Detalhe de um trabalho específico
    # ------------------------------------------------------------------
    def mostrar_detalhe_trabalho(self, trabalho_id):
        self._limpar_conteudo()
        trabalho = self.db.get_trabalho(trabalho_id)
        if not trabalho:
            self.mostrar_trabalhos()
            return
        tid, nome, criado_em, finalizado, finalizado_em = trabalho

        topo = tk.Frame(self.conteudo, bg=COR_FUNDO)
        topo.pack(fill="x", padx=24, pady=(24, 4))
        tk.Label(topo, text=nome, bg=COR_FUNDO, fg=COR_TEXTO, font=FONTE_TITULO).pack(side="left")
        tk.Button(topo, text="✏️ Renomear", relief="flat", bg=COR_FUNDO, fg=COR_ACCENT,
                   cursor="hand2",
                   command=lambda: self._renomear_trabalho_atual(trabalho_id)).pack(
            side="left", padx=12)

        tk.Label(self.conteudo, text=f"Criado em {formatar_data_br(criado_em)}"
                  + (f" • Finalizado em {formatar_data_br(finalizado_em)}" if finalizado else ""),
                  bg=COR_FUNDO, fg=COR_SIDEBAR_TEXTO_SEC, font=FONTE_PADRAO).pack(
            anchor="w", padx=24, pady=(0, 16))

        if not finalizado:
            barra = tk.Frame(self.conteudo, bg=COR_FUNDO)
            barra.pack(fill="x", padx=24, pady=(0, 12))
            tk.Button(barra, text="📅 + Adicionar Dia Trabalhado", bg=COR_ACCENT, fg="white",
                       relief="flat", font=("Segoe UI", 10, "bold"), padx=12, pady=6,
                       command=lambda: self._adicionar_dia(trabalho_id)).pack(side="left")

        # tabela de dias
        card_tabela = self._card()
        card_tabela.pack(fill="x", padx=24, pady=6)

        colunas = ("data", "valor")
        tree = ttk.Treeview(card_tabela, columns=colunas, show="headings", height=8)
        tree.heading("data", text="Data")
        tree.heading("valor", text="Valor recebido no dia")
        tree.column("data", width=140, anchor="center")
        tree.column("valor", width=200, anchor="center")
        tree.pack(fill="x", padx=12, pady=12)

        dias = self.db.listar_dias(trabalho_id)
        for dia_id, data_iso, valor in dias:
            tree.insert("", "end", iid=str(dia_id),
                        values=(formatar_data_br(data_iso), formatar_moeda(valor)))

        if not finalizado and dias:
            tk.Button(self.conteudo, text="🗑 Remover dia selecionado", relief="flat",
                       bg=COR_FUNDO, fg=COR_VERMELHO, cursor="hand2",
                       command=lambda: self._remover_dia(trabalho_id, tree)).pack(
                anchor="w", padx=24, pady=(0, 16))

        total = self.db.total_trabalho(trabalho_id)
        tk.Label(self.conteudo, text=f"Valor total a receber: {formatar_moeda(total)}",
                  bg=COR_FUNDO, fg=COR_VERDE, font=("Segoe UI", 15, "bold")).pack(
            anchor="w", padx=24, pady=(8, 20))

        if not finalizado:
            tk.Button(self.conteudo, text="✅ Finalizar", bg=COR_VERDE, fg="white",
                       relief="flat", font=("Segoe UI", 11, "bold"), padx=16, pady=8,
                       command=lambda: self._finalizar_trabalho(trabalho_id)).pack(
                anchor="w", padx=24, pady=(0, 24))
        else:
            tk.Label(self.conteudo, text="Este trabalho já foi finalizado e está em "
                      "'Trabalhos Finalizados'.", bg=COR_FUNDO, fg=COR_SIDEBAR_TEXTO_SEC,
                      font=FONTE_PADRAO).pack(anchor="w", padx=24, pady=(0, 24))

    def _renomear_trabalho_atual(self, trabalho_id):
        trabalho = self.db.get_trabalho(trabalho_id)
        novo = simpledialog.askstring("Renomear trabalho", "Novo nome:",
                                       initialvalue=trabalho[1], parent=self)
        if novo and novo.strip():
            self.db.renomear_trabalho(trabalho_id, novo.strip())
            self.atualizar_sidebar()
            self.mostrar_detalhe_trabalho(trabalho_id)

    def _adicionar_dia(self, trabalho_id):
        def ao_escolher_data(data_escolhida):
            diaria_padrao_str = self.db.get_config("diaria_padrao", "0")
            try:
                diaria_padrao = float(diaria_padrao_str)
            except ValueError:
                diaria_padrao = 0.0
            valor = simpledialog.askfloat(
                "Valor do dia",
                f"Quanto você recebeu em {data_escolhida.strftime('%d/%m/%Y')}?\n"
                "(use ponto para casas decimais, ex: 150.00)",
                initialvalue=diaria_padrao, minvalue=0, parent=self,
            )
            if valor is not None:
                self.db.adicionar_dia(trabalho_id, data_escolhida.isoformat(), valor)
                self.mostrar_detalhe_trabalho(trabalho_id)

        CalendarioPopup(self, ao_escolher_data)

    def _remover_dia(self, trabalho_id, tree):
        selecionado = tree.selection()
        if not selecionado:
            messagebox.showinfo("Selecione um dia", "Clique em um dia da tabela para remover.")
            return
        dia_id = int(selecionado[0])
        if messagebox.askyesno("Confirmar", "Remover este dia trabalhado?"):
            self.db.remover_dia(dia_id)
            self.mostrar_detalhe_trabalho(trabalho_id)

    def _finalizar_trabalho(self, trabalho_id):
        total = self.db.total_trabalho(trabalho_id)
        if messagebox.askyesno(
            "Finalizar",
            f"Confirmar recebimento total de {formatar_moeda(total)} e mover este "
            "trabalho para 'Trabalhos Finalizados'?"
        ):
            self.db.finalizar_trabalho(trabalho_id)
            self.atualizar_sidebar()
            self.mostrar_finalizados()

    # ------------------------------------------------------------------
    # Tela: Diárias
    # ------------------------------------------------------------------
    def mostrar_diarias(self):
        self._limpar_conteudo()
        self._titulo_tela("Diárias")

        card = self._card()
        card.pack(fill="x", padx=24, pady=6)

        diaria_atual = self.db.get_config("diaria_padrao")
        valor_atual_txt = formatar_moeda(float(diaria_atual)) if diaria_atual else "não definida"
        tk.Label(card, text="Valor padrão atual:", bg=COR_CARD, fg=COR_SIDEBAR_TEXTO_SEC,
                  font=FONTE_PADRAO).pack(anchor="w", padx=16, pady=(16, 0))
        tk.Label(card, text=valor_atual_txt, bg=COR_CARD, fg=COR_VERDE,
                  font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=16, pady=(0, 16))

        linha_edicao = tk.Frame(card, bg=COR_CARD)
        linha_edicao.pack(fill="x", padx=16, pady=(0, 16))
        tk.Label(linha_edicao, text="Novo valor padrão (R$):", bg=COR_CARD,
                  fg=COR_TEXTO, font=FONTE_PADRAO).pack(side="left")
        entrada = tk.Entry(linha_edicao, font=FONTE_PADRAO, width=12)
        entrada.pack(side="left", padx=8)

        def salvar():
            texto = entrada.get().strip().replace(",", ".")
            try:
                valor = float(texto)
                if valor < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Valor inválido", "Digite um número válido, ex: 150.00")
                return
            self.db.set_config("diaria_padrao", valor)
            self.mostrar_diarias()

        tk.Button(linha_edicao, text="Atualizar", bg=COR_ACCENT, fg="white", relief="flat",
                   font=("Segoe UI", 10, "bold"), padx=12, pady=4, command=salvar).pack(
            side="left", padx=8)

        tk.Label(self.conteudo,
                  text=("Esse valor é sugerido automaticamente sempre que você adicionar um novo\n"
                        "dia trabalhado em qualquer trabalho, mas pode ser alterado individualmente\n"
                        "em cada dia (caso receba mais ou menos naquele dia específico)."),
                  bg=COR_FUNDO, fg=COR_SIDEBAR_TEXTO_SEC, font=("Segoe UI", 9),
                  justify="left").pack(anchor="w", padx=24, pady=16)

    # ------------------------------------------------------------------
    # Tela: Trabalhos Finalizados / Histórico
    # ------------------------------------------------------------------
    def mostrar_finalizados(self):
        self._limpar_conteudo()
        self._titulo_tela("Trabalhos Finalizados")

        tk.Label(self.conteudo, text=f"Total recebido: {formatar_moeda(self.db.total_recebido())}",
                  bg=COR_FUNDO, fg=COR_VERDE, font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=24, pady=(0, 16))

        finalizados = self.db.listar_trabalhos(finalizado=True)
        if not finalizados:
            tk.Label(self.conteudo, text="Nenhum trabalho finalizado ainda.",
                      bg=COR_FUNDO, fg=COR_SIDEBAR_TEXTO_SEC, font=FONTE_PADRAO).pack(
                anchor="w", padx=24)
            return

        for tid, nome, criado_em, finalizado_em in finalizados:
            total = self.db.total_trabalho(tid)
            linha = self._card()
            linha.pack(fill="x", padx=24, pady=6)
            info = tk.Frame(linha, bg=COR_CARD)
            info.pack(side="left", fill="both", expand=True, padx=16, pady=12)
            tk.Label(info, text=nome, bg=COR_CARD, font=("Segoe UI", 12, "bold"),
                      fg=COR_TEXTO).pack(anchor="w")
            tk.Label(info, text=f"Finalizado em {formatar_data_br(finalizado_em)}",
                      bg=COR_CARD, fg=COR_SIDEBAR_TEXTO_SEC, font=("Segoe UI", 9)).pack(anchor="w")
            tk.Label(linha, text=formatar_moeda(total), bg=COR_CARD, fg=COR_VERDE,
                      font=("Segoe UI", 13, "bold")).pack(side="left", padx=16)
            tk.Button(linha, text="Ver histórico ▸", relief="flat", bg=COR_CARD, fg=COR_ACCENT,
                       cursor="hand2",
                       command=lambda t=tid, n=nome: self._ver_historico(t, n)).pack(
                side="right", padx=16)

    def _ver_historico(self, trabalho_id, nome):
        janela = tk.Toplevel(self)
        janela.title(f"Histórico — {nome}")
        janela.configure(bg=COR_CARD)
        janela.geometry("420x420")

        tk.Label(janela, text=nome, bg=COR_CARD, font=FONTE_SUBTITULO,
                  fg=COR_TEXTO).pack(anchor="w", padx=16, pady=(16, 8))

        colunas = ("data", "valor")
        tree = ttk.Treeview(janela, columns=colunas, show="headings", height=12)
        tree.heading("data", text="Dia trabalhado")
        tree.heading("valor", text="Valor recebido")
        tree.column("data", width=180, anchor="center")
        tree.column("valor", width=180, anchor="center")
        tree.pack(fill="both", expand=True, padx=16, pady=8)

        for _, data_iso, valor in self.db.listar_dias(trabalho_id):
            tree.insert("", "end", values=(formatar_data_br(data_iso), formatar_moeda(valor)))

        total = self.db.total_trabalho(trabalho_id)
        tk.Label(janela, text=f"Total recebido: {formatar_moeda(total)}", bg=COR_CARD,
                  fg=COR_VERDE, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(4, 16))


if __name__ == "__main__":
    app = App()
    app.mainloop()
