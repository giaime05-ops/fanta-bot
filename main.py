import os
import asyncio
import logging
import requests
import pandas as pd
import feedparser
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import google.generativeai as genai

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

FANTA_EMAIL = os.getenv("FANTA_EMAIL")
FANTA_PASSWORD = os.getenv("FANTA_PASSWORD")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "6226253008"))

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

CHAT_ID_LEGA_1 = int(os.getenv("CHAT_ID_LEGA_1", "0"))
CHAT_ID_LEGA_2 = int(os.getenv("CHAT_ID_LEGA_2", "0"))

TEAMS_MAP = {
    # Lega 1
    18831834: {"name": "UwU", "owner": "gibo"},
    18883778: {"name": "NicoPanz", "owner": "Ciccio"},
    18833116: {"name": "Al-Qaeda United", "owner": "spoleto17"},
    18832547: {"name": "CHIVUISMO", "owner": "Gabbo"},
    18831242: {"name": "Deportivo Sa Carogna", "owner": "Giaime"},
    18832350: {"name": "Luton Down", "owner": "Manuel"},
    18883572: {"name": "BENE EH MANCO MALEN", "owner": "Lamine Kialunga"},
    18885993: {"name": "RSA riabilitazione", "owner": "El vecho"},
    # Lega 2
    19197193: {"name": "HINTER X HINTER", "owner": "gibo"},
    19196752: {"name": "DEMOCRAZIA CRISTANTE", "owner": "Cryan Bristante"},
    19213432: {"name": "COSTIERA ANALFITANA", "owner": "Manuel"},
    19196408: {"name": "CHIVUISMO", "owner": "Gabbo"},
    19213197: {"name": "Scrotone", "owner": "loffredo03"},
    19213459: {"name": "FREE SAPOMODORO FC", "owner": "Marco Priolo Pinolo"},
    19176402: {"name": "IchNusa", "owner": "Giaime"},
    19207011: {"name": "FC Pinolandia", "owner": "Ernesto Tavaroni"}
}

OWNER_LOOKUP = {v["name"].strip().lower(): v["owner"] for v in TEAMS_MAP.values()}

LEGHE = {
    CHAT_ID_LEGA_1: {
        "slug": "fanta4reich",
        "competition_id": 206672,
        "nome": "Fanta4Reich",
        "excel_calendario": "Calendario_Campionato-Nazista.xlsx",
        "excel_rose": "fanta4reich-rosters-1789585342102.xlsx",
        "ultima_giornata": 0
    },
    CHAT_ID_LEGA_2: {
        "slug": "fantacalcio-stalloni-26-27",
        "competition_id": 320101,
        "nome": "Fantacalcio Stalloni",
        "excel_calendario": "Calendario_FANTASTALLONI-26-27.xlsx",
        "excel_rose": "fantacalcio-stalloni-26-27-rosters-1789585334790.xlsx",
        "ultima_giornata": 0
    }
}

LOGIN_URL = "https://apileague.fantacalcio.it/onboarding/v1/login"
FANTA_APP_KEY = "ICiELOObd5DF5uJEATi77CRvHiiRuMU0"
NEWS_NOTIFICATE = set()


def get_fanta_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://leghe.fantacalcio.it/",
        "Origin": "https://leghe.fantacalcio.it",
        "Content-Type": "application/json",
        "app_key": FANTA_APP_KEY,
    })
    payload = {"username": FANTA_EMAIL, "password": FANTA_PASSWORD}
    try:
        res = session.post(LOGIN_URL, json=payload, timeout=10)
        if res.status_code == 200:
            data = res.json()
            token = data.get("token") or data.get("access_token")
            if token:
                session.headers["Authorization"] = f"Bearer {token}"
            return session
    except Exception as e:
        logger.error(f"Errore login: {e}")
    return None


def parse_rosters_file(filepath):
    """Carica la lista giocatori per ogni squadra dal file Excel delle rose."""
    if not os.path.exists(filepath):
        return {}
    try:
        df = pd.read_excel(filepath, sheet_name=0)
        rosters = {}
        for c_idx in range(0, len(df.columns), 3):
            team_name = df.columns[c_idx].strip()
            players = df.iloc[:, c_idx].dropna().astype(str).tolist()
            players = [p.strip() for p in players if p.strip() and p.strip() != 'nan']
            rosters[team_name] = players
        return rosters
    except Exception as e:
        logger.error(f"Errore lettura rose {filepath}: {e}")
        return {}


def get_player_owner(player_name, filepath_rose):
    """Trova quale squadra e quale proprietario possiede il calciatore indicato."""
    rose = parse_rosters_file(filepath_rose)
    p_clean = player_name.lower().strip()
    for team, players in rose.items():
        for p in players:
            if p_clean in p.lower() or p.lower() in p_clean:
                owner = OWNER_LOOKUP.get(team.lower(), "Presidente")
                return team, owner, p
    return None, None, None


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
            team = TEAMS_MAP.get(team_id, {"name": f"Squadra {team_id}", "owner": "N/D"})
            punti = row.get("p", 0)
            fanta_punti = row.get("s_p", 0.0)
            testo += f"<b>{i}.</b> {team['name']} <i>({team['owner']})</i> — <b>{punti} pt</b> ({fanta_punti} fp)\n"
        return testo
    except Exception as e:
        logger.error(f"Errore classifica: {e}")
        return "⚠️ Errore durante la lettura della classifica."


def parse_calendario_excel(filepath):
    if not os.path.exists(filepath):
        return {}
    try:
        df = pd.read_excel(filepath, sheet_name=0, header=None)
        calendar = {}
        for r in range(len(df)):
            for col in [0, 6]:
                val = str(df.iloc[r, col])
                if "Giornata lega" in val:
                    g_num = int(val.strip().split('ª')[0])
                    serie_a = str(df.iloc[r, col + 2]).strip()
                    matches = []
                    for m in range(1, 5):
                        if r + m < len(df):
                            home = str(df.iloc[r + m, col]).strip()
                            p_home = df.iloc[r + m, col + 1]
                            p_away = df.iloc[r + m, col + 2]
                            away = str(df.iloc[r + m, col + 3]).strip()
                            score = str(df.iloc[r + m, col + 4]).strip()
                            if home and away and home != 'nan' and away != 'nan':
                                matches.append({
                                    "home": home,
                                    "away": away,
                                    "p_home": p_home,
                                    "p_away": p_away,
                                    "score": score
                                })
                    calendar[g_num] = {"nome": val.strip(), "serie_a": serie_a, "matches": matches}
        return calendar
    except Exception as e:
        logger.error(f"Errore lettura Excel {filepath}: {e}")
        return {}


def get_incontri_testo(filepath, target_round=None):
    calendario = parse_calendario_excel(filepath)
    if not calendario:
        return "⚠️ File calendario non trovato sul server."

    if target_round is None:
        target_round = 1
        for g_num in sorted(calendario.keys()):
            matches = calendario[g_num]["matches"]
            da_giocare = any(m["score"] in ["-", "nan", ""] for m in matches)
            if da_giocare:
                target_round = g_num
                break

    giornata = calendario.get(target_round)
    if not giornata:
        return f"⚠️ Giornata {target_round} non trovata nel calendario."

    testo = f"⚽ <b>{giornata['nome'].upper()}</b>\n<i>({giornata['serie_a']})</i>\n\n"
    for m in giornata["matches"]:
        h_owner = OWNER_LOOKUP.get(m['home'].lower(), "")
        a_owner = OWNER_LOOKUP.get(m['away'].lower(), "")
        h_str = f"{m['home']} <i>({h_owner})</i>" if h_owner else m['home']
        a_str = f"{m['away']} <i>({a_owner})</i>" if a_owner else m['away']
        
        if m['score'] not in ["-", "nan", ""]:
            testo += f"⚔️ <b>{h_str}</b> {m['p_home']} [{m['score']}] {m['p_away']} <b>{a_str}</b>\n"
        else:
            testo += f"⚔️ <b>{h_str}</b> vs <b>{a_str}</b>\n"
    return testo


def genera_recap_ai(dati_classifica, nome_lega):
    model = genai.GenerativeModel("gemini-3.1-flash-lite")
    prompt = f"""
    Sei il commentatore sportivo più caustico, bastardo ed esilarante d'Italia. 
    Scrivi il recap ufficiale dell'ultima giornata per la lega: {nome_lega}.

    Ecco la classifica e i punteggi aggiornati:
    {dati_classifica}

    LINEE GUIDA:
    1. Prendi di mira direttamente i proprietari (Giaime, Spoleto, Manuel, Gibo, Gabbo, Ciccio, ecc.).
    2. Usa il formato HTML di Telegram: <b>grassetto</b>, <i>corsivo</i>. NON USARE DOPPI ASTERISCHI.
    3. Segui la struttura:
       - 📝 <b>RECAP DI GIORNATA: {nome_lega.upper()}</b> 🍿
       - Frase d'apertura dissacrante sul livello del weekend.
       - ⚽️ <b>SCONTRI E DISASTRI:</b> Commenta le partite più calde.
       - 🍀 <b>LO SCULATO DELLA SETTIMANA:</b> Prendi per il culo chi vince con fortuna.
       - 💩 <b>IL BIDONE D'ORO:</b> Umilia l'ultimo in classifica.
       - 🤡 Chiusura con insulto corale.

    Massimo 300 parole, stile brillante e compatto.
    """
    try:
        res = model.generate_content(prompt)
        testo = res.text.replace("**", "<b>").replace("</b><b>", "")
        return testo
    except Exception as e:
        logger.error(f"Errore Gemini: {e}")
        return "⚠️ Errore generazione recap."


def genera_alert_infortunio_ai(calciatore, squadra, proprietario, notizia_testo):
    """Genera una presa in giro satirica specifica per l'infortunio di un calciatore."""
    model = genai.GenerativeModel("gemini-3.1-flash-lite")
    prompt = f"""
    Sei un bot di Fantacalcio caustico e perfido. 
    È appena arrivata questa brutta notizia di infortunio/mercato:
    "{notizia_testo}"
    
    Il calciatore infortunato è: {calciatore}.
    La squadra che lo possiede è: {squadra}, presieduta da: {proprietario}.
    
    Scrivi un messaggio satirico, cattivo ed esilarante indirizzato direttamente a {proprietario} per prenderlo in giro sul fatto che il suo top player è andato k.o.
    Usa formato HTML di Telegram (<b>grassetto</b>). Massimo 70 parole.
    """
    try:
        res = model.generate_content(prompt)
        return res.text.replace("**", "<b>")
    except Exception:
        return f"🚨 <b>BOLLETTINO MEDICO</b>\n\nBrutte notizie per <b>{proprietario}</b> ({squadra}): si è fatto male <b>{calciatore}</b>!\n<i>{notizia_testo}</i>"


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


async def cmd_incontri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lega = get_lega_autorizzata(update, context)
    if not lega:
        if update.effective_chat.type == "private":
            await update.message.reply_text("Usa: /incontri 1 [giornata] oppure /incontri 2 [giornata]")
        return

    target_giornata = None
    if context.args:
        for arg in context.args:
            if arg.isdigit() and int(arg) not in [1, 2]:
                target_giornata = int(arg)
                break
            elif len(context.args) == 1 and arg.isdigit() and update.effective_chat.type != "private":
                target_giornata = int(arg)

    msg = get_incontri_testo(lega["excel_calendario"], target_giornata)
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_rosa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra la rosa di una determinata squadra."""
    lega = get_lega_autorizzata(update, context)
    if not lega:
        if update.effective_chat.type == "private":
            await update.message.reply_text("Usa: /rosa 1 [NomeSquadra] oppure /rosa 2 [NomeSquadra]")
        return

    rose = parse_rosters_file(lega["excel_rose"])
    if not rose:
        await update.message.reply_text("⚠️ File rose non trovato sul server.")
        return

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


async def cmd_test_recap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or update.effective_user.id != ADMIN_TELEGRAM_ID:
        return

    lega = get_lega_autorizzata(update, context)
    if not lega:
        await update.message.reply_text("Specifica la lega: /test_recap 1 o /test_recap 2")
        return

    await update.message.reply_text(f"⏳ Generazione recap per <b>{lega['nome']}</b>...", parse_mode="HTML")
    classifica_testo = fetch_classifica(lega["slug"], lega["competition_id"])
    recap = genera_recap_ai(classifica_testo, lega["nome"])
    try:
        await update.message.reply_text(recap, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(recap)


async def check_infortuni_e_news(app):
    """Monitora il feed notizie di Fantacalcio e manda alert al gruppo specifico."""
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
                    rose = parse_rosters_file(lega["excel_rose"])
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
        logger.error(f"Errore controllo notizie: {e}")


async def background_checker(app):
    await asyncio.sleep(15)
    while True:
        try:
            # 1. Controllo Infortuni e Notizie
            await check_infortuni_e_news(app)

            # 2. Controllo Calcolo Nuova Giornata
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
                            recap = genera_recap_ai(classifica, config["nome"])
                            try:
                                await app.bot.send_message(chat_id=chat_id, text=recap, parse_mode="HTML")
                            except Exception:
                                await app.bot.send_message(chat_id=chat_id, text=recap)
                            config["ultima_giornata"] = num_giocate
                        elif config["ultima_giornata"] == 0:
                            config["ultima_giornata"] = num_giocate
        except Exception as e:
            logger.error(f"Errore nel background worker: {e}")
        await asyncio.sleep(1200)


async def post_init(app):
    asyncio.create_task(background_checker(app))


def main():
    if not TG_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN mancante!")
        return

    app = ApplicationBuilder().token(TG_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("classifica", cmd_classifica))
    app.add_handler(CommandHandler("incontri", cmd_incontri))
    app.add_handler(CommandHandler("rosa", cmd_rosa))
    app.add_handler(CommandHandler("test_recap", cmd_test_recap))

    logger.info("Bot Fantacalcio avviato con supporto Rose, Calendario e Alert Infortuni.")
    app.run_polling()


if __name__ == "__main__":
    main()
