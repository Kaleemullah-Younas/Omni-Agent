import aiml
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from glob import glob
import hashlib
import re
import dns.resolver
import os
import requests
import base64
import io
import wave
import time
import uuid
from datetime import datetime
from threading import Thread
from memories import MemoryManager
from chat_logger import ChatLogger
from neo4j import GraphDatabase
from simple_gender_predictor import simple_gender_predictor as gender_predictor
from relationship_manager import relationship_manager
import speech_recognition as sr
import pyttsx3

def get_user_real_ip():
    """Get the user's real public IP address"""
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
        if ip and ip != '127.0.0.1' and ip != 'localhost':
            return ip
    
    if request.headers.get('X-Real-IP'):
        ip = request.headers.get('X-Real-IP')
        if ip and ip != '127.0.0.1' and ip != 'localhost':
            return ip
    
    if request.remote_addr in ['127.0.0.1', '::1', 'localhost']:
        try:
            response = requests.get("https://api.ipify.org", timeout=5)
            if response.status_code == 200:
                return response.text.strip()
        except:
            try:
                response = requests.get("https://httpbin.org/ip", timeout=5)
                if response.status_code == 200:
                    return response.json().get('origin', '').split(',')[0].strip()
            except:
                return request.remote_addr
    
    return request.remote_addr

def get_location_from_ip(ip_address):
    """Get location information from IP address"""
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

def hash_password(pwd: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(pwd.encode()).hexdigest()

def _valid_domain(email: str) -> bool:
    """Check if email domain has valid MX records"""
    try:
        dns.resolver.resolve(email.split("@")[1], 'MX')
        return True
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return False

def valid_email(email: str) -> bool:
    """Validate email format and domain"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None and _valid_domain(email)

def connect_neo4j():
    """Connect to Neo4j database"""
    return GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "12345678"))

def get_username(email):
    """Get username from Neo4j by email"""
    driver = connect_neo4j()
    neo4j_session = driver.session()
    try:
        query = "MATCH (u:User{email: $email}) RETURN u.name"
        result = neo4j_session.run(query, email=email).data()
        return result[0]['u.name'] if result else None
    except Exception as e:
        print(f"Error getting username: {e}")
        return None
    finally:
        neo4j_session.close()

def validate_relationship_from_csv(relationship):
    """Validate if relationship exists using relationship patterns from relationship_manager"""
    try:
        # Use the relationship patterns from relationship_manager
        all_valid_relationships = []
        for rel_type, patterns in relationship_manager.relationship_patterns.items():
            all_valid_relationships.extend(patterns)
            all_valid_relationships.append(rel_type)
        
        # Also add common relationship variations
        additional_relationships = ['grandpa', 'grandma', 'granny', 'papa', 'mama', 'daddy', 'mommy']
        all_valid_relationships.extend(additional_relationships)
        
        return relationship.lower() in [rel.lower() for rel in all_valid_relationships]
    except Exception as e:
        print(f"Error validating relationship: {e}")
        # Fallback to common relationships if validation fails
        common_relationships = ['father', 'mother', 'brother', 'sister', 'son', 'daughter', 
                              'husband', 'wife', 'uncle', 'aunt', 'cousin', 'friend', 
                              'grandfather', 'grandmother', 'nephew', 'niece']
        return relationship.lower() in common_relationships

def deduplicate_response(response):
    """Remove duplicate sentences from bot response"""
    if not response or len(response.strip()) == 0:
        return "I'm not sure how to respond to that."
    
    # Split response into sentences
    sentences = []
    for delimiter in ['. ', '! ', '? ']:
        if delimiter in response:
            parts = response.split(delimiter)
            for i, part in enumerate(parts):
                if i < len(parts) - 1:  # Add delimiter back except for last part
                    part += delimiter.strip()
                if part.strip():
                    sentences.append(part.strip())
            break
    else:
        # No sentence delimiters found, treat as single sentence
        sentences = [response.strip()]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_sentences = []
    for sentence in sentences:
        sentence_clean = sentence.lower().strip().rstrip('.!?')
        if sentence_clean and sentence_clean not in seen:
            seen.add(sentence_clean)
            unique_sentences.append(sentence)
    
    # Join sentences back
    result = ' '.join(unique_sentences)
    
    # Clean up extra spaces and ensure proper punctuation
    result = ' '.join(result.split())  # Remove extra whitespace
    if result and not result[-1] in '.!?':
        result += '.'
    
    return result if result else "I'm not sure how to respond to that."

def get_user_greeting(username):
    """Get appropriate greeting based on user's predicted gender"""
    try:
        predicted_gender = gender_predictor.predict_gender(username)
        return "Ma'am" if predicted_gender == 'female' else "Sir"
    except:
        return "Sir"  # Default fallback

def handle_relationship_query(query, username):
    """Handle dynamic relationship queries"""
    import re
    greeting = get_user_greeting(username)
    
    # Check for yes/no verification patterns first
    verification_patterns = [
        r"is ([a-zA-Z\s]+?) my ([a-zA-Z\s]+?)(?:\?|$)"
    ]
    
    for pattern in verification_patterns:
        match = re.search(pattern, query.lower())
        if match:
            person_name = match.group(1).strip().title()
            relationship = match.group(2).strip()
            
            if not validate_relationship_from_csv(relationship):
                return f"{greeting}, I apologize, but '{relationship}' is not a relationship type I can recognize."
            
            try:
                user_relationships = relationship_manager.get_user_relationships(username)
                for rel in user_relationships:
                    rel_type = rel.get('relationship', '').lower()
                    rel_person = rel.get('person_name', '').lower()
                    if ((rel_type == relationship.lower() or 
                         rel_type == relationship.lower().replace(' ', '_') or
                         rel_type.replace('_', ' ') == relationship.lower()) and
                        rel_person == person_name.lower()):
                        return f"Yes {greeting}, {person_name} is indeed your {relationship}."
                
                return f"No {greeting}, {person_name} is not your {relationship}."
            except:
                return f"No, {person_name} is not your {relationship}."
    
    # Check for age query patterns
    age_query_patterns = [
        r"how old am i(?:\?|$)",
        r"what is my age(?:\?|$)",
        r"what is ([a-zA-Z\s]+?) age(?:\?|$)",
        r"what is the age of ([a-zA-Z\s]+?)(?:\?|$)",
        r"how old is ([a-zA-Z\s]+?)(?:\?|$)",
        r"age of ([a-zA-Z\s]+?)(?:\?|$)"
    ]
    
    for pattern in age_query_patterns:
        match = re.search(pattern, query.lower())
        if match:
            if query.lower().startswith('how old am i') or query.lower().startswith('what is my age'):
                person_name = 'me'
            else:
                person_name = match.group(1).strip().title()
            
            try:
                # Handle "my age" queries
                if person_name.lower() in ['my', 'me', 'myself'] or query.lower().startswith('how old am i'):
                    age = relationship_manager.get_person_age(username, username)
                else:
                    age = relationship_manager.get_person_age(username, person_name)
                
                if age:
                    if person_name.lower() in ['my', 'me', 'myself'] or query.lower().startswith('how old am i'):
                        return f"{greeting}, you are {age} years old."
                    else:
                        return f"{greeting}, {person_name} is {age} years old."
                else:
                    if person_name.lower() in ['my', 'me', 'myself'] or query.lower().startswith('how old am i'):
                        return f"{greeting}, I don't have your age information yet. Would you like to tell me?"
                    else:
                        return f"{greeting}, I don't have {person_name}'s age information."
            except:
                return f"{greeting}, I don't have {person_name}'s age information."
    
    # Check for counting patterns
    counting_patterns = [
        r"how many ([a-zA-Z\s]+?) do i have(?:\?|$)",
        r"how many ([a-zA-Z\s]+?) i have(?:\?|$)",
        r"count my ([a-zA-Z\s]+?)(?:\?|$)"
    ]
    
    for pattern in counting_patterns:
        match = re.search(pattern, query.lower())
        if match:
            relationship = match.group(1).strip()
            
            # Handle plural forms
            singular_relationship = relationship.rstrip('s') if relationship.endswith('s') else relationship
            if not validate_relationship_from_csv(singular_relationship):
                return f"{greeting}, I apologize, but '{relationship}' is not a relationship type I can recognize."
            
            try:
                user_relationships = relationship_manager.get_user_relationships(username)
                count = 0
                
                for rel in user_relationships:
                    rel_type = rel.get('relationship', '').lower()
                    if (rel_type == singular_relationship.lower() or 
                        rel_type == singular_relationship.lower().replace(' ', '_') or
                        rel_type.replace('_', ' ') == singular_relationship.lower()):
                        count += 1
                
                if count == 0:
                    return f"{greeting}, you don't have any {relationship} in my records."
                elif count == 1:
                    return f"{greeting}, you have 1 {relationship.rstrip('s')} in my records."
                else:
                    return f"{greeting}, you have {count} {relationship} in my records."
            except:
                return f"Sir, you don't have any {relationship} in my records."
    
    # Extract relationship from query patterns
    patterns = [
        r"who is my ([a-zA-Z\s]+?)(?:\?|$)",
        r"who are my ([a-zA-Z\s]+?)(?:\?|$)",
        r"what is the name of my ([a-zA-Z\s]+?)(?:\?|$)",
        r"what is my ([a-zA-Z\s]+?) name(?:\?|$)",
        r"do you know my ([a-zA-Z\s]+?)(?:\?|$)",
        r"tell me about my ([a-zA-Z\s]+?)(?:\?|$)"
    ]
    
    relationship = None
    for pattern in patterns:
        match = re.search(pattern, query.lower())
        if match:
            relationship = match.group(1).strip()
            break
    
    if not relationship:
        return None
    
    # Handle plural forms and validate relationship
    singular_relationship = relationship.rstrip('s') if relationship.endswith('s') else relationship
    if not validate_relationship_from_csv(singular_relationship):
        return f"{get_user_greeting(username)}, I apologize, but '{relationship}' is not a relationship type I can recognize."
    
    # Query the database for this relationship
    try:
        user_relationships = relationship_manager.get_user_relationships(username)
        matching_relationships = []
        
        for rel in user_relationships:
            rel_type = rel.get('relationship', '').lower()
            if (rel_type == singular_relationship.lower() or 
                rel_type == singular_relationship.lower().replace(' ', '_') or
                rel_type.replace('_', ' ') == singular_relationship.lower()):
                person_name = rel.get('person_name', '')
                matching_relationships.append(person_name)
        
        if matching_relationships:
            if len(matching_relationships) == 1:
                return f"{greeting}, your {relationship}'s name is {matching_relationships[0]}."
            else:
                if len(matching_relationships) == 2:
                    return f"{greeting}, your {relationship}s are {matching_relationships[0]} and {matching_relationships[1]}."
                else:
                    names = ', '.join(matching_relationships[:-1]) + f" and {matching_relationships[-1]}"
                    return f"{greeting}, your {relationship}s are {names}."
        
        return f"{greeting}, I don't have information about your {relationship}. Would you like to tell me about them?"
        
    except Exception as e:
        print(f"Error querying relationship: {e}")
        return f"{greeting}, I don't have information about your {relationship}. Would you like to tell me about them?"

def check_credentials(email, password):
    """Check user credentials in Neo4j"""
    hashed_password = hash_password(password)
    driver = connect_neo4j()
    neo4j_session = driver.session()
    try:
        query = """
        MATCH (u:User{email: $email, password: $password}) 
        SET u.id = COALESCE(u.id, u.name)
        RETURN u.name
        """
        result = neo4j_session.run(query, email=email, password=hashed_password).data()
        return result[0]['u.name'] if result else None
    except Exception as e:
        print(f"Error checking credentials: {e}")
        return None
    finally:
        neo4j_session.close()
        driver.close()

def store_credentials(name, email, password):
    """Store user credentials in Neo4j"""
    hashed_password = hash_password(password)
    driver = connect_neo4j()
    neo4j_session = driver.session()
    try:
        predicted_gender = gender_predictor.predict_gender(name)
        gender_confidence = gender_predictor.predict_with_confidence(name)[1]
        
        query = """
        MERGE (u:User {email: $email})
        SET u.name = $name, u.password = $password, u.id = $name, 
            u.gender = $gender, u.gender_confidence = $confidence
        """
        neo4j_session.run(query, name=name, email=email, password=hashed_password, 
                          gender=predicted_gender, confidence=gender_confidence)
        
        fact_dir = "prolog/facts"
        os.makedirs(fact_dir, exist_ok=True)
        fact_path = os.path.join(fact_dir, f"{email.replace('@', '_at_')}.pl")
        with open(fact_path, "w") as f:
            f.write(f"% Facts for {email}\n")
        
        return True
    except Exception as e:
        print(f"Error storing credentials: {e}")
        return False
    finally:
        neo4j_session.close()

def user_exists(email):
    """Check if user exists in Neo4j"""
    driver = connect_neo4j()
    neo4j_session = driver.session()
    try:
        query = "MATCH (u:User{email: $email}) RETURN u.email"
        result = neo4j_session.run(query, email=email).data()
        return len(result) > 0
    except Exception as e:
        print(f"Error checking user existence: {e}")
        return False
    finally:
        neo4j_session.close()
        driver.close()

# Initialize components
memory_manager = MemoryManager(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="12345678",
    kb_file="prolog/kb.pl"
)

chat_logger = ChatLogger()
myBot = aiml.Kernel()
app = Flask(__name__, static_folder='static/images', static_url_path='/images')
app.secret_key = 'your-secret-key'

# Hardware management globals
hardware_devices = {}  # Track connected ESP32 devices
hardware_commands = {}  # Pending commands for devices
tts_engine = pyttsx3.init()

# Initialize speech recognition
recognizer = sr.Recognizer()

# Load AIML files
for file in glob("aiml files/*.aiml"):
    myBot.learn(file)

@app.route("/")
def home():
    # Force check if user actually exists in database
    if 'email' in session and 'username' in session:
        # Verify user still exists in Neo4j
        if not user_exists(session['email']):
            session.clear()
            return redirect(url_for('login'))
            
        predicted_gender = gender_predictor.predict_gender(session['username'])
        gender_confidence = gender_predictor.predict_with_confidence(session['username'])[1]
        
        return render_template("home.html", 
                             username=session['username'],
                             predicted_gender=predicted_gender,
                             gender_confidence=round(gender_confidence * 100, 1))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")

        username = check_credentials(email, password)
        if username:
            session["email"] = email
            session["username"] = username
            
            fact_file = f"prolog/facts/{email.replace('@', '_at_')}.pl"
            session["fact_file"] = fact_file
            
            session_key = datetime.now().strftime("%Y%m%d_%H%M%S")
            session["session_key"] = session_key
            
            is_returning_user = chat_logger.has_previous_chats(username)
            session["is_returning_user"] = is_returning_user
            
            # Always set username predicate for name validation
            myBot.setPredicate("username", username)
            myBot.setPredicate("name", username)
            
            # Load existing relationships into AIML predicates
            try:
                user_relationships = relationship_manager.get_user_relationships(username)
                for rel in user_relationships:
                    rel_type = rel.get('relationship', '').lower()
                    person_name = rel.get('person_name', '')
                    if rel_type and person_name:
                        myBot.setPredicate(f"{rel_type}_name", person_name)
            except Exception as e:
                print(f"Error loading relationships: {e}")
            
            if is_returning_user:
                try:
                    context = memory_manager.load_previous_context(username, myBot, chat_logger)
                    session["context_loaded"] = context is not None
                    myBot.setPredicate("returning_user", "true")
                    myBot.setPredicate("new_user", "false")
                except:
                    session["context_loaded"] = False
                    myBot.setPredicate("returning_user", "false")
                    myBot.setPredicate("new_user", "true")
            else:
                session["context_loaded"] = False
                myBot.setPredicate("returning_user", "false")
                myBot.setPredicate("new_user", "true")
            
            return redirect(url_for('home') + '?success=login')
        else:
            return redirect(url_for('login') + '?error=invalid')

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            return redirect(url_for('signup') + '?error=password_mismatch')

        if user_exists(email):
            return redirect(url_for('signup') + '?error=email_exists')

        if not valid_email(email):
            return redirect(url_for('signup') + '?error=invalid_email')

        if store_credentials(name, email, password):
            return redirect(url_for('login') + '?success=signup')
        else:
            return redirect(url_for('signup') + '?error=signup_failed')

    return render_template('signup.html')

@app.route("/get")
def get_bot_response():
    if "email" not in session or "username" not in session:
        return "Please log in to use the bot."
    
    # Double check user exists in database
    if not user_exists(session['email']):
        session.clear()
        return "Your session has expired. Please log in again."
    
    query = request.args.get('msg')
    if not query:
        return "No message received."
    
    # Reload knowledge base
    try:
        memory_manager.social.reload_kb("prolog/kb.pl")
        if session.get("fact_file"):
            memory_manager.social.load_user_facts(session["fact_file"])
    except:
        pass
    
    # Get user IP and location
    user_ip = get_user_real_ip()
    user_location = get_location_from_ip(user_ip)

    # Process input through memory systems
    try:
        memory_manager.async_process_input(
            text=query,
            ip_address=user_ip,
            user_id=session["username"],
            user_fact_file=session.get("fact_file"),
            session_key=session.get("session_key")
        )
    except:
        pass

    # Set up social memory references
    memory_manager.social.myBot = myBot
    memory_manager.social.session = session
    
    # Ensure username predicate is always set for name validation
    myBot.setPredicate("username", session["username"])
    myBot.setPredicate("name", session["username"])
    
    # Load existing relationships into AIML predicates ONCE
    try:
        user_relationships = relationship_manager.get_user_relationships(session["username"])
        for rel in user_relationships:
            rel_type = rel.get('relationship', '').lower()
            person_name = rel.get('person_name', '')
            if rel_type and person_name:
                myBot.setPredicate(f"{rel_type}_name", person_name)
    except:
        pass
    
    # Process AIML predicates
    try:
        memory_manager.social.prompt_check()
    except:
        pass
    
    # Process relationships ONCE and collect all messages
    relationship_messages = []
    final_response = None
    
    try:
        relationship_result = relationship_manager.process_user_input(query, session["username"])
        
        # Handle name validation conflicts first (highest priority)
        if relationship_result.get('conflicts'):
            for conflict in relationship_result['conflicts']:
                if conflict.get('type') == 'name_validation':
                    final_response = conflict.get('message', '')
                    break  # Name validation takes precedence
                elif conflict.get('message') and 'wrong' in conflict.get('message', ''):
                    # If there's a relationship conflict, don't process further
                    final_response = conflict.get('message', '')
                    break
        
        # Only handle relationship messages if no conflicts
        if not final_response and relationship_result.get('relationships'):
            for rel in relationship_result['relationships']:
                if rel.get('message'):
                    relationship_messages.append(rel.get('message'))
                # Set AIML predicates for new relationships
                rel_type = rel.get('relationship_type', '').lower()
                person_name = rel.get('person_name', '')
                if rel_type and person_name:
                    myBot.setPredicate(f"{rel_type}_name", person_name)
    except:
        pass
    
    # If no conflict response, check for relationship query or get bot response
    if not final_response:
        relationship_response = handle_relationship_query(query, session["username"])
        if relationship_response:
            final_response = relationship_response
        elif relationship_messages:
            # If we have relationship messages, use them as the response
            unique_messages = list(dict.fromkeys([msg.strip() for msg in relationship_messages if msg.strip()]))
            final_response = ' '.join(unique_messages) if unique_messages else "Thank you for the information."
        else:
            # Get bot response only once
            final_response = myBot.respond(query) or "I'm not sure how to respond to that."
    
    # Set sentiment
    try:
        memory_manager.social.set_sentiment()
    except:
        pass
    
    # Clean up response - remove duplicate sentences
    final_response = deduplicate_response(final_response)
    
    # If response contains relationship/age info, don't add AIML fallback
    if any(phrase in final_response.lower() for phrase in ['noted that', 'years old', 'thank you for']):
        # Remove any trailing fallback responses
        sentences = final_response.split('. ')
        filtered_sentences = []
        for sentence in sentences:
            if not any(fallback in sentence.lower() for fallback in ['couldn\'t catch', 'don\'t understand', 'how you are feeling', 'how is your mood']):
                filtered_sentences.append(sentence)
        final_response = '. '.join(filtered_sentences)
        if final_response and not final_response.endswith(('.', '!', '?')):
            final_response += '.'
    
    # Clear AIML predicates
    try:
        predicates_to_clear = [
            "mood", "word", "dob_person", "age_person", "gender_person",
            "rel", "person1", "person2", "gender", "dob", "relation", "person",
            "other_dob_person", "other_dob", "other_gender_person", "other_gender",
            "other_person1", "other_person2", "other_relation", "description"
        ]
        for key in predicates_to_clear:
            myBot.setPredicate(key, "")
    except:
        pass
    
    # Log chat interaction
    try:
        chat_logger.append(
            session_key=session["session_key"],
            username=session["username"],
            user_msg=query,
            bot_msg=final_response)
    except:
        pass

    return final_response

@app.route("/user_stats")
def get_user_stats():
    """Get user statistics including chat summary and IP history"""
    if "email" not in session:
        return redirect(url_for('login'))
    
    try:
        username = session["username"]
        chat_summary = memory_manager.get_user_chat_summary(username)
        ip_history = memory_manager.get_user_ip_history(username, limit=5)
        recent_episodes = memory_manager.recall_episodes(username, limit=3)
        relationships = relationship_manager.get_user_relationships(username)
        
        return render_template('user_stats.html',
                             username=username,
                             chat_summary=chat_summary,
                             recent_ip_locations=ip_history,
                             recent_episodes=recent_episodes,
                             relationships=relationships)
        
    except Exception as e:
        return f"Error retrieving user stats: {e}"

@app.route("/relationships")
def get_relationships():
    """Get user's relationship graph"""
    if "email" not in session:
        return redirect(url_for('login'))
    
    try:
        username = session["username"]
        relationships = relationship_manager.get_user_relationships(username)
        relationship_graph = relationship_manager.get_relationship_graph(username)
        
        return render_template('relationships.html',
                             username=username,
                             relationships=relationships,
                             relationship_graph=relationship_graph)
        
    except Exception as e:
        return f"Error retrieving relationships: {e}"

@app.route('/graph_visualization')
def graph_visualization():
    """Display Neo4j graph visualization page"""
    if 'email' not in session:
        return redirect(url_for('login'))
    
    return render_template('graph_visualization.html', username=session['username'])

@app.route('/social_memory')
def social_memory():
    """Display social memory relationship visualization"""
    if 'email' not in session:
        return redirect(url_for('login'))
    
    try:
        username = session['username']
        relationships = relationship_manager.get_user_relationships(username)
        
        return render_template('social_memory.html',
                             username=username,
                             relationships=relationships)
        
    except Exception as e:
        return f"Error retrieving social memory: {e}"

@app.route('/api/social_graph')
def get_social_graph_data():
    """API endpoint to fetch relationship graph data for social memory visualization"""
    if 'email' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        username = session['username']
        driver = connect_neo4j()
        neo4j_session = driver.session()
        
        # Get user and their relationships
        query = """
        MATCH (u:User {name: $username})
        OPTIONAL MATCH (u)-[r]->(p:Person)
        RETURN u.name as user_name, 
               collect({person: p.name, relationship: type(r), gender: p.gender}) as relationships
        """
        result = neo4j_session.run(query, username=username).single()
        
        nodes = []
        edges = []
        
        if result:
            # Add user node
            nodes.append({
                "id": result['user_name'],
                "label": result['user_name'],
                "color": "#ff6b6b",
                "size": 30,
                "group": "user"
            })
            
            # Add person nodes and relationships
            for rel in result['relationships']:
                if rel['person']:
                    # Determine color based on gender
                    color = "#4ecdc4" if rel['gender'] == 'male' else "#ff9ff3" if rel['gender'] == 'female' else "#95a5a6"
                    
                    nodes.append({
                        "id": rel['person'],
                        "label": rel['person'],
                        "color": color,
                        "size": 20,
                        "group": "person"
                    })
                    
                    edges.append({
                        "from": result['user_name'],
                        "to": rel['person'],
                        "label": rel['relationship'].lower(),
                        "color": "#666",
                        "arrows": "to"
                    })
        
        return jsonify({
            "nodes": nodes,
            "edges": edges
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to fetch social graph: {str(e)}"}), 500
    finally:
        try:
            neo4j_session.close()
            driver.close()
        except:
            pass

@app.route('/api/graph_data')
def get_graph_data():
    """API endpoint to fetch Neo4j graph data for visualization"""
    if 'email' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        driver = connect_neo4j()
        neo4j_session = driver.session()
    except Exception as e:
        return jsonify({"error": "Database connection failed"}), 503
    
    try:
        # Get nodes with labels and properties
        nodes_query = """
        MATCH (n)
        RETURN elementId(n) as id, labels(n) as labels, properties(n) as properties
        LIMIT 500
        """
        nodes_result = neo4j_session.run(nodes_query)
        
        # Get relationships
        edges_query = """
        MATCH (n1)-[r]->(n2)
        RETURN elementId(n1) as source, elementId(n2) as target, type(r) as type, properties(r) as properties
        LIMIT 1000
        """
        edges_result = neo4j_session.run(edges_query)
        
        # Format nodes for visualization
        nodes = []
        for record in nodes_result:
            node_id = record['id']
            labels = record['labels']
            properties = record['properties']
            
            # Create display label
            display_label = ""
            if 'name' in properties:
                display_label = properties['name']
            elif 'email' in properties:
                display_label = properties['email']
            elif 'sentence_text' in properties:
                display_label = properties['sentence_text'][:50] + "..." if len(properties['sentence_text']) > 50 else properties['sentence_text']
            elif 'full_text' in properties:
                display_label = properties['full_text'][:30] + "..." if len(properties['full_text']) > 30 else properties['full_text']
            else:
                display_label = f"{labels[0] if labels else 'Node'} {node_id}"
            
            # Assign colors based on node type
            color = "#97c2fc"
            if "User" in labels:
                color = "#ff6b6b"
            elif "Person" in labels:
                color = "#4ecdc4"
            elif "Text" in labels or "SensoryMemory" in labels:
                color = "#ffe66d"
            elif "Sentence" in labels:
                color = "#a8e6cf"
            elif "Word" in labels:
                color = "#dcedc1"
            elif "Concept" in labels:
                color = "#ffd93d"
            elif "Memory" in labels:
                color = "#ff8b94"
            
            nodes.append({
                "id": node_id,
                "label": display_label,
                "color": color,
                "title": f"Type: {', '.join(labels)}\nProperties: {str(properties)[:200]}",
                "group": labels[0] if labels else "Unknown"
            })
        
        # Format edges for visualization
        edges = []
        for record in edges_result:
            edges.append({
                "from": record['source'],
                "to": record['target'],
                "label": record['type'],
                "title": f"Type: {record['type']}\nProperties: {str(record['properties'])}"
            })
        
        return jsonify({
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges)
            }
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to fetch graph data: {str(e)}"}), 500
    finally:
        try:
            neo4j_session.close()
            driver.close()
        except:
            pass

@app.route('/migrate_social_memory')
def migrate_social_memory():
    """Add SocialMemory labels to existing Person nodes"""
    if 'email' not in session:
        return redirect(url_for('login'))
    
    try:
        result = relationship_manager.migrate_existing_person_nodes_to_social_memory()
        return f"Successfully migrated {result} person nodes to have SocialMemory labels."
    except Exception as e:
        return f"Error during migration: {e}"

@app.route('/migrate_sensory_memory')
def migrate_sensory_memory():
    """Update existing SensoryMemory labels to SensoryMemory_TextBased"""
    if 'email' not in session:
        return redirect(url_for('login'))
    
    try:
        driver = connect_neo4j()
        neo4j_session = driver.session()
        
        # Update existing SensoryMemory nodes to have SensoryMemory_TextBased label
        text_result = neo4j_session.run("""
            MATCH (n:Text:SensoryMemory)
            WHERE NOT n:SensoryMemory_TextBased
            SET n:SensoryMemory_TextBased
            REMOVE n:SensoryMemory
            RETURN count(n) as updated_count
        """).single()
        
        sentence_result = neo4j_session.run("""
            MATCH (n:Sentence:SensoryMemory)
            WHERE NOT n:SensoryMemory_TextBased
            SET n:SensoryMemory_TextBased
            REMOVE n:SensoryMemory
            RETURN count(n) as updated_count
        """).single()
        
        word_result = neo4j_session.run("""
            MATCH (n:Word:SensoryMemory)
            WHERE NOT n:SensoryMemory_TextBased
            SET n:SensoryMemory_TextBased
            REMOVE n:SensoryMemory
            RETURN count(n) as updated_count
        """).single()
        
        neo4j_session.close()
        driver.close()
        
        text_count = text_result['updated_count'] if text_result else 0
        sentence_count = sentence_result['updated_count'] if sentence_result else 0
        word_count = word_result['updated_count'] if word_result else 0
        
        return f"Successfully migrated sensory memory nodes:<br>Text nodes: {text_count}<br>Sentence nodes: {sentence_count}<br>Word nodes: {word_count}"
    except Exception as e:
        return f"Error during migration: {e}"

# ==================== HARDWARE ENDPOINTS ====================

@app.route('/api/hardware/heartbeat', methods=['POST'])
def hardware_heartbeat():
    """Receive heartbeat from ESP32 devices"""
    try:
        data = request.get_json()
        print(f"Received heartbeat data: {data}")  # Debug print
        
        device_id = data.get('device_id')
        
        if not device_id:
            print("Missing device_id in heartbeat")  # Debug print
            return jsonify({"error": "Missing device_id"}), 400
        
        # Update device status
        hardware_devices[device_id] = {
            'last_seen': datetime.now(),
            'status': data.get('status', 'unknown'),
            'temperature': data.get('temperature'),
            'humidity': data.get('humidity'),
            'pressure': data.get('pressure'),
            'wifi_rssi': data.get('wifi_rssi'),
            'timestamp': data.get('timestamp')
        }
        
        # Store sensor data in Neo4j with SensoryMemory_SensorBased label (overwrites existing)
        try:
            memory_manager.sensory.save_sensor_data(
                device_id=device_id,
                temperature=data.get('temperature'),
                humidity=data.get('humidity'),
                pressure=data.get('pressure'),
                wifi_rssi=data.get('wifi_rssi'),
                timestamp=datetime.now().isoformat()
            )
        except Exception as e:
            print(f"Error storing sensor data to Neo4j: {e}")
        
        print(f"Updated device {device_id}: temp={data.get('temperature')}°C, humidity={data.get('humidity')}%, pressure={data.get('pressure')}hPa")  # Debug print
        
        return jsonify({
            "status": "success",
            "message": "Heartbeat received",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"Error in hardware heartbeat: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/hardware/trigger_speak/<device_id>', methods=['POST'])
def trigger_speak_button(device_id):
    """Trigger audio capture and send to ESP32 when button is pressed"""
    try:
        # Update device LED to indicate listening mode
        send_hardware_command(device_id, 'set_led', {'color': 'blue'})
        
        # Capture audio from computer microphone and send to ESP32 for playback
        return trigger_hardware_speak(device_id)
        
    except Exception as e:
        print(f"Error in trigger speak button: {e}")
        send_hardware_command(device_id, 'set_led', {'color': 'red'})
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/hardware/commands/<device_id>', methods=['GET'])
def get_hardware_commands(device_id):
    """Get pending commands for a specific device"""
    try:
        commands = hardware_commands.get(device_id, [])
        
        if commands:
            # Return the first command and remove it from queue
            command = commands.pop(0)
            if not commands:  # If queue is empty, remove the key
                del hardware_commands[device_id]
            return jsonify(command)
        else:
            return jsonify({"message": "No pending commands"}), 204
            
    except Exception as e:
        print(f"Error getting hardware commands: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/hardware/commands/ack', methods=['POST'])
def acknowledge_hardware_command():
    """Acknowledge command completion from device"""
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        command_id = data.get('command_id')
        status = data.get('status')
        
        print(f"Command {command_id} for device {device_id} completed with status: {status}")
        
        return jsonify({"status": "acknowledged"})
        
    except Exception as e:
        print(f"Error acknowledging hardware command: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/hardware/status')
def get_hardware_status():
    """Get status of all connected hardware devices"""
    try:
        current_time = datetime.now()
        device_list = []
        
        print(f"Hardware status check - Found {len(hardware_devices)} devices: {list(hardware_devices.keys())}")  # Debug print
        
        for device_id, device_info in hardware_devices.items():
            # Check if device is online (last seen within 30 seconds)
            time_diff = current_time - device_info['last_seen']
            is_online = time_diff.total_seconds() < 30
            
            print(f"Device {device_id}: last_seen={device_info['last_seen']}, time_diff={time_diff.total_seconds()}s, online={is_online}")  # Debug print
            
            device_list.append({
                'device_id': device_id,
                'online': is_online,
                'last_seen': device_info['last_seen'].isoformat(),
                'temperature': device_info.get('temperature'),
                'humidity': device_info.get('humidity'),
                'pressure': device_info.get('pressure'),
                'wifi_rssi': device_info.get('wifi_rssi')
            })
        
        response_data = {
            "devices": device_list,
            "timestamp": current_time.isoformat()
        }
        
        print(f"Sending hardware status response: {response_data}")  # Debug print
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error getting hardware status: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/hardware/speak/<device_id>', methods=['POST'])
def trigger_hardware_speak(device_id):
    """Capture microphone audio, process through bot, and send response to ESP32"""
    try:
        import pyaudio
        import time
        
        # Update device LED to indicate listening
        send_hardware_command(device_id, 'set_led', {'color': 'blue'})
        
        # Audio capture settings
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1  # Mono
        RATE = 16000
        RECORD_SECONDS = 5  # Record for 5 seconds to capture user speech
        
        # Initialize PyAudio
        p = pyaudio.PyAudio()
        
        # Use default microphone input device
        try:
            default_device = p.get_default_input_device_info()['index']
            print(f"Using microphone device: {p.get_device_info_by_index(default_device)['name']}")
        except:
            print("No default input device found")
            return jsonify({"error": "No microphone device found"}), 500
        
        # Open audio stream for microphone capture
        stream = p.open(format=FORMAT,
                       channels=CHANNELS,
                       rate=RATE,
                       input=True,
                       input_device_index=default_device,
                       frames_per_buffer=CHUNK)
        
        print("Recording user speech...")
        send_hardware_command(device_id, 'set_led', {'color': 'amber'})  # Indicate recording
        
        frames = []
        
        # Record audio for specified duration
        for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
            except Exception as e:
                print(f"Error reading audio frame: {e}")
                break
        
        print("Finished recording user speech")
        
        # Stop and close stream
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        # Process captured audio
        audio_data = b''.join(frames)
        if audio_data:
            # Update LED to indicate processing
            send_hardware_command(device_id, 'set_led', {'color': 'purple'})
            
            # Convert to WAV format for speech recognition
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(RATE)
                wav_file.writeframes(audio_data)
            
            wav_buffer.seek(0)
            
            # Perform speech recognition
            with sr.AudioFile(wav_buffer) as source:
                audio = recognizer.record(source)
                try:
                    # Use Google Speech Recognition
                    text = recognizer.recognize_google(audio)
                    print(f"User speech recognized: {text}")
                    
                    # Process through bot
                    bot_response = process_hardware_message(text, device_id)
                    
                    # Convert bot response to speech and send to ESP32
                    audio_response = text_to_speech(bot_response)
                    if audio_response:
                        send_hardware_command(device_id, 'play_audio', {'audio_data': audio_response})
                        send_hardware_command(device_id, 'set_led', {'color': 'green'})  # Success
                        
                        return jsonify({
                            "status": "success",
                            "recognized_text": text,
                            "bot_response": bot_response,
                            "message": "Speech processed and response sent to device"
                        })
                    else:
                        send_hardware_command(device_id, 'set_led', {'color': 'red'})
                        return jsonify({"error": "Failed to generate speech response"}), 500
                        
                except sr.UnknownValueError:
                    send_hardware_command(device_id, 'set_led', {'color': 'red'})
                    # Send error message to ESP32
                    error_audio = text_to_speech("Sorry, I couldn't understand what you said.")
                    if error_audio:
                        send_hardware_command(device_id, 'play_audio', {'audio_data': error_audio})
                    return jsonify({"error": "Could not understand speech"}), 400
                    
                except sr.RequestError as e:
                    send_hardware_command(device_id, 'set_led', {'color': 'red'})
                    error_audio = text_to_speech("Sorry, there was an error with speech recognition.")
                    if error_audio:
                        send_hardware_command(device_id, 'play_audio', {'audio_data': error_audio})
                    return jsonify({"error": f"Speech recognition error: {e}"}), 500
        else:
            send_hardware_command(device_id, 'set_led', {'color': 'red'})
            return jsonify({"error": "No audio data captured"}), 500
            
    except ImportError:
        send_hardware_command(device_id, 'set_led', {'color': 'red'})
        return jsonify({
            "error": "PyAudio not installed. Please install with: pip install pyaudio"
        }), 500
    except Exception as e:
        print(f"Error in click-to-speak: {e}")
        send_hardware_command(device_id, 'set_led', {'color': 'red'})
        return jsonify({"error": f"Failed to process speech: {str(e)}"}), 500

def send_hardware_command(device_id, command, parameters=None):
    """Send command to hardware device"""
    try:
        command_data = {
            'command_id': str(uuid.uuid4()),
            'command': command,
            'timestamp': datetime.now().isoformat()
        }
        
        if parameters:
            command_data.update(parameters)
        
        if device_id not in hardware_commands:
            hardware_commands[device_id] = []
        
        hardware_commands[device_id].append(command_data)
        print(f"Command queued for device {device_id}: {command}")
        
    except Exception as e:
        print(f"Error sending hardware command: {e}")

def process_hardware_message(text, device_id):
    """Process message from hardware device through bot"""
    try:
        # Create a temporary session context for hardware
        hardware_session = {
            'username': f'Hardware_{device_id}',
            'email': f'hardware_{device_id}@local.device',
            'session_key': f'hw_{device_id}_{int(time.time())}',
            'fact_file': f'prolog/facts/hardware_{device_id}.pl'
        }
        
        # Set AIML predicates for hardware session
        myBot.setPredicate("username", hardware_session['username'])
        myBot.setPredicate("name", hardware_session['username'])
        
        # Process through memory systems (similar to web interface)
        try:
            memory_manager.async_process_input(
                text=text,
                ip_address="hardware_device",
                user_id=hardware_session['username'],
                user_fact_file=hardware_session['fact_file']
            )
        except:
            pass
        
        # Get bot response and deduplicate
        response = myBot.respond(text)
        response = deduplicate_response(response)
        
        # Log the interaction
        try:
            chat_logger.append(
                session_key=hardware_session['session_key'],
                username=hardware_session['username'],
                user_msg=text,
                bot_msg=response
            )
        except:
            pass
        
        return response
        
    except Exception as e:
        print(f"Error processing hardware message: {e}")
        return "I'm sorry, there was an error processing your message."

def text_to_speech(text):
    """Convert text to speech and return as base64 encoded audio"""
    try:
        # Use pyttsx3 to generate speech
        tts_engine.setProperty('rate', 150)  # Speed of speech
        tts_engine.setProperty('volume', 0.9)  # Volume level
        
        # Save to temporary file
        temp_filename = f"temp_audio_{uuid.uuid4().hex}.wav"
        tts_engine.save_to_file(text, temp_filename)
        tts_engine.runAndWait()
        
        # Read the file and encode as base64
        if os.path.exists(temp_filename):
            with open(temp_filename, 'rb') as audio_file:
                audio_data = audio_file.read()
                base64_audio = base64.b64encode(audio_data).decode('utf-8')
            
            # Clean up temporary file
            os.remove(temp_filename)
            
            return base64_audio
        else:
            print("Failed to generate TTS audio file")
            return None
            
    except Exception as e:
        print(f"Error in text-to-speech: {e}")
        return None

@app.route("/logout")
def logout():
    """Logout user and clear session"""
    # Close current episodic memory episode before logout
    if "username" in session and "session_key" in session:
        try:
            memory_manager.close_user_episode(
                user_id=session["username"],
                session_key=session["session_key"]
            )
        except:
            pass
    
    # Clear all session data
    session.clear()
    
    # Clear any cached predicates
    try:
        myBot.setPredicate("username", "")
        myBot.setPredicate("name", "")
        myBot.setPredicate("returning_user", "false")
        myBot.setPredicate("new_user", "true")
    except:
        pass
    
    return redirect(url_for('login'))

if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=5001, debug=True)
    finally:
        memory_manager.close()