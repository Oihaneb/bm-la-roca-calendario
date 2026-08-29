import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import re

URL = "https://resultadosbalonmano.isquad.es/equipo.php?id=1023863&id_equipo=215051&seleccion=0"

TIMEZONE = "Europe/Madrid"

def limpiar(texto):
    return re.sub(r"\s+", " ", texto).strip()

def uid_partido(local, visitante, fecha):
    texto = f"{local}|{visitante}|{fecha}"
    return hashlib.sha256(texto.encode()).hexdigest() + "@bm-la-roca"

def main():

    respuesta = requests.get(
        URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    respuesta.raise_for_status()

    soup = BeautifulSoup(respuesta.text, "html.parser")

    calendario = Calendar()

    calendario.add("prodid", "-//BM La Roca//Calendario//ES")
    calendario.add("version", "2.0")
    calendario.add("calscale", "GREGORIAN")
    calendario.add("method", "PUBLISH")
    calendario.add("x-wr-calname", "BM La Roca - División de Honor Plata Femenina")
    calendario.add("x-wr-timezone", TIMEZONE)

    # ---------------------------------------------------------
    # IMPORTANTE:
    # Aquí se deben localizar las filas de partidos de la
    # página oficial de la RFEBM.
    # ---------------------------------------------------------

    tabla = soup.find("table")

    if tabla is None:
        raise RuntimeError(
            "No se ha encontrado la tabla de partidos de la RFEBM"
        )

    filas = tabla.find_all("tr")

    encontrados = 0

    for fila in filas:

        columnas = fila.find_all(["td", "th"])

        textos = [limpiar(c.get_text(" ", strip=True))
                  for c in columnas]

        if not textos:
            continue

        # Aquí se filtrarán únicamente las filas de partidos
        # de BM La Roca.

        texto_fila = " ".join(textos)

        if "MUBAK BM LA ROCA" not in texto_fila.upper():
            continue

        # La extracción concreta de fecha/hora/rival se debe
        # adaptar a la estructura actual de la página RFEBM.

        # -----------------------------------------------------
        # Ejemplo conceptual:
        #
        # fecha = ...
        # local = ...
        # visitante = ...
        # pabellon = ...
        # -----------------------------------------------------

        # Una vez obtenidos esos datos:
        #
        # inicio = datetime.strptime(
        #     fecha,
        #     "%d/%m/%Y %H:%M"
        # ).replace(tzinfo=ZoneInfo(TIMEZONE))
        #
        # evento = Event()
        # evento.add("uid", uid_partido(local, visitante, inicio))
        # evento.add("dtstart", inicio)
        # evento.add("dtend", inicio + timedelta(hours=2))
        # evento.add("summary", f"{local} - {visitante}")
        # evento.add("location", pabellon)
        #
        # calendario.add_component(evento)

        encontrados += 1

    if encontrados == 0:
        raise RuntimeError(
            "No se han encontrado partidos de BM La Roca. "
            "Es posible que la estructura de la web haya cambiado."
        )

    with open("bm-la-roca.ics", "wb") as archivo:
        archivo.write(calendario.to_ical())


if __name__ == "__main__":
    main()
