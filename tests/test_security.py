from app.security import hash_password, verify_password, hash_token
from app import config

def test_password_hash_verify():
    pw = "S3curePass!"
    h = hash_password(pw, salt="testsalt12345678")
    assert h.startswith("pbkdf2$")
    assert verify_password(pw, "testsalt12345678", h)
    assert not verify_password("wrong", "testsalt12345678", h)

def test_token_hash():
    t = "sometoken123"
    assert hash_token(t) != t
    assert len(hash_token(t)) == 64

def test_limits_config():
    assert config.MAX_UPLOAD_BYTES == 8 * 1024 * 1024
    assert config.MIN_PASSWORD_LEN >= 8
