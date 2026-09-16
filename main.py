import os
import io
import asyncio
import logging
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import google.generativeai as genai

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Lettura Variabili d'Ambiente
FANTA_EMAIL = os.getenv("FANTA_EMAIL")
FANTA_PASSWORD = os.getenv("FANTA_PASSWORD")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# Configurazione API Gemini
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# Configurazione Gruppi Telegram e Leghe Fantacalcio
CHAT_ID_LEGA_1 = int(os.getenv("CHAT_ID_LEGA_1", "0"))
CHAT_ID_LEGA_2 = int(os.getenv("CHAT_ID_LEGA_2", "0"))

LEGHE = {
    CHAT_ID_LEGA_1: {
        "slug": os.getenv("SLUG_LEGA_1"),
        "nome": "Lega 1",
        "ultima_giornata": 0
    },
    CHAT_ID_LEGA_2: {
        "slug": os.getenv("SLUG_LEGA_2"),
        "nome": "Lega 2",
        "ultima_giornata": 0
    }
}

LOGIN_URL = "https://apileague.fantacalcio.it/onboarding/v1/login"
FANTA_APP_KEY = "ICiELOObd5DF5uJEATi77CRvHiiRuMU0"


def get_fanta_session():
    """Effettua il login su Fantacalcio.it con Bearer Token e App Key."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://leghe.fantacalcio.it/",
        "Origin": "https://leghe.fantacalcio.it",
        "Content-Type": "application/json",
        "app_key": FANTA_APP_KEY,
    })

    payload = {
        "username": FANTA_EMAIL,
        "password": FANTA_PASSWORD,
    }

    try:
        res = session.post(LOGIN_URL, json=payload, timeout=10)
        if res.status_code == 200:
            data = res.json()
            token = (
                data.get("token") 
                or data.get("access_token") 
                or (data.get("data", {}).get("token") if isinstance(data.get("data"), dict) else None)
            )
            
            if token:
                session.headers["Authorization"] = f"Bearer {token}"
                logger.info("Login effettuato con successo e Bearer Token acquisito!")
            else:
                logger.info("Login effettuato con successo tramite sessione.")
            return session
        else:
            logger.error(f"Login non riuscito: status {res.status_code} - {res.text}")
    except Exception as e:
        logger.error(f"Errore di rete durante il login su Fantacalcio: {e}")
    return None


def fetch_classifica(slug):
    """Estrae e formatta la classifica per la lega indicata."""
    session = get_fanta_session()
    if not session:
        return "⚠️ Impossibile accedere a Fantacalcio. Controlla le credenziali."
    
    url = f"https://leghe.fantacalcio.it/{slug}/classifica"
    try:
        res = session.get(url, timeout=10)
        if res.status_code != 200:
            return "⚠️ Errore nel recupero della classifica."
        
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.find_all("tr")
        testo = "🏆 *CLASSIFICA ATTUALE*\n\n"
        trovati = False
        for r in rows:
            cols = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
            if len(cols) >= 3 and cols[0].isdigit():
                trovati = True
                pos, squadra, pt = cols[0], cols[1], cols[2]
                testo += f"*{pos}.* {squadra} — *{pt} pt*\n"
        return testo if trovati else "Classifica al momento non disponibile."
    except Exception as e:
        logger.error(f"Errore fetch classifica: {e}")
        return "⚠️ Si è verificato un errore durante la lettura della classifica."


def fetch_incontri(slug):
    """Estrae i prossimi incontri a calendario."""
    session = get_fanta_session()
    if not session:
        return "⚠️ Impossibile accedere a Fantacalcio."
    
    url = f"https://leghe.fantacalcio.it/{slug}/calendario"
    try:
        res = session.get(url, timeout=10)
        if res.status_code != 200:
            return "⚠️ Errore nel recupero del calendario."
        
        soup = BeautifulSoup(res.text, "html.parser")
        match_items = soup.find_all("div", class_="match") or soup.find_all("li", class_="match-item")
        if not match_items:
            return "Prossimi incontri non ancora disponibili."
        
        testo = "⚽ *PROSSIMI INCONTRI*\n\n"
        for m in match_items[:4]:
            testo += f"⚔️ {m.get_text(separator=' vs ', strip=True)}\n"
        return testo
    except Exception as e:
        logger.error(f"Errore fetch incontri: {e}")
        return "⚠️ Si è verificato un errore durante la lettura del calendario."


def genera_immagine_formazioni(slug):
    """Genera al volo una card grafica con le formazioni."""
    session = get_fanta_session()
    if not session:
        return None
    
    url = f"https://leghe.fantacalcio.it/{slug}/formazioni"
    try:
        res = session.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        
        img = Image.new("RGB", (800, 600), color=(34, 139, 34))
        draw = ImageDraw.Draw(img)
        
        draw.text((25, 20), f"FORMAZIONI SCHIERATE - {slug.upper()}", fill=(255, 255, 255))
        
        cards = soup.find_all("div", class_="lineup") or soup.find_all("div", class_="team-card")
        y = 65
        if not cards:
            draw.text((25, y), "Le formazioni non sono ancora schierate o visibili.", fill=(255, 255, 255))
        else:
            for card in cards[:8]:
                titolo = card.get_text(separator=" ", strip=True)[:75]
                draw.text((25, y), f"• {titolo}", fill=(255, 255, 255))
                y += 45
                
        bio = io.BytesIO()
        bio.name = "formazioni.png"
        img.save(bio, "PNG")
        bio.seek(0)
        return bio
    except Exception as e:
        logger.error(f"Errore generazione immagine formazioni: {e}")
        return None


def genera_recap_ai(dati_giornata):
    """Invia i punteggi al modello Gemini per il commento satirico."""
    model = genai.GenerativeModel("gemini-3.1-flash-lite")

    prompt = f"""
    Sei un commentatore sportivo caustico, cinico ed esilarante.
    Ecco i risultati dell'ultima giornata del nostro fantacalcio:
    
    {dati_giornata}
    
    Scrivi un recap settimanale spietato per il nostro gruppo Telegram:
    - Commenta ognuna delle 4 partite assegnando un titolo ironico.
    - Prendi in giro chi ha perso (soprattutto per mezzo punto, gol subiti o scelte errate).
    - Assegna pagelle semiserie con voti da 1 a 10.
    - Usa formattazione leggibile per Telegram (grassetto, corsivo, elenchi ed emoji).
    - Non dilungarti eccessivamente: massimo 350-400 parole in totale.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Errore chiamata Gemini: {e}")
        return "⚠️ Errore nella generazione del recap satirico."


def get_lega_autorizzata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Isolamento canali: nei gruppi è bloccata sulla lega del gruppo, in privato risponde solo all'admin con selezione 1 o 2."""
    chat = update.effective_chat
    user_id = update.effective_user.id

    # 1. Messaggio inviato in un GRUPPO: blindato sul CHAT_ID del gruppo
    if chat.type in ["group", "supergroup"]:
        if chat.id in LEGHE and LEGHE[chat.id]["slug"]:
            return LEGHE[chat.id]
        return None

    # 2. Messaggio inviato in PRIVATO: solo l'Admin può accedere
    if chat.type == "private" and ADMIN_TELEGRAM_ID != 0 and user_id == ADMIN_TELEGRAM_ID:
        # Se specifichi 1 o 2 (es. /classifica 1 o /classifica 2)
        if context.args:
            scelta = context.args[0].strip()
            if scelta == "1" and CHAT_ID_LEGA_1 in LEGHE:
                return LEGHE[CHAT_ID_LEGA_1]
            elif scelta == "2" and CHAT_ID_LEGA_2 in LEGHE:
                return LEGHE[CHAT_ID_LEGA_2]
        
        # Di default in privato risponde per la Lega 1 se non specificato
        if CHAT_ID_LEGA_1 in LEGHE and LEGHE[CHAT_ID_LEGA_1]["slug"]:
            return LEGHE[CHAT_ID_LEGA_1]

    return None


# Handler Comandi Telegram
async def cmd_classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lega = get_lega_autorizzata(update, context)
    if not lega or not lega["slug"]:
        if update.effective_chat.type == "private":
            await update.message.reply_text("⛔ Usa `/classifica 1` oppure `/classifica 2`.", parse_mode="Markdown")
        return
    msg = fetch_classifica(lega["slug"])
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_incontri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lega = get_lega_autorizzata(update, context)
    if not lega or not lega["slug"]:
        if update.effective_chat.type == "private":
            await update.message.reply_text("⛔ Usa `/incontri 1` oppure `/incontri 2`.", parse_mode="Markdown")
        return
    msg = fetch_incontri(lega["slug"])
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_formazioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lega = get_lega_autorizzata(update, context)
    if not lega or not lega["slug"]:
        if update.effective_chat.type == "private":
            await update.message.reply_text("⛔ Usa `/formazioni 1` oppure `/formazioni 2`.", parse_mode="Markdown")
        return
    photo_bytes = genera_immagine_formazioni(lega["slug"])
    if photo_bytes:
        await update.message.reply_photo(photo=photo_bytes, caption=f"📋 Formazioni schierate ({lega['nome']})")
    else:
        await update.message.reply_text("⚠️ Impossibile generare la scheda formazioni al momento.")


async def cmd_test_recap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando riservato solo all'Admin in privato per testare Gemini."""
    if update.effective_chat.type != "private" or update.effective_user.id != ADMIN_TELEGRAM_ID:
        return

    lega = get_lega_autorizzata(update, context)
    if not lega or not lega["slug"]:
        await update.message.reply_text("Specifica la lega: `/test_recap 1` o `/test_recap 2`", parse_mode="Markdown")
        return

    await update.message.reply_text(f"⏳ Generazione recap satirico per {lega['nome']}...")
    session = get_fanta_session()
    if not session:
        await update.message.reply_text("⚠️ Errore di login a Fantacalcio.")
        return

    url = f"https://leghe.fantacalcio.it/{lega['slug']}/ultima-giornata"
    try:
        res = session.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        dati_grezzi = soup.get_text(separator=" ", strip=True)[:3500]
        recap = genera_recap_ai(dati_grezzi)
        await update.message.reply_text(recap, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Errore: {e}")


async def background_calcolo_checker(app):
    """Loop asincrono in background: controlla ogni 20 minuti l'uscita dei calcoli definitivi."""
    await asyncio.sleep(10)
    while True:
        try:
            session = get_fanta_session()
            if session:
                for chat_id, config in LEGHE.items():
                    if chat_id == 0 or not config["slug"]:
                        continue
                    url = f"https://leghe.fantacalcio.it/{config['slug']}/ultima-giornata"
                    res = session.get(url, timeout=10)
                    if res.status_code != 200:
                        continue

                    soup = BeautifulSoup(res.text, "html.parser")
                    calcolata = "definitiv" in res.text.lower() or "calcolata" in res.text.lower()
                    
                    giornata_tag = soup.find("span", class_="round-name")
                    num_giornata = int(''.join(filter(str.isdigit, giornata_tag.text))) if giornata_tag else 1

                    if calcolata and num_giornata > config["ultima_giornata"]:
                        logger.info(f"Nuova giornata rilevata per {config['nome']}: {num_giornata}")
                        dati_grezzi = soup.get_text(separator=" ", strip=True)[:3500]
                        recap = genera_recap_ai(dati_grezzi)
                        await app.bot.send_message(chat_id=chat_id, text=recap, parse_mode="Markdown")
                        config["ultima_giornata"] = num_giornata
        except Exception as e:
            logger.error(f"Errore nel loop di controllo calcolo: {e}")
        
        await asyncio.sleep(1200)


async def post_init(app):
    asyncio.create_task(background_calcolo_checker(app))


def main():
    if not TG_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN non configurato!")
        return

    app = ApplicationBuilder().token(TG_TOKEN).post_init(post_init).build()

    # Registrazione Comandi
    app.add_handler(CommandHandler("classifica", cmd_classifica))
    app.add_handler(CommandHandler("incontri", cmd_incontri))
    app.add_handler(CommandHandler("formazioni", cmd_formazioni))
    app.add_handler(CommandHandler("test_recap", cmd_test_recap))

    logger.info("Bot Fantacalcio avviato con successo e in ascolto...")
    app.run_polling()


if __name__ == "__main__":
    main()
