"""Piezas comunes: sesión HTTP con reintentos, navegador Selenium y utilidades."""

import json
import logging
import random
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)

COLUMNAS = [
    "tienda", "sku", "titulo", "marca", "vendedor", "categoria",
    "precio_referencia", "precio_oferta", "precio_tarjeta", "url", "timestamp",
]

LIMA = ZoneInfo("America/Lima")

log = logging.getLogger("captura")


def ahora():
    """Hora de Lima sin zona, igual que en los notebooks."""
    return datetime.now(LIMA).replace(tzinfo=None, microsecond=0)


def pausa(minimo=1.0, maximo=2.5):
    time.sleep(random.uniform(minimo, maximo))


def a_numero(valor):
    """Convierte '1,599.90', 'S/ 1,599.90', 1599.9 o ['1,599'] en float. None si no se puede."""
    if valor is None:
        return None
    if isinstance(valor, list):
        valor = valor[0] if valor else None
        if valor is None:
            return None
    if isinstance(valor, (int, float)):
        return float(valor) if valor > 0 else None
    texto = str(valor).replace("S/", "").replace(",", "").strip()
    if texto == "" or texto.count(".") > 1:
        return None
    try:
        numero = float(texto)
    except ValueError:
        return None
    return numero if numero > 0 else None


def fila(tienda, categoria, **datos):
    base = {c: None for c in COLUMNAS}
    base.update(datos)
    base["tienda"] = tienda
    base["categoria"] = categoria
    base["timestamp"] = ahora()
    if base["sku"] is not None:
        base["sku"] = str(base["sku"]).strip()
    for campo in ("titulo", "marca", "vendedor"):
        if isinstance(base[campo], str):
            base[campo] = " ".join(base[campo].split()) or None
    return base


class Cliente:
    """Sesión de requests con reintentos y, si hace falta, un Chrome headless de respaldo."""

    def __init__(self, selenium_de_respaldo=False):
        self.sesion = requests.Session()
        self.sesion.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "es-PE,es;q=0.9",
        })
        reintentos = Retry(
            total=5,
            backoff_factor=3,
            status_forcelist=[403, 429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            respect_retry_after_header=True,
        )
        adaptador = HTTPAdapter(max_retries=reintentos)
        self.sesion.mount("https://", adaptador)
        self.sesion.mount("http://", adaptador)
        self.selenium_de_respaldo = selenium_de_respaldo
        self._driver = None

    def get(self, url, **kwargs):
        respuesta = self.sesion.get(url, timeout=(15, 60), **kwargs)
        respuesta.raise_for_status()
        return respuesta

    def html(self, url):
        """HTML de la página. Si requests falla y hay respaldo, lo intenta con Chrome."""
        try:
            return self.get(url).text
        except requests.RequestException as error:
            if not self.selenium_de_respaldo:
                raise
            log.warning("requests falló (%s), se usa Chrome: %s", error, url)
            return self.html_chrome(url)

    def sopa(self, url):
        return BeautifulSoup(self.html(url), "html.parser")

    def json(self, url):
        return self.get(url, headers={"Accept": "application/json"}).json()

    # ---- Selenium ----

    @property
    def driver(self):
        if self._driver is None:
            self._driver = crear_driver()
        return self._driver

    def html_chrome(self, url, espera_css=None, minimo=1, timeout=40):
        """Abre la página en Chrome y espera a que aparezcan y se estabilicen los elementos."""
        from selenium.common.exceptions import WebDriverException

        for intento in range(3):
            try:
                self.driver.get(url)
                if espera_css:
                    esperar_estable(self.driver, espera_css, minimo, timeout)
                else:
                    time.sleep(5)
                return self.driver.page_source
            except WebDriverException as error:
                log.warning("Chrome falló (intento %s): %s", intento + 1, str(error)[:150])
                self.reiniciar_driver()
                time.sleep(5 * (intento + 1))
        raise RuntimeError(f"Chrome no pudo abrir {url}")

    def reiniciar_driver(self):
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
        self._driver = None

    def cerrar(self):
        self.reiniciar_driver()
        self.sesion.close()


def crear_driver():
    from selenium import webdriver

    opciones = webdriver.ChromeOptions()
    opciones.add_argument("--headless=new")
    opciones.add_argument("--no-sandbox")
    opciones.add_argument("--disable-dev-shm-usage")
    opciones.add_argument("--disable-gpu")
    opciones.add_argument("--window-size=1366,900")
    opciones.add_argument("--blink-settings=imagesEnabled=false")
    opciones.add_argument(f"--user-agent={USER_AGENT}")
    opciones.page_load_strategy = "eager"
    driver = webdriver.Chrome(options=opciones)
    driver.set_page_load_timeout(60)
    return driver


def esperar_estable(driver, css, minimo=1, timeout=40):
    """Espera hasta que haya al menos `minimo` elementos y su número deje de cambiar."""
    limite = time.time() + timeout
    anterior, estable = -1, 0
    while time.time() < limite:
        cantidad = len(driver.find_elements("css selector", css))
        if cantidad >= minimo and cantidad == anterior:
            estable += 1
            if estable >= 2:
                return cantidad
        else:
            estable = 0
        anterior = cantidad
        time.sleep(1.5)
    return max(anterior, 0)


def next_data(sopa):
    """Devuelve el JSON de __NEXT_DATA__ o None."""
    script = sopa.find("script", id="__NEXT_DATA__")
    if script is None or not script.string:
        return None
    try:
        return json.loads(script.string)
    except ValueError:
        return None
