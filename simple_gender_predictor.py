#!/usr/bin/env python3
"""
Simple gender predictor using basic name patterns and built-in dataset
"""

import pandas as pd
import re

class SimpleGenderPredictor:
    """Gender predictor using name patterns and CSV dataset"""
    
    def __init__(self, csv_file="names_to_train.csv"):
        """Initialize with name-based gender predictor"""
        self.name_gender_map = {}
        self.load_training_data(csv_file)
        
        self.male_endings = ['son', 'man', 'boy', 'dad', 'father']
        self.female_endings = ['daughter', 'woman', 'girl', 'mom', 'mother']
        
        self.male_patterns = ['john', 'michael', 'david', 'james', 'robert', 'william', 'richard', 'thomas', 'daniel', 'matthew']
        self.female_patterns = ['mary', 'patricia', 'jennifer', 'linda', 'elizabeth', 'barbara', 'susan', 'jessica', 'sarah', 'karen']
    
    def load_training_data(self, csv_file):
        """Load name-gender mappings from CSV file"""
        try:
            df = pd.read_csv(csv_file)
            for _, row in df.iterrows():
                name = row['Names'].lower().strip()
                gender = 'male' if row['Labels'] == 1 else 'female'
                self.name_gender_map[name] = gender
        except Exception as e:
            print(f"Could not load {csv_file}: {e}")
    
    def predict_gender(self, name):
        """Predict gender using rules and name database"""
        if not name or not isinstance(name, str):
            return "unknown"
        
        name_clean = name.lower().strip()
        
        if name_clean in self.name_gender_map:
            return self.name_gender_map[name_clean]
        
        for male_name in self.male_patterns:
            if male_name in name_clean:
                return "male"
        
        for female_name in self.female_patterns:
            if female_name in name_clean:
                return "female"
        
        for ending in self.male_endings:
            if name_clean.endswith(ending):
                return "male"
        
        for ending in self.female_endings:
            if name_clean.endswith(ending):
                return "female"
        
        if any(char in name_clean for char in ['a', 'e', 'i']) and name_clean.endswith('a'):
            return "female"
        
        if name_clean.endswith(('d', 'n', 'r', 't', 's')):
            return "male"
        
        return "unknown"
    
    def predict_with_confidence(self, name):
        """Predict gender with confidence score"""
        gender = self.predict_gender(name)
        
        if gender == "unknown":
            return gender, 0.0
        
        name_clean = name.lower().strip()
        
        if name_clean in self.name_gender_map:
            return gender, 0.85
        
        return gender, 0.65

# Global instance
simple_gender_predictor = SimpleGenderPredictor() 