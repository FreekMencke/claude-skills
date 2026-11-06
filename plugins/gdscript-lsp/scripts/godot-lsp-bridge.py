#!/usr/bin/env python3
"""Connect Claude Code's stdio LSP client to Godot's GDScript language server, which only listens on TCP.

Claude Code starts this the first time it needs the gdscript server. It starts a headless Godot editor on a free local
port, relays bytes both ways unchanged (both sides frame messages with Content-Length, so nothing needs parsing), and
stops the editor when stdin closes. Everything it logs goes to stderr: Claude Code reads stdout as protocol only.

Environment:
  GODOT          Godot 4 binary, a path or a name on PATH (default: godot)
  GODOT_PROJECT  folder holding project.godot, absolute or relative to the project root (default: the project root if
                 it holds one, else the one folder directly under it that does, skipping addons/ and spikes/)
"""
import os
import queue
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

SKIPPED_FOLDERS = {"addons", "spikes"}
# Inside the plugin's 120 s startupTimeout. A cold import of a small project took about 6 s.
PORT_WAIT_SECONDS = 110


def fail(message):
    print(f"godot-lsp-bridge: {message}", file=sys.stderr, flush=True)
    sys.exit(1)


def find_project(root):
    override = os.environ.get("GODOT_PROJECT")
    if override:
        project = (root / override).resolve()
        if not (project / "project.godot").is_file():
            fail(f"GODOT_PROJECT={override}: no project.godot in {project}")
        return project
    if (root / "project.godot").is_file():
        return root
    found = sorted(
        folder
        for folder in root.iterdir()
        if folder.is_dir()
        and folder.name not in SKIPPED_FOLDERS
        and not folder.name.startswith(".")
        and (folder / "project.godot").is_file()
    )
    if len(found) == 1:
        return found[0]
    if found:
        fail(f"several Godot projects under {root} ({', '.join(f.name for f in found)}); set GODOT_PROJECT to one")
    fail(f"no project.godot in {root} or a folder directly under it; set GODOT_PROJECT")


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def die_with_parent():
    # Linux only: if this bridge is killed outright, the kernel stops the editor too instead of leaving it running.
    import ctypes

    PR_SET_PDEATHSIG = 1
    ctypes.CDLL(None, use_errno=True).prctl(PR_SET_PDEATHSIG, signal.SIGTERM)


def start_editor(godot, project, port):
    return subprocess.Popen(
        [godot, "--headless", "--editor", "--path", str(project), "--lsp-port", str(port)],
        stdin=subprocess.DEVNULL,
        stdout=sys.stderr.fileno(),
        preexec_fn=die_with_parent if sys.platform.startswith("linux") else None,
    )


def connect(editor, port):
    deadline = time.monotonic() + PORT_WAIT_SECONDS
    while True:
        if editor.poll() is not None:
            fail(f"Godot exited with code {editor.returncode} before opening port {port}")
        try:
            return socket.create_connection(("127.0.0.1", port), timeout=1)
        except OSError:
            if time.monotonic() > deadline:
                fail(f"Godot didn't open port {port} within {PORT_WAIT_SECONDS} s")
            time.sleep(0.25)


def stop(editor):
    if editor.poll() is None:
        editor.terminate()
        try:
            editor.wait(5)
        except subprocess.TimeoutExpired:
            editor.kill()
            editor.wait()


def relay(read, write, side, ended):
    try:
        while chunk := read(65536):
            write(chunk)
    except OSError:
        pass
    ended.put(side)


def write_stdout(chunk):
    sys.stdout.buffer.write(chunk)
    sys.stdout.buffer.flush()


def main():
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    project = find_project(root)
    godot = shutil.which(os.environ.get("GODOT", "godot"))
    if not godot:
        fail(f"Godot not found: set GODOT or put godot on PATH (looked for {os.environ.get('GODOT', 'godot')})")

    for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(signum, lambda *_: sys.exit(0))

    port = free_port()
    print(f"godot-lsp-bridge: starting {godot} on {project}, port {port}", file=sys.stderr, flush=True)
    editor = start_editor(godot, project, port)
    ended = queue.Queue()
    try:
        conn = connect(editor, port)
        conn.settimeout(None)
        threading.Thread(target=relay, args=(lambda n: os.read(0, n), conn.sendall, "client", ended), daemon=True).start()
        threading.Thread(target=relay, args=(conn.recv, write_stdout, "godot", ended), daemon=True).start()
        first_closed = ended.get()
    finally:
        stop(editor)
    if first_closed == "godot":
        # A non-zero exit counts as a crash, so Claude Code restarts the server (restartOnCrash, maxRestarts).
        fail(f"Godot closed the connection (editor exit code {editor.returncode})")


if __name__ == "__main__":
    main()
