from app.auth import (
    hash_password,
    verify_password,
)


def test_password_hash_is_not_plaintext():

    password = (
        "VeryStrongProjectPassword123!"
    )

    stored = hash_password(
        password
    )

    assert stored != password

    assert stored.startswith(
        "pbkdf2_sha256$"
    )


def test_correct_password_verifies():

    password = (
        "VeryStrongProjectPassword123!"
    )

    stored = hash_password(
        password
    )

    assert verify_password(
        password,
        stored,
    ) is True


def test_wrong_password_fails():

    stored = hash_password(
        "VeryStrongProjectPassword123!"
    )

    assert verify_password(
        "WrongPassword123!",
        stored,
    ) is False
