import json
import time
import requests
import threading

# Global rate-limit control
_rate_limit_lock = threading.Lock()
_next_allowed_time = 0.0

class reqapi():
    def __init__(self):
        super(reqapi, self).__init__()

    def _wait_for_rate_limit(self):
        """
        Before sending a request, ensure we are past the global next allowed time.
        """
        global _next_allowed_time
        with _rate_limit_lock:
            now = time.time()
            if now < _next_allowed_time:
                wait = _next_allowed_time - now
                print(f"[DEBUG][RATE_LIMIT] Глобальный лимит, ждем {wait:.2f}s")
        # Sleep outside the lock to allow others to check
        if now < _next_allowed_time:
            time.sleep(wait)

    def _handle_rate_limit(self, headers: dict) -> None:
        """
        Если заголовок X-Rl присутствует, выводим оставшееся число запросов.
        Если X-Rl == 0, ждем X-Ttl секунд перед следующими запросами.
        """
        # Accept header names in any case
        rl = headers.get('X-Rl') or headers.get('X-RL') or headers.get('x-rl')
        ttl = headers.get('X-Ttl') or headers.get('X-TTL') or headers.get('x-ttl')
        try:
            remaining = int(rl) if rl is not None else None
            wait = int(ttl) if ttl is not None else 0
        except ValueError:
            print(f"[DEBUG][RATE_LIMIT] Неверный формат заголовков X-Rl/X-Ttl: {rl}/{ttl}")
            return

        if remaining is not None:
            print(f"[DEBUG][RATE_LIMIT] Осталось запросов: {remaining}, до сброса: {wait}s")
        if remaining == 0 and wait > 0:
            # Set global next allowed time
            global _next_allowed_time
            with _rate_limit_lock:
                _next_allowed_time = time.time() + wait
            print(f"[DEBUG][RATE_LIMIT] Лимит исчерпан, ждем {wait} сек...")
            time.sleep(wait)

    def reqapi_ia_get_result(self, target: str) -> dict:
        """
        Debug + rate-limit для ip-api.com
        """
        self._wait_for_rate_limit()
        url = f"http://ip-api.com/json/{target}?fields=status,message,country,isp,org,as"
        print(f"[DEBUG][IA_GET] URL: {url}")
        try:
            resp = requests.get(url, timeout=10)
            print(f"[DEBUG][IA_GET] HTTP {resp.status_code} — body:\n{resp.text}\n")
            self._handle_rate_limit(resp.headers)
            return resp.json()
        except Exception as e:
            print(f"[DEBUG][IA_GET] Ошибка при запросе {url}: {e}")
            return {}

    def reqapi_ch_post_request(self, target: str) -> str:
        """
        Debug + rate-limit для check-host.net whois
        """
        self._wait_for_rate_limit()
        url = "https://check-host.net/ip-info/whois"
        data = {"host": target}
        print(f"[DEBUG][CH_POST] URL: {url} | data: {data}")
        try:
            resp = requests.post(url, data=data, timeout=10)
            print(f"[DEBUG][CH_POST] HTTP {resp.status_code} — body:\n{resp.text}\n")
            self._handle_rate_limit(resp.headers)
            return resp.text
        except Exception as e:
            print(f"[DEBUG][CH_POST] Ошибка при POST {url}: {e}")
            return ""

    def reqapi_ch_get_request(self, target: str, method: str, max_nodes: int) -> dict:
        """
        Debug + rate-limit для запуска проверки на check-host.net
        """
        self._wait_for_rate_limit()
        url = f"https://check-host.net/check-{method}?host={target}&max_nodes={max_nodes}"
        headers = {"Accept": "application/json"}
        print(f"[DEBUG][CH_GET_REQ] URL: {url} | headers: {headers}")
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            print(f"[DEBUG][CH_GET_REQ] HTTP {resp.status_code} — body:\n{resp.text}\n")
            self._handle_rate_limit(resp.headers)
            return resp.json()
        except Exception as e:
            print(f"[DEBUG][CH_GET_REQ] Ошибка при GET {url}: {e}")
            return {}

    def reqapi_ch_get_result(self, request_id: int) -> dict:
        """
        Debug + rate-limit для получения результата проверки
        """
        self._wait_for_rate_limit()
        url = f"https://check-host.net/check-result/{request_id}"
        print(f"[DEBUG][CH_GET_RES] URL: {url}")
        try:
            resp = requests.get(url, timeout=10)
            print(f"[DEBUG][CH_GET_RES] HTTP {resp.status_code} — body:\n{resp.text}\n")
            self._handle_rate_limit(resp.headers)
            return resp.json()
        except Exception as e:
            print(f"[DEBUG][CH_GET_RES] Ошибка при GET {url}: {e}")
            return {}
