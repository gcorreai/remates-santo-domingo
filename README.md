# Direcciones de remates · Santo Domingo

Directorio estático mínimo: siete direcciones y enlaces a Google Maps y a las fichas originales de MisRemates. Sin fotografías, descripciones ni otros campos de las fichas. No usa JavaScript, fuentes remotas, analítica ni dependencias de ejecución.

## Sitio

https://gcorreai.github.io/remates-santo-domingo/

GitHub Pages publica únicamente `docs/`, desde `main` (fuente de rama). Las pruebas y herramientas no forman parte del sitio servido.

## Verificación antes de publicar

```sh
python3 -m unittest discover -s tests -v
node tools/verify_browser.mjs
git diff --check
```

Las pruebas de contrato contrastan las siete direcciones y los catorce destinos/etiquetas exactos, comprueban HTML balanceado, referencias accesibles y ausencia de contenido adicional en las tarjetas. La prueba de navegador requiere Node con WebSocket nativo y Chromium instalado; comprueba vistas de 320, 390, 768 y 1440 px, sin desbordamiento horizontal y con enlaces de al menos 44 px de alto.

Para comprobar el contenido servido por HTTPS:

```sh
SITE_URL=https://gcorreai.github.io/remates-santo-domingo/ python3 -m unittest discover -s tests -v
SITE_URL=https://gcorreai.github.io/remates-santo-domingo/ node tools/verify_browser.mjs
```

Para previsualizar localmente: `python3 -m http.server 8000 --directory docs`, y abrir `http://localhost:8000`.

## Mantenimiento

Modificar solo direcciones y enlaces autorizados. No añadir imágenes, identificadores visibles ni detalles de fichas. Los enlaces externos son responsabilidad de sus plataformas y pueden cambiar; este directorio no indica vigencia ni disponibilidad. Ejecutar las comprobaciones antes de cada commit/push y verificar después la compilación de Pages y el contenido HTTPS. No hay actualización automática ni gate de pruebas remoto para la publicación desde rama.
