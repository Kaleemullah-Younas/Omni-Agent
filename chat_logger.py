import os
from datetime import datetime
from threading import Lock
import glob

class ChatLogger:
    """Handles chat logging functionality for user sessions"""
    
    _lock = Lock()

    def __init__(self, base_dir: str = "chat_logs"):
        """Initialize chat logger with base directory"""
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self._current_files = {}

    def start_session(self, username: str, session_key: str) -> None:
        """Create a new log file for a user's login session"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{username}_episode_{timestamp}.txt"
        path = os.path.join(self.base_dir, filename)
        open(path, "a", encoding="utf-8").close()
        self._current_files[session_key] = path

    def append(self, session_key: str, username: str, user_msg: str, bot_msg: str) -> None:
        """Append a user-bot conversation turn to the active log file"""
        if session_key not in self._current_files:
            self.start_session(username, session_key)

        user_line = f"{username} : {user_msg}\n"
        bot_line = f"Bot : {bot_msg}\n"

        with ChatLogger._lock:
            with open(self._current_files[session_key], "a", encoding="utf-8") as f:
                f.write(user_line)
                f.write(bot_line)

    def end_session(self, session_key: str) -> None:
        """End session and remove file mapping"""
        self._current_files.pop(session_key, None)
    
    def get_user_chat_files(self, username: str) -> list:
        """Get all chat files for a specific user, sorted by modification time"""
        pattern = os.path.join(self.base_dir, f"{username}_episode_*.txt")
        return sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    
    def get_recent_conversations(self, username: str, limit: int = 10) -> list:
        """Get recent conversations from the most recent chat file"""
        chat_files = self.get_user_chat_files(username)
        if not chat_files:
            return []
        
        conversations = []
        try:
            with open(chat_files[0], 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for i in range(0, len(lines), 2):
                if i + 1 < len(lines):
                    user_line = lines[i].strip()
                    bot_line = lines[i + 1].strip()
                    
                    if " : " in user_line and " : " in bot_line:
                        user_msg = user_line.split(" : ", 1)[1]
                        bot_msg = bot_line.split(" : ", 1)[1]
                        conversations.append({
                            'user_msg': user_msg,
                            'bot_msg': bot_msg
                        })
                        
                        if len(conversations) >= limit:
                            break
            
            return conversations
        except Exception as e:
            print(f"Error reading chat file: {e}")
            return []
    
    def has_previous_chats(self, username: str) -> bool:
        """Check if user has any previous chat history"""
        return len(self.get_user_chat_files(username)) > 0
