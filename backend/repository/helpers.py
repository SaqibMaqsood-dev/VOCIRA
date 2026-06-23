from fastapi import FastAPI



class Helpers:
    def __init__(self):
        pass

    @staticmethod

    async def creating(data , db):
        db.add(data)
        await db.commit()
        await db.refresh(data)
        return data