import pandas as pd
import re
from neo4j import GraphDatabase
from datetime import datetime

class RelationshipManager:
    """Manages user relationships and stores them in Neo4j database"""
    
    def __init__(self, neo4j_uri="bolt://localhost:7687", neo4j_user="neo4j", neo4j_password="12345678"):
        """Initialize the relationship manager with Neo4j connection"""
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.load_relationship_types()
        
        self.relationship_patterns = {
            # Parents - Western & Eastern
            'father': ['father', 'dad', 'daddy', 'papa', 'pop', 'pops', 'pa', 'dada', 'baba', 'abbu', 'abu', 'pitaji', 'pita', 'walid'],
            'mother': ['mother', 'mom', 'mommy', 'mama', 'ma', 'maa', 'mummy', 'ammi', 'amma', 'mataji', 'mata', 'walida'],
            'parent': ['parent', 'guardian'],
            
            # Siblings - Western & Eastern
            'brother': ['brother', 'bro', 'bhai', 'anna', 'hyung', 'oppa', 'aniki', 'ge'],
            'elder_brother': ['elder brother', 'older brother', 'big brother', 'dada', 'bada bhai', 'hyung', 'oppa', 'anna'],
            'younger_brother': ['younger brother', 'little brother', 'chota bhai', 'younger bro'],
            'sister': ['sister', 'sis', 'behan', 'didi', 'akka', 'noona', 'unni', 'ane', 'jie'],
            'elder_sister': ['elder sister', 'older sister', 'big sister', 'didi', 'badi behan', 'noona', 'unni', 'akka'],
            'younger_sister': ['younger sister', 'little sister', 'choti behan', 'younger sis'],
            'sibling': ['sibling', 'sib'],
            
            # Children
            'son': ['son', 'boy', 'beta', 'ladka', 'putra'],
            'daughter': ['daughter', 'girl', 'beti', 'ladki', 'putri'],
            'child': ['child', 'kid', 'bachcha', 'baccha'],
            
            # Spouse - Western & Eastern
            'husband': ['husband', 'hubby', 'spouse', 'pati', 'khasam', 'zawj'],
            'wife': ['wife', 'wifey', 'spouse', 'patni', 'biwi', 'zawja'],
            'partner': ['partner', 'significant other', 'better half'],
            
            # Grandparents - Western & Eastern
            'grandfather': ['grandfather', 'grandpa', 'granddad', 'gramps', 'nana', 'dada', 'ajoba', 'thatha', 'dadu'],
            'grandmother': ['grandmother', 'grandma', 'granny', 'nani', 'dadi', 'ajji', 'paati', 'dida'],
            'grandparent': ['grandparent'],
            
            # Grandchildren
            'grandson': ['grandson'],
            'granddaughter': ['granddaughter'],
            'grandchild': ['grandchild'],
            
            # Aunts & Uncles - Western & Eastern
            'uncle': ['uncle', 'chacha', 'mama', 'tau', 'fufa', 'mamu', 'kaka', 'chittappa', 'periappa'],
            'aunt': ['aunt', 'aunty', 'auntie', 'chachi', 'mami', 'tayi', 'buaji', 'mausi', 'kaki', 'chithi', 'perima'],
            'pibling': ['pibling', 'parent sibling'],  # Gender-neutral parent's sibling
            
            # Nieces & Nephews
            'nephew': ['nephew', 'bhatija', 'bhanja'],
            'niece': ['niece', 'bhatiji', 'bhanji'],
            'nibling': ['nibling', 'sibling child'],  # Gender-neutral sibling's child
            
            # Cousins - Western & Eastern
            'cousin': ['cousin', 'cuz', 'cousin brother', 'cousin sister'],
            
            # In-laws - Western & Eastern
            'father_in_law': ['father in law', 'father-in-law', 'sasur', 'saasu'],
            'mother_in_law': ['mother in law', 'mother-in-law', 'saas', 'atte'],
            'brother_in_law': ['brother in law', 'brother-in-law', 'sala', 'jija', 'devar', 'jeth'],
            'sister_in_law': ['sister in law', 'sister-in-law', 'sali', 'bhabhi', 'devrani', 'jethani'],
            'son_in_law': ['son in law', 'son-in-law', 'jamai', 'damad'],
            'daughter_in_law': ['daughter in law', 'daughter-in-law', 'bahu', 'bouma'],
            
            # Step Relations
            'stepfather': ['stepfather', 'step father', 'step dad'],
            'stepmother': ['stepmother', 'step mother', 'step mom'],
            'stepbrother': ['stepbrother', 'step brother'],
            'stepsister': ['stepsister', 'step sister'],
            'stepson': ['stepson', 'step son'],
            'stepdaughter': ['stepdaughter', 'step daughter'],
            
            # Half Relations
            'half_brother': ['half brother', 'half-brother'],
            'half_sister': ['half sister', 'half-sister'],
            
            # Great Relations
            'great_grandfather': ['great grandfather', 'great-grandfather', 'great grandpa', 'pardada'],
            'great_grandmother': ['great grandmother', 'great-grandmother', 'great grandma', 'pardadi'],
            'great_uncle': ['great uncle', 'great-uncle', 'grand uncle'],
            'great_aunt': ['great aunt', 'great-aunt', 'grand aunt'],
            
            # Friends & Social
            'friend': ['friend', 'buddy', 'pal', 'mate', 'dost', 'yaar', 'sakha'],
            'best_friend': ['best friend', 'bestie', 'bff', 'best buddy'],
            'boyfriend': ['boyfriend', 'bf'],
            'girlfriend': ['girlfriend', 'gf'],
            'fiance': ['fiance', 'fiancé', 'fiancée', 'engaged'],
            
            # Professional
            'colleague': ['colleague', 'coworker', 'workmate'],
            'boss': ['boss', 'manager', 'supervisor', 'chief', 'head'],
            'employee': ['employee', 'worker', 'staff', 'subordinate'],
            'teacher': ['teacher', 'instructor', 'professor', 'guru', 'ustad', 'sensei'],
            'student': ['student', 'pupil', 'learner', 'shishya', 'chela'],
            'mentor': ['mentor', 'guide', 'advisor'],
            'mentee': ['mentee', 'protege', 'apprentice'],
            
            # Neighbors & Community
            'neighbor': ['neighbor', 'neighbour', 'padosi'],
            'roommate': ['roommate', 'flatmate', 'housemate'],
            'landlord': ['landlord', 'owner', 'malik'],
            'tenant': ['tenant', 'renter'],
            
            # Godparents & Spiritual
            'godfather': ['godfather', 'godparent'],
            'godmother': ['godmother', 'godparent'],
            'godson': ['godson', 'godchild'],
            'goddaughter': ['goddaughter', 'godchild'],
            
            # Modern/Alternative Family
            'adoptive_father': ['adoptive father', 'adopted father'],
            'adoptive_mother': ['adoptive mother', 'adopted mother'],
            'foster_father': ['foster father'],
            'foster_mother': ['foster mother'],
            'foster_child': ['foster child'],
            
            # Pets (often considered family)
            'pet': ['pet', 'dog', 'cat', 'puppy', 'kitten']
        }
        
        self.invalid_names = {
            'who', 'what', 'where', 'when', 'why', 'how',
            'is', 'was', 'are', 'were', 'be', 'been',
            'this', 'that', 'these', 'those',
            'he', 'she', 'it', 'they', 'them',
            'name', 'person', 'someone', 'anybody', 'nobody',
            'the', 'a', 'an', 'any', 'some', 'many',
            'yes', 'no', 'maybe', 'ok', 'okay'
        }
    
    def load_relationship_types(self):
        """Load relationship types from CSV file"""
        try:
            df = pd.read_csv("Relations_set.csv", header=None)
            self.valid_relationships = [rel.strip().lower() for rel in df[0].tolist()]
        except Exception as e:
            print(f"Warning: Could not load Relations_set.csv: {e}")
            self.valid_relationships = ['father', 'mother', 'brother', 'sister', 'friend', 'colleague']

    def get_user_signup_name(self, username):
        """Get the user's original signup name from Neo4j"""
        with self.driver.session() as session:
            try:
                query = "MATCH (u:User {name: $username}) RETURN u.name as signup_name"
                result = session.run(query, username=username).single()
                return result['signup_name'] if result else None
            except:
                return None

    def detect_name_claims(self, text):
        """Detect if user is claiming a name"""
        text_lower = text.lower()
        name_patterns = [
            r"my name is ([a-zA-Z\s]+?)(?:\.|$|,|\?|!)",
            r"i am ([a-zA-Z\s]+?)(?:\.|$|,|\?|!)",
            r"call me ([a-zA-Z\s]+?)(?:\.|$|,|\?|!)",
            r"i'm ([a-zA-Z\s]+?)(?:\.|$|,|\?|!)"
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text_lower)
            if match:
                claimed_name = match.group(1).strip().title()
                if self.is_valid_name(claimed_name):
                    return claimed_name
        return None

    def validate_name_claim(self, claimed_name, username):
        """Validate if the claimed name matches the signup name"""
        signup_name = self.get_user_signup_name(username)
        if signup_name and claimed_name.lower() != signup_name.lower():
            return False, f"I know your name is {signup_name}, you are lying."
        return True, None
    
    def detect_relationships(self, text):
        """Detect relationships from text input using pattern matching"""
        relationships_found = []
        text_lower = text.lower()
        
        for rel_type, patterns in self.relationship_patterns.items():
            for pattern in patterns:
                # Pattern: "my father is John"
                match1 = re.search(rf"my {pattern} is ([a-zA-Z\s]+?)(?:\.|$|,|\?|!)", text_lower)
                if match1:
                    name = match1.group(1).strip().title()
                    if self.is_valid_name(name):
                        relationships_found.append((rel_type, name))
                    continue
                
                # Pattern: "my father name is John" or "my father's name is John"
                match2 = re.search(rf"my {pattern}(?:'s)? name is ([a-zA-Z\s]+?)(?:\.|$|,|\?|!)", text_lower)
                if match2:
                    name = match2.group(1).strip().title()
                    if self.is_valid_name(name):
                        relationships_found.append((rel_type, name))
                    continue
                
                # Pattern: "[Name] is my [relationship]"
                match3 = re.search(rf"([a-zA-Z\s]+?) is my {pattern}", text_lower)
                if match3:
                    name = match3.group(1).strip().title()
                    if self.is_valid_name(name):
                        relationships_found.append((rel_type, name))
                    continue
                
                # Pattern: "my father John"
                match4 = re.search(rf"my {pattern} ([a-zA-Z\s]+?)(?:\.|$|,|\?|!|\s+is\s|\s+was\s)", text_lower)
                if match4:
                    name = match4.group(1).strip().title()
                    if self.is_valid_name(name):
                        relationships_found.append((rel_type, name))
        
        return relationships_found
    

    

    


    def detect_user_age(self, text):
        """Detect user's own age"""
        text_lower = text.lower()
        
        # Patterns for user age
        user_age_patterns = [
            r"my age is (\d+)",
            r"i am (\d+) years? old",
            r"i'm (\d+) years? old"
        ]
        
        for pattern in user_age_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return int(match.group(1))
        
        return None
    
    def update_user_age(self, user_name, age):
        """Update user's age in Neo4j"""
        with self.driver.session() as session:
            try:
                query = """
                MATCH (u:User {name: $user_name})
                SET u.age = $age, u.updated_at = $timestamp
                RETURN u.name
                """
                session.run(query, 
                    user_name=user_name,
                    age=age,
                    timestamp=datetime.now().isoformat())
                return True
            except Exception as e:
                print(f"Error updating user age: {e}")
                return False
    
    def get_person_age(self, user_name, person_name):
        """Get age of a specific person or user"""
        with self.driver.session() as session:
            try:
                # Check if asking for user's own age
                if person_name.lower() in [user_name.lower(), 'me', 'myself'] or person_name == user_name:
                    query = "MATCH (u:User {name: $user_name}) RETURN u.age as age"
                    result = session.run(query, user_name=user_name).single()
                else:
                    # Check for person's age
                    query = """
                    MATCH (u:User {name: $user_name})-[r]->(p:Person {name: $person_name, user: $user_name})
                    RETURN p.age as age
                    """
                    result = session.run(query, user_name=user_name, person_name=person_name).single()
                
                return result['age'] if result and result['age'] is not None else None
            except Exception as e:
                print(f"Error getting age for {person_name}: {e}")
                return None
    
    def detect_person_age_information(self, text):
        """Detect age information for specific person names"""
        text_lower = text.lower()
        age_info = []
        
        # Pattern: "[Name] age is [number]" or "[Name]'s age is [number]"
        age_patterns = [
            r"([a-zA-Z\s]+?)(?:'s)? age is (\d+)",
            r"([a-zA-Z\s]+?) is (\d+) years? old",
            r"age of ([a-zA-Z\s]+?) is (\d+)"
        ]
        
        for pattern in age_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                person_name = match.group(1).strip().title()
                age = int(match.group(2))
                if self.is_valid_name(person_name):
                    age_info.append((person_name, age))
        
        return age_info
    
    def validate_person_age(self, user_name, person_name, age):
        """Validate age based on relationship constraints"""
        try:
            # Get user's age first
            user_age = self.get_user_age(user_name)
            if not user_age:
                return True, None  # No validation if user age not set
            
            # Get person's relationship with user
            relationship = self.get_person_relationship(user_name, person_name)
            if not relationship:
                return True, None  # No validation if relationship not found
            
            rel_type = relationship.lower()
            
            # Get appropriate greeting based on user's gender
            try:
                from simple_gender_predictor import simple_gender_predictor as gender_predictor
                predicted_gender = gender_predictor.predict_gender(user_name)
                greeting = "Ma'am" if predicted_gender == 'female' else "Sir"
            except:
                greeting = "Sir"  # Default fallback
            
            # Age restriction rules
            if rel_type in ['father', 'dad', 'papa']:
                if age < user_age + 18:
                    return False, f"{greeting}, you're telling me a fake age. Your {rel_type} must be at least 18 years older than you."
            
            elif rel_type in ['mother', 'mom', 'mama']:
                if age < user_age + 18:
                    return False, f"{greeting}, you're telling me a fake age. Your {rel_type} must be at least 18 years older than you."
            
            elif rel_type in ['elder_brother', 'elder brother', 'big brother']:
                if age <= user_age:
                    return False, f"{greeting}, you're telling me a fake age. Your elder brother must be older than you."
            
            elif rel_type in ['elder_sister', 'elder sister', 'big sister']:
                if age <= user_age:
                    return False, f"{greeting}, you're telling me a fake age. Your elder sister must be older than you."
            
            elif rel_type in ['younger_brother', 'younger brother', 'little brother']:
                if age >= user_age:
                    return False, f"{greeting}, you're telling me a fake age. Your younger brother must be younger than you."
            
            elif rel_type in ['younger_sister', 'younger sister', 'little sister']:
                if age >= user_age:
                    return False, f"{greeting}, you're telling me a fake age. Your younger sister must be younger than you."
            
            elif rel_type in ['son']:
                if age >= user_age - 12:  # Minimum 12 year gap
                    return False, f"{greeting}, you're telling me a fake age. Your son must be significantly younger than you."
            
            elif rel_type in ['daughter']:
                if age >= user_age - 12:  # Minimum 12 year gap
                    return False, f"{greeting}, you're telling me a fake age. Your daughter must be significantly younger than you."
            
            elif rel_type in ['grandfather', 'grandpa']:
                if age < user_age + 40:  # Minimum 40 year gap
                    return False, f"{greeting}, you're telling me a fake age. Your grandfather must be much older than you."
            
            elif rel_type in ['grandmother', 'grandma']:
                if age < user_age + 40:  # Minimum 40 year gap
                    return False, f"{greeting}, you're telling me a fake age. Your grandmother must be much older than you."
            
            return True, None
            
        except Exception as e:
            print(f"Error validating age: {e}")
            return True, None  # Allow if validation fails
    
    def get_user_age(self, user_name):
        """Get user's age from Neo4j"""
        with self.driver.session() as session:
            try:
                query = "MATCH (u:User {name: $user_name}) RETURN u.age as age"
                result = session.run(query, user_name=user_name).single()
                return result['age'] if result and result['age'] is not None else None
            except Exception as e:
                print(f"Error getting user age: {e}")
                return None
    
    def get_person_relationship(self, user_name, person_name):
        """Get relationship type for a specific person"""
        with self.driver.session() as session:
            try:
                query = """
                MATCH (u:User {name: $user_name})-[r]->(p:Person {name: $person_name, user: $user_name})
                RETURN p.relation as relationship
                LIMIT 1
                """
                result = session.run(query, user_name=user_name, person_name=person_name).single()
                return result['relationship'] if result else None
            except Exception as e:
                print(f"Error getting person relationship: {e}")
                return None
    
    def update_specific_person_age(self, user_name, person_name, age):
        """Update age for a specific person by name"""
        with self.driver.session() as session:
            try:
                query = """
                MATCH (u:User {name: $user_name})-[r]->(p:Person {name: $person_name, user: $user_name})
                SET p.age = $age, p.updated_at = $timestamp
                RETURN p.name as person_name
                """
                result = session.run(query, 
                    user_name=user_name,
                    person_name=person_name,
                    age=age,
                    timestamp=datetime.now().isoformat()).single()
                return result is not None
            except Exception as e:
                print(f"Error updating age for {person_name}: {e}")
                return False
    
    def is_valid_name(self, name):
        """Check if a name is valid for storage"""
        name_lower = name.lower()
        
        if name_lower in self.invalid_names or len(name_lower) < 2:
            return False
            
        if not all(c.isalpha() or c.isspace() for c in name):
            return False
            
        if len(name_lower.split()) == 1 and name_lower in self.invalid_names:
            return False
            
        return True
    
    def create_person_node(self, name, user_name, relationship_type, properties=None):
        """Create a person node in Neo4j with all required attributes"""
        if properties is None:
            properties = {}
        
        # Determine gender based on relationship type
        gender_mapping = {
            # Male relationships
            'father': 'male', 'son': 'male', 'brother': 'male', 'elder_brother': 'male', 'younger_brother': 'male', 'husband': 'male',
            'grandfather': 'male', 'grandson': 'male', 'uncle': 'male', 'nephew': 'male',
            'father_in_law': 'male', 'brother_in_law': 'male', 'son_in_law': 'male',
            'stepfather': 'male', 'stepbrother': 'male', 'stepson': 'male',
            'half_brother': 'male', 'great_grandfather': 'male', 'great_uncle': 'male',
            'boyfriend': 'male', 'fiance': 'male', 'godfather': 'male', 'godson': 'male',
            'adoptive_father': 'male', 'foster_father': 'male',
            
            # Female relationships
            'mother': 'female', 'daughter': 'female', 'sister': 'female', 'elder_sister': 'female', 'younger_sister': 'female', 'wife': 'female',
            'grandmother': 'female', 'granddaughter': 'female', 'aunt': 'female', 'niece': 'female',
            'mother_in_law': 'female', 'sister_in_law': 'female', 'daughter_in_law': 'female',
            'stepmother': 'female', 'stepsister': 'female', 'stepdaughter': 'female',
            'half_sister': 'female', 'great_grandmother': 'female', 'great_aunt': 'female',
            'girlfriend': 'female', 'godmother': 'female', 'goddaughter': 'female',
            'adoptive_mother': 'female', 'foster_mother': 'female',
            
            # Gender-neutral or unknown
            'parent': 'unknown', 'sibling': 'unknown', 'child': 'unknown',
            'grandparent': 'unknown', 'grandchild': 'unknown', 'pibling': 'unknown',
            'nibling': 'unknown', 'cousin': 'unknown', 'partner': 'unknown',
            'friend': 'unknown', 'best_friend': 'unknown', 'colleague': 'unknown',
            'boss': 'unknown', 'employee': 'unknown', 'teacher': 'unknown',
            'student': 'unknown', 'mentor': 'unknown', 'mentee': 'unknown',
            'neighbor': 'unknown', 'roommate': 'unknown', 'landlord': 'unknown',
            'tenant': 'unknown', 'foster_child': 'unknown', 'pet': 'unknown'
        }
        
        gender = gender_mapping.get(relationship_type.lower(), 'unknown')
        
        # Update properties with all required attributes
        properties.update({
            'name': name,
            'user': user_name,
            'relation': relationship_type,
            'gender': gender,
            'created_at': datetime.now().isoformat()
        })
        
        with self.driver.session() as session:
            try:
                # Use MATCH-MERGE pattern to update existing node or create if doesn't exist
                query = """
                MATCH (u:User {name: $user_name})
                MERGE (p:Person:SocialMemory {name: $name, user: $user_name})
                ON CREATE SET p = $properties
                ON MATCH SET p.relation = $relationship_type,
                            p.gender = $gender,
                            p.updated_at = $timestamp
                RETURN p
                """
                return session.run(query, 
                    name=name, 
                    user_name=user_name, 
                    relationship_type=relationship_type,
                    gender=gender,
                    timestamp=datetime.now().isoformat(),
                    properties=properties).single()
            except Exception as e:
                print(f"Error creating person node for {name}: {e}")
                return None
    
    def create_relationship(self, user_name, person_name, relationship_type):
        """Create relationship between user and person in Neo4j"""
        with self.driver.session() as session:
            try:
                # For unique relationships, delete existing ones of the same type
                unique_relationships_list = ['father', 'mother', 'husband', 'wife', 'grandfather', 'grandmother']
                if relationship_type in unique_relationships_list:
                    delete_query = f"""
                    MATCH (u:User {{name: $user_name}})-[r:{relationship_type.upper()}]->(p:Person)
                    DELETE r, p
                    """
                    session.run(delete_query, user_name=user_name)
                
                # Clean up any generic HAS_RELATION relationships
                cleanup_query = """
                MATCH (u:User {name: $user_name})-[r:HAS_RELATION]->(p:Person)
                DELETE r
                """
                session.run(cleanup_query, user_name=user_name)
                
                # Determine gender based on relationship type
                gender_mapping = {
                    # Male relationships
                    'father': 'male', 'son': 'male', 'brother': 'male', 'husband': 'male',
                    'grandfather': 'male', 'grandson': 'male', 'uncle': 'male', 'nephew': 'male',
                    'father_in_law': 'male', 'brother_in_law': 'male', 'son_in_law': 'male',
                    'stepfather': 'male', 'stepbrother': 'male', 'stepson': 'male',
                    'half_brother': 'male', 'great_grandfather': 'male', 'great_uncle': 'male',
                    'boyfriend': 'male', 'fiance': 'male', 'godfather': 'male', 'godson': 'male',
                    'adoptive_father': 'male', 'foster_father': 'male',
                    
                    # Female relationships
                    'mother': 'female', 'daughter': 'female', 'sister': 'female', 'wife': 'female',
                    'grandmother': 'female', 'granddaughter': 'female', 'aunt': 'female', 'niece': 'female',
                    'mother_in_law': 'female', 'sister_in_law': 'female', 'daughter_in_law': 'female',
                    'stepmother': 'female', 'stepsister': 'female', 'stepdaughter': 'female',
                    'half_sister': 'female', 'great_grandmother': 'female', 'great_aunt': 'female',
                    'girlfriend': 'female', 'godmother': 'female', 'goddaughter': 'female',
                    'adoptive_mother': 'female', 'foster_mother': 'female',
                    
                    # Gender-neutral or unknown
                    'parent': 'unknown', 'sibling': 'unknown', 'child': 'unknown',
                    'grandparent': 'unknown', 'grandchild': 'unknown', 'pibling': 'unknown',
                    'nibling': 'unknown', 'cousin': 'unknown', 'partner': 'unknown',
                    'friend': 'unknown', 'best_friend': 'unknown', 'colleague': 'unknown',
                    'boss': 'unknown', 'employee': 'unknown', 'teacher': 'unknown',
                    'student': 'unknown', 'mentor': 'unknown', 'mentee': 'unknown',
                    'neighbor': 'unknown', 'roommate': 'unknown', 'landlord': 'unknown',
                    'tenant': 'unknown', 'foster_child': 'unknown', 'pet': 'unknown'
                }
                
                gender = gender_mapping.get(relationship_type.lower(), 'unknown')
                timestamp = datetime.now().isoformat()
                
                # Create or update the person node and relationship in a single transaction
                # Convert relationship type to valid Neo4j relationship name
                neo4j_rel_type = relationship_type.upper().replace(' ', '_').replace('-', '_')
                
                query = f"""
                MATCH (u:User {{name: $user_name}})
                MERGE (p:Person:SocialMemory {{name: $person_name, user: $user_name}})
                ON CREATE SET p.relation = $relationship_type,
                              p.gender = $gender,
                              p.created_at = $timestamp
                ON MATCH SET p.relation = $relationship_type,
                            p.gender = $gender,
                            p.updated_at = $timestamp
                MERGE (u)-[r:{neo4j_rel_type}]->(p)
                SET r.created_at = $timestamp
                RETURN r
                """
                
                return session.run(query, 
                    user_name=user_name, 
                    person_name=person_name,
                    relationship_type=relationship_type,
                    gender=gender,
                    timestamp=timestamp).single()
                
            except Exception as e:
                print(f"Error creating relationship {relationship_type} between {user_name} and {person_name}: {e}")
                return None
    
    def get_user_relationships(self, user_name):
        """Get all relationships for a user"""
        with self.driver.session() as session:
            try:
                query = """
                MATCH (u:User {name: $user_name})-[r]->(p:Person)
                RETURN type(r) as relationship, p.name as person_name, r.created_at as created_at, p.relation as relation_type
                ORDER BY p.relation, r.created_at DESC
                """
                results = []
                for record in session.run(query, user_name=user_name):
                    # Use the stored relation type from person node if available, otherwise use relationship type
                    rel_type = record.get('relation_type') or record.get('relationship', '').replace('_', ' ').lower()
                    results.append({
                        'relationship': rel_type,
                        'person_name': record['person_name'],
                        'created_at': record['created_at']
                    })
                return results
            except Exception as e:
                print(f"Error getting relationships for {user_name}: {e}")
                return []
    
    def check_existing_relationship(self, user_name, relationship_type):
        """Check if a relationship of this type already exists for the user"""
        with self.driver.session() as session:
            try:
                query = f"""
                MATCH (u:User {{name: $user_name}})-[r:{relationship_type.upper()}]->(p:Person)
                RETURN p.name as person_name, r.created_at as created_at
                ORDER BY r.created_at DESC
                LIMIT 1
                """
                record = session.run(query, user_name=user_name).single()
                if record:
                    return {
                        'exists': True,
                        'person_name': record['person_name'],
                        'created_at': record['created_at']
                    }
                return {'exists': False}
            except Exception as e:
                print(f"Error checking existing relationship {relationship_type} for {user_name}: {e}")
                return {'exists': False}
    
    def check_specific_person_relationship(self, user_name, relationship_type, person_name):
        """Check if a specific person already has this relationship with the user"""
        with self.driver.session() as session:
            try:
                query = f"""
                MATCH (u:User {{name: $user_name}})-[r:{relationship_type.upper()}]->(p:Person {{name: $person_name}})
                RETURN p.name as person_name
                LIMIT 1
                """
                record = session.run(query, user_name=user_name, person_name=person_name).single()
                return record is not None
            except Exception as e:
                print(f"Error checking specific person relationship: {e}")
                return False

    def get_specific_relationship(self, user_name, relationship_type):
        """Get the specific relationship of a type for a user"""
        with self.driver.session() as session:
            try:
                query = f"""
                MATCH (u:User {{name: $user_name}})-[r:{relationship_type.upper()}]->(p:Person)
                RETURN p.name as person_name, r.created_at as created_at
                ORDER BY r.created_at DESC
                LIMIT 1
                """
                record = session.run(query, user_name=user_name).single()
                if record:
                    return {
                        'person_name': record['person_name'],
                        'created_at': record['created_at']
                    }
                return None
            except Exception as e:
                print(f"Error getting relationship {relationship_type} for {user_name}: {e}")
                return None

    def update_relationship(self, user_name, person_name, relationship_type):
        """Update an existing relationship with a new person"""
        with self.driver.session() as session:
            try:
                delete_query = f"""
                MATCH (u:User {{name: $user_name}})-[r:{relationship_type.upper()}]->(p:Person)
                DELETE r, p
                """
                session.run(delete_query, user_name=user_name)
                
                return self.create_relationship(user_name, person_name, relationship_type)
                
            except Exception as e:
                print(f"Error updating relationship {relationship_type} for {user_name}: {e}")
                return None

    def store_fact_in_prolog(self, username, person_name, relationship_type):
        """Store relationship fact in user's prolog file"""
        try:
            import os
            
            # Ensure facts directory exists
            fact_dir = "prolog/facts"
            os.makedirs(fact_dir, exist_ok=True)
            
            # Create fact file path
            fact_file = os.path.join(fact_dir, f"{username.replace('@', '_at_')}.pl")
            
            # Create the fact - relationship(person, user)
            fact = f"{relationship_type.lower()}({person_name.lower()},{username.lower()}).\n"
            
            # Check if fact already exists to prevent duplicates
            if os.path.exists(fact_file):
                with open(fact_file, "r") as f:
                    existing_content = f.read()
                if fact.strip() in existing_content:
                    return  # Fact already exists
            
            # Append the fact
            with open(fact_file, "a") as f:
                f.write(fact)
                
        except Exception as e:
            print(f"Error storing fact in prolog: {e}")


    
    def process_user_input(self, text, user_name):
        """Process user input and create relationships if found"""
        # First check for name claims
        claimed_name = self.detect_name_claims(text)
        if claimed_name:
            is_valid, error_message = self.validate_name_claim(claimed_name, user_name)
            if not is_valid:
                return {
                    'relationships': [],
                    'conflicts': [{
                        'type': 'name_validation',
                        'message': error_message
                    }]
                }
        

        
        # Check for user age
        user_age = self.detect_user_age(text)
        if user_age:
            self.update_user_age(user_name, user_age)
            age_updates = [{
                'person_name': user_name,
                'age': user_age,
                'message': f"I've noted that you are {user_age} years old. Thank you for the information! Wanna tell more?"
            }]
        else:
            # Check for age information with person names
            age_info = self.detect_person_age_information(text)
            age_updates = []
            
            for person_name, age in age_info:
                # Check age restrictions before updating
                age_valid, error_msg = self.validate_person_age(user_name, person_name, age)
                if not age_valid:
                    age_updates.append({
                        'person_name': person_name,
                        'age': age,
                        'message': error_msg
                    })
                else:
                    # Update age for this specific person
                    updated = self.update_specific_person_age(user_name, person_name, age)
                    if updated:
                        age_updates.append({
                            'person_name': person_name,
                            'age': age,
                            'message': f"I've noted that {person_name} is {age} years old. Thank you for the information! Wanna tell more?"
                        })
        
        relationships_found = self.detect_relationships(text)
        created_relationships = []
        conflict_messages = []
        
        # Remove duplicates from relationships_found
        unique_relationships = list(dict.fromkeys(relationships_found))
        
        for rel_type, person_name in unique_relationships:
            # Check if this specific person already exists for this relationship type
            existing_person_rel = self.check_specific_person_relationship(user_name, rel_type, person_name)
            
            if existing_person_rel:
                # This exact person-relationship combination already exists
                if not any(msg.get('message', '').startswith(f"I already know that {person_name}") for msg in created_relationships):
                    created_relationships.append({
                        'relationship_type': rel_type,
                        'person_name': person_name,
                        'user': user_name,
                        'created': False,
                        'message': f"I already know that {person_name} is your {rel_type}."
                    })
            else:
                # For unique relationships (father, mother, husband, wife), check if any exists
                unique_relationships_list = ['father', 'mother', 'husband', 'wife', 'grandfather', 'grandmother']
                if rel_type in unique_relationships_list:
                    existing_rel = self.check_existing_relationship(user_name, rel_type)
                    if existing_rel['exists']:
                        existing_person = existing_rel['person_name']
                        if not any(msg.get('message', '').startswith(f"I know your {rel_type}'s name already") for msg in conflict_messages):
                            conflict_messages.append({
                                'relationship_type': rel_type,
                                'new_person': person_name,
                                'existing_person': existing_person,
                                'user': user_name,
                                'conflict': True,
                                'message': f"I know your {rel_type}'s name already. This name you have given is wrong. Your {rel_type} name is {existing_person}."
                            })
                        continue
                # Create new relationship
                person_node = self.create_person_node(person_name, user_name, rel_type)
                
                if person_node:
                    relationship = self.create_relationship(user_name, person_name, rel_type)
                    if relationship:
                        # Store the fact in prolog file
                        self.store_fact_in_prolog(user_name, person_name, rel_type)
                        
                        created_relationships.append({
                            'relationship_type': rel_type,
                            'person_name': person_name,
                            'user': user_name,
                            'created': True,
                            'message': f"I've noted that {person_name} is your {rel_type}."
                        })
        
        # Combine all conflicts and remove duplicates
        all_conflicts = conflict_messages
        all_relationships = created_relationships
        
        # Remove duplicate messages
        unique_conflicts = []
        seen_conflict_messages = set()
        for conflict in all_conflicts:
            msg = conflict.get('message', '')
            if msg and msg not in seen_conflict_messages:
                seen_conflict_messages.add(msg)
                unique_conflicts.append(conflict)
        
        unique_relationships = []
        seen_relationship_messages = set()
        for rel in all_relationships:
            msg = rel.get('message', '')
            if msg and msg not in seen_relationship_messages:
                seen_relationship_messages.add(msg)
                unique_relationships.append(rel)
        
        return {
            'relationships': unique_relationships + age_updates,
            'conflicts': unique_conflicts
        }
    
    def get_relationship_graph(self, user_name):
        """Get visual representation of user's relationship graph"""
        with self.driver.session() as session:
            try:
                query = """
                MATCH (u:User {name: $user_name})-[r]->(p:Person)
                RETURN u.name as user, type(r) as relationship, p.name as person
                """
                return [dict(record) for record in session.run(query, user_name=user_name)]
            except Exception as e:
                print(f"Error getting relationship graph for {user_name}: {e}")
                return []
    
    def clear_user_relationships(self, user_name):
        """Clear all relationships for a specific user"""
        with self.driver.session() as session:
            try:
                query = """
                MATCH (u:User {name: $user_name})-[r]->(p:Person {user: $user_name})
                DELETE r, p
                """
                session.run(query, user_name=user_name)
                
                cleanup_query = """
                MATCH (p:Person {user: $user_name})
                WHERE NOT (p)<-[:FATHER|:MOTHER|:BROTHER|:SISTER|:SON|:DAUGHTER|:HUSBAND|:WIFE|:FRIEND|:COUSIN|:UNCLE|:AUNT|:NEPHEW|:NIECE|:GRANDFATHER|:GRANDMOTHER|:GRANDSON|:GRANDDAUGHTER|:COLLEAGUE|:TEACHER|:STUDENT|:BOSS|:EMPLOYEE|:PARTNER]-()
                DELETE p
                """
                session.run(cleanup_query, user_name=user_name)
                
                return True
            except Exception as e:
                print(f"Error clearing relationships for {user_name}: {e}")
                return False
    
    def cleanup_generic_relationships(self, user_name):
        """Clean up generic HAS_RELATION relationships for a user"""
        with self.driver.session() as session:
            try:
                # Remove all HAS_RELATION relationships
                cleanup_query = """
                MATCH (u:User {name: $user_name})-[r:HAS_RELATION]->(p:Person)
                DELETE r
                """
                result = session.run(cleanup_query, user_name=user_name)
                return True
            except Exception as e:
                print(f"Error cleaning up generic relationships for {user_name}: {e}")
                return False
    
    def migrate_existing_person_nodes_to_social_memory(self):
        """Add SocialMemory label to existing Person nodes that don't have it"""
        with self.driver.session() as session:
            try:
                # Update existing Person nodes to have SocialMemory label
                migration_query = """
                MATCH (p:Person)
                WHERE NOT p:SocialMemory
                SET p:SocialMemory
                RETURN count(p) as updated_count
                """
                result = session.run(migration_query).single()
                updated_count = result['updated_count'] if result else 0
                print(f"Updated {updated_count} existing Person nodes with SocialMemory label")
                return updated_count
            except Exception as e:
                print(f"Error migrating existing Person nodes: {e}")
                return 0

    def close(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()

# Global instance for use across the application
relationship_manager = RelationshipManager() 