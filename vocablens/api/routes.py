from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
import logging


from vocablens.services.vocabulary_service import VocabularyService
from vocablens.api.schemas import (
    VocabularyResponse,
    TranslationRequest,
    RegisterRequest,
    LoginRequest,
    TokenResponse,
)
from vocablens.services.ocr_service import OCRService
from vocablens.domain.errors import NotFoundError
from vocablens.api.dependencies import get_current_user
from vocablens.domain.user import User
from vocablens.infrastructure.repositories_users import SQLiteUserRepository
from vocablens.auth.security import hash_password, verify_password
from vocablens.auth.jwt import create_access_token

logger = logging.getLogger(__name__)


def create_routes(
    service: VocabularyService,
    ocr_service: OCRService,
    user_repo: SQLiteUserRepository,
) -> APIRouter:

    router = APIRouter()

    # ------------------------
    # AUTH
    # ------------------------

    @router.post("/register", response_model=TokenResponse)
    def register(payload: RegisterRequest):
        hashed = hash_password(payload.password)

        try:
            user = user_repo.create(
                email=payload.email,
                password_hash=hashed,
            )
        except Exception: # SomeUniqueError
            raise HTTPException(400, "Email already registered")

        token = create_access_token(user.id)

        return TokenResponse(access_token=token)

    @router.post("/login", response_model=TokenResponse)
    def login(payload: LoginRequest):
        user = user_repo.get_by_email(payload.email)

        if not user or not verify_password(
            payload.password,
            user.password_hash,
        ):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        """INSTEAD

user = user_repo.get_by_email(...)
if not user:
    verify_password(payload.password, "$2b$12$dummyhash........")
    raise HTTPException(...)"""


        token = create_access_token(user.id)

        return TokenResponse(access_token=token)

    # ------------------------
    # TRANSLATION
    # ------------------------

    @router.post("/translate", response_model=VocabularyResponse)
    def translate_text(
        payload: TranslationRequest,
        user: User = Depends(get_current_user),
    ):
        item = service.process_text(
            user.id,
            payload.text,
            payload.source_lang,
            payload.target_lang,
        )
        return VocabularyResponse.from_domain(item)

    @router.post("/translate/image", response_model=VocabularyResponse)
    async def translate_image(
        file: UploadFile = File(...),
        source_lang: str = "auto",
        target_lang: str = "en",
        user: User = Depends(get_current_user),
    ):
        image_bytes = await file.read()
        extracted = ocr_service.extract(image_bytes)

        item = service.process_text(
            user.id,
            extracted,
            source_lang,
            target_lang,
        )

        return VocabularyResponse.from_domain(item)

    # ------------------------
    # VOCAB
    # ------------------------

    @router.get("/vocabulary", response_model=list[VocabularyResponse])
    def list_vocabulary(
        limit: int = 50,
        offset: int = 0,
        user: User = Depends(get_current_user),
    ):
        items = service.list_vocabulary(user.id, limit, offset)
        return [VocabularyResponse.from_domain(i) for i in items]

    @router.post("/vocabulary/{item_id}/review", response_model=VocabularyResponse)
    def review_item(
        item_id: int,
        user: User = Depends(get_current_user),
    ):
        try:
            updated = service.review_item(user.id, item_id)
            return VocabularyResponse.from_domain(updated)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @router.get("/vocabulary/due", response_model=list[VocabularyResponse])
    def due_items(user: User = Depends(get_current_user)):
        items = service.list_due_items(user.id)
        return [VocabularyResponse.from_domain(i) for i in items]

    return router


"""
        INSTEAD
        
        limit: int = Query(50, ge=1, le=100)
        offset: int = Query(0, ge=0)


AND

/auth/register
/auth/login
/vocab/...
        """
