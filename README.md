# CRTStalker Bot

Bot online para detectar anuncios nuevos de material de vídeo analógico en España y avisar por Telegram.

## Fuentes iniciales

El bot **no hace scraping directo de Wallapop ni Vinted**. Consulta páginas públicas indexadas por buscadores mediante feeds RSS de resultados y filtra resultados relevantes.

Fuentes:
- Wallapop
- Vinted España

## Qué busca

- TV de tubo / CRT
- Sony PVM / BVM / Trinitron
- JVC TM / Ikegami / monitores broadcast y BNC
- sistemas antiguos de video wall / TV wall CRT
- Edirol V4 / V4EX / V8
- TBC / Time Base Corrector / frame synchronizer
- procesadores, matrices y scalers de vídeo
- cámaras VHS / VHS-C / S-VHS
- Video8 / Hi8 / Betacam / U-matic
- cámaras ENG / broadcast antiguas
- Super 8 / 8 mm / 16 mm

## Ejecución

GitHub Actions ejecuta el bot online cada 20 minutos. Tu ordenador puede estar apagado.

La primera ejecución guarda los resultados existentes y **no envía avisos**. A partir de la siguiente ejecución, solo avisa de enlaces nuevos.

## Secrets necesarios

En GitHub:

`Settings → Secrets and variables → Actions → New repository secret`

Crear:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

No guardes el token de Telegram dentro del código.
