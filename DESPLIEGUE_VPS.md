# Clase en Vivo UNACHI: despliegue en un VPS con Dokploy

Esta guía explica cómo ejecutar la aplicación en un servidor en la nube, por ejemplo un VPS de Hostinger administrado con Dokploy. Así los estudiantes pueden ver la clase desde cualquier red con Internet. El modo de aula (LAN), descrito en `LEAME.md`, no cambia y se sigue iniciando con `iniciar_clase.bat` o `iniciar_clase.sh`.

## Arquitectura

```
                     Internet (HTTPS 443)
Profesor ───────────────┐                      ┌──────────── Estudiantes
(navegador, Chrome)     ▼                      ▼            (cualquier red)
                ┌───────────────── VPS ────────────────────────┐
                │ Traefik (Dokploy) :443 ──► contenedor :8080  │
                │   servidor_clase.py                          │
                │     /profesor.html  (requiere contraseña)    │
                │     /               (clave de clase opcional)│
                │     /clase/whip  ──► MediaMTX 127.0.0.1:8889 │
                │     /clase/whep  ──►        (sólo local)     │
                │     /voz/whip    ──► voz del estudiante con  │
                │     /voz/whep    ──►   la palabra (token)    │
                │     /eventos     chat, manos, palabra (SSE)  │
                │   /app/grabaciones  ◄── MP4 (volumen)        │
                │ MediaMTX medios WebRTC  :8189 UDP/TCP ◄──────┼── video cifrado (DTLS-SRTP)
                └──────────────────────────────────────────────┘
```

| Puerto | Protocolo | Exposición | Configuración en Dokploy |
|---|---|---|---|
| **8080** | TCP/HTTP | Solo hacia Traefik | **Domains → Container Port = 8080**, con HTTPS activado |
| **8189** | UDP y TCP | Publicado en el host | Mapeado `8189:8189` en `docker-compose.yml`; ábralo en el firewall |
| 8889 | TCP/HTTP | Solo `127.0.0.1` dentro del contenedor | No se expone; se accede a través de `/clase/` |
| 9997 | TCP/HTTP | Solo `127.0.0.1` | No se expone |

Las funciones de participación (chat, expresiones, mano y turno de palabra) y la voz de los estudiantes viajan por los mismos puertos: 443 (HTTPS) para la señalización y los eventos, y 8189 para el audio. **No hay que abrir puertos nuevos.**

## Cambios respecto al modo LAN

| Aspecto | LAN (aula) | VPS |
|---|---|---|
| Acceso al panel del profesor | Solo desde `localhost` | **Contraseña** (`CLASE_PASSWORD_PROFESOR`). La sesión dura 12 h, la cookie es `HttpOnly`, `Secure` y firmada con HMAC‑SHA256, y hay un límite de 5 intentos fallidos cada 10 min por IP |
| Publicación (WHIP) | MediaMTX solo acepta 127.0.0.1 | El proxy exige la sesión del profesor o el token de OBS. MediaMTX solo escucha en 127.0.0.1 |
| Visualización (WHEP) | Abierta dentro de la LAN | Abierta, o protegida con la **clave de la clase** (`CLASE_CLAVE_ESTUDIANTES`). El QR del panel ya incluye la clave |
| Señalización | `http://IP:8889` | Mismo origen por **HTTPS** (`/clase/…`), sin contenido mixto ni CORS |
| IP anunciada para el video | Interfaces de la LAN | IP pública del VPS (`CLASE_IP_PUBLICA`) |
| RTMP | Activo solo para uso local | Desactivado. OBS publica por WHIP con token |

## Requisitos

1. Un VPS con Dokploy instalado y un **dominio o subdominio** que apunte a la IP del VPS, por ejemplo un registro A `clase.midominio.edu.pa → 203.0.113.10`.
2. Los puertos **8189/UDP y 8189/TCP abiertos**:
   - En el panel de Hostinger: *VPS → Seguridad → Firewall*.
   - En `ufw`, si lo usa: `sudo ufw allow 8189/udp && sudo ufw allow 8189/tcp`.

## Despliegue en Dokploy (tipo Docker Compose, recomendado)

1. En su proyecto de Dokploy, vaya a **Create Service → Compose**.
   - Proveedor: GitHub. Repositorio: `PGBeermann/transmite`. Rama: la que contenga estos cambios.
   - Compose Path: `./docker-compose.yml`.
2. En **Environment**, copie las variables de `.env.example` con sus valores reales:

   | Variable | Obligatoria | Ejemplo o nota |
   |---|---|---|
   | `CLASE_URL_PUBLICA` | Sí | `https://clase.midominio.edu.pa` |
   | `CLASE_IP_PUBLICA` | Sí | IP pública del VPS, por ejemplo `203.0.113.10` |
   | `CLASE_PASSWORD_PROFESOR` | Sí | Mínimo 10 caracteres; conviene una frase larga |
   | `CLASE_CLAVE_ESTUDIANTES` | No | Por ejemplo `QUIM2026`. Si queda vacía, cualquiera con el enlace puede ver la clase |
   | `CLASE_TOKEN_OBS` | No | Token para OBS Studio (WHIP) |
   | `CLASE_SECRETO` | Recomendada | `python3 -c "import secrets; print(secrets.token_hex(32))"`. Sin esta variable, las sesiones se cierran en cada redeploy |
| `CLASE_DIR_GRABACIONES` | No | Carpeta de las grabaciones dentro del contenedor. Predeterminada: `/app/grabaciones` |

3. En **Domains → Add Domain**:
   - Service Name: `clase`
   - Host: su dominio
   - Path: `/`
   - **Container Port: `8080`**
   - HTTPS: activado, con certificado Let's Encrypt
4. **Grabaciones:** `docker-compose.yml` ya declara el volumen con nombre `grabaciones` montado en `/app/grabaciones`, así que los archivos sobreviven a cada despliegue. Dokploy puede respaldarlo con *Volume Backups*.
5. Pulse **Deploy**. La imagen descarga MediaMTX v1.21.1 durante la construcción.
6. Verifique que `https://su-dominio/salud` responde `ok`.

### Alternativa: tipo Application (Dockerfile)

1. Build Type: **Dockerfile**.
2. Configure las mismas variables de entorno.
3. **Domains:** Container Port `8080`.
4. **Advanced → Ports:** publique `8189 → 8189` con protocolo **UDP** y otra vez `8189 → 8189` con protocolo **TCP**.
5. **Advanced → Volumes → Add Volume:** tipo *Volume Mount*, nombre `transmite-grabaciones`, **Mount Path `/app/grabaciones`**. Sin este volumen, las grabaciones se pierden en cada despliegue.

## Uso en clase

1. El profesor abre `https://su-dominio/profesor.html` desde su computadora, con Chrome, Edge o Firefox de escritorio, e ingresa la contraseña.
2. Pulsa **Compartir pantalla**. Como la página está en HTTPS, el navegador permite capturar la pantalla.
3. Pulsa **Proyectar QR** o **Copiar enlace** para compartirlo por la plataforma del curso. Si configuró una clave de clase, el enlace la incluye (`?k=…`). Los estudiantes que entren sin el enlace verán una pantalla para escribir el código.
4. Durante la clase, el recuadro **Participación** muestra el chat, las manos levantadas y los pedidos de palabra. Con **Dar la palabra**, el estudiante activa su micrófono y toda la clase lo escucha; como la página está en HTTPS, el navegador del estudiante lo permite. Para verlo mientras comparte otra ventana, use **⧉ Ventana flotante**. Los detalles están en `LEAME.md`, sección «Participación de los estudiantes».
5. Para grabar, pulse **● Iniciar grabación**. Los estudiantes ven el aviso «GRABANDO». Las grabaciones se descargan desde el mismo panel y se borran solas a los 30 días.
6. Al terminar, pulsa **Detener transmisión** y luego **Cerrar sesión**.

**OBS Studio:** en *Ajustes → Emisión*, elija Servicio **WHIP**, servidor `https://su-dominio/clase/whip`, y en *Bearer Token* escriba el valor de `CLASE_TOKEN_OBS`.

## Capacidad y ancho de banda

MediaMTX reenvía el video sin volver a codificarlo, así que el procesador del VPS casi no trabaja. El límite real es el **ancho de banda de subida del VPS**:

> tráfico de salida ≈ bitrate del perfil × número de estudiantes

| Perfil | Bitrate | 30 estudiantes | 60 estudiantes |
|---|---|---|---|
| Red saturada | 0,8 Mbps | 24 Mbps | 48 Mbps |
| Equilibrado | 1,5 Mbps | 45 Mbps | 90 Mbps |
| Texto nítido | 2,5 Mbps | 75 Mbps | 150 Mbps |

Una clase de 1 h con 40 estudiantes en el perfil Equilibrado transfiere unos 27 GB. Compare esa cifra con la cuota mensual de tráfico de su plan.

**Turno de palabra:** la voz del estudiante (≈ 64 kbps) va del estudiante al servidor y del servidor al profesor; desde ahí viaja dentro de la transmisión normal, así que no aumenta el tráfico hacia los demás estudiantes.

**Grabación:** ocupa en disco aproximadamente el bitrate del perfil por la duración. Por ejemplo, 1 h en el perfil Equilibrado ocupa unos 0,7 GB. Revise el espacio libre del VPS con `df -h`. El borrado automático (30 días) se cambia con `recordDeleteAfter` en `mediamtx.vps.yml`.

## Solución de problemas

| Síntoma | Causa y solución |
|---|---|
| La página carga y el panel dice «Transmitiendo», pero el estudiante no recibe video | El puerto **8189** está cerrado en el firewall de Hostinger o en `ufw`, o `CLASE_IP_PUBLICA` no es la IP pública correcta. Revise los registros del contenedor: MediaMTX indica qué candidatos anuncia |
| Error 502 en `/clase/…` | MediaMTX no arrancó. Revise los registros; el contenedor se reinicia solo si MediaMTX se detiene |
| El contenedor termina al iniciar con «Defina CLASE_…» | Falta una variable obligatoria |
| «Demasiados intentos» | Se superaron los 5 fallos en 10 minutos desde esa IP. Espere a que pase el bloqueo |
| Redes institucionales muy restrictivas no reciben video | Bloquean la salida al puerto 8189 (UDP y TCP). Haría falta un servidor TURN en el puerto 443, que no está incluido en esta versión |
| El chat o las manos no se actualizan | El proxy está acumulando los eventos en un búfer. Traefik no lo hace por defecto; si hay otro proxy delante (Cloudflare, por ejemplo), desactive el búfer para `/eventos`. El servidor ya envía `X-Accel-Buffering: no` |
| El estudiante pulsa «Activar micrófono» y el panel sigue en «Esperando el micrófono» | El puerto 8189 de ese estudiante está bloqueado; si su red bloquea el 8189, tampoco recibe el video. Revise también el permiso del micrófono en el navegador |
| Las grabaciones desaparecen tras un redeploy | Falta el volumen en `/app/grabaciones` (ver arriba) |

## Pruebas realizadas (30‑sep‑2026)

Se probó con MediaMTX v1.21.1 real y Chromium automatizado (Playwright). La captura de pantalla se simuló con un lienzo animado.

- Sin sesión, `/profesor.html` redirige a `/login.html`; `/api/estado` responde 403; `POST /clase/whip` responde 401. Sin la clave de clase, `POST /clase/whep` responde 401.
- Con la contraseña correcta, el panel carga y el QR contiene `https://…/?k=CLAVE`. Al sexto intento fallido desde una misma IP, la respuesta es **429**.
- Una cookie falsificada o con la fecha de vencimiento alterada se rechaza (403).
- El token de OBS en `Authorization: Bearer` permite publicar. `publisher.js` no está disponible para los estudiantes. Las rutas distintas de `/clase/` responden 404 y no se listan directorios.
- **Prueba completa:** el profesor inicia sesión y publica por WHIP a través del proxy. El estudiante entra con el enlace del QR y recibe video **1280×720** por WHEP. El panel muestra 1 espectador y unos 0,5 Mbps.
- MediaMTX quedó escuchando la señalización solo en `127.0.0.1:8889`.
- El **modo LAN** se verificó de nuevo sin cambios de comportamiento (el profesor publica en `localhost` y el estudiante recibe 1280×720).
- La imagen Docker no se pudo construir en el entorno de prueba porque no había acceso a Docker Hub. El `Dockerfile` usa solo la imagen oficial `python:3.12-slim` y el binario oficial de MediaMTX.

## Pruebas de las funciones de participación (16‑nov‑2026)

Se probaron en modo VPS, con contraseña y clave de clase, usando MediaMTX v1.21.1 real y Chromium automatizado. Los resultados detallados están en `LEAME.md`, sección «Pruebas de chat, palabra y grabación».

- **Chat, expresiones, manos y pedidos de palabra:** se reciben en tiempo real.
- **Voz del estudiante:** la reciben los demás dentro de la transmisión y queda en la grabación.
- **Quitar la palabra:** cierra la sesión de voz en MediaMTX.
- **Grabación:** se descarga con la sesión del profesor; un estudiante recibe 403.
- **Rutas nuevas sin sesión** (eventos, acciones, voz sin token): responden 401 o 403.

## Referencias

- Dokploy, *Docker Compose → Domains*: <https://docs.dokploy.com/docs/core/docker-compose/domains>
- Dokploy, *Applications → Advanced (Ports)*: <https://docs.dokploy.com/docs/core/applications/advanced>
- MediaMTX: <https://mediamtx.org/docs>. Las variables de entorno `MTX_*` sustituyen cualquier clave del YAML.
- IETF RFC 9725 (WHIP); borrador `draft-ietf-wish-whep`.
- IETF RFC 6265bis (atributos `Secure`, `HttpOnly` y `SameSite` de las cookies); RFC 2104 (HMAC).
