import argparse

import os
from time import sleep
from pathlib import Path

import re

import numpy as np
import pandas as pd


import PyPDF2 as pypdf


from crawling import paper_crawler
from scraping import scraping

from utils import *
from utils import namespace_regrex


class nspider():

    def __init__(self, working_dir, executable_path, download_path, cache_path,
                 mode='csv', directory_polling_interval=2., directory_polling_limit=10):
        
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

        self.scraping = scraping(executable_path, cache_path, download_path)

        self.crawler = paper_crawler(executable_path, str(self.download_dir), cache_path)
        self.directory_polling_interval = directory_polling_interval
        self.directory_polling_limit = directory_polling_limit


    def _register_dataset(self, gds):

        gds_uid = set(gds.gds_uid)
        gds_uid_registered = gds_uid & self.gds_index 

#        assert ({*()} == gds_uid_registered), "Found duplicats."

        gds = gds[gds_uid_registered != gds.gds_uid]
        self.gds_index |= gds_uid - gds_uid_registered
        self.gds = pd.concat([self.gds, gds])
    

    def _register_publication(self, publication, source, ret=None):

        publication_doi = set(publication.doi)
        publication_doi_registered = publication_doi & self.publication_index 

#        assert ({*()} == publication_doi_registered), "Found duplicats."

        publication = publication[publication_doi_registered != publication.doi]
        source = source[publication_doi_registered != source.doi]

        self.publication_index |= publication_doi - publication_doi_registered

        free_pmc_links = source[source.doi.isin(publication[publication.is_free_pmc].doi)]

        is_free_pmc_ncbi = 'www.ncbi.nlm.nih.gov' == free_pmc_links.src_domain
        free_pmc_ncbi = free_pmc_links[is_free_pmc_ncbi]

        for index, row in free_pmc_ncbi.iterrows():

            status = bool(self._download_paper_and_rename(row.doi, row.link_to_paper))

            publication.loc[row.doi == publication.doi, 'successful_donwload'] = status

        free_pmc_not_ncbi = free_pmc_links[~is_free_pmc_ncbi]

        for doi, subset in free_pmc_not_ncbi.groupby(['doi']):

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

        self.publication = pd.concat([self.publication, publication])
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
            name_new_file = name_new_file if '.pdf' == name_new_file.suffix else None

            sleep(self.directory_polling_interval)
            n_scan += 1

        if name_new_file is not None:
            name_new_file.rename(self.crawler.download_path / (save_as + '.pdf'))

        else:
            pass

        return name_new_file


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

        #search_pubmed_by_gds_uid
        if param in self.gds_index:

            doi = gds[gds_uid == gds.gds_uid].doi.squeeze()

            if doi is not None:
                publication = self.publication[doi == self.publication.doi]
                source = self.source[doi == self.source.doi]

            return publication.values.tolist(), source.values.tolist()

        #search_pubmed_by_pmid
        if param in self.publication.pmid.values:

            publication = self.publication[param == self.publication.pmid]
            source = self.source[publication.doi.squeeze() == self.source.doi]

            return publication.values.tolist(), source.values.tolist()

    
        publication, source = self.scraping.search_publication_detail(search_pubmed_by, param)

        if [] == publication:
            return publication, source

        publication_df = pd.DataFrame(publication, columns=columns['publication'])
        source_df = pd.DataFrame(source, columns=columns['source'])

        self._register_publication(publication_df, source_df)
        return publication, source


    #@pysnooper.snoop()
    def _search_relative_publication_with_gds(self, uid):

        pmids = self.scraping.search_relative_pmids_with_gds(uid)

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

        gds = []
        publication = []
        source = []
        binded = []
    
        for gds_uid in gds_uids:
    
            _publication, _source = self._get_publication_detail(search_pubmed_by_gds_uid, gds_uid)

            if [] == _publication:
                doi = None
            else:
                doi = _publication[0][0]

            _gds = [[gds_uid, doi]]
     
            if doi is None:
                binded += [False]
            else:
                binded += [True]

                gds += _gds
                publication += _publication
                source += _source

        binding_check_table = pd.DataFrame(
            zip(gds_uids, binded, np.zeros_like(gds_uids, dtype=np.bool)), 
            columns=['gds_uid', 'is_binded', 'find_related_publication']
        )

        nrow = len(binding_check_table)

        for idx in range(nrow):

            row = binding_check_table.iloc[idx]

            if not row.is_binded:

                pmid, score, find_related_publication = self._search_relative_publication_with_gds(row.gds_uid)
                
                if find_related_publication:

                    _publication, _source = self._get_publication_detail(search_pubmed_by_pmid, pmid)

                    if [] == _publication:
                        doi = None
                    else:
                        doi = _publication[0][0]

                    _gds = [[row.gds_uid, doi]]

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

        entry = self.publication[self.publication[type_of_identifier] == identifier]

        if entry.successful_donwload.squeeze():

            fpath = self.download_dir / (entry.doi.squeeze() + '.pdf')
            pdfFileObj = open(fpath, 'rb')

        else:

            pass

        return pdfFileObj


    def get_pmid_by_gds_uid(self, gds_uid):

        if not gds_uid in self.gds_index:

            self._register_publication_by_gds_uid([gds_uid])            

        doi = self.gds[gds_uid == self.gds.gds_uid].doi.values[0]

        pmid = self.publication[doi == self.publication.doi].pmid

        return pmid


    def get_gds_uid_by_pmid(self, pmid):

        if not pmid in self.publication.pmid:
            return None

        doi = self.publication[pmid == self.publication].doi
        gds_uid = self.gds[doi == self.gds.doi].gds_uid

        return gds_uid


    def commit(self):

        self.gds.to_csv(self.gds_path)
        self.publication.to_csv(self.publication_path)
        self.source.to_csv(self.source_path)
  
    

if __name__ == '__main__':
    import shutil
    
    shutil.rmtree('./work/publication/')
    shutil.rmtree('./work/database/')
    os.mkdir('./work/publication/')

    spider = nspider('./work', "/home/bioinfo-lab/Downloads/chromedriver_linux64/chromedriver", 'download/', 'cache/', directory_polling_interval=5., directory_polling_limit=10)
    print(spider.get_pmid_by_gds_uid('200011474'))
#    print(spider.get_pmid_by_gds_uid('200030845'))

    spider.commit()

    del spider

