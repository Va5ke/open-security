import os, base64, time
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

MASTER_KEY_B64 = "OAn1NzvF8BSeHVc4I85m9XVRpGm8T8KpAfD7TqgmXfE="
DATABASE_URL = "postgresql+psycopg2://postgres:opendoors@localhost:5432/kms"

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class KeyRecord(Base):
    __tablename__ = "keys"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    kind = Column(String)
    algorithm = Column(String)
    encrypted_secret = Column(Text)
    public_key = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

if not MASTER_KEY_B64:
    raise RuntimeError("Set MASTER_KEY_B64 env variable (base64-encoded 32 bytes).")

MASTER_KEY = base64.b64decode(MASTER_KEY_B64)
if len(MASTER_KEY) != 32:
    raise RuntimeError("MASTER_KEY_B64 must decode to 32 bytes (AES-256).")

app = FastAPI(title="Key Management API (Postgres)")

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

@app.post("/api/keys/symmetric")
def create_symmetric(body: CreateSym):
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
    return {"id": rec.id, "name": rec.name, "kind": rec.kind, "algorithm": rec.algorithm, "created_at": rec.created_at}

@app.post("/api/keys/asymmetric")
def create_asymmetric(body: CreateAsym):
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
    return {"id": rec.id, "name": rec.name, "kind": rec.kind, "algorithm": rec.algorithm, "created_at": rec.created_at}

@app.get("/api/keys")
def list_keys():
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
    return out

@app.get("/api/keys/{key_id}")
def get_key(key_id: int, reveal: bool = Query(False)):
    db = SessionLocal()
    r = db.query(KeyRecord).filter(KeyRecord.id == key_id).first()
    db.close()
    if not r:
        raise HTTPException(404, "Not found")
    if not reveal:
        return {
            "id": r.id,
            "name": r.name,
            "kind": r.kind,
            "algorithm": r.algorithm,
            "public_key": r.public_key,
            "created_at": r.created_at
        }
    secret = aesgcm_decrypt(MASTER_KEY, r.encrypted_secret)
    return {
        "id": r.id,
        "name": r.name,
        "kind": r.kind,
        "algorithm": r.algorithm,
        "decrypted_secret_b64": base64.b64encode(secret).decode(),
        "public_key": r.public_key,
        "created_at": r.created_at
    }

@app.delete("/api/keys/{key_id}", status_code=204)
def delete_key(key_id: int):
    db = SessionLocal()
    r = db.query(KeyRecord).filter(KeyRecord.id == key_id).first()
    if not r:
        db.close()
        raise HTTPException(404, "Not found")
    db.delete(r); db.commit(); db.close()
    return