import tkinter as tk
from tkinter import filedialog
from tkinter.ttk import Combobox

from parser import main

direct = ''

def salary_validate(some):
    try:
        some = int(some)
        return True
    except ValueError:
        return False


def select_dir():
    global direct

    direct = filedialog.askdirectory()
    dir_label.config(text=direct)


def get_params():
    params = {}
    params['keywords'] = keyword.get()
    params['city'] = city.get()
    params['currency'] = currency.get()
    params['salary_filter'] = salary.get()
    params['direct'] = direct
    for key in params:
        if params[key] == '':
            params[key] = None
    start_parse(params)


def start_parse(params):
    dubl, dollar_rate, quantity, lead_time = main(params)
    window.geometry('400x330')
    text_area = tk.Text(window, width=50, height=5)
    text_area.place(width=375, x=12.25, y=210)
    text_area.insert(1.0, f'[INFO] Dublicate: {dubl}\n'
                          f'[INFO] Dollar rate: {str(dollar_rate)}\n'
                          f'[INFO] Number of vacancies: {str(quantity)}\n'
                          f'[INFO] Lead time: ' + str(lead_time))

window = tk.Tk()
window.geometry('400x240')

sal_val = window.register(salary_validate)


keyword_label = tk.Label(window, text='Введите ключевое слово: ')
keyword_label.place(x=0, y=10)
keyword = tk.Entry(window)
keyword.place(x=200, y=10)

city_label = tk.Label(window, text='Укажите город: ')
city_label.place(x=0, y=35)
city = tk.Entry(window)
city.place(x=200, y=35)

salary_label = tk.Label(window, text='Ввидите минимальную зарплату: ')
salary_label.place(x=0, y=60)
salary = tk.Entry(window, validate='key', 
                  validatecommand=(sal_val, '%P'))
salary.place(x=200, y=60)

currency_label = tk.Label(window, text='Выберите валюту: ')
currency_label.place(x=0, y=85)
currency = Combobox(window, values=('RUB', 'USD'),
                    state='readonly', width=17)
currency.place(x=200, y=85)

dir_label = tk.Label(window, text='hh_parse/parse_result')
dir_label.place(x=0, y=110)
dir_button = tk.Button(text='Обзор', command=select_dir)
dir_button.place(x=231.25, y=110, width=70)

submit_button = tk.Button(window, text='Начать', command=get_params)
submit_button.place(x=162.5, y=180)


if __name__ == '__main__':
    window.mainloop()
