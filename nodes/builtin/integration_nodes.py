import asyncio
import base64
import inspect
import mimetypes
import os
import time
from pathlib import Path
from typing import Any, Dict, List
import httpx
from ..base_node import BaseNode, NodeCategory, NodePort, NodeExecutionResult


class HttpRequestNode(BaseNode):
    id = "core.http_request"
    name = "Requête HTTP / Webhook Sortant"
    name_t = "nodes.http_request.name"
    category = NodeCategory.INTEGRATION
    icon = "http"
    color = "#3b82f6"
    description = "Envoie une requête HTTP (GET, POST, PUT, DELETE, PATCH) avec support JSON, formulaires, authentification et pièces jointes."
    description_t = "nodes.http_request.description"

    def __init__(self):
        self.inputs = [NodePort(id="main", label="Entrée", label_t="ports.input", port_type="main")]
        self.outputs = [
            NodePort(id="main", label="Réponse HTTP", label_t="nodes.http_request.ports.output", port_type="main", color="#3b82f6"),
        ]
        super().__init__()

    def get_sections(self) -> List[Dict[str, Any]]:
        return [
            {"id": "general", "label": "Paramètres Principaux", "label_t": "nodes.http_request.sections.general", "icon": "settings"},
            {"id": "query_params", "label": "Paramètres d'URL (Query)", "label_t": "nodes.http_request.sections.query_params", "icon": "link"},
            {"id": "headers", "label": "En-têtes HTTP (Headers)", "label_t": "nodes.http_request.sections.headers", "icon": "tag"},
            {"id": "auth", "label": "Authentification", "label_t": "nodes.http_request.sections.auth", "icon": "lock"},
            {"id": "body", "label": "Corps de la requête (Body)", "label_t": "nodes.http_request.sections.body", "icon": "description"},
            {"id": "advanced", "label": "Options Réseau & Retries", "label_t": "nodes.http_request.sections.advanced", "icon": "tune"},
        ]

    def get_schema(self) -> Dict[str, Any]:
        return {
            "method": {
                "type": "select",
                "label": "Méthode HTTP",
                "label_t": "nodes.http_request.fields.method.label",
                "section": "general",
                "options": [
                    {"label": "POST", "value": "POST"},
                    {"label": "GET", "value": "GET"},
                    {"label": "PUT", "value": "PUT"},
                    {"label": "DELETE", "value": "DELETE"},
                    {"label": "PATCH", "value": "PATCH"},
                    {"label": "HEAD", "value": "HEAD"},
                    {"label": "OPTIONS", "value": "OPTIONS"},
                ],
                "default": "POST",
                "required": True,
            },
            "url": {
                "type": "string",
                "label": "URL de destination",
                "label_t": "nodes.http_request.fields.url.label",
                "section": "general",
                "required": True,
                "placeholder": "https://api.monservice.com/webhook",
                "description": "Supporte l'interpolation dynamique : {payload.order_id} ou {steps.node_1.id}",
                "description_t": "nodes.http_request.fields.url.description",
            },
            "response_format": {
                "type": "select",
                "label": "Formatage de la Réponse",
                "label_t": "nodes.http_request.fields.response_format.label",
                "section": "general",
                "options": [
                    {"label": "Détection automatique (JSON si possible sinon Texte)", "label_t": "nodes.http_request.fields.response_format.options.autodetect", "value": "autodetect"},
                    {"label": "Forcer JSON (objet Python)", "label_t": "nodes.http_request.fields.response_format.options.json", "value": "json"},
                    {"label": "Texte Brut (String)", "label_t": "nodes.http_request.fields.response_format.options.text", "value": "text"},
                    {"label": "Binaire encodé en Base64", "label_t": "nodes.http_request.fields.response_format.options.base64", "value": "base64"},
                ],
                "default": "autodetect",
            },
            "query_params": {
                "type": "custom",
                "label": "Paramètres de requête URL (Query Parameters)",
                "label_t": "nodes.http_request.fields.query_params.label",
                "section": "query_params",
                "description": "Paramètres ajoutés à l'URL (?cle=valeur). Supporte les variables dynamiques {champ}.",
                "description_t": "nodes.http_request.fields.query_params.description",
                "default": [],
            },
            "headers_mode": {
                "type": "select",
                "label": "Mode de définition des En-têtes",
                "label_t": "nodes.http_request.fields.headers_mode.label",
                "section": "headers",
                "options": [
                    {"label": "Tableau Clé / Valeur (Visuel n8n)", "label_t": "nodes.http_request.fields.headers_mode.options.key_value", "value": "key_value"},
                    {"label": "Objet JSON Brut", "label_t": "nodes.http_request.fields.headers_mode.options.json", "value": "json"},
                ],
                "default": "key_value",
            },
            "headers_key_value": {
                "type": "custom",
                "label": "En-têtes HTTP (Tableau Clé / Valeur)",
                "label_t": "nodes.http_request.fields.headers_key_value.label",
                "section": "headers",
                "default": [],
                "display_if": {"field": "headers_mode", "operator": "==", "value": "key_value"},
            },
            "headers": {
                "type": "json",
                "label": "En-têtes HTTP additionnels (JSON brut)",
                "label_t": "nodes.http_request.fields.headers.label",
                "section": "headers",
                "default": {},
                "display_if": {"field": "headers_mode", "operator": "==", "value": "json"},
            },
            "auth_type": {
                "type": "select",
                "label": "Type d'Authentification",
                "label_t": "nodes.http_request.fields.auth_type.label",
                "section": "auth",
                "options": [
                    {"label": "Aucune", "label_t": "nodes.http_request.fields.auth_type.options.none", "value": "none"},
                    {"label": "Bearer Token", "label_t": "nodes.http_request.fields.auth_type.options.bearer", "value": "bearer"},
                    {"label": "Basic Auth", "label_t": "nodes.http_request.fields.auth_type.options.basic", "value": "basic"},
                    {"label": "En-tête personnalisé (API Key)", "label_t": "nodes.http_request.fields.auth_type.options.header", "value": "header"},
                    {"label": "Paramètre d'URL (Query API Key)", "label_t": "nodes.http_request.fields.auth_type.options.query", "value": "query"},
                ],
                "default": "none",
            },
            "auth_token": {
                "type": "string",
                "label": "Bearer Token",
                "label_t": "nodes.http_request.fields.auth_token.label",
                "section": "auth",
                "placeholder": "Bearer eyJhbGciOi...",
                "description": "Utilisé si Authentification = Bearer Token. Supporte {token}.",
                "description_t": "nodes.http_request.fields.auth_token.description",
                "display_if": {"field": "auth_type", "operator": "==", "value": "bearer"},
            },
            "auth_username": {
                "type": "string",
                "label": "Nom d'utilisateur (Basic Auth)",
                "label_t": "nodes.http_request.fields.auth_username.label",
                "section": "auth",
                "display_if": {"field": "auth_type", "operator": "==", "value": "basic"},
            },
            "auth_password": {
                "type": "string",
                "label": "Mot de passe (Basic Auth)",
                "label_t": "nodes.http_request.fields.auth_password.label",
                "section": "auth",
                "display_if": {"field": "auth_type", "operator": "==", "value": "basic"},
            },
            "auth_header_name": {
                "type": "string",
                "label": "Nom de la clé (En-tête ou Paramètre)",
                "label_t": "nodes.http_request.fields.auth_header_name.label",
                "section": "auth",
                "placeholder": "X-API-Key",
                "display_if": {"field": "auth_type", "operator": "in", "value": ["header", "query"]},
            },
            "auth_header_value": {
                "type": "string",
                "label": "Valeur de la clé",
                "label_t": "nodes.http_request.fields.auth_header_value.label",
                "section": "auth",
                "placeholder": "secret-api-key",
                "display_if": {"field": "auth_type", "operator": "in", "value": ["header", "query"]},
            },
            "body_type": {
                "type": "select",
                "label": "Format du corps (Body)",
                "label_t": "nodes.http_request.fields.body_type.label",
                "section": "body",
                "options": [
                    {"label": "JSON (application/json)", "label_t": "nodes.http_request.fields.body_type.options.json", "value": "json"},
                    {"label": "Multipart / Form-Data (avec fichiers)", "label_t": "nodes.http_request.fields.body_type.options.form_data", "value": "form_data"},
                    {"label": "Form URL-Encoded (application/x-www-form-urlencoded)", "label_t": "nodes.http_request.fields.body_type.options.form_urlencoded", "value": "form_urlencoded"},
                    {"label": "Texte brut (Raw)", "label_t": "nodes.http_request.fields.body_type.options.raw", "value": "raw"},
                    {"label": "Aucun corps (Vide)", "label_t": "nodes.http_request.fields.body_type.options.none", "value": "none"},
                ],
                "default": "json",
                "display_if": {"field": "method", "operator": "in", "value": ["POST", "PUT", "PATCH", "DELETE"]},
            },
            "body": {
                "type": "json",
                "label": "Corps de requête (JSON / Objet)",
                "label_t": "nodes.http_request.fields.body.label",
                "section": "body",
                "description": "Laissez vide pour relayer l'entrée reçue.",
                "description_t": "nodes.http_request.fields.body.description",
                "display_if": {
                    "and": [
                        {"field": "method", "operator": "in", "value": ["POST", "PUT", "PATCH", "DELETE"]},
                        {"field": "body_type", "operator": "in", "value": ["json", "form_urlencoded", "raw"]},
                    ]
                },
            },
            "form_fields": {
                "type": "json",
                "label": "Champs de formulaire textuels (Form-Data)",
                "label_t": "nodes.http_request.fields.form_fields.label",
                "section": "body",
                "description": "Dictionnaire clé/valeur pour les données de formulaire multipart.",
                "description_t": "nodes.http_request.fields.form_fields.description",
                "default": {},
                "display_if": {
                    "and": [
                        {"field": "method", "operator": "in", "value": ["POST", "PUT", "PATCH", "DELETE"]},
                        {"field": "body_type", "operator": "==", "value": "form_data"},
                    ]
                },
            },
            "files": {
                "type": "json",
                "label": "Fichiers joints (Multipart / Form-Data)",
                "label_t": "nodes.http_request.fields.files.label",
                "section": "body",
                "description": "Liste d'objets: [{'field_name': 'file', 'file_source': 'path'|'media_id'|'base64'|'content', 'file_path': '...', 'media_id': '...', 'filename': '...'}]",
                "description_t": "nodes.http_request.fields.files.description",
                "default": [],
                "display_if": {
                    "and": [
                        {"field": "method", "operator": "in", "value": ["POST", "PUT", "PATCH", "DELETE"]},
                        {"field": "body_type", "operator": "==", "value": "form_data"},
                    ]
                },
            },
            "timeout": {
                "type": "number",
                "label": "Délai d'attente (secondes)",
                "label_t": "nodes.http_request.fields.timeout.label",
                "section": "advanced",
                "default": 30,
            },
            "follow_redirects": {
                "type": "boolean",
                "label": "Suivre les redirections (Follow Redirects)",
                "label_t": "nodes.http_request.fields.follow_redirects.label",
                "section": "advanced",
                "default": True,
            },
            "verify_ssl": {
                "type": "boolean",
                "label": "Vérifier le certificat SSL (Verify SSL)",
                "label_t": "nodes.http_request.fields.verify_ssl.label",
                "section": "advanced",
                "default": True,
            },
            "fail_on_error": {
                "type": "boolean",
                "label": "Échouer si code HTTP >= 400",
                "label_t": "nodes.http_request.fields.fail_on_error.label",
                "section": "advanced",
                "default": True,
                "description": "Si désactivé, le nœud continuera normalement même sur les erreurs 4xx ou 5xx.",
                "description_t": "nodes.http_request.fields.fail_on_error.description",
            },
            "retry_on_failure": {
                "type": "boolean",
                "label": "Réessayer automatiquement en cas d'échec (Retry)",
                "label_t": "nodes.http_request.fields.retry_on_failure.label",
                "section": "advanced",
                "default": False,
            },
            "max_retries": {
                "type": "number",
                "label": "Nombre max de tentatives",
                "label_t": "nodes.http_request.fields.max_retries.label",
                "section": "advanced",
                "default": 3,
                "display_if": {"field": "retry_on_failure", "operator": "==", "value": True},
            },
            "retry_delay_seconds": {
                "type": "number",
                "label": "Délai entre les tentatives (secondes)",
                "label_t": "nodes.http_request.fields.retry_delay_seconds.label",
                "section": "advanced",
                "default": 2,
                "display_if": {"field": "retry_on_failure", "operator": "==", "value": True},
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

        # 1. Résolution des Query Parameters
        raw_query_params = config.get("query_params") or []
        query_dict: Dict[str, Any] = {}
        if isinstance(raw_query_params, list):
            for q_item in raw_query_params:
                if isinstance(q_item, dict):
                    k = ExecutionEngine.interpolate_value(q_item.get("key") or q_item.get("name") or "", eval_context)
                    v = ExecutionEngine.interpolate_value(q_item.get("value") or "", eval_context)
                    if k:
                        query_dict[str(k)] = v
        elif isinstance(raw_query_params, dict):
            for k, v in raw_query_params.items():
                interp_k = ExecutionEngine.interpolate_value(k, eval_context)
                interp_v = ExecutionEngine.interpolate_value(v, eval_context)
                if interp_k:
                    query_dict[str(interp_k)] = interp_v

        # 2. Résolution des Headers
        headers: Dict[str, Any] = {}
        headers_mode = str(config.get("headers_mode") or "key_value")
        if headers_mode == "key_value":
            raw_headers_kv = config.get("headers_key_value") or []
            if isinstance(raw_headers_kv, list):
                for h_item in raw_headers_kv:
                    if isinstance(h_item, dict):
                        k = ExecutionEngine.interpolate_value(h_item.get("key") or h_item.get("name") or "", eval_context)
                        v = ExecutionEngine.interpolate_value(h_item.get("value") or "", eval_context)
                        if k:
                            headers[str(k)] = str(v)
            elif isinstance(raw_headers_kv, dict):
                for k, v in raw_headers_kv.items():
                    headers[str(ExecutionEngine.interpolate_value(k, eval_context))] = str(ExecutionEngine.interpolate_value(v, eval_context))

        # En-têtes JSON additionnels
        raw_headers_json = config.get("headers") or {}
        if isinstance(raw_headers_json, dict):
            interp_h_json = ExecutionEngine.interpolate_value(raw_headers_json, eval_context)
            if isinstance(interp_h_json, dict):
                headers.update({str(k): str(v) for k, v in interp_h_json.items()})

        # 3. Authentification
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
                headers[str(h_name)] = str(h_val)
        elif auth_type == "query":
            q_name = ExecutionEngine.interpolate_value(config.get("auth_header_name") or "api_key", eval_context)
            q_val = ExecutionEngine.interpolate_value(config.get("auth_header_value") or "", eval_context)
            if q_name:
                query_dict[str(q_name)] = q_val

        # 4. Corps de requête (Body)
        body_type = str(config.get("body_type") or "").lower()
        raw_files = config.get("files") or []
        files_config = ExecutionEngine.interpolate_value(raw_files, eval_context) if isinstance(raw_files, (list, dict)) else []
        if isinstance(files_config, dict):
            files_config = [files_config]

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

        timeout = float(config.get("timeout") or 30.0)
        follow_redirects = config.get("follow_redirects", True)
        verify_ssl = config.get("verify_ssl", True)
        fail_on_error = config.get("fail_on_error", True)
        retry_on_failure = config.get("retry_on_failure", False)
        max_retries = int(config.get("max_retries") or 3) if retry_on_failure else 1
        retry_delay = float(config.get("retry_delay_seconds") or 2.0)
        response_format = str(config.get("response_format") or "autodetect").lower()

        req_kwargs: Dict[str, Any] = {
            "headers": headers,
            "params": query_dict if query_dict else None,
            "follow_redirects": follow_redirects,
        }
        if http_auth:
            req_kwargs["auth"] = http_auth

        if method in ("POST", "PUT", "PATCH", "DELETE"):
            if body_type == "form_data" or files_config:
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

        # Exécution avec gestion des retries et mesure du temps de réponse
        last_exception = None
        resp = None
        duration_ms = 0

        async with httpx.AsyncClient(timeout=timeout, verify=verify_ssl) as client:
            for attempt in range(1, max_retries + 1):
                t0 = time.time()
                try:
                    resp = await client.request(method=method, url=url, **req_kwargs)
                    duration_ms = int((time.time() - t0) * 1000)
                    if resp.status_code < 400 or not retry_on_failure:
                        break
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay * attempt)
                except Exception as ex:
                    last_exception = ex
                    duration_ms = int((time.time() - t0) * 1000)
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay * attempt)
                    else:
                        break

        if resp is None:
            raise RuntimeError(f"Échec de la requête HTTP vers {url} après {max_retries} tentative(s) : {last_exception}")

        # Traitement du format de réponse
        resp_data = None
        if response_format == "json":
            try:
                resp_data = resp.json()
            except Exception:
                resp_data = resp.text
        elif response_format == "text":
            resp_data = resp.text
        elif response_format == "base64":
            resp_data = base64.b64encode(resp.content).decode("ascii")
        else:  # autodetect
            try:
                resp_data = resp.json()
            except Exception:
                resp_data = resp.text

        output = {
            "status_code": resp.status_code,
            "body": resp_data,
            "data": resp_data,
            "headers": dict(resp.headers),
            "response_time_ms": duration_ms,
            "url": str(resp.url),
        }

        if resp.status_code >= 400 and fail_on_error:
            raise RuntimeError(f"Erreur HTTP {resp.status_code} reçue de {url} : {str(resp_data)[:250]}")

        return NodeExecutionResult(output_data=output, active_ports=["main"])
