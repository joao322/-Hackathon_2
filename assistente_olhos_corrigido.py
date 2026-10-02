import os
import cv2
import time
import urllib.parse
import urllib.request
import threading
import subprocess
import pyttsx3
import pyperclip
import numpy as np
import mediapipe as mp
import serial
import queue
import pyautogui
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ARDUINO
arduino = serial.Serial(
    "/dev/ttyACM0",
    9600,
    timeout=1
)

time.sleep(2)


def ligar_luz():

    arduino.write(b"L")

    print("LUZ LIGADA")


def desligar_luz():

    arduino.write(b"D")

    print("LUZ DESLIGADA")



# 1. MAPEAMENTO DOS CONTATOS DO WHATSAPP (Substitua pelos números reais com DDD)
CONTATOS_WHATSAPP = {
    "JOÃO": "+55719776-1111",
    "SANDRA": "+5575992350300",
    "HUMBERTO": "+5571999990002",
    "HAROLDO": "+5571999990003",
    "SILEIDE": "+5571999990004"
}

# 2. MENSAGEM PADRÃO DIRETA
MENSAGEM_PADRAO_DIRETA = "Saudade meu filho(a), me ligue!"

# 3. DOWNLOAD AUTOMÁTICO DO MODELO DE VISÃO
MODEL_PATH = "face_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

if not os.path.exists(MODEL_PATH):
    print("Baixando o arquivo de modelo face_landmarker.task...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Download concluído com sucesso!")


# Função para síntese de voz em segundo plano
def speak_async(text):
    def run_speech():
        try:
            engine = pyttsx3.init()

            voices = engine.getProperty("voices")

            for voice in voices:
                voice_id = str(voice.id).lower()
                voice_name = str(voice.name).lower()

                if (
                    "pt-br" in voice_id
                    or "pt_br" in voice_id
                    or "brazil" in voice_name
                    or "brasil" in voice_name
                ):
                    engine.setProperty("voice", voice.id)
                    break

            engine.setProperty("rate", 160)
            engine.setProperty("volume", 1.0)

            engine.say(text)
            engine.runAndWait()
            engine.stop()

        except Exception as e:
            print(f"Erro no áudio: {e}")

    threading.Thread(target=run_speech, daemon=True).start()


# Disparo confiável via App do WhatsApp no Windows
def send_whatsapp_desktop_async(nome_contato, numero_telefone, mensagem_texto):
    def run_desktop_app():
        try:
            texto_codificado = urllib.parse.quote(mensagem_texto)
            numero = numero_telefone.replace("+", "")
            link_app = (
                f"https://web.whatsapp.com/send?"
                f"phone={numero}&text={texto_codificado}"
            )

            subprocess.Popen(["xdg-open", link_app])

            print(f"WhatsApp aberto para {nome_contato}.")

        except Exception as e:
            print(f"Erro ao abrir WhatsApp: {e}")

    threading.Thread(target=run_desktop_app, daemon=True).start()

    # NOVA FUNÇÃO: LIGAÇÃO
def ligar_whatsapp(numero):
    numero = numero.replace("+", "").replace(" ", "").replace("-", "")

    mensagem = "Preciso de ajuda. Por favor, me ligue!"

    try:
        subprocess.Popen([
            "flatpak",
            "run",
            "com.ktechpit.whatsie",
            "--new-chat",
            numero
        ])

        time.sleep(10)

        pyautogui.click(500, 700)
        time.sleep(1)

        pyperclip.copy(mensagem)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(1)
        pyautogui.press("enter")

        print("Comando de envio executado!")

    except Exception as e:
        print("Erro ao enviar mensagem:", e)

# Índices dos pontos dos olhos no Face Landmarker
LEFT_EYE_IDXS = [362, 385, 387, 263, 373, 380]
RIGHT_EYE_IDXS = [33, 160, 158, 133, 153, 144]

# --- PARÂMETROS DE TEMPO E FILTRAGEM ---
EAR_THRESHOLD = 0.17
MIN_BLINK_TIME = 0.4
BLINK_TIME_THRESHOLD = 1.0
UNPAUSE_TIME_THRESHOLD = 3.0
SCAN_INTERVAL = 2.0
SELECTION_COOLDOWN = 2.0


def euclidean_dist(pt1, pt2):
    return np.linalg.norm(pt1 - pt2)


def calculate_ear(landmarks, eye_indices, img_w, img_h):
    pts = []

    for idx in eye_indices:
        lm = landmarks[idx]
        pts.append(np.array([lm.x * img_w, lm.y * img_h]))

    v1 = euclidean_dist(pts[1], pts[5])
    v2 = euclidean_dist(pts[2], pts[4])
    h = euclidean_dist(pts[0], pts[3])

    if h == 0:
        return 0.0

    return (v1 + v2) / (2.0 * h)


# Configuração do MediaPipe
base_options = python.BaseOptions(model_asset_path=MODEL_PATH)

options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    output_face_blendshapes=False,
    output_facial_transformation_matrixes=False,
    num_faces=1
)

detector = vision.FaceLandmarker.create_from_options(options)


# ESTRUTURA DOS MENUS ATUALIZADA
menus = {
    "INICIAL": ["PEDIDO", "DOR", "LIGAR","LUZ", "SAIR"],
    "PEDIDO": ["Fome", "Boca Seca", "Ajustar a cama", "Voltar"],
    "DOR": [
        "Cabeça",
        "Peito",
        "Barriga/Enjoo",
        "Perna",
        "Braço",
        "Costas",
        "Voltar"
    ],
    "LIGAR": [
        "JOÃO",
        "SANDRA",
        "HUMBERTO",
        "HAROLDO",
        "SILEIDE",
        "Voltar"
    ],
    "LUZ": [
        "LIGAR LUZ",
        "DESLIGAR LUZ",
        "Voltar"
    ],
}


current_menu = "INICIAL"
selected_idx = 0
last_scan_time = time.time()
blink_start_time = None
selection_cooldown_end = 0
has_opened_eyes_first = False
is_paused = False

solicitacao_pendente = None


# Câmera
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("ERRO: não foi possível acessar a câmera.")
    raise SystemExit


speak_async("Sistema iniciado.")


while cap.isOpened():

    success, frame = cap.read()

    if not success:
        print("Erro ao acessar a câmera.")
        break

    frame = cv2.flip(frame, 1)

    h, w, _ = frame.shape

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb_frame
    )

    detection_result = detector.detect(mp_image)

    is_blinking = False
    blink_progress = 0.0

    now = time.time()

    in_cooldown = now < selection_cooldown_end

    current_ear = 0.0


    if detection_result.face_landmarks:

        landmarks = detection_result.face_landmarks[0]

        left_ear = calculate_ear(
            landmarks,
            LEFT_EYE_IDXS,
            w,
            h
        )

        right_ear = calculate_ear(
            landmarks,
            RIGHT_EYE_IDXS,
            w,
            h
        )

        current_ear = (left_ear + right_ear) / 2.0


        # OLHOS ABERTOS
        if current_ear >= EAR_THRESHOLD:

            has_opened_eyes_first = True
            blink_start_time = None


        # OLHOS FECHADOS
        elif current_ear < EAR_THRESHOLD and has_opened_eyes_first:

            if blink_start_time is None:
                blink_start_time = now

            blink_duration = now - blink_start_time


            if blink_duration >= MIN_BLINK_TIME:

                is_blinking = True


                # MODO PAUSADO
                if is_paused:

                    blink_progress = min(
                        blink_duration / UNPAUSE_TIME_THRESHOLD,
                        1.0
                    )

                    if blink_duration >= UNPAUSE_TIME_THRESHOLD:

                        is_paused = False
                        current_menu = "INICIAL"
                        selected_idx = 0

                        speak_async("Sistema reativado.")

                        blink_start_time = None
                        is_blinking = False
                        has_opened_eyes_first = False

                        selection_cooldown_end = (
                            now + SELECTION_COOLDOWN
                        )

                        last_scan_time = (
                            now + SELECTION_COOLDOWN
                        )


                # MODO ATIVO
                elif not in_cooldown:

                    blink_progress = min(
                        blink_duration / BLINK_TIME_THRESHOLD,
                        1.0
                    )

                    last_scan_time = now


                    if blink_duration >= BLINK_TIME_THRESHOLD:

                        option = menus[current_menu][selected_idx]

                        print(f"SELECIONADO: {option}")
                        
                        # CONTROLE DA LUZ
                        if current_menu == "LUZ" and option == "LIGAR LUZ":
                            ligar_luz()

                        elif current_menu == "LUZ" and option == "DESLIGAR LUZ":
                            desligar_luz()

                        # CONTATO DO WHATSAPP
                        if (
                            current_menu == "LIGAR"
                            and option in CONTATOS_WHATSAPP
                        ):

                            numero = CONTATOS_WHATSAPP[option]


                            speak_async(
                                f"Ligando para {option}"
                            )

                            ligar_whatsapp(numero)

                            solicitacao_pendente = None
                            current_menu = "INICIAL"
                            selected_idx = 0
                                
                        elif option == "SAIR":

                            is_paused = True

                            speak_async(
                                "Sistema em pausa. "
                                "Feche os olhos por 3 segundos para reativar."
                            )


                        else:

                            speak_async(
                                f"Opção selecionada: {option}"
                            )


                        # PEDIDO OU DOR
                        if (
                            current_menu in ["PEDIDO", "DOR"]
                            and option != "Voltar"
                        ):

                            solicitacao_pendente = (
                                f"{current_menu} -> {option}"
                            )

                            current_menu = "LIGAR"
                            selected_idx = 0


                        # NAVEGAÇÃO
                        elif option == "PEDIDO":

                            current_menu = "PEDIDO"
                            selected_idx = 0


                        elif option == "DOR":

                            current_menu = "DOR"
                            selected_idx = 0


                        elif option == "LIGAR":

                            current_menu = "LIGAR"
                            selected_idx = 0
                        elif option == "LUZ":

                            current_menu = "LUZ"
                            selected_idx = 0
                             
                        elif option == "Voltar":

                            current_menu = "INICIAL"
                            selected_idx = 0
                            solicitacao_pendente = None


                        blink_start_time = None
                        is_blinking = False
                        blink_progress = 0.0
                        has_opened_eyes_first = False

                        selection_cooldown_end = (
                            now + SELECTION_COOLDOWN
                        )

                        last_scan_time = (
                            now + SELECTION_COOLDOWN
                        )


    # VARREDURA DO MENU

    if (
        not is_paused
        and not is_blinking
        and not in_cooldown
        and (now - last_scan_time > SCAN_INTERVAL)
    ):

        selected_idx = (
           selected_idx + 1
        ) % len(menus[current_menu])

    # Pega a opção que acabou de ser selecionada
        opcao_atual = menus[current_menu][selected_idx]

    # Mostra no terminal
        print(f"OPÇÃO ATUAL: {opcao_atual}")

    # Fala a opção em voz alta
        speak_async(opcao_atual)

        last_scan_time = now


    # INTERFACE
    display = np.zeros(
        (770, 800, 3),
        dtype=np.uint8
    )


    if is_paused:

        cv2.rectangle(
            display,
            (50, 200),
            (750, 420),
            (30, 30, 30),
            -1
        )

        cv2.rectangle(
            display,
            (50, 200),
            (750, 420),
            (0, 200, 255),
            2
        )


        cv2.putText(
            display,
            "SISTEMA EM PAUSA",
            (180, 270),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (0, 200, 255),
            3
        )


        cv2.putText(
            display,
            "Mantenha os olhos fechados por 3s para REATIVAR",
            (80, 350),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )


        if is_blinking and blink_progress > 0:

            progress_w = int(
                700 * blink_progress
            )

            cv2.rectangle(
                display,
                (50, 450),
                (50 + progress_w, 490),
                (0, 255, 0),
                -1
            )

            cv2.rectangle(
                display,
                (50, 450),
                (750, 490),
                (255, 255, 255),
                2
            )

            pct = int(
                blink_progress * 100
            )

            cv2.putText(
                display,
                f"REATIVANDO: {pct}%",
                (300, 478),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 0),
                2
            )


    else:

        cv2.rectangle(
            display,
            (50, 25),
            (750, 85),
            (40, 40, 40),
            -1
        )


        status_titulo = (
            f"MENU: {current_menu}"
        )


        if solicitacao_pendente:

            status_titulo += (
                f" ({solicitacao_pendente})"
            )


        cv2.putText(
            display,
            f"PAINEL ASSISTIVO | {status_titulo}",
            (70, 65),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2
        )


        btn_x = 50
        btn_y_start = 105
        btn_w = 700
        btn_h = 70
        spacing = 15


        for i, option in enumerate(
            menus[current_menu]
        ):

            y1 = (
                btn_y_start
                + i * (btn_h + spacing)
            )

            y2 = y1 + btn_h


            if i == selected_idx:

                bg_color = (0, 160, 0)
                border_color = (255, 255, 255)
                text_color = (255, 255, 255)


                cv2.rectangle(
                    display,
                    (btn_x, y1),
                    (btn_x + btn_w, y2),
                    bg_color,
                    -1
                )


                if is_blinking and blink_progress > 0:

                    progress_w = int(
                        btn_w * blink_progress
                    )

                    cv2.rectangle(
                        display,
                        (btn_x, y1),
                        (btn_x + progress_w, y2),
                        (255, 140, 0),
                        -1
                    )


                cv2.rectangle(
                    display,
                    (btn_x, y1),
                    (btn_x + btn_w, y2),
                    border_color,
                    3
                )


            else:

                bg_color = (40, 40, 40)
                border_color = (80, 80, 80)
                text_color = (180, 180, 180)


                cv2.rectangle(
                    display,
                    (btn_x, y1),
                    (btn_x + btn_w, y2),
                    bg_color,
                    -1
                )


                cv2.rectangle(
                    display,
                    (btn_x, y1),
                    (btn_x + btn_w, y2),
                    border_color,
                    2
                )


            cv2.putText(
                display,
                option,
                (btn_x + 30, y1 + 48),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.95,
                text_color,
                2
            )


        if in_cooldown:

            cv2.putText(
                display,
                "Aguarde... Mude de tela e abra os olhos",
                (50, 730),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 200, 255),
                2
            )


        elif is_blinking:

            pct = int(
                blink_progress * 100
            )

            cv2.putText(
                display,
                f"CONFIRMANDO SELECAO: {pct}%",
                (50, 730),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2
            )


        else:

            cv2.putText(
                display,
                "Aguarde a opcao desejada e feche os olhos por 1s para selecionar.",
                (50, 730),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (150, 150, 150),
                1
            )


    ear_str = (
        f"EAR Atual: {current_ear:.2f} "
        f"(Limiar Fechado: < {EAR_THRESHOLD})"
    )


    cv2.putText(
        display,
        ear_str,
        (50, 690),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (180, 180, 180),
        1
    )


    cv2.imshow(
        "Assistente de Comunicação",
        display
    )


    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


cap.release()
cv2.destroyAllWindows()