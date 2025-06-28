import re
from setuptools import setup

def extract_dc_imports(dc_file_path):
    pattern = re.compile(r"from\s+([a-zA-Z0-9_./]+)\s+import\s+([a-zA-Z0-9_/, *]+)")
    modules = set()

    with open(dc_file_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line.startswith("//") or not line.startswith("from "):
                continue

            match = pattern.match(line)
            if not match:
                continue

            raw_base, imports_raw = match.groups()

            base_module_parts = raw_base.split("/")
            base_module = base_module_parts[0].replace("/", ".")

            for imp in imports_raw.split(","):
                imp = imp.strip()
                if imp == "*":
                    modules.add(base_module)
                    continue

                imp_parts = imp.split("/")
                class_base = imp_parts[0]
                suffixes = imp_parts[1:]

                if base_module.endswith(f".{class_base}"):
                    module_prefix = base_module[:-(len(class_base) + 1)]
                else:
                    module_prefix = base_module

                modules.add(f"{module_prefix}.{class_base}")
                for suffix in suffixes:
                    modules.add(f"{module_prefix}.{class_base}{suffix}")

    return sorted(modules)

dc_imports = extract_dc_imports("config/ttroff.dc")

manual_dynamic_imports = [
    "toontown.hood.GenericAnimatedProp",
    "toontown.hood.HQTelescopeAnimatedProp",
    "toontown.hood.FishAnimatedProp",
    "toontown.hood.HQPeriscopeAnimatedProp",
    "toontown.hood.PetShopFishAnimatedProp",
    "toontown.hood.SleepingHydrantAnimatedProp",
    "toontown.hood.ZeroAnimatedProp",
    "toontown.hood.HydrantInteractiveProp",
    "toontown.hood.MailboxInteractiveProp",
    "toontown.hood.TrashcanInteractiveProp"
]

all_imports = sorted(set(dc_imports + manual_dynamic_imports))

setup(
    name="ToontownPorkheffley",
    options={
        "build_apps": {
            "gui_apps": {
                "TTPHEngine": "run_game.py"
            },
            "include_patterns": [
                "astron/**",
                "config/**",
                "resources/**",
                "toontown/**",
                "otp/**",
                "logs/**",
                "settings.json"
            ],
            "exclude_patterns": [
                "backups/**",
                "launcher/**",
                "scripts/**",
                ".venv/**",
            ],
            "include_modules": {
                "*": all_imports
            },
            "plugins": ["pandagl", "p3openal_audio"],
            "platforms": ["win_amd64"],
            "icons": {
                "*": ["resources/ttph.jpg"]
            }
        }
    },
    install_requires=["panda3d", "pymongo", "semidbm", "debugpy", "requests"]
)