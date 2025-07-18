from nltk import word_tokenize, pos_tag, ne_chunk, Tree, sent_tokenize
from nltk.sentiment import SentimentIntensityAnalyzer
from .base_memory import BaseNeo4jMemory

try:
    from pos_tags_dict import pos_tags_dict
except ImportError:
    pos_tags_dict = {}

class PerceptualAssociativeMemory(BaseNeo4jMemory):
    """Processes sensory input for patterns, sentiment, and named entities"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sia = SentimentIntensityAnalyzer()

    def extract_named_entities_from_words(self, words):
        """Extract named entities from tokenized words"""
        named_entities = []
        pos = pos_tag(words)
        ne_tree = ne_chunk(pos)
        for subtree in ne_tree:
            if isinstance(subtree, Tree):
                entity_name = " ".join([token for token, _ in subtree.leaves()])
                entity_type = subtree.label()
                named_entities.append((entity_name, entity_type))
        return named_entities

    def classify_sentence_type(self, sentence):
        """Classify sentence type as interrogative, imperative, exclamatory, or declarative"""
        words = word_tokenize(sentence)
        tags = pos_tag(words)

        if not words:
            return "unknown"

        first_word = words[0].lower()
        first_tag = tags[0][1] if tags else ""

        wh_words = {"what", "when", "where", "who", "why", "how", "which", "whom", "whose"}
        aux_modals = {"is", "are", "was", "were", "do", "does", "did", "can", "could", 
                     "will", "would", "should", "shall", "may", "might", "have", "has", "had"}

        if first_word in wh_words or first_word in aux_modals:
            return "interrogative"

        if first_tag == "VB" and all(tag[1] not in {"PRP", "NN", "NNP"} for tag in tags[:2]):
            return "imperative"

        if first_tag == "UH" or first_word in {"what", "how"} and len(tags) > 1 and tags[1][1] in {"JJ", "RB"}:
            return "exclamatory"

        return "declarative"

    def save(self, text, ip_address, user_id=None):
        """Save perceptual analysis of text including sentiment, POS tags, and named entities"""
        try:
            with self.driver.session() as neo4j_session:
                sentences = sent_tokenize(text)
                
                for sentence in sentences:
                    if not sentence.strip():
                        continue

                    sentiment_score = self.sia.polarity_scores(sentence)
                    sentiment = ("positive" if sentiment_score["pos"] > sentiment_score["neg"] 
                               else "negative" if sentiment_score["neg"] > sentiment_score["pos"] 
                               else "neutral")

                    neo4j_session.run("""
                        MERGE (se:Sentiment:PerceptualAssociativeMemory {sentiment: $sentiment})
                        WITH se MATCH (s:Sentence:SensoryMemory_TextBased {sentence_text: $sentence})
                        MERGE (s)-[:HAS_SENTIMENT]->(se)
                    """, sentence=sentence, sentiment=sentiment)

                    sentence_type = self.classify_sentence_type(sentence)
                    neo4j_session.run("""
                        MERGE (t:SentenceType:PerceptualAssociativeMemory {type: $type})
                        WITH t MATCH (s:Sentence:SensoryMemory_TextBased {sentence_text: $sentence})
                        MERGE (s)-[:HAS_TYPE]->(t)
                    """, sentence=sentence, type=sentence_type)

                    words = word_tokenize(sentence)
                    pos_tags = pos_tag(words)
                    for word, pos in pos_tags:
                        long_pos = pos_tags_dict.get(pos, "Unknown")
                        neo4j_session.run("""
                            MERGE (p:POSTag:PerceptualAssociativeMemory {short: $pos, long: $long_pos})
                            WITH p MATCH (w:Word:SensoryMemory_TextBased {word_text: $word})
                            MERGE (w)-[:HAS_POS_TAG]->(p)
                        """, word=word, pos=pos, long_pos=long_pos)

                    named_entities = self.extract_named_entities_from_words(words)
                    for entity_name, entity_type in named_entities:
                        neo4j_session.run("""
                            MERGE (ne:NamedEntity:PerceptualAssociativeMemory 
                                  {entity_text: $entity_name, entity_type: $entity_type})
                            WITH ne MATCH (s:Sentence:SensoryMemory_TextBased {sentence_text: $sentence})
                            MERGE (s)-[:HAS_NAMED_ENTITY]->(ne)
                        """, sentence=sentence, entity_name=entity_name, entity_type=entity_type)

        except:
            pass

    def get_user_ip_history(self, user_id: str, limit: int = 10):
        """Get IP address and location history for a specific user"""
        try:
            with self.driver.session() as neo4j_session:
                query = """
                MATCH (u:User {id: $user_id})-[:ACCESSED_FROM]->(ip:IPAddress)
                OPTIONAL MATCH (ip)-[:LOCATED_AT]->(loc:Location)
                RETURN ip.ip AS ip_address, ip.last_used AS last_used, 
                       loc.city AS city, loc.country AS country
                ORDER BY ip.last_used DESC
                LIMIT $limit
                """
                result = neo4j_session.run(query, user_id=user_id, limit=limit)
                return [record.data() for record in result]
        except:
            return []

    def close(self):
        """Close Neo4j connection"""
        self.driver.close() 