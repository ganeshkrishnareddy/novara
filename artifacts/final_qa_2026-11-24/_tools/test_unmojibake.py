samples = [
    "NOVARA ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â unified web application",
    "NOVARA Ãƒâ€šÃ‚Â· Everything Connected. Everything Under Control.",
    'Search everythingÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦',
    "Counts are calculated by the API from current workspace rows ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â not cached or estimated.",
    "Loading NOVARAÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â¦",
]


def mixed_encode(text):
    out = bytearray()
    for ch in text:
        try:
            out += ch.encode("cp1252")
        except UnicodeEncodeError:
            out += ch.encode("latin-1")
    return bytes(out)


def undo_once(text):
    return mixed_encode(text).decode("utf-8")


for s in samples:
    print("IN :", repr(s))
    cur = s
    for i in range(6):
        try:
            cur = undo_once(cur)
        except UnicodeDecodeError as exc:
            print("  stop:", exc)
            break
        print(f"  pass {i+1}: {cur!r}")
    print()
