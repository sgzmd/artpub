#!/usr/bin/env python

import argparse
import logging
import os
import mimetypes

from urllib.parse import urlparse, urlunparse, unquote

from bs4 import BeautifulSoup
from lxml import etree
from ebooklib import epub

import newspaper
import magic
import requests

from requests.exceptions import RequestException

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


REQUEST_TIMEOUT = 5000

def fetch_image_data(img_url, retry_count=3, timeout_duration=5):
    """
    Fetches image data from a URL with retries and a timeout.

    Args:
    img_url (str): URL of the image to download.
    retry_count (int): Maximum number of retries.
    timeout_duration (int): Timeout for each request in seconds.

    Returns:
    bytes: The content of the image if successful, None otherwise.
    """
    logging.debug("Fetching image data from %s", img_url)
    attempts = 0
    while attempts < retry_count:
        try:
            # Make a GET request with a timeout
            response = requests.get(img_url, timeout=timeout_duration)
            # Check if the request was successful
            response.raise_for_status()
            return response.content
        except RequestException as e:
            print(f"Attempt {attempts + 1} failed: {e}")
            attempts += 1
            if attempts >= retry_count:
                print("Maximum retry attempts reached, failing gracefully.")
                return None

def cleanup_file_name(file_name):
    """
    Cleans up a file name by replacing certain characters and removing spaces.

    Args:
        file_name (str): The original file name.

    Returns:
        str: The cleaned up file name.
    """
    if file_name.find("%") != -1:
        file_name = unquote(file_name)
    return (
        file_name.replace(" ", "_")
        .replace(":", "")
        .replace("/", "")
        .replace("%", "")
        .replace("?", "")
        .replace("=", "")
    )


def infer_title(art: newspaper.Article, args) -> str:
    """
    Infer the title of an article.

    If the `args.title` argument is provided, it will be returned as the title.
    Otherwise, if the `art.title` is not empty, it will be returned as the title.
    If both `args.title` and `art.title` are empty, the `art.url` will be returned as the title.

    Args:
        art (newspaper.Article): The article object.
        args: Additional arguments.

    Returns:
        str: The inferred title of the article.
    """
    if args.title:
        return args.title

    title = art.title
    if not title:
        title = art.url

    return title


def infer_file_name(art: newspaper.Article, args) -> str:
    """
    This function infers the file name based on the provided newspaper article and arguments.
    
    Parameters:
    art (newspaper.Article): The article from which to infer the file name.
    args (argparse.Namespace): The arguments provided to the script.

    Returns:
    str: The inferred file name.
    """
    if args.epub:
        return args.epub

    file_name = art.title
    if not file_name:
        file_name = art.url

    return cleanup_file_name(file_name) + ".epub"



def url_to_base_path(url):
    """
    Convert a URL to a base path by removing the last component of the path, if necessary.

    Args:
        url (str): The URL to convert.

    Returns:
        str: The modified URL with the base path.

    Example:
        >>> url_to_base_path('https://example.com/path/to/file.html')
        'https://example.com/path/to/'

        >>> url_to_base_path('https://example.com')
        'https://example.com/'
    """
    parsed_url = urlparse(url)
    path_components = parsed_url.path.split("/")
    if len(path_components) > 1:
        base_path = "/".join(path_components[:-1])
    else:
        base_path = parsed_url.path
    new_url = parsed_url._replace(path=base_path + "/")
    return urlunparse(new_url)


def clean_unused_tags(soup: BeautifulSoup, tags: list[str]) -> BeautifulSoup:
    """
    Removes unused tags from the given BeautifulSoup object.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object representing the HTML document.
        tags (list[str]): A list of tags to be removed from the HTML document.

    Returns:
        BeautifulSoup: The modified BeautifulSoup object with the unused tags
        removed.
    """
    
    for tag in soup.find_all(tags):
        tag.decompose()
        
    return soup

def main():
    """
    Process URLs and generate an EPUB file.

    This function takes command line arguments, including a list of URLs to process,
    an output directory, verbosity level, cookies, and optional parameters for the
    EPUB file such as title and author. It downloads the articles from the URLs,
    extracts relevant information, and generates an EPUB file containing the articles.

    Args:
        --urls, -u (list[str]): List of URLs to process, each must start with http.
        --out_dir, -o (str): Relative or absolute path to output directory.
        --verbose, -v (int): Level of verbosity, default 0.
        --cookies, -c (str): Cookies to use for requests (e.g., "cookie1=value1; cookie2=value2").
        --epub, -e (str): Output file name (or infer from title if not provided).
        --title, -t (str): Title of the EPUB file (or infer from URL if not provided).
        --author, -a (str): Author of the EPUB file (or infer from article if not provided).

    Returns:
        None
    """
    parser = argparse.ArgumentParser(description="Process some URLs.")
    parser.add_argument(
        "--urls",
        "-u",
        nargs="+",
        required=True,
        help="List of URLs to process, each must start with http",
    )
    parser.add_argument(
        "--out_dir",
        "-o",
        type=str,
        required=True,
        help="Relative or absolute path to output directory",
    )
    parser.add_argument(
        "--verbose", "-v", type=int, default=0, help="Level of verbosity, default 0"
    )
    parser.add_argument(
        "--cookies",
        "-c",
        type=str,
        default=None,
        help='Cookies to use for requests (e.g., "cookie1=value1; cookie2=value2")',
    )

    # output epub file
    parser.add_argument(
        "--epub",
        "-e",
        type=str,
        default=None,
        help="Output file name (or infer from title if not provided)",
    )

    # title of the epub file
    parser.add_argument(
        "--title",
        "-t",
        type=str,
        default=None,
        help="Title of the epub file (or infer from URL if not provided)",
    )

    # author of the epub file
    parser.add_argument(
        "--author",
        "-a",
        type=str,
        default=None,
        help="Author of the epub file (or infer from article if not provided)",
    )

    args = parser.parse_args()

    # Set logging level based on verbosity
    if args.verbose == 0:
        logging.basicConfig(level=logging.WARNING)
    elif args.verbose == 1:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.DEBUG)

    process_articles(args)

def process_articles(args):
    """
    Process a list of article URLs and generate an EPUB book.

    Args:
        args (Namespace): Command-line arguments containing the URLs and output directory.

    Returns:
        None
    """
    urls = args.urls
    out_dir = args.out_dir

    cookies = (
        {x: y for x, y in [cookie.split("=") for cookie in args.cookies.split(";")]}
        if args.cookies
        else {}
    )

    # create outdir if it doesn't exist
    img_dir = os.path.join(out_dir, "img")
    if not os.path.exists(out_dir):
        os.makedirs(img_dir)

    articles: list[newspaper.Article] = []

    for url in urls:
        logging.info("Processing article URL %s", url)
        response = requests.get(url, cookies=cookies, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            downloaded = response.content
            config = newspaper.Config()
            config.MAX_TEXT = 1000000

            art = newspaper.Article(url)

            art.download(input_html=downloaded)
            art.parse()
            art.nlp()

            articles.append(art)

            xhtml = etree.tostring(art.clean_top_node, pretty_print=True).decode(
                "utf-8"
            )

            soup = BeautifulSoup(xhtml, "lxml")
            soup = clean_unused_tags(soup, 
                                     ["script", 
                                      "style", 
                                      "noscript", 
                                      "iframe",
                                      "source",
                                      "svg"])            

            for source in soup.find_all("source"):
                source.decompose()

            art.set_article_html(str(soup))

    book = epub.EpubBook()
    book.set_title(infer_title(articles[0], args))
    book.set_language(articles[0].meta_lang)

    authors = set()
    magic_mime = magic.Magic(mime=True)

    image_names = {}
    html_names = {}

    for art in articles:
        for auth in art.authors:
            if auth not in authors:
                authors.add(auth)
                book.add_author(auth)

        html = art.article_html

        soup = BeautifulSoup(html, "lxml")
        for img in soup.find_all("img"):
            if "src" in img.attrs:
                img_url = img["src"]
                img.attrs = {}
                if not img_url.startswith("http"):
                    img_url = url_to_base_path(art.url) + "/" + img_url

                if img_url in image_names:
                    img["src"] = image_names[img_url]
                    continue

                img_data = fetch_image_data(img_url)
                content_type = magic_mime.from_buffer(img_data)

                ext = mimetypes.guess_extension(content_type)
                file_name = "img/image_" + str(len(image_names)) + ext
                image_names[img_url] = file_name

                book.add_item(
                    epub.EpubItem(
                        file_name=file_name, media_type=content_type, content=img_data
                    )
                )

                img["src"] = file_name
            else:
                logging.debug("Image tag without src attribute: %s, skipping", str(img))

        html = str(soup)

        html_name = "article_" + str(len(html_names)) + ".html"
        html_names[html] = html_name

        eh = epub.EpubHtml(title=art.title, file_name=html_name)
        eh.content = html
        book.add_item(eh)
        book.toc.append(eh)

    spine = ["nav"]
    spine.extend([item for item in book.items if isinstance(item, epub.EpubHtml)])
    book.spine = spine

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    fn = infer_file_name(articles[0], args)
    epub.write_epub(os.path.join(out_dir, fn), book, {})


if __name__ == "__main__":
    main()
