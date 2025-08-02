#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

import requests
import re
import os
from typing import Dict, List, Optional, Set
import pandas as pd

class PortDataScraper:
    def __init__(self, csv_file_path: str = "port_data.csv", source: Optional[str] = None):
        self.url = source or "http://www.dyspozytor.port.szczecin.pl"
        self.csv_file = csv_file_path
        self.encoding = 'iso-8859-2'  # Na podstawie meta tagu w HTML
        
    def fetch_page_content(self) -> Optional[str]:
        """Pobiera zawartość strony"""
        # Pozwala na użycie lokalnego pliku HTML do testów
        if os.path.isfile(self.url):
            with open(self.url, encoding=self.encoding) as f:
                return f.read()

        try:
            response = requests.get(self.url, timeout=30)
            response.encoding = self.encoding
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Błąd podczas pobierania strony: {e}")
            return None
    
    def extract_conference_date(self, content: str) -> Optional[str]:
        """Wyciąga datę konferencji dyspozytorskiej"""
        pattern = r'konferencji\s+dyspozytorskiej\s+z\s+dnia\s+(\d{2}-\d{2}-\d{4})'
        match = re.search(pattern, content, re.IGNORECASE)
        return match.group(1) if match else None
    
    def extract_work_plan_dates(self, content: str) -> List[str]:
        """Wyciąga daty planów pracy dobowo-zmianowych"""
        pattern = r'PLAN\s+PRACY\s+DOBOWO-ZMIANOWY\s+NA\s+DZIEŃ\s+(\d{2}-\d{2}-\d{4})'
        matches = re.findall(pattern, content, re.IGNORECASE)
        return matches
    
    def extract_participants(self, content: str) -> List[Dict[str, str]]:
        """Wyciąga listę uczestników"""
        participants = []
        
        # Znajdź sekcję z uczestnikami
        participants_pattern = r'Uczestnicy:\s*<BR>\s*------<BR>(.*?)(?:<BR>\s*<BR>|PLAN\s+PRACY|$)'
        participants_match = re.search(participants_pattern, content, re.DOTALL | re.IGNORECASE)

        if not participants_match:
            return participants

        participants_text = participants_match.group(1)

        # Każda linia może zawierać dwóch uczestników w formacie "NAZWA - status"
        name_status_pattern = r'([A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż0-9\. ]+?)\s*-\s*(.*?)(?=\s{2,}[A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż0-9\. ]+\s*-|$)'

        for raw_line in participants_text.split('<BR>'):
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            pairs = re.findall(name_status_pattern, raw_line)
            for name, status in pairs:
                name = name.strip()
                status = status.strip() or 'Brak danych'
                if name and name not in ['', '-', 'HD', 'Główny Dysp.Portu']:
                    participants.append({
                        'typ': 'Uczestnik',
                        'nazwa': name,
                        'status': 'Brak danych' if status == '---' else status
                    })

        return participants
    
    def parse_work_plan_section(self, section_text: str, plan_date: str, agents: Set[str]) -> List[Dict[str, str]]:
        """Parsuje sekcję planu pracy"""
        records: List[Dict[str, str]] = []
        current_terminal = ""
        current_record: Optional[Dict[str, str]] = None
        last_agent = ""
        agent_regex = re.compile(r'\b(' + '|'.join(sorted(map(re.escape, agents), key=len, reverse=True)) + r')\b') if agents else None

        # Podział na linie
        lines = section_text.split('<BR>')

        for raw_line in lines:
            line = re.sub(r'<[^>]*>', '', raw_line).replace('\xa0', ' ').strip()
            if not line or re.match(r'^-+$', line):
                continue

            upper_line = line.upper()

            # Nazwa terminalu/sekcji
            if any(keyword in upper_line for keyword in [
                'DB PORT SZCZECIN', 'TERMINAL', 'FAST TERMINALS',
                'VITERRA', 'BULK CARGO', 'GENERAL CARGO', 'BUNGE',
                'PKN ORLEN', 'BALTCHEM', 'EUROTERMINAL', 'PORT NOWE',
                'PORT TRZEBIE', 'PORT STEPNICA', 'PORT POLICE',
                'ALFA TERMINAL', 'CEMEX', 'FOSFAN', 'ANDREAS',
                'MARITIM SHIPYARD', 'SHIP SERVICE', 'PORT RYBACKI',
                'BALTIC STEVEDORING', 'ELEWATOR', 'ORLEN GAZ',
                'MORSKA STOCZNIA', 'STOCZNIA REMONTOWA'
            ]):
                current_terminal = line
                current_record = None
                last_agent = ""
                continue

            # Pomijaj wiersze nagłówkowe
            if 'NABRZ' in upper_line and 'AGENT' in upper_line:
                continue

            # Informacja o braku prac
            if 'PRACE NIEPLANOWANE' in upper_line or 'BRAK STATK' in upper_line:
                records.append({
                    'data_planu': plan_date,
                    'terminal': current_terminal,
                    'nabrze': '',
                    'agent': '',
                    'statek': '',
                    'towar': '',
                    'ton': '',
                    'relacja': '',
                    'sped': '',
                    'zmiana_i': '',
                    'zmiana_ii': '',
                    'zmiana_iii': '',
                    'uwagi': 'Prace nieplanowane' if 'NIEPLANOWANE' in upper_line else 'Brak statków'
                })
                current_record = None
                last_agent = ""
                continue

            # Parsowanie danych statku
            if not line:
                continue

            match = agent_regex.search(line) if agent_regex else None
            if match:
                nabrze = line[:match.start()].strip()
                agent = match.group(1)
                rest_line = line[match.end():]
                last_agent = agent
            else:
                parts = re.split(r'\s{2,}', line, maxsplit=1)
                nabrze = parts[0].strip()
                rest_line = parts[1] if len(parts) > 1 else ''
                agent = last_agent

            ton_regex = re.compile(r'\d+\s*(?:[a-z]{1,3}-[a-z]{1,3}|wag|sam)')
            ton_match = ton_regex.search(rest_line)
            if ton_match:
                before_ton = rest_line[:ton_match.start()].rstrip()
                after_ton = rest_line[ton_match.start():].strip()
            else:
                before_ton = rest_line.strip()
                after_ton = ''

            # statek i towar
            statek = ''
            towar = ''
            if before_ton:
                statek_towar = [p for p in re.split(r'\s{2,}', before_ton) if p]
                if len(statek_towar) >= 2:
                    statek = statek_towar[0].strip()
                    towar = statek_towar[1].strip()
                elif statek_towar:
                    tokens = statek_towar[0].split()
                    if agent and len(tokens) > 2:
                        statek = ' '.join(tokens[:-2])
                        towar = ' '.join(tokens[-2:])
                    elif agent and len(tokens) == 2:
                        statek, towar = tokens
                    elif not agent and len(tokens) > 1:
                        statek = tokens[0]
                        towar = ' '.join(tokens[1:])
                    else:
                        statek = statek_towar[0].strip()

            after_parts = re.split(r'\s{2,}', after_ton)
            ton = after_parts[0].strip() if after_parts else ''
            remainder = [p.strip() for p in after_parts[1:]]

            relacja = remainder[0] if len(remainder) > 0 else ''
            sped = remainder[1] if len(remainder) > 1 else ''
            zmiana_i = remainder[2] if len(remainder) > 2 else ''
            zmiana_ii = remainder[3] if len(remainder) > 3 else ''
            zmiana_iii = remainder[4] if len(remainder) > 4 else ''
            uwagi = ' '.join(remainder[5:]) if len(remainder) > 5 else ''

            if any([statek, towar, ton, relacja, sped, zmiana_i, zmiana_ii, zmiana_iii, uwagi]):
                record = {
                    'data_planu': plan_date,
                    'terminal': current_terminal,
                    'nabrze': nabrze,
                    'agent': agent,
                    'statek': statek,
                    'towar': towar,
                    'ton': ton,
                    'relacja': relacja,
                    'sped': sped,
                    'zmiana_i': zmiana_i,
                    'zmiana_ii': zmiana_ii,
                    'zmiana_iii': zmiana_iii,
                    'uwagi': uwagi
                }

                # Jeżeli kolumna sped zawiera tekst z małymi literami, potraktuj ją jako uwagi
                if re.search(r'[a-z]', record['sped']):
                    record['uwagi'] = ' '.join(filter(None, [record['sped'], record['uwagi']])).strip()
                    record['sped'] = ''

                # Normalizuj spacje
                for key, value in record.items():
                    if isinstance(value, str):
                        record[key] = ' '.join(value.split())

                records.append(record)
                current_record = record
                if agent:
                    last_agent = agent
            elif current_record:
                # Kontynuacja uwag z poprzedniego rekordu
                extra = ' '.join(line.split())
                current_record['uwagi'] = ' '.join(filter(None, [current_record.get('uwagi'), extra]))

        return records
    
    def extract_work_plans(self, content: str, agents: Set[str]) -> List[Dict[str, str]]:
        """Wyciąga plany pracy dla wszystkich dat"""
        all_records = []

        # Znajdź wszystkie sekcje planów pracy
        plan_sections = re.findall(
            r'PLAN\s+PRACY\s+DOBOWO-ZMIANOWY\s+NA\s+DZIEŃ\s+(\d{2}-\d{2}-\d{4})[^<]*?<BR>(.*?)(?=PLAN\s+PRACY\s+DOBOWO-ZMIANOWY|STAN\s+WODY|$)',
            content,
            re.DOTALL | re.IGNORECASE
        )

        for plan_date, section_content in plan_sections:
            records = self.parse_work_plan_section(section_content, plan_date, agents)
            all_records.extend(records)

        return all_records
    
    def data_exists(self, conference_date: str, work_plan_dates: List[str]) -> bool:
        """Sprawdza czy dane już istnieją w CSV"""
        if not os.path.exists(self.csv_file):
            return False
        
        try:
            df = pd.read_csv(self.csv_file)
            
            # Sprawdź datę konferencji
            conference_exists = 'data_konferencji' in df.columns and conference_date in df['data_konferencji'].values
            
            # Sprawdź daty planów pracy
            plans_exist = True
            if 'data_planu' in df.columns:
                for date in work_plan_dates:
                    if date not in df['data_planu'].values:
                        plans_exist = False
                        break
            else:
                plans_exist = False
            
            return conference_exists and plans_exist
            
        except Exception as e:
            print(f"Błąd podczas sprawdzania istniejących danych: {e}")
            return False
    
    def save_to_csv(self, conference_date: str, participants: List[Dict], work_plans: List[Dict]):
        """Zapisuje dane do CSV"""
        all_data = []
        
        # Dodaj uczestników
        for participant in participants:
            all_data.append({
                'data_konferencji': conference_date,
                'data_planu': '',
                'typ': participant['typ'],
                'nazwa': participant['nazwa'],
                'status': participant['status'],
                'terminal': '',
                'nabrze': '',
                'agent': '',
                'statek': '',
                'towar': '',
                'ton': '',
                'relacja': '',
                'sped': '',
                'zmiana_i': '',
                'zmiana_ii': '',
                'zmiana_iii': '',
                'uwagi': ''
            })
        
        # Dodaj plany pracy
        for plan in work_plans:
            plan_record = {
                'data_konferencji': conference_date,
                'typ': 'Plan pracy',
                'nazwa': '',
                'status': '',
                **plan
            }
            all_data.append(plan_record)
        
        # Zapisz do CSV
        if all_data:
            df = pd.DataFrame(all_data)
            
            # Jeśli plik istnieje, dodaj nowe dane
            if os.path.exists(self.csv_file):
                existing_df = pd.read_csv(self.csv_file)
                df = pd.concat([existing_df, df], ignore_index=True)
                # Usuń duplikaty
                df = df.drop_duplicates()
            
            df.to_csv(self.csv_file, index=False, encoding='utf-8-sig')
            print(f"Dane zapisane do: {self.csv_file}")
        else:
            print("Brak danych do zapisania")
    
    def run(self):
        """Główna funkcja uruchamiająca scraper"""
        print("Pobieranie danych ze strony portu...")
        
        content = self.fetch_page_content()
        if not content:
            return
        
        # Wyciągnij daty
        conference_date = self.extract_conference_date(content)
        work_plan_dates = self.extract_work_plan_dates(content)
        
        if not conference_date:
            print("Nie znaleziono daty konferencji dyspozytorskiej")
            return
            
        print(f"Data konferencji: {conference_date}")
        print(f"Daty planów pracy: {work_plan_dates}")
        
        # Sprawdź czy dane już istnieją
        if self.data_exists(conference_date, work_plan_dates):
            print("Dane dla tych dat już istnieją w pliku CSV. Pomijam pobieranie.")
            return
        
        # Wyciągnij dane
        participants = self.extract_participants(content)
        agents = {p['nazwa'] for p in participants}
        work_plans = self.extract_work_plans(content, agents)
        
        print(f"Znaleziono {len(participants)} uczestników")
        print(f"Znaleziono {len(work_plans)} rekordów planów pracy")
        
        # Zapisz do CSV
        self.save_to_csv(conference_date, participants, work_plans)

if __name__ == "__main__":
    import sys

    source = sys.argv[1] if len(sys.argv) > 1 else None
    scraper = PortDataScraper("port_data.csv", source=source)
    scraper.run()
