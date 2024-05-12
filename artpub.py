#!/usr/bin/env python

import argparse
import logging

from article_processor import process_articles

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


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



if __name__ == "__main__":
    main()
