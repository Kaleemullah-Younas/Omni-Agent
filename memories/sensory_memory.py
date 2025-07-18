from datetime import datetime
import requests
from nltk import sent_tokenize, word_tokenize
from .base_memory import BaseNeo4jMemory

def get_location_from_ip(ip_address):
    """Get location information from IP address using ip-api.com"""
    try:
        if ip_address in ["127.0.0.1", "::1", "localhost", "Unknown"]:
            return "Local", "Local"
        
        response = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("city", "Unknown"), data.get("country", "Unknown")
        return "Unknown", "Unknown"
    except:
        return "Unknown", "Unknown"

class SensoryMemory(BaseNeo4jMemory):
    """Stores raw sensory input with user IP tracking"""
    
    def save(self, text, ip_address=None, user_id=None):
        """Save text to sensory memory and track user IP separately"""
        timestamp = datetime.now().isoformat()
        
        with self.driver.session() as neo4j_session:
            # Create text node without IP information
            neo4j_session.run("""
                MERGE (t:Text:SensoryMemory_TextBased {
                    full_text: $text, 
                    timestamp: $timestamp
                })
            """, text=text, timestamp=timestamp)
            
            # Link to user if user_id is provided
            if user_id:
                neo4j_session.run("""
                    MATCH (t:Text:SensoryMemory_TextBased {full_text: $text, timestamp: $timestamp})
                    MERGE (u:User {id: $user_id})
                    MERGE (u)-[:CREATED_TEXT]->(t)
                """, text=text, timestamp=timestamp, user_id=user_id)
                
                # Handle IP address tracking separately for user only
                if ip_address and ip_address != "Unknown":
                    city, country = get_location_from_ip(ip_address)
                    neo4j_session.run("""
                        MERGE (u:User {id: $user_id})
                        MERGE (ip:IPAddress {ip: $ip_address})
                        MERGE (loc:Location {city: $city, country: $country})
                        MERGE (u)-[:ACCESSED_FROM]->(ip)
                        MERGE (ip)-[:LOCATED_AT]->(loc)
                        SET ip.last_used = $timestamp
                    """, user_id=user_id, ip_address=ip_address, city=city, country=country, timestamp=timestamp)

            sentences = sent_tokenize(text)
            prev_sentence = None
            
            for sentence in sentences:
                neo4j_session.run("""
                    MATCH (t:Text:SensoryMemory_TextBased {full_text: $text, timestamp: $timestamp})
                    MERGE (s:Sentence:SensoryMemory_TextBased {sentence_text: $sentence})
                    MERGE (t)-[:HAS_A_SENTENCE]->(s)
                """, text=text, sentence=sentence, timestamp=timestamp)

                if prev_sentence:
                    neo4j_session.run("""
                        MATCH (s1:Sentence:SensoryMemory_TextBased {sentence_text: $prev_sentence}), 
                              (s2:Sentence:SensoryMemory_TextBased {sentence_text: $curr_sentence})
                        MERGE (s1)-[:NEXT_SENTENCE]->(s2)
                    """, prev_sentence=prev_sentence, curr_sentence=sentence)

                prev_sentence = sentence

                words = word_tokenize(sentence)
                prev_word = None
                
                for word in words:
                    neo4j_session.run("""
                        MATCH (s:Sentence:SensoryMemory_TextBased {sentence_text: $sentence})
                        MERGE (w:Word:SensoryMemory_TextBased {word_text: $word})
                        MERGE (s)-[:HAS_A_WORD]->(w)
                    """, sentence=sentence, word=word)

                    if prev_word:
                        neo4j_session.run("""
                            MATCH (w1:Word:SensoryMemory_TextBased {word_text: $prev_word}), 
                                  (w2:Word:SensoryMemory_TextBased {word_text: $curr_word})
                            MERGE (w1)-[:NEXT_WORD]->(w2)
                        """, prev_word=prev_word, curr_word=word)

                    prev_word = word

    def get_user_texts(self, user_id, limit=10):
        """Get recent texts created by a specific user"""
        with self.driver.session() as neo4j_session:
            result = neo4j_session.run("""
                MATCH (u:User {id: $user_id})-[:CREATED_TEXT]->(t:Text:SensoryMemory_TextBased)
                RETURN t.full_text AS text, t.timestamp AS timestamp
                ORDER BY t.timestamp DESC
                LIMIT $limit
            """, user_id=user_id, limit=limit)
            return [record.data() for record in result]

    def get_user_ip_history(self, user_id, limit=10):
        """Get IP address history for a specific user"""
        with self.driver.session() as neo4j_session:
            result = neo4j_session.run("""
                MATCH (u:User {id: $user_id})-[:ACCESSED_FROM]->(ip:IPAddress)
                OPTIONAL MATCH (ip)-[:LOCATED_AT]->(loc:Location)
                RETURN ip.ip AS ip_address, loc.city AS city, loc.country AS country, 
                       ip.last_used AS timestamp
                ORDER BY ip.last_used DESC
                LIMIT $limit
            """, user_id=user_id, limit=limit)
            return [record.data() for record in result]

    def get_texts_by_location(self, city=None, country=None, limit=10):
        """Get texts by users from specific locations"""
        with self.driver.session() as neo4j_session:
            if city and country:
                result = neo4j_session.run("""
                    MATCH (u:User)-[:ACCESSED_FROM]->(ip:IPAddress)-[:LOCATED_AT]->(loc:Location {city: $city, country: $country})
                    MATCH (u)-[:CREATED_TEXT]->(t:Text:SensoryMemory_TextBased)
                    RETURN t.full_text AS text, t.timestamp AS timestamp, 
                           loc.city AS city, loc.country AS country
                    ORDER BY t.timestamp DESC
                    LIMIT $limit
                """, city=city, country=country, limit=limit)
            elif country:
                result = neo4j_session.run("""
                    MATCH (u:User)-[:ACCESSED_FROM]->(ip:IPAddress)-[:LOCATED_AT]->(loc:Location {country: $country})
                    MATCH (u)-[:CREATED_TEXT]->(t:Text:SensoryMemory_TextBased)
                    RETURN t.full_text AS text, t.timestamp AS timestamp, 
                           loc.city AS city, loc.country AS country
                    ORDER BY t.timestamp DESC
                    LIMIT $limit
                """, country=country, limit=limit)
            else:
                return []
            
            return [record.data() for record in result]

    def save_sensor_data(self, device_id, temperature=None, humidity=None, pressure=None, wifi_rssi=None, timestamp=None):
        """Save sensor data with SensoryMemory_SensorBased label - overwrites existing data"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        with self.driver.session() as neo4j_session:
            # Create or update sensor data node (MERGE will overwrite existing properties)
            neo4j_session.run("""
                MERGE (sd:SensorData:SensoryMemory_SensorBased {device_id: $device_id})
                SET sd.temperature = $temperature,
                    sd.humidity = $humidity,
                    sd.pressure = $pressure,
                    sd.wifi_rssi = $wifi_rssi,
                    sd.timestamp = $timestamp,
                    sd.last_updated = $timestamp
                RETURN sd
            """, 
                device_id=device_id,
                temperature=temperature,
                humidity=humidity,
                pressure=pressure,
                wifi_rssi=wifi_rssi,
                timestamp=timestamp
            )
            
            print(f"Sensor data saved/updated for device {device_id}: temp={temperature}°C, humidity={humidity}%, pressure={pressure}hPa")

    def get_sensor_data(self, device_id=None, limit=10):
        """Get sensor data - all devices or specific device"""
        with self.driver.session() as neo4j_session:
            if device_id:
                result = neo4j_session.run("""
                    MATCH (sd:SensorData:SensoryMemory_SensorBased {device_id: $device_id})
                    RETURN sd.device_id AS device_id, sd.temperature AS temperature,
                           sd.humidity AS humidity, sd.pressure AS pressure,
                           sd.wifi_rssi AS wifi_rssi, sd.timestamp AS timestamp,
                           sd.last_updated AS last_updated
                    ORDER BY sd.last_updated DESC
                    LIMIT $limit
                """, device_id=device_id, limit=limit)
            else:
                result = neo4j_session.run("""
                    MATCH (sd:SensorData:SensoryMemory_SensorBased)
                    RETURN sd.device_id AS device_id, sd.temperature AS temperature,
                           sd.humidity AS humidity, sd.pressure AS pressure,
                           sd.wifi_rssi AS wifi_rssi, sd.timestamp AS timestamp,
                           sd.last_updated AS last_updated
                    ORDER BY sd.last_updated DESC
                    LIMIT $limit
                """, limit=limit)
            
            return [record.data() for record in result]

    def close(self):
        """Close Neo4j connection"""
        self.driver.close() 