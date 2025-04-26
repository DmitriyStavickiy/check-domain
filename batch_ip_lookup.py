#!/usr/bin/env python3
# batch_ip_lookup.py
"""
Пакетная обработка IP-lookup:
  1. Читает домены из .txt или .json (можно с полными URL)
  2. Очищает их до чистого домена
  3. Выполняет параллельные запросы через ThreadPoolExecutor
  4. Сохраняет результат в CSV в папке results
  5. Отправляет уведомление и файл в Telegram (по настройкам)
  6. Логирует старт, прогресс и ошибки
"""
import argparse
import json
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import os
import threading

# ---------------------------------------------------
# Настройки для Telegram: рекомендую задавать через переменные окружения
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
DEFAULT_WORKERS = 3
RESULTS_DIR = Path('results')
LOG_FORMAT = '%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s'
LOG_LEVEL = logging.DEBUG
CHUNK_SIZE = 100
# ---------------------------------------------------


class DomainReader:
    """Читает и очищает список доменов из .txt или .json файлов"""

    @staticmethod
    def read(path: Path) -> List[str]:
        text = path.read_text(encoding='utf-8')
        if path.suffix.lower() == '.txt':
            items = [line.strip() for line in text.splitlines() if line.strip()]
        elif path.suffix.lower() == '.json':
            data = json.loads(text)
            if isinstance(data, list):
                items = [str(item) for item in data]
            elif isinstance(data, dict):
                # ищем первый список в значениях
                for v in data.values():
                    if isinstance(v, list):
                        items = [str(item) for item in v]
                        break
                else:
                    raise ValueError('JSON не содержит список доменов')
            else:
                raise ValueError('JSON должен быть списком или словарём со списком')
        else:
            raise ValueError('Поддерживаются только файлы .txt или .json')

        return [DomainReader._extract_domain(raw) for raw in items]

    @staticmethod
    def _extract_domain(raw: str) -> str:
        parsed = urlparse(raw if '://' in raw else f'//{raw}', scheme='')
        netloc = parsed.netloc or parsed.path
        return netloc.split(':')[0]


class ApiClient:
    """Клиент для запросов к внешнему API с поддержкой retry"""

    def __init__(self):
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def lookup(self, api, domain: str) -> Optional[Dict[str, str]]:
        thread = threading.current_thread().name
        logging.debug(f"[{thread}] [LOOKUP] Start lookup for {domain}")
        try:
            res = api.reqapi_ia_get_result(domain)
            logging.debug(f"[{thread}] [LOOKUP] Received status={res.get('status')} for {domain}")
        except Exception as e:
            logging.warning(f"[{thread}] [API] Exception for {domain}: {e}")
            return None

        if res.get('status') != 'success':
            logging.debug(f"[{thread}] [LOOKUP] Unsuccessful status for {domain}, skipping")
            logging.info(f"[API] Неуспешный статус для {domain}")
            return None

        logging.debug(f"[{thread}] [LOOKUP] Successful lookup for {domain}")
        return {
            'domain': domain,
            'country': res.get('country'),
            'isp': res.get('isp'),
            'organization': res.get('org'),
            'as': res.get('as')
        }


class TelegramNotifier:
    """Отправка уведомлений и файлов в Telegram"""

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f'https://api.telegram.org/bot{token}'
        self.session = requests.Session()

    def send_message(self, message: str) -> None:
        url = f"{self.base_url}/sendMessage"
        payload = {'chat_id': self.chat_id, 'text': message}
        try:
            self.session.post(url, data=payload, timeout=10)
        except Exception as e:
            logging.error(f'[Telegram] Ошибка отправки сообщения: {e}')

    def send_file(self, file_path: Path, caption: str = '') -> None:
        url = f"{self.base_url}/sendDocument"
        try:
            with file_path.open('rb') as f:
                files = {'document': f}
                data = {'chat_id': self.chat_id, 'caption': caption}
                self.session.post(url, data=data, files=files, timeout=30)
        except Exception as e:
            logging.error(f'[Telegram] Ошибка отправки файла: {e}')


class BatchIpLookup:
    """Оркестрация чтения, поиска, сохранения и уведомления"""

    def __init__(self, input_path: Path, workers: int):
        self.input_path = input_path
        self.workers = workers
        self.api = self._load_api()
        self.session = requests.Session()
        self.notifier = None

    def _load_api(self):
        from src.script.reqapi import reqapi
        return reqapi()

    def _setup_notifier(self):
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            self.notifier = TelegramNotifier(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)

    def run(self):
        logging.info('🚀 Запуск batch_ip_lookup')
        domains = DomainReader.read(self.input_path)
        total = len(domains)
        logging.info(f'📑 Всего доменов: {total}, воркеры: {self.workers}')
        # Prepare results file with header
        RESULTS_DIR.mkdir(exist_ok=True)
        run_id = uuid.uuid4().hex[:8]
        now = datetime.now()
        date_str = now.strftime('%Y%m%d')
        time_str = now.strftime('%H%M%S')
        output_path = RESULTS_DIR / f'results_{run_id}_{date_str}_{time_str}.csv'
        # Write header only
        pd.DataFrame([], columns=['domain','country','isp','organization','as']) \
          .to_csv(output_path, index=False, encoding='utf-8-sig')
        # Process in chunks
        for start in range(0, total, CHUNK_SIZE):
            end = min(start + CHUNK_SIZE, total)
            chunk = domains[start:end]
            logging.info(f'🔄 Обработка доменов {start+1}-{end} из {total}')
            records = []
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = {executor.submit(ApiClient().lookup, self.api, d): d for d in chunk}
                for idx, future in enumerate(as_completed(futures), start=start+1):
                    domain = futures[future]
                    result = future.result()
                    if result:
                        records.append(result)
                        icon = '✅'
                    else:
                        icon = '❌'
                    logging.info(f"{icon} [{idx}/{total}] {domain}")
            # Append chunk results without header
            pd.DataFrame(records, columns=['domain','country','isp','organization','as']) \
              .to_csv(output_path, mode='a', index=False, header=False, encoding='utf-8-sig')
            logging.info(f'✅ Чанк {start+1}-{end} сохранён')
        logging.info(f'🎉 Все чанки обработаны, результаты в {output_path}')
        # Send notifications if any
        if self.notifier:
            msg = f'Batch ip-lookup завершён. Файл: {output_path.name}'
            logging.info('📤 Отправка уведомления в Telegram...')
            self.notifier.send_message(msg)
            logging.info('📤 Уведомление отправлено')
            logging.info('📤 Отправка файла в Telegram...')
            self.notifier.send_file(output_path, caption=msg)
            logging.info('📤 Файл отправлен')


def parse_args():
    parser = argparse.ArgumentParser(
        description='Batch IP-lookup: из TXT/JSON в CSV с параллельной обработкой и уведомлениями')
    parser.add_argument('-i', '--input', required=True, help='Файл с доменами (.txt или .json)')
    parser.add_argument('-w', '--workers', type=int, default=DEFAULT_WORKERS,
                        help=f'Число потоков (по умолчанию {DEFAULT_WORKERS})')
    return parser.parse_args()


if __name__ == '__main__':
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # capture all levels to logger

    # Console handler: only INFO and above, to stderr
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(ch)

    # File handler: DEBUG and above, to log file
    fh = logging.FileHandler('batch_ip_lookup.log', mode='a', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(fh)

    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        logging.error(f'Файл не найден: {input_path}')
        sys.exit(1)

    try:
        app = BatchIpLookup(input_path, args.workers)
        app._setup_notifier()
        app.run()
    except Exception as e:
        logging.exception(f'Ошибка выполнения: {e}')
        sys.exit(1)
