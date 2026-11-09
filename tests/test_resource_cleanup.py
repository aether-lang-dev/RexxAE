"""Check that interrupted exports return all allocations to the host account."""
import ctypes as c
import json
from pathlib import Path
import sys


class Limits(c.Structure):
    _fields_ = [
        ("memory_bytes", c.c_uint64),
        ("deadline_ms", c.c_int64),
        ("deadline_counts", c.c_int),
        ("parent", c.c_void_p),
    ]


def bind(lib, name, result, *args):
    function = getattr(lib, name)
    function.restype = result
    function.argtypes = args
    return function


def main(library):
    lib = c.CDLL(str(Path(library).resolve()))
    ptr = c.c_void_p
    account_new = bind(lib, "aether_exec_account_new", ptr, c.POINTER(Limits))
    account_use = bind(lib, "aether_exec_use", c.c_int, ptr, ptr)
    account_used = bind(lib, "aether_exec_account_used", c.c_uint64, ptr)
    account_free = bind(lib, "aether_exec_account_free", None, ptr)
    create = bind(lib, "aether_rexxae_create", ptr, c.c_char_p)
    step = bind(lib, "aether_rexxae_step", c.c_int32, ptr, c.c_int32)
    destroy = bind(lib, "aether_rexxae_destroy", None, ptr)
    outcome = bind(lib, "aether_last_outcome", c.c_int)

    sources = {
        "large builtin": 'SAY LENGTH(COPIES("' + "x" * 1024 + '",300))\nEXIT 0\n',
        "dense parse": "x=1\n" * 1800 + "EXIT 0\n",
        "assignment": "x = 1 + 2 * 3\nSAY x\nEXIT 0\n",
        "collections": "x = [1, 2, 3]\ny = {foo: x, bar: 4}\nEXIT 0\n",
        "loop": "DO i = 1 TO 10\nSAY i\nEND\nEXIT 0\n",
        "procedure": "CALL work 1\nEXIT 0\nwork: PROCEDURE\nPARSE ARG input\nRETURN input\n",
    }
    for fixture in ("parse_cases", "routine_cases", "select_cases"):
        path = Path(__file__).with_name(fixture + ".json")
        for name, source, *_ in json.loads(path.read_text()):
            sources[f"{fixture}/{name}"] = source

    warm = create(b"EXIT 0\n")
    assert outcome() == 0 and warm
    destroy(warm)
    caps = [*range(16, 24001, 16), 32768, 65536, 100000, 131072]
    interrupted = set()
    for label, source in sources.items():
        encoded = source.encode()
        for cap in caps:
            account = account_new(c.byref(Limits(cap, 0, 0, None)))
            assert account
            ctx = None
            try:
                assert account_use(account, None) == 0
                ctx = create(encoded)
                stopped = outcome()
                stage = "create"
                if ctx and stopped == 0:
                    for _ in range(1000):
                        status = step(ctx, 32)
                        stopped = outcome()
                        stage = "step"
                        if stopped or status in (-1, 0, 2, 4):
                            break
                    else:
                        raise AssertionError(f"{label} did not stop or suspend at {cap}")
                assert stopped in (0, 4), (label, cap, stage, stopped)
                if stopped == 4:
                    interrupted.add(stage)
            finally:
                # Trusted teardown must run with the exhausted account detached.
                assert account_use(None, None) == 0
                if ctx:
                    destroy(ctx)
                retained = account_used(account)
                account_free(account)
            assert retained == 0, (label, cap, stage, stopped, retained)
    assert interrupted == {"create", "step"}, interrupted
    print(f"Allocation cleanup passed for {len(sources) * len(caps)} script/cap combinations")

    # Time one export at a time so a slow parser cannot satisfy the step case.
    for stage in ("create", "step"):
        ctx = None
        if stage == "step":
            ctx = create(b"SAY LENGTH(COPIES('x',1048576))\nEXIT 0\n")
            assert ctx and outcome() == 0
        account = account_new(c.byref(Limits(0, 2, 1, None)))  # active milliseconds
        assert account and account_use(account, None) == 0
        try:
            if stage == "create":
                ctx = create(b"/*" + b"x" * 1048576 + b"*/\nEXIT 0\n")
            else:
                step(ctx, 32)
            stopped = outcome()
        finally:
            assert account_use(None, None) == 0
            if ctx:
                destroy(ctx)
            retained = account_used(account)
            account_free(account)
        assert (stopped, retained) == (2, 0), (stage, stopped, retained)

    ctx = create(b"EXIT 0\n")
    assert ctx and outcome() == 0
    try:
        assert step(ctx, 32) == 0 and outcome() == 0
    finally:
        destroy(ctx)
    print("Deadline cleanup passed for parsing and a long builtin")


if __name__ == "__main__":
    main(sys.argv[1])
