# Figuras del artículo — cómo se generan

## Resumen

| Figura | Qué es | Cómo se hace | Estado |
|---|---|---|---|
| Fig. 1 | Arquitectura y frontera de datos | `make_figures.py` | **Hecha** |
| Fig. 2 | Canalización de 12 etapas | `make_figures.py` | **Hecha** |
| Fig. 3 | Segmentación comparada (datos reales) | `make_figures.py` | **Hecha** |
| Fig. 4 | Rendimiento por etapa (datos reales) | `make_figures.py` | **Hecha** |
| Fig. 5 | Capturas de los 3 modos de tarjeta | A mano, 20 min | **Pendiente** |

```bash
python make_figures.py
```

Genera las cuatro en `figures/`, en **PDF vectorial** (para el envío) y **PNG a 600 ppp** (para revisar).

Opciones:

```bash
python make_figures.py --listar          # lista los videos del corpus
python make_figures.py --video 6o3m9Bw67Os   # otro video para la Fig. 3
python make_figures.py --solo 1 2        # regenera solo las que indiques
```

Única dependencia: `matplotlib`. Si falta: `python -m pip install matplotlib`.

---

## Por qué no se usan generadores de imágenes por IA

Los generadores de imágenes (Gemini, DALL·E, Midjourney y similares) **no sirven para figuras científicas**:

- Producen texto ilegible o mal escrito en las etiquetas, y una etiqueta mal escrita en un diagrama de arquitectura invalida la figura.
- Inventan elementos que no existen en el sistema descrito.
- Generan mapas de bits, no vectores. IEEE pide vectorial o un mínimo de 600 ppp para líneas.
- Las figuras 3 y 4 **deben** proceder de los datos medidos. Una figura "parecida" generada por IA sería una tergiversación de los resultados.

Lo correcto es lo que hace este script: las figuras de datos se derivan de `data/exp_results.jsonl`, y los diagramas se dibujan con coordenadas explícitas.

---

## Nota sobre la elección del video de la Fig. 3

El script usa por defecto **`4JN7Sk9cTQA`** ("Mixed Signals From Saturn", NASA, 142 s), elegido porque su cobertura de segmentación por IA es del 96 %, cercana a la mediana del corpus.

**No uses `90Kgw_SvK4w`.** Es un caso atípico: la IA solo cubre el 48 % de la duración porque el habla termina pronto. La figura daría una impresión falsa del comportamiento habitual. El script avisa automáticamente si eliges un video con cobertura inferior al 85 %.

Si cambias de video, comprueba que:
1. La cobertura sea ≥ 90 % (columna `cob%` en `--listar`).
2. Las cuatro pistas tengan pocos segmentos, para que la figura sea legible a una columna.

---

## Figura 5 — capturas de los tres modos de tarjeta

Es la única que no se automatiza, porque son capturas reales de la aplicación de repaso. Unos veinte minutos.

### Procedimiento

1. **Genera tres mazos** con la aplicación, a partir de un video del corpus experimental (de dominio público: evita material de terceros en las capturas). Uno por modo: Escucha, Quiz y Combinado. Activa traducción y tip de pronunciación en al menos uno, para que el reverso muestre los campos de enriquecimiento.

2. **Impórtalos en Anki** y abre una tarjeta representativa de cada modo.

3. **Captura seis imágenes**: anverso y reverso de cada uno de los tres modos.
   - Usa siempre la **misma anchura de ventana** en las seis.
   - Tema claro, no oscuro: se imprime mejor.
   - Si la plantilla permite ampliar la tipografía, hazlo: en una figura a dos columnas el texto de la tarjeta queda pequeño.

4. **Recorta** cada captura al área de la tarjeta, sin barras de herramientas ni menús de la aplicación.

5. **Monta una rejilla 3×2**: una fila por modo, columna izquierda el anverso y columna derecha el reverso. Rotula cada fila ("Escucha", "Quiz", "Combinado") y cada columna ("Anverso", "Reverso"). Puedes montarla en PowerPoint, Inkscape, GIMP o la propia plantilla de IEEE.

6. **Exporta** a PDF si la herramienta lo permite; si no, PNG a 600 ppp mínimo.

### Qué debe verse en cada captura

| Modo | Anverso debe mostrar | Reverso debe mostrar |
|---|---|---|
| Escucha | Título y reproductor del clip, **sin texto** | Transcripción del fragmento + traducción y tip si se activaron |
| Quiz | Título y pregunta de comprensión, **sin clip** | Respuesta, clip y extracto desplegable de la transcripción |
| Combinado | Título, pregunta **y** clip | Respuesta, transcripción y campos de enriquecimiento |

Ese contraste es el que sustenta §III-E del artículo: el modo Escucha difiere el texto, y Quiz y Combinado colocan el clip en lados opuestos.

### Precaución

Si una captura muestra una tarjeta con el **desajuste texto-audio** descrito en §V-E, no la uses sin advertirlo. Elige tarjetas correctas para la figura ilustrativa; el defecto se documenta con datos en la Sección V, no con una captura escogida a dedo.

---

## Formato de salida y requisitos de IEEE

- **PDF vectorial** es lo preferible y es lo que produce el script.
- Las tipografías van incrustadas (`pdf.fonttype = 42`), que es un requisito frecuente.
- Las figuras usan escala de grises: funcionan impresas en blanco y negro, que sigue siendo el supuesto por omisión en muchas publicaciones IEEE.
- Anchos: 3,5 pulgadas para una columna (Fig. 4) y 7,16 pulgadas para dos (Figs. 1, 2 y 3).
- Tipografía de 7–8 pt dentro de las figuras, coherente con el cuerpo del artículo a 8 pt.

Si la revista exige TIFF o EPS, convierte desde el PDF con Inkscape o Ghostscript sin pérdida de calidad vectorial.
