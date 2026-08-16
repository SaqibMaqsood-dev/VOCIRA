from pydantic import BaseModel , field_validator , Field ,ConfigDict
from datetime import date
import re 
import phonenumbers
from phonenumbers import NumberParseException
from typing import Optional
from uuid import UUID

# ⁡⁢⁢⁢  --------------------
#   User Response Schema
#   --------------------⁡




class User(BaseModel):
    name            : str
    role            : Optional[str]
    email           : Optional[str]
    password        : Optional[str]
    phone_number    : Optional[str]
    address         : Optional[str]
    location        : Optional[str]
    date_birth      : Optional[date] =  date(2005, 1, 1)

# ⁡⁢⁢⁢    Name  Fields validations ⁡

    
    @field_validator("name")
    @classmethod
    def name_validator(cls , n):
        pattern =  r"^[A-Za-z]+(?: [A-Za-z]+)*$"
        if  not  re.match(pattern ,n ):
            raise ValueError
        return n
        
# ⁡⁢⁢⁢    Email  Fields validations 
# ⁡

    @field_validator("email")
    @classmethod
    def email_validator(cls , e):
        pattern =  r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        
        if not re.match(pattern ,e ):
            raise ValueError("Email must be valid")

        return e

# ⁡⁢⁢⁢      Phone  Fields validations ⁡


    @field_validator("phone_number")
    @classmethod
    def phone(cls , p): 
        try :
            number = phonenumbers.parse(p , "PK")
            if not phonenumbers.is_valid_number(number):
                return "Invalid Number"
            formatted = phonenumbers.format_number( number,  phonenumbers.PhoneNumberFormat.E164 )
            return formatted

        except NumberParseException:
            raise ValueError("Invalid phone number format")
    

# ⁡⁢⁢⁢        Date_Birth  Fields validations 
    #   ⁡
    
    @field_validator("date_birth")
    @classmethod
    def date_birth_validation(cls , dob : date): 
        today = date.today()

        if dob >= today :
            raise ValueError("Date of birth cannot be in the future")
        
        age = today.year - dob.year - ((today.month , today.day) < (dob.month , dob.day))
        
        if age < 18 :
            raise ValueError("User must be at least 18 years old")
        
        if age > 110 :
            raise ValueError("Age seems Unrealistic")

        return dob


    
class UpdateUser(BaseModel):
    name         : str
    role         : str
    email        : str
    password     : str
    phone_number : str
    address      : str
    location     : str
    date_birth   : date


# ⁡⁣⁢⁢ -------------------⁡-
# ⁡⁣⁢⁢ User Response Schema⁡
# ⁡⁣⁢⁢ -------------------⁡-






class ShowUser(BaseModel):
    id: UUID
    name: str
    email: str
    phone_number: str | None = None
    address: str | None = None
    location: str | None = None
    date_birth: date | None = None

    model_config = ConfigDict(from_attributes=True)

class UserPartialUpdate(BaseModel):
    email           : Optional[str]  =  None 
    role            : Optional[str]  =  None 
    password        : Optional[str]  =  None  
    phone_number    : Optional[str]  =  None 
    address         : Optional[str]  =  None 
    location        : Optional[str]  =  None 
    date_birth      : Optional[date] =  None 
    

# class UserPartialUpdate(BaseModel):
#     name            : Optional[str]  =  None 
#     email           : Optional[str]  =  None 
#     password        : Optional[str]  =  None  
#     phone_number    : Optional[str]  =  None 
#     role            : Optional[str]  =  None  
#     address         : Optional[str]  =  None 
#     location        : Optional[str]  =  None 





class LiveKitToken(BaseModel):
 room     : str = "vocira-room"


class LivekitTokkenResponse(BaseModel):
    tokken : str
    room   : str
    url    : str


class _AuthResponse(BaseModel):
    acess_token : str
    barrer      : str
    
