import os, base64, time, jwt
from fastapi import FastAPI, HTTPException, Query, Header, Depends, Body
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from typing import List
from datetime import datetime, timedelta


MASTER_KEY_B64 = "OAn1NzvF8BSeHVc4I85m9XVRpGm8T8KpAfD7TqgmXfE="
DATABASE_URL = "postgresql+psycopg2://postgres:opendoors@localhost:5432/kms"
# DATABASE_URL = "postgresql+psycopg2://postgres:njusko123@localhost:5432/kms"

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class EncryptBody(BaseModel):
    key_id: int
    algorithm: str
    plaintext_b64: str


class SignBody(BaseModel):
    key_id: int
    algorithm: str
    message_b64: str

class VerifyBody(BaseModel):
    key_id: int
    algorithm: str
    message_b64: str
    signature_b64: str



JWT_SECRET = "bakinatajna"
JWT_ALGORITHM = "HS256"
JWT_EXP_MINUTES = 60

def require_roles(allowed_roles: List[str]):
    def dependency(authorization: str = Header(...)):
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        token = authorization.split(" ")[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

        role = payload.get("role")
        if role not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Role '{role}' not allowed")
        return payload
    return dependency


class KeyRecord(Base):
    __tablename__ = "keys"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    kind = Column(String)
    algorithm = Column(String)
    encrypted_secret = Column(Text)
    public_key = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)



class KeyVersion(Base):
    __tablename__ = "key_versions"
    id = Column(Integer, primary_key=True, index=True)
    key_id = Column(Integer, ForeignKey("keys.id"), nullable=False)
    version = Column(Integer, nullable=False)
    encrypted_secret = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    key = relationship("KeyRecord", back_populates="versions")

KeyRecord.versions = relationship("KeyVersion", back_populates="key", cascade="all, delete-orphan")


class AuditLog(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, index=True)        
    key_id = Column(Integer, nullable=True)    
    timestamp = Column(DateTime, default=datetime.now())
    details = Column(Text, nullable=True)


Base.metadata.create_all(bind=engine)

if not MASTER_KEY_B64:
    raise RuntimeError("Set MASTER_KEY_B64 env variable (base64-encoded 32 bytes).")

MASTER_KEY = base64.b64decode(MASTER_KEY_B64)
if len(MASTER_KEY) != 32:
    raise RuntimeError("MASTER_KEY_B64 must decode to 32 bytes (AES-256).")

app = FastAPI(title="Key Management API (Postgres)")

def log_action(action: str, key_id: int = None, details: str = None):
    db = SessionLocal()
    log = AuditLog(action=action, key_id=key_id, details=details)
    db.add(log)
    db.commit()
    db.close()

def aesgcm_encrypt(master_key: bytes, plaintext: bytes) -> str:
    aesgcm = AESGCM(master_key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ct).decode()

def aesgcm_decrypt(master_key: bytes, b64: str) -> bytes:
    data = base64.b64decode(b64)
    nonce, ct = data[:12], data[12:]
    aesgcm = AESGCM(master_key)
    return aesgcm.decrypt(nonce, ct, None)

class CreateSym(BaseModel):
    name: Optional[str] = None
    bits: Optional[int] = 256

class CreateAsym(BaseModel):
    name: Optional[str] = None
    bits: Optional[int] = 2048

class RotateBody(BaseModel):
    new_master_key_b64: str

class TokenRequest(BaseModel):
    username: str
    role: str

@app.post("/api/token")
def get_token(req: TokenRequest = Body(...)):
    if req.role not in ["admin", "viewer"]:
        raise HTTPException(400, "Role must be 'admin' or 'viewer'")
    
    payload = {
        "username": req.username,
        "role": req.role,
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXP_MINUTES)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"token": token}

@app.post("/api/keys/symmetric")
def create_symmetric(body: CreateSym, _: dict = Depends(require_roles(["admin"]))):
    bits = body.bits or 256
    if bits not in (128, 192, 256):
        raise HTTPException(400, "bits must be 128, 192, or 256")
    key_bytes = os.urandom(bits // 8)
    enc = aesgcm_encrypt(MASTER_KEY, key_bytes)
    rec = KeyRecord(
        name=body.name or f"sym-{int(time.time())}",
        kind="SYMMETRIC",
        algorithm=f"AES-{bits}",
        encrypted_secret=enc
    )
    db = SessionLocal(); db.add(rec); db.commit(); db.refresh(rec); db.close()
    log_action("CREATE_KEY", rec.id, f"algorithm={rec.algorithm}")
    return {"id": rec.id, "name": rec.name, "kind": rec.kind, "algorithm": rec.algorithm, "created_at": rec.created_at}

@app.post("/api/keys/asymmetric")
def create_asymmetric(body: CreateAsym, _: dict = Depends(require_roles(["admin"]))):
    bits = body.bits or 2048
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    pub = private_key.public_key()
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    enc = aesgcm_encrypt(MASTER_KEY, priv_bytes)
    rec = KeyRecord(
        name=body.name or f"rsa-{int(time.time())}",
        kind="ASYMMETRIC",
        algorithm=f"RSA-{bits}",
        encrypted_secret=enc,
        public_key=base64.b64encode(pub_bytes).decode()
    )
    db = SessionLocal(); db.add(rec); db.commit(); db.refresh(rec); db.close()
    log_action("CREATE_KEY", rec.id, f"algorithm={rec.algorithm}")
    return {"id": rec.id, "name": rec.name, "kind": rec.kind, "algorithm": rec.algorithm, "created_at": rec.created_at}

@app.get("/api/keys")
def list_keys(_: dict = Depends(require_roles(["admin"]))):
    db = SessionLocal()
    rows = db.query(KeyRecord).all()
    out = [
        {
            "id": r.id,
            "name": r.name,
            "kind": r.kind,
            "algorithm": r.algorithm,
            "public_key_present": bool(r.public_key),
            "created_at": r.created_at
        } for r in rows
    ]
    db.close()
    log_action("LIST_KEYS", details=f"count={len(out)}")
    return out

@app.get("/api/keys/{key_id}")
def get_key(key_id: int, reveal: bool = Query(False), _: dict = Depends(require_roles(["admin"]))):
    db = SessionLocal()
    r = db.query(KeyRecord).filter(KeyRecord.id == key_id).first()
    db.close()
    if not r:
        raise HTTPException(404, "Not found")
    if not reveal:
        log_action("GET_KEY_METADATA", r.id)
        return {
            "id": r.id,
            "name": r.name,
            "kind": r.kind,
            "algorithm": r.algorithm,
            "public_key": r.public_key,
            "created_at": r.created_at
        }
    secret = aesgcm_decrypt(MASTER_KEY, r.encrypted_secret)
    log_action("REVEAL_KEY", r.id)
    return {
        "id": r.id,
        "name": r.name,
        "kind": r.kind,
        "algorithm": r.algorithm,
        "decrypted_secret_b64": base64.b64encode(secret).decode(),
        "public_key": r.public_key,
        "created_at": r.created_at
    }


@app.post("/api/keys/{key_id}/rotate")
def rotate_key(key_id: int, body: RotateBody):
    new_master_key = base64.b64decode(body.new_master_key_b64)
    if len(new_master_key) != 32:
        raise HTTPException(400, "new_master_key_b64 must be 32 bytes (AES-256)")

    db = SessionLocal()
    rec = db.query(KeyRecord).filter(KeyRecord.id == key_id).first()
    if not rec:
        db.close()
        raise HTTPException(404, "Key not found")

    # Save old encrypted secret into versions
    old_version_count = db.query(KeyVersion).filter(KeyVersion.key_id == rec.id).count()
    old_version = KeyVersion(
        key_id=rec.id,
        version=old_version_count + 1,
        encrypted_secret=rec.encrypted_secret
    )
    db.add(old_version)

    secret = aesgcm_decrypt(MASTER_KEY, rec.encrypted_secret)

    new_enc = aesgcm_encrypt(new_master_key, secret)
    rec.encrypted_secret = new_enc

    db.commit()
    db.refresh(rec)
    db.close()

    return {
        "id": rec.id,
        "name": rec.name,
        "kind": rec.kind,
        "algorithm": rec.algorithm,
        "rotated_at": datetime.now()
    }


def encryptAES(rec, plaintext):
    if rec.kind != "SYMMETRIC":
        raise HTTPException(400, "Selected key is not symmetric")

    secret = aesgcm_decrypt(MASTER_KEY, rec.encrypted_secret)
    if len(secret) != 32:
        raise HTTPException(400, "Key material is not 256-bit AES")

    aesgcm = AESGCM(secret)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext, None)
    return {
        "ciphertext_b64": base64.b64encode(nonce + ct).decode(),
        "algorithm": "AES-GCM-256"
    }


def encryptRSA(rec, plaintext):
    if rec.kind != "ASYMMETRIC":
        raise HTTPException(400, "Selected key is not asymmetric")
    
    if not rec.public_key:
        raise HTTPException(400, "No public key stored for this key record")

    try:
        pub_bytes = base64.b64decode(rec.public_key)
    except Exception as e:
        raise HTTPException(500, f"public_key is not valid base64: {e}")
    pub = serialization.load_der_public_key(pub_bytes)

    ct = pub.encrypt(
        plaintext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return {
        "ciphertext_b64": base64.b64encode(ct).decode(),
        "algorithm": "RSA-OAEP"
    }


@app.post("/api/encrypt")
def encrypt_data(body: EncryptBody):
    db = SessionLocal()
    rec = db.query(KeyRecord).filter(KeyRecord.id == body.key_id).first()
    db.close()
    if not rec: raise HTTPException(404, "Key not found")

    plaintext = base64.b64decode(body.plaintext_b64)

    if body.algorithm.upper() == "AES-GCM-256":
        return encryptAES(rec, plaintext)
    elif body.algorithm.upper() == "RSA-OAEP":
        return encryptRSA(rec, plaintext)
    else:
        raise HTTPException(400, "Unsupported algorithm. Use AES-GCM-256 or RSA-OAEP")
    


def signRSA(rec, message: bytes):
    if rec.kind != "ASYMMETRIC":
        raise HTTPException(400, "Selected key is not asymmetric")

    priv_bytes = aesgcm_decrypt(MASTER_KEY, rec.encrypted_secret)
    private_key = serialization.load_der_private_key(priv_bytes, password=None)

    sig = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )

    return {
        "signature_b64": base64.b64encode(sig).decode(),
        "algorithm": "RSA-PSS"
    }


@app.post("/api/sign")
def sign_message(body: SignBody):
    db = SessionLocal()
    rec = db.query(KeyRecord).filter(KeyRecord.id == body.key_id).first()
    db.close()
    if not rec:
        raise HTTPException(404, "Key not found")

    if body.algorithm.upper() != "RSA-PSS":
        raise HTTPException(400, "Unsupported algorithm. Use RSA-PSS")

    message = base64.b64decode(body.message_b64)
    return signRSA(rec, message)


def verifyRSA(rec, message: bytes, signature: bytes):
    if rec.kind != "ASYMMETRIC":
        raise HTTPException(400, "Selected key is not asymmetric")

    pub_bytes = base64.b64decode(rec.public_key)
    public_key = serialization.load_der_public_key(pub_bytes)

    try:
        public_key.verify(
            signature,
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return {"valid": True}
    except Exception:
        return {"valid": False}
    

@app.post("/api/verify")
def verify_message(body: VerifyBody):
    db = SessionLocal()
    rec = db.query(KeyRecord).filter(KeyRecord.id == body.key_id).first()
    db.close()
    if not rec:
        raise HTTPException(404, "Key not found")

    if body.algorithm.upper() != "RSA-PSS":
        raise HTTPException(400, "Unsupported algorithm. Use RSA-PSS")

    message = base64.b64decode(body.message_b64)
    signature = base64.b64decode(body.signature_b64)
    return verifyRSA(rec, message, signature)