from re        import findall, search
from json      import load, dump
from base64    import b64decode
from typing    import Optional, Tuple, List, Dict
from curl_cffi import requests
from ..        import Utils, Log
from ..exceptions import GrokParsingError, GrokNetworkError
from os        import path, makedirs

class Parser:

    mapping: dict = {}
    _mapping_loaded: bool = False

    grok_mapping: list = []
    _grok_mapping_loaded: bool = False

    BASE_DIR = path.dirname(path.dirname(path.abspath(__file__)))
    MAPPINGS_DIR = path.join(BASE_DIR, 'mappings')
    TXID_PATH = path.join(MAPPINGS_DIR, 'txid.json')
    GROK_PATH = path.join(MAPPINGS_DIR, 'grok.json')

    @classmethod
    def _ensure_mappings_dir(cls):
        if not path.exists(cls.MAPPINGS_DIR):
            makedirs(cls.MAPPINGS_DIR)

    @classmethod
    def _load__xsid_mapping(cls):
        if not cls._mapping_loaded and path.exists(cls.TXID_PATH):
            try:
                with open(cls.TXID_PATH, 'r') as f:
                    cls.mapping = load(f)
                cls._mapping_loaded = True
            except Exception as e:
                Log.Error(f"Failed to load txid mapping: {e}")

    @classmethod
    def _load_grok_mapping(cls):
        if not cls._grok_mapping_loaded and path.exists(cls.GROK_PATH):
            try:
                with open(cls.GROK_PATH, 'r') as f:
                    cls.grok_mapping = load(f)
                cls._grok_mapping_loaded = True
            except Exception as e:
                Log.Error(f"Failed to load grok mapping: {e}")

    @staticmethod
    def parse_values(html: str, loading: str = "loading-x-anim-0", scriptId: str = "") -> Tuple[str, Optional[List[int]]]:

        Parser._load__xsid_mapping()

        all_d_values = findall(r'"d":"(M[^"]{200,})"', html)
        if not all_d_values:
            raise GrokParsingError("Failed to find SVG path data in HTML.")

        try:
            loading_idx = int(loading.split("loading-x-anim-")[1])
            svg_data = all_d_values[loading_idx % len(all_d_values)]
        except (IndexError, ValueError):
            svg_data = all_d_values[0]

        if scriptId:
            if scriptId == "ondemand.s":
                script_link: str = 'https://abs.twimg.com/responsive-web/client-web/ondemand.s.' + Utils.between(html, f'"{scriptId}":"', '"') + 'a.js'
            else:
                script_link: str = f'https://grok.com/_next/{scriptId}'

            if script_link in Parser.mapping:
                numbers: list = Parser.mapping[script_link]
            else:
                try:
                    response = requests.get(script_link, impersonate="chrome136")
                    response.raise_for_status()
                    script_content: str = response.text
                except requests.errors.RequestError as e:
                    raise GrokNetworkError(f"Failed to fetch script for parsing: {e}")

                numbers: list = [int(x) for x in findall(r'x\[(\d+)\]\s*,\s*16', script_content)]
                if not numbers:
                    raise GrokParsingError(f"Failed to parse numbers from script: {script_link}")

                Parser.mapping[script_link] = numbers
                Parser._ensure_mappings_dir()
                try:
                    with open(Parser.TXID_PATH, 'w') as f:
                        dump(Parser.mapping, f)
                except Exception as e:
                    Log.Error(f"Failed to save txid mapping: {e}")

            return svg_data, numbers

        return svg_data, None


    @staticmethod
    def get_anim(html:  str, verification: str = "grok-site-verification") -> Tuple[str, str]:

        verification_token: str = Utils.between(html, f'"name":"{verification}","content":"', '"')
        if not verification_token:
            raise GrokParsingError(f"Failed to find verification token: {verification}")

        try:
            array: list = list(b64decode(verification_token))
            anim: str = "loading-x-anim-" + str(array[5] % 4)
            return verification_token, anim
        except Exception:
            return verification_token, "loading-x-anim-0"

    @staticmethod
    def parse_grok(scripts: list) -> Tuple[List[str], str]:

        Parser._load_grok_mapping()

        for index in Parser.grok_mapping:
            if index.get("action_script") in scripts:
                return index["actions"], index["xsid_script"]

        script_content1 = None
        script_content2 = None
        action_script = None

        for script in scripts:
            try:
                response = requests.get(f'https://grok.com{script}', impersonate="chrome136")
                response.raise_for_status()
                content: str = response.text
            except requests.errors.RequestError as e:
                continue

            if "anonPrivateKey" in content:
                script_content1 = content
                action_script = script
            elif "880932)" in content:
                script_content2 = content

        if not script_content1 or not script_content2:
            raise GrokParsingError("Failed to find required script contents for Grok actions.")

        actions: list = findall(r'createServerReference\)\("([a-f0-9]+)"', script_content1)
        xsid_match = search(r'"(static/chunks/[^"]+\.js)"[^}]*?\(880932\)', script_content2)
        xsid_script: str = xsid_match.group(1) if xsid_match else None

        if actions and xsid_script:
            Parser.grok_mapping.append({
                "xsid_script": xsid_script,
                "action_script": action_script,
                "actions": actions
            })

            Parser._ensure_mappings_dir()
            try:
                with open(Parser.GROK_PATH, 'w') as f:
                    dump(Parser.grok_mapping, f, indent=2)
            except Exception as e:
                Log.Error(f"Failed to save grok mapping: {e}")

            return actions, xsid_script
        else:
            raise GrokParsingError("Failed to parse actions or xsid_script from Grok scripts.")
