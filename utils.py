import re



namespace_regrex = {'re': 'http://exslt.org/regular-expressions'}


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
    'gds': ['gds_uid', 'doi'],
    'publication': ['doi', 'pmid', 'is_free_pmc', 'title', 'abstract', 'successful_donwload'],
    'source': ['doi', 'src_domain', 'link_to_paper'],
}