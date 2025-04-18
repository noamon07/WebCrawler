from re import search

import requests
import sys
import os
import tldextract
from urllib.parse import urlparse, urljoin
import json
from bs4 import BeautifulSoup


DUMPS_DIR = "C:\\Users\\noam\\PycharmProjects\\WebCrawler\\cache"

class CrawlerContext:
    def __init__(self, url):
        extracted = tldextract.extract(url)
        self.domain = f"{extracted.domain}.{extracted.suffix}"
        self.root_dir = os.path.join(DUMPS_DIR, self.domain)
        self.parts = urlparse(url)
        self.todo = set()
        self.todo.add((url,None))

    def url_to_dir(self, url):
        extracted = tldextract.extract(url)
        url_fs_path = os.path.join(DUMPS_DIR, f"{extracted.domain}.{extracted.suffix}")
        if extracted.subdomain:
            url_fs_path = os.path.join(url_fs_path, f"{extracted.subdomain}")
        else:
            url_fs_path = os.path.join(url_fs_path, "$")
        parts = urlparse(url).path.split("/")[1:]
        for part in parts[:-1]:
            url_fs_path = os.path.join(url_fs_path, f"{part}")
        if len(parts) == 0:
            # in case that we dont have path and file name
            url_fs_path = os.path.join(url_fs_path, "$")
        else:
            url_fs_path = os.path.join(url_fs_path, f"{parts[-1]}")
            if len(parts[-1].split(".")) == 1:
                # checking if the its a file with extention (.html, .xml...)
                url_fs_path = os.path.join(url_fs_path, "$")
        return url_fs_path

    def url_dir_to_html(self, path_dir):
        return os.path.join(path_dir, "raw.html")

    def url_dir_to_links(self, path_dir):
        return os.path.join(path_dir, "links.json")

    def url_dir_to_url_file(self, path_dir):
        return os.path.join(path_dir, "url.txt")

    def url_dir_to_references(self, path_dir):
        return os.path.join(path_dir, "references.json")

    def url_dir_to_content(self, path_dir):
        return os.path.join(path_dir, "content.txt")

    def url_dump(self, url):
        """

        :param url:
        :return: path_dir, bool downloaded
        """

        path_dir = self.url_to_dir(url)
        path_url = self.url_dir_to_url_file(path_dir)
        path_html = self.url_dir_to_html(path_dir)



        if os.path.exists(path_html):
            return path_dir, False

        url_request = requests.get(url)
        url_request.raise_for_status()
        if url_request.url != url:
            url = url_request.url
            path_dir = self.url_to_dir(url)
            path_html = self.url_dir_to_html(path_dir)
            path_url = self.url_dir_to_url_file(path_dir)
            if os.path.exists(path_html):
                return path_dir, False

        os.makedirs(path_dir, exist_ok=True)

        if not os.path.exists(path_url):
            with open(path_url, "w") as file:
                file.write(url)

        try:
            with open(path_html, "wb") as file:
                file.write(url_request.content)
        except:
            if os.path.exists(path_html):
                os.remove(path_html)
            raise
        return path_dir, True

    def validate_url(self, url):
        parsed_url = urlparse(url)
        return all([parsed_url.scheme, parsed_url.netloc])

    def url_parse_html(self,url, path_dir):
        try:
            with open(self.url_dir_to_html(path_dir), "r", encoding="utf-8") as file:
                soup = BeautifulSoup(file, 'html.parser')
        except UnicodeDecodeError:
            try:
                with open(self.url_dir_to_html(path_dir), "r") as file:
                    soup = BeautifulSoup(file, 'html.parser')
            except:
                return


        a_tags = soup.find_all('a')
        links = set()
        for a_tag in a_tags:
            href = a_tag.attrs.get('href')
            if not href:
                continue
            if href.startswith('javascript'):
                continue
            if self.validate_url(href):
                links.add(href)
            elif href.startswith('/'):
                href = self.parts.scheme + "://"+ self.domain + href
                if self.validate_url(href):
                    links.add(href)
            else:
                href = urljoin(url, href)
                if self.validate_url(href):
                    links.add(href)

        with open(self.url_dir_to_links(path_dir), "w", encoding="utf-8") as file:
            json.dump(list(links), file, indent=4)
        text_tags = soup.find_all(['p', "h1", "h2", "h3", "h4", "h5", "h6", 'span'])
        text = []
        for text_tag in text_tags:
            txt = text_tag.get_text()
            if txt:
                text.append(txt.lower())
        path_content = self.url_dir_to_content(path_dir)
        try:
            with open(path_content, "w", encoding="utf-8") as file:
                file.writelines(text)
        except:
            if os.path.exists(path_content):
                os.remove(path_content)
            raise

    def url_update_referencer(self, path_dir, referencer):
        if not referencer:
            return
        path_references = self.url_dir_to_references(path_dir)
        references_set = set()
        if os.path.exists(path_references):
            with open(path_references, "r") as file:
                references_set = set(json.load(file))
        references_set.add(referencer)
        with open(path_references, "w", encoding="utf-8") as file:
            json.dump(list(references_set), file)

    def url_handle_links(self, url, path_dir):
        links_set = set()
        path_link = self.url_dir_to_links(path_dir)
        if not os.path.exists(path_link):
            return
        with open(path_link, "r") as file:
            links_set = set(json.load(file))
        for link in links_set:
            path_dir = self.url_to_dir(link)
            path_html = self.url_dir_to_html(path_dir)
            if not os.path.exists(path_html):
                extracted = tldextract.extract(link)
                domain = f"{extracted.domain}.{extracted.suffix}"
                if domain == self.domain:
                    self.todo.add((link,url))



    def url_handler(self, url, referencer=None):
        print(f"handling url {url}")
        try:
            path_dir, is_downloaded = self.url_dump(url)
        except Exception as e:
            print(f"failed to handle url {url} {e}")
            return
        self.url_update_referencer(path_dir, referencer)

        if not is_downloaded:
            return
        self.url_parse_html(url, path_dir)
        self.url_handle_links(url, path_dir)


    def crawl(self):
        # url = sys.argv[2]

        while len(self.todo):
            url, referencer = self.todo.pop()
            self.url_handler(url, referencer)


    def url_keys_analytics(self, path_content, path_references, keys):
        text = ""
        with open(path_content, "r", encoding="utf-8") as file:
            text = file.read()
        res = {}
        res["keys"] = {}
        for key in keys:
            res["keys"][key] = text.count(key)

        references_set = set()
        if os.path.exists(path_references):
            with open(path_references, "r") as file:
                references_set = set(json.load(file))
        res["ref"] = len(references_set)
        return res

    def search_score(self, search_obj):
        count = 0
        for value in search_obj["keys"].values():
            if value == 0:
                return 0
            count += value
        count+= search_obj["ref"]
        return count


    def search(self, keys):
        new_keys = []
        for key in keys:
            new_keys.append(key.lower())
        keys = new_keys

        found_files = []
        for root, dirs, files in os.walk(self.root_dir):
            if "content.txt" in files:
                path_content = self.url_dir_to_content(root)
                path_references = self.url_dir_to_references(root)
                path_url = self.url_dir_to_url_file(root)
                with open(path_url, "r") as file:
                    url = file.read()
                res = self.url_keys_analytics(path_content, path_references, keys)
                score = self.search_score(res)
                if score == 0:
                    continue
                found_files.append((score,res,url))
                found_files = sorted(found_files, key=lambda x: x[0], reverse=True)
                if len(found_files) > 10:
                    found_files.pop()
        for url in found_files:
            print(f"{url[2]}, {url[0]}")




def usage():
    print(f"""
{sys.argv[0]} actions are
    1. dump <url>
    2. search <key words>
""")







def main():
    url = "https://www.w3schools.com/"
    context = CrawlerContext(url)
    context.crawl()
    #context.search(['php', 'Example'])


    return
    if len(sys.argv) <= 1:
        usage()
        return
    if sys.argv[1] == "dump":
        dump()
        return
    if sys.argv[1] == "search":
        search()
        return
    usage()



if __name__ == '__main__':
    main()