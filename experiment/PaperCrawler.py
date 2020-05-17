import argparse

import os
from pathlib import Path
from functools import partial
from time import sleep

import re
from lxml import html

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver import Chrome, ChromeOptions

import pandas as pd

import sidekit


import os

_ns = {'re': 'http://exslt.org/regular-expressions'}


class paper_crawler():

    def __init__(self, executable_path, download_path, cache_path):

        self.download_path = Path(download_path)
        self.driver = self.make_driver(executable_path, download_path)
        self.html_loader = sidekit.page_source(self.driver, cache_path)

        self.by_domain_pdf_link_getter = {

            'www.sciencedirect.com': 
                partial(
                    self.get_link_xpath_trip,
                    orderd_xpath_list=[
                        """//*[@id="pdfLink"]""", 
                        """//*[@id='popover-content-download-pdf-popover']/div/div/a[1]"""
                    ]
                ),

            'www.ncbi.nlm.nih.gov':           
                self.get_link_xpath_pdf, 

            'academic.oup.com': 
                self.get_link_xpath_pdf, 

            'journals.plos.org': 
                partial(
                    self.get_link_xpath_trip,
                    orderd_xpath_list=[
                        """//*[@id="downloadPdf"]""", 
                    ]
                ),

            'www.jneurosci.org': 
                self.get_link_xpath_pdf, 

            'www.mdpi.com': 
                self.get_link_xpath_pdf,

            'stke.sciencemag.org': 
                self.get_link_xpath_pdf,

            'dmm.biologists.org': 
                partial(
                    self.get_link_xpath_trip,
                    orderd_xpath_list=[
                        """//*[@id="block-system-main"]/div/div/div/div/div[1]/div/div/div[5]/div/div/ul/li[6]/a[1]"""
                    ]
                ),

            'www.pnas.org': 
                self.get_link_xpath_pdf,

            'elifesciences.org':
                partial(
                    self.get_link_xpath_trip,
                    orderd_xpath_list=[
                        """//*[@id="maincontent"]/header/a""", 
                        """//*[@id="downloads"]/ul[1]/li[1]/a"""
                    ]
                ),
        }

        self.regrex_search_domain = re.compile(r"(?<=https://)[\.\w]+")

        self.file_list = set(self.download_path.glob('*'))

        
    def make_driver(self, executable_path=None, download_path=None):

        mime_types_pdf = "application/pdf,application/vnd.adobe.xfdf,application/vnd.fdf,application/vnd.adobe.xdp+xml, application/octet-stream"
        
        options = ChromeOptions()
        options.add_argument('--kiosk')
        options.add_argument('--kiosk-printing')
        options.add_argument("--disable-extensions")
        options.add_argument('--headless')

        prefs = {
            "download.default_directory" :  download_path, 
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)

        driver = Chrome(
            executable_path=executable_path,
            chrome_options=options
        )
        driver.set_window_position(0, 0)
        driver.set_window_size(1024, 768)

        return driver


    def chk_new_file(self):

        curr_file_list = set(self.download_path.glob('*'))
        new_file = curr_file_list - self.file_list
        new_file = new_file.pop() if not {*()} == new_file else ''
        new_file = Path(new_file)

        self.file_list = curr_file_list

        return new_file #example: PosixPath('download/pone.0118832.pdf')


    def get_link_xpath_trip(self, dom, orderd_xpath_list):

        if 1 < len(orderd_xpath_list):
            for xpath in orderd_xpath_list[:-1]:
                self.html_loader.driver.find_element_by_xpath(xpath).click()
                sleep(5)

        return self.html_loader.driver.find_element_by_xpath(orderd_xpath_list[-1]).get_attribute('href')


    def get_link_xpath_pdf(self, dom):
        return dom.xpath('//*[re:test(@href, ".*.pdf")]', namespaces=_ns)[0].attrib['href']


    def save_publication(self, url_to_publication):
        self.driver.get(url_to_publication)

        already_new_pdf_downloaded = bool(self.chk_new_file())
        
        if not already_new_pdf_downloaded:
            self.html_loader.actions.send_keys(Keys.CONTROL,'p').perform()


    def get_dom(self, query, param='', domain=''):
        src = self.html_loader.get(domain + query%tuple(param), use_cache=False)
        sleep(3.)
        dom = html.fromstring(src.replace("&nbsp;",""))

        return dom

    def get_last_file():
        list_of_files = glob('/path/to/folder/*') # * means all if need specific format then *.csv
        latest_file = max(list_of_files, key=os.path.getctime)
        return latest_file


    def excute(self, urls):

        for url in urls:
            dom = self.get_dom(url)
            curr_url = self.driver.current_url
            domain = self.regrex_search_domain.findall(curr_url)[0]

            pdf_link = self.by_domain_pdf_link_getter[domain](dom)

            is_full_link = bool(re.search(domain, pdf_link))

            if is_full_link:
                url_to_publication = pdf_link
            else:
                url_to_publication = 'https://' + domain + pdf_link

            print(url_to_publication)
            self.save_publication(url_to_publication)




def get_args():

    parser = argparse.ArgumentParser()

    parser.add_argument("links_csv", type=str)
    parser.add_argument("column", type=str)
    parser.add_argument("--download_path", default="./", type=str)
    parser.add_argument("--cache_path", default="./cache", type=str)
    parser.add_argument("--driver_path", default="C:/toolkit/bin/geckodriver.exe", type=str)
    
    return parser.parse_args()


def init(args):
    os.makedirs(args.cache_path, exist_ok=True)


if __name__ == '__main__':

    args = get_args()
    init(args)

    links_csv = pd.read_csv(args.links_csv)[args.column].to_list()[1:]
    crawler = paper_crawler(args.driver_path, args.download_path, args.cache_path)

    crawler.excute(links_csv)

