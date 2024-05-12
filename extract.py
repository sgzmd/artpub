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


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def cleanup_file_name(file_name):
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


def save_file(url, base_dir, img_dir) -> str:
    logging.debug(f"Downloading {url}")
    # Tries to guess the filename (e.g., "image.png")
    filename = cleanup_file_name(os.path.basename(url))
    # If no filename can be guessed, we can create a random one
    # You may want to improve this logic based on your needs
    if not filename:
        filename = "file"
    file_path = os.path.join(base_dir, img_dir, filename)
    url_path = os.path.join(img_dir, filename)
    # Check if file already exists
    if not os.path.isfile(file_path):
        r = requests.get(url)
        with open(file_path, "wb") as f:
            f.write(r.content)

    return url_path


def infer_title(art: newspaper.Article, args) -> str:
    if args.title:
        return args.title

    title = art.title
    if not title:
        title = art.url

    return title


def infer_file_name(art: newspaper.Article, args) -> str:
    if args.epub:
        return args.epub

    file_name = art.title
    if not file_name:
        file_name = art.url

    return cleanup_file_name(file_name) + ".epub"


def url_to_base_path(url):
    # Parse the original URL
    parsed_url = urlparse(url)

    # Extract the path and remove the last component if necessary
    path_components = parsed_url.path.split("/")
    if len(path_components) > 1:  # This check is to ensure there is a path to work with
        base_path = "/".join(path_components[:-1])  # Remove the last element
    else:
        base_path = parsed_url.path  # No change needed if there's nothing to remove

    # Create the new URL with the modified path
    new_url = parsed_url._replace(path=base_path + "/")  # Ensure the path ends with '/'
    return urlunparse(new_url)


def main():
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
        logging.info(f"Processing article URL {url}")
        response = requests.get(url, cookies=cookies)

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
            img_url = img["src"]
            img.attrs = {}
            if not img_url.startswith("http"):
                img_url = url_to_base_path(art.url) + "/" + img_url

            if img_url in image_names:
                img["src"] = image_names[img_url]
                continue

            img_data = requests.get(img_url).content
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
