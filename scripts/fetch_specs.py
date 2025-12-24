from wxbench.specs import fetch_specs


if __name__ == "__main__":
    saved = fetch_specs()
    for path in saved:
        print(f"wrote {path}")
