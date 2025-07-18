from nltk import word_tokenize, pos_tag
from nltk.corpus import wordnet as wn
from .base_memory import BaseNeo4jMemory

class SemanticMemory(BaseNeo4jMemory):
    """Stores semantic relationships and word meanings"""
    
    def get_wordnet_pos(self, treebank_tag):
        """Convert treebank POS tag to WordNet POS tag"""
        if treebank_tag.startswith('J'):
            return wn.ADJ
        elif treebank_tag.startswith('V'):
            return wn.VERB
        elif treebank_tag.startswith('N'):
            return wn.NOUN
        elif treebank_tag.startswith('R'):
            return wn.ADV
        else:
            return None

    def save(self, text):
        """Save semantic information for words in text"""
        words = word_tokenize(text)
        tagged_words = pos_tag(words)

        with self.driver.session() as neo4j_session:
            for word, tag in tagged_words:
                wn_pos = self.get_wordnet_pos(tag)
                if wn_pos:
                    synsets = wn.synsets(word, pos=wn_pos)
                    if synsets:
                        synset = synsets[0]
                        definition = synset.definition()
                        synonyms = set(lemma.name() for lemma in synset.lemmas())
                        antonyms = set(ant.name() for lemma in synset.lemmas() 
                                     for ant in lemma.antonyms())

                        neo4j_session.run("""
                            MERGE (d:Description:SemanticMemory {description: $definition})
                            WITH d MATCH (w:Word:SensoryMemory_TextBased {word_text: $word})
                            MERGE (w)-[:REFERS_TO]->(d)
                        """, word=word, definition=definition)

                        for synonym in synonyms:
                            neo4j_session.run("""
                                MERGE (s:Synonym:SemanticMemory {synonym: $synonym})
                                WITH s MATCH (w:Word:SensoryMemory_TextBased {word_text: $word})
                                MERGE (w)-[:HAS_SYNONYM]->(s)
                            """, word=word, synonym=synonym)

                        for antonym in antonyms:
                            neo4j_session.run("""
                                MERGE (a:Antonym:SemanticMemory {antonym: $antonym})
                                WITH a MATCH (w:Word:SensoryMemory_TextBased {word_text: $word})
                                MERGE (w)-[:HAS_ANTONYM]->(a)
                            """, word=word, antonym=antonym)

                        hypernyms = synset.hypernyms()
                        if hypernyms:
                            hyper = hypernyms[0].lemmas()[0].name()
                            neo4j_session.run("""
                                MERGE (c:Category:SemanticMemory {name: $hypernym})
                                WITH c MATCH (w:Word:SensoryMemory_TextBased {word_text: $word})
                                MERGE (w)-[:IS_A]->(c)
                            """, word=word, hypernym=hyper)

                        domain = synset.lexname().split(".")[-1]
                        neo4j_session.run("""
                            MERGE (d:Domain:SemanticMemory {domain_name: $domain})
                            WITH d MATCH (w:Word:SensoryMemory_TextBased {word_text: $word})
                            MERGE (w)-[:BELONGS_TO_DOMAIN]->(d)
                        """, word=word, domain=domain)

    def close(self):
        """Close Neo4j connection"""
        self.driver.close() 