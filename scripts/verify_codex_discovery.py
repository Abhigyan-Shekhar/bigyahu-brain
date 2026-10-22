"""Verify actual Codex MCP discovery without starting an agent or a coding chat."""

import argparse
import json
import selectors
import subprocess
import time
from pathlib import Path

EXPECTED = {
    "search_code", "read_code", "repository_files", "search_history", "resolve_evidence",
    "repository_status", "get_context", "trace_decision", "find_owner", "check_change", "remember"
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check-change",
        action="store_true",
        help="Invoke check_change through an ephemeral Codex protocol session (no model turn)",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repo-root", help="Absolute Git root for a registry-mode server")
    parser.add_argument(
        "--retrieve-file", help="Verify code search/read, inventory, history and citation reopening for this indexed file",
    )
    parser.add_argument(
        "--repository-status", action="store_true",
        help="Verify configured repository identity and freshness through Codex (no model turn)",
    )
    args = parser.parse_args()
    process = subprocess.Popen(
        ["codex", "app-server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)

    def rpc(request_id, method, params):
        if method == "mcpServer/tool/call" and args.repo_root:
            params = {**params, "arguments": {**params["arguments"], "repo_root": args.repo_root}}
        process.stdin.write(
            json.dumps({"id": request_id, "method": method, "params": params}) + "\n"
        )
        process.stdin.flush()
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if not selector.select(1):
                continue
            line = process.stdout.readline()
            if not line:
                raise RuntimeError("Codex app-server exited before responding")
            response = json.loads(line)
            if response.get("id") == request_id:
                if "error" in response:
                    raise RuntimeError(response["error"])
                return response["result"]
        raise TimeoutError(method)

    try:
        rpc(
            1, "initialize", {"clientInfo": {"name": "company-brain-integration", "version": "0.1"}}
        )
        process.stdin.write(json.dumps({"method": "initialized"}) + "\n")
        process.stdin.flush()
        inventory = rpc(2, "mcpServerStatus/list", {"serverName": "company-brain"})
        matches = [s for s in inventory["data"] if s["name"] == "company-brain"]
        if len(matches) != 1:
            raise RuntimeError("Company Brain was not discovered by Codex")
        server = matches[0]
        if server.get("toolsError") or not EXPECTED.issubset(server["tools"]):
            raise RuntimeError("Tool discovery failed or tool inventory differs from contract")
        report = {
            "status": "ok",
            "client": "codex app-server",
            "server": "company-brain",
            "server_info": server["serverInfo"],
            "tools": sorted(server["tools"]),
            "tools_error": server.get("toolsError"),
            "database_verified": False,
            "model_selected_tool": False,
        }
        if args.repository_status:
            session = rpc(10, "thread/start", {"cwd": str(Path.cwd()), "ephemeral": True})
            call = rpc(11, "mcpServer/tool/call", {
                "threadId": session["thread"]["id"], "server": "company-brain",
                "tool": "repository_status", "arguments": {},
            })
            payload = call.get("structuredContent")
            if payload is None:
                payload = json.loads(next(c["text"] for c in call["content"] if c["type"] == "text"))
            if call.get("isError") or payload.get("status") != "ok":
                raise RuntimeError("Repository is not ready: " + json.dumps(payload))
            report["repository_status"] = payload
            report["database_verified"] = True
        if args.retrieve_file:
            session = rpc(20, "thread/start", {"cwd": str(Path.cwd()), "ephemeral": True})

            def retrieve(request_id, tool, arguments):
                call = rpc(request_id, "mcpServer/tool/call", {
                    "threadId": session["thread"]["id"], "server": "company-brain",
                    "tool": tool, "arguments": arguments,
                })
                payload = call.get("structuredContent")
                if payload is None:
                    payload = json.loads(next(c["text"] for c in call["content"] if c["type"] == "text"))
                if call.get("isError") or payload.get("status") != "ok":
                    raise RuntimeError(tool + " failed: " + json.dumps(payload))
                return payload

            found = retrieve(21, "search_code", {"query": args.retrieve_file})
            if not any(row["path"] == args.retrieve_file for row in found["items"]):
                raise RuntimeError("Requested file was not found by code search")
            inventory = retrieve(22, "repository_files", {"query": args.retrieve_file})
            if args.retrieve_file not in json.loads(inventory["checked_evidence"][0]["text"])["paths"]:
                raise RuntimeError("Requested file was not found in inventory")
            proof = retrieve(23, "read_code", {"path": args.retrieve_file})["checked_evidence"][0]
            reopened = retrieve(24, "resolve_evidence", {"evidence_id": proof["id"]})
            if reopened["checked_evidence"] != [proof]:
                raise RuntimeError("Code citation could not be reproduced")
            history = retrieve(25, "search_history", {"files": [args.retrieve_file]})
            if not history["items"] or not history["checked_evidence"]:
                raise RuntimeError("No checked historical evidence returned for requested file")
            proof = history["checked_evidence"][0]
            reopened = retrieve(26, "resolve_evidence", {"evidence_id": proof["id"]})
            if reopened["checked_evidence"] != [proof]:
                raise RuntimeError("Historical citation could not be reproduced")
            report["retrieval_verified"] = True
            report["retrieval_file"] = args.retrieve_file
            report["database_verified"] = True
        if args.check_change:
            session = rpc(3, "thread/start", {"cwd": str(Path.cwd()), "ephemeral": True})
            thread_id = session["thread"]["id"]
            call = rpc(
                4,
                "mcpServer/tool/call",
                {
                    "threadId": thread_id,
                    "server": "company-brain",
                    "tool": "check_change",
                    "arguments": {
                        "files": ["src/requests/sessions.py"],
                        "symbols": ["SessionRedirectMixin.should_strip_auth"],
                    },
                },
            )
            report["method"] = "mcpServer/tool/call"
            report["tool_result"] = call
            payload = call.get("structuredContent")
            if payload is None:
                payload = json.loads(
                    next(c["text"] for c in call["content"] if c["type"] == "text")
                )
            if call.get("isError") or payload.get("status") != "ok":
                raise RuntimeError("Codex tool call failed: " + json.dumps(call))
            if not any(len(p["path"]) == 3 for p in payload.get("caller_paths", [])):
                raise RuntimeError("No two-hop caller evidence returned")
            report["database_verified"] = True
        if args.output:
            args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: v for k, v in report.items() if k != "tool_result"}, indent=2))

    finally:
        selector.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    main()
