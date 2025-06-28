import sys

def main():
    print("=== TTPH Launcher Main ===")
    print("Calling ToontownStart...")

    try:
        import toontown.toonbase.ToontownStart
    except Exception as e:
        import traceback
        with open("ttp_launcher_crash.log", "w") as f:
            f.write("Exception in run_game main():\n")
            traceback.print_exc(file=f)
        raise

if __name__ == "__main__":
    main()