import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_demo_instances_are_separate_and_cannot_escape_owned_state():
    from tools.local_learning_process import STATE, instance_state

    assert instance_state("legacy") == STATE
    assert instance_state("judge-proof") == STATE / "judge-proof"
    assert instance_state("judge-proof") != instance_state("other")
    for invalid in ("../escape", "D:/outside", "", "a/b", "a\\b"):
        with pytest.raises(ValueError):
            instance_state(invalid)


@pytest.mark.skipif(os.name != "nt", reason="Windows task process-tree regression")
def test_task_parent_shutdown_reaps_children_and_grandchildren():
    import win32api
    import win32con
    import win32event

    root = Path(__file__).resolve().parents[3]
    child_code = (
        "import subprocess,sys,time; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'], "
        "creationflags=subprocess.CREATE_NO_WINDOW); print(p.pid,flush=True); time.sleep(30)"
    )
    parent_code = (
        f"import sys; sys.path.insert(0,{str(root)!r}); "
        "from tools.local_learning_process import bind_child_lifetime; bind_child_lifetime(); "
        "import subprocess,time,json; "
        f"p=subprocess.Popen([sys.executable,'-c',{child_code!r}], stdout=subprocess.PIPE, "
        "text=True, creationflags=subprocess.CREATE_NO_WINDOW); "
        "print(json.dumps([p.pid,int(p.stdout.readline())]),flush=True); time.sleep(30)"
    )
    process = subprocess.Popen(
        [sys._base_executable, "-c", parent_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    handles = []
    try:
        line = process.stdout.readline()
        assert line, process.stderr.read()
        for pid in json.loads(line):
            handles.append(win32api.OpenProcess(win32con.SYNCHRONIZE, False, pid))
        process.terminate()
        process.wait(timeout=5)
        assert all(
            win32event.WaitForSingleObject(handle, 5000) == win32event.WAIT_OBJECT_0
            for handle in handles
        )
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        for handle in handles:
            handle.Close()
