# Clase en Vivo UNACHI

Transmisión de la pantalla del profesor a los estudiantes **dentro de la red Wi‑Fi del aula**, con latencia menor a 1 segundo (WebRTC). Los estudiantes solo necesitan un navegador y **no instalan nada**. La señal no sale de la red local y, después de la primera ejecución, no hace falta Internet.

```
Profesor (este equipo)                                   Estudiantes (misma Wi-Fi)
┌──────────────────────────────────────────┐            ┌────────────────────────┐
│ Navegador: http://localhost:8080/profesor │──WHIP──┐   │ http://IP:8080/        │
│   (captura de pantalla, se codifica 1 vez)│        │   │  (QR proyectado)       │
│ servidor_clase.py  :8080  páginas + estado│        ▼   │                        │
│ MediaMTX v1.21.1   :8889  WHIP/WHEP ──────┼──WHEP─────▶│ celulares, laptops,    │
│                    :8189  medios UDP/TCP  │            │ tabletas               │
└──────────────────────────────────────────┘            └────────────────────────┘
```

> **¿Transmitir desde un servidor en la nube (VPS con Dokploy)?** Vea [`DESPLIEGUE_VPS.md`](DESPLIEGUE_VPS.md): el mismo programa funciona en **modo VPS** (`--modo vps`) con HTTPS, contraseña del profesor y clave opcional para los estudiantes.

## Contenido

| Archivo | Función |
|---|---|
| `iniciar_clase.bat` | Arranque en Windows 10/11 (doble clic) |
| `iniciar_clase.sh` | Arranque en Linux/macOS (`./iniciar_clase.sh`) |
| `abrir_firewall.bat` / `.sh` | Abre los puertos solo para la subred local (se ejecuta **una vez**) |
| `servidor_clase.py` | Descarga e inicia MediaMTX, sirve las páginas y detecta la IP (solo biblioteca estándar) |
| `mediamtx.yml` | Configuración endurecida de MediaMTX |
| `web/profesor.html` | Panel del profesor: compartir pantalla, QR, espectadores y Mbps, participación y grabación |
| `web/profesor-sala.js` | Chat, manos, turno de palabra, mezcla de audio, ventana flotante y grabaciones (profesor) |
| `web/index.html` | Página del estudiante: video en vivo, chat, expresiones, mano, pedir la palabra y hablar |
| `web/comun.js` | Funciones compartidas (eventos en vivo, chat, expresiones) |
| `web/estilo.css` | Identidad visual UNACHI (verde Pantone 364 C, rojo Pantone 187 C) |
| `web/vendor/qrcode.js` | Generador de QR sin conexión (K. Arase, licencia MIT) |
| `mediamtx.vps.yml`, `Dockerfile`, `docker-compose.yml`, `.env.example` | Modo VPS (Dokploy/Docker); ver `DESPLIEGUE_VPS.md` |
| `web/login.html`, `web/entrar.html` | Acceso del profesor y de estudiantes en modo VPS |

## Requisitos

- **Python 3.8+** en el equipo del profesor. En Windows: `winget install -e --id Python.Python.3.12`.
- **Navegador** Chrome, Edge o Firefox actual para el profesor. Los estudiantes pueden usar cualquier navegador moderno, incluido Safari en iOS.
- **Internet solo la primera vez**, para descargar MediaMTX v1.21.1 desde GitHub (descarga de unos 20–25 MB comprimidos). Si no hay conexión en ese momento, descargue el archivo de <https://github.com/bluenviron/mediamtx/releases/tag/v1.21.1> y coloque `mediamtx.exe` (o `mediamtx`) dentro de una carpeta `mediamtx/` junto a este LEAME.

## Uso en clase

1. **Solo la primera vez:** ejecute `abrir_firewall.bat`; pedirá permisos de administrador.
2. Conecte el equipo a la **misma red Wi‑Fi** que los estudiantes.
3. Haga doble clic en **`iniciar_clase.bat`**. Se abrirá el panel del profesor en el navegador.
4. Pulse **Proyectar QR**. Los estudiantes escanean el código, que abre `http://IP-del-profesor:8080/`. Pulse clic o Esc para cerrar la proyección.
5. Pulse **Compartir pantalla** y elija la pantalla, ventana o pestaña que quiere mostrar.
6. Durante la clase:
   - **Cambiar ventana** cambia lo que se comparte; los estudiantes se reconectan solos en unos 2 segundos.
   - El recuadro **Estado** muestra cuántos espectadores hay y el ancho de banda en uso.
7. Para terminar, pulse **Detener transmisión** y cierre la ventana de consola (o pulse Ctrl+C).

## Participación de los estudiantes

La primera vez, cada estudiante escribe su nombre. El navegador lo recuerda para las clases siguientes y se puede cambiar en el chat.

| Función | Estudiante | Profesor (recuadro **Participación**) |
|---|---|---|
| **Chat** | Botón 💬. En la computadora el chat queda abierto a la derecha; en el celular, como panel deslizable | Lee y escribe a toda la clase, **elimina mensajes**, cierra o abre el chat y lo **descarga** en `.txt` |
| **Expresiones** | Botón 😀: 👍 De acuerdo · 👏 Aplausos · 😂 Risa · 😮 Sorpresa · ❤️ Me gusta · 🤔 Tengo una duda · 🐢 Más despacio · 🔁 ¿Puede repetir? | Aparecen flotando sobre la vista previa, con el nombre de quien las envía |
| **Mano levantada** ✋ | Levanta o baja la mano | Lista por orden de llegada, con **Bajar** y **Bajar todas** |
| **Pedir la palabra** 🎤 | Pide o cancela el turno | Lista por orden de llegada, con **Dar la palabra** y ✕ para descartar |
| **Hablar** | Cuando el profesor le da la palabra, pulsa **Activar micrófono**. Mientras habla, el sonido de la clase se silencia en su equipo para evitar eco. Termina con **Terminar de hablar** | Ve quién habla, cuánto tiempo y el nivel de su micrófono. **Quitar la palabra** corta el micrófono en el servidor aunque el navegador del estudiante no responda |

**Cómo llega la voz a todos.** El micrófono del estudiante llega al panel del profesor, que lo **mezcla con el audio de la clase**. Así lo escucha todo el grupo con la misma conexión de siempre, y queda en la grabación. Habla **una persona a la vez**: si da la palabra a otro estudiante, el turno anterior se cierra solo.

- El estudiante solo puede activar el micrófono si la clase se abre por **HTTPS**, como en el modo VPS. En el modo de aula (`http://IP:8080`) el navegador no permite usar el micrófono: el turno funciona igual, pero el estudiante habla en voz alta en el salón.
- **Use audífonos** mientras un estudiante habla, sobre todo si transmite el audio de su micrófono. Si lo escucha por parlantes, su micrófono lo recoge y se produce eco. Con la casilla **Escuchar aquí** puede dejar de oírlo en su equipo; los estudiantes lo siguen escuchando.
- El estudiante necesita pulsar **Activar sonido** una vez para oír la clase, porque el navegador no reproduce audio sin un toque del usuario. Cuando alguien tiene la palabra, en el video aparece un aviso con ese botón.

**Mientras comparte otra ventana**, el panel queda oculto. Para enterarse de lo que pasa:
- **⧉ Ventana flotante** (Chrome o Edge 116+): abre el recuadro de Participación en una ventana pequeña que queda siempre encima. Si comparte la **pantalla completa**, los estudiantes también la verán; para evitarlo, comparta solo la ventana de su presentación.
- **Sonido** al recibir una mano, un pedido de palabra o un mensaje (casilla activada por defecto) y **notificaciones del escritorio** (opcional).
- El título de la pestaña muestra cuántos avisos tiene pendientes.

## Grabación de la clase

En el recuadro **Grabación** del panel, pulse **● Iniciar grabación**.

- **Qué se graba:** lo mismo que reciben los estudiantes: la pantalla, el audio del profesor y la voz de quien tenga la palabra. El chat no se graba; descárguelo aparte en `.txt`.
- **Dónde se graba:** en el servidor, no en el navegador. Si el panel se cierra o el equipo se suspende, la grabación sigue.
- **Formato:** MP4 con video H.264 y audio Opus. Se reproduce en VLC, Chrome, Edge y Firefox. Para un reproductor que no admita Opus, conviértalo con: `ffmpeg -i clase.mp4 -c:v copy -c:a aac clase_aac.mp4`.
- **Aviso a los estudiantes:** ven la insignia **● GRABANDO** y un mensaje en el chat al iniciar y al terminar. Conviene informar al grupo antes de grabar.
- **Activar y desactivar** se hace en caliente: la transmisión no se interrumpe.
- **Cambiar ventana** inicia un archivo nuevo, y las grabaciones de más de 4 h se dividen en varios archivos.
- **Archivos:** el panel los lista con **Descargar** y **🗑 Eliminar**.
  - En el modo de aula también están en la carpeta `grabaciones/clase/` junto a este programa y nunca se borran solos.
  - En el modo VPS se borran automáticamente a los 30 días (`recordDeleteAfter` en `mediamtx.vps.yml`).
- **Códec:** VP8 no se puede grabar. Use H.264 (predeterminado), VP9 o AV1; si intenta grabar con VP8, el panel lo avisa.
- **Espacio en disco:** aproximadamente el bitrate del perfil por la duración. Por ejemplo, 1 h con el perfil Equilibrado (1,5 Mbps) ocupa unos 0,7 GB, y con Texto nítido (2,5 Mbps) unos 1,1 GB.

## Perfiles de calidad

| Perfil | Resolución | fps | Bitrate | Cuándo usarlo |
|---|---|---|---|---|
| Texto nítido | 1080p | 15 | 2,5 Mbps | Código fuente, fórmulas, hojas de cálculo |
| Equilibrado (predeterminado) | 720p | 20 | 1,5 Mbps | Diapositivas y uso general |
| Video/animación | 720p | 30 | 2,5 Mbps | Simulaciones o videos |
| Red saturada | 720p | 10 | 0,8 Mbps | Muchos estudiantes o una Wi‑Fi de 2,4 GHz congestionada |

**Tráfico total ≈ bitrate × número de espectadores.** Por ejemplo, 35 estudiantes con el perfil Equilibrado suman unos 53 Mbps de aire Wi‑Fi. Si puede, conecte el equipo del profesor al router por cable.

## Seguridad (configurada en `mediamtx.yml`)

- **Publicar** solo es posible desde el propio equipo del profesor (127.0.0.1 / ::1). Si un estudiante intenta transmitir, recibe `401 authentication error`.
- **Ver:** solo existe la ruta `clase`. Cualquier otra ruta se rechaza.
- **La API de control** solo escucha en `127.0.0.1`. El panel del profesor no se abre desde otros equipos (se redirige a la vista del estudiante).
- **Voz de los estudiantes (ruta `voz`):** MediaMTX solo la acepta desde `servidor_clase.py`. El servidor exige el **token del turno vigente** para publicar, y solo el profesor puede escucharla directamente. Al quitar la palabra, el token deja de valer y el servidor cierra la sesión en MediaMTX.
- **Chat y acciones:** solo se aceptan peticiones JSON del mismo origen, con límites de frecuencia (5 mensajes cada 10 s por estudiante). Todo el texto se muestra escapado, nunca como HTML. Las acciones de moderación, el turno de palabra, la grabación y la descarga de grabaciones o del chat son exclusivas del profesor.
- **Protocolos desactivados:** RTSP, HLS, SRT y MoQ. RTMP queda disponible solo para OBS local.
- **Firewall:** las reglas se limitan a `remoteip=localsubnet`.
- **Cifrado:** el medio WebRTC siempre va cifrado (DTLS‑SRTP). La señalización HTTP va en claro, lo que es aceptable en una LAN controlada. Para usar HTTPS, active `webrtcEncryption` con un certificado.

## Solución de problemas

| Síntoma | Causa probable y solución |
|---|---|
| El estudiante ve «No se alcanza el servidor del aula» | **Aislamiento de clientes (AP isolation)** en la Wi‑Fi institucional, o firewall. Pruebe `ping IP-del-profesor` desde otro equipo. Pida a TI una SSID o VLAN de aula sin aislamiento, o use un router propio. |
| La página carga pero el video no aparece | Está bloqueado el **UDP 8189**. Ejecute `abrir_firewall.bat`. MediaMTX también ofrece TCP 8189 como respaldo. |
| Windows no deja pasar nada aunque existan las reglas | Si alguna vez pulsó **Cancelar** en el aviso del firewall para `python.exe` o `mediamtx.exe`, Windows creó reglas de **bloqueo** que tienen prioridad. Bórrelas en `wf.msc` → *Reglas de entrada*. |
| El QR muestra una IP que no es la de la Wi‑Fi (VPN, Hyper‑V, VirtualBox) | Elija la IP correcta en el selector del panel, o inicie con `iniciar_clase.bat --ip 192.168.x.y`. Si el video no conecta, añada esa IP en `webrtcAdditionalHosts` de `mediamtx.yml`. |
| «El puerto 8889 ya está en uso» | Hay otra instancia de MediaMTX abierta. Ciérrela desde el Administrador de tareas. |
| El botón «Compartir pantalla» está deshabilitado | El panel debe abrirse como `http://localhost:8080/profesor.html` (el navegador solo permite capturar la pantalla en localhost o HTTPS). |
| En iPhone el video no pasa a pantalla completa | Use el botón **Pantalla completa**: en iOS usa el reproductor nativo. |
| El estudiante tiene la palabra pero no aparece «Activar micrófono» | La página está en `http://` (modo aula). El navegador solo permite el micrófono por HTTPS; en el aula, el estudiante habla en voz alta. |
| «No se permitió usar el micrófono» | El estudiante rechazó el permiso. Debe habilitarlo en el ícono del candado de la barra de direcciones y pulsar de nuevo **Activar micrófono**. |
| Se oye eco cuando habla un estudiante | El micrófono del profesor recoge los parlantes. Use audífonos o desmarque **Escuchar aquí**. |
| Los estudiantes no oyen al compañero que habla | Cada uno debe pulsar **Activar sonido** una vez. En el panel, el medidor junto a «tiene la palabra» debe moverse cuando el estudiante habla. |
| La grabación quedó sin imagen | La transmisión usaba VP8. Elija H.264 en «Códec de video». |

## Alternativa: transmitir con OBS Studio

Use OBS 30 o superior. En *Ajustes → Emisión*, elija el servicio **WHIP** con el servidor `http://localhost:8889/clase/whip`. En *Salida*, use x264, perfil `baseline`, tune `zerolatency`, intervalo de fotogramas clave de 1 s y 1500–2500 kbps. Los estudiantes siguen usando el mismo QR y el panel indica «Transmisión externa detectada».

## Logotipo institucional

Copie el archivo oficial **`logo-unachi.png`** en la carpeta `web/`. Si no existe, el encabezado se muestra sin logotipo. El paquete no reproduce el logotipo, conforme al *Manual de Imagen Institucional* de la UNACHI (Consejo Administrativo N.° 12‑2014), que regula su área de reserva y sus proporciones. Los colores HEX (#299100, #C41237) son la conversión CMYK→RGB de los Pantone oficiales. Para piezas de alto perfil conviene confirmarlos con Relaciones Públicas.

## Pruebas realizadas

Se hicieron el 23‑sep‑2026 con **MediaMTX v1.21.1 real** y Chromium en modo automatizado:

- La configuración carga sin errores.
- El profesor publica su pantalla por WHIP y el estudiante recibe video 1280×720 por WHEP.
- El contador de espectadores y el cálculo de Mbps funcionan.
- Al pulsar «Detener», el estudiante vuelve a la pantalla de espera.
- Un intento de publicar desde otra IP de la LAN recibe **401**, y una ruta distinta de `clase` se rechaza.
- La API no es accesible desde la LAN.
- El QR se decodificó correctamente con OpenCV.
- Ctrl+C cierra también MediaMTX.

Los scripts `.bat` no pudieron ejecutarse en Windows durante las pruebas. Se revisaron manualmente y usan finales de línea CRLF.

## Pruebas de chat, palabra y grabación (16‑nov‑2026)

Se probaron con **MediaMTX v1.21.1 real** y Chromium automatizado (Playwright), con micrófono simulado (tono de prueba) y la pantalla simulada con un lienzo animado. Se usaron un profesor y dos estudiantes, en los modos VPS (con contraseña y clave de clase) y aula.

- **Chat:** los mensajes llegan a todos. Un mensaje con `<b>` se muestra como texto, no como HTML.
- **Expresiones:** llegan al profesor y a los compañeros.
- **Mano y pedido de palabra:** aparecen en el panel por orden de llegada y con el contador correcto.
- **Turno de palabra:**
  - El estudiante recibe el aviso, activa el micrófono y el panel muestra «Micrófono conectado».
  - El **otro estudiante recibe la voz en la transmisión**: el nivel de audio medido pasa de 0 a 128 mientras habla y vuelve a 0 al quitarle la palabra.
  - Al quitar la palabra, MediaMTX no conserva ninguna sesión de voz.
- **Grabación:**
  - Se activó y desactivó durante la transmisión sin cortar a los estudiantes.
  - El MP4 (H.264 1280×720 + Opus) está en silencio antes del turno (−91 dB) y contiene la voz del estudiante durante él (0 dB).
  - El profesor descarga el archivo y un estudiante recibe **403**.
  - Con VP8 el panel avisa que no se puede grabar.
- **Seguridad:** sin sesión, `/eventos`, `/api/accion` y `/voz/whip` (sin token) responden **401**; `/api/grabaciones` responde **403**.
- **Modo aula (http):** el estudiante recibe el turno con la indicación de hablar en voz alta. El audio del micrófono del profesor pasa por la mezcla.
- **Cambiar ventana:** los estudiantes vuelven a la imagen en unos 2 s. Antes de esta versión tardaban unos 10 s, hasta que MediaMTX cerraba la sesión anterior; ahora el servidor les indica que se reconecten.
- **Ventana flotante:** se abre con el chat y vuelve al panel al cerrarla.
- **Relevo de turno:** al dar la palabra a otro estudiante, el turno anterior se cierra y un tercero escucha al nuevo.
- **Página cerrada:** si quien tiene la palabra cierra la página de golpe, el turno se libera y su sesión de voz se cierra en unos 10 s.

## Referencias

- MediaMTX: <https://github.com/bluenviron/mediamtx> (licencia MIT). Documentación de WebRTC, WHIP y WHEP en <https://mediamtx.org/docs>.
- IETF RFC 9725, *WebRTC‑HTTP Ingestion Protocol (WHIP)*, 2025. WHEP: borrador `draft-ietf-wish-whep`.
- W3C, *Screen Capture* (`getDisplayMedia`), que requiere un contexto seguro.
- K. Arase, *QR Code Generator for JavaScript* v2.0.4 (MIT).
- W3C, *Media Capture and Streams* (`getUserMedia`) y WHATWG HTML, *Server-sent events* (`EventSource`).
- W3C Community Group, *Document Picture-in-Picture* (ventana flotante, Chrome/Edge 116+).
- MediaMTX, *Record streams to disk* y API v3 (`/v3/config/paths/patch`, `/v3/webrtcsessions/kick`): <https://mediamtx.org/docs>.
