"""
Sistema de Seguridad con Detección Facial
==========================================
Detecta rostros en tiempo real y determina si son usuarios autorizados o intrusos.
Si detecta un intruso durante 10 segundos, toma foto y bloquea Windows.
"""

import cv2
import numpy as np
import os
import subprocess
import time
from datetime import datetime
import insightface
from insightface.app import FaceAnalysis


# ─── CONFIGURACIÓN ──────────────────────────────────────────────────────────────
SCRIPT_DIR         = os.path.dirname(os.path.abspath(__file__))   # Carpeta del .py
CARPETA_USUARIOS   = os.path.join(SCRIPT_DIR, "usuarios")
CARPETA_INTRUSOS   = os.path.join(SCRIPT_DIR, "intrusos")
UMBRAL_SIMILITUD   = 0.45            # Similitud coseno mínima (bajado para mayor tolerancia)
TIEMPO_INTRUSO_SEG = 10
CAMARA_INDEX       = 0
RESOLUCION         = (1280, 720)

# ─── COLORES (BGR) ──────────────────────────────────────────────────────────────
COLOR_USUARIO  = (0, 220, 80)
COLOR_INTRUSO  = (0, 60, 220)
COLOR_SIN_ID   = (200, 200, 0)
COLOR_BARRA    = (20, 20, 20)
COLOR_TEXTO    = (240, 240, 240)


def similitud_coseno(v1: np.ndarray, v2: np.ndarray) -> float:
    v1 = v1.flatten()
    v2 = v2.flatten()
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))


def cargar_embeddings_usuarios(app: FaceAnalysis) -> dict:
    embeddings = {}

    print(f"\n[DEBUG] Buscando usuarios en: {CARPETA_USUARIOS}")

    if not os.path.exists(CARPETA_USUARIOS):
        os.makedirs(CARPETA_USUARIOS)
        print(f"[INFO] Carpeta 'usuarios' creada en: {CARPETA_USUARIOS}")
        print("[INFO] Agrega fotos de usuarios autorizados y reinicia el programa.")
        return embeddings

    archivos = [f for f in os.listdir(CARPETA_USUARIOS)
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]

    print(f"[DEBUG] Archivos encontrados en usuarios/: {archivos}")

    if not archivos:
        print("[AVISO] La carpeta 'usuarios' está vacía. Todos serán intrusos.")
        return embeddings

    for archivo in archivos:
        ruta = os.path.join(CARPETA_USUARIOS, archivo)
        print(f"[DEBUG] Leyendo imagen: {ruta}")
        img = cv2.imread(ruta)

        if img is None:
            print(f"[ERROR] No se pudo leer la imagen: {ruta}")
            print("        Verifica que el archivo no esté corrupto.")
            continue

        print(f"[DEBUG] Imagen leída OK. Tamaño: {img.shape}")
        rostros = app.get(img)
        print(f"[DEBUG] Rostros detectados en '{archivo}': {len(rostros)}")

        if not rostros:
            print(f"[AVISO] No se detectó ningún rostro en: {archivo}")
            print("        Usa una foto con buena iluminación y rostro visible de frente.")
            continue

        rostro = max(rostros, key=lambda r: (r.bbox[2]-r.bbox[0]) * (r.bbox[3]-r.bbox[1]))
        nombre = os.path.splitext(archivo)[0]
        embeddings[nombre] = rostro.embedding
        sim_consigo = similitud_coseno(rostro.embedding, rostro.embedding)
        print(f"[OK] Usuario cargado: '{nombre}' | Embedding shape: {rostro.embedding.shape}")

    return embeddings


def identificar_rostro(embedding: np.ndarray, embeddings_usuarios: dict):
    if not embeddings_usuarios:
        return "Intruso", 0.0

    mejor_nombre = None
    mejor_sim    = -1.0

    for nombre, emb_ref in embeddings_usuarios.items():
        sim = similitud_coseno(embedding, emb_ref)
        if sim > mejor_sim:
            mejor_sim    = sim
            mejor_nombre = nombre

    # Debug: imprimir similitud en cada comparación
    print(f"[DEBUG] Similitud con '{mejor_nombre}': {mejor_sim:.4f} | Umbral: {UMBRAL_SIMILITUD}", end="\r")

    if mejor_sim >= UMBRAL_SIMILITUD:
        return mejor_nombre, mejor_sim
    else:
        return "Intruso", mejor_sim


def guardar_foto_intruso(frame: np.ndarray) -> str:
    if not os.path.exists(CARPETA_INTRUSOS):
        os.makedirs(CARPETA_INTRUSOS)
        print(f"[INFO] Carpeta 'intrusos' creada en: {CARPETA_INTRUSOS}")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nombre    = f"{timestamp}.jpg"
    ruta      = os.path.join(CARPETA_INTRUSOS, nombre)
    resultado = cv2.imwrite(ruta, frame)
    if resultado:
        print(f"\n[SEGURIDAD] Foto guardada en: {ruta}")
    else:
        print(f"\n[ERROR] No se pudo guardar la foto en: {ruta}")
    return ruta


def bloquear_windows():
    print("[SEGURIDAD] ¡BLOQUEANDO WINDOWS!")
    subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])


def dibujar_rostro(frame, bbox, nombre, similitud, es_intruso):
    x1, y1, x2, y2 = [int(v) for v in bbox]
    color = COLOR_INTRUSO if es_intruso else COLOR_USUARIO

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    largo, grosor = 20, 3
    for (px, py, dx, dy) in [(x1, y1, 1, 1), (x2, y1, -1, 1),
                              (x1, y2, 1, -1), (x2, y2, -1, -1)]:
        cv2.line(frame, (px, py), (px + dx*largo, py), color, grosor)
        cv2.line(frame, (px, py), (px, py + dy*largo), color, grosor)

    label = f"{nombre}  {similitud:.3f}"
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 8, y1), color, -1)
    cv2.putText(frame, label, (x1 + 4, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def dibujar_hud(frame, estado, tiempo_intruso, hay_rostro, n_usuarios):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 50), COLOR_BARRA, -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    cv2.putText(frame, "SISTEMA DE SEGURIDAD FACIAL", (12, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, COLOR_TEXTO, 2)

    color_estado = COLOR_USUARIO if estado == "AUTORIZADO" else (
        COLOR_INTRUSO if estado == "INTRUSO" else COLOR_SIN_ID)
    cv2.putText(frame, f"Estado: {estado}", (w - 280, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, color_estado, 2)

    cv2.putText(frame, f"Usuarios registrados: {n_usuarios}", (12, 44),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_TEXTO, 1)

    if tiempo_intruso > 0:
        progreso = min(tiempo_intruso / TIEMPO_INTRUSO_SEG, 1.0)
        barra_w  = int((w - 24) * progreso)
        cv2.rectangle(frame, (12, 38), (12 + barra_w, 48), COLOR_INTRUSO, -1)
        label_t = f"Intruso: {tiempo_intruso:.1f}s / {TIEMPO_INTRUSO_SEG}s"
        cv2.putText(frame, label_t, (w // 2 - 130, 47),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 180, 180), 1)

    if not hay_rostro:
        cv2.putText(frame, "Sin rostro en camara", (w - 280, 44),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_SIN_ID, 1)


def main():
    print("=" * 60)
    print("  SISTEMA DE SEGURIDAD FACIAL  v1.1 (modo diagnóstico)")
    print("=" * 60)

    # ── 1. Inicializar InsightFace ──────────────────────────────────
    print("\n[INICIO] Cargando modelo InsightFace...")
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    print("[OK] Modelo cargado.\n")

    # ── 2. Cargar embeddings de usuarios ───────────────────────────
    embeddings_usuarios = cargar_embeddings_usuarios(app)

    print(f"\n{'─'*60}")
    print(f"  Usuarios cargados: {len(embeddings_usuarios)}")
    for nombre in embeddings_usuarios:
        print(f"    ✓ {nombre}")
    if not embeddings_usuarios:
        print("  ⚠ Sin usuarios — todo rostro será intruso")
    print(f"{'─'*60}\n")

    # ── 3. Abrir webcam ────────────────────────────────────────────
    print(f"[INICIO] Abriendo cámara {CAMARA_INDEX}...")
    cap = cv2.VideoCapture(CAMARA_INDEX)
    if not cap.isOpened():
        print("[ERROR] No se pudo acceder a la cámara.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  RESOLUCION[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUCION[1])
    print("[OK] Cámara abierta. Presiona Q para salir.\n")

    tiempo_inicio_intruso = None
    bloqueado             = False

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] No se pudo leer frame.")
                break

            rostros        = app.get(frame)
            hay_rostro     = len(rostros) > 0
            hay_intruso    = False
            hay_autorizado = False
            estado_hud     = "SIN ROSTRO"

            for rostro in rostros:
                nombre, similitud = identificar_rostro(rostro.embedding, embeddings_usuarios)
                es_intruso = (nombre == "Intruso")
                if es_intruso:
                    hay_intruso = True
                else:
                    hay_autorizado = True
                dibujar_rostro(frame, rostro.bbox, nombre, similitud, es_intruso)

            if hay_rostro:
                if hay_autorizado and not hay_intruso:
                    estado_hud            = "AUTORIZADO"
                    tiempo_inicio_intruso = None
                    bloqueado             = False
                elif hay_intruso:
                    estado_hud = "INTRUSO"
                    if tiempo_inicio_intruso is None:
                        tiempo_inicio_intruso = time.time()
            else:
                estado_hud            = "SIN ROSTRO"
                tiempo_inicio_intruso = None   # resetea timer si no hay nadie
                bloqueado             = False  # permite volver a bloquear en la siguiente detección

            tiempo_intruso = 0.0
            if tiempo_inicio_intruso is not None:
                tiempo_intruso = time.time() - tiempo_inicio_intruso
                if tiempo_intruso >= TIEMPO_INTRUSO_SEG and not bloqueado:
                    print(f"\n[ALERTA] Intruso por {TIEMPO_INTRUSO_SEG}s.")
                    guardar_foto_intruso(frame)
                    bloquear_windows()
                    bloqueado             = True
                    tiempo_inicio_intruso = None
                    time.sleep(2)

            dibujar_hud(frame, estado_hud, tiempo_intruso, hay_rostro, len(embeddings_usuarios))
            cv2.imshow("Sistema de Seguridad Facial  |  Q = Salir", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("\n[INFO] Saliendo...")
                break

    except KeyboardInterrupt:
        print("\n[INFO] Interrumpido.")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Recursos liberados.")


if __name__ == "__main__":
    main()
