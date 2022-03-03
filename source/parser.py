from lib2to3.pgen2 import driver
import time
import json
import requests
import re
import asyncio
import aiohttp
import os
from datetime import datetime

import lxml
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service


VACANSIES = {'vacancies': []}
dublicate_count = 0

def get_params():

    """Get params from user"""

    params = {}
    params['keywords'] = input('Введите ключевые слова для поиска: ').capitalize()
    params['city'] = input('Введите город: ').capitalize()

    while True:
        params['currency'] = input('Введите валюту (RUB, USD): ').upper()
        currency_check = re.match(r'(USD|RUB)', params['currency'])
        if currency_check is not None or params['currency'] == '':
            break
        print('[Error] Invalid input')

    while True:
        params['salary_filter'] = input('Введите минимальную желаемую зарплату в рублях: ')
        salary_filter_check = re.match(r'^\d+$', params['salary_filter'])
        if salary_filter_check is not None or params['salary_filter'] == '':
            break
        print('[Error] Invalid input')

    for key in params:
        if params[key] == '':
            params[key] = None
    return params


def set_params(url, **filters):

    """Applying parameters"""

    service = Service(ChromeDriverManager().install())

    options = ChromeOptions()
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_argument(f'user-agent={UserAgent().random}')
    options.add_argument('--headless')

    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(10)

    actions = ActionChains(driver)

    try:
        driver.get(url=url)

        keywords_input = driver.find_element(value='a11y-search-input')
        if filters['keywords']:
            keywords_input.send_keys(filters['keywords'])
        keywords_input.send_keys(Keys.ENTER)

        filter_button = driver.find_element(By.CLASS_NAME, 'bloko-icon-link')
        filter_button.click()

        logo = driver.find_element(By.CLASS_NAME, 'supernova-footer-nav-logo')
        actions.move_to_element(logo).perform()

        clear_buttons = driver.find_elements(By.CLASS_NAME, 'bloko-tag-button')
        for button in clear_buttons:
            button.click()

        if filters['city']:               
            city_input = driver.find_element(By.CSS_SELECTOR, 
                                             'input[data-qa="resumes-search-region-add"]')
            city_input.send_keys(filters['city'])

            time.sleep(2)

        if filters['salary_filter']:
            salary_input = driver.find_element(By.CSS_SELECTOR, 
                                               'input[data-qa="vacancysearch__compensation-input"]')
            salary_input.send_keys(filters['salary_filter'])

            salary_checkbox = driver.find_element(By.XPATH,
                    '//span[contains(text(), "Показывать только вакансии")]')
            salary_checkbox.click()

        el_on_page = driver.find_element(By.CSS_SELECTOR,
                                         'label[data-qa="control-search__items-on-page control-search__items-on-page_20"]')
        vacancy_checkbox = el_on_page.find_element(By.TAG_NAME, 'span')
        actions.move_to_element(logo).perform()
        vacancy_checkbox.click()

        submit_button = driver.find_element(value='submit-bottom')
        submit_button.click()

        time.sleep(2)

        search_url = driver.current_url

        page_quantity = driver.find_elements(By.CSS_SELECTOR, 
                                            'a[data-qa="pager-page"]')
        max_page = page_quantity[-1].find_element(By.TAG_NAME, 'span').text

    except Exception as e:
        print(e)

    finally:
        driver.close()
        driver.quit()
        return [max_page, search_url]


async def parse(session, current_url, currency, **params):
    global dublicate_count

    """Get vacancies"""

    headers = {
        'user-agent': UserAgent().random
    }

    request_repeat_attemp = 3

    while (request_repeat_attemp > 0 or len(titles) == 0):
        try:
            async with session.get(url=current_url, headers=headers) as response:
                resp = await response.text()

                bs = BeautifulSoup(resp, 'lxml')

                titles = bs.find_all(attrs={'data-qa': re.compile('^vacancy-serp_'
                                            '_vacancy vacancy-serp__vacancy_')})

                request_repeat_attemp -= 1
        except OSError as e:
            if e.strerror == 'Превышен таймаут семафора':
                pass

    s = 'vacancy-serp__vacancy-'
    for el in titles:
        link = el.find(attrs={'data-qa': s + 'title'})

        salary = el.find(attrs={'data-qa': s + 'compensation'})
        salary = await salary_format(salary, currency, params['dollar_rate'])

        city = el.find(attrs={'data-qa': s + 'address'})

        placement_date = el.find(attrs={'data-qa': s + 'date'})

        company = el.find(attrs={'data-qa': s + 'employer'})
        if company is None:
            company = el.find(attrs={'class': 'vacancy-serp-item__meta-info-company'})

        remote = el.find(text='Можно работать из дома')

        vacancy = {
            'title': link.text,
            'city': city.text,
            'link': link.get('href'),
            'salary': salary,
            'company name': company.text if company else 'Не указано',
            'company link': (f'https://hh.ru{company.get("href")}'
                             if company.get('href') 
                             else 'Не указано'),
            'remote': remote if remote else 'Работа в офисе',
            'placement date': (placement_date.text 
                               if placement_date 
                               else 'Не указано')
        }
        if vacancy in VACANSIES['vacancies']:
            dublicate_count += 1
            continue
        else:
            VACANSIES['vacancies'].append(vacancy)


async def salary_format(salary, currency, dollar_rate):

    """Convert salary"""

    if not salary:
        return 'Не указана'

    salary = salary.text.replace('\u202f', '')
    numbers = re.findall('\d+', salary)
    for idx, num in enumerate(numbers):
        if currency == 'RUB' and ('EUR' in salary or 'USD' in salary):
            numbers[idx] = f'{int(float(num) * dollar_rate)}'
        elif currency == 'USD' and ('руб' in salary):
            numbers[idx] = f'{int(float(num) / dollar_rate)}'
        else:
            return salary

    if len(numbers) > 1:
        return f'{numbers[0]} - {numbers[1]} {currency}.'
    else:
        return f'{salary[0:2]} {numbers[0]} {currency}.'


def get_dollar_exchange_rate():

    """Get dollars rate"""

    response = requests.get('https://www.google.com/'
                            'search?q=%D0%BA%D1%83%D1%80%D1%81+%D0%B4%D0%BE%D0'
                            '%BB%D0%BB%D0%B0%D1%80%D0%B0&oq=%D0%BA%D1%83%D1%80'
                            '%D1%81+%D0%B4%D0%BE%D0%BB%D0%BB%D0%B0&'
                            'aqs=chrome.0.0i131i433i512j69i57j0i131i433i512l4j'
                            '0i512j0i433i512j0i512j0i131i433i512.4128j1j7'
                            '&sourceid=chrome&ie=UTF-8')

    bs = BeautifulSoup(response.text, 'lxml')

    el = bs.find(attrs={'class': 'BNeawe iBp4i AP7Wnd'})

    result = re.match(r'\d+,\d+', el.text).group()
    result = float(result.replace(',', '.'))
    return result


async def create_tasks(max_page, search_url,
                       dollar_rate, currency, city_filter):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for page in range(int(max_page)):
            current_url = search_url + f'&page={page}'
            task = asyncio.create_task(parse(session, current_url,
                                             dollar_rate=dollar_rate,
                                             currency=currency,
                                             city_filter=city_filter))
            tasks.append(task)

        await asyncio.gather(*tasks)


def write_json(keywords, directory):

    """Writing vacancies to json file"""

    for idx, words in enumerate(keywords):
        keywords[idx] = words.lower() if words else ''

    dir = directory if directory is not None else 'parse_results'
    file_name = f'vacancies_{keywords[0]},{keywords[1]}.json'

    if not os.path.exists('parse_results'):
        os.mkdir('parse_results')

    with open(f'{dir}/{file_name}', 'w', encoding='utf-8') as file:
        json.dump(VACANSIES, file, indent=4, ensure_ascii=False)


def main(params, show_detail=False):
    start = datetime.now()

    dollar_rate = get_dollar_exchange_rate() if params['currency'] else None

    max_page, search_url = set_params('https://hh.ru/',
                                      keywords=params['keywords'],
                                      city=params['city'],
                                      salary_filter=params['salary_filter'])

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(create_tasks(max_page, search_url, dollar_rate,
                                         params['currency'], params['city']))
    
    write_json([params['keywords'], params['city']],
                params.setdefault('direct', None))

    lead_time = datetime.now() - start

    if show_detail:
        print(f'[INFO] Dublicate: {dublicate_count}\n'
              f'[INFO] Dollar rate: {dollar_rate}\n'
              f'[INFO] Number of vacancies: {len(VACANSIES["vacancies"])}\n'
              f'[INFO] Lead time: {lead_time}')

    return [dublicate_count, str(dollar_rate), len(VACANSIES['vacancies']), lead_time]
    

if __name__ == '__main__':
    params = get_params()
    main(params, show_detail=True)
