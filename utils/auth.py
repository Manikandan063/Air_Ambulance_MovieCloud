# utils/auth.py

from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
from config import settings
from models.user import TokenData
import random
import smtplib
from email.mime.text import MIMEText


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ==============================
# PASSWORD HASHING
# ==============================
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


# ==============================
# JWT TOKEN
# ==============================
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()

    expire = datetime.utcnow() + (expires_delta or timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    ))

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )

    return encoded_jwt


def verify_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        email: str = payload.get("sub")
        role: str = payload.get("role")

        if email is None:
            return None

        return TokenData(email=email, role=role)

    except JWTError:
        return None


# ==============================
# GENERATE OTP
# ==============================
def generate_otp():
    return str(random.randint(100000, 999999))


# ==============================
# SEND EMAIL OTP
# ==============================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "yourgmail@gmail.com"              # CHANGE
SMTP_PASSWORD = "your_app_password_here"           # CHANGE


def send_email_otp(email: str, otp: str):
    subject = "Your Password Reset OTP"
    body = f"Your OTP is: {otp}\nThis OTP expires in 5 minutes.\n\nDo NOT share this OTP with anyone."

    msg = MIMEText(body)
    msg["From"] = SMTP_USERNAME
    msg["To"] = email
    msg["Subject"] = subject

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_USERNAME, email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print("Email Sending Error:", e)
        return False
