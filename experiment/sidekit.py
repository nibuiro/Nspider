###########################
### kugane's sidekit!!! ###
###########################
import re
import os
import sys
import time
import codecs
import base64
import hashlib
import zipfile
from io import BytesIO
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains

class page_source:
    def __init__(self, driver, save_path, cool_time=1.6):

        self.driver = driver
        self.actions = ActionChains(driver)
        self.save_path = save_path
        self.cool_time = 3.2
        self.symbol = re.compile("[^一-龥ぁ-んァ-ンa-xA-Z0-9_]")
        self.logfile = open('attention.log','a')
        self.current = None
        self.currentfile = open("current.html", 'w')

    def __del__(self):
        #from contextlib import redirect_stdout
#
        #with redirect_stdout(self.currentfile):
        #    print(self.current)
        self.currentfile.close()

        self.logfile.close()

    def get(self, url, tgt_xpath=None, time_out=2.56, remain=3, nametype='raw', use_cache=True, output=True):
        
        if output:
            print(url)

        # old_filename = hashlib.md5(url.encode('utf-8')).hexdigest()
        # old_file_path = os.path.join(self.save_path, old_filename)
        # old_filename = hashlib.sha1(url.encode('utf-8')).hexdigest()
        # old_file_path = os.path.join(self.save_path, old_filename)
        if 'raw' == nametype:
            filename = re.sub(self.symbol, "", url)
        elif 'md5' == nametype:
            filename = hashlib.md5(url.encode('utf-8')).hexdigest()
        elif 'sha1' == nametype:
            filename = hashlib.sha1(url.encode('utf-8')).hexdigest()

        file_path = os.path.join(self.save_path, filename)


        if os.path.isfile(file_path) & use_cache:
            file_proxy = codecs.open(file_path, 'r', 'UTF-8')
            src = file_proxy.read()
            file_proxy.close()

            return src
        else:
            while True:
                try:
                    print("connect")
                    self.driver.get(url)
                except:
                    remain -= 1
                    
                    if 0 <= remain:
                        time.sleep( 600 )
                        continue

                    if input(">>CONTINUE ? (yes/no)") == 'no':
                        if input(">>REALLY ? (yes/no)") == 'yes':
                                sys.exit()
                else:
                    break
            
            wait_time = 0
            response_time = self.driver.execute_script(
                "return performance.timing.loadEventEnd - performance.timing.navigationStart;"
            )

            if 1 <= response_time:
                self.logfile.write(f'{url}\n{filename}\n')

            if None == tgt_xpath:
                print(f"response_time: {response_time}us")
                print(f"cool time: {self.cool_time}s")
#                time.sleep( self.cool_time )

            else:
                try:
                    start = time.time()

                    for xpath in tgt_xpath:
                        WebDriverWait(self.driver, time_out).until(
                            expected_conditions.presence_of_element_located((By.XPATH, xpath))
                        )
                        time_out /= 2

                    elapsed_time = time.time() - start
                    print(f"wait time: {elapsed_time}")
                    
                    if 1 > elapsed_time:
                        time.sleep( 1 - elapsed_time)
                
                except:
                    print(f"""
                        ===============================================
                        >> Warning!!! indicated element has not loaded.
                        ===============================================
                        URL = {url}
                        XPath = {tgt_xpath}
                    """)

            self.current = self.driver.page_source
            
            file_proxy = codecs.open(file_path, 'w', 'UTF-8')
            file_proxy.write(self.current)
            file_proxy.close()

            return self.current.replace("\xa0","").replace("&nbsp;","")


def clear_firefox(
        driver, timeout=10, 
        del_garbage=False, del_cookie=False, del_sitedata=False
    ):

    def get_Minimize_memory_usage_button(driver):
        return driver.find_element_by_xpath("//*[contains( ./text() , 'Minimize memory usage')]")

    def get_clear_cache_button(driver):
        return driver.find_element_by_css_selector('#clearCacheButton')
    
    def get_clear_site_data_button(driver):
        return driver.find_element_by_css_selector('#clearSiteDataButton')

    wait = WebDriverWait(driver, timeout)

    if del_garbage:
        driver.get('about:memory')
        wait.until(get_Minimize_memory_usage_button)
        get_Minimize_memory_usage_button(driver).click()

    # Click the "Clear Now" button under "Cached Web Content"
    if del_cookie:
        driver.get('about:preferences#privacy')
        wait.until(get_clear_cache_button)
        get_clear_cache_button(driver).click()

    # Click the "Clear All Data" button under "Site Data" and accept the alert
    if del_sitedata:
        driver.get('about:preferences#privacy')
        wait.until(get_clear_site_data_button)
        get_clear_site_data_button(driver).click()
    
        wait.until(EC.alert_is_present())
        alert = Alert(driver)
        alert.accept()

    return


def not_null_returnfirst(one_array, func_name=None, argument=None):
    if not [] == one_array or None == one_array:
        if not None == func_name:
            if not None == argument:
                return getattr(one_array[0], func_name)(argument) #Please set by dictionary
            return getattr(one_array[0], func_name)()
        return one_array[0]
    else:
        return None


def hmsf_convert2secf(hmsf):

    if not [] == re.findall("[^0-9.:]", hmsf):
        return None

    secf = None
    splited_dot = hmsf.split('.')
    num_i = not_null_returnfirst(splited_dot)
    
    if not None == num_i:
        secf = 0
        splited_colon = num_i.split(':')

        for i, num in enumerate(reversed(splited_colon)):
            secf += ( int(num) * ( 60 ** i ) )

        if not [] == splited_dot[1:]:
            secf = f"{secf}{splited_dot[1]}"
        else:
            secf = f"{secf}0"

    return secf


def tounicode(data):
    character_encoding = ['shift_jis','utf-8','euc_jp','cp932',
              'euc_jis_2004','euc_jisx0213','iso2022_jp','iso2022_jp_1',
              'iso2022_jp_2','iso2022_jp_2004','iso2022_jp_3','iso2022_jp_ext',
              'shift_jis_2004','shift_jisx0213','utf_16','utf_16_be',
              'utf_16_le','utf_7','utf_8_sig']
    for code in character_encoding:
        try: return (lambda d, enc: d.decode(enc))(data, code)
        except: continue
    print("Can't decoding :(")
    return None

import os
import sys

class mgt_archives_7z:
    def __init__(self, dir_archives, dir_raws, level=9, method='LZMA2'):
        self.dir_archives = dir_archives
        self.dir_raws = dir_raws
        self.level = level
        self.method = method
        self.extracting_now = None

    def compress(self, name_archive, dir_has_tgt=None, tgts=None, _shell=True, wait=True):
        import os
        from subprocess import Popen

        if os.path.exists(f"{self.dir_archives}{name_archive}"):
            return
        if None == dir_has_tgt:
            dir_has_tgt = self.dir_raws
        if None == tgts:
            command = f"""7za a -m{self.level}={self.method} -t7z {self.dir_archives}{name_archive} {dir_has_tgt}*"""
        else:
            tgts = "".join([f" {dir_has_tgt}{tgt}" for tgt in tgts])
            command = f"""7za a -m{self.level}={self.method} -t7z {self.dir_archives}{name_archive}{tgts}"""

        if wait:
            Popen(command, shell=_shell).wait()
        else:
            return Popen(command, shell=_shell)
        
    def extract(self, name_archive, dist_extract = None, _shell=True, wait=True):
        import os
        from subprocess import Popen

        if None == dist_extract:
            dist_extract = self.dir_raws
        if os.path.exists(f"{self.dir_archives}{name_archive}"):
            self.current_extracted = name_archive
            if wait:
                Popen(f"""7za e {self.dir_archives}{name_archive} -o{dist_extract}""", shell=_shell).wait()
            else:
                return Popen(f"""7za e {self.dir_archives}{name_archive} -o{dist_extract}""", shell=_shell)

    def names_archive(self):
        import os

        return [os.path.basename(haspath) for haspath in glob.glob(f"{self.dir_archives}*.7z")]

    def del_dir_raws(self):
        from subprocess import Popen
        Popen(f""" del /s/q "{self.dir_raws}" """, shell=True).wait()
