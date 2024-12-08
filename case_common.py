from urllib.request import urlopen
from urllib.error import HTTPError
from bs4 import BeautifulSoup
import requests
#import datetime
#import json


url = 'https://abakansky--hak.sudrf.ru/modules.php?name=sud_delo&srv_num=2&name_op=case&case_id=69831807&case_uid=72d314dc-bc07-4c83-81a6-2fbd94c53c45&delo_id=1540005'
# url = 'https://abakansky--hak.sudrf.ru/modules.php?name=sud_delo&srv_num=2&name_op=case&case_id=75838512&case_uid=d9fcfb59-8b80-493a-af85-e354b361a998&delo_id=1540005'
# url = 'https://abakansky--hak.sudrf.ru/modules.php?name=sud_delo&srv_num=2&name_op=case&case_id=75838512&case_uid=d9fcfb59-8b80-493a-af85-e354b361a998&delo_id=1540005'
"""
https://abakansky--hak.sudrf.ru/modules.php?name=sud_delo&srv_num=2&name_op=case&case_id=75838512&case_uid=d9fcfb59-8b80-493a-af85-e354b361a998&delo_id=1540005#
https://abakansky--hak.sudrf.ru/modules.php?name=sud_delo&srv_num=2&name_op=case&case_id=75838512&case_uid=d9fcfb59-8b80-493a-af85-e354b361a998&delo_id=1540005#
"""
# url = 'https://abakansky--hak.sudrf.ru/modules.php?name=sud_delo&srv_num=2&name_op=case&case_id=69831807&case_uid=72d314dc-bc07-4c83-81a6-2fbd94c53c45&delo_id=1540005'


def getContent(url):
    session = get_session()
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'accept-language': 'ru-RU,ru;q=0.9,en-RU;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'max-age=0',
        'connection': 'keep-alive',
        'cookie': 'assistFontSize=1',
        'host': 'abakansky--hak.sudrf.ru',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    }

    try:
        data = session.get(url, headers=headers)
        text = data.text
    except HTTPError as e:
        return None
    try:
        bs = BeautifulSoup(text, 'html.parser')
        content = bs.find(id = 'content')
    except AttributeError as e:
        return None
    return content


def get_session():
    s = requests.Session()
    return s


def get_data_from_content(content, link_start):
    case_info = {}
    sub_category, instance = get_case_title(content)
    print('sub_category, instance', sub_category, instance)
    case_number, material_number = get_case_number(content)
    print('case_number, material_number', case_number, material_number)
    tabs_case = get_tabs_case(content, link_start)
    return case_info


def get_case_title(content):
    category = content.find('div', class_ = 'title').get_text()
    sub_category, instance = category.split('-')
    sub_category, instance = sub_category.strip(), instance.strip()
    return sub_category, instance


def get_case_number(content):
    casenumber = content.find('div', class_ = 'casenumber').get_text().strip()
    print(casenumber)
    sym_N_position = casenumber.find('№')
    sym_Tilda_position = casenumber.find('~')
    case_number = casenumber[sym_N_position+1:sym_Tilda_position].strip()
    material_number = casenumber[sym_Tilda_position+1:].strip()
    print(case_number)
    print(material_number)
    return case_number, material_number


def get_tabs_case(content, link_start):
    # print(type(content))
    quantity_tabs = len(content.ul.find_all('li'))
    print('TABS =', quantity_tabs)
    tabs = {}
    for tab in range(1, quantity_tabs+1):
        # print('TAB' + str(tab))
        tab_content = content.find('div', id = 'cont' + str(tab))
        tabs[str(tab)] = tab_content
    for tab in tabs:
        print(tabs[tab], '\n')

    # tab1_case = content.find('div', id = 'cont1')
    # print(tab1_case, '\n')
    # parse_tab1_case(tab1_case, link_start)
    # tab2_case_flow = content.find('div', id = 'cont2')
    # print(tab2_case_flow, '\n')
    # tab3_litigants = content.find('div', id = 'cont3')
    # print(tab3_litigants, '\n')


def parse_tab1_case(tab_1_case, link_start):
    uid = tab_1_case.find('u').get_text()
    print('uid', uid)
    tab_uid_link = tab_1_case.find('a').get('href')
    uid_link = build_uid_link(tab_uid_link, link_start)
    print('uid_link', uid_link)
    date_of_receipt = tab_1_case.find('b', string='Дата поступления').find_next('td').get_text()
    print(date_of_receipt)
    сategory_of_case = 0
    judge = 0	
    date_of_consideration = 0	
    result_of_consideration	= 0
    indication_of_consideration_of_the_case = 0
    court_composition = 0
    pass


def build_link_start(url):
    slash_position = url.find('/modules')
    link_start = url[:slash_position]
    # print('\n', link_start, '\n')
    return link_start


def build_uid_link(tab_uid_link, link_start):
    return link_start + tab_uid_link


def main():
    content = getContent(url)
    
    if content == None:
            print('Content could not be found')
    else:
        #print(content, '\n')
        link_start = build_link_start(url)
        get_data_from_content(content, link_start)


if __name__ == __name__:
    main()