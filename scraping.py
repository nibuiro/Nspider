import os
from time import sleep

import re

from dateutil.parser import parse

import requests
from lxml import html

from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver import Chrome, ChromeOptions

import sidekit

from utils import *
from utils import namespace_regrex

def word_level_comprehension_score(src, tgt):

    src_word_set = set(src.split())
    tgt_word_set = set(tgt.split())

    return len(src_word_set & tgt_word_set) / len(src_word_set)


class scraping():

    def __init__(self, executable_path, cache_path, download_path):
        
        self.driver = self._make_driver(executable_path, download_path)
        self.html_loader = sidekit.page_source(self.driver, cache_path)

            
    def _make_driver(self, executable_path=None, download_path=None):

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
    
    #private
    def _get_dom(self, query, param=None, domain="https://www.ncbi.nlm.nih.gov"):

        src = self.html_loader.get(domain + query%tuple([param] if param is not None else []))
        dom = html.fromstring(src.replace("&nbsp;",""))

        return dom


    def _dom_chunk_from_href(self, dom, xpath, domain=""):
        
        dom_chunk = []
    
        for has_href in dom.cssselect(xpath):
            dom = self._get_dom(has_href.attrib['href'])
            dom_chunk.append(dom)
    
        return dom_chunk

    
    def _is_their_publication(self, contributors, authers):

        is_same = lambda a, b: ((a in b) | (b in a))

        contributors = sorted(contributors, reverse=True, key=len)
        authers = sorted(authers, reverse=True, key=len)
        count = 0
        for contributor in contributors:
            for i, auther in enumerate(authers):
                if is_same(contributor, auther):
                    count += 1
                    authers.pop(i)
                    break

        return (len(contributors) == count)


    def search_publication_detail(self, search_pubmed_by, param):
    
        publication = []
        source = []
     
        dom = self._get_dom(search_pubmed_by, param)
        is_abstruction_page = ([] != dom.cssselect(".abstr"))
    
        abstr_chunk = []
    
        if not is_abstruction_page:
    
            abstr_chunk = self._dom_chunk_from_href(dom, ".rprt > .title > a")
    
        else:
    
            abstr_chunk.append(dom)
    
        for dom in abstr_chunk:
            doi = dom.cssselect(".rprtid")[0].xpath('//a[re:test(@href, "(?i)(doi.org/*)")]', namespaces=namespace_regrex)[0].text.replace('/', '_slash') 

            aux_txt = dom.cssselect(".aux")[0].text_content()

            pmid = regrex_pmid.findall(aux_txt)[0]
        
            is_free_pmc = (not [] == dom.cssselect(".status_icon"))
            
            abstruct = dom.cssselect(".abstr > div > p")[0].text
    
            title = dom.cssselect(".abstract > h1")[0].text
            
            links_to_paper = [element.attrib['href'] for element in dom.cssselect(".portlet > a")]

            publication.append([doi, pmid, is_free_pmc, title, abstruct, None])

            for link_to_paper in links_to_paper:
    
                src_domain = link_to_paper.split('/')[2] #['https:', '', 'academic.oup.com', 'hmg', 'article-lookup', 'doi', '10.1093', 'hmg', 'ddt076']
    
                source.append([doi, src_domain, link_to_paper])

        return publication, source


    def search_relative_pmids_with_gds(self, uid, similarity_fn=word_level_comprehension_score):

        find_related_publication = False

        dom = self._get_dom(search_gds_by_uid, uid)
        
        accession_number = dom.cssselect(".rprtid > dd")[0].text

        title = dom.cssselect(".title > a")[0]
        to_gse_link = title.attrib['href']

        dataset_title = title.text
        

        dom = self._get_dom(to_gse_link)
        
        other_accession_number = regrex_accession_number.findall(dom.text_content())
        publication_date_of_dataset = parse(regrex_publication_date_on_accession_display.findall(dom.text_content())[0])
        contributors = regrex_auther.findall(str(dom.xpath('//a/@href')))
        
        
        dom = self._get_dom(search_pubmed_by_contributor, contributors[0])
        
        desc = dom.cssselect(".rprt .desc")
        authers_list = [desc[i].text_content()[:-1].split(', ') for i in range(len(desc))] #delete period by [:-1]

        matched_idx = []
        
        for idx, authers in enumerate(authers_list):
            if self._is_their_publication(contributors, authers):
                matched_idx.append(idx)
        
        date_intervals = []
        matched_idx_to_date_intervals_idx_table = {}
        
        details = dom.cssselect(".rprt .details")

        
        for i, idx in enumerate(matched_idx):
            text = details[idx].text_content()
            publication_date_of_paper = parse(regrex_year_month.search(text)[0][0]).replace(day=1) #hasn't day info. init by 01.
            date_interval = abs(publication_date_of_paper - publication_date_of_dataset).days
            date_intervals.append(date_interval)
            matched_idx_to_date_intervals_idx_table[idx] = i
        
        # matched_idx -> date_intervals_idx -> date_intervals
        matched_idx = sorted(matched_idx, key=lambda idx: date_intervals[matched_idx_to_date_intervals_idx_table[idx]])
        
        
        titles = dom.cssselect(".rprt .title a")

        pmids = [titles[idx].attrib['href'].split('/')[-1] for idx in matched_idx]

        return pmids