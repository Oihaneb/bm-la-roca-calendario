import re
import hashlib
import requests

from bs4 import BeautifulSoup
from icalendar import Calendar, Event, Alarm
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


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

EQUIPO = "MUBAK - BM LA ROCA"
TIMEZONE = ZoneInfo("Europe/Madrid")


def limpiar(texto):
    return re.sub(r"\s+", " ", texto).strip()


def crear_uid(jornada, fecha, local, visitante):
    texto = f"{jornada}|{fecha}|{local}|{visitante}"
    return hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest() + "@bm-la-roca"


def main():

    print("Descargando calendario oficial RFEBM...")

    respuesta = requests.get(
        URL,
        timeout=60,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/139.0 Safari/537.36"
            ),
            "Accept-Language": "es-ES,es;q=0.9",
        },
    )

    print("Código HTTP:", respuesta.status_code)
    print("Tamaño de la página:", len(respuesta.text))

    respuesta.raise_for_status()

    soup = BeautifulSoup(
        respuesta.text,
        "html.parser"
    )

    calendario = Calendar()

    calendario.add(
        "prodid",
        "-//BM La Roca//DH Plata Femenina//ES"
    )
    calendario.add("version", "2.0")
    calendario.add("calscale", "GREGORIAN")
    calendario.add("method", "PUBLISH")
    calendario.add(
        "x-wr-calname",
        "BM La Roca - División de Honor Plata Femenina"
    )
    calendario.add(
        "x-wr-timezone",
        "Europe/Madrid"
    )

    jornada = None
    fecha_jornada = None
    partidos = []

    filas = soup.find_all("tr")

    print("Filas encontradas:", len(filas))

    for fila in filas:

        texto = limpiar(
            fila.get_text(
                " ",
                strip=True
            )
        )

        if not texto:
            continue

        # -----------------------------------------------
        # Detectar jornada
        # -----------------------------------------------

        match_jornada = re.search(
            r"JORNADA\s+(\d+)\s*\((\d{2})-(\d{2})-(\d{4})\)",
            texto,
            re.IGNORECASE
        )

        if match_jornada:

            jornada = int(
                match_jornada.group(1)
            )

            fecha_jornada = datetime.strptime(
                (
                    f"{match_jornada.group(2)}-"
                    f"{match_jornada.group(3)}-"
                    f"{match_jornada.group(4)}"
                ),
                "%d-%m-%Y"
            ).date()

            print(
                f"Jornada {jornada} "
                f"({fecha_jornada})"
            )

            continue

        # -----------------------------------------------
        # Solo partidos de BM La Roca
        # -----------------------------------------------

        if "BM LA ROCA" not in texto.upper():
            continue

        print("PARTIDO ENCONTRADO:")
        print(texto)

        columnas = [
            limpiar(
                celda.get_text(
                    " ",
                    strip=True
                )
            )
            for celda in fila.find_all(
                ["td", "th"]
            )
        ]

        print("COLUMNAS:", columnas)

        if not columnas:
            continue

        # -----------------------------------------------
        # La primera columna contiene los dos equipos
        # -----------------------------------------------

        equipos = columnas[0]

        # Quitar VS
        equipos = re.sub(
            r"^\s*VS\s+",
            "",
            equipos,
            flags=re.IGNORECASE
        )

        partes = re.split(
            r"\s+-\s+",
            equipos
        )

        if len(partes) < 2:
            print(
                "No se pudieron separar los equipos"
            )
            continue

        # Normalmente son exactamente dos
        local = limpiar(partes[0])
        visitante = limpiar(
            " - ".join(partes[1:])
        )

        # -----------------------------------------------
        # Buscar fecha/hora
        # -----------------------------------------------

        fecha = fecha_jornada
        hora = None

        for columna in columnas:

            # Fecha + hora
            m = re.search(
                r"(\d{2})/(\d{2})/(\d{4})\s+"
                r"(\d{1,2}):(\d{2})",
                columna
            )

            if m:

                fecha = datetime.strptime(
                    (
                        f"{m.group(1)}/"
                        f"{m.group(2)}/"
                        f"{m.group(3)}"
                    ),
                    "%d/%m/%Y"
                ).date()

                hora = (
                    int(m.group(4)),
                    int(m.group(5))
                )

                break

            # Solo hora
            m = re.fullmatch(
                r"(\d{1,2}):(\d{2})",
                columna
            )

            if m:

                h = int(m.group(1))
                minutos = int(m.group(2))

                if h != 0 or minutos != 0:

                    hora = (
                        h,
                        minutos
                    )

        if fecha is None:
            print(
                "No se pudo determinar la fecha"
            )
            continue

        # -----------------------------------------------
        # Buscar pabellón
        # -----------------------------------------------

        lugar = ""

        for columna in columnas[1:]:

            if (
                columna
                and columna not in [
                    "-",
                    "0 - 0",
                    "0:00"
                ]
                and not re.fullmatch(
                    r"\d{1,2}:\d{2}",
                    columna
                )
                and not re.fullmatch(
                    r"\d{2}/\d{2}/\d{4}.*",
                    columna
                )
            ):

                if (
                    "PABELL" in columna.upper()
                    or "POLIESPORT" in columna.upper()
                    or "PALAU" in columna.upper()
                    or "POLIDEPORT" in columna.upper()
                ):
                    lugar = columna
                    break

        partidos.append(
            {
                "jornada": jornada,
                "fecha": fecha,
                "hora": hora,
                "local": local,
                "visitante": visitante,
                "lugar": lugar,
            }
        )

    print(
        "--------------------------------"
    )

    print(
        "PARTIDOS ENCONTRADOS:",
        len(partidos)
    )

    print(
        "--------------------------------"
    )

    if not partidos:

        raise RuntimeError(
            "La página RFEBM se ha descargado, "
            "pero no se han podido localizar "
            "los partidos de BM La Roca."
        )

    # -----------------------------------------------
    # Eliminar duplicados
    # -----------------------------------------------

    unicos = {}

    for partido in partidos:

        clave = (
            partido["jornada"],
            partido["fecha"],
            partido["local"],
            partido["visitante"],
        )

        unicos[clave] = partido

    partidos = list(unicos.values())

    partidos.sort(
        key=lambda p: (
            p["fecha"],
            p["jornada"] or 999
        )
    )

    # -----------------------------------------------
    # Crear eventos
    # -----------------------------------------------

    for partido in partidos:

        evento = Event()

        uid = crear_uid(
            partido["jornada"],
            partido["fecha"],
            partido["local"],
            partido["visitante"]
        )

        evento.add(
            "uid",
            uid
        )

        evento.add(
            "summary",
            (
                f"🤾 {partido['local']} - "
                f"{partido['visitante']}"
            )
        )

        # -------------------------------------------
        # Con hora confirmada
        # -------------------------------------------

        if partido["hora"]:

            h, minutos = partido["hora"]

            inicio = datetime(
                partido["fecha"].year,
                partido["fecha"].month,
                partido["fecha"].day,
                h,
                minutos,
                tzinfo=TIMEZONE
            )

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

            # Aviso 24 horas antes
            alarma1 = Alarm()
            alarma1.add(
                "action",
                "DISPLAY"
            )
            alarma1.add(
                "description",
                "Partido BM La Roca mañana"
            )
            alarma1.add(
                "trigger",
                timedelta(hours=-24)
            )

            evento.add_component(
                alarma1
            )

            # Aviso 2 horas antes
            alarma2 = Alarm()
            alarma2.add(
                "action",
                "DISPLAY"
            )
            alarma2.add(
                "description",
                "Partido BM La Roca en 2 horas"
            )
            alarma2.add(
                "trigger",
                timedelta(hours=-2)
            )

            evento.add_component(
                alarma2
            )

        # -------------------------------------------
        # Sin hora confirmada
        # -------------------------------------------

        else:

            evento.add(
                "dtstart",
                partido["fecha"]
            )

            evento.add(
                "dtend",
                partido["fecha"]
                + timedelta(days=1)
            )

            evento.add(
                "description",
                "Hora pendiente de confirmar."
            )

        # -------------------------------------------
        # Lugar
        # -------------------------------------------

        if partido["lugar"]:

            evento.add(
                "location",
                partido["lugar"]
            )

        # -------------------------------------------
        # Descripción
        # -------------------------------------------

        descripcion = (
            "División de Honor Plata Femenina\n"
            "Liga Regular - Grupo C\n\n"
            f"Jornada: {partido['jornada']}\n"
            f"Local: {partido['local']}\n"
            f"Visitante: {partido['visitante']}"
        )

        if partido["lugar"]:

            descripcion += (
                f"\nPabellón: "
                f"{partido['lugar']}"
            )

        evento.add(
            "description",
            descripcion
        )

        calendario.add_component(
            evento
        )

    # -----------------------------------------------
    # Guardar calendario
    # -----------------------------------------------

    with open(
        "bm-la-roca.ics",
        "wb"
    ) as archivo:

        archivo.write(
            calendario.to_ical()
        )

    print(
        "--------------------------------"
    )

    print(
        "CALENDARIO GENERADO CORRECTAMENTE"
    )

    print(
        "Archivo: bm-la-roca.ics"
    )

    print(
        "Partidos:",
        len(partidos)
    )

    print(
        "--------------------------------"
    )


if __name__ == "__main__":
    main()
