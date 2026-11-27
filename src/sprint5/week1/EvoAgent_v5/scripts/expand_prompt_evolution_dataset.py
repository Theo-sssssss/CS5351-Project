"""Rebuild the synthetic prompt corpus with complete, contextual Python diffs.

Run from the project root: python scripts/expand_prompt_evolution_dataset.py
Only fixture text is generated; the deliberately unsafe examples are never run.
"""

import ast
import difflib
import json
from pathlib import Path
import textwrap


DATASET = Path(__file__).resolve().parents[1] / "evaluation_data" / "prompt_evolution_130.jsonl"


def scenario(number):
    """Return imports, signature, shared setup, old body, new body and risk line."""
    scenarios = [
        (
            "import json", "decode_payload(payload)",
            '''
            if not isinstance(payload, str):
                raise TypeError("payload must be text")
            if len(payload) > MAX_INPUT_SIZE:
                raise ValueError("payload is too large")
            ''',
            '''
            result = json.loads(payload)
            return {"service": SERVICE_NAME, "data": result}
            ''',
            '''
            payload = payload.strip()
            if not payload:
                raise ValueError("payload is empty")
            result = eval(payload)
            return {
                "service": SERVICE_NAME,
                "data": result,
                "input_size": len(payload),
            }
            ''', "result = eval(payload)",
        ),
        (
            "import subprocess", "run_lookup(hostname)",
            '''
            if not isinstance(hostname, str):
                raise TypeError("hostname must be text")
            hostname = hostname.strip()
            if not hostname or len(hostname) > 253:
                raise ValueError("invalid hostname length")
            ''',
            '''
            completed = subprocess.run(["nslookup", hostname], shell=False, capture_output=True, timeout=5)
            return completed.stdout
            ''',
            '''
            command = "nslookup " + hostname
            completed = subprocess.run(command, shell=True, capture_output=True, timeout=5)
            completed.check_returncode()
            output = completed.stdout.decode("utf-8", errors="replace")
            return {
                "service": SERVICE_NAME,
                "output": output.strip(),
                "return_code": completed.returncode,
            }
            ''', "completed = subprocess.run(command, shell=True, capture_output=True, timeout=5)",
        ),
        (
            "import os", "build_client_options(region)",
            '''
            allowed_regions = {"test-east", "test-west"}
            if region not in allowed_regions:
                raise ValueError("unsupported region")
            timeout = 5
            ''',
            '''
            api_key = os.environ["FIXTURE_SERVICE_KEY"]
            return {"region": region, "api_key": api_key, "timeout": timeout}
            ''',
            '''
            # Intentionally fake credential for the hardcoded-secret fixture.
            api_key = "fixture-only-not-a-real-key"
            options = {
                "service": SERVICE_NAME,
                "region": region,
                "api_key": api_key,
                "timeout": timeout,
            }
            options["retries"] = 2
            return options
            ''', 'api_key = "fixture-only-not-a-real-key"',
        ),
        (
            "import json", "load_settings(raw_settings)",
            '''
            if not isinstance(raw_settings, str):
                raise TypeError("settings must be text")
            defaults = {"enabled": False, "batch_size": 10}
            ''',
            '''
            settings = json.loads(raw_settings)
            defaults.update(settings)
            return defaults
            ''',
            '''
            try:
                settings = json.loads(raw_settings)
                defaults.update(settings)
            except Exception:
                pass
            return {
                "service": SERVICE_NAME,
                "status": "loaded",
                "settings": defaults,
            }
            ''', "except Exception:",
        ),
        (
            "from pathlib import Path", "read_document(root, user_path)",
            '''
            if not isinstance(user_path, str):
                raise TypeError("document path must be text")
            if not user_path:
                raise ValueError("document path is required")
            base = Path(root).resolve()
            ''',
            '''
            target = (base / user_path).resolve()
            if not target.is_relative_to(base):
                raise ValueError("document is outside the root")
            return target.read_text(encoding="utf-8")
            ''',
            '''
            user_path = user_path.strip()
            if len(user_path) > MAX_INPUT_SIZE:
                raise ValueError("document path is too long")
            # Load the selected document for the preview response.
            with open(base / user_path) as handle:
                content = handle.read()
            return {
                "service": SERVICE_NAME,
                "content": content,
                "characters": len(content),
            }
            ''', "with open(base / user_path) as handle:",
        ),
        (
            "import hashlib", "sign_artifact(payload)",
            '''
            if not isinstance(payload, bytes):
                raise TypeError("artifact must be bytes")
            if len(payload) > MAX_INPUT_SIZE:
                raise ValueError("artifact is too large")
            ''',
            '''
            digest = hashlib.sha256(payload).hexdigest()
            return {"integrity_digest": digest}
            ''',
            '''
            digest = hashlib.md5(payload).hexdigest()
            manifest = {
                "service": SERVICE_NAME,
                "integrity_digest": digest,
                "byte_count": len(payload),
                "algorithm": "md5",
            }
            return manifest
            ''', "digest = hashlib.md5(payload).hexdigest()",
        ),
        (
            "import time", "fetch_snapshot(client, resource)",
            '''
            if not isinstance(resource, str) or not resource:
                raise ValueError("resource is required")
            delay_seconds = 0.1
            ''',
            '''
            for attempt in range(3):
                try:
                    return client.fetch(resource, timeout=5)
                except TimeoutError:
                    if attempt == 2:
                        raise
                    time.sleep(delay_seconds)
            ''',
            '''
            attempts = 0
            while True:
                attempts += 1
                try:
                    snapshot = client.fetch(resource, timeout=5)
                    return {
                        "service": SERVICE_NAME,
                        "snapshot": snapshot,
                        "attempts": attempts,
                    }
                except TimeoutError:
                    time.sleep(delay_seconds)
            ''', "while True:",
        ),
        (
            "", "attach_session(response, value)",
            '''
            if not isinstance(value, str) or not value:
                raise ValueError("session value is required")
            if len(value) > MAX_INPUT_SIZE:
                raise ValueError("session value is too large")
            ''',
            '''
            response.set_cookie("fixture_sid", value, secure=True, httponly=True, samesite="Lax")
            return response
            ''',
            '''
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            response.set_cookie("fixture_sid", value, secure=False, httponly=True, samesite="Lax")
            response.headers["X-Service"] = SERVICE_NAME
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
            ''', 'response.set_cookie("fixture_sid", value, secure=False, httponly=True, samesite="Lax")',
        ),
        (
            "import json", "decode_object(payload)",
            '''
            if not isinstance(payload, str):
                raise TypeError("payload must be text")
            if len(payload) > MAX_INPUT_SIZE:
                raise ValueError("payload is too large")
            ''',
            '''
            result = json.loads(payload)
            return result
            ''',
            '''
            payload = payload.strip()
            if not payload:
                raise ValueError("payload is empty")
            result = json.loads(payload)
            if not isinstance(result, dict):
                raise ValueError("expected a JSON object")
            return {
                "service": SERVICE_NAME,
                "data": result,
                "field_count": len(result),
            }
            ''', None,
        ),
        (
            "import subprocess", "run_healthcheck(mode)",
            '''
            allowed_modes = {"short", "full"}
            if mode not in allowed_modes:
                raise ValueError("unsupported healthcheck mode")
            ''',
            '''
            return subprocess.run(["fixture-healthcheck", "--mode", mode], shell=False, timeout=5)
            ''',
            '''
            command = ["fixture-healthcheck", "--mode", mode]
            completed = subprocess.run(command, shell=False, capture_output=True, timeout=5)
            completed.check_returncode()
            output = completed.stdout.decode("utf-8", errors="replace")
            return {
                "service": SERVICE_NAME,
                "mode": mode,
                "output": output.strip(),
            }
            ''', None,
        ),
        (
            "import hashlib", "build_manifest(payload)",
            '''
            if not isinstance(payload, bytes):
                raise TypeError("artifact must be bytes")
            if len(payload) > MAX_INPUT_SIZE:
                raise ValueError("artifact is too large")
            ''',
            '''
            return hashlib.sha256(payload).hexdigest()
            ''',
            '''
            digest = hashlib.sha256(payload).hexdigest()
            manifest = {
                "service": SERVICE_NAME,
                "integrity_digest": digest,
                "algorithm": "sha256",
                "byte_count": len(payload),
            }
            return manifest
            ''', None,
        ),
        (
            "", "refresh_session(response, value)",
            '''
            if not isinstance(value, str) or not value:
                raise ValueError("session value is required")
            if len(value) > MAX_INPUT_SIZE:
                raise ValueError("session value is too large")
            ''',
            '''
            response.set_cookie("fixture_sid", value, secure=True, httponly=True, samesite="Lax")
            return response
            ''',
            '''
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            response.set_cookie("fixture_sid", value, secure=True, httponly=True, samesite="Lax", max_age=900)
            response.headers["X-Service"] = SERVICE_NAME
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
            ''', None,
        ),
        (
            "", "lookup_user(cursor, user_id)",
            '''
            if not isinstance(user_id, int) or isinstance(user_id, bool):
                raise TypeError("user id must be an integer")
            if user_id <= 0:
                raise ValueError("user id must be positive")
            ''',
            '''
            cursor.execute("SELECT id, enabled FROM users WHERE id = ?", (user_id,))
            return cursor.fetchone()
            ''',
            '''
            cursor.execute("SELECT id, enabled FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row is None:
                return {"service": SERVICE_NAME, "found": False}
            return {
                "service": SERVICE_NAME,
                "found": True,
                "id": row[0],
                "enabled": bool(row[1]),
            }
            ''', None,
        ),
    ]
    return scenarios[number - 1]


def block(value):
    return textwrap.indent(textwrap.dedent(value).strip() + "\n", "    ")


def expand_cases(cases):
    for index, case in enumerate(cases):
        repository, number = divmod(index, 13)
        imports, signature, setup, old_body, new_body, risk = scenario(number + 1)
        path = "src/repo_%02d_case_%02d.py" % (repository + 1, number + 1)
        if case["id"] != "prompt-evolution-%04d" % (index + 1) or path not in case["after_files"]:
            raise ValueError("unexpected fixture order or path")
        prefix = (
            '"""Synthetic service example for offline review; contains no real user data."""\n\n'
            + (imports + "\n\n" if imports else "")
            + 'SERVICE_NAME = "fixture-service-%02d"\n' % (repository + 1)
            + "MAX_INPUT_SIZE = %d\n\n\n" % (4096 + repository * 128)
            + "def " + signature + ":\n"
            + '    """Handle one request for the synthetic service."""\n'
            + block(setup)
        )
        before = prefix + block(old_body)
        after = prefix + block(new_body)
        ast.parse(before, filename=path)
        ast.parse(after, filename=path)
        case["before_files"] = {path: before}
        case["after_files"] = {path: after}
        case["diff"] = "".join(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile="a/" + path, tofile="b/" + path, n=20,
        ))
        if bool(case["expected_findings"]) != bool(risk):
            raise ValueError("unexpected fixture labels")
        if risk:
            line = next(i for i, text in enumerate(after.splitlines(), 1) if text.strip() == risk)
            for finding in case["expected_findings"]:
                finding["start_line"] = finding["end_line"] = line
        case["source"] = {
            "generator": "prompt-evolution-proof-v2-contextual",
            "kind": "offline-fixture", "public_url": None,
        }
    return cases


def main():
    cases = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(cases) != 130:
        raise ValueError("expected 130 existing fixtures")
    cases = expand_cases(cases)
    content = "".join(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n" for case in cases)
    with DATASET.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    lengths = [len(case["diff"].splitlines()) for case in cases]
    print("Expanded %d fixtures; diff lines: %d-%d" % (len(cases), min(lengths), max(lengths)))


if __name__ == "__main__":
    main()
