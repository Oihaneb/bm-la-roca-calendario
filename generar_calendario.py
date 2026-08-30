import re
import hashlib
import requests

from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# Calendario oficial 2026/27 de División de Honor Plata Femenina,
# Grupo C, de la RFEBM.
URL = (
    "https://resultadosbalonmano.isquad.es/"
    "calendario.php?id=1038403"
    "&id_ambito=1"
    "&id_categoria=3020"
    "&id_competicion=211441"
    "&id_superficie=1"
    "&id_territorial=9999"
    "&iframe=0"
    "&seleccion=0"
)

EQUIPO = "MUBAK"
NOMBRE_CALENDARIO = "BM La Roca - División de Honor Plata Femenina"
ZONA_HORARIA = "Europe/Madrid"


def limpiar(texto):
    return re.sub(r"\s+", " ", texto).strip()


def crear_uid(local, visitante, fecha, jornada):
    texto = f"{jornada}|{fecha}|{local}|{visitante}"
    hash_partido = hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()

    return f"{hash_partido}@bm-la-roca"


def separar_equipos(texto):
    """
    Convierte:

        MUBAK - BM LA ROCA - HANDBOL SANT CUGAT A

    en:

        local = MUBAK - BM LA ROCA
        visitante = HANDBOL SANT CUGAT A

    El calendario de RFEBM utiliza ' - ' como separador.
    """

    texto = limpiar(texto)

    if texto.upper().startswith("VS "):
        texto = texto[3:].strip()

    partes = texto.split(" - ")

    if len(partes) < 2:
        return None, None

    # BM La Roca puede aparecer como:
    # MUBAK - BM LA ROCA
    #
    # Por eso buscamos dónde aparece BM LA ROCA y tomamos
    # dos partes para el nombre del equipo.

    posiciones_roca = []

    for i, parte in enumerate(partes):
        if "BM LA ROCA" in parte.upper():
            posiciones_roca.append(i)

    if posiciones_roca:
        i = posiciones_roca[0]

        # Normalmente:
        # MUBAK - BM LA ROCA - RIVAL
        if i > 0:
            local = " - ".join(partes[:i + 1])
            visitante = " - ".join(partes[i + 1:])

            if visitante:
                return limpiar(local), limpiar(visitante)

        # Si BM La Roca es visitante:
        if i < len(partes) - 1:
            local = " - ".join(partes[:i])
            visitante = " - ".join(partes[i:])

            if local:
                return limpiar(local), limpiar(visitante)

    # Último recurso
    mitad = len(partes) // 2

    local = " - ".join(partes[:mitad])
    visitante = " - ".join(partes[mitad:])

    return limpiar(local), limpiar(visitante)


def obtener_fecha_hora(texto, fecha_jornada):
    """
    Busca una fecha/hora del tipo:

        08/10/2026 21:15

    Si no existe, utiliza la fecha de la jornada.

    Cuando RFEBM muestra 0:00 significa que todavía no
    hay hora definitiva. En ese caso creamos un evento de
    día completo en vez de inventar una hora.
    """

    patron = r"(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2})"

    encontrado = re.search(patron, texto)

    if encontrado:
        fecha = encontrado.group(1)
        hora = encontrado.group(2)

        dt = datetime.strptime(
            f"{fecha} {hora}",
            "%d/%m/%Y %H:%M"
        )

        if hora == "0:00" or hora == "00:00":
            return dt.date(), None

        return (
            dt.replace(
                tzinfo=ZoneInfo(ZONA_HORARIA)
            ),
            "hora"
        )

    if fecha_jornada:
        dt = datetime.strptime(
            fecha_jornada,
            "%d-%m-%Y"
        )

        return dt.date(), None

    return None, None


def main():

    print("Descargando calendario oficial RFEBM...")

    respuesta = requests.get(
        URL,
        timeout=30,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 "
                "Version/17.0 Mobile/15E148 Safari/604.1"
            )
        }
    )

    respuesta.raise_for_status()

    # La página puede venir con una codificación antigua.
    respuesta.encoding = respuesta.apparent_encoding

    soup = BeautifulSoup(
        respuesta.text,
        "html.parser"
    )

    calendario = Calendar()

    calendario.add(
        "prodid",
        "-//BM La Roca//Division Honor Plata Femenina//ES"
    )

    calendario.add("version", "2.0")
    calendario.add("calscale", "GREGORIAN")
    calendario.add("method", "PUBLISH")

    calendario.add(
        "x-wr-calname",
        NOMBRE_CALENDARIO
    )

    calendario.add(
        "x-wr-timezone",
        ZONA_HORARIA
    )

    partidos = []

    fecha_jornada = None
    jornada_actual = None

    # La RFEBM presenta los partidos en filas <tr>.
    filas = soup.find_all("tr")

    for fila in filas:

        texto = limpiar(
            fila.get_text(" ", strip=True)
        )

        if not texto:
            continue

        # --------------------------------------------------
        # Detectar jornada
        # Ejemplo:
        # JORNADA 1 (04-10-2026)
        # --------------------------------------------------

        patron_jornada = re.search(
            r"JORNADA\s+(\d+)\s*\((\d{2}-\d{2}-\d{4})\)",
            texto,
            re.IGNORECASE
        )

        if patron_jornada:

            jornada_actual = int(
                patron_jornada.group(1)
            )

            fecha_jornada = patron_jornada.group(2)

            print(
                f"Jornada {jornada_actual}: "
                f"{fecha_jornada}"
            )

            continue

        # --------------------------------------------------
        # Solo queremos partidos donde aparezca BM LA ROCA
        # --------------------------------------------------

        if "BM LA ROCA" not in texto.upper():
            continue

        # Evitar filas que no sean partidos.
        if "VS " not in texto.upper():
            continue

        # --------------------------------------------------
        # Extraer equipos
        # --------------------------------------------------

        local, visitante = separar_equipos(texto)

        if not local or not visitante:
            print(
                "No se pudieron separar los equipos:",
                texto
            )
            continue

        # --------------------------------------------------
        # Fecha y hora
        # --------------------------------------------------

        fecha_hora, tipo_fecha = obtener_fecha_hora(
            texto,
            fecha_jornada
        )

        if fecha_hora is None:
            print(
                "No se pudo obtener fecha:",
                texto
            )
            continue

        # --------------------------------------------------
        # Lugar
        # --------------------------------------------------

        columnas = [
            limpiar(c.get_text(" ", strip=True))
            for c in fila.find_all(["td", "th"])
        ]

        lugar = ""

        if columnas:
            # Normalmente el último campo es el pabellón.
            posible_lugar = columnas[-1]

            if (
                posible_lugar
                and "JORNADA" not in posible_lugar.upper()
            ):
                lugar = posible_lugar

        partidos.append(
            {
                "jornada": jornada_actual,
                "fecha": fecha_hora,
                "tipo_fecha": tipo_fecha,
                "local": local,
                "visitante": visitante,
                "lugar": lugar,
                "texto_original": texto,
            }
        )

    # ------------------------------------------------------
    # Eliminar duplicados
    # ------------------------------------------------------

    partidos_unicos = {}

    for partido in partidos:

        clave = (
            partido["jornada"],
            str(partido["fecha"]),
            partido["local"],
            partido["visitante"],
        )

        partidos_unicos[clave] = partido

    partidos = list(partidos_unicos.values())

    # ------------------------------------------------------
    # Ordenar
    # ------------------------------------------------------

    partidos.sort(
        key=lambda p: (
            p["fecha"],
            p["jornada"] or 999
        )
    )

    print(
        f"Partidos encontrados: {len(partidos)}"
    )

    if not partidos:

        raise RuntimeError(
            "No se han encontrado partidos de "
            "MUBAK BM LA ROCA en el calendario oficial "
            "2026/27 de la RFEBM."
        )

    # ------------------------------------------------------
    # Crear eventos
    # ------------------------------------------------------

    for partido in partidos:

        evento = Event()

        uid = crear_uid(
            partido["local"],
            partido["visitante"],
            partido["fecha"],
            partido["jornada"]
        )

        evento.add("uid", uid)

        titulo = (
            f"🤾 {partido['local']} - "
            f"{partido['visitante']}"
        )

        evento.add(
            "summary",
            titulo
        )

        # --------------------------------------------------
        # Partido con hora conocida
        # --------------------------------------------------

        if partido["tipo_fecha"] == "hora":

            inicio = partido["fecha"]

            fin = inicio + timedelta(
                hours=2
            )

            evento.add(
                "dtstart",
                inicio
            )

            evento.add(
                "dtend",
                fin
            )

            evento.add(
                "dtstamp",
                datetime.now(
                    ZoneInfo(ZONA_HORARIA)
                )
            )

        # --------------------------------------------------
        # Partido sin hora confirmada
        # --------------------------------------------------

        else:

            fecha = partido["fecha"]

            evento.add(
                "dtstart",
                fecha
            )

            evento.add(
                "dtend",
                fecha + timedelta(days=1)
            )

            evento.add(
                "dtstamp",
                datetime.now(
                    ZoneInfo(ZONA_HORARIA)
                )
            )

            evento.add(
                "description",
                "Hora pendiente de confirmar por RFEBM."
            )

        # --------------------------------------------------
        # Lugar
        # --------------------------------------------------

        if partido["lugar"]:
            evento.add(
                "location",
                partido["lugar"]
            )

        # --------------------------------------------------
        # Descripción
        # --------------------------------------------------

        descripcion = (
            "División de Honor Plata Femenina\n"
            "Liga Regular - Grupo C\n"
            f"Jornada: {partido['jornada']}\n"
            f"Local: {partido['local']}\n"
            f"Visitante: {partido['visitante']}"
        )

        if partido["lugar"]:
            descripcion += (
                f"\nPabellón: {partido['lugar']}"
            )

        evento.add(
            "description",
            descripcion
        )

        # --------------------------------------------------
        # Alarmas
        # --------------------------------------------------

        alarma_24h = Event()

        # Usamos VALARM correctamente a continuación.
        from icalendar import Alarm

        alarm1 = Alarm()
        alarm1.add(
            "action",
            "DISPLAY"
        )
        alarm1.add(
            "description",
            "Partido BM La Roca mañana"
        )
        alarm1.add(
            "trigger",
            timedelta(hours=-24)
        )

        evento.add_component(alarm1)

        alarm2 = Alarm()
        alarm2.add(
            "action",
            "DISPLAY"
        )
        alarm2.add(
            "description",
            "Partido BM La Roca en 2 horas"
        )
        alarm2.add(
            "trigger",
            timedelta(hours=-2)
        )

        evento.add_component(alarm2)

        calendario.add_component(evento)

        print(
            f"OK: {partido['fecha']} - "
            f"{partido['local']} vs "
            f"{partido['visitante']}"
        )

    # ------------------------------------------------------
    # Guardar ICS
    # ------------------------------------------------------

    with open(
        "bm-la-roca.ics",
        "wb"
    ) as archivo:

        archivo.write(
            calendario.to_ical()
        )

    print(
        "Calendario generado correctamente: "
        "bm-la-roca.ics"
    )


if __name__ == "__main__":
    main()
