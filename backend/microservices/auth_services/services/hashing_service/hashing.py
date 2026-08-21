from pwdlib import PasswordHash
import hashlib


















































password_hash = PasswordHash.recommended()


class Hash:
    @staticmethod
    def get_hash_password(password: str):
        print("=========")

        return password_hash.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str):
        print("=========")
        return password_hash.verify(plain_password, hashed_password)
    
    @staticmethod
    
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    