#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clase en Vivo UNACHI — orquestador del aula.

Funciones:
  1. Descarga (una sola vez) MediaMTX para el sistema operativo del profesor.
  2. Inicia MediaMTX con ./mediamtx.yml.
  3. Sirve las páginas web del aula (profesor y estudiantes) en el puerto 8080.
  4. Expone /config.js (IP de la LAN, puertos) y /api/estado (espectadores).
  5. Abre el panel del profesor en el navegador y detiene todo con Ctrl+C.

Modos de operación:
  lan (predeterminado)  El profesor ejecuta todo en su equipo; los estudiantes
                        se conectan por la Wi-Fi del aula (sin cambios).
  vps                   Servidor en la nube detrás de un proxy HTTPS (Traefik /
                        Dokploy). El panel del profesor exige contraseña, la
                        señalización WebRTC viaja por el mismo origen HTTPS
                        (/clase/whip, /clase/whep) y MediaMTX sólo escucha en
                        127.0.0.1. Variables de entorno: ver .env.example.

Sólo usa la biblioteca estándar de Python 3.8+.
Uso:  python servidor_clase.py [--modo lan|vps] [--ip 192.168.1.50]
                               [--puerto-web 8080] [--sin-navegador]
                               [--sin-mediamtx]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import http.client
import http.server
import io
import json
import secrets
import os
import platform
import shutil
import signal
import socket
import socketserver
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from pathlib import Path

MEDIAMTX_VERSION = "v1.21.1"
RUTA_STREAM = "clase"
PUERTO_WEBRTC = 8889
PUERTO_ICE = 8189
API_MEDIAMTX = "http://127.0.0.1:9997"

BASE = Path(__file__).resolve().parent
DIR_WEB = BASE / "web"
DIR_BIN = BASE / "mediamtx"
CONFIG_MTX = BASE / "mediamtx.yml"
CONFIG_MTX_VPS = BASE / "mediamtx.vps.yml"

ES_WINDOWS = os.name == "nt"
NOMBRE_BIN = "mediamtx.exe" if ES_WINDOWS else "mediamtx"


def log(msg: str) -> None:
    print(f"[clase] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Red
# ---------------------------------------------------------------------------
def ip_principal() -> str:
    """IP de la interfaz con ruta por defecto (no envía tráfico real)."""
    for destino in ("10.255.255.255", "192.168.255.255", "8.8.8.8"):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect((destino, 1))
            ip = s.getsockname()[0]
            if not ip.startswith("127."):
                return ip
        except OSError:
            pass
        finally:
            s.close()
    return "127.0.0.1"


def ips_locales() -> list[str]:
    """Todas las IPv4 privadas conocidas del equipo (la principal primero)."""
    ips = [ip_principal()]
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except socket.gaierror:
        pass
    privadas = [ip for ip in ips if ip.startswith(("10.", "192.168.")) or
                (ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31)]
    resto = [ip for ip in ips if ip not in privadas and ip != "127.0.0.1"]
    return privadas + resto or ["127.0.0.1"]


def puerto_libre(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", puerto))
            return True
        except OSError:
            return False


# ---------------------------------------------------------------------------
# MediaMTX
# ---------------------------------------------------------------------------
def nombre_paquete() -> str:
    sistema = platform.system().lower()
    maquina = platform.machine().lower()
    if sistema == "windows":
        return f"mediamtx_{MEDIAMTX_VERSION}_windows_amd64.zip"
    if sistema == "darwin":
        arq = "arm64" if maquina in ("arm64", "aarch64") else "amd64"
        return f"mediamtx_{MEDIAMTX_VERSION}_darwin_{arq}.tar.gz"
    if sistema == "linux":
        arq = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64",
               "arm64": "arm64", "armv7l": "armv7", "armv6l": "armv6"}.get(maquina)
        if arq:
            return f"mediamtx_{MEDIAMTX_VERSION}_linux_{arq}.tar.gz"
    raise RuntimeError(f"Plataforma no soportada: {sistema}/{maquina}")


def asegurar_mediamtx() -> Path:
    binario = DIR_BIN / NOMBRE_BIN
    if binario.exists():
        return binario
    en_path = shutil.which("mediamtx")
    if en_path:
        log(f"Usando MediaMTX del sistema: {en_path} (se recomienda {MEDIAMTX_VERSION})")
        return Path(en_path)

    paquete = nombre_paquete()
    url = (f"https://github.com/bluenviron/mediamtx/releases/download/"
           f"{MEDIAMTX_VERSION}/{paquete}")
    log(f"Descargando MediaMTX {MEDIAMTX_VERSION} (sólo la primera vez)...")
    log(f"  {url}")
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            datos = r.read()
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(
            f"No se pudo descargar MediaMTX ({e}).\n"
            f"  Descárguelo manualmente desde {url}\n"
            f"  y copie '{NOMBRE_BIN}' dentro de la carpeta: {DIR_BIN}") from e

    DIR_BIN.mkdir(exist_ok=True)
    if paquete.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            z.extract(NOMBRE_BIN, DIR_BIN)
            if "LICENSE" in z.namelist():
                z.extract("LICENSE", DIR_BIN)
    else:
        with tarfile.open(fileobj=io.BytesIO(datos), mode="r:gz") as t:
            for nombre in (NOMBRE_BIN, "LICENSE"):
                try:
                    miembro = t.getmember(nombre)
                except KeyError:
                    continue
                with t.extractfile(miembro) as src, open(DIR_BIN / nombre, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        binario.chmod(0o755)
    log(f"MediaMTX instalado en {binario}")
    return binario


def iniciar_mediamtx(binario: Path, config: Path = CONFIG_MTX,
                     entorno: dict | None = None) -> subprocess.Popen:
    for puerto in (PUERTO_WEBRTC, 9997):
        if not puerto_libre(puerto):
            raise RuntimeError(
                f"El puerto {puerto} ya está en uso: ¿hay otra instancia de "
                f"MediaMTX abierta? Ciérrela e intente de nuevo.")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if ES_WINDOWS else 0
    proc = subprocess.Popen([str(binario), str(config)], cwd=str(BASE),
                            creationflags=flags, env={**os.environ, **(entorno or {})})
    # Esperar a que la API responda
    for _ in range(50):
        if proc.poll() is not None:
            raise RuntimeError("MediaMTX terminó al iniciar; revise los mensajes anteriores.")
        try:
            urllib.request.urlopen(f"{API_MEDIAMTX}/v3/paths/list", timeout=1).read()
            return proc
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            time.sleep(0.2)
    log("Advertencia: la API de MediaMTX aún no responde; se continúa.")
    return proc


def estado_stream() -> dict:
    try:
        with urllib.request.urlopen(
                f"{API_MEDIAMTX}/v3/paths/get/{RUTA_STREAM}", timeout=2) as r:
            d = json.load(r)
        return {
            "servidor": True,
            "enVivo": bool(d.get("online", d.get("ready", False))),
            "espectadores": len(d.get("readers") or []),
            "bytesEntrada": d.get("inboundBytes", d.get("bytesReceived", 0)),
            "fuente": (d.get("source") or {}).get("type"),
        }
    except urllib.error.HTTPError as e:
        # 404 = la ruta existe en la config pero nadie publica todavía
        return {"servidor": True, "enVivo": False, "espectadores": 0,
                "bytesEntrada": 0, "fuente": None, "codigo": e.code}
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        return {"servidor": False, "enVivo": False, "espectadores": 0,
                "bytesEntrada": 0, "fuente": None}




# ---------------------------------------------------------------------------
# Seguridad para el modo VPS (sesiones firmadas con HMAC-SHA256)
# ---------------------------------------------------------------------------
class Seguridad:
    """Credenciales y sesiones del modo VPS. En modo LAN no se usa."""

    DURACION_SESION = 12 * 3600          # una jornada de clases
    MAX_FALLOS, VENTANA_FALLOS = 5, 600   # 5 intentos fallidos cada 10 min por IP

    def __init__(self, clave_profesor: str, clave_estudiantes: str = "",
                 token_obs: str = "", secreto: str = ""):
        self.clave_profesor = clave_profesor
        self.clave_estudiantes = clave_estudiantes
        self.token_obs = token_obs
        # Si no se fija CLASE_SECRETO, las sesiones caducan al reiniciar.
        self.secreto = (secreto or secrets.token_hex(32)).encode()
        self._fallos: dict[str, list[float]] = {}
        self._cerrojo = threading.Lock()

    @staticmethod
    def iguales(a: str, b: str) -> bool:
        return hmac.compare_digest(a.encode(), b.encode())

    def _firma(self, texto: str) -> str:
        return hmac.new(self.secreto, texto.encode(), hashlib.sha256).hexdigest()

    # -- sesión del profesor ------------------------------------------------
    def emitir_profesor(self) -> str:
        vence = str(int(time.time()) + self.DURACION_SESION)
        return f"{vence}.{self._firma('prof|' + vence)}"

    def valida_profesor(self, valor: str | None) -> bool:
        try:
            vence, firma = (valor or "").split(".", 1)
            return int(vence) > time.time() and self.iguales(firma, self._firma("prof|" + vence))
        except ValueError:
            return False

    # -- acceso de estudiantes (opcional) -------------------------------------
    @property
    def requiere_clave_estudiantes(self) -> bool:
        return bool(self.clave_estudiantes)

    def emitir_estudiante(self) -> str:
        # La firma depende de la clave: al cambiarla se invalidan los accesos previos.
        return self._firma("est|" + self.clave_estudiantes)

    def valida_estudiante(self, valor: str | None) -> bool:
        return (not self.requiere_clave_estudiantes) or self.iguales(
            valor or "", self.emitir_estudiante())

    # -- limitación de intentos -----------------------------------------------
    def bloqueado(self, ip: str) -> bool:
        ahora = time.time()
        with self._cerrojo:
            f = [t for t in self._fallos.get(ip, []) if ahora - t < self.VENTANA_FALLOS]
            self._fallos[ip] = f
            return len(f) >= self.MAX_FALLOS

    def registrar_fallo(self, ip: str) -> None:
        with self._cerrojo:
            self._fallos.setdefault(ip, []).append(time.time())


# ---------------------------------------------------------------------------
# Servidor web
# ---------------------------------------------------------------------------
# Cabeceras que no se reenvían entre el cliente y MediaMTX.
SALTO_A_SALTO = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
                 "te", "trailers", "transfer-encoding", "upgrade", "content-length",
                 "server", "date"}
MAX_CUERPO = 256 * 1024     # una oferta SDP ocupa pocos KB


class ManejadorAula(http.server.SimpleHTTPRequestHandler):
    ips: list[str] = []
    puerto_web: int = 8080
    modo: str = "lan"
    url_publica: str = ""
    seg: Seguridad | None = None

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DIR_WEB), **kw)

    # ---------------- utilidades ----------------
    @property
    def vps(self) -> bool:
        return self.modo == "vps"

    def es_local(self) -> bool:
        return self.client_address[0] in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

    def ip_cliente(self) -> str:
        """IP real del cliente. En modo VPS Traefik añade la IP al final de
        X-Forwarded-For (y descarta la que envíe un cliente no confiable)."""
        if self.vps:
            xff = self.headers.get("X-Forwarded-For", "")
            if xff:
                return xff.split(",")[-1].strip()
        return self.client_address[0]

    def cookies(self) -> dict[str, str]:
        out = {}
        for parte in self.headers.get("Cookie", "").split(";"):
            if "=" in parte:
                k, v = parte.split("=", 1)
                out[k.strip()] = v.strip()
        return out

    def es_profesor(self) -> bool:
        if not self.vps:
            return self.es_local()
        return self.seg.valida_profesor(self.cookies().get("clase_prof"))

    def es_estudiante(self) -> bool:
        if not self.vps:
            return True
        return self.es_profesor() or self.seg.valida_estudiante(self.cookies().get("clase_est"))

    def cookie(self, nombre: str, valor: str, max_age: int) -> str:
        return (f"{nombre}={valor}; Path=/; Max-Age={max_age}; HttpOnly; "
                f"Secure; SameSite=Lax")

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if self.vps:
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        super().end_headers()

    def responder(self, cuerpo: bytes, tipo: str, codigo: int = 200, extra=None):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(cuerpo)

    def redirigir(self, destino: str, extra=None):
        self.responder(b"", "text/plain", 303, [("Location", destino)] + list(extra or []))

    def leer_cuerpo(self) -> bytes | None:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if n < 0 or n > MAX_CUERPO:
            return None
        return self.rfile.read(n) if n else b""

    def formulario(self) -> dict[str, str]:
        cuerpo = self.leer_cuerpo() or b""
        datos = urllib.parse.parse_qs(cuerpo.decode("utf-8", "replace"))
        return {k: v[0] for k, v in datos.items()}

    def list_directory(self, path):          # nunca listar carpetas
        self.send_error(404)
        return None

    # ---------------- configuración para las páginas ----------------
    def config_js(self) -> bytes:
        cfg = {"modo": self.modo, "ips": self.ips, "ip": self.ips[0],
               "puertoWeb": self.puerto_web, "puertoWebrtc": PUERTO_WEBRTC,
               "ruta": RUTA_STREAM, "version": MEDIAMTX_VERSION,
               "baseWebrtc": f"/{RUTA_STREAM}/" if self.vps else None}
        if self.vps:
            cfg["urlPublica"] = self.url_publica
            cfg["claveEstudiantes"] = self.seg.requiere_clave_estudiantes
            if self.es_profesor():
                # Sólo el profesor recibe el enlace con la clave (para el QR).
                url = self.url_publica.rstrip("/") + "/"
                if self.seg.requiere_clave_estudiantes:
                    url += "?k=" + urllib.parse.quote(self.seg.clave_estudiantes)
                cfg["urlEstudiante"] = url
                cfg["obsWhip"] = self.url_publica.rstrip("/") + f"/{RUTA_STREAM}/whip"
                cfg["obsToken"] = bool(self.seg.token_obs)
        return ("window.CLASE = " + json.dumps(cfg) + ";\n").encode()

    # ---------------- proxy WHIP/WHEP hacia MediaMTX (sólo VPS) ----------------
    def proxy_mediamtx(self):
        ruta = self.path.split("?", 1)[0]
        tramo = ruta[len(f"/{RUTA_STREAM}/"):]
        publicar = tramo == "whip" or tramo.startswith("whip/") or tramo == "publisher.js"
        if publicar:
            autorizado = self.es_profesor()
            auth = self.headers.get("Authorization", "")
            if not autorizado and self.seg.token_obs and auth.startswith("Bearer "):
                autorizado = self.seg.iguales(auth[7:].strip(), self.seg.token_obs)
        else:
            autorizado = self.es_estudiante()
        if not autorizado:
            return self.responder(b'{"error":"no autorizado"}', "application/json", 401)
        cuerpo = self.leer_cuerpo() if self.command in ("POST", "PATCH") else b""
        if cuerpo is None:
            return self.responder(b"cuerpo demasiado grande", "text/plain", 413)
        cab = {k: v for k, v in self.headers.items()
               if k.lower() in ("content-type", "if-match", "accept")}
        # No se reenvían Authorization, Cookie ni X-Forwarded-For: MediaMTX ve
        # la petición como local (127.0.0.1), que es quien tiene permiso de publicar.
        try:
            con = http.client.HTTPConnection("127.0.0.1", PUERTO_WEBRTC, timeout=15)
            con.request(self.command, self.path, body=cuerpo or None, headers=cab)
            r = con.getresponse()
            datos = r.read()
        except (OSError, http.client.HTTPException):
            return self.responder(b'{"error":"MediaMTX no responde"}', "application/json", 502)
        finally:
            con.close()
        extra = [(k, v) for k, v in r.getheaders()
                 if k.lower() not in SALTO_A_SALTO and not k.lower().startswith("access-control")
                 and k.lower() not in ("content-type", "cache-control")]
        self.responder(datos, r.getheader("Content-Type", "application/octet-stream"),
                       r.status, extra)

    def es_ruta_webrtc(self) -> bool:
        return self.vps and self.path.startswith(f"/{RUTA_STREAM}/")

    # ---------------- métodos HTTP ----------------
    def do_OPTIONS(self):
        if self.es_ruta_webrtc():
            return self.proxy_mediamtx()
        self.send_error(405)

    def do_PATCH(self):
        if self.es_ruta_webrtc():
            return self.proxy_mediamtx()
        self.send_error(405)

    def do_DELETE(self):
        if self.es_ruta_webrtc():
            return self.proxy_mediamtx()
        self.send_error(405)

    def do_POST(self):
        if self.es_ruta_webrtc():
            return self.proxy_mediamtx()
        ruta = self.path.split("?", 1)[0]
        if not self.vps or ruta not in ("/login", "/entrar"):
            return self.send_error(405)
        ip = self.ip_cliente()
        if self.seg.bloqueado(ip):
            return self.responder("Demasiados intentos. Espere 10 minutos.".encode(),
                                  "text/plain; charset=utf-8", 429)
        clave = self.formulario().get("clave", "")
        if ruta == "/login":
            if self.seg.iguales(clave, self.seg.clave_profesor):
                log(f"Inicio de sesión del profesor desde {ip}")
                return self.redirigir("/profesor.html", [("Set-Cookie", self.cookie(
                    "clase_prof", self.seg.emitir_profesor(), Seguridad.DURACION_SESION))])
            self.seg.registrar_fallo(ip)
            log(f"Contraseña de profesor incorrecta desde {ip}")
            return self.redirigir("/login.html?e=1")
        # /entrar (estudiantes)
        if self.seg.requiere_clave_estudiantes and not self.seg.iguales(
                clave, self.seg.clave_estudiantes):
            self.seg.registrar_fallo(ip)
            return self.redirigir("/entrar.html?e=1")
        return self.redirigir("/", [("Set-Cookie", self.cookie(
            "clase_est", self.seg.emitir_estudiante(), Seguridad.DURACION_SESION))])

    def do_GET(self):
        ruta, _, consulta = self.path.partition("?")
        if self.es_ruta_webrtc():
            return self.proxy_mediamtx()
        if ruta == "/config.js":
            return self.responder(self.config_js(), "application/javascript; charset=utf-8")
        if ruta == "/salud":
            return self.responder(b"ok", "text/plain")
        if ruta == "/api/estado":
            if not self.es_profesor():
                return self.responder(b'{"error":"solo profesor"}', "application/json", 403)
            return self.responder(json.dumps(estado_stream()).encode(), "application/json")

        if ruta in ("/profesor", "/profesor.html") and not self.es_profesor():
            # LAN: el panel sólo se abre desde el propio equipo.
            # VPS: requiere iniciar sesión con la contraseña del profesor.
            return self.redirigir("/login.html" if self.vps else "/")

        if self.vps:
            if ruta == "/logout":
                return self.redirigir("/login.html", [("Set-Cookie", self.cookie(
                    "clase_prof", "", 0))])
            if ruta in ("/", "/index.html"):
                k = urllib.parse.parse_qs(consulta).get("k", [""])[0]
                if k and self.seg.requiere_clave_estudiantes:
                    ip = self.ip_cliente()
                    if not self.seg.bloqueado(ip) and self.seg.iguales(k, self.seg.clave_estudiantes):
                        return self.redirigir("/", [("Set-Cookie", self.cookie(
                            "clase_est", self.seg.emitir_estudiante(), Seguridad.DURACION_SESION))])
                    self.seg.registrar_fallo(ip)
                    return self.redirigir("/entrar.html?e=1")
                if not self.es_estudiante():
                    return self.redirigir("/entrar.html")
        elif ruta in ("/login.html", "/entrar.html"):
            return self.redirigir("/")
        return super().do_GET()

    def log_message(self, fmt, *args):
        if os.environ.get("CLASE_DEBUG"):
            super().log_message(fmt, *args)


class ServidorHilos(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


# ---------------------------------------------------------------------------
def preparar_vps(args) -> tuple[Seguridad, str, dict]:
    """Lee y valida la configuración del modo VPS desde variables de entorno."""
    e = os.environ
    clave = e.get("CLASE_PASSWORD_PROFESOR", "")
    if len(clave) < 10:
        raise RuntimeError("Defina CLASE_PASSWORD_PROFESOR (mínimo 10 caracteres).")
    url = e.get("CLASE_URL_PUBLICA", "").rstrip("/")
    if not url.startswith("https://"):
        raise RuntimeError("Defina CLASE_URL_PUBLICA con https:// (p. ej. https://clase.unachi.ac.pa).")
    host_ice = e.get("CLASE_IP_PUBLICA", "").strip()
    if not host_ice:
        raise RuntimeError("Defina CLASE_IP_PUBLICA con la IP pública del VPS "
                           "(se anuncia a los navegadores para el tráfico UDP 8189).")
    seg = Seguridad(clave, e.get("CLASE_CLAVE_ESTUDIANTES", ""),
                    e.get("CLASE_TOKEN_OBS", ""), e.get("CLASE_SECRETO", ""))
    entorno = {"MTX_WEBRTCADDITIONALHOSTS": host_ice}
    return seg, url, entorno


def main() -> int:
    ap = argparse.ArgumentParser(description="Clase en Vivo UNACHI")
    ap.add_argument("--modo", choices=("lan", "vps"),
                    default=os.environ.get("CLASE_MODO", "lan"))
    ap.add_argument("--ip", help="IP de la LAN a mostrar a los estudiantes")
    ap.add_argument("--puerto-web", type=int,
                    default=int(os.environ.get("CLASE_PUERTO_WEB", "8080")))
    ap.add_argument("--sin-navegador", action="store_true")
    ap.add_argument("--sin-mediamtx", action="store_true",
                    help="no iniciar MediaMTX (ya se ejecuta aparte)")
    args = ap.parse_args()

    vps = args.modo == "vps"
    ManejadorAula.modo = args.modo
    ManejadorAula.puerto_web = args.puerto_web
    proc = None
    try:
        if vps:
            seg, url_publica, entorno = preparar_vps(args)
            ManejadorAula.seg = seg
            ManejadorAula.url_publica = url_publica
            ips = [urllib.parse.urlsplit(url_publica).hostname or "127.0.0.1"]
            config, args.sin_navegador = CONFIG_MTX_VPS, True
        else:
            ips = ips_locales()
            if args.ip:
                ips = [args.ip] + [i for i in ips if i != args.ip]
            config, entorno = CONFIG_MTX, {}
        ManejadorAula.ips = ips

        if not args.sin_mediamtx:
            proc = iniciar_mediamtx(asegurar_mediamtx(), config, entorno)
        if not puerto_libre(args.puerto_web):
            raise RuntimeError(f"El puerto web {args.puerto_web} está ocupado; "
                               f"use --puerto-web 8081")
        httpd = ServidorHilos(("0.0.0.0", args.puerto_web), ManejadorAula)
    except RuntimeError as e:
        log(f"ERROR: {e}")
        if proc:
            proc.terminate()
        return 1

    print("\n" + "=" * 64)
    print("  CLASE EN VIVO — UNACHI" + ("  (modo VPS)" if vps else ""))
    if vps:
        print(f"  Panel del profesor : {ManejadorAula.url_publica}/profesor.html")
        print(f"  Enlace estudiantes : {ManejadorAula.url_publica}/")
        print(f"  Escuchando en      : 0.0.0.0:{args.puerto_web} (detrás del proxy HTTPS)")
        print(f"  Medios WebRTC      : {os.environ.get('CLASE_IP_PUBLICA')}:{PUERTO_ICE} UDP/TCP")
    else:
        print(f"  Panel del profesor : http://localhost:{args.puerto_web}/profesor.html")
        print(f"  Enlace estudiantes : http://{ips[0]}:{args.puerto_web}/")
        if len(ips) > 1:
            print(f"  Otras IP del equipo: {', '.join(ips[1:])}")
    print("  Detener            : Ctrl+C")
    print("=" * 64 + "\n", flush=True)
    url_prof = f"http://localhost:{args.puerto_web}/profesor.html"

    hilo = threading.Thread(target=httpd.serve_forever, daemon=True)
    hilo.start()
    if not args.sin_navegador:
        threading.Timer(1.0, lambda: webbrowser.open(url_prof)).start()

    detener = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: detener.set())
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, lambda *_: detener.set())
    codigo = 0
    try:
        while not detener.is_set():
            if proc and proc.poll() is not None:
                log("MediaMTX se detuvo inesperadamente.")
                codigo = 1   # en Docker, el contenedor se reinicia
                break
            detener.wait(1)
    finally:
        log("Cerrando...")
        httpd.shutdown()
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
    return codigo


if __name__ == "__main__":
    sys.exit(main())
