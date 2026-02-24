
class DebugSessionManager:
    _active_session_id: str | None = None

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
