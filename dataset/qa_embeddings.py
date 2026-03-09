import csv
import json
import os
from datetime import datetime
from sentence_transformers import SentenceTransformer


country_id_to_name = {}
country_name_to_id = {}
cricketers_path = 'cricketers.csv'
if os.path.exists(cricketers_path):
    with open(cricketers_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            country = row.get('Country')
            if country:
                country_name_to_id[country.strip().lower()] = None

players_info_path = 'players_info.csv'
if os.path.exists(players_info_path):
    with open(players_info_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            country_id = row.get('country_id')
            name = row.get('player_name')
            if country_id and name:
                country_id = str(float(country_id)).rstrip('.0') if country_id else None
                with open(cricketers_path, 'r', encoding='utf-8') as f2:
                    reader2 = csv.DictReader(f2)
                    for row2 in reader2:
                        if row2.get('Name') and row2.get('Name').strip().lower() == name.strip().lower():
                            country = row2.get('Country')
                            if country:
                                country_id_to_name[country_id] = country
                                country_name_to_id[country.strip().lower()] = country_id
                            break

qa_pairs = []

if os.path.exists(cricketers_path):
    with open(cricketers_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get('Name')
            country = row.get('Country')
            dob = row.get('Date_Of_Birth')
            test = row.get('Test')
            odi = row.get('ODI')
            t20 = row.get('T20')
            if name:
                if odi:
                    qa_pairs.append({
                        'question': f'How many ODIs did {name} play?',
                        'answer': f'{name} played {odi} ODIs.'
                    })
                if test:
                    qa_pairs.append({
                        'question': f'How many Test matches did {name} play?',
                        'answer': f'{name} played {test} Test matches.'
                    })
                if t20:
                    qa_pairs.append({
                        'question': f'How many T20s did {name} play?',
                        'answer': f'{name} played {t20} T20s.'
                    })
                if country:
                    qa_pairs.append({
                        'question': f'Which country does {name} represent?',
                        'answer': f'{name} represents {country}.'
                    })

                if dob:
                    try:
                        if '-' in dob:
                            dob_dt = datetime.strptime(dob, '%Y-%m-%d')
                        else:
                            dob_dt = datetime.strptime(dob, '%d/%m/%Y')
                        today = datetime.today()
                        age = today.year - dob_dt.year - ((today.month, today.day) < (dob_dt.month, dob_dt.day))
                        qa_pairs.append({
                            'question': f"What is {name}'s age?",
                            'answer': f"{name} is {age} years old."
                        })
                        qa_pairs.append({
                            'question': f"{name}'s age?",
                            'answer': f"{name} is {age} years old."
                        })
                    except Exception as e:
                        pass

odi_path = 'odi_Batting_Card.csv'
if os.path.exists(odi_path):
    with open(odi_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            team = row.get('team')
            batsman = row.get('batsman')
            runs = row.get('runs')
            match_id = row.get('Match ID')
            wicket_type = row.get('wicketType')
            is_out = row.get('isOut')
            if team and batsman and runs:
                qa_pairs.append({
                    'question': f'How many runs did batsman {batsman} score for {team}?',
                    'answer': f'Batsman {batsman} scored {runs} runs for {team}.'
                })
            if match_id and team and batsman and wicket_type and is_out == 'True':
                qa_pairs.append({
                    'question': f'Who was {wicket_type} out in match {match_id} for {team}?',
                    'answer': f'Batsman {batsman} was {wicket_type} out in match {match_id} for {team}.'
                })

if os.path.exists(players_info_path):
    with open(players_info_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get('player_name')
            batting_style = row.get('batting_style')
            bowling_style = row.get('bowling_style')
            country_id = row.get('country_id')
            country_name = None
            if country_id:
                country_id_str = str(float(country_id)).rstrip('.0')
                country_name = country_id_to_name.get(country_id_str)
            if name and batting_style:
                qa_pairs.append({
                    'question': f'What is {name}\'s batting style?',
                    'answer': f'{name} is a {batting_style}.'
                })
            if name and bowling_style:
                qa_pairs.append({
                    'question': f'What is {name}\'s bowling style?',
                    'answer': f'{name} bowls {bowling_style}.'
                })
            if name and country_name:
                qa_pairs.append({
                    'question': f'Which country does {name} play for?',
                    'answer': f'{name} plays for {country_name}.'
                })

asiacup_path = 'asiacup.csv'
if os.path.exists(asiacup_path):
    with open(asiacup_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            team = row.get('Team')
            opponent = row.get('Opponent')
            ground = row.get('Ground')
            year = row.get('Year')
            player_of_match = row.get('Player Of The Match')
            result = row.get('Result')
            if team and opponent and ground and year and player_of_match:
                qa_pairs.append({
                    'question': f'Who was the player of the match in {team} vs {opponent}, ODI, {ground}, {year}?',
                    'answer': f'{player_of_match} was the player of the match.'
                })
            if team and opponent and ground and year and result:
                qa_pairs.append({
                    'question': f'What was the result of {team} vs {opponent}, ODI, {ground}, {year}?',
                    'answer': f'{team} vs {opponent} at {ground} in {year}: {result}.'
                })

model = SentenceTransformer('all-MiniLM-L6-v2')

new_embeddings = []
for pair in qa_pairs:
    chunk = f"Q: {pair['question']}\nA: {pair['answer']}"
    embedding = model.encode(chunk).tolist()
    new_embeddings.append({
        'chunk': chunk,
        'embedding': embedding
    })

embeddings_path = 'embeddings.json'
if os.path.exists(embeddings_path):
    with open(embeddings_path, 'r', encoding='utf-8') as f:
        existing = json.load(f)
else:
    existing = []

existing.extend(new_embeddings)

with open(embeddings_path, 'w', encoding='utf-8') as f:
    json.dump(existing, f, indent=2, ensure_ascii=False)

print(f"Appended {len(new_embeddings)} new Q&A embeddings to embeddings.json.")
