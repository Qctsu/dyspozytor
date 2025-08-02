#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import re
import csv
import os
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

class PortDataScraper:
    def __init__(self, csv_file_path: str = "port_data.csv"):
        self.url = "http://www.dyspozytor.port.szczecin.pl"
        self.csv_file = csv_file_path
        self.encoding = 'iso-8859-2'  # Na podstawie meta tagu w HTML
        
    def fetch_page_content(self) -> Optional[str]:
        """Pobiera zawartość strony"""
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
        participants_pattern = r'Uczestnicy:\s*<BR>\s*------<BR>(.*?)(?=<BR>\s*<BR>\s*PLAN\s+PRACY|$)'
        participants_match = re.search(participants_pattern, content, re.DOTALL | re.IGNORECASE)
        
        if participants_match:
            participants_text = participants_match.group(1)
            # Wyciąg linii z uczestnikami (format: NAZWA - status)
            lines = re.findall(r'([A-Z0-9\.\s]+?)\s*-\s*([^<]*?)(?:<BR>|$)', participants_text)
            
            for name, status in lines:
                name = name.strip()
                status = status.strip()
                if name and name not in ['', '-', 'HD', 'Główny Dysp.Portu']:
                    participants.append({
                        'typ': 'Uczestnik',
                        'nazwa': name,
                        'status': status if status != '---' else 'Brak danych'
                    })
        
        return participants
    
    def parse_work_plan_section(self, section_text: str, plan_date: str) -> List[Dict[str, str]]:
        """Parsuje sekcję planu pracy"""
        records = []
        current_terminal = ""
        
        # Podział na linie
        lines = section_text.split('<BR>')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Sprawdź czy to nazwa terminalu/sekcji
            if any(keyword in line.upper() for keyword in [
                'DB PORT SZCZECIN', 'TERMINAL', 'FAST TERMINALS', 
                'VITERRA', 'BULK CARGO', 'GENERAL CARGO', 'BUNGE',
                'PKN ORLEN', 'BALTCHEM', 'EUROTERMINAL', 'PORT NOWE',
                'PORT TRZEBIE', 'PORT STEPNICA', 'PORT POLICE',
                'ALFA TERMINAL', 'CEMEX', 'FOSFAN', 'ANDREAS',
                'MARITIM SHIPYARD', 'SHIP SERVICE', 'PORT RYBACKI',
                'BALTIC STEVEDORING', 'ELEWATOR', 'ORLEN GAZ',
                'MORSKA STOCZNIA', 'STOCZNIA REMONTOWA'
            ]):
                current_terminal = re.sub(r'<[^>]*>', '', line).strip()
                continue
            
            # Sprawdź czy to informacja o braku prac
            if 'prace nieplanowane' in line.lower() or 'brak statków' in line.lower():
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
                    'uwagi': 'Prace nieplanowane' if 'nieplanowane' in line.lower() else 'Brak statków'
                })
                continue
            
            # Parsuj linię z danymi statku (uproszczona wersja)
            # Format: Nabrz Agent Statek Towar Ton Relacja Sped I II III
            parts = re.split(r'\s{2,}', line)  # Dziel po 2+ spacjach
            
            if len(parts) >= 3:  # Minimalne wymagania dla rekordu
                record = {
                    'data_planu': plan_date,
                    'terminal': current_terminal,
                    'nabrze': parts[0] if len(parts) > 0 else '',
                    'agent': parts[1] if len(parts) > 1 else '',
                    'statek': parts[2] if len(parts) > 2 else '',
                    'towar': parts[3] if len(parts) > 3 else '',
                    'ton': parts[4] if len(parts) > 4 else '',
                    'relacja': parts[5] if len(parts) > 5 else '',
                    'sped': parts[6] if len(parts) > 6 else '',
                    'zmiana_i': parts[7] if len(parts) > 7 else '',
                    'zmiana_ii': parts[8] if len(parts) > 8 else '',
                    'zmiana_iii': parts[9] if len(parts) > 9 else '',
                    'uwagi': ''
                }
                
                # Usuń tagi HTML z wszystkich pól
                for key, value in record.items():
                    if isinstance(value, str):
                        record[key] = re.sub(r'<[^>]*>', '', value).strip()
                
                records.append(record)
        
        return records
    
    def extract_work_plans(self, content: str) -> List[Dict[str, str]]:
        """Wyciąga plany pracy dla wszystkich dat"""
        all_records = []
        
        # Znajdź wszystkie sekcje planów pracy
        plan_sections = re.findall(
            r'PLAN\s+PRACY\s+DOBOWO-ZMIANOWY\s+NA\s+DZIEŃ\s+(\d{2}-\d{2}-\d{4})[^<]*?<BR>(.*?)(?=PLAN\s+PRACY\s+DOBOWO-ZMIANOWY|STAN\s+WODY|$)',
            content, 
            re.DOTALL | re.IGNORECASE
        )
        
        for plan_date, section_content in plan_sections:
            records = self.parse_work_plan_section(section_content, plan_date)
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
        work_plans = self.extract_work_plans(content)
        
        print(f"Znaleziono {len(participants)} uczestników")
        print(f"Znaleziono {len(work_plans)} rekordów planów pracy")
        
        # Zapisz do CSV
        self.save_to_csv(conference_date, participants, work_plans)

if __name__ == "__main__":
    scraper = PortDataScraper("port_data.csv")
    scraper.run()