"""PostgreSQL repository for System 11 Admin, Escalations, Knowledge Base, and Audits."""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from app.database.connection import get_connection
from app.models.admin import (
    AdminAuditLog,
    AdminRole,
    AdminUser,
    Escalation,
    EscalationCategory,
    EscalationPriority,
    EscalationStatus,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
)

logger = logging.getLogger(__name__)


class AdminRepository:
    """Handles multi-tenant persistence for SACCO staff, escalations, and KB."""

    # -----------------------------------------------------------------------
    # Admin User Management
    # -----------------------------------------------------------------------
    def create_admin_user(
        self,
        id: str,
        username: str,
        password_hash: str,
        sacco_id: str = "demo_sacco",
        email: Optional[str] = None,
        role: AdminRole = AdminRole.STAFF,
    ) -> AdminUser:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO admin_users (id, username, password_hash, email, sacco_id, role, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, true)
                ON CONFLICT (username) DO UPDATE
                SET password_hash = EXCLUDED.password_hash,
                    email = EXCLUDED.email,
                    role = EXCLUDED.role,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, username, password_hash, email, sacco_id, role, is_active, created_at, updated_at
                """,
                (id, username, password_hash, email, sacco_id, role.value),
            )
            row = cur.fetchone()
            return AdminUser(
                id=row[0],
                username=row[1],
                password_hash=row[2],
                email=row[3],
                sacco_id=row[4],
                role=AdminRole(row[5]),
                is_active=row[6],
                created_at=row[7],
                updated_at=row[8],
            )

    def get_admin_by_username(self, username: str) -> Optional[AdminUser]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, username, password_hash, email, sacco_id, role, is_active, created_at, updated_at
                FROM admin_users
                WHERE username = %s AND is_active = true
                """,
                (username,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return AdminUser(
                id=row[0],
                username=row[1],
                password_hash=row[2],
                email=row[3],
                sacco_id=row[4],
                role=AdminRole(row[5]),
                is_active=row[6],
                created_at=row[7],
                updated_at=row[8],
            )

    def get_admin_by_id(self, admin_id: str) -> Optional[AdminUser]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, username, password_hash, email, sacco_id, role, is_active, created_at, updated_at
                FROM admin_users
                WHERE id = %s AND is_active = true
                """,
                (admin_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return AdminUser(
                id=row[0],
                username=row[1],
                password_hash=row[2],
                email=row[3],
                sacco_id=row[4],
                role=AdminRole(row[5]),
                is_active=row[6],
                created_at=row[7],
                updated_at=row[8],
            )

    # -----------------------------------------------------------------------
    # Escalations Management
    # -----------------------------------------------------------------------
    def create_escalation(
        self,
        conversation_key: str,
        query: str,
        sacco_id: str = "demo_sacco",
        member_id: Optional[str] = None,
        category: EscalationCategory = EscalationCategory.COMPLEX_QUERY,
        priority: EscalationPriority = EscalationPriority.MEDIUM,
        notes: Optional[str] = None,
    ) -> Escalation:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO escalations (sacco_id, member_id, conversation_key, query, category, status, priority, notes)
                VALUES (%s, %s, %s, %s, %s, 'open', %s, %s)
                RETURNING id, sacco_id, member_id, conversation_key, query, category, status, priority, notes, assigned_to, created_at, resolved_at
                """,
                (sacco_id, member_id, conversation_key, query, category.value, priority.value, notes),
            )
            row = cur.fetchone()
            return Escalation(
                id=row[0],
                sacco_id=row[1],
                member_id=row[2],
                conversation_key=row[3],
                query=row[4],
                category=EscalationCategory(row[5]),
                status=EscalationStatus(row[6]),
                priority=EscalationPriority(row[7]),
                notes=row[8],
                assigned_to=row[9],
                created_at=row[10],
                resolved_at=row[11],
            )

    def list_escalations(
        self,
        sacco_id: str = "demo_sacco",
        status: Optional[EscalationStatus] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query_sql = """
            SELECT e.id, e.sacco_id, e.member_id, m.display_name, e.conversation_key, e.query,
                   e.category, e.status, e.priority, e.notes, e.assigned_to, e.created_at, e.resolved_at
            FROM escalations e
            LEFT JOIN members m ON e.member_id = m.id
            WHERE e.sacco_id = %s
        """
        params: list[Any] = [sacco_id]
        if status:
            query_sql += " AND e.status = %s"
            params.append(status.value)
        query_sql += " ORDER BY e.created_at DESC LIMIT %s"
        params.append(limit)

        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(query_sql, tuple(params))
            results = []
            for row in cur.fetchall():
                results.append({
                    "id": row[0],
                    "sacco_id": row[1],
                    "member_id": row[2],
                    "member_name": row[3],
                    "conversation_key": row[4],
                    "query": row[5],
                    "category": EscalationCategory(row[6]),
                    "status": EscalationStatus(row[7]),
                    "priority": EscalationPriority(row[8]),
                    "notes": row[9],
                    "assigned_to": row[10],
                    "created_at": row[11],
                    "resolved_at": row[12],
                })
            return results

    def update_escalation(
        self,
        escalation_id: int,
        sacco_id: str = "demo_sacco",
        status: Optional[EscalationStatus] = None,
        priority: Optional[EscalationPriority] = None,
        notes: Optional[str] = None,
        assigned_to: Optional[str] = None,
    ) -> Optional[Escalation]:
        updates = []
        params: list[Any] = []
        if status is not None:
            updates.append("status = %s")
            params.append(status.value)
            if status in (EscalationStatus.RESOLVED, EscalationStatus.DISMISSED):
                updates.append("resolved_at = CURRENT_TIMESTAMP")
        if priority is not None:
            updates.append("priority = %s")
            params.append(priority.value)
        if notes is not None:
            updates.append("notes = %s")
            params.append(notes)
        if assigned_to is not None:
            updates.append("assigned_to = %s")
            params.append(assigned_to)

        if not updates:
            return None

        params.extend([escalation_id, sacco_id])
        sql = f"""
            UPDATE escalations
            SET {", ".join(updates)}
            WHERE id = %s AND sacco_id = %s
            RETURNING id, sacco_id, member_id, conversation_key, query, category, status, priority, notes, assigned_to, created_at, resolved_at
        """
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            row = cur.fetchone()
            if not row:
                return None
            return Escalation(
                id=row[0],
                sacco_id=row[1],
                member_id=row[2],
                conversation_key=row[3],
                query=row[4],
                category=EscalationCategory(row[5]),
                status=EscalationStatus(row[6]),
                priority=EscalationPriority(row[7]),
                notes=row[8],
                assigned_to=row[9],
                created_at=row[10],
                resolved_at=row[11],
            )

    # -----------------------------------------------------------------------
    # Knowledge Base Workflow Management
    # -----------------------------------------------------------------------
    def create_knowledge_document(
        self,
        id: str,
        title: str,
        content: str,
        category: str = "general",
        sacco_id: str = "demo_sacco",
        created_by: Optional[str] = None,
        effective_date: Optional[Any] = None,
    ) -> KnowledgeDocument:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO knowledge_documents (id, sacco_id, title, category, content, version, status, created_by, effective_date)
                VALUES (%s, %s, %s, %s, %s, 1, 'draft', %s, COALESCE(%s, CURRENT_DATE))
                RETURNING id, sacco_id, title, category, content, version, status, created_by, approved_by, effective_date, qdrant_indexed_at, created_at, updated_at
                """,
                (id, sacco_id, title, category, content, created_by, effective_date),
            )
            row = cur.fetchone()
            return KnowledgeDocument(
                id=row[0],
                sacco_id=row[1],
                title=row[2],
                category=row[3],
                content=row[4],
                version=row[5],
                status=KnowledgeDocumentStatus(row[6]),
                created_by=row[7],
                approved_by=row[8],
                effective_date=row[9],
                qdrant_indexed_at=row[10],
                created_at=row[11],
                updated_at=row[12],
            )

    def list_knowledge_documents(
        self,
        sacco_id: str = "demo_sacco",
        status: Optional[KnowledgeDocumentStatus] = None,
    ) -> list[KnowledgeDocument]:
        sql = """
            SELECT id, sacco_id, title, category, content, version, status,
                   created_by, approved_by, effective_date, qdrant_indexed_at, created_at, updated_at
            FROM knowledge_documents
            WHERE sacco_id = %s
        """
        params: list[Any] = [sacco_id]
        if status:
            sql += " AND status = %s"
            params.append(status.value)
        sql += " ORDER BY updated_at DESC"

        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            docs = []
            for row in cur.fetchall():
                docs.append(KnowledgeDocument(
                    id=row[0],
                    sacco_id=row[1],
                    title=row[2],
                    category=row[3],
                    content=row[4],
                    version=row[5],
                    status=KnowledgeDocumentStatus(row[6]),
                    created_by=row[7],
                    approved_by=row[8],
                    effective_date=row[9],
                    qdrant_indexed_at=row[10],
                    created_at=row[11],
                    updated_at=row[12],
                ))
            return docs

    def get_knowledge_document(self, doc_id: str, sacco_id: str = "demo_sacco") -> Optional[KnowledgeDocument]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, sacco_id, title, category, content, version, status,
                       created_by, approved_by, effective_date, qdrant_indexed_at, created_at, updated_at
                FROM knowledge_documents
                WHERE id = %s AND sacco_id = %s
                """,
                (doc_id, sacco_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return KnowledgeDocument(
                id=row[0],
                sacco_id=row[1],
                title=row[2],
                category=row[3],
                content=row[4],
                version=row[5],
                status=KnowledgeDocumentStatus(row[6]),
                created_by=row[7],
                approved_by=row[8],
                effective_date=row[9],
                qdrant_indexed_at=row[10],
                created_at=row[11],
                updated_at=row[12],
            )

    def mark_document_approved(
        self,
        doc_id: str,
        approved_by: str,
        sacco_id: str = "demo_sacco",
    ) -> Optional[KnowledgeDocument]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE knowledge_documents
                SET status = 'approved',
                    approved_by = %s,
                    qdrant_indexed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND sacco_id = %s
                RETURNING id, sacco_id, title, category, content, version, status,
                          created_by, approved_by, effective_date, qdrant_indexed_at, created_at, updated_at
                """,
                (approved_by, doc_id, sacco_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return KnowledgeDocument(
                id=row[0],
                sacco_id=row[1],
                title=row[2],
                category=row[3],
                content=row[4],
                version=row[5],
                status=KnowledgeDocumentStatus(row[6]),
                created_by=row[7],
                approved_by=row[8],
                effective_date=row[9],
                qdrant_indexed_at=row[10],
                created_at=row[11],
                updated_at=row[12],
            )

    # -----------------------------------------------------------------------
    # Admin Audit Logs
    # -----------------------------------------------------------------------
    def record_audit(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        admin_id: Optional[str] = None,
        sacco_id: str = "demo_sacco",
        details: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO admin_audit_logs (sacco_id, admin_id, action, resource_type, resource_id, details, ip_address)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    sacco_id,
                    admin_id,
                    action,
                    resource_type,
                    resource_id,
                    json.dumps(details) if details else None,
                    ip_address,
                ),
            )
