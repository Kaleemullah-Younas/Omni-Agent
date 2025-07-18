import pytholog as pl
from dateutil import parser
import os
import calendar
from datetime import date
from nltk.corpus import wordnet as wn
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk import pos_tag, ne_chunk
from nltk.tree import Tree

class SocialMemory:
    """Manages social knowledge using Prolog knowledge base"""
    
    def __init__(self, kb_file="prolog/kb.pl"):
        """Initialize social memory with knowledge base"""
        self.kb = pl.KnowledgeBase("family")
        self.kb.from_file(kb_file)
        self.myBot = None
        self.session = None
        self.mood = ""
        self.sia = SentimentIntensityAnalyzer()
        
    def reload_kb(self, kb_file="prolog/kb.pl"):
        """Reload knowledge base from file"""
        self.kb.clear_cache()
        self.kb.from_file(kb_file)

    def load_user_facts(self, fact_file):
        """Load user-specific facts from their fact file"""
        if os.path.exists(fact_file):
            self.kb.from_file(fact_file)

    def get_description(self, word):
        """Get word descriptions from WordNet"""
        description = '\n'
        sn = wn.synsets(word)
        length = len(sn)
        for i in range(length):
            description += str(i + 1) + ". " + sn[i].definition()
            if i + 1 != length:
                description += '\n'
        return description

    def check_meanings(self, word):
        """Check word meanings and set AIML predicates"""
        if not self.myBot:
            return
            
        if word == "":
            self.myBot.setPredicate("description", "I don't know.")
            return
        else:
            self.myBot.setPredicate("description", self.get_description(word))
            word = word.capitalize()
            self.myBot.setPredicate("word", word)
            return

    def sentiment_analysis(self, text):
        """Analyze sentiment and set global mood"""
        if not self.myBot:
            return
            
        results = self.sia.polarity_scores(text)
        if results['pos'] > results['neg']:
            self.myBot.setPredicate("sentiment", "positive")
            self.mood = "positive"
            return
        elif results['neg'] > results['pos']:
            self.myBot.setPredicate("sentiment", "negative")
            self.mood = "negative"
            return
        return

    def check_sentiment(self, sentiment):
        """Check if sentiment is a name or actual sentiment"""
        if not self.myBot:
            return
            
        pos = pos_tag([sentiment])
        entity = ne_chunk(pos)
        if isinstance(entity[0], Tree):
            entity_label = entity[0].label()
            if pos[0][1] == "NNP" and (entity_label == 'GPE' or entity_label == 'PERSON'):
                self.myBot.setPredicate("username", sentiment)
                self.myBot.setPredicate("sentiment", "")
                return

        self.sentiment_analysis(sentiment)
        return

    def set_sentiment(self):
        """Set sentiment from global mood"""
        if not self.myBot:
            return
            
        sentiment = self.myBot.getPredicate("sentiment")
        if sentiment == "":
            self.myBot.setPredicate("sentiment", self.mood)
            return
        return

    def find_person(self, person, relation):
        """Find person in relationship from Prolog KB with comprehensive relationship support"""
        try:
            person_lower = person.lower()
            relation_lower = relation.lower()
            
            # Try multiple query formats for better compatibility
            queries_to_try = [
                f"{relation_lower}(X,{person_lower})",  # father(X,john) - who is john's father
                f"{relation_lower}({person_lower},X)",  # father(john,X) - who is john the father of
            ]
            
            for query in queries_to_try:
                try:
                    result = self.kb.query(pl.Expr(query))
                    if result and len(result) > 0:
                        if isinstance(result[0], dict) and 'X' in result[0]:
                            return result[0]['X'].capitalize()
                        elif isinstance(result[0], str):
                            return result[0].capitalize()
                except:
                    continue
            
            return None
        except:
            return None

    def find_all_relationships(self, person):
        """Find all relationships for a given person"""
        relationships = {}
        person_lower = person.lower()
        
        # Define all possible relationship types from the Prolog KB
        relationship_types = [
            # Western relationships
            'father', 'mother', 'parent', 'child', 'son', 'daughter',
            'brother', 'sister', 'sibling', 'grandfather', 'grandmother',
            'grandson', 'granddaughter', 'grandchild', 'uncle', 'aunt',
            'nephew', 'niece', 'cousin', 'husband', 'wife', 'married',
            
            # Eastern relationships
            'abu', 'ami', 'taya', 'tayi', 'chacha', 'chachi', 'mama', 'mami',
            'khala', 'khalu', 'dada', 'dadi', 'nana', 'nani', 'dewar', 'dewrani',
            'jeth', 'jethani', 'saas', 'sasur', 'nand', 'bahu', 'damad',
            'saala', 'saali', 'bhanoyi', 'beta', 'beti', 'bhai', 'behn',
            'bhatija', 'bhatiji', 'pota', 'poti', 'nawasa', 'nawasi',
            'bhanja', 'bhanji'
        ]
        
        for rel_type in relationship_types:
            try:
                # Try both query directions
                queries = [
                    f"{rel_type}(X,{person_lower})",  # who is person's relation
                    f"{rel_type}({person_lower},X)",  # who is person the relation of
                ]
                
                for query in queries:
                    try:
                        result = self.kb.query(pl.Expr(query))
                        if result and len(result) > 0:
                            for res in result:
                                if isinstance(res, dict) and 'X' in res:
                                    if rel_type not in relationships:
                                        relationships[rel_type] = []
                                    relationships[rel_type].append(res['X'].capitalize())
                                elif isinstance(res, str):
                                    if rel_type not in relationships:
                                        relationships[rel_type] = []
                                    relationships[rel_type].append(res.capitalize())
                    except:
                        continue
            except:
                continue
        
        return relationships

    def get_relationship_description(self, person1, person2):
        """Get a natural language description of the relationship between two people"""
        person1_lower = person1.lower()
        person2_lower = person2.lower()
        
        # Find all relationships for person1
        relationships = self.find_all_relationships(person1)
        
        # Check if person2 is in any relationship with person1
        for rel_type, related_people in relationships.items():
            if any(p.lower() == person2_lower for p in related_people):
                return f"{person2.capitalize()} is the {rel_type} of {person1.capitalize()}"
        
        # Try reverse relationship
        relationships_reverse = self.find_all_relationships(person2)
        for rel_type, related_people in relationships_reverse.items():
            if any(p.lower() == person1_lower for p in related_people):
                return f"{person1.capitalize()} is the {rel_type} of {person2.capitalize()}"
        
        return f"I don't know the relationship between {person1.capitalize()} and {person2.capitalize()}"

    def check_relation(self, rel, person1):
        """Check if person1 has a specific relation"""
        if not self.myBot:
            return
            
        result = self.find_person(person1, rel)
        if result:
            self.myBot.setPredicate("rel", rel)
            self.myBot.setPredicate("person1", person1)
            self.myBot.setPredicate("person2", result)
            return
        else:
            self.myBot.setPredicate("rel", "")
            self.myBot.setPredicate("person1", "")
            self.myBot.setPredicate("person2", "")
            return

    def find_dob(self, person_name):
        """Find date of birth for a person"""
        if not self.myBot:
            return
            
        try:
            expr = f"dob({person_name},Y)"
            result = self.kb.query(pl.Expr(expr))
            if result and len(result) > 0:
                date_str = result[0]['Y'] if isinstance(result[0], dict) else result[0]
                try:
                    parsed_date = parser.parse(str(date_str))
                    formatted_date = parsed_date.strftime("%B %d, %Y")
                    self.myBot.setPredicate("dob_person", person_name)
                    self.myBot.setPredicate("dob", formatted_date)
                    return formatted_date
                except:
                    pass
        except:
            pass
        
        self.myBot.setPredicate("dob_person", "")
        self.myBot.setPredicate("dob", "")
        return None

    def find_gender(self, person_name):
        """Find gender for a person"""
        if not self.myBot:
            return
            
        try:
            expr = f"gender({person_name},Y)"
            result = self.kb.query(pl.Expr(expr))
            if result and len(result) > 0:
                gender = result[0]['Y'] if isinstance(result[0], dict) else result[0]
                self.myBot.setPredicate("gender_person", person_name)
                self.myBot.setPredicate("gender", str(gender))
                return str(gender)
        except:
            pass
        
        self.myBot.setPredicate("gender_person", "")
        self.myBot.setPredicate("gender", "")
        return None

    def find_age(self, person_name):
        """Calculate age from date of birth"""
        if not self.myBot:
            return
            
        try:
            expr = f"dob({person_name},Y)"
            result = self.kb.query(pl.Expr(expr))
            if result and len(result) > 0:
                date_str = result[0]['Y'] if isinstance(result[0], dict) else result[0]
                try:
                    parsed_date = parser.parse(str(date_str))
                    today = date.today()
                    age = today.year - parsed_date.year - ((today.month, today.day) < (parsed_date.month, parsed_date.day))
                    self.myBot.setPredicate("age_person", person_name)
                    self.myBot.setPredicate("age", str(age))
                    return age
                except:
                    pass
        except:
            pass
        
        self.myBot.setPredicate("age_person", "")
        self.myBot.setPredicate("age", "")
        return None

    def append_fact(self, fact_file, fact):
        """Append a fact to the knowledge base file"""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(fact_file), exist_ok=True)
            
            # Check if fact already exists to prevent duplicates
            if os.path.exists(fact_file):
                with open(fact_file, "r") as f:
                    existing_content = f.read()
                if fact.strip() in existing_content:
                    return  # Fact already exists
            
            with open(fact_file, "a") as f:
                f.write(fact + "\n")
                
            # Reload the knowledge base to include new fact
            self.kb.from_file(fact_file)
        except Exception as e:
            print(f"Error appending fact: {e}")

    def append_gender_fact(self, username, gender):
        """Append gender fact to user's fact file"""
        fact_file = f"prolog/facts/{username.replace('@', '_at_')}.pl"
        fact = f"gender({username.lower()},{gender.lower()})."
        self.append_fact(fact_file, fact)
        
        try:
            self._store_person_gender_in_neo4j(username, gender)
        except:
            pass

    def append_dob_fact(self, username, dob):
        """Append date of birth fact to user's fact file"""
        fact_file = f"prolog/facts/{username.replace('@', '_at_')}.pl"
        try:
            parsed_date = parser.parse(dob)
            formatted_date = parsed_date.strftime("%Y-%m-%d")
            fact = f"dob({username.lower()},'{formatted_date}')."
            self.append_fact(fact_file, fact)
        except Exception as e:
            print(f"Error appending DOB fact: {e}")

    def append_relation_fact(self, username, person1, relation):
        """Append relationship fact to user's fact file"""
        fact_file = f"prolog/facts/{username.replace('@', '_at_')}.pl"
        fact = f"{relation.lower()}({person1.lower()},{username.lower()})."
        self.append_fact(fact_file, fact)
        
        try:
            self._store_relation_gender_in_neo4j(username, person1, relation)
        except:
            pass
    
    def _store_relation_gender_in_neo4j(self, username, person1, relation):
        """Store relationship gender information in Neo4j - DISABLED to prevent duplicate relationships"""
        # This method is disabled to prevent creating duplicate HAS_RELATION relationships
        # The relationship_manager.py already handles proper relationship creation
        # Only keep this for backward compatibility
        pass

    def _store_person_gender_in_neo4j(self, person_name, gender):
        """Store person's gender in Neo4j"""
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "12345678"))
        
        with driver.session() as session:
            # Use MERGE to update existing node or create if doesn't exist
            session.run("""
                MERGE (p:Person:SocialMemory {name: $name})
                ON CREATE SET p.gender = $gender,
                             p.created_at = datetime()
                ON MATCH SET p.gender = $gender
            """, name=person_name, gender=gender)
        
        driver.close()

    def find_relation(self, person1, relation, person2=None):
        """Find or verify relationships between people"""
        try:
            if person2:
                # Verify specific relationship
                expr = f"{relation.lower()}({person1.lower()},{person2.lower()})"
                result = self.kb.query(pl.Expr(expr))
                return len(result) > 0 if result else False
            else:
                # Find relationship
                queries_to_try = [
                    f"{relation.lower()}(X,{person1.lower()})",  # who is person1's relation
                    f"{relation.lower()}({person1.lower()},X)",  # who is person1 the relation of
                ]
                
                for query in queries_to_try:
                    try:
                        result = self.kb.query(pl.Expr(query))
                        if result and len(result) > 0:
                            if isinstance(result[0], dict) and 'X' in result[0]:
                                return result[0]['X']
                            elif isinstance(result[0], str):
                                return result[0]
                    except:
                        continue
                
                return None
        except:
            return None

    def prompt_check(self):
        """Process AIML predicates and execute corresponding actions"""
        if not self.myBot or not self.session:
            return
            
        # Check word meanings
        word = self.myBot.getPredicate("word")
        if word and word != "":
            self.check_meanings(word)
        
        # Check sentiment
        mood = self.myBot.getPredicate("mood")
        if mood and mood != "":
            self.check_sentiment(mood)
        
        # Check person's date of birth
        dob_person = self.myBot.getPredicate("dob_person")
        if dob_person and dob_person != "":
            self.find_dob(dob_person)
        
        # Check person's age
        age_person = self.myBot.getPredicate("age_person")
        if age_person and age_person != "":
            self.find_age(age_person)
        
        # Check person's gender
        gender_person = self.myBot.getPredicate("gender_person")
        if gender_person and gender_person != "":
            self.find_gender(gender_person)

        # Check relationships
        rel = self.myBot.getPredicate("rel")
        person1 = self.myBot.getPredicate("person1")
        if rel and person1 and rel != "" and person1 != "":
            self.check_relation(rel, person1)
        
        # Store gender information
        person = self.myBot.getPredicate("person")
        gender = self.myBot.getPredicate("gender")
        if person and gender and person != "" and gender != "":
            self.append_gender_fact(person, gender)
        
        # Store date of birth
        dob = self.myBot.getPredicate("dob")
        if person and dob and person != "" and dob != "":
            self.append_dob_fact(person, dob)
        
        # Store relationship
        relation = self.myBot.getPredicate("relation")
        if person and relation and person != "" and relation != "":
            self.append_relation_fact(self.session.get("username", ""), person, relation)
        
        # Handle other predicates for user information
        other_dob_person = self.myBot.getPredicate("other_dob_person")
        if other_dob_person and other_dob_person != "":
            self.find_dob(other_dob_person)
        
        other_dob = self.myBot.getPredicate("other_dob")
        if other_dob and other_dob != "":
            self.append_dob_fact(other_dob_person, other_dob)
            
        other_gender_person = self.myBot.getPredicate("other_gender_person")
        if other_gender_person and other_gender_person != "":
            self.find_gender(other_gender_person)
        
        other_gender = self.myBot.getPredicate("other_gender")
        if other_gender and other_gender != "":
            self.append_gender_fact(other_gender_person, other_gender)
            
        other_person1 = self.myBot.getPredicate("other_person1")
        other_person2 = self.myBot.getPredicate("other_person2")
        other_relation = self.myBot.getPredicate("other_relation")
        if other_person1 and other_person2 and other_relation and other_person1 != "" and other_person2 != "" and other_relation != "":
            self.append_relation_fact(other_person2, other_person1, other_relation) 