from .sensory_memory import SensoryMemory
from .semantic_memory import SemanticMemory
from .perceptual_memory import PerceptualAssociativeMemory
from .social_memory import SocialMemory
from .episodic_memory import EpisodicMemory
from threading import Thread
import re

class MemoryManager:
    """Manages multiple memory systems and coordinates their interactions"""
    
    def __init__(self, neo4j_uri="bolt://localhost:7687", 
                 neo4j_user="neo4j", neo4j_password="12345678",
                 kb_file="prolog/kb.pl"):
        """Initialize all memory systems"""
        self.sensory = SensoryMemory(neo4j_uri, neo4j_user, neo4j_password)
        self.semantic = SemanticMemory(neo4j_uri, neo4j_user, neo4j_password)
        self.perceptual = PerceptualAssociativeMemory(neo4j_uri, neo4j_user, neo4j_password)
        self.episodic = EpisodicMemory(neo4j_uri, neo4j_user, neo4j_password)   
        self.social = SocialMemory(kb_file)

    def process_input(self, text, ip_address, user_id, user_fact_file=None, session_key=None):
        """Process input text through all memory systems synchronously"""
        try:
            self.sensory.save(text, ip_address=ip_address, user_id=user_id)
        except:
            pass
        
        try:
            self.semantic.save(text)
        except:
            pass
        
        try:
            self.perceptual.save(text, ip_address, user_id)
        except:
            pass
        
        try:
            self.episodic.save(user_id=user_id or "anonymous", text=text, session_key=session_key)
        except:
            pass
        
        if user_fact_file:
            try:
                self.social.load_user_facts(user_fact_file)
            except:
                pass

    def async_process_input(self, text, ip_address, user_id, user_fact_file=None, session_key=None):
        """Process input text through all memory systems asynchronously"""
        def _async_save_all():
            try:
                self.sensory.save(text, ip_address=ip_address, user_id=user_id)
            except:
                pass
            
            try:
                self.semantic.save(text)
            except:
                pass
            
            try:
                self.perceptual.save(text, ip_address, user_id)
            except:
                pass
            
            try:
                self.episodic.save(user_id=user_id or "anonymous", text=text, session_key=session_key)
            except:
                pass
            
            if user_fact_file:
                try:
                    self.social.load_user_facts(user_fact_file)
                except:
                    pass
        
        Thread(target=_async_save_all).start()

    def load_previous_context(self, user_id: str, myBot, chat_logger):
        """Load previous context for returning users"""
        try:
            recent_episodes = self.recall_episodes(user_id, limit=5)
            recent_chats = chat_logger.get_recent_conversations(user_id, limit=10)
            extracted_info = self._extract_important_info(recent_episodes, recent_chats)
            
            self._restore_aiml_predicates(myBot, user_id, extracted_info)
            
            return {
                'recent_episodes': recent_episodes,
                'recent_chats': recent_chats,
                'extracted_info': extracted_info
            }
        except:
            return None
    
    def _extract_important_info(self, episodes, chats):
        """Extract important user information from previous conversations"""
        info = {
            'name': None,
            'age': None,
            'father': None,
            'mother': None,
            'relationships': {},
            'mood_history': [],
            'topics_discussed': []
        }
        
        try:
            for episode in episodes:
                text = episode.get('text', '').lower()
                
                if episode.get('emotion'):
                    info['mood_history'].append(episode['emotion'])
                
                if any(word in text for word in ['name', 'called', 'am']):
                    info['topics_discussed'].append('identity')
                if any(word in text for word in ['age', 'old', 'years']):
                    info['topics_discussed'].append('age')
                if any(word in text for word in ['father', 'dad', 'papa']):
                    info['topics_discussed'].append('family')
            
            for chat in chats:
                user_msg = chat.get('user_msg', '').lower()
                
                name_patterns = [
                    r"my name is (\w+)",
                    r"i am (\w+)",
                    r"call me (\w+)"
                ]
                for pattern in name_patterns:
                    match = re.search(pattern, user_msg)
                    if match:
                        info['name'] = match.group(1).title()
                        break
                
                age_pattern = r"i am (\d+) years? old"
                age_match = re.search(age_pattern, user_msg)
                if age_match:
                    info['age'] = age_match.group(1)
                
                father_patterns = [
                    r"my father name is (\w+)",
                    r"my dad name is (\w+)",
                    r"father name is (\w+)"
                ]
                for pattern in father_patterns:
                    match = re.search(pattern, user_msg)
                    if match:
                        info['father'] = match.group(1).title()
                        break
                
                mother_patterns = [
                    r"my mother name is (\w+)",
                    r"my mom name is (\w+)",
                    r"mother name is (\w+)"
                ]
                for pattern in mother_patterns:
                    match = re.search(pattern, user_msg)
                    if match:
                        info['mother'] = match.group(1).title()
                        break
            
            info['topics_discussed'] = list(set(info['topics_discussed']))
            info['mood_history'] = list(set(info['mood_history']))
            
            return info
        except:
            return info
    
    def _restore_aiml_predicates(self, myBot, user_id, extracted_info):
        """Restore AIML predicates with extracted information"""
        try:
            myBot.setPredicate("username", user_id)
            
            if extracted_info.get('name'):
                myBot.setPredicate("name", extracted_info['name'])
            
            if extracted_info.get('age'):
                myBot.setPredicate("age", extracted_info['age'])
            
            if extracted_info.get('father'):
                myBot.setPredicate("father", extracted_info['father'])
            
            if extracted_info.get('mother'):
                myBot.setPredicate("mother", extracted_info['mother'])
            
            myBot.setPredicate("returning_user", "true")
            myBot.setPredicate("context_loaded", "true")
        except:
            pass

    def find_person_info(self, person_name):
        """Get all available information about a person"""
        return {
            "dob": self.social.find_dob(person_name),
            "gender": self.social.find_gender(person_name)
        }

    def find_relationships(self, person1, relation, person2=None):
        """Find or verify relationships between people"""
        return self.social.find_relation(person1, relation, person2)

    def add_person_fact(self, fact_file, fact_type, person, value, related_person=None):
        """Add a new fact about a person"""
        if fact_type == "gender":
            self.social.append_gender_fact(fact_file, person, value)
        elif fact_type == "dob":
            self.social.append_dob_fact(fact_file, person, value)
        elif fact_type == "relation" and related_person:
            self.social.append_relation_fact(fact_file, person, related_person, value)
            
    def recall_episodes(self, user_id: str, limit: int = 5):
        """Return the most recent episodic memories for user"""
        return self.episodic.recall(user_id=user_id, limit=limit)
    
    def get_sensor_data(self, device_id=None, limit=10):
        """Get sensor data from sensory memory"""
        return self.sensory.get_sensor_data(device_id=device_id, limit=limit)
    
    def save_sensor_data(self, device_id, temperature=None, humidity=None, pressure=None, wifi_rssi=None, timestamp=None):
        """Save sensor data to sensory memory with SensoryMemory_SensorBased label"""
        return self.sensory.save_sensor_data(device_id=device_id, temperature=temperature, 
                                            humidity=humidity, pressure=pressure, 
                                            wifi_rssi=wifi_rssi, timestamp=timestamp)

    def get_user_ip_history(self, user_id: str, limit: int = 10):
        """Get user's IP history from sensory memory"""
        return self.sensory.get_user_ip_history(user_id, limit)

    def get_user_chat_summary(self, user_id: str):
        """Get user's chat summary from episodic memory"""
        return self.episodic.get_user_chat_summary(user_id=user_id)

    def get_user_texts(self, user_id: str, limit: int = 10):
        """Get user's recent texts from sensory memory"""
        return self.sensory.get_user_texts(user_id, limit)

    def get_texts_by_location(self, city=None, country=None, limit: int = 10):
        """Get texts by location from sensory memory"""
        return self.sensory.get_texts_by_location(city, country, limit)

    def close_user_episode(self, user_id: str, session_key: str = None):
        """Close the current episode for a user session"""
        try:
            self.episodic.close_episode(user_id=user_id, session_key=session_key)
        except:
            pass

    def close(self):
        """Close all memory system connections"""
        self.sensory.close()
        self.semantic.close()
        self.perceptual.close()
        self.episodic.close()