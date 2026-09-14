# AI Sentinel: Monitor de Gobernanza, Seguridad y Pensadores de la IA

Una aplicación web local interactiva y ligera diseñada para seguir de forma rigurosa las noticias, debates éticos, políticas públicas y riesgos existenciales de la Inteligencia Artificial, con foco en **Yuval Noah Harari**, **Geoffrey Hinton**, **Yoshua Bengio** y **Yann LeCun**.

## 🚀 Inicio Rápido (Windows)

Simplemente haz doble clic en el archivo:
```
iniciar_dashboard.bat
```
Esto abrirá automáticamente tu navegador en `http://localhost:8000`.

O desde PowerShell / CMD:
```bash
cd "C:\Users\alber\.gemini\antigravity\scratch\ai-governance-dashboard"
python app.py
```

---

## 🎯 Temas y Pensadores Cubiertos

1. **Yuval Noah Harari**:
   - Impacto en la democracia y la manipulación social.
   - Su tesis en *Nexus*: la IA como sistema inorgánico capaz de hackear el sistema operativo de la civilización (el lenguaje).
2. **Geoffrey Hinton & Yoshua Bengio ("Padrinos de la IA")**:
   - Advertencias sobre la pérdida de control, rebelión de agentes y riesgos existenciales.
   - Tratados internacionales de supervisión y pruebas de seguridad obligatorias.
3. **Yann LeCun (Tercer "Padrino" - Meta)**:
   - Postura abierta y crítica contra el catastrofismo (*open source* vs. monopolios corporativos).
4. **Gobernanza y Leyes Globales**:
   - *EU AI Act* (Ley de Inteligencia Artificial de la UE), Institutos de Seguridad de IA (EE.UU., Reino Unido), cumbres multilaterales y recomendaciones de la OCDE.
5. **Boletines y Think Tanks Especializados**:
   - *Import AI* (Jack Clark)
   - *AI Snake Oil* (Universidad de Princeton)
   - *Future of Life Institute (FLI)*
   - *Center for Humane Technology (Tristan Harris)*
   - *Alignment Forum* (Seguridad técnica)

---

## 🛠️ Características de la Interfaz

- **Tarjetas de Pensadores**: Clic para aislar en 1 segundo las noticias y declaraciones de Harari, Hinton, Bengio o LeCun.
- **Filtros Temáticos**: Gobernanza, Seguridad y Riesgo, Sociedad y Democracia, Código Abierto, Newsletters.
- **Buscador en Tiempo Real**: Filtrado instantáneo por palabras clave (presiona `/` en el teclado para buscar).
- **Vista Rápida Modal**: Lectura del extracto en un diálogo limpio sin salir de la app.
- **Guardados / Favoritos**: Guarda artículos interesantes para leer más tarde (se mantienen guardados en tu navegador).
- **Modo Oscuro / Claro**: Selector integrado con detección de preferencia del sistema.
- **Caché Inteligente**: Almacena en `cache.json` para carga ultrarrápida sin sobrecargar las fuentes originales. Botón de actualización manual disponible.
