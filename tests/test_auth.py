import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.auth import InvalidToken, TokenVerifier

SECRET = "x" * 32


def make_claims(**overrides):
    claims = {
        "sub": "user-1",
        "aud": "authenticated",
        "exp": int(time.time()) + 60,
        "app_metadata": {"role": "admin"},
    }
    claims.update(overrides)
    return claims


@pytest.fixture
def verifier():
    return TokenVerifier(jwt_secret=SECRET, jwks_url="")


def hs256(claims, secret=SECRET):
    return jwt.encode(claims, secret, algorithm="HS256")


def test_valid_hs256_token_returns_claims(verifier):
    claims = verifier.verify(hs256(make_claims()))

    assert claims["sub"] == "user-1"


def test_wrong_secret_is_rejected(verifier):
    with pytest.raises(InvalidToken):
        verifier.verify(hs256(make_claims(), secret="y" * 32))


def test_expired_token_is_rejected(verifier):
    with pytest.raises(InvalidToken):
        verifier.verify(hs256(make_claims(exp=int(time.time()) - 10)))


def test_wrong_audience_is_rejected(verifier):
    with pytest.raises(InvalidToken):
        verifier.verify(hs256(make_claims(aud="other")))


def test_garbage_is_rejected(verifier):
    with pytest.raises(InvalidToken):
        verifier.verify("not-a-token")


def test_unsupported_algorithm_is_rejected(verifier):
    unsigned = jwt.encode(make_claims(), key=None, algorithm="none")

    with pytest.raises(InvalidToken):
        verifier.verify(unsigned)


def test_asymmetric_token_verified_with_jwks_key():
    private_key = ec.generate_private_key(ec.SECP256R1())
    verifier = TokenVerifier(
        jwt_secret="", jwks_url="https://example.test/jwks",
        key_resolver=lambda token: private_key.public_key(),
    )
    token = jwt.encode(make_claims(), private_key, algorithm="ES256")

    assert verifier.verify(token)["sub"] == "user-1"


def test_asymmetric_token_without_jwks_configured_is_rejected():
    private_key = ec.generate_private_key(ec.SECP256R1())
    verifier = TokenVerifier(jwt_secret=SECRET, jwks_url="")
    token = jwt.encode(make_claims(), private_key, algorithm="ES256")

    with pytest.raises(InvalidToken):
        verifier.verify(token)
