from pydantic import BaseModel 


class LiveKitToken(BaseModel):
 room     : str = "vocira-room"


class LivekitTokkenResponse(BaseModel):
    tokken : str
    room   : str
    url    : str

