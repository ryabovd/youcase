import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from bs4 import BeautifulSoup
import requests
import json
import time
import re
import hashlib
import os
import difflib
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('case_parser.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class CaseChangeTracker:
    """Класс для отслеживания изменений в делах"""
    
    def __init__(self, state_file: str = 'case_state.json'):
        self.state_file = state_file
        self.previous_state = self.load_previous_state()
        self.current_state = {}
        self.changes = []
        self.detailed_changes = []
    
    def load_previous_state(self) -> Dict:
        """Загружает предыдущее состояние из файла"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Не удалось загрузить предыдущее состояние: {e}")
        return {}
    
    def save_current_state(self):
        """Сохраняет текущее состояние в файл"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_state, f, ensure_ascii=False, indent=2)
            logger.info(f"Текущее состояние сохранено в {self.state_file}")
        except IOError as e:
            logger.error(f"Ошибка при сохранении состояния: {e}")
    
    def calculate_content_hash(self, content: Any) -> str:
        """Вычисляет хеш содержимого для сравнения"""
        if isinstance(content, str):
            return hashlib.md5(content.encode('utf-8')).hexdigest()
        elif isinstance(content, dict):
            return hashlib.md5(json.dumps(content, sort_keys=True).encode('utf-8')).hexdigest()
        return ""
    
    def extract_text_content(self, html_content: str) -> str:
        """Извлекает чистый текст из HTML для сравнения"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            return ' '.join(chunk for chunk in chunks if chunk)
        except Exception:
            return html_content
    
    def compare_text_content(self, old_text: str, new_text: str) -> List[str]:
        """Сравнивает текстовое содержимое и возвращает различия"""
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile='previous', tofile='current',
            lineterm=''
        )
        
        changes = []
        for line in diff:
            if line.startswith('+') and not line.startswith('+++'):
                changes.append(f"Добавлено: {line[1:].strip()}")
            elif line.startswith('-') and not line.startswith('---'):
                changes.append(f"Удалено: {line[1:].strip()}")
        
        return changes
    
    def track_case_changes(self, case_url: str, case_data: Dict) -> Tuple[List[Dict], List[Dict]]:
        """Отслеживает изменения в деле"""
        changes = []
        detailed_changes = []
        case_key = case_url
        case_number = case_data.get('case_number', 'N/A')
        
        # Сохраняем текущее состояние ВМЕСТЕ с данными дела для следующего сравнения
        self.current_state[case_key] = {
            'last_check': datetime.now().isoformat(),
            'case_number': case_number,
            'content_hash': self.calculate_content_hash(case_data),
            'tabs_hashes': {},
            'tabs_content': {},
            'case_data': case_data  # Сохраняем ВСЕ данные дела для следующего сравнения
        }
        
        # Вычисляем хеши и сохраняем содержимое для каждой вкладки
        for tab_num, tab_data in case_data.get('tabs', {}).items():
            tab_content = tab_data.get('raw_content', '')
            tab_hash = self.calculate_content_hash(tab_content)
            self.current_state[case_key]['tabs_hashes'][tab_num] = tab_hash
            self.current_state[case_key]['tabs_content'][tab_num] = tab_content
        
        # Проверяем изменения по сравнению с предыдущим состоянием
        if case_key not in self.previous_state:
            change = {
                'type': 'new_case',
                'case_url': case_url,
                'case_number': case_number,
                'timestamp': datetime.now().isoformat(),
                'message': 'Обнаружено новое дело',
                'details': ['Дело добавлено в мониторинг']
            }
            changes.append(change)
            detailed_changes.append(change)
            return changes, detailed_changes
        
        prev_state = self.previous_state[case_key]
        
        # ПЕРВОЕ: Проверяем изменение номера дела
        prev_case_number = prev_state.get('case_number')
        if prev_case_number and case_number != prev_case_number:
            change = {
                'type': 'case_number_changed',
                'case_url': case_url,
                'previous_case_number': prev_case_number,
                'current_case_number': case_number,
                'timestamp': datetime.now().isoformat(),
                'message': 'Изменен номер дела',
                'details': [f'Номер дела изменен с "{prev_case_number}" на "{case_number}"']
            }
            changes.append(change)
            detailed_changes.append(change)
        
        # ВТОРОЕ: Проверяем изменения в основных полях дела
        field_changes = self.check_field_changes(case_url, case_number, case_data, prev_state)
        changes.extend(field_changes)
        detailed_changes.extend(field_changes)
        
        # ТРЕТЬЕ: Проверяем изменения в основном содержимом
        if prev_state.get('content_hash') != self.current_state[case_key]['content_hash']:
            change = {
                'type': 'content_changed',
                'case_url': case_url,
                'case_number': case_number,
                'timestamp': datetime.now().isoformat(),
                'message': 'Изменено содержимое дела',
                'details': ['Общие изменения в структуре дела']
            }
            changes.append(change)
            detailed_changes.append(change)
        
        # ЧЕТВЕРТОЕ: Проверяем изменения в отдельных вкладках
        prev_tabs = prev_state.get('tabs_hashes', {})
        prev_tabs_content = prev_state.get('tabs_content', {})
        curr_tabs = self.current_state[case_key]['tabs_hashes']
        curr_tabs_content = self.current_state[case_key]['tabs_content']
        
        # Проверяем новые вкладки
        new_tabs = set(curr_tabs.keys()) - set(prev_tabs.keys())
        for tab_num in new_tabs:
            change = {
                'type': 'new_tab',
                'case_url': case_url,
                'case_number': case_number,
                'tab_number': tab_num,
                'timestamp': datetime.now().isoformat(),
                'message': f'Добавлена новая вкладка {tab_num}',
                'details': [f'Вкладка {tab_num}: добавлено новое содержимое']
            }
            changes.append(change)
            detailed_changes.append(change)
        
        # Проверяем удаленные вкладки
        removed_tabs = set(prev_tabs.keys()) - set(curr_tabs.keys())
        for tab_num in removed_tabs:
            change = {
                'type': 'removed_tab',
                'case_url': case_url,
                'case_number': case_number,
                'tab_number': tab_num,
                'timestamp': datetime.now().isoformat(),
                'message': f'Удалена вкладка {tab_num}',
                'details': [f'Вкладка {tab_num}: полностью удалена']
            }
            changes.append(change)
            detailed_changes.append(change)
        
        # Проверяем измененные вкладки
        for tab_num in set(prev_tabs.keys()) & set(curr_tabs.keys()):
            if prev_tabs[tab_num] != curr_tabs[tab_num]:
                old_content = prev_tabs_content.get(tab_num, '')
                new_content = curr_tabs_content.get(tab_num, '')
                
                old_text = self.extract_text_content(old_content)
                new_text = self.extract_text_content(new_content)
                
                text_changes = self.compare_text_content(old_text, new_text)
                
                change = {
                    'type': 'tab_changed',
                    'case_url': case_url,
                    'case_number': case_number,
                    'tab_number': tab_num,
                    'timestamp': datetime.now().isoformat(),
                    'message': f'Изменено содержимое вкладки {tab_num}',
                    'details': text_changes if text_changes else ['Содержимое изменено (детали не определены)']
                }
                changes.append(change)
                detailed_changes.append(change)
        
        return changes, detailed_changes
    
    def check_field_changes(self, case_url: str, case_number: str, current_data: Dict, 
                          previous_state: Dict) -> List[Dict]:
        """Проверяет изменения в основных полях дела"""
        field_changes = []
        
        try:
            # Получаем предыдущие данные дела
            prev_data = previous_state.get('case_data', {})
            
            fields_to_check = [
                'sub_category', 'instance', 'material_number', 
                'judge', 'date_of_receipt', 'result_of_consideration'
            ]
            
            for field in fields_to_check:
                current_value = current_data.get(field)
                previous_value = prev_data.get(field)
                
                # Проверяем, изменилось ли значение
                if current_value != previous_value:
                    change_message = self.get_field_change_message(field, previous_value, current_value)
                    
                    change = {
                        'type': 'field_changed',
                        'case_url': case_url,
                        'case_number': case_number,
                        'field': field,
                        'previous_value': previous_value,
                        'current_value': current_value,
                        'timestamp': datetime.now().isoformat(),
                        'message': f'Изменено поле {self.get_field_name(field)}',
                        'details': [change_message]
                    }
                    field_changes.append(change)
                    
        except Exception as e:
            logger.error(f"Ошибка при проверке изменений полей: {e}")
        
        return field_changes
    
    def get_field_change_message(self, field: str, previous_value: Any, current_value: Any) -> str:
        """Формирует сообщение об изменении поля"""
        field_name = self.get_field_name(field)
        
        if previous_value is None and current_value is not None:
            return f"Поле '{field_name}': добавлено значение '{current_value}'"
        elif current_value is None and previous_value is not None:
            return f"Поле '{field_name}': удалено значение '{previous_value}'"
        elif previous_value is not None and current_value is not None:
            return f"Поле '{field_name}': изменено с '{previous_value}' на '{current_value}'"
        return f"Поле '{field_name}': неопределенное изменение"
    
    def get_field_name(self, field: str) -> str:
        """Возвращает читаемое название поля"""
        field_names = {
            'sub_category': 'Категория дела',
            'instance': 'Инстанция',
            'material_number': 'Материальный номер',
            'case_number': 'Номер дела',
            'judge': 'Судья',
            'date_of_receipt': 'Дата поступления',
            'result_of_consideration': 'Результат рассмотрения'
        }
        return field_names.get(field, field)
    
    def save_changes_report(self, changes: List[Dict], detailed_changes: List[Dict]):
        """Сохраняет отчет об изменениях"""
        if not changes:
            logger.info("Изменений не обнаружено")
            return
        
        # Сохраняем краткий отчет
        report_file = f'changes_summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'total_changes': len(changes),
                    'changes': changes
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"Краткий отчет сохранен в {report_file}")
            
        except IOError as e:
            logger.error(f"Ошибка при сохранении отчета: {e}")
        
        # Сохраняем детальный отчет
        detailed_file = f'changes_detailed_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        try:
            with open(detailed_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'total_changes': len(detailed_changes),
                    'detailed_changes': detailed_changes
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"Детальный отчет сохранен в {detailed_file}")
            
        except IOError as e:
            logger.error(f"Ошибка при сохранении детального отчета: {e}")
        
        # Выводим сводку в консоль
        self.print_changes_summary(changes, detailed_changes)
    
    def print_changes_summary(self, changes: List[Dict], detailed_changes: List[Dict]):
        """Выводит сводку изменений в консоль"""
        print("\n" + "="*80)
        print("ДЕТАЛЬНАЯ СВОДКА ИЗМЕНЕНИЙ В ДЕЛАХ")
        print("="*80)
        
        # Группируем изменения по делам
        changes_by_case = {}
        for change in detailed_changes:
            case_key = change.get('case_number', change.get('case_url', 'unknown'))
            if case_key not in changes_by_case:
                changes_by_case[case_key] = []
            changes_by_case[case_key].append(change)
        
        # Выводим изменения для каждого дела
        for case_key, case_changes in changes_by_case.items():
            print(f"\n🔍 ДЕЛО: {case_key}")
            print("-" * 60)
            
            for change in case_changes:
                change_type = change['type']
                print(f"   📋 {self.get_change_type_name(change_type)}:")
                
                # Выводим детали изменений
                for detail in change.get('details', []):
                    print(f"      • {detail}")
                
                # Специальная обработка для изменения номера дела
                if change_type == 'case_number_changed':
                    print(f"      Предыдущий номер: {change.get('previous_case_number')}")
                    print(f"      Текущий номер: {change.get('current_case_number')}")
                
                # Для изменений полей показываем значения
                elif change_type == 'field_changed':
                    print(f"      Поле: {self.get_field_name(change.get('field'))}")
                    print(f"      Было: {change.get('previous_value', 'N/A')}")
                    print(f"      Стало: {change.get('current_value', 'N/A')}")
                
                # Для изменений вкладок показываем номер вкладки
                elif change_type in ['tab_changed', 'new_tab', 'removed_tab']:
                    print(f"      Вкладка: {change.get('tab_number')}")
                
                print()
        
        # Общая статистика
        print("="*80)
        print("ОБЩАЯ СТАТИСТИКА:")
        
        change_types = {}
        for change in changes:
            change_type = change['type']
            change_types[change_type] = change_types.get(change_type, 0) + 1
        
        for change_type, count in change_types.items():
            print(f"   {self.get_change_type_name(change_type)}: {count}")
        
        print(f"   Всего изменений: {len(detailed_changes)}")
        print(f"   Затронуто дел: {len(changes_by_case)}")
        print("="*80)
    
    def get_change_type_name(self, change_type: str) -> str:
        """Возвращает читаемое название типа изменения"""
        names = {
            'new_case': 'НОВОЕ ДЕЛО',
            'content_changed': 'ИЗМЕНЕНИЕ СОДЕРЖИМОГО',
            'new_tab': 'НОВАЯ ВКЛАДКА',
            'removed_tab': 'УДАЛЕНА ВКЛАДКА',
            'tab_changed': 'ИЗМЕНЕНИЕ ВКЛАДКИ',
            'field_changed': 'ИЗМЕНЕНИЕ ПОЛЯ',
            'case_number_changed': 'ИЗМЕНЕНИЕ НОМЕРА ДЕЛА'
        }
        return names.get(change_type, change_type)

# Остальные функции без изменений
def get_session() -> requests.Session:
    return requests.Session()

def get_content(url: str, max_retries: int = 3) -> Optional[BeautifulSoup]:
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
                
        time.sleep(2 ** attempt)
        
    return None

def parse_case_title(content: BeautifulSoup) -> Dict:
    try:
        title_div = content.find('div', class_='title')
        if not title_div:
            return {'sub_category': None, 'instance': None}
            
        category_text = title_div.get_text().strip()
        if '-' in category_text:
            parts = category_text.split('-', 1)
            sub_category = parts[0].strip()
            instance = parts[1].strip() if len(parts) > 1 else None
            return {'sub_category': sub_category, 'instance': instance}
        return {'sub_category': category_text, 'instance': None}
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге заголовка: {e}")
        return {'sub_category': None, 'instance': None}

def parse_case_number(content: BeautifulSoup) -> Dict:
    try:
        case_number_div = content.find('div', class_='casenumber')
        if not case_number_div:
            return {'case_number': None, 'material_number': None}
            
        text = case_number_div.get_text().strip()
        n_pos = text.find('№')
        tilda_pos = text.find('~')
        
        if n_pos != -1 and tilda_pos != -1 and tilda_pos > n_pos:
            case_number = text[n_pos+1:tilda_pos].strip()
            material_number = text[tilda_pos+1:].strip()
            return {'case_number': case_number, 'material_number': material_number}
        
        if n_pos != -1:
            case_number = text[n_pos+1:].strip()
            return {'case_number': case_number, 'material_number': None}
            
        return {'case_number': None, 'material_number': None}
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге номера дела: {e}")
        return {'case_number': None, 'material_number': None}

def parse_tab1_case(tab_content: BeautifulSoup, base_url: str) -> Dict:
    data = {
        'uid': None, 'uid_link': None, 'date_of_receipt': None, 'category_of_case': None,
        'judge': None, 'date_of_consideration': None, 'result_of_consideration': None,
        'indication_of_consideration': None, 'court_composition': None
    }
    
    try:
        uid_elem = tab_content.find('u')
        if uid_elem:
            data['uid'] = uid_elem.get_text().strip()
        
        link_elem = tab_content.find('a')
        if link_elem and link_elem.get('href'):
            relative_link = link_elem.get('href')
            data['uid_link'] = base_url + relative_link if relative_link.startswith('/') else relative_link
        
        date_elem = tab_content.find('b', string=re.compile(r'Дата поступления', re.IGNORECASE))
        if date_elem:
            next_td = date_elem.find_next('td')
            if next_td:
                data['date_of_receipt'] = next_td.get_text().strip()
        
        judge_elem = tab_content.find('b', string=re.compile(r'Судья', re.IGNORECASE))
        if judge_elem:
            next_td = judge_elem.find_next('td')
            if next_td:
                data['judge'] = next_td.get_text().strip()
        
        result_elem = tab_content.find('b', string=re.compile(r'Результат', re.IGNORECASE))
        if result_elem:
            next_td = result_elem.find_next('td')
            if next_td:
                data['result_of_consideration'] = next_td.get_text().strip()
                
    except Exception as e:
        logger.error(f"Ошибка при парсинге первой вкладки: {e}")
        
    return data

def parse_tab_content(tab_content: BeautifulSoup, base_url: str, tab_number: int) -> Dict:
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
    tabs = {}
    
    try:
        tab_list = content.find('ul')
        if not tab_list:
            return tabs
            
        tab_items = tab_list.find_all('li')
        logger.info(f"Найдено вкладок: {len(tab_items)}")
        
        for i, _ in enumerate(tab_items, 1):
            tab_id = f'cont{i}'
            tab_content = content.find('div', id=tab_id)
            
            if tab_content:
                tabs[str(i)] = {
                    'raw_content': str(tab_content),
                    'parsed_data': parse_tab_content(tab_content, base_url, i),
                    'parsing_timestamp': datetime.now().isoformat()
                }
                
    except Exception as e:
        logger.error(f"Ошибка при парсинге вкладки: {e}")
        
    return tabs

def parse_case_data(content: BeautifulSoup, base_url: str) -> Dict:
    case_data = {
        'sub_category': None, 'instance': None, 'case_number': None, 'material_number': None,
        'tabs': {}, 'parsing_timestamp': datetime.now().isoformat(), 'parsing_success': False
    }
    
    try:
        title_data = parse_case_title(content)
        case_data.update(title_data)
        
        number_data = parse_case_number(content)
        case_data.update(number_data)
        
        case_data['tabs'] = parse_all_tabs(content, base_url)
        
        # Извлекаем дополнительные поля из первой вкладки
        if '1' in case_data['tabs']:
            tab1_data = case_data['tabs']['1']['parsed_data']
            case_data.update({
                'judge': tab1_data.get('judge'),
                'date_of_receipt': tab1_data.get('date_of_receipt'),
                'result_of_consideration': tab1_data.get('result_of_consideration')
            })
        
        case_data['parsing_success'] = True
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге данных: {e}")
        case_data['error'] = str(e)
        
    return case_data

def build_base_url(url: str) -> str:
    try:
        if '://' in url:
            protocol_end = url.find('://') + 3
            domain_end = url.find('/', protocol_end)
            return url[:domain_end] if domain_end != -1 else url
        return url
    except Exception as e:
        logger.error(f"Ошибка при построении базового URL: {e}")
        return ''

def load_cases() -> Dict:
    try:
        with open('case_common.json', 'r', encoding='utf-8') as file:
            cases = json.load(file)
        logger.info(f"Загружено {len(cases.get('civil_cases', []))} дел")
        return cases
    except FileNotFoundError:
        logger.error("Файл case_common.json не найден")
        return {'civil_cases': []}
    except Exception as e:
        logger.error(f"Ошибка при загрузке дел: {e}")
        return {'civil_cases': []}

def get_case_links(cases: Dict) -> List[str]:
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
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f'parsed_cases_{timestamp}.json'
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                'parsing_timestamp': datetime.now().isoformat(),
                'total_cases': len(results),
                'successful_cases': len([r for r in results if r.get('success')]),
                'cases': results
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"Результаты сохранены в {results_file}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении результатов: {e}")

def main():
    try:
        logger.info("Запуск парсера судебных дел с детальным отслеживанием изменений")
        
        tracker = CaseChangeTracker()
        cases = load_cases()
        case_links = get_case_links(cases)
        
        if not case_links:
            logger.warning("Нет ссылок на дела для обработки")
            return
        
        results = []
        all_changes = []
        all_detailed_changes = []
        successful = 0
        
        for i, link in enumerate(case_links, 1):
            logger.info(f"Обработка дела {i}/{len(case_links)}: {link}")
            
            content = get_content(link)
            if not content:
                results.append({'url': link, 'success': False, 'error': 'Не удалось получить контент'})
                continue
                
            base_url = build_base_url(link)
            case_data = parse_case_data(content, base_url)
            
            changes, detailed_changes = tracker.track_case_changes(link, case_data)
            all_changes.extend(changes)
            all_detailed_changes.extend(detailed_changes)
            
            result_item = {
                'url': link, 'data': case_data, 'success': case_data['parsing_success'],
                'changes': changes, 'detailed_changes': detailed_changes
            }
            
            results.append(result_item)
            if case_data['parsing_success']:
                successful += 1
            
            if i < len(case_links):
                time.sleep(1)
        
        tracker.save_current_state()
        tracker.save_changes_report(all_changes, all_detailed_changes)
        save_results(results)
        
        logger.info(f"Обработка завершена. Успешно: {successful}/{len(case_links)} дел")
        
    except KeyboardInterrupt:
        logger.info("Приложение остановлено пользователем")
    except Exception as e:
        logger.critical(f"Критическая ошибка в main: {e}")

if __name__ == "__main__":
    main()