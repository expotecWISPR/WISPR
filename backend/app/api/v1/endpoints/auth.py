"""
Endpoints de autenticación: registro, login, y la dependencia que protege
al resto de endpoints (get_current_user).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])

# Le indica a FastAPI (y a la documentación automática en /docs) dónde
# está el endpoint de login y que el token se manda en cada petición como
# header "Authorization: Bearer <token>". No crea ninguna ruta por sí solo.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)) -> User:
    """Crea un usuario nuevo. Rechaza si el email o el username ya existen."""
    existing = db.execute(
        select(User).where((User.email == user_in.email) | (User.username == user_in.username))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email o el nombre de usuario ya están registrados.",
        )

    user = User(
        email=user_in.email,
        username=user_in.username,
        password_hash=hash_password(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)  # trae de vuelta id, created_at, etc. que puso la BD
    return user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    """
    Inicia sesión y devuelve un JWT.

    OAuth2PasswordRequestForm siempre llama al campo "username" — acá el
    usuario escribe su email ahí, es solo el nombre estándar del campo.
    """
    user = db.execute(select(User).where(User.email == form_data.username)).scalar_one_or_none()
    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token({"sub": user.email})
    return Token(access_token=access_token)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Dependencia reutilizable: decodifica el JWT del header Authorization y
    devuelve el User correspondiente.

    Cualquier endpoint que la reciba como parámetro (Depends(get_current_user))
    queda protegido — sin un token válido, FastAPI corta la petición acá
    mismo, antes de que el código del endpoint llegue a ejecutarse.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar la credencial.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    email = payload.get("sub")
    if email is None:
        raise credentials_exception

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        raise credentials_exception

    return user
