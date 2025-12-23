from .           import Log, Run, Utils, Parser, Signature, Anon, Headers
from .exceptions import GrokError, GrokNetworkError, GrokParsingError, GrokAuthError, GrokSessionError
from curl_cffi   import requests, CurlMime
from dataclasses import dataclass, field
from bs4         import BeautifulSoup
from json        import dumps, loads
from secrets     import token_hex
from uuid        import uuid4
from typing      import Generator

@dataclass
class Models:
    models: dict[str, list[str]] = field(default_factory=lambda: {
        "grok-3-auto": ["MODEL_MODE_AUTO", "auto"],
        "grok-3-fast": ["MODEL_MODE_FAST", "fast"],
        "grok-4": ["MODEL_MODE_EXPERT", "expert"],
        "grok-4-mini-thinking-tahoe": ["MODEL_MODE_GROK_4_MINI_THINKING", "grok-4-mini-thinking"],
    })

    def get_model_mode(self, model: str, index: int) -> str:
        return self.models.get(model, ["MODEL_MODE_AUTO", "auto"])[index]

_Models = Models()

class Grok:
    def __init__(self, model: str = "grok-3-auto", proxy: str = None) -> None:
        self.session: requests.session.Session = requests.Session(impersonate="chrome136", default_headers=False)
        self.headers: Headers = Headers()

        self.model_mode: str = _Models.get_model_mode(model, 0)
        self.mode: str = _Models.get_model_mode(model, 1)

        self.model = model

        self.c_run: int = 0
        self.keys: dict = Anon.generate_keys()
        if proxy:
            self.session.proxies = {
                "all": proxy
            }

    def _load(self, extra_data: dict = None) -> None:

        if not extra_data:
            self.session.headers = self.headers.LOAD
            try:
                load_site: requests.models.Response = self.session.get('https://grok.com/c')
                load_site.raise_for_status()
            except requests.errors.RequestError as e:
                raise GrokNetworkError(f"Failed to load Grok: {e}")

            self.session.cookies.update(load_site.cookies)

            scripts: list = [s['src'] for s in BeautifulSoup(load_site.text, 'html.parser').find_all('script', src=True) if s['src'].startswith('/_next/static/chunks/')]
            if not scripts:
                raise GrokParsingError("Failed to find necessary scripts on Grok site.")

            self.actions, self.xsid_script = Parser.parse_grok(scripts)

            self.baggage: str = Utils.between(load_site.text, '<meta name="baggage" content="', '"')
            self.sentry_trace: str = Utils.between(load_site.text, '<meta name="sentry-trace" content="', '-')

            if not self.baggage or not self.sentry_trace:
                raise GrokParsingError("Failed to parse metadata from Grok site.")
        else:
            self.session.cookies.update(extra_data["cookies"])

            self.actions: list = extra_data["actions"]
            self.xsid_script: list =  extra_data["xsid_script"]
            self.baggage: str = extra_data["baggage"]
            self.sentry_trace: str = extra_data["sentry_trace"]


    def c_request(self, next_action: str) -> None:

        self.session.headers = self.headers.C_REQUEST
        self.session.headers.update({
            'baggage': self.baggage,
            'next-action': next_action,
            'sentry-trace': f'{self.sentry_trace}-{str(uuid4()).replace("-", "")[:16]}-0',
        })
        self.session.headers = Headers.fix_order(self.session.headers, self.headers.C_REQUEST)

        if self.c_run == 0:
            self.session.headers.pop("content-type", None)

            mime = CurlMime()
            mime.addpart(name="1", data=bytes(self.keys["userPublicKey"]), filename="blob", content_type="application/octet-stream")
            mime.addpart(name="0", filename=None, data='[{"userPublicKey":"$o1"}]')

            try:
                c_request: requests.models.Response = self.session.post("https://grok.com/c", multipart=mime)
                c_request.raise_for_status()
            except requests.errors.RequestError as e:
                raise GrokNetworkError(f"Network error during c_request(0): {e}")

            self.session.cookies.update(c_request.cookies)

            self.anon_user: str = Utils.between(c_request.text, '{"anonUserId":"', '"')
            if not self.anon_user:
                raise GrokParsingError("Failed to parse anonUserId from c_request.")
            self.c_run += 1

        else:

            match self.c_run:
                case 1:
                    data: str = dumps([{"anonUserId":self.anon_user}])
                case 2:
                    data: str = dumps([{"anonUserId":self.anon_user,**self.challenge_dict}])

            try:
                c_request: requests.models.Response = self.session.post('https://grok.com/c', data=data)
                c_request.raise_for_status()
            except requests.errors.RequestError as e:
                raise GrokNetworkError(f"Network error during c_request({self.c_run}): {e}")

            self.session.cookies.update(c_request.cookies)

            match self.c_run:
                case 1:
                    start_idx = c_request.content.hex().find("3a6f38362c")
                    if start_idx != -1:
                        start_idx += len("3a6f38362c")
                        end_idx = c_request.content.hex().find("313a", start_idx)
                        if end_idx != -1:
                            challenge_hex = c_request.content.hex()[start_idx:end_idx]
                            challenge_bytes = bytes.fromhex(challenge_hex)
                        else:
                             raise GrokParsingError("Failed to find end index for challenge hex.")
                    else:
                         raise GrokParsingError("Failed to find start index for challenge hex.")

                    self.challenge_dict: dict = Anon.sign_challenge(challenge_bytes, self.keys["privateKey"])
                    Log.Success(f"Solved Challenge: {self.challenge_dict}")
                case 2:
                    self.verification_token, self.anim = Parser.get_anim(c_request.text, "grok-site-verification")
                    self.svg_data, self.numbers = Parser.parse_values(c_request.text, self.anim, self.xsid_script)

                    if not self.verification_token or not self.svg_data:
                         raise GrokParsingError("Failed to parse verification token or SVG data.")

            self.c_run += 1


    def _get_conversation_data(self, message: str, extra_data: dict = None) -> dict:
        """Helper to build conversation data payload."""
        if not extra_data:
            return {
                'temporary': False,
                'modelName': self.model,
                'message': message,
                'fileAttachments': [],
                'imageAttachments': [],
                'disableSearch': False,
                'enableImageGeneration': True,
                'returnImageBytes': False,
                'returnRawGrokInXaiRequest': False,
                'enableImageStreaming': True,
                'imageGenerationCount': 2,
                'forceConcise': False,
                'toolOverrides': {},
                'enableSideBySide': True,
                'sendFinalMetadata': True,
                'isReasoning': "THINKING" in self.model_mode,
                'webpageUrls': [],
                'disableTextFollowUps': False,
                'responseMetadata': {
                    'requestModelDetails': {
                        'modelId': self.model,
                    },
                },
                'disableMemory': False,
                'forceSideBySide': False,
                'modelMode': self.model_mode,
                'isAsyncChat': False,
            }
        else:
            return {
                'message': message,
                'modelName': self.model,
                'parentResponseId': extra_data["parentResponseId"],
                'disableSearch': False,
                'enableImageGeneration': True,
                'imageAttachments': [],
                'returnImageBytes': False,
                'returnRawGrokInXaiRequest': False,
                'fileAttachments': [],
                'enableImageStreaming': True,
                'imageGenerationCount': 2,
                'forceConcise': False,
                'toolOverrides': {},
                'enableSideBySide': True,
                'sendFinalMetadata': True,
                'customPersonality': '',
                'isReasoning': "THINKING" in self.model_mode,
                'webpageUrls': [],
                'metadata': {
                    'requestModelDetails': {
                        'modelId': self.model,
                    },
                    'request_metadata': {
                        'model': self.model,
                        'mode': self.mode,
                    },
                },
                'disableTextFollowUps': False,
                'disableArtifact': False,
                'isFromGrokFiles': False,
                'disableMemory': False,
                'forceSideBySide': False,
                'modelMode': self.model_mode,
                'isAsyncChat': False,
                'skipCancelCurrentInflightRequests': False,
                'isRegenRequest': False,
            }

    def chat(self, message: str, extra_data: dict = None) -> dict:
        if not extra_data:
            self._load()
            self.c_request(self.actions[0])
            self.c_request(self.actions[1])
            self.c_request(self.actions[2])
            xsid: str = Signature.generate_sign('/rest/app-chat/conversations/new', 'POST', self.verification_token, self.svg_data, self.numbers)
            url = 'https://grok.com/rest/app-chat/conversations/new'
        else:
            self._load(extra_data)
            self.c_run: int = 1
            self.anon_user: str = extra_data["anon_user"]
            self.keys["privateKey"] = extra_data["privateKey"]
            self.c_request(self.actions[1])
            self.c_request(self.actions[2])
            xsid: str = Signature.generate_sign(f'/rest/app-chat/conversations/{extra_data["conversationId"]}/responses', 'POST', self.verification_token, self.svg_data, self.numbers)
            url = f'https://grok.com/rest/app-chat/conversations/{extra_data["conversationId"]}/responses'

        self.session.headers = self.headers.CONVERSATION
        self.session.headers.update({
            'baggage': self.baggage,
            'sentry-trace': f'{self.sentry_trace}-{str(uuid4()).replace("-", "")[:16]}-0',
            'x-statsig-id': xsid,
            'x-xai-request-id': str(uuid4()),
            'traceparent': f"00-{token_hex(16)}-{token_hex(8)}-00"
        })
        self.session.headers = Headers.fix_order(self.session.headers, self.headers.CONVERSATION)

        conversation_data = self._get_conversation_data(message, extra_data)

        try:
            convo_request: requests.models.Response = self.session.post(url, json=conversation_data, timeout=9999)
            convo_request.raise_for_status()
        except requests.errors.RequestError as e:
            raise GrokNetworkError(f"Network error during chat: {e}")

        if "modelResponse" in convo_request.text:
            response = conversation_id = parent_response = image_urls = None
            stream_response: list = []

            for response_dict in convo_request.text.strip().split('\n'):
                try:
                    data: dict = loads(response_dict)
                except Exception:
                    continue

                if not extra_data:
                    token: str = data.get('result', {}).get('response', {}).get('token')
                    if not conversation_id and data.get('result', {}).get('conversation', {}).get('conversationId'):
                        conversation_id: str = data['result']['conversation']['conversationId']
                    if not parent_response and data.get('result', {}).get('response', {}).get('modelResponse', {}).get('responseId'):
                        parent_response: str = data['result']['response']['modelResponse']['responseId']
                    if not image_urls and data.get('result', {}).get('response', {}).get('modelResponse', {}).get('generatedImageUrls', {}):
                        image_urls: str = data['result']['response']['modelResponse']['generatedImageUrls']
                else:
                    token: str = data.get('result', {}).get('token')
                    if not parent_response and data.get('result', {}).get('modelResponse', {}).get('responseId'):
                        parent_response: str = data['result']['modelResponse']['responseId']
                    if not image_urls and data.get('result', {}).get('modelResponse', {}).get('generatedImageUrls', {}):
                        image_urls: str = data['result']['modelResponse']['generatedImageUrls']
                    conversation_id = extra_data["conversationId"]

                if token:
                    stream_response.append(token)

                if not response and data.get('result', {}).get('modelResponse', {}).get('message'):
                    response: str = data['result']['modelResponse']['message']
                elif not response and not extra_data and data.get('result', {}).get('response', {}).get('modelResponse', {}).get('message'):
                     response: str = data['result']['response']['modelResponse']['message']

            return {
                "response": response,
                "stream_response": stream_response,
                "images": image_urls,
                "extra_data": {
                    "anon_user": self.anon_user,
                    "cookies": self.session.cookies.get_dict(),
                    "actions": self.actions,
                    "xsid_script": self.xsid_script,
                    "baggage": self.baggage,
                    "sentry_trace": self.sentry_trace,
                    "conversationId": conversation_id,
                    "parentResponseId": parent_response,
                    "privateKey": self.keys["privateKey"]
                }
            }
        else:
            if 'rejected by anti-bot rules' in convo_request.text:
                Log.Info("Anti-bot detected, retrying with new session...")
                return Grok(self.model, self.session.proxies.get("all")).chat(message=message, extra_data=extra_data)

            Log.Error(f"Grok Error: {convo_request.text}")
            raise GrokError(f"Grok API error: {convo_request.text}")

    def chat_stream(self, message: str, extra_data: dict = None) -> Generator[dict, None, None]:
        if not extra_data:
            self._load()
            self.c_request(self.actions[0])
            self.c_request(self.actions[1])
            self.c_request(self.actions[2])
            xsid: str = Signature.generate_sign('/rest/app-chat/conversations/new', 'POST', self.verification_token, self.svg_data, self.numbers)
            url = 'https://grok.com/rest/app-chat/conversations/new'
        else:
            self._load(extra_data)
            self.c_run: int = 1
            self.anon_user: str = extra_data["anon_user"]
            self.keys["privateKey"] = extra_data["privateKey"]
            self.c_request(self.actions[1])
            self.c_request(self.actions[2])
            xsid: str = Signature.generate_sign(f'/rest/app-chat/conversations/{extra_data["conversationId"]}/responses', 'POST', self.verification_token, self.svg_data, self.numbers)
            url = f'https://grok.com/rest/app-chat/conversations/{extra_data["conversationId"]}/responses'

        self.session.headers = self.headers.CONVERSATION
        self.session.headers.update({
            'baggage': self.baggage,
            'sentry-trace': f'{self.sentry_trace}-{str(uuid4()).replace("-", "")[:16]}-0',
            'x-statsig-id': xsid,
            'x-xai-request-id': str(uuid4()),
            'traceparent': f"00-{token_hex(16)}-{token_hex(8)}-00"
        })
        self.session.headers = Headers.fix_order(self.session.headers, self.headers.CONVERSATION)

        conversation_data = self._get_conversation_data(message, extra_data)

        try:
            response = self.session.post(url, json=conversation_data, stream=True, timeout=9999)
            response.raise_for_status()
        except requests.errors.RequestError as e:
            raise GrokNetworkError(f"Network error during chat_stream: {e}")

        full_response_text = ""
        conversation_id = extra_data.get("conversationId") if extra_data else None
        parent_response = None

        for line in response.iter_lines():
            if not line:
                continue

            decoded_line = line.decode('utf-8')
            try:
                data = loads(decoded_line)
            except Exception:
                continue

            # Handle both new and existing conversation structures
            if not extra_data:
                token = data.get('result', {}).get('response', {}).get('token')
                if not conversation_id:
                    conversation_id = data.get('result', {}).get('conversation', {}).get('conversationId')
                if not parent_response:
                    parent_response = data.get('result', {}).get('response', {}).get('modelResponse', {}).get('responseId')
            else:
                token = data.get('result', {}).get('token')
                if not parent_response:
                    parent_response = data.get('result', {}).get('modelResponse', {}).get('responseId')

            if token:
                full_response_text += token
                yield {
                    "token": token,
                    "meta": None
                }

        # Yield final metadata needed for next turn
        yield {
            "token": None,
            "meta": {
                "response": full_response_text,
                "extra_data": {
                    "anon_user": self.anon_user,
                    "cookies": self.session.cookies.get_dict(),
                    "actions": self.actions,
                    "xsid_script": self.xsid_script,
                    "baggage": self.baggage,
                    "sentry_trace": self.sentry_trace,
                    "conversationId": conversation_id,
                    "parentResponseId": parent_response,
                    "privateKey": self.keys["privateKey"]
                }
            }
        }
