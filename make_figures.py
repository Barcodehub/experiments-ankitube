"""
Genera las figuras del artículo. Las cuatro salen de este único script.

Produce (PDF vectorial para el envío + PNG a 600 ppp para revisar):
  figures/fig1_arquitectura.pdf   -> Fig. 1: arquitectura y frontera de datos
  figures/fig2_pipeline.pdf       -> Fig. 2: canalización de 12 etapas
  figures/fig3_segmentacion.pdf   -> Fig. 3: un video segmentado por las 4 estrategias (datos reales)
  figures/fig4_rendimiento.pdf    -> Fig. 4: tiempo por etapa vs duración (datos reales)

La Fig. 5 son capturas de pantalla: no se genera aquí (ver README_FIGURAS.md).

Uso:
    python make_figures.py                       # genera las cuatro
    python make_figures.py --video 6o3m9Bw67Os   # otro video para la Fig. 3
    python make_figures.py --listar              # lista los videos y sale
    python make_figures.py --solo 1 2            # genera solo las figuras indicadas

Única dependencia: matplotlib.
"""

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

# --------------------------------------------------------------------------
# Configuración de estilo para publicación IEEE
# --------------------------------------------------------------------------
# IEEE: columna simple = 3.5 pulgadas; doble columna = 7.16 pulgadas.
# Tipografía serif de 8 pt, que es lo que exige el formato de dos columnas.
COL_SIMPLE = 3.5
COL_DOBLE = 7.16

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "lines.linewidth": 1.0,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
    "pdf.fonttype": 42,   # TrueType incrustada: requisito frecuente de IEEE
    "ps.fonttype": 42,
})

# Escala de grises + un acento, para que la figura funcione impresa en blanco y negro
GRIS_OSCURO = "#222222"
GRIS_MEDIO = "#777777"
GRIS_CLARO = "#BBBBBB"
ACENTO = "#1A1A1A"

AQUI = os.path.dirname(os.path.abspath(__file__))
RUTA_DATOS = os.path.join(AQUI, "data", "exp_results.jsonl")
DIR_SALIDA = os.path.join(AQUI, "figures")

# Video por defecto para la Fig. 3. Criterio de selección: cobertura de la IA
# representativa del corpus (96 %, frente a una mediana de 95 %), duración media
# y un número de segmentos legible en las cuatro pistas.
#
# ATENCIÓN: no usar 90Kgw_SvK4w. Es un caso atípico en el que la IA solo cubre el
# 48 % de la duración del video (el habla termina antes), lo que daría una
# impresión falsa del comportamiento habitual del sistema.
VIDEO_POR_DEFECTO = "4JN7Sk9cTQA"

# Por debajo de este porcentaje de cobertura, el script avisa de que el video
# elegido no es representativo del corpus.
UMBRAL_COBERTURA_AVISO = 85.0

# Orden y etiquetas de las estrategias tal como aparecen en el artículo
ESTRATEGIAS = [
    ("llm_auto", "Semántica (IA)"),
    ("llm_short2", "Límite 2 oraciones"),
    ("llm_medium5", "Límite 5 oraciones"),
    ("fixed_20", "Intervalo fijo 20 s"),
]


def cargar():
    with open(RUTA_DATOS, encoding="utf-8") as f:
        return [json.loads(linea) for linea in f if linea.strip()]


def asegurar_dir():
    os.makedirs(DIR_SALIDA, exist_ok=True)


def guardar(fig, nombre):
    asegurar_dir()
    ruta_pdf = os.path.join(DIR_SALIDA, nombre + ".pdf")
    ruta_png = os.path.join(DIR_SALIDA, nombre + ".png")
    fig.savefig(ruta_pdf)
    fig.savefig(ruta_png, dpi=600)
    plt.close(fig)
    print(f"  escrito: {ruta_pdf}")
    print(f"  escrito: {ruta_png}")


# ==========================================================================
# Utilidades de dibujo para los diagramas (Fig. 1 y Fig. 2)
# ==========================================================================
def caja(ax, x, y, w, h, texto, *, relleno="white", borde=GRIS_OSCURO,
         grosor=0.8, tam=7, estilo="round,pad=0.012", guion=None, negrita=False):
    """Dibuja una caja redondeada con texto centrado."""
    p = FancyBboxPatch((x, y), w, h, boxstyle=estilo,
                       facecolor=relleno, edgecolor=borde,
                       linewidth=grosor, linestyle=guion or "solid", zorder=2)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, texto, ha="center", va="center",
            fontsize=tam, zorder=3, linespacing=1.3,
            fontweight="bold" if negrita else "normal")
    return p


def flecha(ax, xy_origen, xy_destino, *, color=GRIS_OSCURO, grosor=0.9,
           estilo="-|>", guion=None, curva=0.0):
    ax.add_patch(FancyArrowPatch(
        xy_origen, xy_destino, arrowstyle=estilo, mutation_scale=8,
        linewidth=grosor, color=color, zorder=4,
        linestyle=guion or "solid",
        connectionstyle=f"arc3,rad={curva}",
    ))


# ==========================================================================
# FIGURA 1 — Arquitectura del sistema y frontera de datos
# ==========================================================================
def figura1():
    fig, ax = plt.subplots(figsize=(COL_DOBLE, 3.9))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 62)
    ax.axis("off")

    # --- Contenedor: equipo del usuario -----------------------------------
    ax.add_patch(FancyBboxPatch(
        (2, 24), 96, 36, boxstyle="round,pad=0.4",
        facecolor="#F7F7F7", edgecolor=GRIS_OSCURO,
        linewidth=1.1, linestyle=(0, (5, 3)), zorder=1))
    ax.text(4, 57.4, "Equipo del usuario", fontsize=7.5,
            fontweight="bold", va="center", ha="left", zorder=3)

    # Plano 1: cliente de escritorio
    caja(ax, 6, 48.5, 88, 6.6,
         "Cliente de escritorio  ·  Tauri (Rust) + React/TypeScript\n"
         "formulario de configuración · indicador de etapas · guardado del artefacto",
         relleno="white", tam=7)

    flecha(ax, (50, 48.3), (50, 45.2))
    ax.text(51, 46.75, "HTTP a interfaz de bucle local", fontsize=6,
            va="center", ha="left", color=GRIS_MEDIO)

    # Plano 2: servicio local
    caja(ax, 6, 27, 88, 18,
         "", relleno="white", tam=7)
    ax.text(50, 43.2, "Servicio local  ·  FastAPI (Python), empaquetado con PyInstaller",
            fontsize=7, ha="center", va="center", fontweight="bold")
    ax.text(50, 40.6, "orquestación de la canalización  ·  un trabajo a la vez",
            fontsize=6.3, ha="center", va="center", color=GRIS_MEDIO)

    # Dependencias embebidas
    deps = [
        ("yt-dlp", "adquisición"),
        ("faster-whisper", "ASR local"),
        ("FFmpeg", "recorte de medios"),
        ("genanki", "empaquetado"),
        ("SQLite", "telemetría local"),
    ]
    ancho = 15.6
    hueco = 1.6
    x0 = 50 - (len(deps) * ancho + (len(deps) - 1) * hueco) / 2
    for i, (nombre, rol) in enumerate(deps):
        caja(ax, x0 + i * (ancho + hueco), 28.6, ancho, 9.4,
             f"{nombre}\n\n{rol}", relleno="#EDEDED", tam=6.4, grosor=0.6)

    # --- Frontera de datos ------------------------------------------------
    ax.annotate("", xy=(2, 22.4), xytext=(98, 22.4),
                arrowprops=dict(arrowstyle="-", linewidth=0.7,
                                color=GRIS_MEDIO, linestyle=(0, (2, 2))))

    # Lo que NO cruza: flecha tachada
    flecha(ax, (18, 22.2), (18, 17.4), grosor=0.9, guion=(0, (3, 2)), color=GRIS_MEDIO)
    ax.plot([15.6, 20.4], [20.9, 18.7], color=GRIS_OSCURO, linewidth=1.6, zorder=6)
    ax.plot([15.6, 20.4], [18.7, 20.9], color=GRIS_OSCURO, linewidth=1.6, zorder=6)
    caja(ax, 3, 11.2, 30, 5.6,
         "Video y audio:\nnunca cruzan la frontera",
         relleno="white", borde=GRIS_OSCURO, tam=6.6, grosor=1.0, guion=(0, (3, 2)))

    # Lo que sí cruza
    flecha(ax, (58, 22.2), (58, 14.2), grosor=1.1)
    ax.text(59.4, 18.2,
            "solo TEXTO de la transcripción,\ny solo si se activa una función de IA",
            fontsize=6.4, va="center", ha="left", linespacing=1.3)

    flecha(ax, (86, 22.2), (86, 14.2), grosor=0.9, guion=(0, (3, 2)))
    ax.text(87.4, 18.2, "sesión, plan,\ncréditos", fontsize=6.4,
            va="center", ha="left", linespacing=1.3, color=GRIS_MEDIO)

    # --- Planos externos ---------------------------------------------------
    caja(ax, 38, 2.6, 30, 11.2,
         "Proveedores de modelo\nde lenguaje\n\n"
         "clave propia o proxy gestionado\n(patrón Strategy, intercambiables)",
         relleno="white", tam=6.4)

    caja(ax, 71, 2.6, 27, 11.2,
         "Backend remoto\n\n"
         "cuentas · JWT RS256\ncapacidades por plan · créditos",
         relleno="white", tam=6.4)

    ax.text(2, 0.6,
            "El plano externo nunca recibe medios. La única información que sale del equipo es texto, "
            "y solo cuando el usuario activa una función de IA.",
            fontsize=6, ha="left", va="bottom", color=GRIS_MEDIO, style="italic")

    guardar(fig, "fig1_arquitectura")


# ==========================================================================
# FIGURA 2 — Canalización de doce etapas
# ==========================================================================
def figura2():
    # (número, nombre en 2 líneas, detalle, estocástica)
    etapas = [
        (1, "Verificación\nde capacidades", "token firmado, sin red", False),
        (2, "Adquisición", "descarga o copia local", False),
        (3, "Obtención de\ntranscripción", "manual > automática > ASR", False),
        (4, "Normalización", "a formato SRT", False),
        (5, "Limpieza textual", "anotaciones no habladas", False),
        (6, "Segmentación", "cuatro estrategias", True),
        (7, "Deduplicación", "opcional, umbral 0,85", False),
        (8, "Formato\nde turnos", "reglas | IA | desactivado", True),
        (9, "Recorte\nde medios", "por segmento, H.264/AAC", False),
        (10, "Sub-transcripción", "re-temporizada", False),
        (11, "Generación\nde tarjeta", "+ enriquecimiento opcional", True),
        (12, "Empaquetado", "medios embebidos", False),
    ]

    fig, ax = plt.subplots(figsize=(COL_DOBLE, 3.9))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 59)
    ax.axis("off")

    n_col = 4
    ancho = 21.0
    alto = 13.0
    sep_x = 5.3
    y_fila = [44.0, 27.0, 10.0]

    centros = []
    for i, (num, nombre, detalle, estoc) in enumerate(etapas):
        fila = i // n_col
        col = i % n_col
        # Serpentina: las filas pares van a la derecha, las impares a la izquierda
        if fila % 2 == 1:
            col = n_col - 1 - col
        x = 2 + col * (ancho + sep_x)
        y = y_fila[fila]

        relleno = "#D9D9D9" if estoc else "white"
        caja(ax, x, y, ancho, alto, "", relleno=relleno,
             grosor=1.1 if estoc else 0.8)
        ax.text(x + 1.6, y + alto - 2.2, f"{num}", fontsize=6.8,
                ha="left", va="center", fontweight="bold", color=GRIS_MEDIO)
        ax.text(x + ancho / 2, y + alto / 2 + 0.9, nombre, fontsize=6.8,
                ha="center", va="center", linespacing=1.15)
        ax.text(x + ancho / 2, y + 2.3, detalle, fontsize=5.5,
                ha="center", va="center", color=GRIS_MEDIO)
        centros.append((x, y, ancho, alto, fila))

    for i in range(len(etapas) - 1):
        x1, y1, w1, h1, f1 = centros[i]
        x2, y2, w2, h2, f2 = centros[i + 1]
        if f1 == f2:
            if x2 > x1:
                flecha(ax, (x1 + w1 + 0.4, y1 + h1 / 2), (x2 - 0.4, y2 + h2 / 2), grosor=0.8)
            else:
                flecha(ax, (x1 - 0.4, y1 + h1 / 2), (x2 + w2 + 0.4, y2 + h2 / 2), grosor=0.8)
        else:
            flecha(ax, (x1 + w1 / 2, y1 - 0.4), (x2 + w2 / 2, y2 + h2 + 0.4), grosor=0.8)

    # Leyenda en banda inferior, sin colisionar con las cajas
    caja(ax, 2, 2.0, 6.0, 4.4, "", relleno="#D9D9D9", grosor=1.1)
    ax.text(9.4, 4.2, "invoca un modelo de lenguaje (etapa opcional)",
            fontsize=6, ha="left", va="center")
    caja(ax, 52, 2.0, 6.0, 4.4, "", relleno="white", grosor=0.8)
    ax.text(59.4, 4.2, "determinista", fontsize=6, ha="left", va="center")
    ax.text(98, 4.2, "4 de 12 etapas invocan modelo",
            fontsize=5.8, ha="right", va="center", color=GRIS_MEDIO, style="italic")

    guardar(fig, "fig2_pipeline")


# ==========================================================================
# FIGURA 3 — Un mismo video segmentado por las cuatro estrategias
# ==========================================================================
def figura3(registros, id_video):
    reg = next((r for r in registros if r["id"] == id_video), None)
    if reg is None:
        raise SystemExit(f"No existe el video {id_video}. Usa --listar para ver los disponibles.")

    dur = reg["duration"]

    fig, ax = plt.subplots(figsize=(COL_DOBLE, 2.5))

    alto_pista = 0.62
    sep = 1.0

    for i, (clave, etiqueta) in enumerate(ESTRATEGIAS):
        y = (len(ESTRATEGIAS) - 1 - i) * sep
        trozos = reg["seg"][clave]
        trozos = trozos["chunks"] if isinstance(trozos, dict) else trozos

        for j, (ini, fin) in enumerate(trozos):
            # Alternar relleno para que los límites entre segmentos se vean
            # incluso cuando son contiguos, como ocurre con el intervalo fijo.
            color = GRIS_MEDIO if j % 2 == 0 else GRIS_CLARO
            ax.add_patch(Rectangle(
                (ini, y), max(fin - ini, 0.01), alto_pista,
                facecolor=color, edgecolor=GRIS_OSCURO, linewidth=0.5,
            ))

        # Marcas verticales en cada punto de corte
        for (ini, _fin) in trozos[1:]:
            ax.plot([ini, ini], [y, y + alto_pista],
                    color=ACENTO, linewidth=0.9, solid_capstyle="butt")

        ax.text(-dur * 0.015, y + alto_pista / 2,
                f"{etiqueta}\n({len(trozos)} seg.)",
                ha="right", va="center", fontsize=7, linespacing=1.25)

    ax.set_xlim(-dur * 0.30, dur * 1.01)
    ax.set_ylim(-0.25, len(ESTRATEGIAS) * sep - sep + alto_pista + 0.25)
    ax.set_yticks([])
    ax.set_xlabel("Tiempo del video (s)")

    paso = 30 if dur <= 300 else 60
    ax.set_xticks(list(range(0, int(dur) + 1, paso)))

    for lado in ("left", "right", "top"):
        ax.spines[lado].set_visible(False)
    ax.tick_params(axis="y", length=0)

    # Recuadro que delimita la extensión real del video
    ax.axvline(0, color=GRIS_OSCURO, linewidth=0.6, zorder=0)
    ax.axvline(dur, color=GRIS_OSCURO, linewidth=0.6, linestyle=":", zorder=0)
    ax.text(dur, -0.18, f" fin ({dur} s)", fontsize=6, va="top", ha="right", color=GRIS_MEDIO)

    guardar(fig, "fig3_segmentacion")

    print(f"\n  Video usado: {reg['id']} — \"{reg['title']}\" ({reg['channel']}), {dur} s")
    print("  Segmentos por estrategia:")
    for clave, etiqueta in ESTRATEGIAS:
        t = reg["seg"][clave]
        t = t["chunks"] if isinstance(t, dict) else t
        duraciones = [b - a for a, b in t]
        media = sum(duraciones) / len(duraciones)
        print(f"    {etiqueta:<22} n={len(t):>3}  duración media={media:5.1f} s")

    # Control de representatividad: si la IA cubre poco del video, la figura
    # transmitiría una impresión equivocada del comportamiento habitual.
    ch_auto = reg["seg"]["llm_auto"]
    ch_auto = ch_auto["chunks"] if isinstance(ch_auto, dict) else ch_auto
    cobertura = 100 * max(b for _a, b in ch_auto) / dur
    print(f"  Cobertura de la segmentación por IA: {cobertura:.0f} % de la duración")
    if cobertura < UMBRAL_COBERTURA_AVISO:
        print(f"\n  *** AVISO: cobertura del {cobertura:.0f} %, por debajo del umbral de "
              f"{UMBRAL_COBERTURA_AVISO:.0f} %.")
        print("  Este video NO es representativo del corpus (mediana ~95 %). Usar otro")
        print("  en la figura del artículo, o explicar el caso en el pie de figura.")


# ==========================================================================
# FIGURA 4 — Tiempo de proceso por etapa frente a duración del video
# ==========================================================================
def ajuste_lineal(xs, ys):
    """Mínimos cuadrados sin numpy: devuelve (pendiente, intercepto)."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return 0.0, my
    m = sxy / sxx
    return m, my - m * mx


def figura4(registros):
    # Promedio de las dos mediciones de descarga, como en el artículo
    remed = {}
    ruta_remed = os.path.join(AQUI, "data", "download_remeasure.jsonl")
    if os.path.exists(ruta_remed):
        with open(ruta_remed, encoding="utf-8") as f:
            for linea in f:
                if linea.strip():
                    d = json.loads(linea)
                    clave = d.get("id") or d.get("video_id")
                    valor = d.get("t_download") or d.get("t")
                    if clave and valor:
                        remed[clave] = valor

    series = {
        "Adquisición": [],
        "Transcripción (ASR local)": [],
        "Segmentación semántica (IA)": [],
        "Empaquetado (cortes + mazo)": [],
    }

    for r in registros:
        if not r.get("ok"):
            continue
        dur = r["duration"]

        d1 = r.get("t_download")
        d2 = remed.get(r["id"])
        if d1 is not None:
            descarga = (d1 + d2) / 2 if d2 is not None else d1
            series["Adquisición"].append((dur, descarga))

        if r.get("t_transcribe") is not None:
            series["Transcripción (ASR local)"].append((dur, r["t_transcribe"]))

        seg = r.get("seg", {}).get("llm_auto")
        if isinstance(seg, dict) and seg.get("t") is not None and seg.get("chunks"):
            series["Segmentación semántica (IA)"].append((dur, seg["t"]))

        pack = r.get("pack", {}).get("llm_auto")
        if isinstance(pack, dict) and pack.get("t_cut_cards") is not None:
            series["Empaquetado (cortes + mazo)"].append(
                (dur, pack["t_cut_cards"] + pack.get("t_build", 0.0))
            )

    marcadores = {
        "Adquisición": ("o", GRIS_MEDIO),
        "Transcripción (ASR local)": ("s", ACENTO),
        "Segmentación semántica (IA)": ("^", GRIS_OSCURO),
        "Empaquetado (cortes + mazo)": ("D", GRIS_CLARO),
    }

    fig, ax = plt.subplots(figsize=(COL_SIMPLE, 2.7))

    manijas = []
    for nombre, puntos in series.items():
        if not puntos:
            continue
        xs = [p[0] for p in puntos]
        ys = [p[1] for p in puntos]
        marca, color = marcadores[nombre]

        ax.scatter(xs, ys, s=11, marker=marca, facecolors="none",
                   edgecolors=color, linewidths=0.7, zorder=3)

        m, b = ajuste_lineal(xs, ys)
        x0, x1 = min(xs), max(xs)
        ax.plot([x0, x1], [m * x0 + b, m * x1 + b],
                color=color, linewidth=0.9, linestyle="-", zorder=2)

        manijas.append(Line2D([], [], marker=marca, linestyle="-",
                              markerfacecolor="none", markeredgecolor=color,
                              color=color, markersize=4, linewidth=0.9,
                              label=f"{nombre} (n={len(puntos)})"))

    ax.set_xlabel("Duración del video (s)")
    ax.set_ylabel("Tiempo de proceso (s)")
    ax.grid(True, linewidth=0.3, color=GRIS_CLARO, alpha=0.6)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)

    # Margen superior para que la leyenda no se solape con los puntos
    y_max = max(y for puntos in series.values() for _x, y in puntos)
    ax.set_ylim(top=y_max * 1.52)

    ax.legend(handles=manijas, loc="upper left", frameon=False,
              handlelength=1.6, borderpad=0.2, labelspacing=0.3)

    guardar(fig, "fig4_rendimiento")

    print("\n  Pendientes del ajuste (segundos de proceso por segundo de video):")
    for nombre, puntos in series.items():
        if not puntos:
            continue
        m, b = ajuste_lineal([p[0] for p in puntos], [p[1] for p in puntos])
        print(f"    {nombre:<32} {m:+.4f}  (intercepto {b:+.1f} s, n={len(puntos)})")


# ==========================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default=VIDEO_POR_DEFECTO,
                    help="ID del video para la Fig. 3")
    ap.add_argument("--listar", action="store_true",
                    help="lista los videos disponibles y termina")
    ap.add_argument("--solo", nargs="+", type=int, choices=[1, 2, 3, 4],
                    help="genera solo las figuras indicadas (p. ej. --solo 1 2)")
    args = ap.parse_args()
    cuales = set(args.solo) if args.solo else {1, 2, 3, 4}

    registros = cargar()

    if args.listar:
        print(f"{'ID':<14} {'dur':>5} {'cob%':>5}  {'auto':>4} {'c2':>4} {'m5':>4} {'f20':>4}   título")
        for r in registros:
            if not r.get("ok"):
                continue
            n = {}
            for clave, _ in ESTRATEGIAS:
                t = r["seg"].get(clave)
                t = t.get("chunks") if isinstance(t, dict) else t
                n[clave] = len(t) if t else 0
            ch = r["seg"].get("llm_auto")
            ch = ch.get("chunks") if isinstance(ch, dict) else ch
            cob = 100 * max(b for _a, b in ch) / r["duration"] if ch else 0
            marca = "  <- atípico" if cob < UMBRAL_COBERTURA_AVISO else ""
            print(f"{r['id']:<14} {r['duration']:>5} {cob:>5.0f}  "
                  f"{n['llm_auto']:>4} {n['llm_short2']:>4} "
                  f"{n['llm_medium5']:>4} {n['fixed_20']:>4}   {r['title'][:36]}{marca}")
        print("\ncob% = porcentaje de la duración del video cubierto por la segmentación por IA.")
        print("Para la figura del artículo, elige un video con cobertura alta y pocos segmentos.")
        return

    if 1 in cuales:
        print("Figura 1 — arquitectura y frontera de datos")
        figura1()
    if 2 in cuales:
        print("\nFigura 2 — canalización de doce etapas")
        figura2()
    if 3 in cuales:
        print("\nFigura 3 — segmentación comparada")
        figura3(registros, args.video)
    if 4 in cuales:
        print("\nFigura 4 — rendimiento por etapa")
        figura4(registros)

    print(f"\nListo. Figuras en: {DIR_SALIDA}")
    print("Usa los .pdf para el envío (vectorial) y los .png para revisar.")
    print("Falta la Fig. 5 (capturas de pantalla): ver README_FIGURAS.md")


if __name__ == "__main__":
    main()
