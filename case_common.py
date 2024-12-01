from urllib.request import urlopen
from urllib.error import HTTPError
from bs4 import BeautifulSoup
import requests
#import datetime
#import json
#import csv
#from send_email import send_notification



url = 'https://abakansky--hak.sudrf.ru/modules.php?name=sud_delo&srv_num=2&name_op=case&case_id=75838512&case_uid=d9fcfb59-8b80-493a-af85-e354b361a998&delo_id=1540005'
#url = 'https://abakansky--hak.sudrf.ru/modules.php?name=sud_delo&srv_num=2&name_op=case&case_id=75838512&case_uid=d9fcfb59-8b80-493a-af85-e354b361a998&delo_id=1540005'

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
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        # 'Remote Address': '84.42.111.139:443',
        # 'Referrer Policy': 'strict-origin-when-cross-origin'
    }
    data = session.get(url, headers=headers)
    #print(data.text)
    text = data.text
    #print(type(data))
    #print(BeautifulSoup(text, 'html.parser'))
    #print(data.status_code)
    print('/n', data.status_code)
    if data.status_code == 200:
        print('/n YES 200!!!!!')
    try:
        html = data
    except HTTPError as e:
        return None
    try:
        bs = BeautifulSoup(text, 'html.parser')
        content = bs.find(id = 'content')
        #print(content)
    except AttributeError as e:
        return None
    return content


def get_session():
    s = requests.Session()
    return s


def main():
    content = getContent(url)
    if content == None:
            print('Content could not be found')
    else:
        print(content)
    pass


if __name__ == __name__:
    main()