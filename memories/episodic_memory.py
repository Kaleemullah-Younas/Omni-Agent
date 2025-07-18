from datetime import datetime
import json
import time
import nltk
from nltk.corpus import stopwords, opinion_lexicon
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import word_tokenize
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer
from neo4j import GraphDatabase
from .base_memory import BaseNeo4jMemory

class EpisodicMemory(BaseNeo4jMemory):
    """Stores time-stamped, context-rich user episodes"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sia = SentimentIntensityAnalyzer()
        self.stop_words = set(stopwords.words("english"))

    def save(self, *, user_id: str, text: str, episode_type: str = "conversation", session_key: str = None):
        """Add interaction to current session episode or create new session episode"""
        topics = self._extract_topics(text)
        sentiment_data = self._analyze_sentiment(text)
        emotion = self._detect_emotion(text)
        timestamp = time.time()

        with self.driver.session() as ses:
            # Check if there's an active session episode for this user
            existing_episode = ses.run("""
                MATCH (u:User {id: $user_id})-[:EXPERIENCED]->(e:Episode:EpisodicMemory)
                WHERE e.session_key = $session_key AND e.status = 'active'
                RETURN e
                ORDER BY e.created_timestamp DESC
                LIMIT 1
            """, user_id=user_id, session_key=session_key).single()
            
            if existing_episode and session_key:
                # Add interaction to existing episode
                ses.run("""
                    MATCH (u:User {id: $user_id})-[:EXPERIENCED]->(e:Episode:EpisodicMemory)
                    WHERE e.session_key = $session_key AND e.status = 'active'
                    CREATE (i:Interaction:EpisodicMemory {
                        text: $text,
                        timestamp: $timestamp,
                        sentiment: $sentiment,
                        confidence: $confidence,
                        emotion: $emotion,
                        topics: $topics
                    })
                    CREATE (e)-[:HAS_INTERACTION]->(i)
                    SET e.last_interaction = $timestamp,
                        e.interaction_count = COALESCE(e.interaction_count, 0) + 1
                """, 
                    user_id=user_id,
                    session_key=session_key,
                    text=text,
                    timestamp=timestamp,
                    sentiment=sentiment_data["sentiment"],
                    confidence=float(sentiment_data["confidence"]),
                    emotion=emotion,
                    topics=json.dumps(topics)
                )
            else:
                # Create new session episode
                session_key = session_key or f"session_{user_id}_{int(timestamp)}"
                ses.run("""
                    MERGE (u:User {id: $user_id})
                    CREATE (e:Episode:EpisodicMemory {
                        session_key: $session_key,
                        created_timestamp: $timestamp,
                        last_interaction: $timestamp,
                        type: $episode_type,
                        status: 'active',
                        interaction_count: 1
                    })
                    CREATE (u)-[:EXPERIENCED]->(e)
                    CREATE (i:Interaction:EpisodicMemory {
                        text: $text,
                        timestamp: $timestamp,
                        sentiment: $sentiment,
                        confidence: $confidence,
                        emotion: $emotion,
                        topics: $topics
                    })
                    CREATE (e)-[:HAS_INTERACTION]->(i)
                """,
                    user_id=user_id,
                    session_key=session_key,
                    text=text,
                    timestamp=timestamp,
                    episode_type=episode_type,
                    sentiment=sentiment_data["sentiment"],
                    confidence=float(sentiment_data["confidence"]),
                    emotion=emotion,
                    topics=json.dumps(topics)
                )

    def recall(self, *, user_id: str, limit: int = 5):
        """Return the most recent episodes for user with their interactions"""
        cypher = (
            "MATCH (u:User {id:$user_id})-[:EXPERIENCED]->(e:Episode:EpisodicMemory)\n"
            "OPTIONAL MATCH (e)-[:HAS_INTERACTION]->(i:Interaction:EpisodicMemory)\n"
            "RETURN e.session_key AS session_key, e.created_timestamp AS episode_start, \n"
            "       e.last_interaction AS episode_end, e.interaction_count AS interaction_count,\n"
            "       e.status AS status, collect(i.text) AS interactions,\n"
            "       collect(i.sentiment) AS sentiments, collect(i.emotion) AS emotions\n"
            "ORDER BY e.created_timestamp DESC LIMIT $limit"
        )
        with self.driver.session() as ses:
            return [rec.data() for rec in ses.run(cypher, user_id=user_id, limit=limit)]
    
    def close_episode(self, *, user_id: str, session_key: str = None):
        """Close the current active episode for a user session"""
        with self.driver.session() as ses:
            if session_key:
                ses.run("""
                    MATCH (u:User {id: $user_id})-[:EXPERIENCED]->(e:Episode:EpisodicMemory)
                    WHERE e.session_key = $session_key AND e.status = 'active'
                    SET e.status = 'closed', e.closed_timestamp = timestamp()
                """, user_id=user_id, session_key=session_key)
            else:
                # Close all active episodes for user if no session_key provided
                ses.run("""
                    MATCH (u:User {id: $user_id})-[:EXPERIENCED]->(e:Episode:EpisodicMemory)
                    WHERE e.status = 'active'
                    SET e.status = 'closed', e.closed_timestamp = timestamp()
                """, user_id=user_id)

    def get_user_chat_summary(self, *, user_id: str):
        """Get a summary of all chat episodes for a specific user"""
        cypher = (
            "MATCH (u:User {id:$user_id})-[:EXPERIENCED]->(e:Episode:EpisodicMemory)\n"
            "OPTIONAL MATCH (e)-[:HAS_INTERACTION]->(i:Interaction:EpisodicMemory)\n"
            "RETURN count(DISTINCT e) AS total_episodes, \n"
            "       count(i) AS total_interactions,\n"
            "       collect(DISTINCT i.sentiment) AS sentiments_used,\n"
            "       collect(DISTINCT i.emotion) AS emotions_detected,\n"
            "       min(e.created_timestamp) AS first_interaction,\n"
            "       max(e.last_interaction) AS last_interaction\n"
        )
        with self.driver.session() as ses:
            result = ses.run(cypher, user_id=user_id).single()
            return result.data() if result else None

    def _analyze_sentiment(self, text: str):
        """Analyze sentiment of text"""
        scores = self.sia.polarity_scores(text)
        comp = scores["compound"]
        if comp >= 0.05:
            return {"sentiment": "Positive", "confidence": scores["pos"]}
        if comp <= -0.05:
            return {"sentiment": "Negative", "confidence": scores["neg"]}
        return {"sentiment": "Neutral", "confidence": scores["neu"]}

    def _detect_emotion(self, text: str):
        """Detect basic emotions from text"""
        base = {"joy": 0, "sadness": 0, "anger": 0, "fear": 0}
        toks = [t for t in word_tokenize(text.lower()) if t.isalnum() and t not in self.stop_words]
        for t in toks:
            if t in opinion_lexicon.positive():
                base["joy"] += 1
            if t in opinion_lexicon.negative():
                base["sadness"] += 1
            if t in ("angry", "mad", "furious", "rage"):
                base["anger"] += 3
            if t in ("afraid", "scared", "fear", "panic"):
                base["fear"] += 4
        return max(base, key=base.get)

    def _extract_topics(self, text: str):
        """Extract topics from text using LDA"""
        try:
            vec = CountVectorizer(stop_words="english", max_features=50)
            clean = " ".join(
                w for w in word_tokenize(text.lower()) if w.isalnum() and w not in self.stop_words
            )
            if not clean or len(clean.split()) < 2:
                return []
            
            dtm = vec.fit_transform([clean])
            lda = LatentDirichletAllocation(n_components=1, random_state=42)
            lda.fit(dtm)
            features = vec.get_feature_names_out()
            topic = lda.components_[0]
            return [features[i] for i in topic.argsort()[:-6:-1]]
        except (ValueError, AttributeError):
            return []