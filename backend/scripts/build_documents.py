"""
Builds and embeds RaceDocuments for a given session.

Usage (from backend/, with PYTHONPATH set):
    venv\\Scripts\\python.exe scripts\\build_documents.py <session_key>

Example:
    venv\\Scripts\\python.exe scripts\\build_documents.py 11307
"""
import asyncio
import sys
import uuid
from app.database import AsyncSessionLocal
from app.models.f1_models import Session
from app.services.document_builder import build_all_documents_for_session
from app.services.embeddings import store_documents
from sqlalchemy import select


async def build_documents_for_session_key(session_key: int):
    async with AsyncSessionLocal() as db:
        async with db.begin():
            # Look up the internal session UUID from the OpenF1 session_key
            result = await db.execute(
                select(Session).where(Session.session_key == session_key)
            )
            session = result.scalar_one_or_none()
            if not session:
                print(f"❌ No session found with session_key={session_key}. "
                      f"Run the ingestion pipeline for this session first.")
                return

            print(f"\n📄 Building documents for session {session_key} "
                  f"({session.session_name})...\n")

            documents = await build_all_documents_for_session(db, session.id)
            print(f"  ✅ Built {len(documents)} text documents")

            if documents:
                print(f"\n  --- Sample document ---")
                print(f"  [{documents[0]['doc_type']}]")
                print(f"  {documents[0]['content'][:300]}...")
                print(f"  -----------------------\n")

            count = await store_documents(db, session_key, documents)
            print(f"  ✅ Embedded and stored {count} documents in pgvector")

        print(f"\n🏁 Document build complete for session {session_key}")


if __name__ == "__main__":
    key = int(sys.argv[1]) if len(sys.argv) > 1 else 11307
    asyncio.run(build_documents_for_session_key(key))