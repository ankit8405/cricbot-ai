import pandas as pd
from docx import Document
from sentence_transformers import SentenceTransformer
import numpy as np
import json
import os

def load_docx(filepath):
    doc = Document(filepath)
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

def facts_from_cricketers(filepath):
    df = pd.read_csv(filepath)
    facts = []
    for _, row in df.iterrows():
        name = str(row.get('Name', '')).strip() if not pd.isna(row.get('Name', '')) else ''
        country = str(row.get('Country', '')).strip() if not pd.isna(row.get('Country', '')) else ''
        dob = str(row.get('Date_Of_Birth', '')).strip() if not pd.isna(row.get('Date_Of_Birth', '')) else ''
        if name and country:
            facts.append(f"Who is {name}? {name} is a cricketer from {country}.")
        if name and dob:
            facts.append(f"{name} was born on {dob}.")
    return facts

def facts_from_players_info(filepath):
    df = pd.read_csv(filepath)
    facts = []
    for _, row in df.iterrows():
        name = str(row.get('player_name', '')).strip() if not pd.isna(row.get('player_name', '')) else ''
        country = str(row.get('country_id', '')).strip() if not pd.isna(row.get('country_id', '')) else ''
        dob = str(row.get('dob', '')).strip() if not pd.isna(row.get('dob', '')) else ''
        bat = str(row.get('batting_style', '')).strip() if not pd.isna(row.get('batting_style', '')) else ''
        bowl = str(row.get('bowling_style', '')).strip() if not pd.isna(row.get('bowling_style', '')) else ''
        if name and dob:
            facts.append(f"{name} was born on {dob}.")
        if name and bat:
            facts.append(f"{name}'s batting style is {bat}.")
        if name and bowl:
            facts.append(f"{name}'s bowling style is {bowl}.")
    return facts

def facts_from_asiacup(filepath):
    df = pd.read_csv(filepath)
    facts = []
    for _, row in df.iterrows():
        team = str(row.get('Team', '')).strip() if not pd.isna(row.get('Team', '')) else ''
        opp = str(row.get('Opponent', '')).strip() if not pd.isna(row.get('Opponent', '')) else ''
        year = str(row.get('Year', '')).strip() if not pd.isna(row.get('Year', '')) else ''
        ground = str(row.get('Ground', '')).strip() if not pd.isna(row.get('Ground', '')) else ''
        runs = str(row.get('Run Scored', '')).strip() if not pd.isna(row.get('Run Scored', '')) else ''
        wickets = str(row.get('Wicket Lost', '')).strip() if not pd.isna(row.get('Wicket Lost', '')) else ''
        if team and opp and year:
            facts.append(f"In {year}, {team} played against {opp} at {ground}. {team} scored {runs} runs and lost {wickets} wickets.")
    return facts

def facts_from_odi_batting(filepath, n=100):
    df = pd.read_csv(filepath)
    facts = []
    for _, row in df.head(n).iterrows():
        match = str(row.get('Match ID', '')).strip() if not pd.isna(row.get('Match ID', '')) else ''
        team = str(row.get('team', '')).strip() if not pd.isna(row.get('team', '')) else ''
        batsman = str(row.get('batsman', '')).strip() if not pd.isna(row.get('batsman', '')) else ''
        runs = str(row.get('runs', '')).strip() if not pd.isna(row.get('runs', '')) else ''
        balls = str(row.get('balls', '')).strip() if not pd.isna(row.get('balls', '')) else ''
        if team and batsman:
            facts.append(f"In match {match}, {team}'s batsman {batsman} scored {runs} runs from {balls} balls.")
    return facts

def split_into_chunks(text, max_words=200):
    words = text.split()
    return [" ".join(words[i:i+max_words]) for i in range(0, len(words), max_words)]

def create_embeddings(chunks, model_name='all-MiniLM-L6-v2'):
    model = SentenceTransformer(model_name)
    embeddings = model.encode(chunks)
    return list(embeddings)

def save_embeddings(chunks, embeddings, out_file='embeddings.json'):
    data = [{"chunk": c, "embedding": e.tolist()} for c, e in zip(chunks, embeddings)]
    with open(out_file, 'w') as f:
        json.dump(data, f)

if __name__ == "__main__":
    text = load_docx("C:\\Users\\ankit\\Desktop\\projects\\chatbot\\dataset\\dataset.docx")
    chunks = split_into_chunks(text)
    chunks += facts_from_cricketers("C:\\Users\\ankit\\Desktop\\projects\\chatbot\\dataset\\cricketers.csv")
    chunks += facts_from_players_info("C:\\Users\\ankit\\Desktop\\projects\\chatbot\\dataset\\players_info.csv")
    chunks += facts_from_asiacup("C:\\Users\\ankit\\Desktop\\projects\\chatbot\\dataset\\asiacup.csv")
    chunks += facts_from_odi_batting("C:\\Users\\ankit\\Desktop\\projects\\chatbot\\dataset\\odi_Batting_Card.csv")
    embeddings = create_embeddings(chunks)
    save_embeddings(chunks, embeddings)
    print("✅ Embeddings saved to embeddings.json")