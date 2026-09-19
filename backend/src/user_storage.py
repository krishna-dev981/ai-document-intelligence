from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
USERS_DIR = ROOT / "storage" / "users"
LEGACY_DIR = ROOT / "storage"
MIGRATION_MARKER = USERS_DIR / ".legacy_migrated"

USERS_DIR.mkdir(parents=True, exist_ok=True)


def user_storage_dir(user_id: str) -> Path:
    path = USERS_DIR / user_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def migrate_legacy_data(user_id: str):
    """
    One-time migration of the Step 15.1 global storage into the first
    authenticated user's private workspace. Later users get clean storage.
    """
    workspace = user_storage_dir(user_id)
    if MIGRATION_MARKER.exists():
        return

    legacy_files = [
        "documents.json",
        "embeddings.npy",
        "faiss.index",
        "chat_history.db",
    ]
    for name in legacy_files:
        source = LEGACY_DIR / name
        target = workspace / name
        if source.exists() and not target.exists():
            shutil.copy2(source, target)

    MIGRATION_MARKER.write_text(user_id, encoding="utf-8")
