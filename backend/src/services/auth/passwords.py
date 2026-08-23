"""Argon2id password hashing (research.md §1, tech-stack.md's
Authentication section) -- OWASP's current recommended default for new
systems, chosen over bcrypt since this is a greenfield choice with no
existing bcrypt usage in this codebase to match.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
