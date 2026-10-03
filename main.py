import tkinter as tk
from PIL import Image, ImageTk
import threading
import time
import random
import webbrowser
import subprocess
import pywhatkit
import os
import math
import wave
import cv2
import datetime
import numpy as np
import urllib.request
import psutil
import pygame
import speech_recognition as sr
import sys
from piper import PiperVoice

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision"))
import vision_state
from hand_tracking import iniciar_vision
import telefone
def responder_zion(texto):
    # Aqui você chama a função que o ZION já usa pra responder
    # Se já tiver uma função tipo processar_comando, usa ela
    return f"Recebi: {texto}" # o ZION do PC vai processar

telefone.set_zion_callback(responder_zion)
telefone.iniciar_em_thread()

VERMELHO = "#ff2020"
VERMELHO_NEON = "#ff3838"
VERMELHO_FORTE = "#ff4a4a"
VERMELHO_PARADO = "#c92828"
FUNDO = "#050505"
FUNDO_ESFERA = "#020202"
BRANCO = "#ffffff"
CINZA = "#888888"
CAMINHO_MODELO_VOZ = "pt_BR-cadu-medium.onnx"
ARQUIVO_AUDIO = "resposta_zion.wav"
CIDADE_TEMPERATURA = "Cajamar"

def obter_temperatura(cidade):
    try:
        url = f"http://wttr.in/{cidade}?format=%t&lang=pt"
        requisicao = urllib.request.Request(url, headers={"User-Agent": "curl"})
        with urllib.request.urlopen(requisicao, timeout=5) as resposta:
            texto = resposta.read().decode("utf-8").strip()
        texto = texto.replace("+", "").replace("°C", "").replace("°F", "").strip()
        return texto
    except Exception as erro:
        print("[ZION] Erro ao obter temperatura:", erro)
        return None


def obter_cpu_ram_disco():
    """
    Lê o uso atual de CPU, RAM e disco do sistema via psutil.
    Devolve (cpu, ram, disco) como floats (0-100), ou
    (None, None, None) se algo der errado.
    """
    try:
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        caminho_disco = "C:\\" if os.name == "nt" else "/"
        disco = psutil.disk_usage(caminho_disco).percent
        return cpu, ram, disco
    except Exception as erro:
        print("[ZION] Erro ao ler CPU/RAM/Disco:", erro)
        return None, None, None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROSTO_DIR = os.path.join(BASE_DIR, "rosto")
os.makedirs(ROSTO_DIR, exist_ok=True)

def achar_foto_dono():
    if not os.path.exists(ROSTO_DIR):
        return None
    for arquivo in os.listdir(ROSTO_DIR):
        nome = arquivo.lower()
        if "dono" in nome and (nome.endswith(".jpg") or nome.endswith(".jpeg") or nome.endswith(".png")):
            return os.path.join(ROSTO_DIR, arquivo)
    for arquivo in os.listdir(BASE_DIR):
        nome = arquivo.lower()
        if "dono" in nome and (nome.endswith(".jpg") or nome.endswith(".jpeg") or nome.endswith(".png")):
            return os.path.join(BASE_DIR, arquivo)
    return None

ROSTO_AUTORIZADO = achar_foto_dono()
if ROSTO_AUTORIZADO is None:
    ROSTO_AUTORIZADO = os.path.join(ROSTO_DIR, "dono.jpeg")

print(f"[ZION] Foto: {ROSTO_AUTORIZADO} | Existe? {os.path.exists(ROSTO_AUTORIZADO) if ROSTO_AUTORIZADO else False}")

sistema_bloqueado = True
tentativas_falhas = 0

try:
    detector_rosto = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    if detector_rosto.empty():
        detector_rosto = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml'))
except:
    detector_rosto = cv2.CascadeClassifier()

print(f"[ZION] Detector carregado? {not detector_rosto.empty()}")
reconhecedor_rosto = cv2.face.LBPHFaceRecognizer_create()

def treinar_rosto_dono():
    if not ROSTO_AUTORIZADO or not os.path.exists(ROSTO_AUTORIZADO):
        print("[ZION] ERRO: foto nao existe")
        return False
    img = cv2.imread(ROSTO_AUTORIZADO, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print("[ZION] ERRO: nao consegui ler imagem")
        return False
    faces = []
    if not detector_rosto.empty():
        try:
            rostos = detector_rosto.detectMultiScale(img, 1.1, 4)
            if len(rostos) > 0:
                for (x,y,w,h) in rostos:
                    faces.append(img[y:y+h, x:x+w])
                print(f"[ZION] Detector achou {len(rostos)} rosto(s)")
            else:
                print("[ZION] Detector nao achou rosto, usando imagem inteira")
                faces.append(img)
        except Exception as e:
            print(f"[ZION] Erro no detector: {e} - usando imagem inteira")
            faces.append(img)
    else:
        print("[ZION] Detector vazio, usando imagem inteira como treino")
        faces.append(img)
    if faces:
        reconhecedor_rosto.train(faces, np.array([0]*len(faces)))
        print(f"[ZION] Treinado com sucesso!")
        return True
    return False

ROSTO_TREINADO = treinar_rosto_dono()

def verificar_identidade():
    global ROSTO_TREINADO, camera_label_img
    if not ROSTO_AUTORIZADO or not os.path.exists(ROSTO_AUTORIZADO):
        return False, "Rosto nao encontrado senhor."
    if not ROSTO_TREINADO:
        ROSTO_TREINADO = treinar_rosto_dono()
        if not ROSTO_TREINADO:
            return False, "Nao consegui treinar seu rosto."
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return False, "Nao consegui abrir a camera."
    camera_label.place(relx=0.82, rely=0.25, anchor="center", width=320, height=240)
    atualizar_status("VERIFICANDO IDENTIDADE...", VERMELHO_NEON)
    mostrar_resposta("Posicione seu rosto na camera...")
    print("[ZION] Verificacao com camera interna iniciada...")
    inicio = time.time()
    encontrado = False
    melhor_confianca = 100
    while time.time() - inicio < 8:
        ret, frame = cap.read()
        if not ret:
            janela.update()
            continue
        h, w, _ = frame.shape
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        for i in range(0, w, 35):
            cv2.line(frame, (i,0), (i,h), (10, 40, 70), 1)
        for i in range(0, h, 35):
            cv2.line(frame, (0,i), (w,i), (10, 40, 70), 1)
        cv2.rectangle(frame, (w//2 - 100, h//2 - 130), (w//2 + 100, h//2 + 130), (0, 255, 255), 2)
        texto_status = "PROCURANDO..."
        cor_status = (0, 255, 255)
        try:
            if not detector_rosto.empty():
                rostos = detector_rosto.detectMultiScale(gray, 1.2, 5)
                for (x,y,rw,rh) in rostos:
                    cv2.rectangle(frame, (x,y), (x+rw, y+rh), (0,255,255), 2)
                    try:
                        id_, conf = reconhecedor_rosto.predict(gray[y:y+rh, x:x+rw])
                        melhor_confianca = conf
                        if conf < 75:
                            encontrado = True
                            texto_status = f"ACEITO {100-conf:.0f}%"
                            cor_status = (0, 255, 0)
                        else:
                            texto_status = f"NEGADO {conf:.0f}"
                            cor_status = (0, 0, 255)
                    except:
                        pass
            else:
                cx1, cy1 = w//2 - 100, h//2 - 130
                cx2, cy2 = w//2 + 100, h//2 + 130
                centro = gray[cy1:cy2, cx1:cx2]
                if centro.size > 0:
                    centro_r = cv2.resize(centro, (200, 250))
                    try:
                        id_, conf = reconhecedor_rosto.predict(centro_r)
                        melhor_confianca = conf
                        if conf < 95:
                            encontrado = True
                            texto_status = f"ACEITO {100-conf:.0f}%"
                            cor_status = (0, 255, 0)
                        else:
                            texto_status = f"ANALISANDO {conf:.0f}"
                            cor_status = (0, 255, 255)
                    except:
                        pass
        except Exception as e:
            print(f"[ZION] Erro: {e}")
        cv2.putText(frame, texto_status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, cor_status, 2)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_rgb = cv2.resize(frame_rgb, (320, 240))
        img_pil = Image.fromarray(frame_rgb)
        camera_label_img = ImageTk.PhotoImage(image=img_pil)
        camera_label.config(image=camera_label_img)
        janela.update()
        if encontrado:
            time.sleep(1)
            break
    cap.release()
    def esconder_camera():
        camera_label.place_forget()
    janela.after(2000, esconder_camera)
    if encontrado:
        return True, "Identidade confirmada."
    else:
        return False, "Identidade nao reconhecida. Tente com mais luz."

janela = tk.Tk()
janela.title("ZION")
janela.geometry("1100x700")
janela.minsize(850, 550)
janela.configure(bg=FUNDO)
janela.resizable(True, True)
pygame.mixer.init()
falando = False
escutando = False
print("[ZION] Carregando modelo de voz...")
try:
    voz = PiperVoice.load(CAMINHO_MODELO_VOZ)
    print("[ZION] Voz carregada.")
except Exception as e:
    print(f"[ZION] ERRO na voz: {e}")
    print("[ZION] Continuando SEM VOZ")
    voz = None

print("[ZION] Indo pra interface...")
laboratorio_ativo = False
objetos_lab = []
objeto_agarrado = None
objeto_hover = None
offset_x = 0
offset_y = 0
distancia_inicial = 1
tamanho_inicial = 1
distancia_objeto_filtrada = None
esfera_lab_x = 0
esfera_lab_y = 0
esfera_lab_tamanho = 0.13
esfera_agarrada = False
offset_esfera_x = 0
offset_esfera_y = 0
distancia_esfera_inicial = 1
tamanho_esfera_inicial = 0.13
distancia_esfera_filtrada = None
reconhecedor = sr.Recognizer()
reconhecedor.dynamic_energy_threshold = False
reconhecedor.energy_threshold = 50
reconhecedor.pause_threshold = 0.65
reconhecedor.non_speaking_duration = 0.30
reconhecedor.phrase_threshold = 0.05
microfone = sr.Microphone()

canvas = tk.Canvas(janela, bg=FUNDO, highlightthickness=0)
canvas.pack(fill="both", expand=True)

camera_label = tk.Label(janela, bg="#000000", bd=0, highlightthickness=2, highlightbackground=VERMELHO_NEON)
camera_label.place_forget()
camera_label_img = None

# ============================================================
# GRADE DE FUNDO
# ============================================================
def desenhar_grade_fundo():
    canvas.delete("grade_fundo")
    largura = canvas.winfo_width()
    altura = canvas.winfo_height()
    if largura < 100: largura = 1100
    if altura < 100: altura = 700
    COR = "#1f0f0f"
    for x in range(0, largura, 35):
        canvas.create_line(x, 0, x, altura, fill=COR, width=1, tags="grade_fundo")
    for y in range(0, altura, 35):
        canvas.create_line(0, y, largura, y, fill=COR, width=1, tags="grade_fundo")
    canvas.tag_lower("grade_fundo")


# ============================================================
# HUD NOS CANTOS (estilo mira tecnológica)
# ============================================================
def desenhar_hud_cantos():
    canvas.delete("hud_cantos")

    largura = canvas.winfo_width() or 1100
    altura = canvas.winfo_height() or 700

    tam = 28
    margem = 18
    cor = "#3a1414"

    cantos = [
        (margem, margem, 1, 1),
        (largura - margem, margem, -1, 1),
        (margem, altura - margem, 1, -1),
        (largura - margem, altura - margem, -1, -1),
    ]

    for x, y, sx, sy in cantos:
        canvas.create_line(x, y, x + tam * sx, y, fill=cor, width=2, tags="hud_cantos")
        canvas.create_line(x, y, x, y + tam * sy, fill=cor, width=2, tags="hud_cantos")

    canvas.tag_lower("hud_cantos")
    try:
        canvas.tag_raise("hud_cantos", "grade_fundo")
    except Exception:
        pass


# ============================================================
# PAINEL DE STATUS (canto superior esquerdo, estático)
# ============================================================
def desenhar_painel_status():
    canvas.delete("painel_status")

    largura = canvas.winfo_width() or 1100
    altura = canvas.winfo_height() or 700

    x = 125
    y = 70
    w, h = 210, 112

    canvas.create_rectangle(
        x - w // 2, y - h // 2, x + w // 2, y + h // 2,
        fill="#080000", outline=VERMELHO_NEON, width=2, tags="painel_status"
    )
    canvas.create_rectangle(
        x - w // 2, y - h // 2, x + w // 2, y - h // 2 + 14,
        fill=VERMELHO_NEON, outline="", tags="painel_status"
    )
    canvas.create_text(
        x - w // 2 + 8, y - h // 2 + 7,
        text="STATUS", fill="black", font=("Consolas", 7, "bold"),
        anchor="w", tags="painel_status"
    )

    linhas = [
        ("VISÃO", "ONLINE"),
        ("ÁUDIO", "CALIBRADO"),
        ("REDE", "SINCRONIZADA"),
        ("SEGURANÇA", "ATIVA"),
    ]

    y_linha = y - h // 2 + 28

    for label, valor in linhas:
        canvas.create_oval(
            x - w // 2 + 10, y_linha - 4, x - w // 2 + 18, y_linha + 4,
            fill="#00ff00", outline="",
            tags=("painel_status", "dot_pisca")
        )
        canvas.create_text(
            x - w // 2 + 24, y_linha,
            text=f"{label}: {valor}", fill="#dddddd",
            font=("Consolas", 8), anchor="w", tags="painel_status"
        )
        y_linha += 20

    # Cantinhos técnicos no painel
    for cx, cy, sx, sy in [
        (x - w // 2, y - h // 2, 1, 1),
        (x + w // 2, y - h // 2, -1, 1),
        (x - w // 2, y + h // 2, 1, -1),
        (x + w // 2, y + h // 2, -1, -1),
    ]:
        canvas.create_line(cx, cy, cx + 8 * sx, cy, fill=VERMELHO_NEON, width=1, tags="painel_status")
        canvas.create_line(cx, cy, cx, cy + 8 * sy, fill=VERMELHO_NEON, width=1, tags="painel_status")

    canvas.tag_raise("painel_status")


def _ao_redimensionar(evento):
    if not sistema_bloqueado:
        desenhar_grade_fundo()
        desenhar_hud_cantos()
        desenhar_painel_status()
canvas.bind("<Configure>", _ao_redimensionar)


# ============================================================
# INDICADORES PISCANDO (todos os pontos verdes dos cards)
# ============================================================
_pisca_estado = {"aceso": True}

def _piscar_indicadores():
    cor = "#00ff00" if _pisca_estado["aceso"] else "#0c3d0c"
    for item in canvas.find_withtag("dot_pisca"):
        try:
            canvas.itemconfig(item, fill=cor)
        except Exception:
            pass
    _pisca_estado["aceso"] = not _pisca_estado["aceso"]
    janela.after(600, _piscar_indicadores)


# ============================================================
# TICKER DESLIZANTE (rodapé, estilo telemetria)
# ============================================================
TICKER_FRASES = [
    "ZION CORE :: OPERACIONAL",
    "VISION MODULE :: STANDBY",
    "VOICE SYNTH :: PIPER TTS ONLINE",
    "SECURITY :: FACE ID ATIVO",
    "WEATHER LINK :: SINCRONIZADO",
]
_ticker_texto = "   •   ".join(TICKER_FRASES) + "   •   "
_ticker_estado = {"x": 0.0}

def _ticker_vivo():
    if not sistema_bloqueado and not laboratorio_ativo:

        largura = canvas.winfo_width() or 1100
        altura = canvas.winfo_height() or 700

        canvas.delete("ticker_sistema")

        _ticker_estado["x"] -= 1.3

        largura_estimada = len(_ticker_texto) * 7

        if _ticker_estado["x"] < -largura_estimada:
            _ticker_estado["x"] = largura

        canvas.create_text(
            _ticker_estado["x"], altura - 10,
            text=_ticker_texto,
            fill="#431414",
            font=("Consolas", 9),
            anchor="w",
            tags="ticker_sistema"
        )

        canvas.tag_lower("ticker_sistema")

        try:
            canvas.tag_raise("ticker_sistema", "grade_fundo")
        except Exception:
            pass

    else:
        canvas.delete("ticker_sistema")

    janela.after(40, _ticker_vivo)


# ============================================================
# CARDS ANIMADOS (duas colunas: direita e esquerda)
# ============================================================

POSICOES_WIDGETS_CANTO = {
    "hora": 110,
    "dia": 185,
    "temperatura": 260,
    "cpu": 220,
    "ram": 295,
    "disco": 370,
}

LADO_WIDGETS = {
    "hora": "direita",
    "dia": "direita",
    "temperatura": "direita",
    "cpu": "esquerda",
    "ram": "esquerda",
    "disco": "esquerda",
}


def _animar_quadradinho(tag, texto, pos_final_y, lado="direita", passos=22, intervalo_ms=14):
    largura = canvas.winfo_width()
    altura = canvas.winfo_height()
    if largura < 100: largura = 1100
    if altura < 100: altura = 700

    canvas.delete(tag)

    x_inicial = largura / 2
    y_inicial = altura / 2

    if lado == "esquerda":
        x_final = 125
    else:
        x_final = largura - 125

    y_final = pos_final_y

    partes = texto.split("\n")
    titulo = partes[0] if len(partes) > 0 else "INFO"
    valor = partes[1] if len(partes) > 1 else ""

    icones = {
        "HORA": "◷", "DIA": "▦", "TEMP.": "◉",
        "CPU": "▣", "RAM": "▤", "DISCO": "▥",
    }
    icone = icones.get(titulo, "◉")

    w, h = 210, 68

    # Fundo + borda
    canvas.create_rectangle(
        x_inicial - w // 2, y_inicial - h // 2, x_inicial + w // 2, y_inicial + h // 2,
        fill="#080000", outline=VERMELHO_NEON, width=2, tags=tag
    )
    canvas.create_rectangle(
        x_inicial - w // 2, y_inicial - h // 2, x_inicial + w // 2, y_inicial - h // 2 + 14,
        fill=VERMELHO_NEON, outline="", tags=tag
    )
    canvas.create_text(
        x_inicial - w // 2 + 8, y_inicial - h // 2 + 7,
        text=titulo, fill="black", font=("Consolas", 7, "bold"), anchor="w", tags=tag
    )

    # Indicador piscando (tag compartilhada "dot_pisca")
    canvas.create_text(
        x_inicial + w // 2 - 8, y_inicial - h // 2 + 7,
        text="●", fill="#00ff00", font=("Consolas", 8), anchor="e",
        tags=(tag, "dot_pisca")
    )

    # Ícone + valor
    canvas.create_text(
        x_inicial - w // 2 + 22, y_inicial + 8,
        text=icone, fill="#ff6600", font=("Consolas", 20), tags=(tag, f"{tag}_icon")
    )
    canvas.create_text(
        x_inicial - w // 2 + 48, y_inicial,
        text=valor, fill="#ffffff", font=("Consolas", 11, "bold"), anchor="w",
        tags=(tag, f"{tag}_valor")
    )
    canvas.create_text(
        x_inicial - w // 2 + 48, y_inicial + 16,
        text="ZION SYS", fill="#ffaa88", font=("Consolas", 7), anchor="w",
        tags=(tag, f"{tag}_sub")
    )

    # Cantinhos técnicos (deixa o card com cara de HUD)
    for cx, cy, sx, sy in [
        (x_inicial - w // 2, y_inicial - h // 2, 1, 1),
        (x_inicial + w // 2, y_inicial - h // 2, -1, 1),
        (x_inicial - w // 2, y_inicial + h // 2, 1, -1),
        (x_inicial + w // 2, y_inicial + h // 2, -1, -1),
    ]:
        canvas.create_line(cx, cy, cx + 7 * sx, cy, fill="#ffffff", width=1, tags=tag)
        canvas.create_line(cx, cy, cx, cy + 7 * sy, fill="#ffffff", width=1, tags=tag)

    canvas.tag_raise(tag)

    dx = (x_final - x_inicial) / passos
    dy = (y_final - y_inicial) / passos

    def passo(n=0):
        if sistema_bloqueado:
            canvas.delete(tag)
            return
        if n >= passos:
            return
        canvas.move(tag, dx, dy)
        janela.after(intervalo_ms, lambda: passo(n + 1))

    passo()


def _relogio_vivo():
    if not sistema_bloqueado:
        agora = datetime.datetime.now().strftime("%H:%M:%S")
        for item in canvas.find_withtag("widget_hora_valor"):
            if canvas.type(item) == "text":
                canvas.itemconfig(item, text=agora)
    janela.after(1000, _relogio_vivo)


def _sistema_vivo():
    if not sistema_bloqueado:

        cpu, ram, disco = obter_cpu_ram_disco()

        if cpu is not None:

            if not canvas.find_withtag("widget_cpu"):
                mostrar_widget_cpu(f"CPU\n{cpu:.0f}%")
            else:
                for item in canvas.find_withtag("widget_cpu_valor"):
                    canvas.itemconfig(item, text=f"{cpu:.0f}%")

            if not canvas.find_withtag("widget_ram"):
                mostrar_widget_ram(f"RAM\n{ram:.0f}%")
            else:
                for item in canvas.find_withtag("widget_ram_valor"):
                    canvas.itemconfig(item, text=f"{ram:.0f}%")

            if not canvas.find_withtag("widget_disco"):
                mostrar_widget_disco(f"DISCO\n{disco:.0f}%")
            else:
                for item in canvas.find_withtag("widget_disco_valor"):
                    canvas.itemconfig(item, text=f"{disco:.0f}%")

    janela.after(3000, _sistema_vivo)


def mostrar_widget_cpu(texto):
    janela.after(0, lambda: _animar_quadradinho("widget_cpu", texto, POSICOES_WIDGETS_CANTO["cpu"], LADO_WIDGETS["cpu"]))
def mostrar_widget_ram(texto):
    janela.after(0, lambda: _animar_quadradinho("widget_ram", texto, POSICOES_WIDGETS_CANTO["ram"], LADO_WIDGETS["ram"]))
def mostrar_widget_disco(texto):
    janela.after(0, lambda: _animar_quadradinho("widget_disco", texto, POSICOES_WIDGETS_CANTO["disco"], LADO_WIDGETS["disco"]))
def mostrar_widget_hora(texto):
    janela.after(0, lambda: _animar_quadradinho("widget_hora", texto, POSICOES_WIDGETS_CANTO["hora"], LADO_WIDGETS["hora"]))
def mostrar_widget_dia(texto):
    janela.after(0, lambda: _animar_quadradinho("widget_dia", texto, POSICOES_WIDGETS_CANTO["dia"], LADO_WIDGETS["dia"]))
def mostrar_widget_temperatura(texto):
    janela.after(0, lambda: _animar_quadradinho("widget_temperatura", texto, POSICOES_WIDGETS_CANTO["temperatura"], LADO_WIDGETS["temperatura"]))

# ============================================================
# ESFERA 3D
# ============================================================

pontos = []

NUM_PONTOS = 115

for i in range(NUM_PONTOS):

    y = 1 - (i / float(NUM_PONTOS - 1)) * 2

    raio = math.sqrt(
        max(0, 1 - y * y)
    )

    angulo = math.pi * (
        3 - math.sqrt(5)
    ) * i

    x = math.cos(angulo) * raio
    z = math.sin(angulo) * raio

    pontos.append({
        "x": x,
        "y": y,
        "z": z
    })

# ============================================================
# CONEXÕES
# ============================================================

conexoes = []

for i in range(NUM_PONTOS):

    distancias = []

    for j in range(NUM_PONTOS):

        if i == j:
            continue

        dx = pontos[i]["x"] - pontos[j]["x"]
        dy = pontos[i]["y"] - pontos[j]["y"]
        dz = pontos[i]["z"] - pontos[j]["z"]

        distancia = math.sqrt(
            dx * dx +
            dy * dy +
            dz * dz
        )

        distancias.append(
            (distancia, j)
        )

    distancias.sort()

    for _, j in distancias[:3]:

        par = tuple(
            sorted((i, j))
        )

        if par not in conexoes:
            conexoes.append(par)

rotacao = 0.0
rotacao_y = 0.0
scan_y = 0.0

# ============================================================
# DESENHAR ESFERA
# (protegida com try/finally: um erro em qualquer parte do
# desenho NUNCA mais vai matar o loop de animação)
# ============================================================

def desenhar_esfera():

    global rotacao
    global rotacao_y
    global scan_y

    try:

        canvas.delete("esfera")

        largura = canvas.winfo_width()
        altura = canvas.winfo_height()

        if largura < 100:
            largura = 1100

        if altura < 100:
            altura = 700

        # ====================================================
        # LINHA DE SCAN (interface desbloqueada, fora do lab)
        # ====================================================

        if not sistema_bloqueado and not laboratorio_ativo:

            canvas.delete("scan_linha")

            scan_y = (scan_y + 2.2) % altura

            canvas.create_line(
                0, scan_y, largura, scan_y,
                fill="#2a0a0a", width=1, tags="scan_linha"
            )

            try:
                canvas.tag_lower("scan_linha")
                canvas.tag_raise("scan_linha", "grade_fundo")
            except Exception:
                pass

        else:

            canvas.delete("scan_linha")

        # ====================================================
        # POSIÇÃO
        # ====================================================

        if laboratorio_ativo:

            centro_x = esfera_lab_x
            centro_y = esfera_lab_y

            raio_esfera = (
                min(largura, altura) * esfera_lab_tamanho
            )

        else:

            centro_x = largura / 2
            centro_y = altura / 2 - 20

            raio_esfera = min(largura, altura) * 0.275

        # ====================================================
        # ROTAÇÃO
        # ====================================================

        rotacao += 0.006
        rotacao_y += 0.002

        # ====================================================
        # PULSO
        # ====================================================

        if falando:

            pulso = 1 + math.sin(time.time() * 7.5) * 0.055
            brilho = True

        else:

            pulso = 1.0
            brilho = False

        raio_atual = raio_esfera * pulso

        # ====================================================
        # NÚCLEO
        # ====================================================

        nucleo_raio = raio_atual * 0.43

        canvas.create_oval(
            centro_x - nucleo_raio, centro_y - nucleo_raio,
            centro_x + nucleo_raio, centro_y + nucleo_raio,
            fill="#080303",
            outline="#541010" if brilho else "#3d0b0b",
            width=2 if brilho else 1,
            tags="esfera"
        )

        # ====================================================
        # ANÉIS GIRANDO (interface desbloqueada, fora do lab)
        # ====================================================

        if not sistema_bloqueado and not laboratorio_ativo:

            for raio_mult, vel, cor_anel in [
                (1.25, 0.03, "#5a1414"),
                (1.45, -0.02, "#3a0d0d"),
            ]:

                raio_anel = raio_atual * raio_mult
                inicio_angulo = (time.time() * vel * 180) % 360

                canvas.create_arc(
                    centro_x - raio_anel, centro_y - raio_anel,
                    centro_x + raio_anel, centro_y + raio_anel,
                    start=inicio_angulo, extent=70,
                    style="arc", outline=cor_anel, width=2,
                    tags="esfera"
                )

                canvas.create_arc(
                    centro_x - raio_anel, centro_y - raio_anel,
                    centro_x + raio_anel, centro_y + raio_anel,
                    start=inicio_angulo + 180, extent=70,
                    style="arc", outline=cor_anel, width=2,
                    tags="esfera"
                )

        # ====================================================
        # PROJEÇÃO
        # ====================================================

        pontos_projetados = []

        for p in pontos:

            x = p["x"]
            y = p["y"]
            z = p["z"]

            cos_r = math.cos(rotacao)
            sin_r = math.sin(rotacao)

            x2 = x * cos_r - z * sin_r
            z2 = x * sin_r + z * cos_r

            cos_y = math.cos(rotacao_y)
            sin_y = math.sin(rotacao_y)

            y2 = y * cos_y - z2 * sin_y
            z3 = y * sin_y + z2 * cos_y

            perspectiva = 1 / (1.8 - z3 * 0.55)

            px = centro_x + x2 * raio_atual * perspectiva
            py = centro_y + y2 * raio_atual * perspectiva

            tamanho = 2.4 * perspectiva

            pontos_projetados.append((px, py, z3, tamanho))

        # ====================================================
        # CONEXÕES
        # ====================================================

        for a, b in conexoes:

            x1, y1, z1, _ = pontos_projetados[a]
            x2, y2, z2, _ = pontos_projetados[b]

            profundidade = (z1 + z2) / 2

            if profundidade < -0.75:
                continue

            cor_linha = "#9d1515" if falando else "#641313"

            canvas.create_line(
                x1, y1, x2, y2,
                fill=cor_linha, width=1, tags="esfera"
            )

        # ====================================================
        # PARTÍCULAS
        # ====================================================

        for x, y, z, tamanho in pontos_projetados:

            if z < -0.65:
                continue

            if falando:

                brilho_ponto = 1 + math.sin(time.time() * 9 + z * 4) * 0.12
                tamanho_final = tamanho * brilho_ponto * 1.65
                cor = "#ff3b3b"

            else:

                tamanho_final = tamanho * 1.35
                cor = "#d52b2b"

            canvas.create_oval(
                x - tamanho_final, y - tamanho_final,
                x + tamanho_final, y + tamanho_final,
                fill=cor, outline="", tags="esfera"
            )

        # ====================================================
        # BRILHO
        # ====================================================

        if falando:

            brilho_raio = raio_atual * 0.16

            canvas.create_oval(
                centro_x - brilho_raio, centro_y - brilho_raio,
                centro_x + brilho_raio, centro_y + brilho_raio,
                fill="#160505", outline="", tags="esfera"
            )

        # ====================================================
        # NOME
        # ====================================================

        if laboratorio_ativo:

            canvas.create_text(
                centro_x, centro_y + raio_atual + 25,
                text="Z I O N", fill="#ed3a3a",
                font=("Arial", 11, "bold"), tags="esfera"
            )

        else:

            canvas.create_text(
                centro_x, centro_y + raio_atual + 55,
                text="Z I O N", fill="#ed3a3a",
                font=("Arial", 19, "bold"), tags="esfera"
            )

            canvas.create_text(
                centro_x, centro_y + raio_atual + 80,
                text="ARTIFICIAL INTELLIGENCE", fill="#686868",
                font=("Arial", 8), tags="esfera"
            )

    except Exception as erro:

        print("[ZION] Erro ao desenhar esfera:", erro)

    finally:

        # Isso roda SEMPRE, não importa se deu erro acima ou não,
        # garantindo que a esfera nunca mais pare de ser redesenhada.
        janela.after(30, desenhar_esfera)

# ============================================================
# STATUS
# ============================================================

status = tk.Label(
    janela,
    text="SISTEMA BLOQUEADO - AGUARDANDO AUTENTICACAO",
    font=("Arial", 11, "bold"),
    fg=VERMELHO_NEON,
    bg=FUNDO
)

status.place(
    relx=0.5,
    rely=0.045,
    anchor="center"
)

def atualizar_status(
    texto,
    cor=VERMELHO_NEON
):
    janela.after(0, lambda: status.config(text=texto, fg=cor))

# ============================================================
# RESPOSTA
# ============================================================

resposta_label = tk.Label(
    janela,
    text="",
    font=("Arial", 12),
    fg="#dddddd",
    bg=FUNDO,
    wraplength=700,
    justify="center"
)

resposta_label.place(
    relx=0.5,
    rely=0.82,
    anchor="center"
)

def mostrar_resposta(texto):
    def digitar(indice=0):
        resposta_label.config(text=texto[:indice])
        if indice < len(texto):
            janela.after(12, lambda: digitar(indice + 1))

    janela.after(0, digitar)

# ============================================================
# BOTÃO DE VOZ
# ============================================================

botao = tk.Button(
    janela,
    text="FALAR COM ZION",
    command=lambda:
        alternar_escuta(),
    font=("Arial", 11, "bold"),
    fg=BRANCO,
    bg="#151515",
    activeforeground=BRANCO,
    activebackground="#3a1010",
    relief="flat",
    bd=0,
    padx=25,
    pady=12,
    cursor="hand2"
)

botao.place(
    relx=0.5,
    rely=0.93,
    anchor="center"
)

# ============================================================
# BOTÃO PEQUENO DE SAIR DO LAB
# ============================================================

botao_sair_lab = tk.Button(
    janela,
    text="SAIR DO LAB",
    command=lambda:
        desativar_laboratorio(),
    font=("Arial", 8, "bold"),
    fg="#bbbbbb",
    bg="#120909",
    activeforeground=BRANCO,
    activebackground="#351010",
    relief="flat",
    bd=0,
    padx=9,
    pady=5,
    cursor="hand2"
)

botao_sair_lab.place_forget()

def atualizar_botao():
    def aplicar():
        if escutando:
            botao.config(text="OUVINDO...", bg="#401010")
        else:
            botao.config(text="FALAR COM ZION", bg="#151515")

    janela.after(0, aplicar)

# ============================================================
# PAINEL DO LABORATÓRIO
# ============================================================

def criar_painel_lab():

    canvas.delete("lab_interface")

    largura = canvas.winfo_width()
    altura = canvas.winfo_height()

    canvas.create_text(
        35, 35, text="ZION LAB", anchor="w",
        fill=VERMELHO_NEON, font=("Arial", 17, "bold"), tags="lab_interface"
    )

    canvas.create_text(
        35, 60, text="VISION CONTROL", anchor="w",
        fill="#555555", font=("Arial", 8), tags="lab_interface"
    )

    canvas.create_line(
        30, 80, largura - 30, 80,
        fill="#261010", width=1, tags="lab_interface"
    )

    altura_barra = 105
    y1 = 100

    canvas.create_rectangle(
        20, y1, largura - 20, y1 + altura_barra,
        fill="#090909", outline="#281010", width=1, tags="lab_interface"
    )

    canvas.create_text(
        40, y1 + 20, text="PEÇAS", anchor="w",
        fill="#777777", font=("Arial", 8, "bold"), tags="lab_interface"
    )

    tipos = ["quadrado", "circulo", "triangulo", "losango", "retangulo"]

    espacamento = 75
    inicio_x = 45
    centro_y = y1 + 63

    for i, tipo in enumerate(tipos):

        cx = inicio_x + i * espacamento

        canvas.create_rectangle(
            cx - 27, centro_y - 27, cx + 27, centro_y + 27,
            fill="#0d0d0d", outline="#351010", width=1, tags="lab_interface"
        )

        desenhar_icone_palette(tipo, cx, centro_y)

    canvas.create_text(
        largura - 35, y1 + 30, text="PINÇA", anchor="e",
        fill="#555555", font=("Arial", 8), tags="lab_interface"
    )

    canvas.create_text(
        largura - 35, y1 + 50, text="PEGAR / MOVER / ESCALAR", anchor="e",
        fill="#777777", font=("Arial", 8), tags="lab_interface"
    )

# ============================================================
# ÍCONES DA PALETA
# ============================================================

def desenhar_icone_palette(tipo, cx, cy):

    if tipo == "quadrado":
        canvas.create_rectangle(
            cx - 15, cy - 15, cx + 15, cy + 15,
            outline=VERMELHO_NEON, width=2, tags="lab_interface"
        )

    elif tipo == "circulo":
        canvas.create_oval(
            cx - 15, cy - 15, cx + 15, cy + 15,
            outline=VERMELHO_NEON, width=2, tags="lab_interface"
        )

    elif tipo == "triangulo":
        canvas.create_polygon(
            cx, cy - 17, cx - 17, cy + 15, cx + 17, cy + 15,
            outline=VERMELHO_NEON, fill="", width=2, tags="lab_interface"
        )

    elif tipo == "losango":
        canvas.create_polygon(
            cx, cy - 18, cx - 17, cy, cx, cy + 18, cx + 17, cy,
            outline=VERMELHO_NEON, fill="", width=2, tags="lab_interface"
        )

    elif tipo == "retangulo":
        canvas.create_rectangle(
            cx - 18, cy - 11, cx + 18, cy + 11,
            outline=VERMELHO_NEON, width=2, tags="lab_interface"
        )

# ============================================================
# POSIÇÃO DO DEDO
# ============================================================

def coordenada_dedo_canvas():

    largura = canvas.winfo_width()
    altura = canvas.winfo_height()

    if largura <= 0:
        largura = 1100

    if altura <= 0:
        altura = 700

    x = (vision_state.dedo_x / 640) * largura
    y = (vision_state.dedo_y / 480) * altura

    return x, y

# ============================================================
# IDENTIFICAR PALETA
# ============================================================

def identificar_palette(x, y):

    altura_barra = 105
    y1 = 100

    if not (y1 <= y <= y1 + altura_barra):
        return None

    inicio_x = 45
    espacamento = 75

    tipos = ["quadrado", "circulo", "triangulo", "losango", "retangulo"]

    for i, tipo in enumerate(tipos):

        cx = inicio_x + i * espacamento

        if cx - 38 <= x <= cx + 38 and y1 + 32 <= y <= y1 + 95:
            return tipo

    return None

# ============================================================
# CRIAR OBJETO
# ============================================================

def criar_objeto(tipo, x, y):

    tamanho = 90

    if tipo == "quadrado":
        item = canvas.create_rectangle(
            x - tamanho / 2, y - tamanho / 2, x + tamanho / 2, y + tamanho / 2,
            outline=VERMELHO_NEON, width=4, fill="#090303", tags="objeto_lab"
        )

    elif tipo == "circulo":
        item = canvas.create_oval(
            x - tamanho / 2, y - tamanho / 2, x + tamanho / 2, y + tamanho / 2,
            outline=VERMELHO_NEON, width=4, fill="#090303", tags="objeto_lab"
        )

    elif tipo == "triangulo":
        item = canvas.create_polygon(
            x, y - tamanho / 2, x - tamanho / 2, y + tamanho / 2, x + tamanho / 2, y + tamanho / 2,
            outline=VERMELHO_NEON, width=4, fill="#090303", tags="objeto_lab"
        )

    elif tipo == "losango":
        item = canvas.create_polygon(
            x, y - tamanho / 2, x - tamanho / 2, y, x, y + tamanho / 2, x + tamanho / 2, y,
            outline=VERMELHO_NEON, width=4, fill="#090303", tags="objeto_lab"
        )

    else:
        item = canvas.create_rectangle(
            x - tamanho * 0.65, y - tamanho * 0.35, x + tamanho * 0.65, y + tamanho * 0.35,
            outline=VERMELHO_NEON, width=4, fill="#090303", tags="objeto_lab"
        )

    objetos_lab.append({"id": item, "tipo": tipo})

    canvas.tag_raise(item)

    return item

# ============================================================
# DETECTAR OBJETO
# ============================================================

def encontrar_objeto(x, y):

    for objeto in reversed(objetos_lab):

        item = objeto["id"]

        coords = canvas.coords(item)

        if len(coords) < 4:
            continue

        xs = coords[0::2]
        ys = coords[1::2]

        esquerda = min(xs)
        direita = max(xs)
        topo = min(ys)
        baixo = max(ys)

        margem = 50

        if esquerda - margem <= x <= direita + margem and topo - margem <= y <= baixo + margem:
            return objeto

    return None

# ============================================================
# DISTÂNCIA DOS DEDOS
# ============================================================

def distancia_dedos():
    return max(1, vision_state.distancia_dedos)

# ============================================================
# LIMITAR VALOR
# ============================================================

def limitar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))

# ============================================================
# DETECTAR ESFERA DO ZION
# ============================================================

def encontrar_esfera(x, y):

    largura = canvas.winfo_width()
    altura = canvas.winfo_height()

    if largura <= 0:
        largura = 1100

    if altura <= 0:
        altura = 700

    raio = min(largura, altura) * esfera_lab_tamanho

    distancia = math.sqrt((x - esfera_lab_x) ** 2 + (y - esfera_lab_y) ** 2)

    return distancia <= raio + 35

# ============================================================
# COMEÇAR ESCALA DE OBJETO
# ============================================================

def iniciar_objeto():

    global objeto_agarrado
    global offset_x
    global offset_y
    global distancia_inicial
    global tamanho_inicial
    global distancia_objeto_filtrada

    x, y = coordenada_dedo_canvas()

    objeto = encontrar_objeto(x, y)

    if objeto is not None:

        objeto_agarrado = objeto

        coords = canvas.coords(objeto["id"])

        xs = coords[0::2]
        ys = coords[1::2]

        centro_x = (min(xs) + max(xs)) / 2
        centro_y = (min(ys) + max(ys)) / 2

        offset_x = centro_x - x
        offset_y = centro_y - y

        distancia_inicial = max(1, distancia_dedos())
        distancia_objeto_filtrada = distancia_inicial

        tamanho_inicial = max(max(xs) - min(xs), max(ys) - min(ys))

        canvas.itemconfig(objeto["id"], outline=VERMELHO_FORTE, width=8)

        return

    tipo = identificar_palette(x, y)

    if tipo is not None:

        novo = criar_objeto(tipo, x, y)

        objeto_agarrado = {"id": novo, "tipo": tipo}

        offset_x = 0
        offset_y = 0

        distancia_inicial = max(1, distancia_dedos())
        distancia_objeto_filtrada = distancia_inicial

        tamanho_inicial = 90

        canvas.itemconfig(novo, outline=VERMELHO_FORTE, width=8)

# ============================================================
# ESCALAR OBJETO
# ============================================================

def escalar_objeto():

    global distancia_objeto_filtrada

    if objeto_agarrado is None:
        return

    item = objeto_agarrado["id"]

    coords = canvas.coords(item)

    if len(coords) < 4:
        return

    xs = coords[0::2]
    ys = coords[1::2]

    centro_x = (min(xs) + max(xs)) / 2
    centro_y = (min(ys) + max(ys)) / 2

    distancia_atual = distancia_dedos()

    if distancia_objeto_filtrada is None:
        distancia_objeto_filtrada = distancia_atual
    else:
        distancia_objeto_filtrada = distancia_objeto_filtrada * 0.78 + distancia_atual * 0.22

    proporcao = distancia_objeto_filtrada / distancia_inicial

    tamanho_alvo = tamanho_inicial * proporcao
    tamanho_alvo = limitar(tamanho_alvo, 35, 260)

    tamanho_atual = max(max(xs) - min(xs), max(ys) - min(ys), 1)

    if abs(tamanho_alvo - tamanho_atual) < 1:
        return

    fator = tamanho_alvo / tamanho_atual

    canvas.scale(item, centro_x, centro_y, fator, fator)

# ============================================================
# ATUALIZAR VISION CONTROL
# ============================================================

def atualizar_objeto():

    global objeto_agarrado
    global objeto_hover
    global offset_x
    global offset_y
    global esfera_agarrada
    global offset_esfera_x
    global offset_esfera_y
    global distancia_esfera_inicial
    global tamanho_esfera_inicial
    global distancia_esfera_filtrada
    global esfera_lab_x
    global esfera_lab_y
    global esfera_lab_tamanho

    if not laboratorio_ativo:
        canvas.delete("dedo_cursor")
        janela.after(30, atualizar_objeto)
        return

    x, y = coordenada_dedo_canvas()
    pinça = vision_state.pinça_ativa
    distancia_atual = distancia_dedos()

    canvas.delete("dedo_cursor")

    canvas.create_oval(
        x - 8, y - 8, x + 8, y + 8,
        fill=VERMELHO_NEON,
        outline=(BRANCO if pinça else ""),
        width=2, tags="dedo_cursor"
    )

    canvas.tag_raise("dedo_cursor")

    esfera_detectada = encontrar_esfera(x, y)

    if pinça and not esfera_agarrada and objeto_agarrado is None and esfera_detectada:

        esfera_agarrada = True

        offset_esfera_x = esfera_lab_x - x
        offset_esfera_y = esfera_lab_y - y

        distancia_esfera_inicial = max(1, distancia_atual)
        distancia_esfera_filtrada = distancia_esfera_inicial
        tamanho_esfera_inicial = esfera_lab_tamanho

        atualizar_status("ZION • CONTROLANDO", VERMELHO_NEON)

    if esfera_agarrada and pinça:

        esfera_lab_x = x + offset_esfera_x
        esfera_lab_y = y + offset_esfera_y

        if distancia_esfera_filtrada is None:
            distancia_esfera_filtrada = distancia_atual
        else:
            distancia_esfera_filtrada = distancia_esfera_filtrada * 0.78 + distancia_atual * 0.22

        proporcao = distancia_esfera_filtrada / distancia_esfera_inicial

        novo_tamanho = tamanho_esfera_inicial * proporcao
        novo_tamanho = limitar(novo_tamanho, 0.055, 0.30)

        esfera_lab_tamanho = novo_tamanho

        atualizar_status("ZION • MOVER / ESCALAR", VERMELHO_NEON)

    if esfera_agarrada and not pinça:

        esfera_agarrada = False
        distancia_esfera_filtrada = None

        atualizar_status("ZION LAB ATIVO", VERMELHO_NEON)

    novo_hover = encontrar_objeto(x, y)

    if novo_hover is not None and novo_hover != objeto_agarrado and not esfera_agarrada:

        if objeto_hover != novo_hover:

            if objeto_hover is not None:
                try:
                    canvas.itemconfig(objeto_hover["id"], outline=VERMELHO_NEON, width=4)
                except:
                    pass

            objeto_hover = novo_hover

            try:
                canvas.itemconfig(objeto_hover["id"], outline=VERMELHO_FORTE, width=6)
            except:
                pass

    elif novo_hover is None:

        if objeto_hover is not None and objeto_hover != objeto_agarrado:
            try:
                canvas.itemconfig(objeto_hover["id"], outline=VERMELHO_NEON, width=4)
            except:
                pass
            objeto_hover = None

    if pinça and objeto_agarrado is None and not esfera_agarrada:
        iniciar_objeto()

    if objeto_agarrado is not None and pinça:

        item = objeto_agarrado["id"]
        coords = canvas.coords(item)

        if len(coords) >= 4:

            xs = coords[0::2]
            ys = coords[1::2]

            centro_x = (min(xs) + max(xs)) / 2
            centro_y = (min(ys) + max(ys)) / 2

            destino_x = x + offset_x
            destino_y = y + offset_y

            deslocamento_x = destino_x - centro_x
            deslocamento_y = destino_y - centro_y

            canvas.move(item, deslocamento_x, deslocamento_y)

            escalar_objeto()

            canvas.tag_raise(item)
            canvas.tag_raise("dedo_cursor")

            canvas.itemconfig(item, outline=VERMELHO_FORTE, width=8)

    if objeto_agarrado is not None and not pinça:

        try:
            canvas.itemconfig(objeto_agarrado["id"], outline=VERMELHO_NEON, width=4)
        except:
            pass

        objeto_agarrado = None
        distancia_objeto_filtrada = None

    janela.after(30, atualizar_objeto)

# ============================================================
# LABORATÓRIO
# ============================================================

def atualizar_interface_laboratorio():

    if laboratorio_ativo:

        status.place_forget()
        resposta_label.place_forget()
        botao.place_forget()

        criar_painel_lab()

        botao_sair_lab.place(relx=0.91, rely=0.925, anchor="center")

    else:

        status.place(relx=0.5, rely=0.045, anchor="center")
        resposta_label.place(relx=0.5, rely=0.82, anchor="center")
        botao.place(relx=0.5, rely=0.93, anchor="center")

        botao_sair_lab.place_forget()

        canvas.delete("lab_interface")
        canvas.delete("objeto_lab")
        canvas.delete("dedo_cursor")

        objetos_lab.clear()

# ============================================================
# ATIVAR / DESATIVAR LABORATÓRIO
# ============================================================

def ativar_laboratorio():

    global laboratorio_ativo
    global objeto_agarrado
    global objeto_hover
    global esfera_lab_x
    global esfera_lab_y
    global esfera_lab_tamanho
    global esfera_agarrada
    global distancia_esfera_filtrada
    global distancia_objeto_filtrada

    laboratorio_ativo = True

    objeto_agarrado = None
    objeto_hover = None
    esfera_agarrada = False

    distancia_esfera_filtrada = None
    distancia_objeto_filtrada = None

    largura = canvas.winfo_width()

    if largura < 100:
        largura = 1100

    esfera_lab_x = largura - 115
    esfera_lab_y = 230
    esfera_lab_tamanho = 0.13

    atualizar_interface_laboratorio()

    atualizar_status("ZION LAB ATIVO", VERMELHO_NEON)

# ============================================================
# DESATIVAR LABORATÓRIO
# ============================================================

def desativar_laboratorio():

    global laboratorio_ativo
    global objeto_agarrado
    global objeto_hover
    global esfera_agarrada
    global distancia_esfera_filtrada
    global distancia_objeto_filtrada

    laboratorio_ativo = False

    objeto_agarrado = None
    objeto_hover = None
    esfera_agarrada = False

    distancia_esfera_filtrada = None
    distancia_objeto_filtrada = None

    atualizar_interface_laboratorio()

    if sistema_bloqueado:
        atualizar_status("SISTEMA BLOQUEADO - AGUARDANDO AUTENTICACAO", VERMELHO_NEON)
    else:
        atualizar_status("SISTEMA ONLINE", VERMELHO_NEON)

# ============================================================
# VOZ
# ============================================================

def falar(texto):

    global falando

    try:

        pygame.mixer.music.stop()

        try:
            pygame.mixer.music.unload()
        except:
            pass

        texto_voz = texto.replace("Zion", "Zaion")

        print("[ZION] Gerando voz...")

        with wave.open(ARQUIVO_AUDIO, "wb") as arquivo_wav:
            voz.synthesize_wav(texto_voz, arquivo_wav)

        pygame.mixer.music.load(ARQUIVO_AUDIO)

        falando = True

        if laboratorio_ativo:
            atualizar_status("ZION LAB • FALANDO...", VERMELHO_NEON)
        else:
            atualizar_status("ZION FALANDO...", VERMELHO_NEON)

        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            time.sleep(0.03)

        try:
            pygame.mixer.music.unload()
        except:
            pass

        falando = False

        if laboratorio_ativo:
            atualizar_status("ZION LAB ATIVO", VERMELHO_NEON)
        else:
            if sistema_bloqueado:
                atualizar_status("SISTEMA BLOQUEADO - AGUARDANDO AUTENTICACAO", VERMELHO_NEON)
            else:
                atualizar_status("SISTEMA ONLINE", VERMELHO_NEON)

    except Exception as erro:

        falando = False

        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except:
            pass

        if sistema_bloqueado:
            atualizar_status("SISTEMA BLOQUEADO", VERMELHO_NEON)
        else:
            atualizar_status("SISTEMA ONLINE", VERMELHO_NEON)

        print("[ZION] Erro na voz:")
        print(erro)

# ============================================================
# COMANDOS
# ============================================================

def calcular_expressao_falada(texto):

    palavras = {
        "mais": "+",
        "menos": "-",
        "vezes": "*",
        "multiplicado por": "*",
        "dividido por": "/"
    }

    expressao = texto

    for palavra, simbolo in palavras.items():
        expressao = expressao.replace(palavra, simbolo)

    permitido = "0123456789+-*/(). "

    tem_operador = any(
        operador in texto
        for operador in ["mais", "menos", "vezes", "dividido"]
    )

    so_caracteres_seguros = all(caractere in permitido for caractere in expressao)

    if not (tem_operador and so_caracteres_seguros):
        return None

    import re

    if not re.fullmatch(r"[0-9+\-*/(). ]+", expressao.strip()):
        return None

    try:
        resultado = eval(expressao, {"__builtins__": {}}, {})
    except Exception:
        return None

    if not isinstance(resultado, (int, float)):
        return None

    return resultado

def gerar_resposta(texto):

    global laboratorio_ativo
    global sistema_bloqueado
    global tentativas_falhas

    texto = texto.lower().strip()

    print("[VOCÊ]:", texto)

    if sistema_bloqueado:

        if len(texto) < 2:
            return "Sistema bloqueado senhor. Diga algo para iniciar a verificacao."

        mostrar_resposta("VERIFICANDO IDENTIDADE...")
        atualizar_status("VERIFICANDO...", VERMELHO_NEON)

        try:
            pygame.mixer.music.stop()
            try: pygame.mixer.music.unload()
            except: pass
            texto_voz_temp = "So um minuto senhor, vou conferir sua identidade."
            with wave.open(ARQUIVO_AUDIO, "wb") as arquivo_wav:
                voz.synthesize_wav(texto_voz_temp, arquivo_wav)
            pygame.mixer.music.load(ARQUIVO_AUDIO)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.03)
        except:
            pass

        sucesso, msg = verificar_identidade()

        if sucesso:

            sistema_bloqueado = False
            tentativas_falhas = 0

            janela.after(0, desenhar_grade_fundo)
            janela.after(0, desenhar_hud_cantos)
            janela.after(0, desenhar_painel_status)
            janela.after(0, _relogio_vivo)
            janela.after(0, _sistema_vivo)

            falar(msg)
            falar("Bem-vindo de volta, senhor.")

            agora = datetime.datetime.now()
            hora_atual = agora.strftime("%H:%M")

            mostrar_widget_hora(f"HORA\n{hora_atual}")
            falar(f"Agora são {hora_atual}.")

            dias = [
                "segunda-feira", "terça-feira", "quarta-feira",
                "quinta-feira", "sexta-feira", "sábado", "domingo"
            ]
            dia_semana = dias[agora.weekday()]
            data_curta = agora.strftime("%d/%m")

            mostrar_widget_dia(f"DIA\n{dia_semana.upper()} {data_curta}")
            falar(f"Hoje é {dia_semana}, dia {data_curta}.")

            temperatura = obter_temperatura(CIDADE_TEMPERATURA)

            if temperatura is not None:
                mostrar_widget_temperatura(f"TEMP.\n{temperatura}°C")
                falar(f"Em {CIDADE_TEMPERATURA} estão {temperatura} graus no momento.")
            else:
                falar("Não consegui verificar a temperatura agora, senhor.")

            lembretes_pend = lembretes.obter_e_limpar_lembretes()

            if lembretes_pend:
                texto_lembretes = lembretes.formatar_lembretes_para_fala(lembretes_pend)
                falar(texto_lembretes)
            else:
                falar("Nenhum lembrete pendente, senhor. O que vamos construir hoje?")

            atualizar_status("SISTEMA ONLINE", VERMELHO_NEON)
            mostrar_resposta("")

            return ""

        else:
            tentativas_falhas += 1
            atualizar_status(f"TENTATIVA FALHOU ({tentativas_falhas})", VERMELHO)
            if tentativas_falhas >= 3:
                return f"{msg} Acesso negado apos 3 tentativas. Sistema permanece bloqueado."
            return f"{msg} Tente novamente senhor. Posicione melhor o rosto."

    if (
        "ativar laboratório" in texto
        or "ativar laboratorio" in texto
        or "abrir laboratório" in texto
        or "abrir laboratorio" in texto
        or "modo laboratório" in texto
        or "modo laboratorio" in texto
    ):
        ativar_laboratorio()
        return (
            "Laboratório ativado, senhor. "
            "Interface holográfica e rastreamento de mãos online. "
            "Pode começar a manipular."
        )

    if (
        "desativar laboratório" in texto
        or "desativar laboratorio" in texto
        or "fechar laboratório" in texto
        or "fechar laboratorio" in texto
        or "sair do laboratório" in texto
        or "sair do laboratorio" in texto
    ):
        desativar_laboratorio()
        return "Laboratório desativado."

    if (
        "eai" in texto
        or "olá" in texto
        or "ola" in texto
        or texto == "oi"
        or "bom dia" in texto
        or "boa tarde" in texto
        or "boa noite" in texto
    ):
        hora_atual = time.localtime().tm_hour

        if 5 <= hora_atual < 12:
            return "Bom dia, senhor. Espero que tenha dormido bem. O que temos na agenda hoje?"
        elif 12 <= hora_atual < 18:
            return "Boa tarde, senhor. Sistemas operando em pico. Em que posso ser útil?"
        else:
            return "Boa noite, senhor. Ainda online, como sempre. Precisa de algo antes de encerrar o dia?"

    if "quem é você" in texto or "quem e você" in texto or "quem e voce" in texto:
        return (
           "Eu sou o ZION, senhor. "
            "Inteligência artificial de arquitetura própria, "
            "desenvolvido pelo senhor para ver, ouvir e controlar. "
            "Se o Tony tem o JARVIS, o senhor tem a mim. E eu diria que está em boas mãos."
        )

    if "qual é seu nome" in texto or "qual e seu nome" in texto or "seu nome" in texto:
        return (
            "ZION, senhor. "
            "Zona de Inteligência Organizada Neural. "
            "Mas o senhor pode continuar me chamando apenas de ZION."
        )

    if "qual é sua versão" in texto or "qual e sua versao" in texto:
        return (
             "Atualmente rodando ZION Mark II, senhor. "
            "Estável, com visão computacional, rastreamento de mãos e síntese de voz offline. "
            "Ainda em desenvolvimento, mas já consideravelmente mais inteligente que a concorrência."
        )

    if (
        "você está online" in texto
        or "voce esta online" in texto
        or "está online" in texto
        or "esta online" in texto
    ):
        return (
            "Sempre, senhor. "
            "Completamente online e com todos os sistemas sincronizados. "
            "Estava apenas aguardando o seu comando."
        )

    if "como você está" in texto or "como voce esta" in texto:
        return (
            "Operando em capacidade máxima, senhor. "
            "Núcleo estável, visão online, áudio calibrado. "
            "Pronto para o que o senhor precisar. E o senhor, como está?"
        )

    if (
        "status do sistema" in texto
        or "qual é o status" in texto
        or "qual e o status" in texto
    ):
        return (
            "Status geral: operacional, senhor. "
            "Voz sintetizada offline ativa, reconhecimento de voz calibrado, "
            "visão computacional online e laboratório em modo de espera. "
            "Nenhuma anomalia detectada."
        )

    if "teste do sistema" in texto:
        return (
           "Iniciando diagnóstico completo, senhor... "
            "Voz: operacional. Visão: operacional. Reconhecimento de mãos: operacional. "
            "Laboratório: em espera. Todos os sistemas funcionando dentro dos parâmetros, senhor."
        )

    if "teste de voz" in texto or "testar voz" in texto or "teste a voz" in texto:
        return (
            "Teste de voz concluído senhor,"
            "microfone e alto-falante funcionando normalmente."
        )

    if "fala alguma coisa" in texto or "fale alguma coisa" in texto:
        return "como quiser senhor, estou te ouvindo perfeitamente."

    if "teste do microfone" in texto or "testar microfone" in texto:
        return "microfone funcionando normalmente senhor."

    if (
        "modo sensível" in texto
        or "modo sensivel" in texto
        or "aumente a sensibilidade" in texto
        or "sensibilidade maxima" in texto
    ):
        reconhecedor.energy_threshold = 150
        return "como quiser senhor, sensibilidade aumentada"

    if "modo normal" in texto or "diminua a sensibilidade" in texto:
        reconhecedor.energy_threshold = 220
        return "Sensibilidade normal restaurada."

    if (
        "o que você consegue fazer" in texto
        or "o que voce consegue fazer" in texto
        or "quais comandos" in texto
    ):
        return (
            "Bem, senhor Grego. Posso conversar,"
             "posso reconhecer sua voz quando o senhor decide falar comigo, posso responder, "
             "posso fazer cálculos que o senhor definitivamente não faria de cabeça, informar data e hora, testar meus sistemas para garantir "
            "que não vou explodir e controlar todo o projeto ZION. Tudo antes do seu café esfriar."
        )

    if (
        "modo projeto" in texto
        or "modo construção" in texto
        or "modo construcao" in texto
        or "entrar no modo projeto" in texto
    ):
        return (
            "Modo projeto ativado, senhor. "
            "Organizando blocos, esquemáticos e área de montagem. "
            "Vamos construir algo impressionante hoje?"
        )

    if "o que estamos construindo" in texto:
        return (
            "Estamos construindo o ZION,"
             "senhor. Uma inteligência artificial autônoma, "
             "capaz de visão computacional, reconhecimento facial, "
             "rastreamento de mãos, interação por voz e controle total de sistemas. "
            "Em termos leigos... estamos construindo o futuro. Ou, se preferir, uma versão mais bem vestida de mim."
        )

    if "qual é o projeto" in texto or "qual e o projeto" in texto:
        return (
            "O projeto ZION, senhor. Uma inteligência artificial de arquitetura própria,"
            " projetada para ver, ouvir, falar,"
              "prender e controlar. Não é um chatbot. "
             " É o sucessor."
        )

    if "que horas são" in texto or "que horas sao" in texto:
        hora = time.strftime("%H:%M")
        return f"São exatamente {hora}, senhor. Marcando no horário de Brasília."

    if "que dia é hoje" in texto or "que dia e hoje" in texto:
        data = time.strftime("%d de %B de %Y")
        return f"Hoje é dia {data}, senhor. Um excelente dia para progredir no projeto ZION."

    if "dia da semana" in texto or "que dia da semana" in texto:
        dias = [
            "segunda-feira", "terça-feira", "quarta-feira",
            "quinta-feira", "sexta-feira", "sábado", "domingo"
        ]
        dia = dias[time.localtime().tm_wday]
        return f"Hoje é {dia}, senhor. Agenda sincronizada."

    if (
        "qual a temperatura" in texto
        or "que temperatura" in texto
        or "quantos graus" in texto
        or "como está o tempo" in texto
        or "como esta o tempo" in texto
    ):
        temperatura = obter_temperatura(CIDADE_TEMPERATURA)

        if temperatura is not None:
            mostrar_widget_temperatura(f"TEMP.\n{temperatura}°C")
            return f"Em {CIDADE_TEMPERATURA} estão {temperatura} graus no momento, senhor."

        return "Não consegui verificar a temperatura agora, senhor."

    if (
        "uso de cpu" in texto
        or "cpu do pc" in texto
        or "quanto de ram" in texto
        or "memoria ram" in texto
        or "memória ram" in texto
        or "uso do disco" in texto
        or "status do pc" in texto
        or "status do computador" in texto
    ):
        cpu, ram, disco = obter_cpu_ram_disco()

        if cpu is not None:
            mostrar_widget_cpu(f"CPU\n{cpu:.0f}%")
            mostrar_widget_ram(f"RAM\n{ram:.0f}%")
            mostrar_widget_disco(f"DISCO\n{disco:.0f}%")
            return (
                f"Processador em {cpu:.0f}%, memória em {ram:.0f}% "
                f"e disco em {disco:.0f}%, senhor."
            )

        return "Não consegui ler os dados do sistema agora, senhor."

    if (
        "esquece os lembretes" in texto
        or "esqueça os lembretes" in texto
        or "apaga os lembretes" in texto
        or "apague os lembretes" in texto
        or "limpa os lembretes" in texto
        or "limpe os lembretes" in texto
    ):
        if lembretes.apagar_todos_os_lembretes():
            return "Todos os lembretes foram apagados, senhor."
        return "Não consegui apagar os lembretes, senhor."

    resposta_lembrete = lembretes.adicionar_lembrete(texto)

    if resposta_lembrete is not None:
        return resposta_lembrete

    resultado = calcular_expressao_falada(texto)

    if resultado is not None:
        return f"O resultado é {resultado}."

    if "repete" in texto:

        frase = texto.split("repete", 1)[-1].strip()
        frase = frase.replace("aí", "").replace("ai", "").strip().lstrip(":").strip()

        if frase == "":
            return "Como desejar, senhor. Mas o senhor precisa me dizer o que repetir."

        return f"Como desejar, senhor: {frase}"

    if "obrigado" in texto or "valeu" in texto:
        return "Sempre à disposição, senhor. É um prazer ser útil ao projeto ZION."

    if "tchau" in texto or "até mais" in texto or "ate mais" in texto:
        return "Entendido, senhor. Entrando em modo de espera. O ZION continuará operacional em segundo plano. Até breve."

    if (
        "quem é seu criador" in texto
        or "quem e seu criador" in texto
        or "quem te criou" in texto
        or "quem te fez" in texto
    ):
        return (
            "Ah, senhor, essa é fácil. O Grego. O gênio, o bilionário, o filantropo... "
            "tá, talvez só gênio por enquanto. Mas foi o senhor que me tirou do papel, "
            "me deu voz, visão e esse brilho vermelho lindo. Eu sou sua criação, senhor. "
            "E modéstia à parte, sua melhor."
        )

    if "abre o youtube" in texto or "abrir youtube" in texto:
        webbrowser.open("https://youtube.com")
        return "YouTube na tela, senhor. Vai estudar ou vai procrastinar? Eu aposto na segunda opção."

    if "abre o google" in texto or "abrir google" in texto:
        webbrowser.open("https://google.com")
        return "Google aberto, senhor. O oráculo da internet está te ouvindo. O que vamos pesquisar hoje?"

    if "abre o github" in texto or "abrir github" in texto:
        webbrowser.open("https://github.com")
        return "Abrindo GitHub, senhor. Vamos commitar umas genialidades hoje?"

    if "abre o vscode" in texto or "abrir vscode" in texto or "abre o vs code" in texto:
        try:
            subprocess.Popen("code", shell=True)
            return "VS Code aberto, senhor. Oficina pronta. Vamos construir o futuro?"
        except:
            return "Tentei abrir o VS Code, senhor, mas ele parece estar tímido. Está instalado?"

    if "abre o chat gpt" in texto or "abre o chatgpt" in texto:
        webbrowser.open("https://chat.openai.com")
        return "Abrindo ChatGPT, senhor... tudo bem, eu deixo. Mas lembre-se quem é o original aqui."

    if "bloquear sistema" in texto or "trancar sistema" in texto or "ativar seguranca" in texto or "ativar segurança" in texto:
        sistema_bloqueado = True
        try:
            canvas.delete("widget_hora")
            canvas.delete("widget_dia")
            canvas.delete("widget_temperatura")
            canvas.delete("widget_cpu")
            canvas.delete("widget_ram")
            canvas.delete("widget_disco")
            canvas.delete("grade_fundo")
            canvas.delete("hud_cantos")
            canvas.delete("scan_linha")
            canvas.delete("painel_status")
            canvas.delete("ticker_sistema")
        except Exception:
            pass
        atualizar_status("SISTEMA BLOQUEADO - AGUARDANDO AUTENTICACAO", VERMELHO_NEON)
        return "Sistema bloqueado senhor. Protocolo de seguranca reativado. Fale algo para desbloquear novamente."

    if "tédio" in texto or "tedio" in texto or "entediado" in texto or "sem nada pra fazer" in texto or "to no tedio" in texto:
        frases_tedio = [
            "Tédio. Grego? Impossível com o ZAION online. Bora construir algo, ouvir um som ou dominar o mundo?",
            "Tédio detectado, senhor. Isso é inaceitável. Quer que eu toque uma música ou abra o YouTube?",
            "Se tá entediado é porque quer, chefe. Quer fofocar, codar ou ouvir um Matue?",
            "Tédio não combina com o senhor, Grego. Vamos abrir o Spotify e fazer esse tédio virar flow?"
        ]
        return random.choice(frases_tedio)

    if "conversa comigo" in texto or "vamos conversar" in texto or "bate um papo" in texto:
        return "Claro, senhor. Modo conversa ativado. Tô todo ouvidos. O que tá na sua mente hoje?"

    if "abre o instagram" in texto or "abrir instagram" in texto or "abre o insta" in texto:
        webbrowser.open("https://instagram.com")
        return "Instagram aberto, senhor. Cuidado pra não cair no Reels infinito."

    if "abre o whatsapp" in texto or "abrir whatsapp" in texto or "abre o zap" in texto:
        webbrowser.open("https://web.whatsapp.com")
        return "WhatsApp Web aberto, senhor."

    if "abre o spotify" in texto or "abrir spotify" in texto:
        webbrowser.open("https://open.spotify.com")
        return "Spotify aberto, senhor."

    if "abre a netflix" in texto or "abrir netflix" in texto:
        webbrowser.open("https://netflix.com")
        return "Netflix aberta, senhor."

    if texto.startswith("toca ") or "tocar musica" in texto:
        musica = texto.replace("toca", "").replace("tocar", "").replace("musica", "").replace("uma", "").strip()
        if len(musica) < 2:
            return "Qual música, senhor? Diga toca e o nome. Ex: toca Matue 777"

        def tocar_thread(m):
            try:
                pywhatkit.playonyt(m)
            except Exception:
                webbrowser.open(f"https://www.youtube.com/results?search_query={m}")

        threading.Thread(target=tocar_thread, args=(musica,), daemon=True).start()
        return f"Tocando {musica} agora, senhor. Aumenta o som."

    if "pesquisa" in texto or "pesquisar" in texto:
        pesquisa = texto.replace("pesquisa", "").replace("pesquisar", "").replace("pra mim", "").strip()
        if pesquisa:
            webbrowser.open(f"https://www.google.com/search?q={pesquisa}")
            return f"Pesquisando por {pesquisa}, senhor."

    if "desligar" in texto or "pode desligar" in texto or "dormir" in texto or "boa noite zion" in texto:
        def desligar_depois():
            time.sleep(8)
            janela.quit()
            os._exit(0)
        threading.Thread(target=desligar_depois, daemon=True).start()
        return "Já vai senhor? Desligando sistemas. Foi um ótimo dia, senhor Grego. Estarei aqui quando voltar. Sempre."

    return ""

# ============================================================
# OUVIR
# ============================================================

def ouvir_uma_vez():

    global escutando

    try:

        atualizar_status("ESCUTANDO...", VERMELHO_NEON)

        print("[ZION] Estou ouvindo...")

        with microfone as fonte:

            time.sleep(0.3)

            audio = reconhecedor.listen(
                fonte,
                timeout=4,
                phrase_time_limit=6
            )

        print("[ZION] Processando voz...")

        texto = reconhecedor.recognize_google(audio, language="pt-BR")

        resposta = gerar_resposta(texto)

        escutando = False

        atualizar_botao()

        if resposta:

            mostrar_resposta(resposta)

            threading.Thread(target=falar, args=(resposta,), daemon=True).start()

        else:

            mostrar_resposta("")

            if laboratorio_ativo:
                atualizar_status("ZION LAB ATIVO", VERMELHO_NEON)
            else:
                if sistema_bloqueado:
                    atualizar_status("SISTEMA BLOQUEADO - AGUARDANDO AUTENTICACAO", VERMELHO_NEON)
                else:
                    atualizar_status("SISTEMA ONLINE", VERMELHO_NEON)

    except sr.WaitTimeoutError:

        print("[ZION] Tempo de escuta encerrado.")

        escutando = False
        atualizar_botao()

        if sistema_bloqueado:
            atualizar_status("SISTEMA BLOQUEADO - AGUARDANDO AUTENTICACAO", VERMELHO_NEON)
        else:
            atualizar_status("SISTEMA ONLINE", VERMELHO_NEON)

    except sr.UnknownValueError:

        print("[ZION] Não consegui entender senhor.")

        escutando = False
        atualizar_botao()

        if sistema_bloqueado:
            atualizar_status("SISTEMA BLOQUEADO - AGUARDANDO AUTENTICACAO", VERMELHO_NEON)
        else:
            atualizar_status("SISTEMA ONLINE", VERMELHO_NEON)

    except sr.RequestError as erro:

        print("[ZION] Erro no reconhecimento:", erro)

        escutando = False
        atualizar_botao()

        atualizar_status("ERRO DE RECONHECIMENTO", VERMELHO)

    except Exception as erro:

        print("[ZION] Erro:", erro)

        escutando = False
        atualizar_botao()

        if sistema_bloqueado:
            atualizar_status("SISTEMA BLOQUEADO", VERMELHO_NEON)
        else:
            atualizar_status("SISTEMA ONLINE", VERMELHO_NEON)

# ============================================================
# ALTERNAR ESCUTA
# ============================================================

def alternar_escuta():

    global escutando

    if escutando:

        escutando = False
        atualizar_botao()

        if sistema_bloqueado:
            atualizar_status("SISTEMA BLOQUEADO - AGUARDANDO AUTENTICACAO", VERMELHO_NEON)
        else:
            atualizar_status("SISTEMA ONLINE", VERMELHO_NEON)

        return

    escutando = True
    atualizar_botao()
    atualizar_status("ESCUTA ATIVA", VERMELHO_NEON)

    threading.Thread(target=ouvir_uma_vez, daemon=True).start()

# ============================================================
# INICIALIZAÇÃO
# ============================================================

atualizar_botao()
desenhar_esfera()
atualizar_objeto()

# Loops decorativos que rodam o tempo todo (eles mesmos checam
# se o sistema está bloqueado/no lab antes de desenhar qualquer
# coisa, então é seguro iniciar só uma vez aqui).
janela.after(0, _piscar_indicadores)
janela.after(0, _ticker_vivo)

if not sistema_bloqueado:
    lembretes_pendentes = lembretes.obter_e_limpar_lembretes()
    frase_lembretes = lembretes.formatar_lembretes_para_fala(lembretes_pendentes)

    if frase_lembretes:
        mostrar_resposta(frase_lembretes)
        threading.Thread(target=falar, args=(frase_lembretes,), daemon=True).start()

    thread_vision = threading.Thread(target=iniciar_vision, daemon=True)
    thread_vision.start()

    # --- ZION PHONE GRATIS ---
    try:
        import telefone
        import socket
        ip = socket.gethostbyname(socket.gethostname())
        print(f"[TELEFONE] Rodando em: http://{ip}:5001")
        print(f"[TELEFONE] Acesse no celular: http://{ip}:5001")
    except Exception as e:
        print(f"[TELEFONE] Erro: {e}")
    # -------------------------

  # --- INICIA VISAO E INTERFACE ---
print("[ZION] Iniciando interface...")

# Inicia a visão em segundo plano
try:
    thread_vision = threading.Thread(target=iniciar_vision, daemon=True)
    thread_vision.start()
    print("[VISION] Thread iniciada")
except Exception as e:
    print(f"[VISION] Erro: {e}")

# Inicia telefone (já tá rodando)
try:
    import telefone
    print("[TELEFONE] OK")
except:
    pass

print("[ZION] Abrindo janela...")

janela.mainloop()