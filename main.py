import os
import asyncio
import json
import logging
import requests
import feedparser
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from google import genai

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

FANTA_EMAIL = os.getenv("FANTA_EMAIL")
FANTA_PASSWORD = os.getenv("FANTA_PASSWORD")
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
    18831834: {"name": "UwU", "owner": "gibo"},
    18883778: {"name": "NicoPanz", "owner": "Ciccio"},
    18833116: {"name": "Al-Qaeda United", "owner": "spoleto17"},
    18832547: {"name": "CHIVUISMO", "owner": "Gabbo"},
    18831242: {"name": "Deportivo Sa Carogna", "owner": "Giaime"},
    18832350: {"name": "Luton Down", "owner": "Manuel"},
    18883572: {"name": "BENE EH MANCO MALEN", "owner": "Lamine Kialunga"},
    18885993: {"name": "RSA riabilitazione", "owner": "El vecho"},
    # Lega 2: Fantacalcio Stalloni
    19197193: {"name": "HINTER X HINTER", "owner": "gibo"},
    19196752: {"name": "DEMOCRAZIA CRISTANTE", "owner": "Cryan Bristante"},
    19213432: {"name": "COSTIERA ANALFITANA", "owner": "Manuel"},
    19196408: {"name": "CHIVUISMO", "owner": "Gabbo"},
    19197005: {"name": "Scrotone", "owner": "loffredo03"},
    19209834: {"name": "FREE SAPOMODORO FC", "owner": "Marco Priolo Pinolo"},
    19176402: {"name": "IchNusa", "owner": "Giaime"},
    19197286: {"name": "FC Pinolandia", "owner": "Ernesto Tavaroni"}
}

NAME_TO_ID = {v["name"].strip().lower(): k for k, v in TEAMS_MAP.items()}
OWNER_LOOKUP = {v["name"].strip().lower(): v["owner"] for v in TEAMS_MAP.values()}

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
    3: {"nome": "3ª Giornata lega", "serie_a": 5, "matches": [{"home": "Deportivo Sa Carogna", "away": "NicoPanz", "score": "-"}, {"home": "BENE EH MANCO MALEN", "away": "RSA riabilitazione", "score": "-"}, {"home": "CHIVUISMO", "away": "Al-Qaeda United", "score": "-"}, {"home": "UwU", "away": "Luton Down", "score": "-"}]},
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
    2: {"nome": "2ª Giornata lega", "serie_a": 4, "matches": [{"home": "FREE SAPOMODORO FC", "away": "COSTIERA ANALFITANA", "p_home": 72.5, "p_away": 76.5, "score": "2-2"}, {"home": "FC Pinolandia", "away": "HINTER X HINTER", "p_home": 77.0, "p_away": 79.5, "score": "2-3"}, {"home": "Scrotone", "away": "DEMOCRAZIA CRISTANTE", "p_home": 71.0, "p_away": 71.5, "score": "1-1"}, {"home": "IchNusa", "away": "CHIVUISMO", "p_home": 68.0, "p_away": 70.0, "score": "1-1"}]},
    3: {"nome": "3ª Giornata lega", "serie_a": 5, "matches": [{"home": "DEMOCRAZIA CRISTANTE", "away": "FC Pinolandia", "score": "-"}, {"home": "HINTER X HINTER", "away": "FREE SAPOMODORO FC", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "CHIVUISMO", "score": "-"}, {"home": "Scrotone", "away": "IchNusa", "score": "-"}]},
    4: {"nome": "4ª Giornata lega", "serie_a": 6, "matches": [{"home": "CHIVUISMO", "away": "HINTER X HINTER", "score": "-"}, {"home": "FREE SAPOMODORO FC", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}, {"home": "FC Pinolandia", "away": "Scrotone", "score": "-"}, {"home": "IchNusa", "away": "COSTIERA ANALFITANA", "score": "-"}]},
    5: {"nome": "5ª Giornata lega", "serie_a": 7, "matches": [{"home": "DEMOCRAZIA CRISTANTE", "away": "CHIVUISMO", "score": "-"}, {"home": "HINTER X HINTER", "away": "COSTIERA ANALFITANA", "score": "-"}, {"home": "FC Pinolandia", "away": "IchNusa", "score": "-"}, {"home": "Scrotone", "away": "FREE SAPOMODORO FC", "score": "-"}]},
    6: {"nome": "6ª Giornata lega", "serie_a": 8, "matches": [{"home": "CHIVUISMO", "away": "Scrotone", "score": "-"}, {"home": "FREE SAPOMODORO FC", "away": "FC Pinolandia", "score": "-"}, {"home": "HINTER X HINTER", "away": "IchNusa", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}]},
    7: {"nome": "7ª Giornata lega", "serie_a": 9, "matches": [{"home": "DEMOCRAZIA CRISTANTE", "away": "HINTER X HINTER", "score": "-"}, {"home": "FC Pinolandia", "away": "CHIVUISMO", "score": "-"}, {"home": "Scrotone", "away": "COSTIERA ANALFITANA", "score": "-"}, {"home": "IchNusa", "away": "FREE SAPOMODORO FC", "score": "-"}]},
    8: {"nome": "8ª Giornata lega", "serie_a": 10, "matches": [{"home": "CHIVUISMO", "away": "COSTIERA ANALFITANA", "score": "-"}, {"home": "FREE SAPOMODORO FC", "away": "HINTER X HINTER", "score": "-"}, {"home": "Scrotone", "away": "FC Pinolandia", "score": "-"}, {"home": "IchNusa", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}]},
    9: {"nome": "9ª Giornata lega", "serie_a": 11, "matches": [{"home": "DEMOCRAZIA CRISTANTE", "away": "Scrotone", "score": "-"}, {"home": "HINTER X HINTER", "away": "CHIVUISMO", "score": "-"}, {"home": "FC Pinolandia", "away": "FREE SAPOMODORO FC", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "IchNusa", "score": "-"}]},
    10: {"nome": "10ª Giornata lega", "serie_a": 12, "matches": [{"home": "CHIVUISMO", "away": "FC Pinolandia", "score": "-"}, {"home": "FREE SAPOMODORO FC", "away": "Scrotone", "score": "-"}, {"home": "DEMOCRAZIA CRISTANTE", "away": "COSTIERA ANALFITANA", "score": "-"}, {"home": "IchNusa", "away": "HINTER X HINTER", "score": "-"}]},
    11: {"nome": "11ª Giornata lega", "serie_a": 13, "matches": [{"home": "Scrotone", "away": "CHIVUISMO", "score": "-"}, {"home": "FC Pinolandia", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}, {"home": "FREE SAPOMODORO FC", "away": "IchNusa", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "HINTER X HINTER", "score": "-"}]},
    12: {"nome": "12ª Giornata lega", "serie_a": 14, "matches": [{"home": "CHIVUISMO", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "FREE SAPOMODORO FC", "score": "-"}, {"home": "HINTER X HINTER", "away": "FC Pinolandia", "score": "-"}, {"home": "IchNusa", "away": "Scrotone", "score": "-"}]},
    13: {"nome": "13ª Giornata lega", "serie_a": 15, "matches": [{"home": "CHIVUISMO", "away": "IchNusa", "score": "-"}, {"home": "DEMOCRAZIA CRISTANTE", "away": "FREE SAPOMODORO FC", "score": "-"}, {"home": "FC Pinolandia", "away": "COSTIERA ANALFITANA", "score": "-"}, {"home": "Scrotone", "away": "HINTER X HINTER", "score": "-"}]},
    14: {"nome": "14ª Giornata lega", "serie_a": 16, "matches": [{"home": "FREE SAPOMODORO FC", "away": "CHIVUISMO", "score": "-"}, {"home": "HINTER X HINTER", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "Scrotone", "score": "-"}, {"home": "IchNusa", "away": "FC Pinolandia", "score": "-"}]},
    15: {"nome": "15ª Giornata lega", "serie_a": 17, "matches": [{"home": "Scrotone", "away": "FREE SAPOMODORO FC", "score": "-"}, {"home": "CHIVUISMO", "away": "COSTIERA ANALFITANA", "score": "-"}, {"home": "FC Pinolandia", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}, {"home": "IchNusa", "away": "HINTER X HINTER", "score": "-"}]},
    16: {"nome": "16ª Giornata lega", "serie_a": 18, "matches": [{"home": "FREE SAPOMODORO FC", "away": "IchNusa", "score": "-"}, {"home": "HINTER X HINTER", "away": "FC Pinolandia", "score": "-"}, {"home": "DEMOCRAZIA CRISTANTE", "away": "CHIVUISMO", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "Scrotone", "score": "-"}]},
    17: {"nome": "17ª Giornata lega", "serie_a": 19, "matches": [{"home": "CHIVUISMO", "away": "HINTER X HINTER", "score": "-"}, {"home": "FC Pinolandia", "away": "FREE SAPOMODORO FC", "score": "-"}, {"home": "IchNusa", "away": "Scrotone", "score": "-"}, {"home": "DEMOCRAZIA CRISTANTE", "away": "COSTIERA ANALFITANA", "score": "-"}]},
    18: {"nome": "18ª Giornata lega", "serie_a": 20, "matches": [{"home": "Scrotone", "away": "FC Pinolandia", "score": "-"}, {"home": "FREE SAPOMODORO FC", "away": "CHIVUISMO", "score": "-"}, {"home": "HINTER X HINTER", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "IchNusa", "score": "-"}]},
    19: {"nome": "19ª Giornata lega", "serie_a": 21, "matches": [{"home": "CHIVUISMO", "away": "Scrotone", "score": "-"}, {"home": "FC Pinolandia", "away": "IchNusa", "score": "-"}, {"home": "HINTER X HINTER", "away": "COSTIERA ANALFITANA", "score": "-"}, {"home": "DEMOCRAZIA CRISTANTE", "away": "FREE SAPOMODORO FC", "score": "-"}]},
    20: {"nome": "20ª Giornata lega", "serie_a": 22, "matches": [{"home": "Scrotone", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}, {"home": "FREE SAPOMODORO FC", "away": "HINTER X HINTER", "score": "-"}, {"home": "FC Pinolandia", "away": "COSTIERA ANALFITANA", "score": "-"}, {"home": "IchNusa", "away": "CHIVUISMO", "score": "-"}]},
    21: {"nome": "21ª Giornata lega", "serie_a": 23, "matches": [{"home": "CHIVUISMO", "away": "FC Pinolandia", "score": "-"}, {"home": "HINTER X HINTER", "away": "Scrotone", "score": "-"}, {"home": "DEMOCRAZIA CRISTANTE", "away": "IchNusa", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "FREE SAPOMODORO FC", "score": "-"}]},
    22: {"nome": "22ª Giornata lega", "serie_a": 24, "matches": [{"home": "Scrotone", "away": "IchNusa", "score": "-"}, {"home": "FREE SAPOMODORO FC", "away": "FC Pinolandia", "score": "-"}, {"home": "DEMOCRAZIA CRISTANTE", "away": "HINTER X HINTER", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "CHIVUISMO", "score": "-"}]},
    23: {"nome": "23ª Giornata lega", "serie_a": 25, "matches": [{"home": "CHIVUISMO", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}, {"home": "FC Pinolandia", "away": "Scrotone", "score": "-"}, {"home": "HINTER X HINTER", "away": "FREE SAPOMODORO FC", "score": "-"}, {"home": "IchNusa", "away": "COSTIERA ANALFITANA", "score": "-"}]},
    24: {"nome": "24ª Giornata lega", "serie_a": 26, "matches": [{"home": "Scrotone", "away": "HINTER X HINTER", "score": "-"}, {"home": "FREE SAPOMODORO FC", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}, {"home": "CHIVUISMO", "away": "IchNusa", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "FC Pinolandia", "score": "-"}]},
    25: {"nome": "25ª Giornata lega", "serie_a": 27, "matches": [{"home": "DEMOCRAZIA CRISTANTE", "away": "Scrotone", "score": "-"}, {"home": "HINTER X HINTER", "away": "CHIVUISMO", "score": "-"}, {"home": "FC Pinolandia", "away": "FREE SAPOMODORO FC", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "IchNusa", "score": "-"}]},
    26: {"nome": "26ª Giornata lega", "serie_a": 28, "matches": [{"home": "Scrotone", "away": "CHIVUISMO", "score": "-"}, {"home": "IchNusa", "away": "FREE SAPOMODORO FC", "score": "-"}, {"home": "FC Pinolandia", "away": "HINTER X HINTER", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}]},
    27: {"nome": "27ª Giornata lega", "serie_a": 29, "matches": [{"home": "Scrotone", "away": "COSTIERA ANALFITANA", "score": "-"}, {"home": "CHIVUISMO", "away": "FREE SAPOMODORO FC", "score": "-"}, {"home": "HINTER X HINTER", "away": "IchNusa", "score": "-"}, {"home": "DEMOCRAZIA CRISTANTE", "away": "FC Pinolandia", "score": "-"}]},
    28: {"nome": "28ª Giornata lega", "serie_a": 30, "matches": [{"home": "FREE SAPOMODORO FC", "away": "Scrotone", "score": "-"}, {"home": "FC Pinolandia", "away": "CHIVUISMO", "score": "-"}, {"home": "IchNusa", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "HINTER X HINTER", "score": "-"}]},
    29: {"nome": "29ª Giornata lega", "serie_a": 31, "matches": [{"home": "FC Pinolandia", "away": "IchNusa", "score": "-"}, {"home": "FREE SAPOMODORO FC", "away": "COSTIERA ANALFITANA", "score": "-"}, {"home": "Scrotone", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}, {"home": "HINTER X HINTER", "away": "CHIVUISMO", "score": "-"}]},
    30: {"nome": "30ª Giornata lega", "serie_a": 32, "matches": [{"home": "IchNusa", "away": "HINTER X HINTER", "score": "-"}, {"home": "CHIVUISMO", "away": "Scrotone", "score": "-"}, {"home": "DEMOCRAZIA CRISTANTE", "away": "FREE SAPOMODORO FC", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "FC Pinolandia", "score": "-"}]},
    31: {"nome": "31ª Giornata lega", "serie_a": 33, "matches": [{"home": "FREE SAPOMODORO FC", "away": "CHIVUISMO", "score": "-"}, {"home": "Scrotone", "away": "IchNusa", "score": "-"}, {"home": "HINTER X HINTER", "away": "FC Pinolandia", "score": "-"}, {"home": "DEMOCRAZIA CRISTANTE", "away": "COSTIERA ANALFITANA", "score": "-"}]},
    32: {"nome": "32ª Giornata lega", "serie_a": 34, "matches": [{"home": "FC Pinolandia", "away": "Scrotone", "score": "-"}, {"home": "IchNusa", "away": "FREE SAPOMODORO FC", "score": "-"}, {"home": "CHIVUISMO", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "HINTER X HINTER", "score": "-"}]},
    33: {"nome": "33ª Giornata lega", "serie_a": 35, "matches": [{"home": "FREE SAPOMODORO FC", "away": "FC Pinolandia", "score": "-"}, {"home": "Scrotone", "away": "HINTER X HINTER", "score": "-"}, {"home": "CHIVUISMO", "away": "COSTIERA ANALFITANA", "score": "-"}, {"home": "DEMOCRAZIA CRISTANTE", "away": "IchNusa", "score": "-"}]},
    34: {"nome": "34ª Giornata lega", "serie_a": 36, "matches": [{"home": "FC Pinolandia", "away": "DEMOCRAZIA CRISTANTE", "score": "-"}, {"home": "IchNusa", "away": "CHIVUISMO", "score": "-"}, {"home": "Scrotone", "away": "COSTIERA ANALFITANA", "score": "-"}, {"home": "HINTER X HINTER", "away": "FREE SAPOMODORO FC", "score": "-"}]},
    35: {"nome": "35ª Giornata lega", "serie_a": 37, "matches": [{"home": "FREE SAPOMODORO FC", "away": "Scrotone", "score": "-"}, {"home": "CHIVUISMO", "away": "FC Pinolandia", "score": "-"}, {"home": "DEMOCRAZIA CRISTANTE", "away": "HINTER X HINTER", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "IchNusa", "score": "-"}]},
    36: {"nome": "36ª Giornata lega", "serie_a": 38, "matches": [{"home": "FC Pinolandia", "away": "HINTER X HINTER", "score": "-"}, {"home": "IchNusa", "away": "Scrotone", "score": "-"}, {"home": "DEMOCRAZIA CRISTANTE", "away": "CHIVUISMO", "score": "-"}, {"home": "COSTIERA ANALFITANA", "away": "FREE SAPOMODORO FC", "score": "-"}]}
}

LEGHE = {
    CHAT_ID_LEGA_1: {
        "slug": "fanta4reich",
        "competition_id": 206672,
        "nome": "Fanta4Reich",
        "calendario": CALENDARIO_LEGA_1,
        "rose": ROSE_LEGA_1,
        "ultima_giornata": 0
    },
    CHAT_ID_LEGA_2: {
        "slug": "fantacalcio-stalloni-26-27",
        "competition_id": 320101,
        "nome": "Fantacalcio Stalloni",
        "calendario": CALENDARIO_LEGA_2,
        "rose": ROSE_LEGA_2,
        "ultima_giornata": 0
    }
}

LOGIN_URL = "https://apileague.fantacalcio.it/onboarding/v1/login"
FANTA_APP_KEY = "ICiELOObd5DF5uJEATi77CRvHiiRuMU0"
NEWS_NOTIFICATE = set()

OFFICIAL_PLAYERS_MAP = {
    5585: "Malen", 2764: "Martinez L.", 6052: "Hojlund", 4871: "Thuram", 6875: "Paz N.", 254: "Dimarco", 2194: "Calhanoglu", 6397: "Ramos G.", 7017: "Douvikas", 2097: "Kean", 7126: "Baturina", 4777: "McTominay", 2167: "Orsolini", 2423: "Pulisic", 2379: "Rabiot", 6752: "Woltemade", 5951: "Kolo Muani", 2848: "Frattesi", 5637: "Davis K.", 309: "Dybala", 2529: "Zaccagni", 7175: "Adzic", 2223: "Zielinski", 5373: "De Ketelaere", 5930: "Esposito F.P.", 6112: "Yildiz", 2826: "Pellegrini Lo.", 2419: "Saelemaekers", 5352: "Pinamonti", 4786: "Vlasic", 7078: "Akanji", 5334: "Samardzic", 2072: "Berardi", 4933: "Colpani", 7071: "Zortea", 5670: "Idzes", 6821: "Terracciano", 6204: "Kristensen T.", 7485: "Obert", 6869: "Mancini", 7023: "Beto", 6372: "Konè M.", 7484: "Sarr P.", 7347: "Adams A.", 1870: "Thorstvedt", 6462: "Scamacca", 2137: "Barella", 6989: "Samardzic", 6677: "Kean", 7554: "Varela G.", 6415: "Atta", 6684: "Volpato", 4896: "Simeone", 4463: "Saelemaekers", 5500: "Pinamonti"
}


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
    session = get_fanta_session()
    if not session:
        return None

    url = f"https://apileague.fantacalcio.it/gaming/v1/teamLineup/{competition_id}/{round_num}/{serie_a_round}/{id_home}/{id_away}"
    try:
        r = session.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.error(f"Errore match lineup: {e}")
    return None


def fetch_tabellini_analizzati(lega, round_num):
    comp_id = lega["competition_id"]
    calendario = lega["calendario"]
    giornata_info = calendario.get(round_num)
    if not giornata_info:
        return "Giornata non presente nel calendario."

    serie_a_round = giornata_info.get("serie_a", round_num + 2)
    matches = giornata_info.get("matches", [])

    report = f"📊 <b>DETTAGLIO UFFICIALE {giornata_info['nome'].upper()} (MODALITÀ DEBUG PID)</b>\n"

    for m in matches:
        h_name = m["home"]
        a_name = m["away"]
        id_h = NAME_TO_ID.get(h_name.lower())
        id_a = NAME_TO_ID.get(a_name.lower())
        h_owner = OWNER_LOOKUP.get(h_name.lower(), "")
        a_owner = OWNER_LOOKUP.get(a_name.lower(), "")

        if not id_h or not id_a:
            continue

        data = fetch_match_lineup(comp_id, round_num, serie_a_round, id_h, id_a)
        score_text = m.get("score", "-")
        p_h = m.get("p_home", "")
        p_a = m.get("p_away", "")

        report += f"\n⚔️ <b>{h_name}</b> ({h_owner}) <b>{p_h} [{score_text}] {p_a}</b> <b>{a_name}</b> ({a_owner})\n"

        if not data:
            continue

        home_obj = data.get("home", {})
        away_obj = data.get("away", {})

        for team_label, team_obj, t_owner in [(h_name, home_obj, h_owner), (a_name, away_obj, a_owner)]:
            if not isinstance(team_obj, dict):
                continue

            starts = team_obj.get("starts", [])
            bench = team_obj.get("bench", [])

            titolari_top = []
            titolari_flop = []
            panchina_rimpianti = []

            for p in starts:
                pid = int(p.get("pid", 0))
                p_name = OFFICIAL_PLAYERS_MAP.get(pid, f"Sconosciuto")
                display_name = f"{p_name} [PID:{pid}]"
                voto = float(p.get("scr", 0))
                fvoto = float(p.get("cscr", 0))

                if fvoto >= 9.5 and fvoto < 50:
                    titolari_top.append(f"{display_name} ⚽ (FV {fvoto})")
                elif voto <= 4.5 and voto > 0:
                    titolari_flop.append(f"{display_name} 💩 (voto {voto})")

            for p in bench:
                pid = int(p.get("pid", 0))
                p_name = OFFICIAL_PLAYERS_MAP.get(pid, f"Sconosciuto")
                display_name = f"{p_name} [PID:{pid}]"
                voto = float(p.get("scr", 0))
                fvoto = float(p.get("cscr", 0))

                if fvoto >= 9.5 and fvoto < 50:
                    panchina_rimpianti.append(f"GOL DI {display_name.upper()} (FV {fvoto})")
                elif voto >= 7.0 and voto < 50:
                    panchina_rimpianti.append(f"{display_name} (voto {voto})")

            if titolari_top:
                report += f"  • {team_label} - Protagonisti: {', '.join(titolari_top)}\n"
            if titolari_flop:
                report += f"  • {team_label} - Disastri: {', '.join(titolari_flop)}\n"
            if panchina_rimpianti:
                report += f"  ⚠️ <b>PANCHINA {t_owner.upper()}:</b> {', '.join(panchina_rimpianti)} lasciati fuori!\n"

    return report


def fetch_classifica(slug, competition_id):
    session = get_fanta_session()
    if not session:
        return "⚠️ Impossibile accedere a Fantacalcio."

    url = f"https://leghe.fantacalcio.it/servizi/v1_legheCompetizione/classificagiornate?alias_lega={slug}&id_competizione={competition_id}&giornata_inizio=1&giornata_fine=38"
    try:
        res = session.get(url, timeout=10)
        if res.status_code != 200:
            return "⚠️ Errore nel recupero della classifica."

        rows = res.json().get("data", [])
        if not rows:
            return "Classifica al momento non disponibile."

        testo = "🏆 <b>CLASSIFICA ATTUALE</b>\n\n"
        for i, row in enumerate(rows, 1):
            team_id = row.get("id")
            nome = TEAMS_MAP.get(team_id, {}).get("name", f"Squadra {team_id}")
            punti = int(row.get("p", 0))
            fanta_punti = float(row.get("s_p", 0.0))
            testo += f"<b>{i}.</b> {nome} — <b>{punti} pt</b> <i>({fanta_punti} fp)</i>\n"
        return testo
    except Exception as e:
        logger.error(f"Errore classifica: {e}")
        return "⚠️ Errore durante la lettura della classifica."


def get_calendario_testo(calendario, target_round=None):
    if not calendario:
        return "⚠️ Calendario non disponibile."

    if target_round is None:
        target_round = 1
        for g_num in sorted(calendario.keys()):
            matches = calendario[g_num]["matches"]
            if any(m.get("score") in ["-", "nan", ""] for m in matches):
                target_round = g_num
                break

    giornata = calendario.get(target_round)
    if not giornata:
        return f"⚠️ Giornata {target_round} non trovata nel calendario."

    testo = f"⚽ <b>{giornata['nome'].upper()}</b>\n<i>({giornata['serie_a']}ª Giornata Serie A)</i>\n\n"
    for m in giornata["matches"]:
        h = m['home']
        a = m['away']
        score = m.get("score", "-")

        if score and score not in ["-", "nan", ""]:
            testo += f"• <b>{h}</b> {m['p_home']} <b>[{score}]</b> {m['p_away']} <b>{a}</b>\n\n"
        else:
            testo += f"• <b>{h}</b> 🆚 <b>{a}</b>\n"
    return testo


def genera_recap_ai(dati_classifica, dati_tabellino, nome_lega):
    if not client:
        return "⚠️ API Key Gemini non configurata."
    prompt = f"""
    Sei il commentatore sportivo più caustico, spietato ed esilarante d'Italia. 
    Scrivi il recap ufficiale dell'ultima giornata per la lega: {nome_lega}.

    Classifica attuale:
    {dati_classifica}

    DATI UFFICIALI PARTITE, MARCATORI E PANCHINE:
    {dati_tabellino}

    LINEE GUIDA RIGIDE:
    1. Prendi di mira direttamente i proprietari storici (Giaime, Spoleto, Manuel, Gibo, Gabbo, Ciccio, Loffredo, Ernesto).
    2. SE QUALCUNO HA LASCIATO GOL O BONUS IN PANCHINA, MASSACRALO SENZA PIETÀ! Fagli notare quanto è incompetente citando i nomi dei calciatori rimasti fuori.
    3. Analizza le beffe dei punteggi (vittorie per mezzo punto, pareggi rubati).
    4. Usa solo formato HTML di Telegram: <b>grassetto</b>, <i>corsivo</i>. MAI DOPPI ASTERISCHI (**).
    5. Struttura del messaggio:
       - 📝 <b>RECAP DI GIORNATA: {nome_lega.upper()}</b> 🍿
       - Frase d'apertura tagliente.
       - ⚽️ <b>SCONTRI E DISASTRI:</b> Analizza le partite calde citando chi ha segnato e chi ha sbagliato la formazione.
       - 🍀 <b>LO SCULATO:</b> Chi vince col minimo sforzo.
       - 💩 <b>IL BIDONE D'ORO:</b> Chi ha buttato via punti lasciando gol in panca o chi è ultimo.
       - 🤡 Chiusura con insulto corale.

    Massimo 280 parole.
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text.replace("**", "<b>").replace("</b><b>", "")
    except Exception as e:
        logger.error(f"Errore Gemini: {e}")
        return "⚠️ Errore generazione recap."


def genera_alert_infortunio_ai(calciatore, squadra, proprietario, notizia_testo):
    if not client:
        return f"🚨 <b>ALLERTA INFORTUNIO!</b>\n\nBrutte notizie per <b>{proprietario}</b> ({squadra}): novità su <b>{calciatore}</b>!\n<i>{notizia_testo}</i>"
    prompt = f"""
    Sei un bot caustico di Fantacalcio. Notizia ricevuta: "{notizia_testo}".
    Il calciatore è {calciatore}, della squadra {squadra} (proprietario: {proprietario}).
    Prendi per il culo {proprietario} per la perdita del calciatore.
    Usa solo tag HTML <b>grassetto</b>. Massimo 50 parole.
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text.replace("**", "<b>")
    except Exception:
        return f"🚨 <b>ALLERTA INFORTUNIO!</b>\n\nBrutte notizie per <b>{proprietario}</b> ({squadra}): novità su <b>{calciatore}</b>!\n<i>{notizia_testo}</i>"


def get_lega_autorizzata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user_id = update.effective_user.id

    if chat.type in ["group", "supergroup"]:
        return LEGHE.get(chat.id)

    if chat.type == "private" and ADMIN_TELEGRAM_ID != 0 and user_id == ADMIN_TELEGRAM_ID:
        if context.args:
            scelta = context.args[0].strip()
            if scelta == "1":
                return LEGHE[CHAT_ID_LEGA_1]
            elif scelta == "2":
                return LEGHE[CHAT_ID_LEGA_2]
        return LEGHE[CHAT_ID_LEGA_1]
    return None


async def cmd_classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lega = get_lega_autorizzata(update, context)
    if not lega:
        if update.effective_chat.type == "private":
            await update.message.reply_text("Usa: /classifica 1 oppure /classifica 2")
        return
    msg = fetch_classifica(lega["slug"], lega["competition_id"])
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_calendario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lega = get_lega_autorizzata(update, context)
    if not lega:
        if update.effective_chat.type == "private":
            await update.message.reply_text("Usa: /calendario 1 [giornata] oppure /calendario 2 [giornata]")
        return

    target_giornata = None
    if context.args:
        for arg in context.args:
            if arg.isdigit() and int(arg) not in [1, 2]:
                target_giornata = int(arg)
                break
            elif len(context.args) == 1 and arg.isdigit() and update.effective_chat.type != "private":
                target_giornata = int(arg)

    msg = get_calendario_testo(lega["calendario"], target_giornata)
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_rosa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lega = get_lega_autorizzata(update, context)
    if not lega:
        if update.effective_chat.type == "private":
            await update.message.reply_text("Usa: /rosa 1 [NomeSquadra] oppure /rosa 2 [NomeSquadra]")
        return

    rose = lega["rose"]
    squadra_cercata = " ".join([a for a in context.args if a not in ["1", "2"]]).strip().lower()
    if not squadra_cercata:
        elenco = "\n".join([f"• <b>{t}</b> <i>({OWNER_LOOKUP.get(t.lower(), '')})</i>" for t in rose.keys()])
        await update.message.reply_text(f"Specifica una squadra:\n\n{elenco}", parse_mode="HTML")
        return

    for t_name, players in rose.items():
        if squadra_cercata in t_name.lower():
            owner = OWNER_LOOKUP.get(t_name.lower(), "")
            testo = f"🛡 <b>ROSA {t_name.upper()}</b> <i>({owner})</i>\n\n"
            testo += "\n".join([f"{i}. {p}" for i, p in enumerate(players, 1)])
            await update.message.reply_text(testo, parse_mode="HTML")
            return

    await update.message.reply_text("Squadra non trovata.")


async def cmd_test_dettaglio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TELEGRAM_ID:
        return

    lega = get_lega_autorizzata(update, context) or LEGHE[CHAT_ID_LEGA_1]
    giornata = 2

    await update.message.reply_text(f"🔍 Scarico tabellini in modalità DEBUG per <b>{lega['nome']}</b> (G{giornata})...", parse_mode="HTML")
    res = fetch_tabellini_analizzati(lega, giornata)
    await update.message.reply_text(res[:4000], parse_mode="HTML")


async def cmd_test_recap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or update.effective_user.id != ADMIN_TELEGRAM_ID:
        return

    lega = get_lega_autorizzata(update, context)
    if not lega:
        await update.message.reply_text("Specifica la lega: /test_recap 1 o /test_recap 2")
        return

    await update.message.reply_text(f"⏳ Generazione recap chirurgico per <b>{lega['nome']}</b>...", parse_mode="HTML")
    classifica_testo = fetch_classifica(lega["slug"], lega["competition_id"])
    dati_tabellino = fetch_tabellini_analizzati(lega, 2)
    recap = genera_recap_ai(classifica_testo, dati_tabellino, lega["nome"])
    try:
        await update.message.reply_text(recap, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(recap)


async def check_infortuni_e_news(app):
    feed_url = "https://www.fantacalcio.it/rss/notizie"
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:10]:
            entry_id = entry.get("id") or entry.get("link")
            if entry_id in NEWS_NOTIFICATE:
                continue

            titolo = entry.get("title", "")
            sommario = entry.get("summary", "")
            testo_news = f"{titolo} - {sommario}"

            parole_chiave = ["infortunio", "lesione", "stop", "distorsione", "salta", "operazione", "ceduto", "ufficiale"]
            if any(k in testo_news.lower() for k in parole_chiave):
                for chat_id, lega in LEGHE.items():
                    if chat_id == 0:
                        continue
                    rose = lega["rose"]
                    for team_name, players in rose.items():
                        for p in players:
                            if p.lower() in testo_news.lower() and len(p) > 3:
                                owner = OWNER_LOOKUP.get(team_name.lower(), "Mister")
                                alert_msg = genera_alert_infortunio_ai(p, team_name, owner, testo_news)
                                try:
                                    await app.bot.send_message(chat_id=chat_id, text=alert_msg, parse_mode="HTML")
                                except Exception:
                                    await app.bot.send_message(chat_id=chat_id, text=alert_msg)
                                break

            NEWS_NOTIFICATE.add(entry_id)
    except Exception as e:
        logger.error(f"Errore feed news: {e}")


async def background_checker(app):
    await asyncio.sleep(15)
    while True:
        try:
            await check_infortuni_e_news(app)

            session = get_fanta_session()
            if session:
                for chat_id, config in LEGHE.items():
                    if chat_id == 0 or not config["slug"]:
                        continue
                    url = f"https://leghe.fantacalcio.it/servizi/v1_legheCompetizione/classificagiornate?alias_lega={config['slug']}&id_competizione={config['competition_id']}&giornata_inizio=1&giornata_fine=38"
                    res = session.get(url, timeout=10)
                    if res.status_code == 200:
                        rows = res.json().get("data", [])
                        num_giocate = max((r.get("g", 0) for r in rows), default=0)
                        if num_giocate > config["ultima_giornata"] and config["ultima_giornata"] != 0:
                            classifica = fetch_classifica(config["slug"], config["competition_id"])
                            tabellino = fetch_tabellini_analizzati(config, num_giocate)
                            recap = genera_recap_ai(classifica, tabellino, config["nome"])
                            try:
                                await app.bot.send_message(chat_id=chat_id, text=recap, parse_mode="HTML")
                            except Exception:
                                await app.bot.send_message(chat_id=chat_id, text=recap)
                            config["ultima_giornata"] = num_giocate
                        elif config["ultima_giornata"] == 0:
                            config["ultima_giornata"] = num_giocate
        except Exception as e:
            logger.error(f"Errore background: {e}")
        await asyncio.sleep(1200)


async def post_init(app):
    asyncio.create_task(background_checker(app))


def main():
    if not TG_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN mancante!")
        return

    app = ApplicationBuilder().token(TG_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("classifica", cmd_classifica))
    app.add_handler(CommandHandler(["calendario", "incontri"], cmd_calendario))
    app.add_handler(CommandHandler("rosa", cmd_rosa))
    app.add_handler(CommandHandler("test_recap", cmd_test_recap))
    app.add_handler(CommandHandler("test_dettaglio", cmd_test_dettaglio))

    logger.info("Bot Fantacalcio in modalità DEBUG PID attivo.")
    app.run_polling()


if __name__ == "__main__":
    main()
