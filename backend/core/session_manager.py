import asyncio


class SessionManager:
    def __init__(self):
        self.active_sessions = {}   # session_id -> task
        self.lock = asyncio.Lock()

    async def start_session(self, session_id, coro):
        async with self.lock:
            if session_id in self.active_sessions:
                print(f" Session {session_id} already running")
                return False

            task = asyncio.create_task(coro)
            self.active_sessions[session_id] = task

            task.add_done_callback(
                lambda t: self.cleanup(session_id)
            )

            return True

    def cleanup(self, session_id):
        self.active_sessions.pop(session_id, None)
        print(f" Cleaned session {session_id}")

    def stop_session(self, session_id):
        task = self.active_sessions.get(session_id)
        if task:
            task.cancel()