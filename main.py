import os
import io
import asyncio
import logging
import requests
from PIL import Image, ImageDraw
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

LEGHE = {
    CHAT_ID_LEGA_1: {
        "slug": os.getenv("SLUG_LEGA_1", "fanta4reich"),
        "competition_id": int(os.getenv("COMP_ID_LEGA_1", "206672")),
        "nome": "Fanta4Reich",
        "ultima_giornata": 0
    },
    CHAT_ID_LEGA_2: {
        "slug": os.getenv("SLUG_LEGA_2", "fantacalcio-stalloni-26-27"),
        "competition_id": int(os.getenv("COMP_ID_LEGA_2", "320101")),
        "nome": "Fantacalcio Stalloni",
        "ultima_giornata": 0
    }
}

LOGIN_URL = "https://apileague.fantacalcio.it/onboarding/v1/login"
FANTA_APP_KEY = "ICiELOObd5DF5uJEATi77CRvHiiRuMU0"


def get_fanta_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
            token = data.get("token") or data.get("access_token") or (data.get("data", {}).get("token") if isinstance(data.get("data"), dict) else None)
            if token:
                session.headers["Authorization"] = f"Bearer {token}"
            return session
        else:
            logger.error(f"Login non riuscito: status {res.status_code} - {res.text}")
    except Exception as e:
        logger.error(f"Errore di rete login: {e}")
    return None


def get_teams_map(session, competition_id):
    url = f"https://apileague.fantacalcio.it/onboarding/v1/league/competition/teams?page=1&pageSize=50&competitionId={competition_id}"
    teams = {}
    try:
        res = session.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            items = data.get("data", []) if isinstance(data, dict) else data
            if isinstance(items, dict):
                items = items.get("items", []) or items.get("teams", [])
            for item in items:
                t_id = item.get("id") or item.get("teamId")
                t_name = item.get("name") or item.get("teamName") or item.get("nome")
                if t_id and t_name:
                    teams[t_id] = t_name
    except Exception as e:
        logger.error(f"Errore fetch teams map: {e}")
    return teams


def fetch_classifica(slug, competition_id):
    session = get_fanta_session()
    if not session:
        return "Impossibile accedere a Fantacalcio. Controlla le credenziali."

    teams_map = get_teams_map(session, competition_id)
    url = f"https://leghe.fantacalcio.it/servizi/v1_legheCompetizione/classificagiornate?alias_lega={slug}&id_competizione={competition_id}&giornata_inizio=1&giornata_fine=38"
    
    try:
        res = session.get(url, timeout=10)
        if res.status_code != 200:
            return "Errore nel recupero della classifica."

        payload = res.json()
        rows = payload.get("data", [])
        if not rows:
            return "Classifica al momento non disponibile."

        testo = "🏆 CLASSIFICA ATTUALE\n\n"
        for i, row in enumerate(rows, 1):
            team_id = row.get("id")
            squadra_nome = teams_map.get(team_id, f"Squadra {team_id}")
            punti = row.get("p", 0)
            fanta_punti = row.get("s_p", 0.0)
            testo += f"{i}. {squadra_nome} — {punti} pt ({fanta_punti} fp)\n"
        return testo
    except Exception as e:
        logger.error(f"Errore fetch classifica: {e}")
        return "Errore durante la lettura della classifica."


def fetch_incontri(competition_id):
    session = get_fanta_session()
    if not session:
        return "Impossibile accedere a Fantacalcio."

    teams_map = get_teams_map(session, competition_id)
    url = f"https://apileague.fantacalcio.it/onboarding/v1/league/competition/calendar/{competition_id}"
    
    try:
        res = session.get(url, timeout=10)
        if res.status_code != 200:
            return "Errore nel recupero del calendario."

        data = res.json()
        calendar_data = data.get("data", data)
        days = calendar_data.get("days", []) if isinstance(calendar_data, dict) else []

        active_day = next((d for d in days if not d.get("isFinished", False) and not d.get("calculated", False)), None)
        if not active_day and days:
            active_day = days[-1]

        if not active_day:
            return "Prossimi incontri non disponibili."

        matches = active_day.get("matches", [])
        round_name = active_day.get("name", "Prossima Giornata")
        testo = f"⚽ {round_name.upper()}\n\n"

        for m in matches:
            home_id = m.get("homeTeamId") or m.get("id_squadra_casa")
            away_id = m.get("awayTeamId") or m.get("id_squadra_trasferta")
            home_name = teams_map.get(home_id, m.get("homeTeamName", "Casa"))
            away_name = teams_map.get(away_id, m.get("awayTeamName", "Trasferta"))
            testo += f"⚔️ {home_name} vs {away_name}\n"

        return testo
    except Exception as e:
        logger.error(f"Errore fetch incontri: {e}")
        return "Errore durante la lettura del calendario."


def genera_immagine_formazioni(slug):
    img = Image.new("RGB", (700, 300), color=(34, 139, 34))
    draw = ImageDraw.Draw(img)
    draw.text((25, 25), f"FORMAZIONI - {slug.upper()}", fill=(255, 255, 255))
    draw.text((25, 80), "Per le formazioni live consulta l'app ufficiale.", fill=(255, 255, 255))
    
    bio = io.BytesIO()
    bio.name = "formazioni.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio


def genera_recap_ai(dati_giornata):
    model = genai.GenerativeModel("gemini-3.1-flash-lite")
    prompt = f"""
    Sei un commentatore sportivo caustico, cinico ed esilarante.
    Ecco i risultati dell'ultima giornata del nostro fantacalcio:
    
    {dati_giornata}
    
    Scrivi un recap settimanale spietato per il gruppo Telegram:
    - Commenta le partite assegnando a ciascuna un titolo ironico.
    - Prendi in giro chi ha perso.
    - Assegna pagelle con voti da 1 a 10.
    - Usa un testo pulito e leggibile (non eccedere con formattazioni complesse).
    - Massimo 350 parole.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Errore chiamata Gemini: {e}")
        return "Errore nella generazione del recap satirico."


def get_lega_autorizzata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user_id = update.effective_user.id

    if chat.type in ["group", "supergroup"]:
        if chat.id in LEGHE and LEGHE[chat.id]["slug"]:
            return LEGHE[chat.id]
        return None

    if chat.type == "private" and ADMIN_TELEGRAM_ID != 0 and user_id == ADMIN_TELEGRAM_ID:
        if context.args:
            scelta = context.args[0].strip()
            if scelta == "1" and CHAT_ID_LEGA_1 in LEGHE:
                return LEGHE[CHAT_ID_LEGA_1]
            elif scelta == "2" and CHAT_ID_LEGA_2 in LEGHE:
                return LEGHE[CHAT_ID_LEGA_2]
        
        if CHAT_ID_LEGA_1 in LEGHE and LEGHE[CHAT_ID_LEGA_1]["slug"]:
            return LEGHE[CHAT_ID_LEGA_1]

    return None


async def cmd_classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lega = get_lega_autorizzata(update, context)
    if not lega or not lega["slug"]:
        if update.effective_chat.type == "private":
            await update.message.reply_text("Usa /classifica 1 oppure /classifica 2")
        return
    msg = fetch_classifica(lega["slug"], lega["competition_id"])
    await update.message.reply_text(msg)


async def cmd_incontri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lega = get_lega_autorizzata(update, context)
    if not lega or not lega["slug"]:
        if update.effective_chat.type == "private":
            await update.message.reply_text("Usa /incontri 1 oppure /incontri 2")
        return
    msg = fetch_incontri(lega["competition_id"])
    await update.message.reply_text(msg)


async def cmd_formazioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lega = get_lega_autorizzata(update, context)
    if not lega or not lega["slug"]:
        if update.effective_chat.type == "private":
            await update.message.reply_text("Usa /formazioni 1 oppure /formazioni 2")
        return
    photo_bytes = genera_immagine_formazioni(lega["slug"])
    if photo_bytes:
        await update.message.reply_photo(photo=photo_bytes, caption=f"Formazioni ({lega['nome']})")


async def cmd_test_recap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or update.effective_user.id != ADMIN_TELEGRAM_ID:
        return

    lega = get_lega_autorizzata(update, context)
    if not lega or not lega["slug"]:
        await update.message.reply_text("Specifica la lega: /test_recap 1 o /test_recap 2")
        return

    await update.message.reply_text(f"Generazione recap satirico per {lega['nome']}...")
    session = get_fanta_session()
    if not session:
        await update.message.reply_text("Errore di login a Fantacalcio.")
        return

    url = f"https://leghe.fantacalcio.it/servizi/v1_legheCompetizione/classificagiornate?alias_lega={lega['slug']}&id_competizione={lega['competition_id']}&giornata_inizio=1&giornata_fine=38"
    try:
        res = session.get(url, timeout=10)
        dati_grezzi = res.text[:3500]
        recap = genera_recap_ai(dati_grezzi)
        await update.message.reply_text(recap)
    except Exception as e:
        await update.message.reply_text(f"Errore: {e}")


async def background_calcolo_checker(app):
    await asyncio.sleep(10)
    while True:
        try:
            session = get_fanta_session()
            if session:
                for chat_id, config in LEGHE.items():
                    if chat_id == 0 or not config["slug"]:
                        continue
                    url = f"https://leghe.fantacalcio.it/servizi/v1_legheCompetizione/classificagiornate?alias_lega={config['slug']}&id_competizione={config['competition_id']}&giornata_inizio=1&giornata_fine=38"
                    res = session.get(url, timeout=10)
                    if res.status_code == 200:
                        payload = res.json()
                        rows = payload.get("data", [])
                        num_giocate = max((r.get("g", 0) for r in rows), default=0)
                        if num_giocate > config["ultima_giornata"] and config["ultima_giornata"] != 0:
                            recap = genera_recap_ai(res.text[:3500])
                            await app.bot.send_message(chat_id=chat_id, text=recap)
                            config["ultima_giornata"] = num_giocate
                        elif config["ultima_giornata"] == 0:
                            config["ultima_giornata"] = num_giocate
        except Exception as e:
            logger.error(f"Errore nel background checker: {e}")
        await asyncio.sleep(1200)


async def post_init(app):
    asyncio.create_task(background_calcolo_checker(app))


def main():
    if not TG_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN mancante!")
        return

    app = ApplicationBuilder().token(TG_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("classifica", cmd_classifica))
    app.add_handler(CommandHandler("incontri", cmd_incontri))
    app.add_handler(CommandHandler("formazioni", cmd_formazioni))
    app.add_handler(CommandHandler("test_recap", cmd_test_recap))

    logger.info("Bot Fantacalcio avviato con successo.")
    app.run_polling()


if __name__ == "__main__":
    main()
