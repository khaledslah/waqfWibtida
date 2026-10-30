"""
Status helper for _full_run.
  python run_status.py summary
  python run_status.py next12 K     -> next K batch tags needing pass 1/2 (not done, not launched)
  python run_status.py next3 K      -> next K batch tags with pass12 done but pass3 not done/launched
  python run_status.py mark12 TAG.. / mark3 TAG..   -> mark launched
  python run_status.py check        -> validate finished outputs (JSON parses, counts)
"""
import json
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parent / "_full_run"
MAN = json.load(open(RUN / "MANIFEST.json", encoding="utf-8"))
LF = RUN / "LAUNCHED.json"
L = json.load(open(LF, encoding="utf-8")) if LF.exists() else {"p12": [], "p3": []}


def save():
    LF.write_text(json.dumps(L, indent=1), encoding="utf-8")


def done(path):
    return Path(path).exists()


def load(path):
    return json.load(open(path, encoding="utf-8-sig"))


def main():
    cmd = sys.argv[1]
    if cmd == "summary":
        n = len(MAN)
        d12 = sum(done(m["pass12_out"]) for m in MAN)
        d3 = sum(done(m["pass3_out"]) for m in MAN)
        print(f"batches={n} pass12_done={d12} pass12_launched={len(L['p12'])} pass3_done={d3} pass3_launched={len(L['p3'])}")
    elif cmd == "next12":
        k = int(sys.argv[2])
        out = [m["tag"] for m in MAN if not done(m["pass12_out"]) and m["tag"] not in L["p12"]][:k]
        print(" ".join(out))
    elif cmd == "next3":
        k = int(sys.argv[2])
        out = [m["tag"] for m in MAN if done(m["pass12_out"]) and not done(m["pass3_out"]) and m["tag"] not in L["p3"]][:k]
        print(" ".join(out))
    elif cmd in ("mark12", "mark3"):
        key = "p12" if cmd == "mark12" else "p3"
        for t in sys.argv[2:]:
            if t not in L[key]:
                L[key].append(t)
        save()
        print("ok")
    elif cmd == "check":
        bad = 0
        tw = ops = 0
        for m in MAN:
            for key in ("pass12_out", "pass3_out"):
                p = m[key]
                if not done(p):
                    continue
                try:
                    d = load(p)
                except Exception as ex:  # noqa
                    print("BAD JSON", p, ex)
                    bad += 1
                    continue
                if key == "pass12_out":
                    tw += len(d.get("waqfs", []))
                    ops += sum(len(a.get("opinions", [])) for w in d.get("waqfs", []) for a in w.get("apparatus", []))
        print(f"bad={bad} waqfs={tw} opinions={ops}")


if __name__ == "__main__":
    main()
