import asyncio
import base64
import inspect
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List
import httpx
from ..base_node import BaseNode, NodeCategory, NodePort, NodeExecutionResult


class HttpRequestNode(BaseNode):
    id = "core.http_request"
    name = "Requête HTTP / Webhook Sortant"
    category = NodeCategory.INTEGRATION
    icon = "http"
    color = "#3b82f6"
    description = "Envoie une requête HTTP (GET, POST, PUT, DELETE, PATCH) avec support JSON, formulaires, authentification et pièces jointes."

    def __init__(self):
        self.inputs = [NodePort(id="main", label="Entrée", port_type="main")]
        self.outputs = [
            NodePort(id="main", label="Réponse HTTP", port_type="main", color="#3b82f6"),
        ]
        super().__init__()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "method": {
                "type": "select",
                "label": "Méthode HTTP",
                "options": [
                    {"label": "POST", "value": "POST"},
                    {"label": "GET", "value": "GET"},
                    {"label": "PUT", "value": "PUT"},
                    {"label": "DELETE", "value": "DELETE"},
                    {"label": "PATCH", "value": "PATCH"},
                ],
                "default": "POST",
                "required": True,
            },
            "url": {
                "type": "string",
                "label": "URL de destination",
                "required": True,
                "placeholder": "https://api.monservice.com/webhook",
                "description": "Supporte l'interpolation : {payload.order_id}",
            },
            "auth_type": {
                "type": "select",
                "label": "Authentification",
                "options": [
                    {"label": "Aucune", "value": "none"},
                    {"label": "Bearer Token", "value": "bearer"},
                    {"label": "Basic Auth", "value": "basic"},
                    {"label": "En-tête personnalisé (API Key)", "value": "header"},
                ],
                "default": "none",
            },
            "auth_token": {
                "type": "string",
                "label": "Bearer Token",
                "placeholder": "Bearer eyJhbGciOi...",
                "description": "Utilisé si Authentification = Bearer Token. Supporte {token}.",
            },
            "auth_username": {
                "type": "string",
                "label": "Nom d'utilisateur (Basic Auth)",
            },
            "auth_password": {
                "type": "string",
                "label": "Mot de passe (Basic Auth)",
            },
            "auth_header_name": {
                "type": "string",
                "label": "Nom de l'en-tête (API Key)",
                "placeholder": "X-API-Key",
            },
            "auth_header_value": {
                "type": "string",
                "label": "Valeur de l'en-tête",
                "placeholder": "secret-api-key",
            },
            "headers": {
                "type": "json",
                "label": "En-têtes HTTP additionnels (JSON)",
                "default": {},
            },
            "body_type": {
                "type": "select",
                "label": "Format du corps (Body)",
                "options": [
                    {"label": "JSON (application/json)", "value": "json"},
                    {"label": "Multipart / Form-Data (avec fichiers)", "value": "form_data"},
                    {"label": "Form URL-Encoded (application/x-www-form-urlencoded)", "value": "form_urlencoded"},
                    {"label": "Texte brut (Raw)", "value": "raw"},
                    {"label": "Aucun corps (Vide)", "value": "none"},
                ],
                "default": "json",
            },
            "body": {
                "type": "json",
                "label": "Corps de requête (JSON / Objet)",
                "description": "Pour JSON ou Form URL-Encoded. Laissez vide pour relayer l'entrée reçue.",
            },
            "form_fields": {
                "type": "json",
                "label": "Champs de formulaire textuels (Form-Data)",
                "description": "Dictionnaire clé/valeur pour les données de formulaire multipart.",
                "default": {},
            },
            "files": {
                "type": "json",
                "label": "Fichiers joints (Multipart / Form-Data)",
                "description": "Liste d'objets: [{'field_name': 'file', 'file_source': 'path'|'media_id'|'base64'|'content', 'file_path': '...', 'media_id': '...', 'filename': '...'}]",
                "default": [],
            },
            "timeout": {
                "type": "number",
                "label": "Délai d'attente (secondes)",
                "default": 15,
            },
            "fail_on_error": {
                "type": "boolean",
                "label": "Échouer si code HTTP >= 400",
                "default": True,
            },
        }

    async def _resolve_file_bytes(
        self,
        item: Dict[str, Any],
        eval_context: Dict[str, Any],
        app: Any,
    ) -> tuple[str, bytes, str]:
        """
        Résout le nom de fichier, le contenu binaire et le Content-Type pour un fichier joint.
        Retourne: (filename, file_bytes, content_type)
        """
        from ...services.execution_engine import ExecutionEngine

        source = str(item.get("file_source") or "path").lower()
        custom_filename = ExecutionEngine.interpolate_value(item.get("filename") or "", eval_context) or None
        content_type = ExecutionEngine.interpolate_value(item.get("content_type") or "", eval_context) or None

        if source == "path":
            raw_path = ExecutionEngine.interpolate_value(item.get("file_path") or "", eval_context)
            if not raw_path:
                raise ValueError("Chemin de fichier 'file_path' manquant pour la pièce jointe.")
            p = Path(raw_path)
            if not p.exists():
                raise FileNotFoundError(f"Fichier introuvable sur le disque: {raw_path}")
            file_bytes = p.read_bytes()
            filename = custom_filename or p.name
            if not content_type:
                content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            return filename, file_bytes, content_type

        elif source == "media_id":
            media_id = ExecutionEngine.interpolate_value(str(item.get("media_id") or ""), eval_context)
            if not media_id:
                raise ValueError("Identifiant 'media_id' manquant pour la pièce jointe.")

            media = None
            if app and hasattr(app, "db"):
                try:
                    async with app.db.get_session() as session:
                        from core.orm import select
                        from base.models.media_model import MediaModel
                        stmt = select(MediaModel).where(MediaModel.media_id == media_id)
                        res = await session.execute(stmt)
                        media = res.scalar_one_or_none()
                except Exception:
                    media = None

            if not media:
                raise ValueError(f"Média introuvable en base pour media_id='{media_id}'")

            filename = custom_filename or media.filename or f"media_{media_id}"
            if not content_type:
                content_type = media.mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

            file_bytes = None
            # Tentative de lecture via Storage
            try:
                from core.file_management.storage import Storage
                storage = Storage(app)
                res_read = storage.read(media.filename, media.path_dir or "")
                if inspect.isawaitable(res_read):
                    file_bytes = await res_read
                else:
                    file_bytes = res_read
            except Exception:
                file_bytes = None

            # Fallback direct filesystem
            if file_bytes is None:
                base_dir = getattr(app.config, "PATH_DIR_STORAGE", "./storage") if hasattr(app, "config") else "./storage"
                disk_path = Path(base_dir) / (media.path_dir or "") / media.filename
                if disk_path.exists():
                    file_bytes = disk_path.read_bytes()
                else:
                    raise FileNotFoundError(f"Fichier du média '{media_id}' introuvable sur le stockage local ({disk_path})")

            return filename, file_bytes, content_type

        elif source == "base64":
            raw_b64 = ExecutionEngine.interpolate_value(item.get("base64_data") or item.get("content") or "", eval_context)
            if not raw_b64:
                raise ValueError("Contenu base64 manquant.")
            if isinstance(raw_b64, str) and ";base64," in raw_b64:
                raw_b64 = raw_b64.split(";base64,")[1]
            file_bytes = base64.b64decode(raw_b64)
            filename = custom_filename or "attachment.bin"
            if not content_type:
                content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            return filename, file_bytes, content_type

        elif source == "content":
            raw_content = ExecutionEngine.interpolate_value(item.get("content") or "", eval_context)
            if isinstance(raw_content, str):
                file_bytes = raw_content.encode("utf-8")
            elif isinstance(raw_content, bytes):
                file_bytes = raw_content
            else:
                file_bytes = str(raw_content).encode("utf-8")
            filename = custom_filename or "document.txt"
            if not content_type:
                content_type = "text/plain; charset=utf-8"
            return filename, file_bytes, content_type

        else:
            raise ValueError(f"Source de fichier inconnue: '{source}'. Valeurs possibles: path, media_id, base64, content.")

    async def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Dict[str, Any],
        app: Any,
    ) -> NodeExecutionResult:
        from ...services.execution_engine import ExecutionEngine

        eval_context = dict(context)
        if isinstance(input_data, dict):
            eval_context.setdefault("input", input_data)
            for k, v in input_data.items():
                if k not in eval_context:
                    eval_context[k] = v

        raw_url = config.get("url") or ""
        url = ExecutionEngine.interpolate_value(raw_url, eval_context)
        if not url:
            raise ValueError("URL manquante pour la requête HTTP.")

        method = str(config.get("method") or "POST").upper()
        raw_headers = config.get("headers") or {}
        headers = ExecutionEngine.interpolate_value(raw_headers, eval_context) if isinstance(raw_headers, dict) else {}

        # Authentification
        auth_type = str(config.get("auth_type") or "none").lower()
        http_auth = None
        if auth_type == "bearer":
            raw_token = config.get("auth_token") or ""
            token = ExecutionEngine.interpolate_value(raw_token, eval_context)
            if token:
                if not str(token).lower().startswith("bearer "):
                    headers["Authorization"] = f"Bearer {token}"
                else:
                    headers["Authorization"] = str(token)
        elif auth_type == "basic":
            raw_user = config.get("auth_username") or ""
            raw_pass = config.get("auth_password") or ""
            username = ExecutionEngine.interpolate_value(raw_user, eval_context)
            password = ExecutionEngine.interpolate_value(raw_pass, eval_context)
            http_auth = (username, password)
        elif auth_type == "header":
            h_name = ExecutionEngine.interpolate_value(config.get("auth_header_name") or "", eval_context)
            h_val = ExecutionEngine.interpolate_value(config.get("auth_header_value") or "", eval_context)
            if h_name:
                headers[h_name] = str(h_val)

        # Corps de requête
        body_type = str(config.get("body_type") or "").lower()
        raw_files = config.get("files") or []
        files_config = ExecutionEngine.interpolate_value(raw_files, eval_context) if isinstance(raw_files, (list, dict)) else []
        if isinstance(files_config, dict):
            files_config = [files_config]

        # Détection automatique si body_type non renseigné mais des fichiers sont fournis
        if not body_type:
            if files_config:
                body_type = "form_data"
            else:
                body_type = "json"

        raw_body = config.get("body")
        if raw_body is not None:
            body = ExecutionEngine.interpolate_value(raw_body, eval_context)
        else:
            body = input_data

        timeout = float(config.get("timeout") or 15.0)
        fail_on_error = config.get("fail_on_error", True)

        req_kwargs: Dict[str, Any] = {"headers": headers}
        if http_auth:
            req_kwargs["auth"] = http_auth

        if method in ("POST", "PUT", "PATCH", "DELETE"):
            if body_type == "form_data" or files_config:
                # Suppression du Content-Type application/json pour laisser httpx fixer multipart/form-data et son boundary
                for ct_key in [k for k in headers.keys() if k.lower() == "content-type"]:
                    if "json" in headers[ct_key].lower():
                        del headers[ct_key]

                raw_fields = config.get("form_fields") or {}
                form_fields = ExecutionEngine.interpolate_value(raw_fields, eval_context) if isinstance(raw_fields, dict) else {}
                data_dict = dict(form_fields)
                if isinstance(body, dict) and body != input_data:
                    data_dict.update(body)

                files_tuples: List[tuple] = []
                for f_item in files_config:
                    if not isinstance(f_item, dict):
                        continue
                    field_name = ExecutionEngine.interpolate_value(f_item.get("field_name") or "file", eval_context)
                    fn, f_bytes, ctype = await self._resolve_file_bytes(f_item, eval_context, app)
                    files_tuples.append((field_name, (fn, f_bytes, ctype)))

                req_kwargs["data"] = data_dict
                if files_tuples:
                    req_kwargs["files"] = files_tuples

            elif body_type == "form_urlencoded":
                form_data = body if isinstance(body, dict) else {}
                raw_fields = config.get("form_fields") or {}
                if isinstance(raw_fields, dict):
                    form_data.update(ExecutionEngine.interpolate_value(raw_fields, eval_context))
                req_kwargs["data"] = form_data

            elif body_type == "raw":
                req_kwargs["content"] = str(body) if body is not None else ""

            elif body_type == "json":
                if isinstance(body, (dict, list)):
                    req_kwargs["json"] = body
                elif body is not None:
                    req_kwargs["content"] = str(body)

            elif body_type == "none":
                pass

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method=method, url=url, **req_kwargs)
            try:
                resp_data = resp.json()
            except Exception:
                resp_data = resp.text

            output = {
                "status_code": resp.status_code,
                "body": resp_data,
                "headers": dict(resp.headers),
            }

            if resp.status_code >= 400 and fail_on_error:
                raise RuntimeError(f"Erreur HTTP {resp.status_code} reçue de {url} : {str(resp_data)[:200]}")

            return NodeExecutionResult(output_data=output, active_ports=["main"])
