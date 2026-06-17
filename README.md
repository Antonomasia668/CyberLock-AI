# CyberLock-AI
# 🔐 Sistema de Seguridad Facial


Detección facial en tiempo real con reconocimiento de usuarios autorizados e intrusos.  
Si se detecta un intruso durante **10 segundos continuos**, el programa toma una foto y **bloquea Windows**.

---

## Estructura del proyecto

```
face_security/
├── detector.py          ← Script principal
├── requirements.txt     ← Dependencias
├── README.md
├── usuarios/            ← Fotos de usuarios autorizados (tú las agregas)
│   └── juan.jpg
│   └── maria.png
└── intrusos/            ← Fotos capturadas automáticamente por el programa
    └── 2024-06-15_14-32-01.jpg
```

---

## Instalación

### 1. Requisitos previos
- Python 3.9 o superior
- Cámara web conectada
- Windows (para el bloqueo automático)

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

> **Nota:** En la primera ejecución, InsightFace descargará automáticamente el modelo
> `buffalo_l` (~300 MB). Necesitas conexión a internet la primera vez.

---

## Configuración de usuarios

1. Coloca **una foto clara** de cada usuario autorizado en la carpeta `usuarios/`.
2. El nombre del archivo será el nombre mostrado en pantalla (ej. `Juan.jpg` → "Juan").
3. Requisitos de la foto:
   - El rostro debe ser visible y bien iluminado.
   - Un solo rostro por foto (se toma el más prominente si hay varios).
   - Formatos soportados: `.jpg`, `.jpeg`, `.png`, `.webp`

---

## Uso

```bash
python detector.py
```

- **Verde** → Usuario autorizado reconocido.
- **Rojo** → Intruso detectado. La barra de progreso indica el tiempo transcurrido.
- **Q** → Salir del programa.

---

## Parámetros configurables

Edita las constantes al inicio de `detector.py`:

| Parámetro | Valor por defecto | Descripción |
|---|---|---|
| `UMBRAL_SIMILITUD` | `0.45` | Similitud mínima (0-1) para reconocer un usuario. Súbelo si hay falsos positivos, bájalo si no reconoce bien. |
| `TIEMPO_INTRUSO_SEG` | `10` | Segundos continuos de intruso antes de bloquear. |
| `CAMARA_INDEX` | `0` | Índice de la cámara (0 = predeterminada, 1 = segunda cámara, etc.). |
| `RESOLUCION` | `(1280, 720)` | Resolución de captura. |

---

## Comportamiento del sistema

```
Cámara activa
    │
    ├─ Sin rostro detectado  → Espera. No reinicia contador de intruso.
    │
    ├─ Rostro detectado
    │       │
    │       ├─ Similitud ≥ UMBRAL  → ✅ AUTORIZADO (recuadro verde)
    │       │
    │       └─ Similitud < UMBRAL  → 🔴 INTRUSO (recuadro rojo)
    │               │
    │               └─ ¿10 segundos continuos?
    │                       │
    │                       └─ Sí → 📸 Foto guardada en /intrusos/
    │                                🔒 Windows bloqueado
    │                                ⏱  Contador reiniciado
```

---

## Solución de problemas

**No reconoce al usuario autorizado:**
- Agrega varias fotos del mismo usuario con diferentes condiciones de luz.
- Baja el `UMBRAL_SIMILITUD` a `0.35`.

**Muchos falsos positivos (reconoce intrusos como usuarios):**
- Sube el `UMBRAL_SIMILITUD` a `0.55`.

**La cámara no abre:**
- Cambia `CAMARA_INDEX` a `1` o `2`.
- Verifica que ninguna otra aplicación esté usando la cámara.

**Error al instalar InsightFace en Windows:**
```bash
pip install insightface --no-build-isolation
