import os
import re
import html
import json
import asyncio
import hashlib
import logging
import unicodedata
import requests
import feedparser
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from google import genai

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
# httpx a livello INFO stampa nei log l'URL con il token del bot: lo silenziamo.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

FANTA_COOKIE = os.getenv("FANTA_COOKIE", "")
FANTA_BEARER_TOKEN = os.getenv("FANTA_BEARER_TOKEN", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "6226253008"))

client = None
if GEMINI_KEY:
    client = genai.Client(api_key=GEMINI_KEY)

CHAT_ID_LEGA_1 = int(os.getenv("CHAT_ID_LEGA_1", "0"))
CHAT_ID_LEGA_2 = int(os.getenv("CHAT_ID_LEGA_2", "0"))

TEAMS_MAP = {
    # Lega 1: Fanta4Reich
    18831834: {"name": "UwU", "owner": "gibo", "lega": 1},
    18883778: {"name": "NicoPanz", "owner": "Ciccio", "lega": 1},
    18833116: {"name": "Al-Qaeda United", "owner": "spoleto17", "lega": 1},
    18832547: {"name": "CHIVUISMO", "owner": "Gabbo", "lega": 1},
    18831242: {"name": "Deportivo Sa Carogna", "owner": "Giaime", "lega": 1},
    18832350: {"name": "Luton Down", "owner": "Manuel", "lega": 1},
    18883572: {"name": "BENE EH MANCO MALEN", "owner": "Lamine Kialunga", "lega": 1},
    18885993: {"name": "RSA riabilitazione", "owner": "El vecho", "lega": 1},
    # Lega 2: Fantacalcio Stalloni
    19197193: {"name": "HINTER X HINTER", "owner": "gibo", "lega": 2},
    19196752: {"name": "DEMOCRAZIA CRISTANTE", "owner": "Cryan Bristante", "lega": 2},
    19213432: {"name": "COSTIERA ANALFITANA", "owner": "Manuel", "lega": 2},
    19196408: {"name": "CHIVUISMO", "owner": "Gabbo", "lega": 2},
    19197005: {"name": "Scrotone", "owner": "loffredo03", "lega": 2},
    19209834: {"name": "FREE SAPOMODORO FC", "owner": "Marco Priolo Pinolo", "lega": 2},
    19176402: {"name": "IchNusa", "owner": "Giaime", "lega": 2},
    19197286: {"name": "FC Pinolandia", "owner": "Ernesto Tavaroni", "lega": 2}
}

# Indici PER LEGA: "CHIVUISMO" esiste in entrambe le leghe con ID diversi,
# un dizionario unico farebbe vincere sempre l'ultimo (Lega 2).
TEAM_IDS_BY_LEGA = {
    n: {v["name"].strip().lower(): k for k, v in TEAMS_MAP.items() if v["lega"] == n} for n in (1, 2)
}
OWNERS_BY_LEGA = {
    n: {v["name"].strip().lower(): v["owner"] for v in TEAMS_MAP.values() if v["lega"] == n} for n in (1, 2)
}

ROSE_LEGA_1 = {
    "Deportivo Sa Carogna": ['Svilar', 'Caprile', 'Gollini', 'Mancini', 'Ramon', 'Ostigard', 'Valdepenas', 'Miranda J.', 'Koulierakis', 'De Winter', 'Bartesaghi', 'Calhanoglu', 'Baturina', 'Gudmundsson A.', 'Bernardeschi', 'Massolin', 'Sucic P.', 'Mbangula', 'Gonzalez N.', 'Ramos G.', 'Krstovic', 'Lontani', 'Yeboah J.', 'Camarda', 'Piccoli'],
    "UwU": ['Vicario', 'Grabara', 'Perri', 'Chalobah T.', 'Pavlovic', 'Akanji', 'Di Lorenzo', 'Jimenez A.', 'Bernasconi', 'Comuzzo', 'Diego Carlos', 'Orsolini', 'Da Cunha', 'Alajbegovic', 'Mastantuono', 'Zaniolo', 'Cacciamani', 'Cambiaghi', 'Modric', 'Thuram', 'Beto', 'Pellegrino M.', 'Soulè', 'Dovbyk', 'Castro S.'],
    "Luton Down": ['Maignan', 'Terracciano', 'Falcone', 'Wesley', 'Solet', 'Scalvini', 'Mangas', 'Hainaut', 'Tiago Gabriel', 'Coco', 'Theate', 'Frattesi', 'Vlasic', 'Samardzic', 'Conceicao', 'Chukwueze', 'Colpani', 'Adzic', 'Douglas Luiz', 'Kolo Muani', 'Kean', 'Berardi', 'Varela G.', 'Romero D.', 'Kevin Carlos'],
    "CHIVUISMO": ['Martinez Jo.', 'Provedel', 'Di Gennaro', 'Bastoni', 'Kamara H.', 'Hermoso', 'Carlos Augusto', 'Celik', 'Cinquegrano', 'Bella-Kotchap', 'Mina', 'McTominay', 'Zaccagni', 'Jones C.', 'Romano', 'Fitz-Jim', 'Busio', 'Loftus-Cheek', 'Locatelli', 'Martinez L.', 'Laurientè', 'Bonny', 'Santos A.', 'Raspadori', 'Adams C.'],
    "Al-Qaeda United": ['Carnesecchi', 'Palmisani', 'Sportiello', 'Gila', 'Vojvoda', 'Couto', 'Vasquez', 'Valeri', 'Sugawara', 'Kristensen T.', 'Obert', 'Rabiot', 'Atta', 'Ekkelenkamp', 'Ederson D.S.', 'Pisilli', 'Bernabè', 'Perrone', 'Volpato', 'Malen', 'Simeone', 'Vitinha O.', 'Kvernadze', 'Gnonto', 'Maldini'],
    "BENE EH MANCO MALEN": ['Okoye', 'Muric', 'Skorupski', 'Dimarco', 'Bremer', 'Zappacosta', 'Spence', 'Bellanova', 'Bracaglia', 'Idzes', 'Zortea', 'Barella', 'Diouf', 'McKennie', 'Zambo Anguissa', 'Calò', 'Thorstvedt', 'Thuram K.', 'Adopo', 'Davis K.', 'Scamacca', 'Esposito F.P.', 'Yildiz', 'Diao', 'Colombo'],
    "NicoPanz": ['Butez', 'Mandas', 'Sanchez Ro.', 'Kalulu', 'Molina N.', 'Stones', "N'Dicka", 'Belghali', 'Doekhi', 'Badiashile', 'Spinazzola', 'Paz N.', 'De Bruyne', 'Sarr P.', 'Zielinski', 'Moreira', 'Kessiè', 'Taylor K.', 'Konè M.', 'Hojlund', 'Dybala', 'De Ketelaere', 'Adams A.', 'Raimondo', 'Bowie'],
    "RSA riabilitazione": ['Meret', 'De Gea', 'Milinkovic-Savic V.', 'Rrahmani', 'Bisseck', 'Tavares N.', 'Lucumì', 'Valle', 'Delprato', 'Lulli', 'Dodò', 'Pulisic', 'Mora', 'Milla', 'Rodriguez Je.', 'Saelemaekers', 'Gaetano', 'Rowe', 'Cancellieri', 'Douvikas', 'Woltemade', 'Pinamonti', 'Esposito Se.', 'Tourè E.', 'Cutrone']
}

ROSE_LEGA_2 = {
    "IchNusa": ['Maignan', 'Palmisani', 'Terracciano', 'Molina N.', 'Ostigard', 'Couto', 'De Winter', 'Bernasconi', 'Hainaut', 'Lucumì', 'Theate', 'Baturina', 'McTominay', 'Ekkelenkamp', 'Calò', 'Sucic P.', 'Mbangula', 'Busio', 'Bernardeschi', 'Ramos G.', 'Simeone', 'Beto', 'Adams A.', 'Mendy P.', 'Piccoli'],
    "CHIVUISMO": ['Martinez Jo.', 'Stankovic F.', 'Skorupski', 'Solet', 'Spence', 'Bisseck', 'Mangas', 'Dragusin', 'Hermoso', 'Belghali', 'Bella-Kotchap', 'Mora', 'Barella', 'Alajbegovic', 'Conceicao', 'Locatelli', 'Milla', 'Saelemaekers', 'Politano', 'Thuram', 'Kean', 'Pinamonti', 'Bonny', 'Varela G.', 'Vitinha O.'],
    "DEMOCRAZIA CRISTANTE": ['Butez', 'Gollini', 'Sanchez Ro.', 'Wesley', 'Akanji', 'Di Lorenzo', 'Tavares N.', 'Kaiki', 'Bartesaghi', 'Miranda J.', 'Diego Carlos', 'Paz N.', 'Diouf', 'Moreira', 'Liberali', 'Cambiaghi', 'Colpani', 'Zalewski', 'Cristante', 'Dybala', 'Scamacca', 'Krstovic', 'Pellegrino M.', 'Diao', 'Soulè'],
    "Scrotone": ['Provedel', 'De Gea', 'Mandas', 'Dimarco', 'Gila', 'Valle', 'Vasquez', 'Pavard', 'Zappacosta', 'Delprato', 'Carlos Augusto', 'De Bruyne', 'Vlasic', 'Goncalves P.', 'Zielinski', 'Rowe', 'Samardzic', 'Konè M.', 'Cacciamani', 'Douvikas', 'Davis K.', 'Berardi', 'Boga', 'Santos A.', 'Colombo'],
    "HINTER X HINTER": ['Meret', 'Perri', 'Milinkovic-Savic V.', 'Rrahmani', 'Mancini', 'Pavlovic', 'Chalobah T.', 'Kempf', 'Tiago Gabriel', 'Kristensen T.', 'Spinazzola', 'Pulisic', 'Atta', 'Ederson D.S.', 'Adzic', 'Pisilli', 'Fazzini', 'Casadei', 'Sarr P.', 'Martinez L.', 'Laurientè', 'Yeboah J.', 'Neres', 'Tourè E.', 'Kvernadze'],
    "FC Pinolandia": ['Carnesecchi', 'Okoye', 'Sportiello', 'Kalulu', "N'Dicka", 'Vojvoda', 'Lulli', 'Kamara H.', 'Scalvini', 'Ismajli', 'Balerdi', 'Mastantuono', 'Frattesi', 'Zaniolo', 'McKennie', 'Kessiè', 'Romano', 'Unai Gomez', 'Pellegrini Lo.', 'Kolo Muani', 'Woltemade', 'Castro S.', 'Esposito Se.', 'Raspadori', 'Bowie'],
    "FREE SAPOMODORO FC": ['Svilar', 'Corvi', 'Falcone', 'Bremer', 'Stones', 'Mina', 'Bracaglia', 'Valeri', 'Pedraza', 'Jimenez A.', 'Monterisi', 'Rabiot', 'Orsolini', 'Zaccagni', 'Cissè A.', 'Gonzalez N.', 'Taylor K.', 'Vergara', 'Modric', 'Malen', 'Raimondo', 'Romero D.', 'De Ketelaere', 'Kevin Carlos', 'Dovbyk'],
    "COSTIERA ANALFITANA": ['Vicario', 'Caprile', 'Grabara', 'Bastoni', 'Ramon', 'Valdepenas', 'Celik', 'Marcandalli', 'Comuzzo', 'Obert', 'Cambiaso', 'Calhanoglu', 'Da Cunha', 'Gudmundsson A.', 'Volpato', 'Jones C.', 'Gaetano', 'Bernabè', 'Baldanzi', 'Hojlund', 'Esposito F.P.', 'Yildiz', 'Lucca', 'Maldini', 'Adams C.']
}

CALENDARIO_LEGA_1 = {
    1: {"nome": "1ª Giornata lega", "serie_a": 3, "matches": [{"home": "Al-Qaeda United", "away": "RSA riabilitazione", "p_home": 70.0, "p_away": 64.0, "score": "1-0"}, {"home": "Deportivo Sa Carogna", "away": "Luton Down", "p_home": 75.5, "p_away": 70.5, "score": "2-1"}, {"home": "BENE EH MANCO MALEN", "away": "UwU", "p_home": 74.5, "p_away": 79.0, "score": "2-3"}, {"home": "CHIVUISMO", "away": "NicoPanz", "p_home": 78.5, "p_away": 84.5, "score": "3-4"}]},
    2: {"nome": "2ª Giornata lega", "serie_a": 4, "matches": [{"home": "RSA riabilitazione", "away": "CHIVUISMO", "p_home": 67.0, "p_away": 77.0, "score": "1-2"}, {"home": "NicoPanz", "away": "BENE EH MANCO MALEN", "p_home": 68.0, "p_away": 67.5, "score": "1-1"}, {"home": "UwU", "away": "Deportivo Sa Carogna", "p_home": 80.5, "p_away": 73.0, "score": "3-2"}, {"home": "Luton Down", "away": "Al-Qaeda United", "p_home": 75.5, "p_away": 76.0, "score": "2-2"}]},
    3: {"nome": "3ª Giornata lega", "serie_a": 5, "matches": [{"home": "Deportivo Sa Carogna", "away": "NicoPanz", "p_home": 72.0, "p_away": 75.0, "score": "1-2"}, {"home": "BENE EH MANCO MALEN", "away": "RSA riabilitazione", "p_home": 74.0, "p_away": 71.0, "score": "2-1"}, {"home": "CHIVUISMO", "away": "Al-Qaeda United", "p_home": 68.5, "p_away": 73.0, "score": "1-2"}, {"home": "UwU", "away": "Luton Down", "p_home": 81.0, "p_away": 74.0, "score": "3-1"}]},
    4: {"nome": "4ª Giornata lega", "serie_a": 6, "matches": [{"home": "Al-Qaeda United", "away": "BENE EH MANCO MALEN", "score": "-"}, {"home": "RSA riabilitazione", "away": "Deportivo Sa Carogna", "score": "-"}, {"home": "NicoPanz", "away": "UwU", "score": "-"}, {"home": "Luton Down", "away": "CHIVUISMO", "score": "-"}]},
    5: {"nome": "5ª Giornata lega", "serie_a": 7, "matches": [{"home": "Deportivo Sa Carogna", "away": "Al-Qaeda United", "score": "-"}, {"home": "BENE EH MANCO MALEN", "away": "CHIVUISMO", "score": "-"}, {"home": "NicoPanz", "away": "Luton Down", "score": "-"}, {"home": "UwU", "away": "RSA riabilitazione", "score": "-"}]},
    6: {"nome": "6ª Giornata lega", "serie_a": 8, "matches": [{"home": "Al-Qaeda United", "away": "UwU", "score": "-"}, {"home": "RSA riabilitazione", "away": "NicoPanz", "score": "-"}, {"home": "BENE EH MANCO MALEN", "away": "Luton Down", "score": "-"}, {"home": "CHIVUISMO", "away": "Deportivo Sa Carogna", "score": "-"}]},
    7: {"nome": "7ª Giornata lega", "serie_a": 9, "matches": [{"home": "Deportivo Sa Carogna", "away": "BENE EH MANCO MALEN", "score": "-"}, {"home": "NicoPanz", "away": "Al-Qaeda United", "score": "-"}, {"home": "UwU", "away": "CHIVUISMO", "score": "-"}, {"home": "Luton Down", "away": "RSA riabilitazione", "score": "-"}]},
    8: {"nome": "8ª Giornata lega", "serie_a": 10, "matches": [{"home": "BENE EH MANCO MALEN", "away": "Al-Qaeda United", "score": "-"}, {"home": "NicoPanz", "away": "Deportivo Sa Carogna", "score": "-"}, {"home": "CHIVUISMO", "away": "RSA riabilitazione", "score": "-"}, {"home": "Luton Down", "away": "UwU", "score": "-"}]},
    9: {"nome": "9ª Giornata lega", "serie_a": 11, "matches": [{"home": "Al-Qaeda United", "away": "NicoPanz", "score": "-"}, {"home": "RSA riabilitazione", "away": "Luton Down", "score": "-"}, {"home": "Deportivo Sa Carogna", "away": "CHIVUISMO", "score": "-"}, {"home": "UwU", "away": "BENE EH MANCO MALEN", "score": "-"}]},
    10: {"nome": "10ª Giornata lega", "serie_a": 12, "matches": [{"home": "BENE EH MANCO MALEN", "away": "Deportivo Sa Carogna", "score": "-"}, {"home": "CHIVUISMO", "away": "UwU", "score": "-"}, {"home": "Luton Down", "away": "NicoPanz", "score": "-"}, {"home": "RSA riabilitazione", "away": "Al-Qaeda United", "score": "-"}]},
    11: {"nome": "11ª Giornata lega", "serie_a": 13, "matches": [{"home": "CHIVUISMO", "away": "BENE EH MANCO MALEN", "score": "-"}, {"home": "Deportivo Sa Carogna", "away": "UwU", "score": "-"}, {"home": "NicoPanz", "away": "RSA riabilitazione", "score": "-"}, {"home": "Al-Qaeda United", "away": "Luton Down", "score": "-"}]},
    12: {"nome": "12ª Giornata lega", "serie_a": 14, "matches": [{"home": "RSA riabilitazione", "away": "BENE EH MANCO MALEN", "score": "-"}, {"home": "Al-Qaeda United", "away": "CHIVUISMO", "score": "-"}, {"home": "UwU", "away": "NicoPanz", "score": "-"}, {"home": "Luton Down", "away": "Deportivo Sa Carogna", "score": "-"}]},
    13: {"nome": "13ª Giornata lega", "serie_a": 15, "matches": [{"home": "Deportivo Sa Carogna", "away": "RSA riabilitazione", "score": "-"}, {"home": "BENE EH MANCO MALEN", "away": "NicoPanz", "score": "-"}, {"home": "CHIVUISMO", "away": "Luton Down", "score": "-"}, {"home": "UwU", "away": "Al-Qaeda United", "score": "-"}]},
    14: {"nome": "14ª Giornata lega", "serie_a": 16, "matches": [{"home": "Al-Qaeda United", "away": "Deportivo Sa Carogna", "score": "-"}, {"home": "RSA riabilitazione", "away": "UwU", "score": "-"}, {"home": "NicoPanz", "away": "CHIVUISMO", "score": "-"}, {"home": "Luton Down", "away": "BENE EH MANCO MALEN", "score": "-"}]},
    15: {"nome": "15ª Giornata lega", "serie_a": 17, "matches": [{"home": "Deportivo Sa Carogna", "away": "Luton Down", "score": "-"}, {"home": "UwU", "away": "RSA riabilitazione", "score": "-"}, {"home": "Al-Qaeda United", "away": "BENE EH MANCO MALEN", "score": "-"}, {"home": "CHIVUISMO", "away": "NicoPanz", "score": "-"}]},
    16: {"nome": "16ª Giornata lega", "serie_a": 18, "matches": [{"home": "Luton Down", "away": "CHIVUISMO", "score": "-"}, {"home": "NicoPanz", "away": "Al-Qaeda United", "score": "-"}, {"home": "BENE EH MANCO MALEN", "away": "UwU", "score": "-"}, {"home": "RSA riabilitazione", "away": "Deportivo Sa Carogna", "score": "-"}]},
    17: {"nome": "17ª Giornata lega", "serie_a": 19, "matches": [{"home": "UwU", "away": "NicoPanz", "score": "-"}, {"home": "Al-Qaeda United", "away": "Luton Down", "score": "-"}, {"home": "CHIVUISMO", "away": "Deportivo Sa Carogna", "score": "-"}, {"home": "BENE EH MANCO MALEN", "away": "RSA riabilitazione", "score": "-"}]},
    18: {"nome": "18ª Giornata lega", "serie_a": 20, "matches": [{"home": "Deportivo Sa Carogna", "away": "Al-Qaeda United", "score": "-"}, {"home": "Luton Down", "away": "UwU", "score": "-"}, {"home": "NicoPanz", "away": "BENE EH MANCO MALEN", "score": "-"}, {"home": "RSA riabilitazione", "away": "CHIVUISMO", "score": "-"}]},
    19: {"nome": "19ª Giornata lega", "serie_a": 21, "matches": [{"home": "UwU", "away": "Deportivo Sa Carogna", "score": "-"}, {"home": "Al-Qaeda United", "away": "CHIVUISMO", "score": "-"}, {"home": "NicoPanz", "away": "RSA riabilitazione", "score": "-"}, {"home": "BENE EH MANCO MALEN", "away": "Luton Down", "score": "-"}]},
    20: {"nome": "20ª Giornata lega", "serie_a": 22, "matches": [{"home": "Deportivo Sa Carogna", "away": "BENE EH MANCO MALEN", "score": "-"}, {"home": "Luton Down", "away": "NicoPanz", "score": "-"}, {"home": "Al-Qaeda United", "away": "RSA riabilitazione", "score": "-"}, {"home": "CHIVUISMO", "away": "UwU", "score": "-"}]},
    21: {"nome": "21ª Giornata lega", "serie_a": 23, "matches": [{"home": "UwU", "away": "Al-Qaeda United", "score": "-"}, {"home": "NicoPanz", "away": "Deportivo Sa Carogna", "score": "-"}, {"home": "BENE EH MANCO MALEN", "away": "CHIVUISMO", "score": "-"}, {"home": "RSA riabilitazione", "away": "Luton Down", "score": "-"}]},
    22: {"nome": "22ª Giornata lega", "serie_a": 24, "matches": [{"home": "Al-Qaeda United", "away": "Deportivo Sa Carogna", "score": "-"}, {"home": "NicoPanz", "away": "UwU", "score": "-"}, {"home": "CHIVUISMO", "away": "Luton Down", "score": "-"}, {"home": "RSA riabilitazione", "away": "BENE EH MANCO MALEN", "score": "-"}]},
    23: {"nome": "23ª Giornata lega", "serie_a": 25, "matches": [{"home": "Deportivo Sa Carogna", "away": "NicoPanz", "score": "-"}, {"home": "Luton Down", "away": "RSA riabilitazione", "score": "-"}, {"home": "UwU", "away": "CHIVUISMO", "score": "-"}, {"home": "BENE EH MANCO MALEN", "away": "Al-Qaeda United", "score": "-"}]},
    24: {"nome": "24ª Giornata lega", "serie_a": 26, "matches": [{"home": "Al-Qaeda United", "away": "UwU", "score": "-"}, {"home": "CHIVUISMO", "away": "BENE EH MANCO MALEN", "score": "-"}, {"home": "RSA riabilitazione", "away": "NicoPanz", "score": "-"}, {"home": "Luton Down", "away": "Deportivo Sa Carogna", "score": "-"}]},
    25: {"nome": "25ª Giornata lega", "serie_a": 27, "matches": [{"home": "CHIVUISMO", "away": "Al-Qaeda United", "score": "-"}, {"home": "UwU", "away": "BENE EH MANCO MALEN", "score": "-"}, {"home": "NicoPanz", "away": "Luton Down", "score": "-"}, {"home": "Deportivo Sa Carogna", "away": "RSA riabilitazione", "score": "-"}]},
    26: {"nome": "26ª Giornata lega", "serie_a": 28, "matches": [{"home": "Luton Down", "away": "Al-Qaeda United", "score": "-"}, {"home": "Deportivo Sa Carogna", "away": "CHIVUISMO", "score": "-"}, {"home": "BENE EH MANCO MALEN", "away": "NicoPanz", "score": "-"}, {"home": "RSA riabilitazione", "away": "UwU", "score": "-"}]},
    27: {"nome": "27ª Giornata lega", "serie_a": 29, "matches": [{"home": "UwU", "away": "Luton Down", "score": "-"}, {"home": "Al-Qaeda United", "away": "NicoPanz", "score": "-"}, {"home": "CHIVUISMO", "away": "RSA riabilitazione", "score": "-"}, {"home": "BENE EH MANCO MALEN", "away": "Deportivo Sa Carogna", "score": "-"}]},
    28: {"nome": "28ª Giornata lega", "serie_a": 30, "matches": [{"home": "Deportivo Sa Carogna", "away": "UwU", "score": "-"}, {"home": "Luton Down", "away": "BENE EH MANCO MALEN", "score": "-"}, {"home": "NicoPanz", "away": "CHIVUISMO", "score": "-"}, {"home": "RSA riabilitazione", "away": "Al-Qaeda United", "score": "-"}]},
    29: {"nome": "29ª Giornata lega", "serie_a": 31, "matches": [{"home": "BENE EH MANCO MALEN", "away": "RSA riabilitazione", "score": "-"}, {"home": "NicoPanz", "away": "Deportivo Sa Carogna", "score": "-"}, {"home": "Luton Down", "away": "UwU", "score": "-"}]},
    30: {"nome": "30ª Giornata lega", "serie_a": 32, "matches": [{"home": "RSA riabilitazione", "away": "Al-Qaeda United", "score": "-"}, {"home": "CHIVUISMO", "away": "Luton Down", "score": "-"}, {"home": "UwU", "away": "NicoPanz", "score": "-"}, {"home": "Deportivo Sa Carogna", "away": "BENE EH MANCO MALEN", "score": "-"}]},
    31: {"nome": "31ª Giornata lega", "serie_a": 33, "matches": [{"home": "NicoPanz", "away": "CHIVUISMO", "score": "-"}, {"home": "Luton Down", "away": "RSA riabilitazione", "score": "-"}, {"home": "Al-Qaeda United", "away": "BENE EH MANCO MALEN", "score": "-"}, {"home": "UwU", "away": "Deportivo Sa Carogna", "score": "-"}]},
    32: {"nome": "32ª Giornata lega", "serie_a": 34, "matches": [{"home": "BENE EH MANCO MALEN", "away": "Luton Down", "score": "-"}, {"home": "RSA riabilitazione", "away": "NicoPanz", "score": "-"}, {"home": "CHIVUISMO", "away": "UwU", "score": "-"}, {"home": "Deportivo Sa Carogna", "away": "Al-Qaeda United", "score": "-"}]},
    33: {"nome": "33ª Giornata lega", "serie_a": 35, "matches": [{"home": "NicoPanz", "away": "BENE EH MANCO MALEN", "score": "-"}, {"home": "Luton Down", "away": "Al-Qaeda United", "score": "-"}, {"home": "CHIVUISMO", "away": "Deportivo Sa Carogna", "score": "-"}, {"home": "UwU", "away": "RSA riabilitazione", "score": "-"}]},
    34: {"nome": "34ª Giornata lega", "serie_a": 36, "matches": [{"home": "BENE EH MANCO MALEN", "away": "UwU", "score": "-"}, {"home": "RSA riabilitazione", "away": "CHIVUISMO", "score": "-"}, {"home": "Luton Down", "away": "Deportivo Sa Carogna", "score": "-"}, {"home": "Al-Qaeda United", "away": "NicoPanz", "score": "-"}]},
    35: {"nome": "35ª Giornata lega", "serie_a": 37, "matches": [{"home": "NicoPanz", "away": "Luton Down", "score": "-"}, {"home": "CHIVUISMO", "away": "BENE EH MANCO MALEN", "score": "-"}, {"home": "UwU", "away": "Al-Qaeda United", "score": "-"}, {"home": "Deportivo Sa Carogna", "away": "RSA riabilitazione", "score": "-"}]},
    36: {"nome": "36ª Giornata lega", "serie_a": 38, "matches": [{"home": "Luton Down", "away": "BENE EH MANCO MALEN", "score": "-"}, {"home": "CHIVUISMO", "away": "NicoPanz", "score": "-"}, {"home": "Al-Qaeda United", "away": "RSA riabilitazione", "score": "-"}, {"home": "Deportivo Sa Carogna", "away": "UwU", "score": "-"}]}
}

CALENDARIO_LEGA_2 = {
    1: {"nome": "1ª Giornata lega", "serie_a": 3, "matches": [{"home": "CHIVUISMO", "away": "FREE SAPOMODORO FC", "p_home": 75.5, "p_away": 71.0, "score": "2-1"}, {"home": "DEMOCRAZIA CRISTANTE", "away": "IchNusa", "p_home": 86.0, "p_away": 75.5, "score": "4-2"}, {"home": "HINTER X HINTER", "away": "Scrotone", "p_home": 83.0, "p_away": 73.0, "score": "3-2"}, {"home": "COSTIERA ANALFITANA", "away": "FC Pinolandia", "p_home": 74.0, "p_away": 70.0, "score": "2-1"}]},
    2: {"nome": "2ª Giornata lega", "serie_a": 4, "matches": [{"home": "FREE SAPOMODORO FC", "away": "COSTIERA ANALFITANA", "p_home": 72.5, "p_away": 76.5, "score": "2-2"}, {"home": "FC Pinolandia", "away": "HINTER X HINTER", "p_home": 77.0, "p_away": 79.5, "score": "2-3"}, {"home": "Scrotone", "away": "DEMOCRAZIA CRISTANTE", "p_home": 71.0, "p_away": 71.5, "score": "1-1"}, {"home": "IchNusa", "away": "CHIVUISMO", "p_home": 68.0, "p_away": 70.0, "score": "1-1"}]}
}

# Chiave = numero lega (1, 2): non dipende dagli ID chat, quindi non collassa
# se una variabile CHAT_ID_* manca (prima entrambe finivano sulla chiave 0).
LEGHE = {
    1: {
        "num": 1,
        "chat_id": CHAT_ID_LEGA_1,
        "slug": "fanta4reich",
        "competition_id": 206672,
        "nome": "Fanta4Reich",
        "calendario": CALENDARIO_LEGA_1,
        "rose": ROSE_LEGA_1,
        "team_ids": TEAM_IDS_BY_LEGA[1],
        "owners": OWNERS_BY_LEGA[1],
    },
    2: {
        "num": 2,
        "chat_id": CHAT_ID_LEGA_2,
        "slug": "fantacalcio-stalloni-26-27",
        "competition_id": 320101,
        "nome": "Fantacalcio Stalloni",
        "calendario": CALENDARIO_LEGA_2,
        "rose": ROSE_LEGA_2,
        "team_ids": TEAM_IDS_BY_LEGA[2],
        "owners": OWNERS_BY_LEGA[2],
    },
}
CHAT_TO_LEGA = {l["chat_id"]: l for l in LEGHE.values() if l["chat_id"]}

# Stato in memoria dei controlli automatici
STATO = {n: {"snapshot": None, "pending": None, "giornata": 0} for n in LEGHE}

# Preferibile impostarla come variabile d'ambiente (il repo e' pubblico).
FANTA_APP_KEY = os.getenv("FANTA_APP_KEY", "ICiELOObd5DF5uJEATi77CRvHiiRuMU0")
FEED_URL = "https://www.fantacalcio.it/rss/notizie"
GEMINI_MODEL = "gemini-2.5-flash"
INTERVALLO_CONTROLLI = 1200  # secondi
NEWS_NOTIFICATE = set()
NEWS_INIZIALIZZATE = False

OFFICIAL_PLAYERS_MAP = {
    # RSA Riabilitazione
    2170: "De Gea", 6217: "Valle", 4409: "Bisseck", 6042: "Tavares N.", 6664: "Delprato", 7412: "Milla", 6844: "Pulisic", 7556: "Rowe", 6752: "Woltemade", 6229: "Douvikas", 2038: "Esposito Se.", 2815: "Meret", 6867: "Milinkovic-Savic V.", 2155: "Rrahmani", 4463: "Saelemaekers", 5620: "Lucumì", 7599: "Dodò", 4892: "Tourè E.", 5885: "Mora", 5500: "Pinamonti", 7129: "Cutrone",
    # Bene Eh Manco Malen
    133: "Skorupski", 4887: "Bellanova", 2788: "Bremer", 6672: "Idzes", 7469: "Bracaglia", 4220: "Zambo Anguissa", 7472: "Calò", 4870: "Adopo", 4923: "Colombo", 2137: "Barella", 7071: "Zortea", 4236: "Muric", 254: "Dimarco", 554: "Zappacosta", 5844: "Thorstvedt", 6274: "Diouf", 4973: "McKennie", 6967: "Diao", 5637: "Davis K.", 6462: "Scamacca", 5982: "Spence", 
    # UwU
    4964: "Vicario", 5641: "Chalobah T.", 4159: "Pavlovic", 2816: "Akanji", 5022: "Di Lorenzo", 7078: "Mastantuono", 5559: "Alajbegovic", 7436: "Da Cunha", 5694: "Thuram", 5734: "Beto", 4871: "Soulè", 7603: "Grabara", 6531: "Jimenez A.", 7219: "Diego Carlos", 2606: "Comuzzo", 4436: "Orsolini", 7060: "Modric", 4137: "Cambiaghi", 6495: "Pellegrino M.", 6534: "Castro S.", 7023: "Cacciamani", 6675: "Perri", 6572: "Zaniolo",
    # Luton Down
    4312: "Maignan", 6821: "Mangas", 7485: "Scalvini", 5526: "Theate", 7181: "Wesley", 5119: "Vlasic", 2848: "Frattesi", 6884: "Conceicao", 531: "Kean", 2097: "Romero D.", 5951: "Berardi", 2134: "Terracciano", 2521: "Falcone", 6989: "Hainaut", 5675: "Coco", 6642: "Tiago Gabriel", 4911: "Chukwueze", 5878: "Colpani", 5687: "Adzic", 4856: "Douglas Luiz", 6677: "Samardzic", 7523: "Varela G.", 7554: "Kolo Muani",
    # NicoPanz
    6966: "Butez", 4317: "N'Dicka", 2514: "Belghali", 4976: "Kalulu", 4998: "Molina N.", 1850: "De Bruyne", 152: "Zielinski", 6875: "Paz N.", 5436: "Bowie", 6052: "Hojlund", 309: "Dybala", 6344: "Sanchez Ro.", 6482: "Mandas", 6320: "Doekhi", 1852: "Spinazzola", 7220: "Badiashile", 5680: "Taylor K.", 2517: "Sarr P.", 6372: "Konè M.", 7314: "Kessiè", 5995: "Raimondo", 7484: "De Ketelaere", 7347: "Adams A.",
    # Deportivo Sa Carogna
    5841: "Caprile", 5750: "Ostigard", 2296: "Miranda J.", 6869: "Ramon", 5739: "De Winter", 4179: "Gonzalez N.", 2194: "Bernardeschi", 7126: "Baturina", 6904: "Yeboah J.", 6397: "Ramos G.", 6435: "Piccoli", 610: "Gollini", 4360: "Svilar", 4734: "Mancini", 7294: "Valdepenas", 6496: "Bartesaghi", 7529: "Koulierakis", 5800: "Gudmundsson A.", 184: "Mbangula", 6833: "Sucic P.", 7070: "Camarda", 4359: "Lontani", 7561: "Krstovic",
    # Altri (PID da verificare con /squadra)
    5585: "Malen", 2764: "Martinez L.", 4777: "McTominay", 2379: "Rabiot", 6204: "Kristensen T.", 6415: "Atta", 6684: "Volpato", 4896: "Simeone", 2529: "Zaccagni", 5930: "Esposito F.P.", 6112: "Yildiz", 2826: "Pellegrini Lo.", 
}



# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def esc(s):
    return html.escape(str(s), quote=False)


def strip_tags(t):
    return re.sub(r"<[^>]+>", "", t or "")


def to_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def to_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def norm(t):
    """Minuscolo, senza accenti, apostrofi normalizzati (per il matching dei nomi)."""
    t = unicodedata.normalize("NFKD", (t or "").replace("’", "'"))
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def is_played(m):
    return str(m.get("score", "-")).strip().lower() not in ("-", "nan", "", "none")


def ultima_giocata(calendario):
    """Ultima giornata con TUTTI i match giocati (0 se nessuna)."""
    last = 0
    for g in sorted(calendario):
        matches = calendario[g].get("matches", [])
        if matches and all(is_played(m) for m in matches):
            last = g
        else:
            break
    return last


def giornata_attiva(calendario):
    """Prima giornata con almeno un match non ancora giocato."""
    for g in sorted(calendario):
        if any(not is_played(m) for m in calendario[g].get("matches", [])):
            return g
    return max(calendario) if calendario else 1


def split_message(text, limit=3800):
    chunks, cur = [], ""
    for line in text.split("\n"):
        if cur and len(cur) + len(line) + 1 > limit:
            chunks.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur)
    return chunks or [text or "-"]


async def reply_long(message, text, html_mode=True):
    """Invia testi lunghi spezzandoli per riga (mai a meta' di un tag HTML)."""
    for chunk in split_message(text):
        try:
            await message.reply_text(chunk, parse_mode="HTML" if html_mode else None)
        except BadRequest:
            await message.reply_text(strip_tags(chunk))


def is_admin(update: Update):
    u = update.effective_user
    return bool(u and ADMIN_TELEGRAM_ID and u.id == ADMIN_TELEGRAM_ID)


def parse_command_args(update: Update, context: ContextTypes.DEFAULT_TYPE, single_is_lega=True):
    """
    Ritorna (lega, giornata, nome).
    - Gruppo registrato: la lega e' quella del gruppo.
    - Privato con admin: lega 1 di default; "1"/"2" come primo argomento sceglie la lega
      (se e' l'unico argomento conta come lega solo con single_is_lega=True).
    - Il primo argomento numerico rimasto e' la giornata; il resto e' il nome squadra.
    """
    chat = update.effective_chat
    args = list(context.args or [])
    lega = None

    if chat and chat.type in ("group", "supergroup"):
        lega = CHAT_TO_LEGA.get(chat.id)
    elif chat and chat.type == "private" and is_admin(update):
        lega = LEGHE[1]
        if args and args[0] in ("1", "2") and (len(args) > 1 or single_is_lega):
            lega = LEGHE[int(args.pop(0))]

    giornata = None
    for a in args:
        if a.isdigit():
            giornata = int(a)
            args.remove(a)
            break
    return lega, giornata, " ".join(args).strip()


# ---------------------------------------------------------------------------
# API Fantacalcio
# ---------------------------------------------------------------------------
def get_fanta_session():
    session = requests.Session()
    clean_cookie = FANTA_COOKIE.strip().replace("\r", " ").replace("\n", " ")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://leghe.fantacalcio.it/",
        "Origin": "https://leghe.fantacalcio.it",
        "Content-Type": "application/json",
        "app_key": FANTA_APP_KEY,
    }
    if clean_cookie:
        headers["Cookie"] = clean_cookie

    bearer = FANTA_BEARER_TOKEN.strip()
    if bearer:
        if not bearer.lower().startswith("bearer "):
            bearer = f"Bearer {bearer}"
        headers["Authorization"] = bearer

    session.headers.update(headers)
    return session


def fetch_match_lineup(competition_id, round_num, serie_a_round, id_home, id_away):
    if not id_home or not id_away:
        return None
    url = f"https://apileague.fantacalcio.it/gaming/v1/teamLineup/{competition_id}/{round_num}/{serie_a_round}/{id_home}/{id_away}"
    try:
        r = get_fanta_session().get(url, timeout=15)
    except requests.RequestException as e:
        logger.error(f"Errore match lineup: {e}")
        return None
    if r.status_code != 200:
        logger.warning(f"teamLineup HTTP {r.status_code} per {url} (cookie/token scaduti?)")
        return None
    try:
        data = r.json()
    except ValueError:
        logger.error(f"teamLineup non e' JSON: {url}")
        return None
    if isinstance(data, dict) and "home" not in data and isinstance(data.get("data"), dict):
        data = data["data"]
    return data if isinstance(data, dict) else None


def lista_giocatori(team_obj, chiave):
    items = team_obj.get(chiave) if isinstance(team_obj, dict) else None
    return [p for p in (items or []) if isinstance(p, dict)]


def player_name(p):
    """Nome da OFFICIAL_PLAYERS_MAP; se manca prova i campi nome del JSON; poi fallback."""
    pid = to_int(p.get("pid"))
    nome = OFFICIAL_PLAYERS_MAP.get(pid)
    if nome:
        return nome
    for k in ("n", "name", "sn", "surname", "cognome", "nome"):
        v = p.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip().title()
    return f"Giocatore #{pid}"


def fetch_tabellini_analizzati(lega, round_num):
    calendario = lega["calendario"]
    giornata_info = calendario.get(round_num)
    if not giornata_info:
        return f"Giornata {round_num} non presente nel calendario."

    comp_id = lega["competition_id"]
    serie_a_round = giornata_info.get("serie_a", round_num + 2)
    report = f"📊 <b>DETTAGLIO UFFICIALE {esc(giornata_info['nome'].upper())}</b> - {esc(lega['nome'])}\n"

    for m in giornata_info.get("matches", []):
        h_name, a_name = m["home"], m["away"]
        id_h = lega["team_ids"].get(h_name.lower())
        id_a = lega["team_ids"].get(a_name.lower())
        h_owner = lega["owners"].get(h_name.lower(), "")
        a_owner = lega["owners"].get(a_name.lower(), "")
        if not id_h or not id_a:
            logger.warning(f"Squadra senza ID: {h_name} / {a_name}")
            continue

        report += (f"\n⚔️ <b>{esc(h_name)}</b> ({esc(h_owner)}) <b>{m.get('p_home', '')} "
                   f"[{esc(m.get('score', '-'))}] {m.get('p_away', '')}</b> <b>{esc(a_name)}</b> ({esc(a_owner)})\n")

        data = fetch_match_lineup(comp_id, round_num, serie_a_round, id_h, id_a)
        if not data:
            report += "  ⚠️ formazioni non disponibili\n"
            continue

        for team_label, team_obj, t_owner in [(h_name, data.get("home"), h_owner), (a_name, data.get("away"), a_owner)]:
            if not isinstance(team_obj, dict):
                continue

            top, flop, rimpianti = [], [], []
            for p in lista_giocatori(team_obj, "starts"):
                nome, voto, fvoto = player_name(p), to_float(p.get("scr")), to_float(p.get("cscr"))
                if 9.5 <= fvoto < 50:
                    top.append(f"{esc(nome)} ⚽ (FV {fvoto})")
                elif 0 < voto <= 4.5:
                    flop.append(f"{esc(nome)} 💩 (voto {voto})")

            for p in lista_giocatori(team_obj, "bench"):
                nome, voto, fvoto = player_name(p), to_float(p.get("scr")), to_float(p.get("cscr"))
                if 9.5 <= fvoto < 50:
                    rimpianti.append(f"GOL DI {esc(nome.upper())} (FV {fvoto})")
                elif 7.0 <= voto < 50:
                    rimpianti.append(f"{esc(nome)} (voto {voto})")

            if top:
                report += f"  • {esc(team_label)} - Protagonisti: {', '.join(top)}\n"
            if flop:
                report += f"  • {esc(team_label)} - Disastri: {', '.join(flop)}\n"
            if rimpianti:
                report += f"  ⚠️ <b>PANCHINA {esc(t_owner.upper())}:</b> {', '.join(rimpianti)} lasciati fuori!\n"

    return report


def fetch_classifica_rows(slug, competition_id):
    """Righe grezze della classifica, oppure None se la chiamata fallisce."""
    url = (f"https://leghe.fantacalcio.it/servizi/v1_legheCompetizione/classificagiornate"
           f"?alias_lega={slug}&id_competizione={competition_id}&giornata_inizio=1&giornata_fine=38")
    try:
        res = get_fanta_session().get(url, timeout=15)
        if res.status_code != 200:
            logger.warning(f"classifica HTTP {res.status_code} (cookie/token scaduti?)")
            return None
        rows = res.json().get("data", [])
        return rows if isinstance(rows, list) else []
    except (requests.RequestException, ValueError, AttributeError) as e:
        logger.error(f"Errore classifica: {e}")
        return None


def formatta_classifica(rows):
    testo = "🏆 <b>CLASSIFICA ATTUALE</b>\n\n"
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        team_id = to_int(row.get("id"))
        nome = TEAMS_MAP.get(team_id, {}).get("name", f"Squadra {team_id}")
        punti = to_int(row.get("p"))
        fanta_punti = to_float(row.get("s_p"))
        testo += f"<b>{i}.</b> {esc(nome)} — <b>{punti} pt</b> <i>({fanta_punti} fp)</i>\n"
    return testo


def fetch_classifica(slug, competition_id):
    rows = fetch_classifica_rows(slug, competition_id)
    if rows is None:
        return "⚠️ Errore nel recupero della classifica."
    if not rows:
        return "Classifica al momento non disponibile."
    return formatta_classifica(rows)


def get_calendario_testo(calendario, target_round=None):
    if not calendario:
        return "⚠️ Calendario non disponibile."
    if target_round is None:
        target_round = giornata_attiva(calendario)

    giornata = calendario.get(target_round)
    if not giornata:
        return f"⚠️ Giornata {target_round} non trovata nel calendario."

    testo = f"⚽ <b>{esc(giornata['nome'].upper())}</b>\n<i>({giornata['serie_a']}ª Giornata Serie A)</i>\n\n"
    for m in giornata["matches"]:
        if is_played(m):
            testo += (f"• <b>{esc(m['home'])}</b> {m.get('p_home', '')} <b>[{esc(m['score'])}]</b> "
                      f"{m.get('p_away', '')} <b>{esc(m['away'])}</b>\n\n")
        else:
            testo += f"• <b>{esc(m['home'])}</b> 🆚 <b>{esc(m['away'])}</b>\n"
    return testo


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
def genera_testo_ai(prompt):
    if not client:
        return None
    try:
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        testo = (resp.text or "").strip()
        return testo or None
    except Exception as e:
        logger.error(f"Errore Gemini: {e}")
        return None


def genera_recap_ai(classifica_testo, dati_tabellino, nome_lega):
    prompt = (
        f"Sei il cronista piu' caustico, sarcastico e spietato del Fantacalcio. Scrivi in italiano il recap "
        f"dell'ultima giornata della lega \"{nome_lega}\", con tono feroce ma goliardico tra amici "
        f"(niente insulti pesanti, discriminazioni o volgarita' gratuite).\n"
        f"Usa SOLO i dati qui sotto: non inventare risultati, giocatori o punteggi. "
        f"Infierisci sui rimpianti in panchina, sui disastri dei titolari e commenta la classifica.\n"
        f"Massimo 1800 caratteri, testo semplice senza markdown ne' HTML, qualche emoji.\n\n"
        f"CLASSIFICA:\n{strip_tags(classifica_testo)}\n\nTABELLINI:\n{strip_tags(dati_tabellino)}"
    )
    recap = genera_testo_ai(prompt)
    if recap:
        return recap
    return "⚠️ Gemini non disponibile, ecco i dati grezzi.\n\n" + strip_tags(dati_tabellino)


# ---------------------------------------------------------------------------
# Comandi
# ---------------------------------------------------------------------------
async def cmd_classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lega, _, _ = parse_command_args(update, context)
    if not lega:
        return
    msg = await asyncio.to_thread(fetch_classifica, lega["slug"], lega["competition_id"])
    await reply_long(update.message, f"<b>{esc(lega['nome'])}</b>\n{msg}")


async def cmd_calendario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lega, giornata, _ = parse_command_args(update, context)
    if not lega:
        return
    await reply_long(update.message, get_calendario_testo(lega["calendario"], giornata))


async def cmd_rosa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lega, _, cercata = parse_command_args(update, context)
    if not lega:
        return

    rose = lega["rose"]
    cercata = cercata.lower()
    if not cercata:
        elenco = "\n".join(f"• <b>{esc(t)}</b> <i>({esc(lega['owners'].get(t.lower(), ''))})</i>" for t in rose)
        await update.message.reply_text(f"Specifica una squadra:\n\n{elenco}", parse_mode="HTML")
        return

    for t_name, players in rose.items():
        if cercata in t_name.lower():
            owner = lega["owners"].get(t_name.lower(), "")
            testo = f"🛡 <b>ROSA {esc(t_name.upper())}</b> <i>({esc(owner)})</i>\n\n"
            testo += "\n".join(f"{i}. {esc(p)}" for i, p in enumerate(players, 1))
            await update.message.reply_text(testo, parse_mode="HTML")
            return

    await update.message.reply_text("Squadra non trovata.")


# /dettaglio [lega] [giornata]  (es. /dettaglio 3  oppure /dettaglio 2 3)
async def cmd_dettaglio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    lega, giornata, _ = parse_command_args(update, context, single_is_lega=False)
    lega = lega or LEGHE[1]
    cal = lega["calendario"]
    giornata = giornata or ultima_giocata(cal) or giornata_attiva(cal)
    if giornata not in cal:
        await update.message.reply_text(f"Giornata {giornata} non presente nel calendario di {lega['nome']}.")
        return

    await update.message.reply_text(
        f"🔍 Scarico tabellini ufficiali per <b>{esc(lega['nome'])}</b> (Giornata {giornata})...", parse_mode="HTML")
    res = await asyncio.to_thread(fetch_tabellini_analizzati, lega, giornata)
    await reply_long(update.message, res)


# /squadra [lega] [giornata] NomeSquadra  (es. /squadra CHIVUISMO  oppure /squadra 2 2 CHIVUISMO)
async def cmd_squadra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    lega, giornata, cercata = parse_command_args(update, context, single_is_lega=False)
    lega = lega or LEGHE[1]
    cal = lega["calendario"]
    giornata = giornata or giornata_attiva(cal)
    info = cal.get(giornata)
    if not info:
        await update.message.reply_text(f"Giornata {giornata} non presente nel calendario di {lega['nome']}.")
        return

    matches = info.get("matches", [])
    cercata = cercata.lower()
    if not cercata:
        elenco = "\n".join(f"• <b>{esc(m['home'])}</b> vs <b>{esc(m['away'])}</b>" for m in matches)
        await update.message.reply_text(
            f"⚠️ <b>Specifica la squadra!</b> Esempio: <code>/squadra CHIVUISMO</code>\n\n"
            f"{esc(lega['nome'])} - giornata {giornata}:\n{elenco}", parse_mode="HTML")
        return

    match, is_home = None, True
    for m in matches:
        if cercata in m["home"].lower():
            match, is_home = m, True
            break
        if cercata in m["away"].lower():
            match, is_home = m, False
            break
    if not match:
        await update.message.reply_text(f"Squadra non trovata nella giornata {giornata} di {lega['nome']}.")
        return

    id_h = lega["team_ids"].get(match["home"].lower())
    id_a = lega["team_ids"].get(match["away"].lower())
    data = await asyncio.to_thread(
        fetch_match_lineup, lega["competition_id"], giornata, info.get("serie_a", giornata + 2), id_h, id_a)
    if not data:
        await update.message.reply_text("Errore nel recupero della formazione dal server (cookie/token scaduti?).")
        return

    label = match["home"] if is_home else match["away"]
    team_obj = data.get("home") if is_home else data.get("away")
    if not isinstance(team_obj, dict):
        await update.message.reply_text("Formazione non disponibile per questa squadra.")
        return

    non_mappati = []

    def riga(p):
        pid = to_int(p.get("pid"))
        nome = player_name(p)
        if pid not in OFFICIAL_PLAYERS_MAP:
            non_mappati.append(pid)
        return f"• <code>PID {pid}</code> ➔ {esc(nome)} (Voto: {p.get('scr', 0)}, FV: {p.get('cscr', 0)})\n"

    testo = f"🛡 <b>ROSA SCHIERATA: {esc(label.upper())}</b> (giornata {giornata})\n\n<b>TITOLARI:</b>\n"
    testo += "".join(riga(p) for p in lista_giocatori(team_obj, "starts"))
    testo += "\n<b>PANCHINA:</b>\n"
    testo += "".join(riga(p) for p in lista_giocatori(team_obj, "bench"))

    if non_mappati:
        mappati = {norm(n) for n in OFFICIAL_PLAYERS_MAP.values()}
        rosa = next((pl for t, pl in lega["rose"].items() if t.lower() == label.lower()), [])
        senza_pid = [n for n in rosa if norm(n) not in mappati]
        testo += f"\n❓ <b>PID non mappati:</b> {', '.join(str(p) for p in dict.fromkeys(non_mappati))}\n"
        if senza_pid:
            testo += f"👤 In rosa senza PID noto: {esc(', '.join(senza_pid))}\n"
        testo += "<i>Abbinali e aggiungili a OFFICIAL_PLAYERS_MAP.</i>\n"

    await reply_long(update.message, testo)


async def cmd_test_recap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or not is_admin(update):
        return

    lega, giornata, _ = parse_command_args(update, context, single_is_lega=True)
    lega = lega or LEGHE[1]
    cal = lega["calendario"]
    giornata = giornata or ultima_giocata(cal) or giornata_attiva(cal)

    await update.message.reply_text(
        f"⏳ Generazione recap per <b>{esc(lega['nome'])}</b> (giornata {giornata})...", parse_mode="HTML")
    classifica_testo = await asyncio.to_thread(fetch_classifica, lega["slug"], lega["competition_id"])
    dati_tabellino = await asyncio.to_thread(fetch_tabellini_analizzati, lega, giornata)
    recap = await asyncio.to_thread(genera_recap_ai, classifica_testo, dati_tabellino, lega["nome"])
    await reply_long(update.message, recap, html_mode=False)


# ---------------------------------------------------------------------------
# Controlli automatici
# ---------------------------------------------------------------------------
INFORTUNIO_RE = re.compile(
    r"infortun|lesion|\bstop\b|indisponibil|distorsion|contrattur|elongazion|stirament|frattur|"
    r"operazion|\bk\.?o\.?\b|affaticament|problema (muscolare|fisico)|forfait", re.I)


def _chiave_cognome(nome_rosa):
    # "Miranda J." / "Esposito Se." / "Ederson D.S." -> cognome senza iniziali
    return norm(re.sub(r"\s+\S+\.$", "", nome_rosa).strip())


def costruisci_indice_giocatori():
    """cognome normalizzato -> [(nome in rosa, squadra, numero lega)]"""
    indice = {}
    for num, lega in LEGHE.items():
        for squadra, giocatori in lega["rose"].items():
            for g in giocatori:
                indice.setdefault(_chiave_cognome(g), []).append((g, squadra, num))
    return indice


INDICE_GIOCATORI = costruisci_indice_giocatori()
INDICE_RE = re.compile(r"(?<!\w)(" + "|".join(re.escape(k) for k in sorted(INDICE_GIOCATORI, key=len, reverse=True)) + r")(?!\w)")


def valida_mappa_giocatori():
    per_nome = {}
    for pid, nome in OFFICIAL_PLAYERS_MAP.items():
        per_nome.setdefault(nome, []).append(pid)
    for nome, pids in per_nome.items():
        if len(pids) > 1:
            logger.warning(f"OFFICIAL_PLAYERS_MAP: '{nome}' ha piu' PID {pids}: verificane uno")
    mappati = {norm(n) for n in OFFICIAL_PLAYERS_MAP.values()}
    for num, lega in LEGHE.items():
        mancanti = sorted({g for pl in lega["rose"].values() for g in pl if norm(g) not in mappati})
        logger.info(f"Lega {num}: {len(mancanti)} giocatori di rosa senza PID mappato")


async def check_infortuni_e_news(app):
    global NEWS_INIZIALIZZATE
    feed = await asyncio.to_thread(feedparser.parse, FEED_URL)
    entries = list(feed.entries[:15])

    # Al primo giro memorizza solo: niente raffica di alert a ogni riavvio.
    if not NEWS_INIZIALIZZATE:
        NEWS_NOTIFICATE.update(e.get("id") or e.get("link") for e in entries)
        NEWS_INIZIALIZZATE = True
        return

    for entry in entries:
        entry_id = entry.get("id") or entry.get("link")
        if not entry_id or entry_id in NEWS_NOTIFICATE:
            continue
        NEWS_NOTIFICATE.add(entry_id)

        titolo = entry.get("title", "")
        sommario = strip_tags(entry.get("summary", ""))
        testo = f"{titolo}. {sommario}"
        if not INFORTUNIO_RE.search(testo):
            continue

        per_lega = {}
        for cognome in dict.fromkeys(INDICE_RE.findall(norm(testo))):
            for nome, squadra, num in INDICE_GIOCATORI[cognome]:
                owner = LEGHE[num]["owners"].get(squadra.lower(), "")
                per_lega.setdefault(num, []).append(f"{nome} ({squadra}, {owner})")

        for num, coinvolti in per_lega.items():
            chat_id = LEGHE[num]["chat_id"]
            if not chat_id:
                continue
            prompt = (
                "Sei un cronista di Fantacalcio caustico e sarcastico. Scrivi in italiano un avviso di 2-3 righe, "
                "ironico ma senza insulti pesanti, su questa notizia di infortunio, prendendo in giro i proprietari "
                "coinvolti. Non inventare nulla oltre ai dati. Testo semplice, niente markdown/HTML.\n\n"
                f"Notizia: {titolo}\nDettagli: {sommario[:600]}\nGiocatori coinvolti: {'; '.join(coinvolti)}"
            )
            ai = await asyncio.to_thread(genera_testo_ai, prompt)
            msg = ai or f"🚑 {titolo}\nCoinvolti: {'; '.join(coinvolti)}"
            link = entry.get("link", "")
            try:
                await app.bot.send_message(chat_id, f"🚑 {msg}\n\n{link}".strip())
            except Exception as e:
                logger.error(f"Invio alert infortunio fallito (lega {num}): {e}")


async def check_fine_giornata(app):
    """
    Rileva la chiusura di una giornata dal cambiamento della classifica (stabile su due
    controlli consecutivi) e invia il recap nella chat della lega.
    La giornata recappata e' (ultima giornata nota) + 1: va tenuto allineato il calendario.
    """
    for num, lega in LEGHE.items():
        stato = STATO[num]
        rows = await asyncio.to_thread(fetch_classifica_rows, lega["slug"], lega["competition_id"])
        if not rows:
            continue

        firma = sorted((str(r.get("id")), r.get("p"), r.get("s_p")) for r in rows if isinstance(r, dict))
        snap = hashlib.md5(json.dumps(firma, default=str).encode()).hexdigest()

        if stato["snapshot"] is None:
            stato["snapshot"] = snap
            stato["giornata"] = ultima_giocata(lega["calendario"])
            continue
        if snap == stato["snapshot"]:
            stato["pending"] = None
            continue
        if stato["pending"] != snap:
            stato["pending"] = snap  # aspetta conferma al prossimo controllo
            continue

        stato["snapshot"], stato["pending"] = snap, None
        giornata = stato["giornata"] + 1
        if giornata not in lega["calendario"]:
            logger.warning(f"Lega {num}: classifica cambiata ma giornata {giornata} non in calendario")
            continue
        stato["giornata"] = giornata

        if not lega["chat_id"]:
            logger.warning(f"Lega {num}: CHAT_ID mancante, recap giornata {giornata} non inviato")
            continue

        logger.info(f"Lega {num}: recap automatico giornata {giornata}")
        classifica_testo = formatta_classifica(rows)
        dati = await asyncio.to_thread(fetch_tabellini_analizzati, lega, giornata)
        recap = await asyncio.to_thread(genera_recap_ai, classifica_testo, dati, lega["nome"])
        try:
            for chunk in split_message(recap):
                await app.bot.send_message(lega["chat_id"], chunk)
        except Exception as e:
            logger.error(f"Invio recap fallito (lega {num}): {e}")


async def background_checker(app):
    await asyncio.sleep(15)
    while True:
        for nome, fn in (("news", check_infortuni_e_news), ("fine giornata", check_fine_giornata)):
            try:
                await fn(app)
            except Exception as e:
                logger.error(f"Errore background ({nome}): {e}")
        await asyncio.sleep(INTERVALLO_CONTROLLI)


async def post_init(app):
    valida_mappa_giocatori()
    app.bot_data["bg_task"] = asyncio.create_task(background_checker(app))


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Errore non gestito", exc_info=context.error)


def main():
    if not TG_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN mancante!")
        return

    app = ApplicationBuilder().token(TG_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("classifica", cmd_classifica))
    app.add_handler(CommandHandler(["calendario", "incontri"], cmd_calendario))
    app.add_handler(CommandHandler("rosa", cmd_rosa))
    app.add_handler(CommandHandler("test_recap", cmd_test_recap))
    app.add_handler(CommandHandler("dettaglio", cmd_dettaglio))
    app.add_handler(CommandHandler("squadra", cmd_squadra))
    app.add_error_handler(on_error)

    logger.info("Bot Fantacalcio operativo.")
    app.run_polling()


if __name__ == "__main__":
    main()
