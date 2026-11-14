# Direcciones de remates · Santo Domingo

Shortlist estática mínima: dirección, Google Maps cuando la ficha lo proporciona y enlace a la ficha original de MisRemates. Sin fotos, ID/rol visible, descripciones, fecha, mínimo, causa, deudas ni otros datos de las fichas. Sin scraping, geocodificación externa, JavaScript del sitio, analítica ni assets remotos.

## Sitio y archivos

https://gcorreai.github.io/remates-santo-domingo/

GitHub Pages publica solo `docs/`, desde `main:/docs`. La programación queda en Hermes: no hay workflows propios ni cron de GitHub. Esta implementación no modifica el cron ni accede a Obsidian.

- `data/catalog.json`: catálogo público mínimo, inicialmente siete registros; IDs solo para deduplicar (también son accesibles en el repositorio público y en los href originales).
- `tools/update_catalog.py`: actualizador/generador offline, Python 3 y biblioteca estándar, Linux (`fcntl`). No hace commit, push ni llamadas de red.
- `tools/index.template.html` y `docs/styles.css`: presentación. No editar manualmente las tarjetas de `docs/index.html`.
- `tests/fixtures/seven.html`: snapshot de las siete tarjetas originales para verificar regeneración byte a byte.

## Comando y esquema de entrada

Desde el repositorio:

```sh
python3 tools/update_catalog.py add /ruta/privada/lote.json
# Sobre una copia temporal del repo:
python3 tools/update_catalog.py add /ruta/privada/lote.json --root /ruta/copia
```

El lote es un array JSON UTF-8. Cada objeto debe tener **exactamente** estas cuatro claves:

```json
[
  {
    "id": "142172",
    "address": "LAS GAVIOTAS 182",
    "maps_url": "https://www.google.com/maps/search/?api=1&query=-33.692366%2C-71.636694",
    "source_url": "https://www.misremates.cl/remate/casa-las-gaviotas-182-santo-domingo-142172"
  }
]
```

- `id`: string decimal positivo de la ficha, nunca un rol.
- `address`: solo dirección en mayúsculas. Alcance conservador: LAS GAVIOTAS, LAS TORCAZAS, LOS MIRLOS, LOS ALBATROS, LAS GARZAS. Número; opcionalmente `DPC número` o `DP letra número` y `BD número`; también `MZ letra LT número`. El slug de la ficha debe terminar en esa misma dirección, `santo-domingo` e ID. Una dirección/formato distinto se detiene para revisión, no se corrige ni amplía por inferencia. Cron debe comprobar la comuna en la ficha legible: el slug no demuestra por sí solo la ubicación real.
- `source_url`: HTTPS, host exacto `www.misremates.cl`, ruta `/remate/slug-ID`, sin query, fragmento, credenciales ni puerto.
- `maps_url`: URL **exacta copiada del enlace de la ficha**, sin construirla a partir de coordenadas deducidas. Allowlist conservadora: `https://www.google.com/maps/search/?api=1&query=latitud%2Clongitud` (también coma literal). Sin parámetros adicionales, puertos ni otros hosts/rutas. Si existe otra forma de enlace, detener y avisar a Metis para revisar el validador: no convertirla ni poner null para eludirlo. Si realmente no existe enlace Maps, usar JSON `null`; aparecerá «Google Maps no disponible en la ficha», sin geocodificación externa.

No se normalizan ni reescriben las URLs. Un ID repetido con los cuatro valores idénticos es un no-op; distinto contenido con el mismo ID es error, incluso dentro del lote. El orden anterior se conserva y lo nuevo se agrega al final. Salida: `added=N total=N`; éxito 0, validación/I/O 2. Un lote inválido se rechaza completo antes de escribir el catálogo o HTML. `[]` regenera sin añadir.

El comando serializa actualizaciones con `.local/update.lock`, prepara ambos archivos y los reemplaza individualmente, con recuperación de errores ordinarios de escritura. No es una transacción atómica de dos archivos frente a caída del proceso/equipo: conservar el lote y repetirlo antes de publicar, ejecutar pruebas y revisar ambos archivos. No ejecutar procesos Git de publicación en paralelo; el bloqueo del helper no cubre Git.

## Procedimiento para el cron de Hermes (a incorporar por Metis)

1. Comprobar rama `main`, árbol limpio y sincronizado (`git pull --ff-only`). Ante cambios ajenos, detener la parte pública; nunca reset/clean ni sobrescribirlos.
2. Investigar únicamente dentro del alcance autorizado, sin scraping ni otros portales. Procesar toda propiedad legible que cumpla Santo Domingo/calles y no esté procesada/excluida. Mantener el registro privado de exclusiones/procesados en el flujo privado; este helper no lo conoce. Actualizar idempotentemente la shortlist privada de Obsidian por el mecanismo privado de Hermes. **No guardar notas privadas ni el informe detallado en este repositorio.**
3. **Antes de publicar**, comprobar que la lista completa sigue siendo una shortlist reducida y revisar que los términos vigentes de https://www.misremates.cl/terminos no cambiaron. Los consultados con actualización 3-11-2026 permiten consulta personal, enlazar una ficha o citar un dato puntual, pero prohíben republicar el catálogo o una parte importante sin autorización. No existe aquí un umbral jurídico numérico. Si el crecimiento o los términos hacen dudosa la republicación, **detener la parte pública y avisar a Metis para pedir autorización escrita**; la lista privada puede actualizarse. El helper no decide esta evaluación jurídica ni sustituye esa comprobación.
4. Preparar un lote fuera del repo con solo los cuatro campos. Comprobar legibilidad, comuna, calle y que Maps procede literalmente de la ficha. Ejecutar primero en una copia temporal (`--root`), revisar el resultado, después ejecutar en el repo. Un conflicto no se resuelve cambiando el ID: detener y consultar a Metis.
5. Ejecutar pruebas, revisar `git diff -- data/catalog.json docs/index.html` y confirmar que no se borró nada ni aparecieron datos adicionales. No editar HTML a mano para salvar validaciones.
6. Solo con las verificaciones anteriores y la autorización vigente: `git add data/catalog.json docs/index.html`; si no hay diferencias staged, terminar sin commit; en caso contrario commit descriptivo y `git push origin main`. Sin force push. Si hubo error de publicación, conservar el lote y el estado para reintento sin duplicados; no marcar la parte pública como publicada hasta verificarla.
7. Verificar SHA remoto, build de Pages y contenido HTTPS con los comandos siguientes. Informar a Metis de altas, omitidos/excluidos, conflictos o detención pública. No exponer los detalles privados en el informe público.

## Pruebas y verificación

```sh
python3 -m unittest discover -s tests -v
node tools/verify_browser.mjs
git diff --check
```

Las pruebas ejecutan el comando real en copias temporales: siete registros originales y sus URLs exactas, idempotencia, conflictos sin mutación, esquema mínimo, allowlist de URLs, dirección/comuna no coincidente, Maps null, ausencia de fotos/IDs/detalles visibles, preparación de salida fallida y bloqueo de concurrencia. La suite pública compara todo el catálogo y fija los siete originales. Las pruebas del actualizador usan fixtures independientes y siguen funcionando al crecer el catálogo.

El navegador requiere Node con WebSocket nativo y Chromium instalado. Revisa vistas de 320, 390, 768 y 1440 px sin desbordamiento y enlaces de al menos 44 px; cuenta tarjetas y enlaces según el catálogo, incluyendo Maps null.

Después de publicar:

```sh
SITE_URL=https://gcorreai.github.io/remates-santo-domingo/ python3 -m unittest discover -s tests -v
SITE_URL=https://gcorreai.github.io/remates-santo-domingo/ node tools/verify_browser.mjs
# Con gh disponible y autenticado (o API autenticada equivalente):
gh api repos/gcorreai/remates-santo-domingo/pages
gh api repos/gcorreai/remates-santo-domingo/pages/builds/latest
```

Exigir `status: built`, fuente `main:/docs`, commit esperado y sin error. Si Pages tarda, esperar y repetir; nunca confundir push con publicación verificada. Para previsualizar: `python3 -m http.server 8000 --directory docs`.

Los enlaces externos pueden cambiar; el directorio no asegura vigencia ni disponibilidad. No hay gate de pruebas remoto: la publicación desde rama exige ejecutar este procedimiento en Hermes.
