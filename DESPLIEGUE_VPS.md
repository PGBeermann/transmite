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
                │ MediaMTX medios WebRTC  :8189 UDP/TCP ◄──────┼── video cifrado (DTLS-SRTP)
                └──────────────────────────────────────────────┘
```

| Puerto | Protocolo | Exposición | Configuración en Dokploy |
|---|---|---|---|
| **8080** | TCP/HTTP | Solo hacia Traefik | **Domains → Container Port = 8080**, con HTTPS activado |
| **8189** | UDP y TCP | Publicado en el host | Mapeado `8189:8189` en `docker-compose.yml`; ábralo en el firewall |
| 8889 | TCP/HTTP | Solo `127.0.0.1` dentro del contenedor | No se expone; se accede a través de `/clase/` |
| 9997 | TCP/HTTP | Solo `127.0.0.1` | No se expone |

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

3. En **Domains → Add Domain**:
   - Service Name: `clase`
   - Host: su dominio
   - Path: `/`
   - **Container Port: `8080`**
   - HTTPS: activado, con certificado Let's Encrypt
4. Pulse **Deploy**. La imagen descarga MediaMTX v1.21.1 durante la construcción.
5. Verifique que `https://su-dominio/salud` responde `ok`.

### Alternativa: tipo Application (Dockerfile)

1. Build Type: **Dockerfile**.
2. Configure las mismas variables de entorno.
3. **Domains:** Container Port `8080`.
4. **Advanced → Ports:** publique `8189 → 8189` con protocolo **UDP** y otra vez `8189 → 8189` con protocolo **TCP**.

## Uso en clase

1. El profesor abre `https://su-dominio/profesor.html` desde su computadora, con Chrome, Edge o Firefox de escritorio, e ingresa la contraseña.
2. Pulsa **Compartir pantalla**. Como la página está en HTTPS, el navegador permite capturar la pantalla.
3. Pulsa **Proyectar QR** o **Copiar enlace** para compartirlo por la plataforma del curso. Si configuró una clave de clase, el enlace la incluye (`?k=…`). Los estudiantes que entren sin el enlace verán una pantalla para escribir el código.
4. Al terminar, pulsa **Detener transmisión** y luego **Cerrar sesión**.

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

## Solución de problemas

| Síntoma | Causa y solución |
|---|---|
| La página carga y el panel dice «Transmitiendo», pero el estudiante no recibe video | El puerto **8189** está cerrado en el firewall de Hostinger o en `ufw`, o `CLASE_IP_PUBLICA` no es la IP pública correcta. Revise los registros del contenedor: MediaMTX indica qué candidatos anuncia |
| Error 502 en `/clase/…` | MediaMTX no arrancó. Revise los registros; el contenedor se reinicia solo si MediaMTX se detiene |
| El contenedor termina al iniciar con «Defina CLASE_…» | Falta una variable obligatoria |
| «Demasiados intentos» | Se superaron los 5 fallos en 10 minutos desde esa IP. Espere a que pase el bloqueo |
| Redes institucionales muy restrictivas no reciben video | Bloquean la salida al puerto 8189 (UDP y TCP). Haría falta un servidor TURN en el puerto 443, que no está incluido en esta versión |

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

## Referencias

- Dokploy, *Docker Compose → Domains*: <https://docs.dokploy.com/docs/core/docker-compose/domains>
- Dokploy, *Applications → Advanced (Ports)*: <https://docs.dokploy.com/docs/core/applications/advanced>
- MediaMTX: <https://mediamtx.org/docs>. Las variables de entorno `MTX_*` sustituyen cualquier clave del YAML.
- IETF RFC 9725 (WHIP); borrador `draft-ietf-wish-whep`.
- IETF RFC 6265bis (atributos `Secure`, `HttpOnly` y `SameSite` de las cookies); RFC 2104 (HMAC).
