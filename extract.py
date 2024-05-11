import trafilatura as tfr
import pprint as pp
import requests
import newspaper
from lxml import etree
from bs4 import BeautifulSoup
import os
import urllib.parse as urlparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def cleanup_file_name(file_name):
    if file_name.find("%") != -1:
        file_name = urlparse.unquote(file_name)
    return file_name.replace(" ", "_").replace(":", "").replace("/", "")

def save_file(url, folder) -> str:
    logging.info(f"Downloading {url}")
    # Tries to guess the filename (e.g., "image.png")
    filename = cleanup_file_name(os.path.basename(url))
    # If no filename can be guessed, we can create a random one
    # You may want to improve this logic based on your needs
    if not filename:
        filename = "file"
    file_path = os.path.join(folder, filename)
    # Check if file already exists
    if not os.path.isfile(file_path):
        r = requests.get(url)
        with open(file_path, 'wb') as f:
            f.write(r.content)
    return file_path

def main():
    urls = ["https://newsletter.pragmaticengineer.com/p/zirp", "https://newsletter.pragmaticengineer.com/p/zirp-software-engineers"]
    cookies = {'connect.sid': """s%3ADkMsCz345rRMcxMefq0iq1IizNbCwdl7.FtA4X5wR8yjBSNeTeifqeWY61Faqyiq1d8hTkzUt4Tg"""}
    
    for url in urls:
        response = requests.get(url, cookies=cookies)
        
        if response.status_code == 200:
            downloaded = response.content
            config = newspaper.Config()
            config.MAX_TEXT = 1000000
            
            art = newspaper.Article(url)
            art.download(input_html=downloaded)
            art.parse()
            art.nlp()
            
            xhtml = etree.tostring(art.clean_top_node, pretty_print=True).decode("utf-8")

            soup = BeautifulSoup(xhtml, "lxml")
            
            for source in soup.find_all('source'):
                source.decompose()
            
            for img in soup.find_all("img"):                
                img_url = img["src"]
                img.attrs = {}
                if not img_url.startswith("http"):
                    img_url = url + img_url # TODO this doesn't work FIXME
                
                path = save_file(img_url, "images")
                img["src"] = path
            
            # create valid file name from art.title
            file_name = art.title.replace(" ", "_").replace(":", "").replace("/", "")
            with open(file_name + ".html", 'w') as f:
                f.write(str(soup))
        

if __name__ == "__main__":
    main()