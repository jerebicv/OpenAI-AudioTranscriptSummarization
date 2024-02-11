import streamlit as st
import os 
import re
import openai
from htmlTemplates import css, bot_template
import sqlite3
from langchain.chains import LLMChain
from langchain import OpenAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv


def create_users_db():
    conn = sqlite3.connect('MASTER.db')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            password TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_user_to_db(email, password):
    conn = sqlite3.connect('MASTER.db')
    cursor = conn.cursor()
    insert_query = """
        INSERT INTO Users (email, password)
        VALUES (?, ?)
    """
    cursor.execute(insert_query, (email, password))
    conn.commit()
    conn.close()


def authenticate_user(email, password):
    conn = sqlite3.connect('MASTER.db')
    cursor = conn.cursor()
    select_query = """
        SELECT * FROM Users WHERE email = ? AND password = ?
    """
    cursor.execute(select_query, (email, password))
    user = cursor.fetchone()
    conn.close()
    if user:
        return True
    else:
        return False
    

def get_user_id(email):
    conn = sqlite3.connect('MASTER.db')
    cursor = conn.cursor()
    select_query = """
        SELECT user_id FROM Users WHERE email = ?
    """
    cursor.execute(select_query, (email,))
    user_id = cursor.fetchone()
    conn.close()
    return user_id[0] if user_id else None

    

def approve_password(password):
    if len(password) >= 8 and re.search(r"(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[_@$#!?&*%])", password):
        return True
    return False
    
def create_transcripts_db():
    with sqlite3.connect('MASTER.db') as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                transcription TEXT,
                transcription_summary TEXT,
                user_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES Users(user_id)
            )
        """)


def insert_into_transcripts(user_id, file_name, transcription, transcription_summary):
    with sqlite3.connect('MASTER.db') as conn:
        cursor = conn.cursor()
        query = """
            INSERT INTO Transcripts (user_id, file_name, transcription, transcription_summary) 
            VALUES (?, ?, ?, ?)
        """
        cursor.execute(query, (user_id, file_name, transcription, transcription_summary))
        conn.commit()


def get_transcript_ids_and_names():
    with sqlite3.connect('MASTER.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, file_name FROM Transcripts")
        results = cursor.fetchall()
        return [f"{row[0]} - {row[1]}" for row in results]
    

def get_transcript_by_id(selection):
    id = int(selection.split(' - ')[0])
    with sqlite3.connect('MASTER.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT transcription FROM Transcripts WHERE id = ?", (id,))
        result = cursor.fetchone()
        if result is not None: return result[0]
        else: return "No transcript found for the given id"


def get_summary_by_id(selection):
    id = int(selection.split(' - ')[0])
    with sqlite3.connect('MASTER.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT transcription_summary FROM Transcripts WHERE id = ? AND user_id = ?", 
                       (id, st.session_state.user_id))
        result = cursor.fetchone()
        if result is not None: return result[0]
        else: return "No transcript found for the given id"


def user_authentication_tab():
    if st.session_state.user_authenticated:
        st.success("Korisnik uspješno logiran")
    else:
        with st.expander("Autentifikacija", expanded=True):
            login_tab, create_account_tab = st.tabs(["Login", "Create Account"])

            with login_tab:
                email = st.text_input("Email:") 
                password = st.text_input("Password:", type='password')
                if st.button("Login"):
                    if authenticate_user(email=email,password=password):
                        st.session_state.user_authenticated = True
                        st.session_state.user_id = get_user_id(email=email)
                        st.experimental_rerun()
                    else:
                        st.caption('Netočno ime ili šifra')


            with create_account_tab:
                new_email = st.text_input("New Email:")
                new_password = st.text_input("New Password:", type='password')
                confirm_password = st.text_input("Confirm Password:", type='password')
                if st.button("Create Account"):
                    if not approve_password(new_password):
                        st.caption("Invalid Password")
                        return
                    if new_password != confirm_password:
                        st.caption("Passwords do not match")
                        return
                    add_user_to_db(email=new_email, password=new_password)
                    st.caption(f"{new_email} Successfully Added")
#Sistemski prompt za analizu razgovora u call centru
system_prompt = f"""
Opis zadatka:
Analizirajte transkripte razgovora agenata u call centru kako biste pratili njihovu uspješnost i performanse prema predefiniranom obrascu. 
Cilj je identificirati obrasce ponašanja agenata i pružiti preporuke za poboljšanje korisničkog iskustva.
Agenti rade u pozivnom centru za naplatu zakašnjelih potraživanja. 

Kriteriji uspješnosti:

Kvaliteta usluge: Ocjena pristojnosti, jasnoće i korisničkog iskustva tijekom razgovora.
Rješavanje problema: Procjena sposobnosti agenata u rješavanju problema korisnika.
Pridržavanje protokola: Ocjena pridržavanja postavljenih procedura i protokola.

Standardna pitanja za analizu:
Jesu li agenti ljubazno pozdravili korisnike na početku razgovora?
Koliko je puta agent morao ponoviti informaciju ili pitanje korisnika radi jasnoće?
Jesu li agenti efikasno rješavali probleme korisnika?
Koliko je vremena agent proveo u pronalaženju potrebnih informacija tijekom razgovora?
Jesu li agenti pravilno koristili dostupne alate i resurse?
Jesu li agenti premašili očekivanja korisnika ili dodali dodatnu vrijednost razgovoru?
Jesu li agenti zabilježili sve potrebne informacije ili zahtjeve korisnika na odgovarajući način?
Jesu li agenti ostali smireni i profesionalni tijekom potencijalno stresnih situacija?
Jesu li agenti aktivno slušali korisnike i postavljali relevantna pitanja radi boljeg razumijevanja problema?
Konačna analiza:
Koristeći transkripte razgovora, analizirajte svakog agenta pojedinačno kako biste identificirali njihove snage i slabosti u pružanju usluge. 
Ocijenite ih prema zadanim kriterijima i predložite eventualne korake za poboljšanje performansi.

Očekivani rezultati:
Očekuje se da će analiza pomoći u identificiranju obrazaca ponašanja agenata i pružiti smjernice za poboljšanje kvalitete usluge i korisničkog iskustva u call centru.
Analiza treba biti u standardiziranom formatu.
"""

def main():
    st.set_page_config(page_title="LLM - analiza razgovora agenta")
    create_users_db()
    create_transcripts_db()
    st.write(css, unsafe_allow_html=True)
    st.session_state.setdefault("audio_file_path", None)
    st.session_state.setdefault("transcript", None)
    st.session_state.setdefault("transcript_summary")
    st.session_state.setdefault("prev_file_path", None)
    st.session_state.setdefault("prev_transcript", None)
    st.session_state.setdefault("user_id", None)
    st.session_state.setdefault("user_authenticated", False)
    st.title("LLM - analiza razgovora agenta")
    user_authentication_tab()

    if st.session_state.user_authenticated:
        create_tab, prev_tab = st.tabs(["Analiziraj razgovor","Prethodne analize"])

        with create_tab:
            uploaded_file = st.file_uploader("Učitaj snimku", type=['mp3', 'mp4', 'mpeg', 'mpga', 
                                                                        'm4a', 'wav', 'webm'])
            
            if st.button("Generiraj transkript") and uploaded_file:
                with st.spinner('Processing...'):
                    upload_dir = 'uploads'
                    os.makedirs(upload_dir, exist_ok=True)
                    file_path = os.path.join(upload_dir, uploaded_file.name)
                    with open(file_path, 'wb') as f:
                        f.write(uploaded_file.getbuffer())
                    st.session_state.audio_file_path = file_path
                    with open(st.session_state.audio_file_path, 'rb') as audio_file:
                        st.session_state.transcript = openai.Audio.transcribe("whisper-1", audio_file, language = 'hr')['text']
                    summary_prompt = PromptTemplate(
                        input_variables=['input'],
                        template='''
                        Audio transkript je na hrvatskom jeziku. Analiziraj ga. Odgovori isključivo na hrvatskom. 
                        Tu su ti upute ''' + system_prompt + '''. Slijedi transkript:
                        <transcript>{input}</transcript>
                        '''
                    )
                    llm = OpenAI(temperature=0.0, model_name="gpt-4")
                    summary_chain = LLMChain(llm=llm, 
                                            prompt=summary_prompt
                    )
                    st.session_state.transcript_summary = summary_chain.run(input=st.session_state.transcript)

                    # Summarize Transcripts
                    insert_into_transcripts(file_name=(st.session_state.audio_file_path.split("\\")[0]),
                                            transcription=st.session_state.transcript,
                                            transcription_summary=st.session_state.transcript_summary,
                                            user_id=st.session_state.user_id)
                    

            if st.session_state.audio_file_path:
                if st.session_state.transcript:
                    st.write(st.session_state.audio_file_path.split("\\")[0]+" ~ Transkript")
                    st.markdown(bot_template.replace("{{MSG}}", st.session_state.transcript), unsafe_allow_html=True)
                if st.session_state.transcript_summary:
                    st.write(st.session_state.audio_file_path.split("\\")[0]+" ~ Analiza")
                    st.markdown(bot_template.replace("{{MSG}}", st.session_state.transcript_summary), unsafe_allow_html=True)
                
        with prev_tab:
            transcript_selection = st.selectbox(label="Select Transcript", options=get_transcript_ids_and_names())
            if st.button("Render Transcript") and transcript_selection:
                st.session_state.prev_file_path = transcript_selection
                st.session_state.prev_transcript = get_transcript_by_id(transcript_selection)
                st.session_state.prev_transcript_summary = get_summary_by_id(transcript_selection)
            if st.session_state.prev_transcript:
                st.write(str(st.session_state.prev_file_path) + " ~ Transkript")
                st.markdown(bot_template.replace("{{MSG}}", st.session_state.prev_transcript), unsafe_allow_html=True)
                st.write(str(st.session_state.prev_file_path) + " ~ Analiza")
                st.markdown(bot_template.replace("{{MSG}}", st.session_state.prev_transcript_summary), unsafe_allow_html=True)


if __name__ == "__main__":
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")
    main()
    
