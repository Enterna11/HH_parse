import time
import lxml
import json
import requests
import re
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service

URL='https://hh.ru/'

def get_params():
    params = {}
    params['keywords'] = input('Введите ключевые слова для поиска: ').capitalize()
    params['city'] = input('Введите город: ').capitalize()
    while True:
        params['currency'] = input('Введите валюту (RUB, USD): ').upper()
        currency_check = re.match(r'(USD|RUB)', params['currency'])
        if currency_check is not None or params['currency'] == '':
            break
        print('[INFO] Недопустимый ввод')
    while True:
        params['salary_filter'] = input('Введите минимальную желаемую зарплату в рублях: ')
        salary_filter_check = re.match(r'^\d+$', params['salary_filter'])
        if salary_filter_check is not None or params['salary_filter'] == '':
            break
        print('[INFO] Недопустимый ввод')
    for key in params:
        if params[key] == '':
            params[key] = None
    return params

def get_data(url, keywords, city, salary_filter):
    user_agent = UserAgent()

    service = Service(ChromeDriverManager().install())

    options = ChromeOptions()
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_argument(f'user-agent={user_agent.random}')
    options.add_argument('--headless')

    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(10)
    
    page_range = [1, 0]
    actions = ActionChains(driver)
    html_list = []
    try:
        driver.get(url=url)

        keywords_input = driver.find_element(value='a11y-search-input')
        if keywords:
            keywords_input.send_keys(keywords)
        keywords_input.send_keys(Keys.ENTER)

        filter_button = driver.find_element(By.CLASS_NAME, value='bloko-icon-link')
        filter_button.click()
            
        el = driver.find_element(By.CLASS_NAME, value='supernova-footer-nav-logo')
        actions.move_to_element(el).click().perform()

        clear_buttons = driver.find_elements(By.CLASS_NAME, value='bloko-tag-button')
        for button in clear_buttons:
            button.click()
            
        if city:               
            city_input = driver.find_element(By.CSS_SELECTOR, value='input[data-qa=resumes-search-region-add]')
            city_input.send_keys(city)

            time.sleep(2)

        if salary_filter:
            salary_input = driver.find_element(By.CSS_SELECTOR, value='input[data-qa=vacancysearch__compensation-input]')
            salary_input.send_keys(salary_filter)

            checkbox = driver.find_element(By.XPATH, '//span[contains(text(), "Показывать только вакансии")]')
            checkbox.click()

        submit_button = driver.find_element(value='submit-bottom')
        submit_button.click()

        time.sleep(2)
            
        while True:
            html_list.append(driver.page_source)
            page_range[0] += 1
            page_range[1] += 1
            next_page = driver.find_elements(By.CSS_SELECTOR, value=f'span[data-qa=pager-page-wrapper-{page_range[0]}-{page_range[1]}]')
            if next_page:
                actions.move_to_element(next_page[0]).click().perform()
                time.sleep(1)
            else:
                break           
    except Exception as e:
        print(e)
    finally:
        driver.close()
        driver.quit()
        return html_list


def parse(html, currency, dollar_rate):
    vacancy_list = []
    for page in html:
        bs = BeautifulSoup(page, 'lxml')
        titles = bs.find_all('div', class_='vacancy-serp-item vacancy-serp-item_redesigned')
        for el in titles:
            a = el.find(attrs={'data-qa': 'vacancy-serp__vacancy-title'})
            salary = el.find(attrs={'data-qa': 'vacancy-serp__vacancy-compensation'})
            if currency:
                salary = salary_format(salary, currency, dollar_rate)
            else:
                salary = salary.text.replace('\u202f', '')
            placement_date = el.find(attrs={'data-qa': 'vacancy-serp__vacancy-date'})
            company = el.find(attrs={'data-qa': 'vacancy-serp__vacancy-employer'})
            if company is None:
                company = el.find(attrs={'class': 'vacancy-serp-item__meta-info-company'})  
            remote = el.find(text='Можно работать из дома')
            vacancy = {
                'title': a.text,
                'link': a.get('href'),
                'salary': salary,
                'company name': company.text if company else 'Не указано',
                'company link': f'https://hh.ru{company.get("href")}' if company.get('href') else 'Не указано',
                'remote': remote if remote else 'Работа в офисе',
                'placement date': placement_date.text if placement_date else 'Не указано'
            }
            if vacancy in vacancy_list:
                continue
            else:
                vacancy_list.append(vacancy)
    objects = { 'vacancies': vacancy_list }
    print(f'[INFO] Количество вакансий: {len(vacancy_list)}')
    with open('vacancies.json', 'w', encoding='utf-8') as file:
        json.dump(objects, file, indent=4, ensure_ascii=False)

def salary_format(salary, currency, dollar_rate):
    if salary:
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
    else:
        return 'Не указана'

def get_dollar_exchange_rate():
    response = requests.get('https://www.google.com/'
                            'search?q=%D0%BA%D1%83%D1%80%D1%81+%D0%B4%D0%BE%D0%BB%D0%BB%D0%B0%D1%80%D0%B0&oq=%D0%BA%D1%83%D1%80%D1%81+%D0%B4%D0%BE%D0%BB%D0%BB%D0%B0&'
                            'aqs=chrome.0.0i131i433i512j69i57j0i131i433i512l4j0i512j0i433i512j0i512j0i131i433i512.4128j1j7&sourceid=chrome&ie=UTF-8')
    bs = BeautifulSoup(response.text, 'lxml')
    el = bs.find(attrs={'class': 'BNeawe iBp4i AP7Wnd'})
    result = re.match(r'\d+,\d+', el.text).group()
    result = float(result.replace(',', '.'))
    print('[INFO] Dollar rate: ' + str(result))
    return result
    
def main():
    params = get_params()
    if params['currency']:
        dollar_rate = get_dollar_exchange_rate()
    else:
        dollar_rate = None
    html_list = get_data(url=URL, keywords=params['keywords'], city=params['city'], salary_filter=params['salary_filter'])
    parse(html=html_list, dollar_rate=dollar_rate, currency=params['currency'])


if __name__ == '__main__':
    main()