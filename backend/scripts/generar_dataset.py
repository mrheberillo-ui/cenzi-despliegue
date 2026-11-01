"""Genera el dataset sintético de consultas de clientes de Cenzi.

Cada intención tiene varias *frases base*; de cada frase base se derivan
variantes (saludos, cortesías, minúsculas, sin acentos, errores de tecleo y
abreviaturas). La columna ``frase_base`` permite partir el dataset por grupos
para que una misma frase no aparezca en entrenamiento y en prueba.

Uso:
    python scripts/generar_dataset.py            # escribe data/consultas_cenzi.csv
"""
from __future__ import annotations

import csv
import random
import unicodedata
from pathlib import Path

SEMILLA = 42
VARIANTES_POR_FRASE = 5
RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "data" / "consultas_cenzi.csv"

# intención -> (acción, frases base)
FRASES: dict[str, tuple[str, list[str]]] = {
    "consultar_saldo": ("responder", [
        "cuánto debo de mi crédito",
        "quiero saber mi saldo pendiente",
        "cuál es el saldo de mi préstamo",
        "me pueden decir cuánto me falta por pagar",
        "dónde consulto lo que debo",
        "necesito saber el monto para liquidar",
        "cuánto tengo que pagar para terminar mi crédito",
        "cómo veo mi saldo en la app",
        "saldo actual de mi cuenta",
        "cuánto es mi deuda total",
        "me dices mi adeudo",
        "quiero ver cuánto llevo pagado y cuánto falta",
        "monto para liquidar anticipadamente",
        "cuál es mi saldo al día de hoy",
        "cuánto debo todavía",
        "cuánto sería para pagar todo de una vez",
        "información de mi saldo",
        "cuánto me queda de deuda",
    ]),
    "fecha_pago": ("responder", [
        "cuándo es mi fecha de pago",
        "qué día me toca pagar",
        "hasta cuándo tengo para pagar este mes",
        "cuál es la fecha límite de mi mensualidad",
        "se me olvidó qué día vence mi pago",
        "cada cuándo tengo que pagar",
        "si pago un día después me cobran algo",
        "cuándo vence mi próxima quincena",
        "qué día es el corte",
        "cuándo tengo que hacer el siguiente pago",
        "cuál es mi día de pago",
        "en qué fecha debo depositar",
        "vence mañana mi pago o pasado",
        "fecha de vencimiento de mi crédito",
        "cuándo cae mi pago de este mes",
        "hasta qué día puedo pagar sin recargo",
        "qué día se vence la mensualidad",
        "mi pago es los días 15 o los 30",
    ]),
    "medios_pago": ("responder", [
        "dónde puedo pagar mi crédito",
        "puedo pagar en oxxo",
        "cuál es la clabe para transferir mi pago",
        "aceptan pago con tarjeta",
        "cómo pago desde la app",
        "puedo pagar en una tienda de conveniencia",
        "qué referencia uso para depositar",
        "se puede domiciliar el pago",
        "en qué bancos puedo depositar",
        "formas de pago disponibles",
        "puedo pagar por spei",
        "dónde hago mi depósito",
        "me pasas los datos para transferir",
        "aceptan efectivo en sucursal",
        "se puede pagar en walmart o en farmacias",
        "número de cuenta para pagar",
        "cómo hago el pago en línea",
        "puedo pagar con mi tarjeta de débito desde el celular",
    ]),
    "pago_no_reflejado": ("responder", [
        "ya pagué y no aparece mi pago",
        "hice una transferencia y no se refleja",
        "mi pago no sale en la app",
        "deposité ayer y sigue saliendo que debo",
        "pagué en oxxo y no me lo han aplicado",
        "cuánto tarda en verse mi pago",
        "no me registraron el abono",
        "pagué a tiempo pero me marca atraso",
        "mi abono no aparece",
        "ya transferí pero sigue igual mi saldo",
        "no veo reflejado mi depósito",
        "el pago que hice no se ve",
        "me siguen cobrando aunque ya pagué",
        "hace dos días pagué y nada",
        "no se ha acreditado mi pago",
        "pagué por spei y no aparece en mi cuenta",
        "ya deposité y me sigue saliendo vencido",
        "mi pago de la semana pasada no aparece",
    ]),
    "estatus_solicitud": ("responder", [
        "cómo va mi solicitud de crédito",
        "ya aprobaron mi préstamo",
        "en qué estatus está mi trámite",
        "cuánto tardan en responder mi solicitud",
        "me dijeron que me llamarían y no me han dicho nada",
        "quiero saber si me autorizaron",
        "cuándo depositan el crédito aprobado",
        "sigue en revisión mi solicitud",
        "qué pasó con mi solicitud",
        "ya revisaron mis documentos",
        "tengo respuesta de mi crédito",
        "cuándo me dicen si me dan el préstamo",
        "sigue pendiente mi trámite",
        "me aprobaron o me rechazaron",
        "cuándo me depositan el dinero del préstamo",
        "ya pasó una semana y no sé nada de mi solicitud",
        "cómo saber si fui aceptado",
        "seguimiento a mi solicitud de préstamo",
    ]),
    "requisitos_credito": ("responder", [
        "qué necesito para pedir un crédito",
        "cuáles son los requisitos para un préstamo",
        "qué documentos piden",
        "puedo sacar un crédito si soy independiente",
        "piden aval para el préstamo",
        "necesito comprobante de ingresos",
        "cuál es la edad mínima para solicitar",
        "me pueden prestar si estoy en buró",
        "qué papeles necesito",
        "cómo solicito un préstamo",
        "quiero pedir un crédito nuevo",
        "me prestan con ine solamente",
        "qué se necesita para un préstamo personal",
        "cuánto me pueden prestar",
        "puedo pedir crédito sin comprobante de ingresos",
        "si tengo mal historial me dan crédito",
        "requisitos para pyme",
        "cómo tramito un crédito",
    ]),
    "tasa_cat": ("responder", [
        "cuál es la tasa de interés",
        "qué cat tiene el crédito",
        "cuánto cobran de interés al mes",
        "cuánto voy a pagar en total de intereses",
        "la tasa es fija o variable",
        "por qué me cobran tantos intereses",
        "cuál es el costo anual total",
        "cuánto es la comisión por apertura",
        "cuánto interés cobran",
        "de cuánto es el interés anual",
        "qué porcentaje de interés manejan",
        "cuál es el cat promedio",
        "cobran comisiones",
        "cuánto pago de intereses al final",
        "el interés es muy alto",
        "tasa anual del préstamo",
        "cuánto cobran por pagar tarde",
        "de cuánto es la penalización por atraso",
    ]),
    "sucursales_horarios": ("responder", [
        "dónde hay una sucursal",
        "a qué hora abren",
        "qué horario tienen los sábados",
        "cuál es la sucursal más cercana",
        "abren en domingo",
        "dirección de la sucursal en querétaro",
        "a qué hora cierran hoy",
        "tienen sucursal en san juan del río",
        "dónde están ubicados",
        "horario de atención",
        "están abiertos hoy",
        "hay oficina en el centro",
        "cuál es la dirección",
        "a qué hora puedo ir a la sucursal",
        "dónde queda la oficina más cerca de mí",
        "horario de sucursal entre semana",
        "abren en días festivos",
        "ubicación de sus oficinas",
    ]),
    "actualizar_datos": ("responder", [
        "quiero cambiar mi número de teléfono",
        "cómo actualizo mi correo",
        "me cambié de domicilio",
        "necesito modificar mis datos personales",
        "cambié de celular y quiero registrarlo",
        "cómo cambio mi dirección",
        "mi correo está mal escrito",
        "quiero poner otro teléfono de contacto",
        "quiero actualizar mi información",
        "cambié mi correo electrónico",
        "mi teléfono ya no es el mismo",
        "actualizar domicilio",
        "cómo registro mi nuevo número",
        "corregir mi nombre en el sistema",
        "quiero cambiar el correo donde me llegan las notificaciones",
        "ya no vivo en la misma dirección",
        "modificar mi número de contacto",
        "cambio de datos de contacto",
    ]),
    "estado_cuenta": ("responder", [
        "cómo descargo mi estado de cuenta",
        "no me llegó mi estado de cuenta",
        "necesito mis movimientos del mes",
        "dónde veo mi historial de pagos",
        "me pueden mandar mi estado de cuenta por correo",
        "quiero una constancia de mis pagos",
        "cómo obtengo un comprobante de pago",
        "necesito la carta de liquidación",
        "dónde descargo mi estado de cuenta",
        "quiero mi comprobante de pago",
        "me mandas mi historial",
        "necesito un documento que diga que ya pagué",
        "carta de no adeudo",
        "cómo saco mis movimientos",
        "no encuentro mi estado de cuenta en la app",
        "estado de cuenta del mes pasado",
        "quiero el resumen de mis pagos",
        "documento de liquidación de mi crédito",
    ]),
    "reestructura": ("responder", [
        "no puedo pagar este mes",
        "quiero una prórroga",
        "me quedé sin trabajo y no puedo pagar",
        "se puede reestructurar mi crédito",
        "puedo pagar menos este mes",
        "necesito un convenio de pago",
        "me pueden dar más plazo",
        "tengo problemas para pagar qué opciones hay",
        "necesito ayuda para pagar",
        "no me alcanza para la mensualidad",
        "puedo diferir mis pagos",
        "me atrasé y no sé qué hacer",
        "quiero bajar la mensualidad",
        "hay algún programa de apoyo",
        "puedo ampliar el plazo de mi crédito",
        "estoy enfermo y no puedo pagar",
        "quiero negociar mi deuda",
        "me pueden congelar los pagos",
    ]),
    "aclaracion": ("escalar", [
        "me cobraron de más",
        "hay un cargo que no reconozco",
        "me descontaron dos veces",
        "el monto que me cobran no es correcto",
        "quiero levantar una aclaración",
        "me cobraron una comisión que no debía",
        "aparece un pago que yo no hice",
        "mi saldo no coincide con lo que pagué",
        "no reconozco este cobro",
        "me están cobrando algo que no es",
        "me aplicaron un cargo indebido",
        "me cobraron doble el pago",
        "quiero que revisen un cobro",
        "el cobro está mal",
        "me cargaron intereses que no corresponden",
        "hay un error en mi estado de cuenta",
        "me cobraron una penalización injusta",
        "no entiendo este cargo y creo que está mal",
    ]),
    "queja": ("escalar", [
        "quiero poner una queja",
        "el asesor me trató muy mal",
        "estoy muy molesto con el servicio",
        "me llaman a cada rato para cobrarme",
        "nadie me resuelve nada",
        "voy a reportarlos a condusef",
        "pésima atención en la sucursal",
        "me amenazaron por teléfono para cobrar",
        "quiero hablar con un supervisor",
        "esto es un pésimo servicio",
        "me siento engañado",
        "me hicieron esperar horas",
        "el trato fue grosero",
        "exijo una solución ya",
        "estoy harto de que no me atiendan",
        "quiero reportar a un empleado",
        "me acosan con llamadas de cobranza",
        "nunca contestan el teléfono",
    ]),
}

PREFIJOS = ["", "", "", "hola ", "buenas tardes ", "buen día, ", "oye ", "disculpe ", "una pregunta, "]
SUFIJOS = ["", "", "", " por favor", " gracias", "?", " porfa", " me urge", " de favor"]
ABREVIATURAS = {
    "por favor": "xfa", "porque": "xq", "qué": "q", "que": "q",
    "también": "tmb", "teléfono": "tel", "número": "num", "cuánto": "cnto",
    "crédito": "cred", "información": "info",
}


def sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def con_error_de_tecleo(texto: str, rng: random.Random) -> str:
    letras = [i for i, c in enumerate(texto) if c.isalpha()]
    if len(letras) < 4:
        return texto
    i = rng.choice(letras[1:-1])
    operacion = rng.choice(["intercambio", "omision", "duplicado"])
    if operacion == "intercambio" and i + 1 < len(texto):
        return texto[:i] + texto[i + 1] + texto[i] + texto[i + 2:]
    if operacion == "omision":
        return texto[:i] + texto[i + 1:]
    return texto[:i] + texto[i] + texto[i:]


def abreviado(texto: str) -> str:
    for largo, corto in ABREVIATURAS.items():
        texto = texto.replace(largo, corto)
    return texto


def variante(frase: str, rng: random.Random) -> str:
    texto = rng.choice(PREFIJOS) + frase + rng.choice(SUFIJOS)
    if rng.random() < 0.35:
        texto = sin_acentos(texto)
    if rng.random() < 0.25:
        texto = abreviado(texto)
    if rng.random() < 0.30:
        texto = con_error_de_tecleo(texto, rng)
    if rng.random() < 0.15:
        texto = texto.capitalize()
    if rng.random() < 0.05:
        texto = texto.upper()
    return " ".join(texto.split())


def generar() -> list[dict[str, str]]:
    rng = random.Random(SEMILLA)
    filas: list[dict[str, str]] = []
    for intencion, (accion, frases) in FRASES.items():
        for j, frase in enumerate(frases):
            grupo = f"{intencion}-{j:02d}"
            vistos = {frase}
            filas.append({"texto": frase, "intencion": intencion, "accion": accion, "frase_base": grupo})
            intentos = 0
            while len(vistos) < VARIANTES_POR_FRASE + 1 and intentos < 200:
                intentos += 1
                v = variante(frase, rng)
                if v not in vistos:
                    vistos.add(v)
                    filas.append({"texto": v, "intencion": intencion, "accion": accion, "frase_base": grupo})
    rng.shuffle(filas)
    for k, fila in enumerate(filas, start=1):
        fila["id"] = f"C{k:05d}"
    return filas


def main() -> None:
    filas = generar()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "texto", "intencion", "accion", "frase_base"])
        w.writeheader()
        w.writerows(filas)
    print(f"{len(filas)} consultas escritas en {SALIDA}")


if __name__ == "__main__":
    main()
