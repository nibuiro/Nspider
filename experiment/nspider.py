import argparse

import os
from time import sleep
from pathlib import Path

import re

import numpy as np
import pandas as pd

from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse

import requests
from lxml import html

from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver import Chrome, ChromeOptions

import PyPDF2 as pypdf

from functools import partial

from numba import jit

import sidekit
from PaperCrawler import paper_crawler


_ns = {'re': 'http://exslt.org/regular-expressions'}

domain = "https://www.ncbi.nlm.nih.gov"
gds_pubmed = "/pubmed?LinkName=gds_pubmed&from_uid=%s"#200044110

regrex_year_month = re.compile("((\d{4} )(Jun|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))")
regrex_accession_number = re.compile(r'GSE\d+')
regrex_auther = re.compile(r"[a-zA-Z ]+(?=\[Author\])")
regrex_publication_date_on_accession_display  = re.compile("(?<=Public on)[\w ,]+")
regrex_pmid = re.compile("(?<=PMID: )\d+")
regrex_doi_format = re.compile("([\d\.]+/[\d\w\-\.]+)")
regrex_pmid_format = re.compile("^(?!.*[^\d]).+$")

check_identifier = lambda regrex, identifier: bool(regrex.search(identifier))

search_pubmed_by_pmid = "/pubmed/%s"
search_pubmed_by_contributor = "/pubmed/?term=%s[Author]"
search_pubmed_by_gds_uid = "/pubmed?LinkName=gds_pubmed&from_uid=%s"
search_gds_by_uid = "/gds/?term=%s[uid]"

columns = {
    'gds': ['gds_uid', 'term', 'taxid', 'doi'],
    'publication': ['doi', 'pmid', 'is_free_pmc', 'title', 'abstract', 'successful_donwload'],
    'source': ['doi', 'src_domain', 'link_to_paper'],
}


def word_level_comprehension_score(src, tgt):

    src_word_set = set(src.split())
    tgt_word_set = set(tgt.split())

    return len(src_word_set & tgt_word_set) / len(src_word_set)


class nspider():

    def __init__(self, working_dir, executable_path, download_path, cache_path,
                 mode='csv', directory_polling_interval=2., directory_polling_limit=10):
        

        if 'csv' == mode:

            self.working_dir = Path(working_dir)
            self.working_dir.mkdir(exist_ok=True)
    
            self.download_dir = self.working_dir / 'publication'
            self.download_dir.mkdir(exist_ok=True)
    
            self.database_dir = self.working_dir / 'database'
            self.database_dir.mkdir(exist_ok=True)

            self.gds_path = self.database_dir / 'gds.csv'
            self.publication_path = self.database_dir / 'publication.csv'
            self.source_path = self.database_dir / 'source.csv'

            if self.gds_path.exists():
                self.gds = pd.read_csv(self.gds_path)
                self.gds_index = set(self.gds.gds_uid)
            else:
                self.gds = pd.DataFrame(columns=columns['gds'])
                self.gds_index = set()

            if self.publication_path.exists():
                self.publication = pd.read_csv(self.publication_path)
                self.publication_index = set(self.publication.doi)
            else:
                self.publication = pd.DataFrame(columns=columns['publication'])
                self.publication_index = set()

            if self.source_path.exists():
                self.source = pd.read_csv(self.source_path)
            else:
                self.source = pd.DataFrame(columns=columns['source'])

        elif 'oracle' == mode:

            pass

        #executable_path, download_path, cache_path, mode='csv', store_path='./'
        self.driver = self.make_driver(executable_path, str(self.download_dir))
        self.html_loader = sidekit.page_source(self.driver, cache_path)
        self.mode = mode

        self.crawler = paper_crawler(executable_path, str(self.download_dir), cache_path)
        self.directory_polling_interval = directory_polling_interval
        self.directory_polling_limit = directory_polling_limit



    def __del__(self):
 #       self.crawler.html_loader.driver.quit()
 #       self.html_loader.driver.quit()
        print( type(self.gds),type(self.publication),type(self.source))

        print("self.gds_path:", self.gds_path)
        print("self.publication_path:", self.publication_path)
        print("self.source_path:", self.source_path)

        self.gds.to_csv(self.gds_path)
        self.publication.to_csv(self.publication_path)
        self.source.to_csv(self.source_path)

            
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


    #private
    def _get_dom(self, query, param=None, domain="https://www.ncbi.nlm.nih.gov"):
        print(query, param)
        src = self.html_loader.get(domain + query%tuple([param] if param is not None else []))
        dom = html.fromstring(src.replace("&nbsp;",""))

        return dom


    def _dom_chunk_from_href(self, dom, xpath, domain=""):
        
        dom_chunk = []
    
        for has_href in dom.cssselect(xpath):
            dom = self._get_dom(has_href.attrib['href'])
            dom_chunk.append(dom)
    
        return dom_chunk
    

    def _register_dataset(self, gds):

        print("==_register_dataset==")


        if self.mode is 'csv':

            gds_uid = set(gds.gds_uid)
            print('gds_uid: ', gds_uid)
            print('self.gds_index :', self.gds_index )
            gds_uid_registered = gds_uid & self.gds_index 

#            assert ({*()} == gds_uid_registered), "Found duplicats."

            gds = gds[gds_uid_registered != gds.gds_uid]
            self.gds_index |= gds_uid - gds_uid_registered
            self.gds = pd.concat([self.gds, gds])
    

    def _register_publication(self, publication, source, ret=None):

        print("==_register_publication==")
        print('publication->\n', publication)
        print('source->\n', source)


        if self.mode is 'csv':

            publication_doi = set(publication.doi)
            publication_doi_registered = publication_doi & self.publication_index 

#            assert ({*()} == publication_doi_registered), "Found duplicats."

            publication = publication[publication_doi_registered != publication.doi]
            source = source[publication_doi_registered != source.doi]

            self.publication_index |= publication_doi - publication_doi_registered

            free_pmc_links = source[source.doi.isin(publication[publication.is_free_pmc].doi)]
            print("source", source)
            print("free_pmc_links", free_pmc_links)
            print("free_pmc_links.src_domain", free_pmc_links.columns)

            is_free_pmc_ncbi = 'www.ncbi.nlm.nih.gov' == free_pmc_links.src_domain
            free_pmc_ncbi = free_pmc_links[is_free_pmc_ncbi]

            for index, row in free_pmc_ncbi.iterrows():

                status = bool(self._download_paper_and_rename(row.doi, row.link_to_paper))

                publication.loc[row.doi == publication.doi, 'successful_donwload'] = status

            free_pmc_not_ncbi = free_pmc_links[~is_free_pmc_ncbi]

            for doi, subset in free_pmc_not_ncbi.groupby(['doi']):
                print(doi)

                if publication[doi == publication.doi].successful_donwload.values[0]:
                    continue

                status = False

                for index, row in subset.iterrows():

                    status = bool(self._download_paper_and_rename(row.doi, row.link_to_paper))

                    if status:
                        break
                    else:
                        pass

                publication.loc[row.doi == publication.doi, 'successful_donwload'] = status


            print('publication', publication)


            self.publication = pd.concat([self.publication, publication])
            print('self.publication', self.publication)
            self.source = pd.concat([self.source, source])

        return None


    def _download_paper_and_rename(self, doi, link):

        save_as = doi

        self.crawler.chk_new_file() #update file_list
        curr_files = self.crawler.file_list

        self.crawler.excute([link])

        name_new_file = None
        n_scan = 0

        while (name_new_file is None) & (self.directory_polling_limit > n_scan):

            name_new_file = self.crawler.chk_new_file()
            print(name_new_file)
            name_new_file = name_new_file if '.pdf' == name_new_file.suffix else None

            sleep(self.directory_polling_interval)
            n_scan += 1

        if name_new_file is not None:
            name_new_file.rename(self.crawler.download_path / (save_as + '.pdf'))

        else:
            pass

        return name_new_file

    
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


    def _get_text_from_publication(self, pmid):
    
        publication_text = ""
        publication_pdfFileObj = None


        if not pmid in self.publication.pmid:

            publication, source = self._get_publication_detail(search_pubmed_by_pmid, pmid)
        
        publication_pdfFileObj = self.load_publication(pmid)


        if publication_pdfFileObj is not None:

            publication_pdfReader = pypdf.PdfFileReader(publication_pdfFileObj)
            
            for page_number in range(publication_pdfReader.numPages):
                pageObj = publication_pdfReader.getPage(page_number) 
      
                publication_text += pageObj.extractText() 
                  
            publication_pdfFileObj.close() 
    
        return publication_text
    

    def _get_publication_detail(self, search_pubmed_by, param):
    
        publication = []
        source = []

        #search_pubmed_by_gds_uid
        if param in self.gds_index:

            doi = gds[gds_uid == gds.gds_uid].doi.values[0]

            if doi is not None:
                publication = self.publication[doi == self.publication.doi]
                source = self.source[doi == self.source.doi]

            return publication.values.tolist(), source.values.tolist()

        #search_pubmed_by_pmid
        if param in self.publication.pmid.values:

            publication = self.publication[param == self.publication.pmid]
            source = self.source[publication.doi.values[0] == self.source.doi]

            return publication.values.tolist(), source.values.tolist()

    
        dom = self._get_dom(search_pubmed_by, param)
        print("_get_publication_detail: successful get dom.")
        is_abstruction_page = ([] != dom.cssselect(".abstr"))
    
        abstr_chunk = []
    
        if not is_abstruction_page:
    
            abstr_chunk = self._dom_chunk_from_href(dom, ".rprt > .title > a")
    
        else:
            print("=is_abstruction_page=")
    
            abstr_chunk.append(dom)
    
        for dom in abstr_chunk:
            doi = dom.cssselect(".rprtid")[0].xpath('//a[re:test(@href, "(?i)(doi.org/*)")]', namespaces=_ns)[0].text.replace('/', '_slash') 

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

        if [] == publication:
            return [], []

        publication_df = pd.DataFrame(publication, columns=columns['publication'])
        source_df = pd.DataFrame(source, columns=columns['source'])

        self._register_publication(publication_df, source_df)
        return publication, source


    #@pysnooper.snoop()
    def _search_relative_publication_with_gds(self, uid, similarity_fn=word_level_comprehension_score):

        find_related_publication = False

        dom = self._get_dom(search_gds_by_uid, uid)
        
        accession_number = dom.cssselect(".rprtid > dd")[0].text
        print('\n\n\n\n\n\n\naccession_number>>>', accession_number)
        title = dom.cssselect(".title > a")[0]
        to_gse_link = title.attrib['href']
        print('to_gse_link: ', to_gse_link)
        dataset_title = title.text
        

        dom = self._get_dom(to_gse_link)
        
        other_accession_number = regrex_accession_number.findall(dom.text_content())
        publication_date_of_dataset = parse(regrex_publication_date_on_accession_display.findall(dom.text_content())[0])
        contributors = regrex_auther.findall(str(dom.xpath('//a/@href')))
        
        
        dom = self._get_dom(search_pubmed_by_contributor, contributors[0])
        
        desc = dom.cssselect(".rprt .desc")
        authers_list = [desc[i].text_content()[:-1].split(', ') for i in range(len(desc))] #delete period by [:-1]
        print('#authers_list', authers_list)
        matched_idx = []
        
        for idx, authers in enumerate(authers_list):
            if self._is_their_publication(contributors, authers):
                matched_idx.append(idx)
        
        date_intervals = []
        matched_idx_to_date_intervals_idx_table = {}
        
        details = dom.cssselect(".rprt .details")
        print('#details', len(details))
        
        for i, idx in enumerate(matched_idx):
            text = details[idx].text_content()
            publication_date_of_paper = parse(regrex_year_month.search(text)[0][0]).replace(day=1) #hasn't day info. init by 01.
            date_interval = abs(publication_date_of_paper - publication_date_of_dataset).days
            date_intervals.append(date_interval)
            matched_idx_to_date_intervals_idx_table[idx] = i
        
        # matched_idx -> date_intervals_idx -> date_intervals
        matched_idx = sorted(matched_idx, key=lambda idx: date_intervals[matched_idx_to_date_intervals_idx_table[idx]])
        
        
        titles = dom.cssselect(".rprt .title a")
        print('#titles', titles)
        pmids = [titles[idx].attrib['href'].split('/')[-1] for idx in matched_idx]

        for pmid in pmids:

            text = self._get_text_from_publication(pmid)

            if accession_number in text:
                find_related_publication = True
                return pmid, None, find_related_publication

        similarity = []

        for pmid in pmids:

            abstruct = self.publication[pmid == self.publication.pmid].abstract.values[0]
            similarity.append(similarity_fn(dataset_title, abstruct))

        max_idx = max(range(len(similarity)), key=lambda x: similarity[x])

        find_related_publication = True

        return pmids[max_idx], similarity[max_idx], find_related_publication


    def _register_publication_by_gds_uid(self, gds_uids):

        print('_register_publication_by_gds_uid')

        gds = []
        publication = []
        source = []
        binded = []
    
        for gds_uid in gds_uids:
    
            _publication, _source = self._get_publication_detail(search_pubmed_by_gds_uid, gds_uid)
            print("##!#  _publicationdoi", type(_publication), '\n\n\n')
            doi = _publication[:1][:1]
            print("#!#  doi", doi, '\n\n\n')
            if [] == _publication:
                doi = None
            else:
                doi = _publication[0][0]

            _gds = [[gds_uid, None, None, doi]] #[:1][:1] for avoiding out of index error

            print('dDOI!!!!!!!!!!!!!!!!!!', doi)
     
            if doi is None:
                binded.append(False)
            else:
                binded.append(True)

                gds += _gds
                publication += _publication
                source += _source
    
            

        print(_publication, _source)

        binding_check_table = pd.DataFrame(
            zip(gds_uids, binded, np.zeros_like(gds_uids, dtype=np.bool)), 
            columns=['gds_uid', 'is_binded', 'find_related_publication']
        )

        nrow = len(binding_check_table)

        for idx in range(nrow):

            row = binding_check_table.iloc[idx]

            print('not row.is_binded', not row.is_binded)

            if not row.is_binded:

                pmid, score, find_related_publication = self._search_relative_publication_with_gds(row.gds_uid)
                
                if find_related_publication:

                    _publication, _source = self._get_publication_detail(search_pubmed_by_pmid, pmid)
                    print("#!#  _publication", type(_publication), '\n\n\n')
                    if [] == _publication:
                        doi = None
                    else:
                        doi = _publication[0][0]
                    print("#!#  doi", doi, '\n\n\n')
                    _gds = [[row.gds_uid, None, None, doi]]

                    gds += _gds
                    publication += _publication
                    source += _source

                binding_check_table.find_related_publication.at[idx] = find_related_publication

        gds = pd.DataFrame(gds, columns=columns['gds'])
        self._register_dataset(gds)

        return None


    #public
    def load_publication(self, identifier):

        if check_identifier(regrex_doi_format, identifier.replace('_slash', '/')):
            type_of_identifier = 'doi'
        elif check_identifier(regrex_pmid_format, identifier):
            type_of_identifier = 'pmid'
        else:
            raise AttributeError("Invalid identifier format.")

        pdfFileObj = None

        if 'csv' == self.mode:
            entry = self.publication[self.publication[type_of_identifier] == identifier]
            print('entry', entry)
            if entry.successful_donwload.values[0]:

                print('entry.doi.values', entry.doi.values[0])

                print(self.download_dir)

                print(os.getcwd())

                fpath = self.download_dir / (entry.doi.values[0] + '.pdf')
                pdfFileObj = open(fpath, 'rb')

            else:

                pass

        else:

            pass

        return pdfFileObj


    def get_pmid_by_gds_uid(self, gds_uid):

        if not gds_uid in self.gds_index:

            self._register_publication_by_gds_uid([gds_uid])            

        doi = self.gds[gds_uid == self.gds.gds_uid].doi.values[0]
        print('\n\n\n\n', doi, '\n\n\n\n')
        pmid = self.publication[doi == self.publication.doi].pmid

        return pmid


    def get_gds_uid_by_pmid(self, pmid):

        if not pmid in self.publication.pmid:
            return None

        doi = self.publication[pmid == self.publication].doi
        gds_uid = self.gds[doi == self.gds.doi].gds_uid

        return gds_uid
    
    

if __name__ == '__main__':
    import shutil
    
    shutil.rmtree('./work/publication/')
    shutil.rmtree('./work/database/')
    os.mkdir('./work/publication/')

    spider = nspider('./work', "/home/poo/Downloads/chromedriver", 'download/', 'cache/', directory_polling_interval=5., directory_polling_limit=10)
#print(spider.get_pmid_by_gds_uid('200011474'))
    print(spider.get_pmid_by_gds_uid('200030845'))

    del spider

