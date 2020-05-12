import nspider



spider = nspider.nspider('./work', "/home/poo/Downloads/chromedriver", 'download/', 'cache/')
print(spider.get_pmid_by_gds_uid('200011474'))
