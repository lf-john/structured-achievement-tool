class DebugSessionManager:
    _instance = None
    _active_session_id: str = None  # Class-level to be accessed by classmethods

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DebugSessionManager, cls).__new__(cls)
            # We're using _active_session_id as a class variable, so no instance init needed here
        return cls._instance

    @classmethod
    def start_session(cls, session_id: str) -> bool:
        if cls._active_session_id is None:
            cls._active_session_id = session_id
            return True
        return False

    @classmethod
    def end_session(cls, session_id: str) -> bool:
        if cls._active_session_id == session_id:
            cls._active_session_id = None
            return True
        return False

    @classmethod
    def is_active(cls) -> bool:
        return cls._active_session_id is not None

    @classmethod
    def get_active_session_id(cls) -> str | None:
        return cls._active_session_id
