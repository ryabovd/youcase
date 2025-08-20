import logging
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from bs4 import BeautifulSoup
import requests
import json
import time
import re

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('case_parser.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def get_session() -> requests.Session:
    """Создает и возвращает сессию requests"""
    return requests.Session()

def get_content(url: str, max_retries: int = 3) -> Optional[BeautifulSoup]:
    """
    Получает контент страницы с обработкой ошибок и повторными попытками
    """
    session = get_session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
    }
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Попытка {attempt + 1} для {url}")
            response = session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            bs = BeautifulSoup(response.text, 'html.parser')
            content = bs.find(id='content')
            
            if not content:
                logger.warning(f"Контент не найден на странице: {url}")
                return None
                
            return content
            
        except HTTPError as e:
            logger.error(f"HTTP ошибка {e.status_code} для {url}: {e}")
            if attempt == max_retries - 1:
                return None
                
        except (requests.exceptions.RequestException, AttributeError) as e:
            logger.error(f"Ошибка при получении {url}: {e}")
            if attempt == max_retries - 1:
                return None
                
        time.sleep(2 ** attempt)  # Экспоненциальная задержка
        
    return None

def parse_case_title(content: BeautifulSoup) -> Dict:
    """Парсит заголовок дела"""
    try:
        title_div = content.find('div', class_='title')
        if not title_div:
            logger.warning("Заголовок дела не найден")
            return {'sub_category': None, 'instance': None}
            
        category_text = title_div.get_text().strip()
        if '-' in category_text:
            parts = category_text.split('-', 1)
            sub_category = parts[0].strip()
            instance = parts[1].strip() if len(parts) > 1 else None
            return {
                'sub_category': sub_category,
                'instance': instance
            }
        return {'sub_category': category_text, 'instance': None}
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге заголовка: {e}")
        return {'sub_category': None, 'instance': None}

def parse_case_number(content: BeautifulSoup) -> Dict:
    """Парсит номер дела"""
    try:
        case_number_div = content.find('div', class_='casenumber')
        if not case_number_div:
            logger.warning("Номер дела не найден")
            return {'case_number': None, 'material_number': None}
            
        text = case_number_div.get_text().strip()
        n_pos = text.find('№')
        tilda_pos = text.find('~')
        
        if n_pos != -1 and tilda_pos != -1 and tilda_pos > n_pos:
            case_number = text[n_pos+1:tilda_pos].strip()
            material_number = text[tilda_pos+1:].strip()
            return {
                'case_number': case_number,
                'material_number': material_number
            }
        
        # Альтернативный парсинг если нет тильды
        if n_pos != -1:
            case_number = text[n_pos+1:].strip()
            return {
                'case_number': case_number,
                'material_number': None
            }
            
        return {'case_number': None, 'material_number': None}
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге номера дела: {e}")
        return {'case_number': None, 'material_number': None}

def parse_tab1_case(tab_content: BeautifulSoup, base_url: str) -> Dict:
    """Парсит первую вкладку с основной информацией"""
    data = {
        'uid': None,
        'uid_link': None,
        'date_of_receipt': None,
        'category_of_case': None,
        'judge': None,
        'date_of_consideration': None,
        'result_of_consideration': None,
        'indication_of_consideration': None,
        'court_composition': None
    }
    
    try:
        # UID
        uid_elem = tab_content.find('u')
        if uid_elem:
            data['uid'] = uid_elem.get_text().strip()
        
        # Ссылка UID
        link_elem = tab_content.find('a')
        if link_elem and link_elem.get('href'):
            relative_link = link_elem.get('href')
            if relative_link.startswith('/'):
                data['uid_link'] = base_url + relative_link
            else:
                data['uid_link'] = relative_link
        
        # Дата поступления
        date_elem = tab_content.find('b', string='Дата поступления')
        if not date_elem:
            # Попробуем найти по тексту
            date_elem = tab_content.find('b', string=re.compile(r'Дата поступления', re.IGNORECASE))
        
        if date_elem:
            next_td = date_elem.find_next('td')
            if next_td:
                data['date_of_receipt'] = next_td.get_text().strip()
        
        # Судья
        judge_elem = tab_content.find('b', string=re.compile(r'Судья', re.IGNORECASE))
        if judge_elem:
            next_td = judge_elem.find_next('td')
            if next_td:
                data['judge'] = next_td.get_text().strip()
        
        # Результат рассмотрения
        result_elem = tab_content.find('b', string=re.compile(r'Результат', re.IGNORECASE))
        if result_elem:
            next_td = result_elem.find_next('td')
            if next_td:
                data['result_of_consideration'] = next_td.get_text().strip()
                
    except Exception as e:
        logger.error(f"Ошибка при парсинге первой вкладки: {e}")
        
    return data

def parse_tab_content(tab_content: BeautifulSoup, base_url: str, tab_number: int) -> Dict:
    """Парсит содержимое конкретной вкладки"""
    try:
        if tab_number == 1:
            return parse_tab1_case(tab_content, base_url)
        elif tab_number == 2:
            return {'tab_type': 'case_flow', 'content_present': bool(tab_content)}
        elif tab_number == 3:
            return {'tab_type': 'litigants', 'content_present': bool(tab_content)}
        else:
            return {'tab_type': f'unknown_tab_{tab_number}', 'content_present': bool(tab_content)}
            
    except Exception as e:
        logger.error(f"Ошибка при парсинге вкладки {tab_number}: {e}")
        return {'error': str(e)}

def parse_all_tabs(content: BeautifulSoup, base_url: str) -> Dict:
    """Парсит все вкладки дела"""
    tabs = {}
    
    try:
        tab_list = content.find('ul')
        if not tab_list:
            logger.warning("Список вкладок не найден")
            return tabs
            
        tab_items = tab_list.find_all('li')
        logger.info(f"Найдено вкладок: {len(tab_items)}")
        
        for i, _ in enumerate(tab_items, 1):
            tab_id = f'cont{i}'
            tab_content = content.find('div', id=tab_id)
            
            if tab_content:
                tabs[str(i)] = {
                    'raw_content': str(tab_content),
                    'parsed_data': parse_tab_content(tab_content, base_url, i)
                }
            else:
                logger.warning(f"Вкладка {tab_id} не найдена")
                
    except Exception as e:
        logger.error(f"Ошибка при парсинге вкладок: {e}")
        
    return tabs

def parse_case_data(content: BeautifulSoup, base_url: str) -> Dict:
    """Парсит все данные по делу"""
    case_data = {
        'sub_category': None,
        'instance': None,
        'case_number': None,
        'material_number': None,
        'tabs': {},
        'parsing_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'parsing_success': False
    }
    
    try:
        # Основная информация
        title_data = parse_case_title(content)
        case_data.update(title_data)
        
        number_data = parse_case_number(content)
        case_data.update(number_data)
        
        # Вкладки
        case_data['tabs'] = parse_all_tabs(content, base_url)
        case_data['parsing_success'] = True
        
        logger.info(f"Успешно распарсено дело: {case_data.get('case_number')}")
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге данных: {e}")
        case_data['error'] = str(e)
        
    return case_data

def build_base_url(url: str) -> str:
    """Извлекает базовый URL"""
    try:
        if '://' in url:
            protocol_end = url.find('://') + 3
            domain_end = url.find('/', protocol_end)
            if domain_end != -1:
                return url[:domain_end]
            return url
        return url
    except Exception as e:
        logger.error(f"Ошибка при построении базового URL: {e}")
        return ''

def load_cases() -> Dict:
    """Загружает дела из JSON файла"""
    try:
        with open('case_common.json', 'r', encoding='utf-8') as file:
            cases = json.load(file)
        logger.info(f"Загружено {len(cases.get('civil_cases', []))} дел")
        return cases
    except FileNotFoundError:
        logger.error("Файл case_common.json не найден")
        return {'civil_cases': []}
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return {'civil_cases': []}
    except Exception as e:
        logger.error(f"Ошибка при загрузке дел: {e}")
        return {'civil_cases': []}

def get_case_links(cases: Dict) -> List[str]:
    """Извлекает ссылки на дела"""
    case_links = []
    try:
        for case in cases.get('civil_cases', []):
            link = case.get('case_link')
            if link:
                case_links.append(link)
        logger.info(f"Извлечено {len(case_links)} ссылок на дела")
    except Exception as e:
        logger.error(f"Ошибка при извлечении ссылок: {e}")
    
    return case_links

def save_results(results: List[Dict]):
    """Сохраняет результаты в файл"""
    try:
        with open('parsed_cases.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"Результаты сохранены в parsed_cases.json ({len(results)} дел)")
    except Exception as e:
        logger.error(f"Ошибка при сохранении результатов: {e}")

def main():
    """Основная функция приложения"""
    try:
        logger.info("Запуск парсера судебных дел")
        
        cases = load_cases()
        case_links = get_case_links(cases)
        
        if not case_links:
            logger.warning("Нет ссылок на дела для обработки")
            return
        
        results = []
        successful = 0
        
        for i, link in enumerate(case_links, 1):
            logger.info(f"Обработка дела {i}/{len(case_links)}: {link}")
            
            content = get_content(link)
            if not content:
                logger.warning(f"Не удалось получить контент для {link}")
                results.append({
                    'url': link,
                    'success': False,
                    'error': 'Не удалось получить контент'
                })
                continue
                
            base_url = build_base_url(link)
            case_data = parse_case_data(content, base_url)
            
            result_item = {
                'url': link,
                'data': case_data,
                'success': case_data['parsing_success']
            }
            
            results.append(result_item)
            if case_data['parsing_success']:
                successful += 1
            
            # Пауза между запросами
            if i < len(case_links):
                time.sleep(1)
        
        # Сохранение результатов
        save_results(results)
        logger.info(f"Обработка завершена. Успешно: {successful}/{len(case_links)} дел")
        
    except KeyboardInterrupt:
        logger.info("Приложение остановлено пользователем")
    except Exception as e:
        logger.critical(f"Критическая ошибка в main: {e}")

if __name__ == "__main__":
    main()